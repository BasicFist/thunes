"""Integration tests for PaperTrader with adaptive parameter management."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from src.live.paper_trader import PaperTrader


@pytest.fixture
def temp_params_file() -> Path:
    """Create temporary parameters file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        params = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "strategy": "RSI",
            "parameters": {
                "rsi_period": 14,
                "oversold": 30.0,
                "overbought": 70.0,
                "stop_loss": 3.0,
            },
            "metrics": {"sharpe_ratio": 2.5, "n_trials": 25},
            "optimized_at": "2025-10-01T10:00:00",
            "optimization_data_period": "2025-09-01 to 2025-10-01",
            "lookback_days": 30,
        }
        json.dump(params, f, indent=2)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def mock_binance_client() -> MagicMock:
    """Mock Binance client."""
    client = MagicMock()
    client.get_account.return_value = {
        "balances": [{"asset": "USDT", "free": "1000.0", "locked": "0.0"}]
    }
    client.get_exchange_info.return_value = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.00001"},
                    {"filterType": "NOTIONAL", "minNotional": "10.0"},
                ],
            }
        ]
    }
    return client


@pytest.fixture
def mock_data_client() -> MagicMock:
    """Mock data client."""
    data_client = MagicMock()
    # Return sample OHLCV data
    data_client.get_historical_klines.return_value = pd.DataFrame(
        {
            "open": [50000.0] * 100,
            "high": [51000.0] * 100,
            "low": [49000.0] * 100,
            "close": [50000.0] * 100,
            "volume": [1000.0] * 100,
        }
    )
    return data_client


def test_initialization(mock_binance_client: MagicMock) -> None:
    """Test PaperTrader initialization with all components."""
    with patch("src.live.paper_trader.Client", return_value=mock_binance_client):
        trader = PaperTrader(
            testnet=True, enable_risk_manager=True, enable_performance_tracking=True
        )

        assert trader.testnet is True
        assert trader.enable_risk_manager is True
        assert trader.enable_performance_tracking is True
        assert hasattr(trader, "risk_manager")
        assert hasattr(trader, "performance_tracker")
        assert hasattr(trader, "position_tracker")


def test_load_parameters_from_file(temp_params_file: Path) -> None:
    """Test loading parameters from JSON file."""
    with (
        patch("src.live.paper_trader.Client"),
        patch("src.live.paper_trader.ARTIFACTS_DIR", temp_params_file.parent),
    ):
        trader = PaperTrader(
            testnet=True, enable_risk_manager=False, enable_performance_tracking=False
        )
        trader.params_file = temp_params_file

        params = trader.load_parameters()

        assert params["strategy"] == "RSI"
        assert params["parameters"]["rsi_period"] == 14
        assert params["parameters"]["oversold"] == 30.0
        assert params["parameters"]["overbought"] == 70.0
        assert params["optimized_at"] == "2025-10-01T10:00:00"


def test_load_parameters_fallback_to_defaults():
    """Test fallback to industry defaults when file missing."""
    with patch("src.live.paper_trader.Client"):
        trader = PaperTrader(
            testnet=True, enable_risk_manager=False, enable_performance_tracking=False
        )
        trader.params_file = Path("/nonexistent/path/params.json")

        params = trader.load_parameters()

        # Should return industry defaults
        assert params["strategy"] == "RSI"
        assert params["parameters"]["rsi_period"] == 14
        assert params["parameters"]["oversold"] == 30.0
        assert params["optimized_at"] is None


def test_parameter_hot_reload(temp_params_file: Path) -> None:
    """Test hot-reload when parameters file is updated."""
    with (
        patch("src.live.paper_trader.Client"),
        patch("src.live.paper_trader.ARTIFACTS_DIR", temp_params_file.parent),
    ):
        trader = PaperTrader(
            testnet=True, enable_risk_manager=False, enable_performance_tracking=False
        )
        trader.params_file = temp_params_file

        # First load
        params1 = trader.load_parameters()
        assert params1["parameters"]["rsi_period"] == 14

        # Update file
        with open(temp_params_file) as f:
            data = json.load(f)
        data["parameters"]["rsi_period"] = 20  # Change parameter
        with open(temp_params_file, "w") as f:
            json.dump(data, f)

        # Check reload
        reloaded = trader.check_parameter_reload()
        assert reloaded is True
        assert trader.current_params["parameters"]["rsi_period"] == 20


def test_run_strategy_with_risk_manager_blocking(
    mock_binance_client: MagicMock, mock_data_client: MagicMock
) -> None:
    """Test that RiskManager blocks trades when limits exceeded."""
    with (
        patch("src.live.paper_trader.Client", return_value=mock_binance_client),
        patch("src.live.paper_trader.BinanceDataClient", return_value=mock_data_client),
    ):
        trader = PaperTrader(
            testnet=True, enable_risk_manager=True, enable_performance_tracking=False
        )

        # Mock risk manager to block trade
        trader.risk_manager.validate_trade = Mock(  # Fixed method name
            return_value=(False, "KILL_SWITCH: Daily loss limit exceeded")
        )

        # Should not execute any orders
        trader.run_strategy(symbol="BTCUSDT", timeframe="1h", quote_amount=10.0)

        # Verify no orders placed
        mock_binance_client.create_order.assert_not_called()


def test_run_strategy_with_rsi_parameters(
    mock_binance_client: MagicMock, mock_data_client: MagicMock, temp_params_file: Path
) -> None:
    """Test strategy execution with RSI parameters from JSON."""
    with (
        patch("src.live.paper_trader.Client", return_value=mock_binance_client),
        patch("src.live.paper_trader.BinanceDataClient", return_value=mock_data_client),
        patch("src.live.paper_trader.ARTIFACTS_DIR", temp_params_file.parent),
    ):
        trader = PaperTrader(
            testnet=True, enable_risk_manager=False, enable_performance_tracking=False
        )
        trader.params_file = temp_params_file
        trader.current_params = trader.load_parameters()

        # Should use RSI strategy from JSON
        trader.run_strategy(symbol="BTCUSDT", timeframe="1h", quote_amount=10.0)

        # Verify data fetched with correct limit (rsi_period + 50)
        mock_data_client.get_historical_klines.assert_called_once()
        call_kwargs = mock_data_client.get_historical_klines.call_args.kwargs
        assert call_kwargs["limit"] >= 64  # 14 + 50


def test_performance_monitoring_integration(
    mock_binance_client: MagicMock, mock_data_client: MagicMock
) -> None:
    """Test performance monitoring after trade execution."""
    with (
        patch("src.live.paper_trader.Client", return_value=mock_binance_client),
        patch("src.live.paper_trader.BinanceDataClient", return_value=mock_data_client),
    ):
        trader = PaperTrader(
            testnet=True, enable_risk_manager=False, enable_performance_tracking=True
        )

        # Mock performance tracker methods
        perf_tracker = trader.performance_tracker
        perf_tracker.get_performance_metrics = Mock(
            return_value={
                "rolling_sharpe": {"1d": 0.5, "3d": 0.6, "7d": 0.7},
                "win_rate_7d": 55.0,
                "avg_pnl_7d": 5.0,
                "total_trades": 10,
                "total_pnl": 50.0,
                "decay_detected": False,
                "decay_severity": "OK",
                "requires_reoptimization": False,
            }
        )
        perf_tracker.detect_decay = Mock(return_value=(False, "OK", 0.7))
        perf_tracker.log_performance_snapshot = Mock()

        # Run strategy
        trader.run_strategy(symbol="BTCUSDT", timeframe="1h", quote_amount=10.0)

        # Verify performance tracking called
        perf_tracker.get_performance_metrics.assert_called_once()
        perf_tracker.detect_decay.assert_called_once()
        perf_tracker.log_performance_snapshot.assert_called_once()


def test_get_account_balance(mock_binance_client: MagicMock) -> None:
    """Test balance retrieval."""
    with patch("src.live.paper_trader.Client", return_value=mock_binance_client):
        trader = PaperTrader(
            testnet=True, enable_risk_manager=False, enable_performance_tracking=False
        )

        balance = trader.get_account_balance("USDT")

        assert balance == 1000.0
        mock_binance_client.get_account.assert_called_once()
