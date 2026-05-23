"""Compute Daily / Weekly / Monthly / Yearly highs and lows.

The Daily reference is the *previous* completed candle (i.e. ``df.iloc[-2]``).
This lets the most-recent candle (``df.iloc[-1]``) potentially pierce and close
back inside that level — otherwise the pattern is circular (a candle cannot
pierce its own high or low).

Weekly / Monthly / Yearly are computed across the current period *excluding*
the most-recent candle, for the same reason.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PriceLevels:
    """Significant high/low reference levels for a single ticker.

    Attributes:
        ticker: Yahoo-Finance symbol the levels were computed for.
        daily_high: Previous complete daily candle's High.
        daily_low: Previous complete daily candle's Low.
        weekly_high: Highest High in the current ISO week (excluding the
            most-recent candle).
        weekly_low: Lowest Low in the current ISO week (excluding the
            most-recent candle).
        monthly_high: Highest High in the current calendar month (excluding
            the most-recent candle).
        monthly_low: Lowest Low in the current calendar month (excluding
            the most-recent candle).
        yearly_high: Highest High in the current calendar year (excluding
            the most-recent candle).
        yearly_low: Lowest Low in the current calendar year (excluding
            the most-recent candle).
    """

    ticker: str
    daily_high: float
    daily_low: float
    weekly_high: float
    weekly_low: float
    monthly_high: float
    monthly_low: float
    yearly_high: float
    yearly_low: float


def _safe_max(series: pd.Series, fallback: float) -> float:
    """Return the max of ``series`` or ``fallback`` if it's empty/all-NaN."""
    if series.empty:
        return fallback
    val = series.max()
    return float(val) if pd.notna(val) else fallback


def _safe_min(series: pd.Series, fallback: float) -> float:
    """Return the min of ``series`` or ``fallback`` if it's empty/all-NaN."""
    if series.empty:
        return fallback
    val = series.min()
    return float(val) if pd.notna(val) else fallback


def compute_price_levels(ticker: str, df: pd.DataFrame) -> PriceLevels:
    """Derive significant horizontal levels for a single ticker.

    Args:
        ticker: Yahoo-Finance symbol (used only for the returned dataclass).
        df: OHLCV frame with at least 2 rows; index must be a ``DatetimeIndex``.

    Returns:
        A populated ``PriceLevels`` instance.

    Raises:
        ValueError: If ``df`` has fewer than 2 rows or lacks a DatetimeIndex.
    """
    if df is None or len(df) < 2:
        raise ValueError(f"Need at least 2 rows of OHLCV data for {ticker}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"DataFrame for {ticker} must be DatetimeIndex-ed")

    # Daily reference = previous completed candle (so the current candle can
    # plausibly pierce it). df.iloc[-1] is "current", df.iloc[-2] is "previous".
    prev = df.iloc[-2]
    daily_high = float(prev["High"])
    daily_low = float(prev["Low"])

    # Reference point for "current period" — use the timestamp of the most-recent
    # row, not wall-clock now, so the function is deterministic on historical
    # data.
    ref_ts: pd.Timestamp = df.index[-1]

    # Strip the current candle for period aggregations so the level is
    # historical, not self-defining.
    history = df.iloc[:-1]

    # Current ISO week (Mon..Sun)
    week_start = ref_ts.normalize() - pd.Timedelta(days=ref_ts.weekday())
    week_mask = history.index >= week_start
    week_slice = history.loc[week_mask]

    # Current calendar month
    month_start = pd.Timestamp(year=ref_ts.year, month=ref_ts.month, day=1)
    month_mask = history.index >= month_start
    month_slice = history.loc[month_mask]

    # Current calendar year
    year_start = pd.Timestamp(year=ref_ts.year, month=1, day=1)
    year_mask = history.index >= year_start
    year_slice = history.loc[year_mask]

    return PriceLevels(
        ticker=ticker,
        daily_high=daily_high,
        daily_low=daily_low,
        weekly_high=_safe_max(week_slice["High"], daily_high),
        weekly_low=_safe_min(week_slice["Low"], daily_low),
        monthly_high=_safe_max(month_slice["High"], daily_high),
        monthly_low=_safe_min(month_slice["Low"], daily_low),
        yearly_high=_safe_max(year_slice["High"], daily_high),
        yearly_low=_safe_min(year_slice["Low"], daily_low),
    )
