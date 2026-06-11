"""Validated daily long-breakout detector — the one edge that passed every test.

Backtest pedigree (see backtest/ for reproducible scripts):
  * In-sample positive on BTC/Gold/Oil.
  * Out-of-sample validated (trained on old data, tested on unseen years).
  * Walk-forward stable: every 3-year block over 2000-2026 positive; fixed
    parameters beat re-optimization (not curve-fit).
  * Portfolio over 26 years / 6 assets: PF 1.62, max drawdown -10.2%.

Rules (do NOT optimize — the fixed values are what survived out-of-sample):
  * Regime : ADX(14) < 20  (a low-ADX consolidation that is breaking out)
  * Entry  : Close > Donchian-high(20) of the PRIOR bar  (breakout up)
  * Macro  : Close > SMA(200)  (only long in an established uptrend)
  * Risk   : SL = 1.5 x ATR(14), TP = 3.0 x ATR(14)  (1:2)
Timeframe is DAILY — the edge does not survive intraday (tested: 1h loses, 4h
is marginal/unvalidated).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

# Fixed, validated parameters. These are intentionally not exposed as tunables
# in the detector — re-optimizing them reintroduces curve-fit (proven in the
# walk-forward test).
ADX_PERIOD = 14
ADX_RANGING = 20.0
DONCHIAN = 20
MACRO_SMA = 200
ATR_PERIOD = 14
SL_ATR_MULT = 1.5
TP_ATR_MULT = 3.0
MIN_BARS = MACRO_SMA + 5


@dataclass
class BreakoutSignal:
    """A validated daily long-breakout signal for one ticker.

    Attributes:
        ticker: Yahoo-Finance symbol.
        ticker_display_name: Human-readable name.
        direction: Always ``"LONG"`` (the validated edge is long-only).
        entry_price: Breakout bar's close.
        stop_loss: ``entry - 1.5 * ATR``.
        take_profit: ``entry + 3.0 * ATR`` (1:2 R:R).
        atr: Latest ATR(14).
        adx: Latest ADX(14) (the regime reading at the signal).
        donchian_high: The 20-bar Donchian high that was broken.
        sma200: The 200-bar SMA (macro trend reference).
        risk_per_unit: Price distance from entry to stop.
        timestamp: UTC time the signal was generated.
    """

    ticker: str
    ticker_display_name: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    atr: float
    adx: float
    donchian_high: float
    sma200: float
    risk_per_unit: float
    timestamp: datetime


def _wilder(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing (EMA with alpha = 1/period)."""
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def compute_adx(df: pd.DataFrame, period: int = ADX_PERIOD) -> pd.Series:
    """Compute the Wilder ADX(period).

    Args:
        df: OHLCV frame with ``High``, ``Low``, ``Close``.
        period: Smoothing period. Defaults to 14.

    Returns:
        ADX series (0-100).
    """
    up = df["High"].diff()
    down = -df["Low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = _wilder(tr, period)
    plus_di = 100 * _wilder(pd.Series(plus_dm, index=df.index), period) / atr
    minus_di = 100 * _wilder(pd.Series(minus_dm, index=df.index), period) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return _wilder(dx.fillna(0), period)


def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """Compute Wilder ATR(period).

    Args:
        df: OHLCV frame with ``High``, ``Low``, ``Close``.
        period: Smoothing period. Defaults to 14.

    Returns:
        ATR series (>= 0).
    """
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return _wilder(tr, period).clip(lower=0.0)


def detect_breakout(
    ticker: str,
    ticker_name: str,
    df: pd.DataFrame,
) -> Optional[BreakoutSignal]:
    """Detect a validated daily long-breakout on the most-recent closed bar.

    All conditions are evaluated on the last row of ``df`` (which must be a
    completed daily candle). The Donchian high uses the *prior* bar's 20-bar
    high so the breakout is a genuine new high, not self-referential.

    Args:
        ticker: Yahoo-Finance symbol.
        ticker_name: Human-readable display name.
        df: Daily OHLCV frame, oldest-first, with a DatetimeIndex and at least
            ``MIN_BARS`` rows.

    Returns:
        A :class:`BreakoutSignal` if all conditions pass on the latest bar,
        otherwise ``None``.
    """
    if df is None or len(df) < MIN_BARS:
        return None

    adx = compute_adx(df)
    atr = compute_atr(df)
    sma200 = df["Close"].rolling(MACRO_SMA).mean()
    donchian_high_prev = df["High"].rolling(DONCHIAN).max().shift(1)

    last = -1
    close = float(df["Close"].iloc[last])
    a = float(atr.iloc[last]) if pd.notna(atr.iloc[last]) else float("nan")
    adx_val = float(adx.iloc[last]) if pd.notna(adx.iloc[last]) else float("nan")
    sma_val = float(sma200.iloc[last]) if pd.notna(sma200.iloc[last]) else float("nan")
    dhigh = float(donchian_high_prev.iloc[last]) if pd.notna(donchian_high_prev.iloc[last]) else float("nan")

    if not all(np.isfinite([close, a, adx_val, sma_val, dhigh])) or a <= 0:
        return None

    # The three validated conditions.
    regime_ok = adx_val < ADX_RANGING
    breakout_ok = close > dhigh
    macro_ok = close > sma_val
    if not (regime_ok and breakout_ok and macro_ok):
        return None

    risk = SL_ATR_MULT * a
    return BreakoutSignal(
        ticker=ticker,
        ticker_display_name=ticker_name,
        direction="LONG",
        entry_price=close,
        stop_loss=close - risk,
        take_profit=close + TP_ATR_MULT * a,
        atr=a,
        adx=adx_val,
        donchian_high=dhigh,
        sma200=sma_val,
        risk_per_unit=risk,
        timestamp=datetime.now(timezone.utc),
    )
