"""Paper trading module for Binance Testnet with adaptive parameter management."""

import argparse
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from binance.client import Client
from binance.exceptions import BinanceAPIException

from src.alerts.telegram import TelegramBot
from src.backtest.rsi_strategy import RSIStrategy
from src.backtest.strategy import SMAStrategy
from src.config import ARTIFACTS_DIR, settings
from src.data.binance_client import BinanceDataClient
from src.filters.exchange_filters import ExchangeFilters
from src.models.position import PositionTracker
from src.monitoring.performance_tracker import PerformanceTracker
from src.risk.manager import RiskManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__, log_file="paper_trader.log")


class PaperTrader:
    """
    Execute paper trades on Binance Testnet with adaptive parameter management.

    Integrates:
    - Weekly re-optimization (parameter loading from JSON)
    - Performance monitoring (decay detection)
    - Risk management (kill-switch, position limits)
    """

    def __init__(
        self,
        testnet: bool = True,
        enable_risk_manager: bool = True,
        enable_performance_tracking: bool = True,
        enable_telegram: bool = True,
    ) -> None:
        """
        Initialize paper trader.

        Args:
            testnet: If True, use testnet. If False, use production (DANGEROUS)
            enable_risk_manager: Enable risk management validation
            enable_performance_tracking: Enable performance decay monitoring
            enable_telegram: Enable Telegram notifications
        """
        if not testnet:
            logger.critical("PRODUCTION MODE - REAL MONEY AT RISK!")
            if not settings.is_production:
                raise ValueError("Cannot use production without environment=live")

        self.testnet = testnet
        self.enable_risk_manager = enable_risk_manager
        self.enable_performance_tracking = enable_performance_tracking
        self.enable_telegram = enable_telegram

        # Initialize clients
        if testnet:
            self.client = Client(
                api_key=settings.binance_testnet_api_key,
                api_secret=settings.binance_testnet_api_secret,
                testnet=True,
            )
        else:
            self.client = Client(
                api_key=settings.binance_api_key,
                api_secret=settings.binance_api_secret,
            )

        self.data_client = BinanceDataClient(testnet=testnet)
        self.filters = ExchangeFilters(self.client)
        self.position_tracker = PositionTracker()

        # Telegram notifications (initialize BEFORE RiskManager)
        self.telegram: TelegramBot | None = None
        if enable_telegram:
            self.telegram = TelegramBot()
            if self.telegram.enabled:
                logger.info("Telegram notifications enabled")
            else:
                logger.warning("Telegram disabled: Missing token or chat_id in .env")

        # Risk management (with Telegram propagation)
        if enable_risk_manager:
            self.risk_manager = RiskManager(
                position_tracker=self.position_tracker,
                enable_telegram=enable_telegram,
                telegram_bot=self.telegram,
            )
            logger.info("RiskManager enabled")

        # Performance tracking
        if enable_performance_tracking:
            self.performance_tracker = PerformanceTracker(
                position_tracker=self.position_tracker,
                sharpe_threshold=1.0,
                critical_threshold=0.5,
                rolling_window_days=7,
            )
            logger.info("PerformanceTracker enabled")

        # Parameter management
        self.params_file = ARTIFACTS_DIR / "optimize" / "current_parameters.json"
        self.last_params_load: datetime | None = None
        self.current_params: dict[str, Any] = {}

        logger.info(f"PaperTrader initialized (testnet={testnet})")

    def load_parameters(self) -> dict[str, Any]:
        """
        Load current strategy parameters from JSON file.

        Returns:
            Dict with strategy type and parameters
        """
        if not self.params_file.exists():
            logger.warning(
                f"Parameters file not found: {self.params_file}. Using industry defaults."
            )
            return {
                "strategy": "RSI",
                "parameters": {
                    "rsi_period": 14,
                    "oversold": 30.0,
                    "overbought": 70.0,
                    "stop_loss": 3.0,
                },
                "optimized_at": None,
            }

        with open(self.params_file) as f:
            data = json.load(f)

        self.last_params_load = datetime.now()
        logger.info(
            f"Parameters loaded: {data.get('strategy', 'UNKNOWN')} "
            f"(optimized {data.get('optimized_at', 'never')})"
        )

        return data

    def check_parameter_reload(self) -> bool:
        """
        Check if parameters file has been updated since last load.

        Returns:
            True if parameters were reloaded
        """
        if not self.params_file.exists():
            return False

        # Check file modification time
        file_mtime = datetime.fromtimestamp(self.params_file.stat().st_mtime)

        # Reload if file updated after last load OR if never loaded
        if self.last_params_load is None or file_mtime > self.last_params_load:
            logger.info("Parameter file updated - reloading parameters")
            self.current_params = self.load_parameters()
            return True

        return False

    def get_account_balance(self, asset: str = "USDT") -> float:
        """
        Get account balance for specified asset.

        Args:
            asset: Asset symbol (e.g., "USDT", "BTC")

        Returns:
            Available balance
        """
        try:
            account = self.client.get_account()
            balance = next(
                (float(b["free"]) for b in account["balances"] if b["asset"] == asset),
                0.0,
            )
            logger.info(f"Balance for {asset}: {balance}")
            return balance

        except BinanceAPIException as e:
            logger.error(f"Failed to get balance: {e}")
            raise

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quote_qty: float,
    ) -> dict[Any, Any] | None:
        """
        Place a market order using quote quantity.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quote_qty: Amount in quote currency

        Returns:
            Order response or None if failed
        """
        try:
            # Prepare and validate order
            order_params = self.filters.prepare_market_order(
                symbol=symbol,
                side=side,
                quote_qty=quote_qty,
            )

            # Execute order
            logger.info(f"Placing order: {order_params}")
            response = self.client.create_order(**order_params)

            logger.info(f"Order executed: {response['orderId']}")
            logger.info(f"Status: {response['status']}")
            logger.info(f"Executed qty: {response.get('executedQty', 'N/A')}")

            return response

        except BinanceAPIException as e:
            logger.error(f"Order failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def run_strategy(
        self,
        symbol: str,
        timeframe: str,
        quote_amount: float,
        fast_window: int | None = None,
        slow_window: int | None = None,
    ) -> None:
        """
        Run strategy and execute trade if signal present.

        Loads parameters from JSON file if available, falls back to CLI args.
        Integrates risk management and performance tracking.

        Args:
            symbol: Trading pair
            timeframe: Candlestick timeframe
            quote_amount: Amount to trade in quote currency
            fast_window: Fast SMA window (overrides JSON params if provided)
            slow_window: Slow SMA window (overrides JSON params if provided)
        """
        logger.info(f"Running strategy for {symbol}")

        # Check for parameter updates (hot-reload)
        self.check_parameter_reload()

        # Load parameters if not already loaded
        if not self.current_params:
            self.current_params = self.load_parameters()

        # Extract strategy type and parameters
        strategy_type = self.current_params.get("strategy", "RSI")
        params = self.current_params.get("parameters", {})

        # Risk validation BEFORE fetching data
        if self.enable_risk_manager:
            is_valid, reason = self.risk_manager.validate_trade(
                symbol=symbol, quote_qty=quote_amount
            )
            if not is_valid:
                logger.warning(f"Risk check failed: {reason}")

                # Send Telegram kill-switch alert if daily loss limit exceeded
                if "KILL-SWITCH" in reason and self.enable_telegram and self.telegram.enabled:
                    daily_loss = self.risk_manager.get_daily_pnl()
                    self.telegram.send_message_sync(
                        "🚨 *KILL-SWITCH TRIGGERED* 🚨\n\n"
                        "*Daily Loss Limit Exceeded*\n"
                        f"Current Loss: `{daily_loss:.2f} USDT`\n"
                        f"Limit: `{self.risk_manager.max_daily_loss:.2f} USDT`\n\n"
                        "⛔ *TRADING HALTED* ⛔\n"
                        f"Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                        "Action Required: Review logs and adjust strategy parameters"
                    )

                return

        # Fetch recent data
        if strategy_type == "SMA":
            fast = fast_window or params.get("fast_window", 20)
            slow = slow_window or params.get("slow_window", 50)
            limit = max(slow + 10, 100)
        else:  # RSI
            rsi_period = params.get("rsi_period", 14)
            limit = max(rsi_period + 50, 100)

        df = self.data_client.get_historical_klines(
            symbol=symbol,
            interval=timeframe,
            limit=limit,
        )

        # Generate signals based on strategy type
        if strategy_type == "SMA":
            fast = fast_window or params.get("fast_window", 20)
            slow = slow_window or params.get("slow_window", 50)
            strategy = SMAStrategy(fast_window=fast, slow_window=slow)
            entries, exits = strategy.generate_signals(df)
            logger.info(f"Using SMA strategy: fast={fast}, slow={slow}")
        else:  # RSI (default from weekly re-opt)
            rsi_strategy = RSIStrategy(
                rsi_period=params.get("rsi_period", 14),
                oversold_threshold=params.get("oversold", 30.0),
                overbought_threshold=params.get("overbought", 70.0),
                stop_loss_pct=params.get("stop_loss", 3.0),
            )
            entries, exits = rsi_strategy.generate_signals(df)
            logger.info(
                f"Using RSI strategy: period={params.get('rsi_period', 14)}, "
                f"oversold={params.get('oversold', 30.0)}, "
                f"overbought={params.get('overbought', 70.0)}"
            )

        # Check latest signal
        latest_entry = entries.iloc[-1]
        latest_exit = exits.iloc[-1]

        # Get current position status
        has_position = self.position_tracker.has_open_position(symbol)

        if latest_entry and not has_position:
            logger.info("Entry signal detected - placing BUY order")
            response = self.place_market_order(symbol, "BUY", quote_amount)

            if response and response.get("status") == "FILLED":
                # Track the opened position
                executed_qty = Decimal(response["executedQty"])
                # Calculate average fill price
                cum_quote = Decimal(response["cummulativeQuoteQty"])
                avg_price = cum_quote / executed_qty

                self.position_tracker.open_position(
                    symbol=symbol,
                    quantity=executed_qty,
                    entry_price=avg_price,
                    order_id=str(response["orderId"]),
                )
                logger.info(f"Position opened: {executed_qty} @ {avg_price}")

        elif latest_exit and has_position:
            logger.info("Exit signal detected - placing SELL order")
            position = self.position_tracker.get_open_position(symbol)

            if position:
                # Sell the entire position
                # For market SELL, we need to specify quantity in base currency
                response = self.client.create_order(
                    symbol=symbol,
                    side="SELL",
                    type="MARKET",
                    quantity=float(position.quantity),
                )

                if response and response.get("status") == "FILLED":
                    # Calculate average exit price
                    cum_quote = Decimal(response["cummulativeQuoteQty"])
                    executed_qty = Decimal(response["executedQty"])
                    avg_exit_price = cum_quote / executed_qty

                    # Close position
                    self.position_tracker.close_position(
                        symbol=symbol,
                        exit_price=avg_exit_price,
                        exit_order_id=str(response["orderId"]),
                    )
                    logger.info(f"Position closed @ {avg_exit_price}")

        elif latest_entry and has_position:
            logger.info("Entry signal detected but position already open - skipping")

        elif latest_exit and not has_position:
            logger.info("Exit signal detected but no position open - skipping")

        else:
            logger.info("No signal - no trade")

        # Performance monitoring (if enabled)
        if self.enable_performance_tracking:
            self._monitor_performance()

    def _monitor_performance(self) -> None:
        """
        Monitor performance and check for decay.

        Logs performance snapshot and checks if re-optimization needed.
        """
        metrics = self.performance_tracker.get_performance_metrics()

        logger.info(
            f"Performance: Sharpe(7d)={metrics['rolling_sharpe']['7d']:.2f}, "
            f"WinRate={metrics['win_rate_7d']:.1f}%, "
            f"AvgPnL={metrics['avg_pnl_7d']:.2f}"
        )

        # Check for decay
        is_decaying, severity, sharpe = self.performance_tracker.detect_decay()

        if is_decaying:
            logger.warning(f"⚠️ Performance decay detected: {severity} (Sharpe={sharpe:.2f})")

            # Send Telegram alert for parameter decay
            if self.enable_telegram and self.telegram.enabled:
                threshold = (
                    self.performance_tracker.critical_threshold
                    if severity == "CRITICAL"
                    else self.performance_tracker.sharpe_threshold
                )
                self.telegram.send_message_sync(
                    f"{'🚨' if severity == 'CRITICAL' else '⚠️'} *PARAMETER DECAY: {severity}*\n\n"
                    f"Current Sharpe: `{sharpe:.4f}`\n"
                    f"Threshold: `{threshold:.4f}`\n\n"
                    f"Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
                )

            # Check if immediate re-optimization needed
            should_trigger, reason = self.performance_tracker.should_trigger_reoptimization()
            if should_trigger:
                logger.critical(f"🚨 RE-OPTIMIZATION REQUIRED: {reason}")

        # Log snapshot every run
        self.performance_tracker.log_performance_snapshot()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run paper trading on Binance Testnet")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair")
    parser.add_argument("--quote", type=float, default=10.0, help="Quote amount (USDT)")
    parser.add_argument("--tf", type=str, default="1h", help="Timeframe")
    parser.add_argument("--fast", type=int, default=20, help="Fast SMA window")
    parser.add_argument("--slow", type=int, default=50, help="Slow SMA window")
    parser.add_argument("--prod", action="store_true", help="Use PRODUCTION (DANGEROUS)")

    args = parser.parse_args()

    if args.prod:
        confirm = input("⚠️  WARNING: Use PRODUCTION API? (type 'YES' to confirm): ")
        if confirm != "YES":
            print("Cancelled.")
            return

    trader = PaperTrader(testnet=not args.prod)

    # Show balance
    balance = trader.get_account_balance("USDT")
    print(f"Account balance: {balance} USDT\n")

    # Run strategy
    trader.run_strategy(
        symbol=args.symbol,
        timeframe=args.tf,
        quote_amount=args.quote,
        fast_window=args.fast,
        slow_window=args.slow,
    )


if __name__ == "__main__":
    main()
