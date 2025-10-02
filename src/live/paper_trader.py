"""Paper trading module for Binance Testnet."""

import argparse
from decimal import Decimal
from typing import Optional

from binance.client import Client
from binance.exceptions import BinanceAPIException

from src.backtest.strategy import SMAStrategy
from src.config import settings
from src.data.binance_client import BinanceDataClient
from src.filters.exchange_filters import ExchangeFilters
from src.models.position import PositionTracker
from src.utils.logger import setup_logger

logger = setup_logger(__name__, log_file="paper_trader.log")


class PaperTrader:
    """Execute paper trades on Binance Testnet."""

    def __init__(self, testnet: bool = True) -> None:
        """
        Initialize paper trader.

        Args:
            testnet: If True, use testnet. If False, use production (DANGEROUS)
        """
        if not testnet:
            logger.critical("PRODUCTION MODE - REAL MONEY AT RISK!")
            if not settings.is_production:
                raise ValueError("Cannot use production without environment=live")

        self.testnet = testnet

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

        logger.info(f"PaperTrader initialized (testnet={testnet})")

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
    ) -> Optional[dict]:
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
        fast_window: int = 20,
        slow_window: int = 50,
    ) -> None:
        """
        Run strategy and execute trade if signal present.

        Args:
            symbol: Trading pair
            timeframe: Candlestick timeframe
            quote_amount: Amount to trade in quote currency
            fast_window: Fast SMA window
            slow_window: Slow SMA window
        """
        logger.info(f"Running strategy for {symbol}")

        # Fetch recent data
        df = self.data_client.get_historical_klines(
            symbol=symbol,
            interval=timeframe,
            limit=max(slow_window + 10, 100),
        )

        # Generate signals
        strategy = SMAStrategy(fast_window=fast_window, slow_window=slow_window)
        entries, exits = strategy.generate_signals(df)

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
