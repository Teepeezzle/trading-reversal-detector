"""OHLCV data fetcher backed by yfinance.

Supports daily and intraday intervals (15m / 30m / 1h / 4h / 1d). Each
interval has its own yfinance ``period`` and its own cache TTL so that
fresh intraday bars are pulled often while daily bars are reused for hours.

The 4h interval is synthesised by fetching 1h bars and resampling — yfinance
does not expose a native 4h product.

Errors are appended to ``logs/fetch_errors.log`` (when ``error_log_path`` is
provided to the constructor) so transient yfinance/network failures don't
crash a scan but remain recoverable.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

# yfinance ``period`` per supported interval. The 4h entry is the period used
# for the underlying 1h fetch that we resample.
INTERVAL_PERIODS: Dict[str, str] = {
    "15m": "5d",
    "30m": "5d",
    "1h": "30d",
    "4h": "60d",
    "1d": "1y",
}

# Cache TTL per interval, in seconds. Daily bars are cached for 5 hours
# because they only refresh once per close; short intraday bars get short TTLs.
DEFAULT_INTERVAL_CACHE_SECONDS: Dict[str, int] = {
    "15m": 5 * 60,
    "30m": 10 * 60,
    "1h": 15 * 60,
    "4h": 30 * 60,
    "1d": 300 * 60,
}

# Pandas resample rule for the synthesised 4h bars.
RESAMPLE_4H_RULE = "4h"
RESAMPLE_AGG: Dict[str, str] = {
    "Open": "first",
    "High": "max",
    "Low": "min",
    "Close": "last",
    "Volume": "sum",
}


class DataFetcher:
    """Fetches OHLCV data from Yahoo Finance with per-interval caching.

    The cache key is ``(ticker, interval)`` so daily and intraday frames for
    the same ticker are tracked independently.
    """

    def __init__(
        self,
        interval_cache_overrides: Optional[Dict[str, int]] = None,
        error_log_path: Optional[Path] = None,
    ) -> None:
        """Initialise the fetcher.

        Args:
            interval_cache_overrides: Optional ``{interval: seconds}`` map that
                overrides the per-interval defaults.
            error_log_path: Optional absolute path to ``fetch_errors.log``.
                When set, every fetch failure is appended there with a UTC
                timestamp.
        """
        self._cache: Dict[Tuple[str, str], Tuple[float, pd.DataFrame]] = {}
        self._cache_durations: Dict[str, int] = dict(DEFAULT_INTERVAL_CACHE_SECONDS)
        if interval_cache_overrides:
            self._cache_durations.update(interval_cache_overrides)
        self._error_log_path: Optional[Path] = error_log_path

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def fetch_ohlcv(
        self,
        ticker: str,
        interval: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """Fetch (or return cached) OHLCV data for ``ticker`` at ``interval``.

        Args:
            ticker: A yfinance ticker symbol (e.g. ``"EURUSD=X"``, ``"GC=F"``).
            interval: One of ``"15m"``, ``"30m"``, ``"1h"``, ``"4h"``, ``"1d"``.

        Returns:
            A pandas ``DataFrame`` indexed by datetime with columns
            ``[Open, High, Low, Close, Volume]``, or ``None`` if the fetch
            failed, the interval is unknown, or yfinance returned no data.
        """
        if interval not in INTERVAL_PERIODS:
            self._log_error(
                ticker,
                interval,
                f"Unsupported interval '{interval}'. "
                f"Choose from {sorted(INTERVAL_PERIODS)}.",
            )
            return None

        cache_key = (ticker, interval)
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached is not None:
            ts, df = cached
            if now - ts < self._cache_durations.get(interval, 300):
                logger.debug(
                    "Cache hit for %s@%s (age %.1fs)", ticker, interval, now - ts
                )
                return df.copy()

        if interval == "4h":
            df = self._fetch_4h_via_resample(ticker)
        else:
            df = self._raw_fetch(ticker, interval=interval, period=INTERVAL_PERIODS[interval])

        if df is None or df.empty:
            return None

        self._cache[cache_key] = (now, df)
        logger.info("Fetched %d rows for %s@%s", len(df), ticker, interval)
        return df.copy()

    def clear_cache(self) -> None:
        """Drop every cached frame (forces fresh fetches on next call)."""
        self._cache.clear()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _raw_fetch(
        self,
        ticker: str,
        interval: str,
        period: str,
    ) -> Optional[pd.DataFrame]:
        """Pull a frame directly from yfinance and normalise its columns.

        Args:
            ticker: yfinance ticker symbol.
            interval: yfinance interval string.
            period: yfinance period string.

        Returns:
            A cleaned OHLCV DataFrame, or ``None`` on any failure.
        """
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
            self._log_error(ticker, interval, f"yfinance download exception: {exc}")
            return None

        if raw is None or raw.empty:
            self._log_error(ticker, interval, "yfinance returned an empty frame")
            return None

        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        missing = [c for c in OHLCV_COLUMNS if c not in raw.columns]
        if missing:
            self._log_error(ticker, interval, f"Missing columns from yfinance: {missing}")
            return None

        df = raw[OHLCV_COLUMNS].copy()
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        df["Volume"] = df["Volume"].fillna(0)

        if df.empty:
            self._log_error(ticker, interval, "Frame empty after cleaning")
            return None

        return df

    def _fetch_4h_via_resample(self, ticker: str) -> Optional[pd.DataFrame]:
        """Build a 4h frame by resampling 1h bars.

        Args:
            ticker: yfinance ticker symbol.

        Returns:
            A 4h OHLCV DataFrame, or ``None`` if the underlying 1h fetch failed.
        """
        hourly = self._raw_fetch(ticker, interval="1h", period=INTERVAL_PERIODS["4h"])
        if hourly is None or hourly.empty:
            return None

        try:
            resampled = hourly.resample(RESAMPLE_4H_RULE).agg(RESAMPLE_AGG)
        except Exception as exc:  # noqa: BLE001
            self._log_error(ticker, "4h", f"Resample to 4h failed: {exc}")
            return None

        resampled = resampled.dropna(subset=["Open", "High", "Low", "Close"])
        if resampled.empty:
            self._log_error(ticker, "4h", "4h frame empty after resampling")
            return None

        # REPAINT FIX: the cron fires mid-bucket (07:00/11:00/15:00/19:00 UTC),
        # so the final 4h bucket is almost always still forming. Acting on it is
        # lookahead — its OHLC changes before the candle truly closes. Drop the
        # last bucket unless the most recent 1h bar is its closing hour, so the
        # detector only ever sees COMPLETED 4h candles.
        last_bucket_start = resampled.index[-1]
        bucket_end = last_bucket_start + pd.Timedelta(RESAMPLE_4H_RULE)
        last_hour_start = hourly.index[-1]
        if last_hour_start < bucket_end - pd.Timedelta(hours=1):
            resampled = resampled.iloc[:-1]
        if resampled.empty:
            self._log_error(ticker, "4h", "no completed 4h bar available yet")
            return None

        return resampled

    def _log_error(self, ticker: str, interval: str, message: str) -> None:
        """Send an error to both the standard logger and ``fetch_errors.log``.

        Args:
            ticker: yfinance ticker symbol.
            interval: The interval being fetched.
            message: Human-readable error message.
        """
        full = f"{ticker}@{interval}: {message}"
        logger.error(full)
        if self._error_log_path is None:
            return
        try:
            self._error_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._error_log_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"{datetime.now(timezone.utc).isoformat()} | ERROR | {full}\n"
                )
        except Exception:  # noqa: BLE001
            # Don't let a logging failure mask the original error.
            pass
