"""Binance API client wrapper for data fetching."""

import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class BinanceDataClient:
    """Wrapper for Binance client with testnet support."""

    def __init__(self, testnet: bool = True) -> None:
        """
        Initialize Binance client.

        Args:
            testnet: If True, use testnet API. If False, use production API.
        """
        self.testnet = testnet

        if testnet:
            # Testnet requires API keys
            self.client = Client(
                api_key=settings.binance_testnet_api_key,
                api_secret=settings.binance_testnet_api_secret,
                testnet=True,
            )
            logger.info("Initialized Binance TESTNET client")
        else:
            # Production - use empty keys for public endpoints (historical data)
            # API keys only needed for private endpoints (account info, orders)
            api_key = settings.binance_api_key if settings.binance_api_key else ""
            api_secret = settings.binance_api_secret if settings.binance_api_secret else ""
            self.client = Client(api_key=api_key, api_secret=api_secret)
            if api_key:
                logger.warning("Initialized Binance PRODUCTION client with API keys")
            else:
                logger.info("Initialized Binance PRODUCTION client (public endpoints only)")

    def get_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_str: str | None = None,
        end_str: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch historical klines (candlestick) data with automatic pagination.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Kline interval (e.g., "1h", "4h", "1d")
            start_str: Start date string (e.g., "1 Jan, 2024" or "90 days ago UTC")
            end_str: End date string (optional)
            limit: Number of klines to fetch (None = fetch all available, auto-paginates)

        Returns:
            DataFrame with OHLCV data

        Note:
            Binance has a 1000 candle limit per request. If limit > 1000 or limit=None,
            this method automatically paginates to fetch all requested data.
        """
        try:
            # If limit is None or > 1000, use python-binance's automatic pagination
            # by NOT passing a limit parameter (fetches all data between start_str and end_str)
            if limit is None or limit > 1000:
                klines = self.client.get_historical_klines(
                    symbol=symbol,
                    interval=interval,
                    start_str=start_str,
                    end_str=end_str,
                    # No limit parameter = fetch all
                )
            else:
                klines = self.client.get_historical_klines(
                    symbol=symbol,
                    interval=interval,
                    start_str=start_str,
                    end_str=end_str,
                    limit=limit,
                )

            df = pd.DataFrame(
                klines,
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "close_time",
                    "quote_volume",
                    "trades",
                    "taker_buy_base",
                    "taker_buy_quote",
                    "ignore",
                ],
            )

            # Convert types
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            logger.info(f"Fetched {len(df)} klines for {symbol} ({interval})")
            return df

        except BinanceAPIException as e:
            logger.error(f"Binance API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching klines: {e}")
            raise
