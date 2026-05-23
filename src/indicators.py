"""Technical indicators: Wilder RSI(14), Wilder ATR(14), and Volume SMA(20)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Indicators:
    """Snapshot of the most-recent indicator values plus the full series.

    Attributes:
        rsi: Latest RSI(14) value.
        atr: Latest ATR(14) value (always >= 0).
        volume_ma: Latest 20-period simple moving average of volume.
        rsi_series: Full RSI(14) series (same index as the source frame).
        atr_series: Full ATR(14) series.
        volume_ma_series: Full Volume MA(20) series.
    """

    rsi: float
    atr: float
    volume_ma: float
    rsi_series: pd.Series
    atr_series: pd.Series
    volume_ma_series: pd.Series


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute the Wilder RSI.

    Uses an EMA with ``alpha = 1/period`` (Wilder's smoothing) on average gains
    and losses derived from successive close-price differences.

    Args:
        close: Series of closing prices.
        period: RSI lookback period. Defaults to 14.

    Returns:
        A pandas Series of RSI values bounded to [0, 100].
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Where avg_loss == 0 and avg_gain > 0 → all gains → RSI = 100
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    # Where both are 0 → no movement → neutral
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return rsi.clip(lower=0.0, upper=100.0)


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute the Wilder ATR.

    True Range is ``max(high-low, |high-prev_close|, |low-prev_close|)``;
    ATR is its Wilder-smoothed EMA.

    Args:
        df: OHLCV frame containing ``High``, ``Low``, ``Close``.
        period: ATR lookback period. Defaults to 14.

    Returns:
        A pandas Series of ATR values (>= 0).
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return atr.clip(lower=0.0)


def compute_volume_ma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Compute a simple moving average of volume.

    Args:
        volume: Series of per-bar volumes.
        period: Window size. Defaults to 20.

    Returns:
        Rolling-mean Series; values are NaN until ``period`` bars are available.
    """
    return volume.rolling(window=period, min_periods=period).mean()


def compute_indicators(
    df: pd.DataFrame,
    rsi_period: int = 14,
    atr_period: int = 14,
    volume_period: int = 20,
) -> Indicators:
    """Compute RSI, ATR, and Volume-MA for a frame and return latest values.

    Args:
        df: OHLCV frame.
        rsi_period: RSI lookback. Defaults to 14.
        atr_period: ATR lookback. Defaults to 14.
        volume_period: Volume-MA window. Defaults to 20.

    Returns:
        An ``Indicators`` dataclass with both the latest scalar values and the
        full series for each indicator.
    """
    rsi_series = compute_rsi(df["Close"], period=rsi_period)
    atr_series = compute_atr(df, period=atr_period)
    volume_ma_series = compute_volume_ma(df["Volume"], period=volume_period)

    def _last_or_nan(series: pd.Series) -> float:
        if series.empty:
            return float("nan")
        val = series.iloc[-1]
        return float(val) if pd.notna(val) else float("nan")

    return Indicators(
        rsi=_last_or_nan(rsi_series),
        atr=_last_or_nan(atr_series),
        volume_ma=_last_or_nan(volume_ma_series),
        rsi_series=rsi_series,
        atr_series=atr_series,
        volume_ma_series=volume_ma_series,
    )
