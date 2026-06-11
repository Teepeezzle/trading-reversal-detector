"""Overnight metals drift — a separate, validated short-hold edge.

The "night effect": holding from the daily close to the next open captures a
small but persistent positive drift in precious metals. Validated net-of-cost
and out-of-sample on ~25 years of daily data (see backtest/expand_validate.py):

    Gold   : +0.026%/night net, Sharpe 0.64, holds OOS
    Silver : +0.060%/night net, Sharpe 0.67, holds OOS (stronger out-of-sample)

Platinum and Copper were negative and are excluded. This is NOT intraday
day-trading — it is an overnight hold (a few hours), best run on low-cost
futures where the per-night edge clears execution costs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

# Per-night net-of-cost drift observed in validation (for context/sizing hints).
VALIDATED_DRIFT = {"GC=F": 0.00026, "SI=F": 0.00060}
MIN_BARS = 30


@dataclass
class OvernightSignal:
    """A long-overnight signal for a metal (enter at close, exit next open).

    Attributes:
        ticker: Yahoo-Finance symbol.
        market_name: Human-readable name.
        direction: Always ``"LONG"`` (the drift is long-biased).
        entry_close: The most-recent daily close (suggested entry).
        expected_drift_pct: Validated net per-night drift, as a percent.
        atr: Latest ATR(14), for optional risk sizing / gap awareness.
        timestamp: UTC time the signal was generated.
    """

    ticker: str
    market_name: str
    direction: str
    entry_close: float
    expected_drift_pct: float
    atr: float
    timestamp: datetime


def _wilder(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ATR(period) for the metal (used for gap-risk context)."""
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return _wilder(tr, period)


def build_overnight_signal(
    ticker: str, market_name: str, df: pd.DataFrame
) -> Optional[OvernightSignal]:
    """Build the long-overnight signal for a metal from its daily frame.

    The drift is unconditional (long every night), so this always returns a
    signal when data is sufficient — it is a daily *reminder + context*, not a
    conditional pattern. Run it near the daily close.

    Args:
        ticker: Yahoo-Finance symbol (should be ``GC=F`` or ``SI=F``).
        market_name: Human-readable name.
        df: Daily OHLCV frame (oldest-first), >= ``MIN_BARS`` rows.

    Returns:
        An :class:`OvernightSignal`, or ``None`` if data is insufficient or the
        ticker is not a validated overnight market.
    """
    if df is None or len(df) < MIN_BARS:
        return None
    if ticker not in VALIDATED_DRIFT:
        return None
    close = float(df["Close"].iloc[-1])
    atr = compute_atr(df)
    atr_val = float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else float("nan")
    if not np.isfinite(close) or close <= 0:
        return None
    return OvernightSignal(
        ticker=ticker,
        market_name=market_name,
        direction="LONG",
        entry_close=close,
        expected_drift_pct=VALIDATED_DRIFT[ticker] * 100.0,
        atr=atr_val,
        timestamp=datetime.now(timezone.utc),
    )
