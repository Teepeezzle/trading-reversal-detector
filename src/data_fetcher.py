"""OHLCV data fetcher backed by yfinance with an in-memory TTL cache."""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


class DataFetcher:
    """Fetches daily OHLCV data from Yahoo Finance with per-ticker caching.

    The cache is an instance attribute (no module-level mutable state). Each
    cached entry is a ``(timestamp, dataframe)`` tuple and is considered fresh
    while ``time.time() - timestamp < cache_duration_seconds``.
    """

    def __init__(self, cache_duration_seconds: int = 300) -> None:
        """Initialise the fetcher.

        Args:
            cache_duration_seconds: How long (seconds) a cached frame is reused
                before a fresh fetch is performed. Defaults to 300 (5 minutes).
        """
        self._cache: Dict[str, Tuple[float, pd.DataFrame]] = {}
        self._cache_duration: int = int(cache_duration_seconds)

    def fetch_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """Fetch (or return cached) daily OHLCV data for ``ticker``.

        Args:
            ticker: A yfinance ticker symbol (e.g. ``"EURUSD=X"``, ``"GC=F"``).
            period: yfinance period string. Defaults to ``"1y"``.
            interval: yfinance interval string. Defaults to ``"1d"``.

        Returns:
            A pandas ``DataFrame`` indexed by date with columns
            ``[Open, High, Low, Close, Volume]``, or ``None`` if the fetch
            failed or returned no data.
        """
        now = time.time()
        cached = self._cache.get(ticker)
        if cached is not None:
            ts, df = cached
            if now - ts < self._cache_duration:
                logger.debug("Cache hit for %s (age %.1fs)", ticker, now - ts)
                return df.copy()

        try:
            raw = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("yfinance download failed for %s: %s", ticker, exc)
            return None

        if raw is None or raw.empty:
            logger.warning("No data returned for %s", ticker)
            return None

        # yfinance can return a MultiIndex columns frame (level 0 = field,
        # level 1 = ticker). Flatten to a plain column index.
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        missing = [c for c in OHLCV_COLUMNS if c not in raw.columns]
        if missing:
            logger.error("Missing columns for %s: %s", ticker, missing)
            return None

        df = raw[OHLCV_COLUMNS].copy()
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        df["Volume"] = df["Volume"].fillna(0)

        if df.empty:
            logger.warning("Frame empty after cleaning for %s", ticker)
            return None

        self._cache[ticker] = (now, df)
        logger.info("Fetched %d rows for %s", len(df), ticker)
        return df.copy()

    def clear_cache(self) -> None:
        """Drop every cached frame (forces fresh fetches on next call)."""
        self._cache.clear()
