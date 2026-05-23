"""Core reversal-signal detection logic.

A signal fires when *all four* conditions are true at a significant level:

1. EXTREME TOUCH        – previous candle's extreme pierced the level
                          (within ``tolerance_pct`` fraction).
2. CLOSE-BACK REJECTION – most-recent closed candle's Close is back inside
                          the level.
3. RSI DIVERGENCE       – bullish (longs) or bearish (shorts) divergence
                          between the last two swing points.
4. VOLUME CONFIRMATION  – volume on the rejection candle > Volume MA(20).

For instruments where ``Volume`` is reported as 0 (forex pairs on yfinance),
the volume condition is treated as a soft pass and confidence is reduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from .price_levels import PriceLevels


@dataclass
class ReversalSignal:
    """A complete reversal signal ready for display / logging.

    Attributes:
        ticker: Yahoo-Finance symbol.
        ticker_display_name: Human-readable name (e.g. ``"Gold"``).
        direction: ``"LONG"`` or ``"SHORT"``.
        level_type: ``"Daily"`` | ``"Weekly"`` | ``"Monthly"`` | ``"Yearly"``.
        level_name: ``"High"`` (resistance) or ``"Low"`` (support).
        level_price: The reference price of the level.
        entry_price: Suggested entry (the rejection candle's close).
        stop_loss: Stop-loss price.
        tp1: Take-profit 1 (closes 50%).
        tp2: Take-profit 2 (closes the remainder).
        confidence_score: Integer-rounded score in [0, 100].
        reason_string: Human-readable explanation.
        timestamp: UTC time the signal was generated.
        blocked: True when risk limits prevented the signal from being taken.
        blocked_reason: Free-text reason when ``blocked`` is True.
    """

    ticker: str
    ticker_display_name: str
    direction: str
    level_type: str
    level_name: str
    level_price: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    confidence_score: float
    reason_string: str
    timestamp: datetime
    blocked: bool = False
    blocked_reason: str = ""


def _find_swing_lows(series: pd.Series, lookback: int = 5) -> List[int]:
    """Return positional indices of local minima in ``series``.

    A point ``i`` is a swing low when ``series[i]`` is strictly less than every
    value in ``series[i-lookback:i]`` and less-or-equal to every value in
    ``series[i+1:i+lookback+1]``.

    Args:
        series: Numeric series to scan.
        lookback: Window size on each side.

    Returns:
        Sorted list of positional indices.
    """
    indices: List[int] = []
    n = len(series)
    if n < 2 * lookback + 1:
        return indices
    values = series.to_numpy()
    for i in range(lookback, n - lookback):
        center = values[i]
        before = values[i - lookback : i]
        after = values[i + 1 : i + lookback + 1]
        if center < before.min() and center <= after.min():
            indices.append(i)
    return indices


def _find_swing_highs(series: pd.Series, lookback: int = 5) -> List[int]:
    """Return positional indices of local maxima in ``series``.

    Mirror of :func:`_find_swing_lows`.

    Args:
        series: Numeric series to scan.
        lookback: Window size on each side.

    Returns:
        Sorted list of positional indices.
    """
    indices: List[int] = []
    n = len(series)
    if n < 2 * lookback + 1:
        return indices
    values = series.to_numpy()
    for i in range(lookback, n - lookback):
        center = values[i]
        before = values[i - lookback : i]
        after = values[i + 1 : i + lookback + 1]
        if center > before.max() and center >= after.max():
            indices.append(i)
    return indices


def _check_rsi_divergence(
    df: pd.DataFrame,
    rsi_series: pd.Series,
    direction: str,
    lookback: int = 5,
) -> Tuple[bool, float]:
    """Test for bullish (LONG) or bearish (SHORT) RSI divergence.

    Uses the last two swing points within a ``lookback``-period window on each
    side.

    Args:
        df: OHLCV frame.
        rsi_series: Aligned RSI series.
        direction: ``"LONG"`` or ``"SHORT"``.
        lookback: Swing-point window. Defaults to 5.

    Returns:
        A tuple ``(has_divergence, rsi_gap)`` where ``rsi_gap`` is the absolute
        difference in RSI between the two swing points (used for confidence
        scoring); 0.0 if no divergence.
    """
    if direction == "LONG":
        indices = _find_swing_lows(df["Low"], lookback=lookback)
        if len(indices) < 2:
            return False, 0.0
        last_i, prev_i = indices[-1], indices[-2]
        price_ll = bool(df["Low"].iloc[last_i] < df["Low"].iloc[prev_i])
        rsi_last = float(rsi_series.iloc[last_i])
        rsi_prev = float(rsi_series.iloc[prev_i])
        if not (np.isfinite(rsi_last) and np.isfinite(rsi_prev)):
            return False, 0.0
        rsi_hl = rsi_last > rsi_prev
        return (price_ll and rsi_hl), abs(rsi_last - rsi_prev)

    indices = _find_swing_highs(df["High"], lookback=lookback)
    if len(indices) < 2:
        return False, 0.0
    last_i, prev_i = indices[-1], indices[-2]
    price_hh = bool(df["High"].iloc[last_i] > df["High"].iloc[prev_i])
    rsi_last = float(rsi_series.iloc[last_i])
    rsi_prev = float(rsi_series.iloc[prev_i])
    if not (np.isfinite(rsi_last) and np.isfinite(rsi_prev)):
        return False, 0.0
    rsi_lh = rsi_last < rsi_prev
    return (price_hh and rsi_lh), abs(rsi_last - rsi_prev)


def _compute_confidence(
    rsi_gap: float,
    volume_ratio: float,
    close_back_pct: float,
    volume_applicable: bool,
) -> float:
    """Combine signal components into a 0-100 confidence score.

    The base of 50 is granted for satisfying all four conditions; the
    remaining 50 points are distributed across volume strength, RSI-divergence
    magnitude, and close-back distance.

    Args:
        rsi_gap: |RSI(last_swing) - RSI(prev_swing)|.
        volume_ratio: ``current.Volume / volume_ma`` (1.0 if not applicable).
        close_back_pct: |Close - level| / level * 100.
        volume_applicable: False for instruments with zero/missing volume.

    Returns:
        Float in [0, 100].
    """
    score = 50.0
    if volume_applicable:
        score += min(20.0, max(0.0, (volume_ratio - 1.0) * 20.0))
    else:
        score += 5.0  # neutral partial credit
    score += min(15.0, rsi_gap)
    score += min(15.0, close_back_pct * 30.0)
    return float(max(0.0, min(100.0, score)))


def _attempt_signal_for_level(
    ticker: str,
    ticker_name: str,
    df: pd.DataFrame,
    rsi_series: pd.Series,
    volume_ma_series: pd.Series,
    atr_value: float,
    level_price: float,
    level_type: str,
    level_name: str,
    direction: str,
    tolerance_pct: float,
    swing_lookback: int,
) -> Optional[ReversalSignal]:
    """Evaluate all four conditions for one (level, direction) combination.

    Returns:
        A populated ``ReversalSignal`` if all conditions pass, otherwise
        ``None``. SL/TP fields are placeholders (zeros) here and are filled by
        the risk manager downstream.
    """
    if len(df) < (2 * swing_lookback + 2):
        return None
    if not np.isfinite(level_price) or level_price <= 0:
        return None
    if not np.isfinite(atr_value) or atr_value <= 0:
        return None

    prev = df.iloc[-2]
    curr = df.iloc[-1]
    prev_low = float(prev["Low"])
    prev_high = float(prev["High"])
    curr_close = float(curr["Close"])
    curr_volume = float(curr["Volume"])

    # --- Condition 1 + 2 -----------------------------------------------------
    # Condition 1 (touch): prev candle's extreme pierced the level, with up to
    # ``tolerance_pct`` slack on the other side of the level (e.g. for LONG a
    # low that lands 0.1% above support still counts as a touch).
    if direction == "LONG":
        touch = prev_low < level_price * (1.0 + tolerance_pct)
        close_back = curr_close > level_price
        extreme_price = prev_low
    else:
        touch = prev_high > level_price * (1.0 - tolerance_pct)
        close_back = curr_close < level_price
        extreme_price = prev_high

    if not (touch and close_back):
        return None

    # --- Condition 3 ---------------------------------------------------------
    has_divergence, rsi_gap = _check_rsi_divergence(
        df, rsi_series, direction, lookback=swing_lookback
    )
    if not has_divergence:
        return None

    # --- Condition 4 ---------------------------------------------------------
    volume_ma_value = float(volume_ma_series.iloc[-1]) if not volume_ma_series.empty else float("nan")
    volume_applicable = np.isfinite(volume_ma_value) and volume_ma_value > 0
    if volume_applicable:
        if curr_volume <= volume_ma_value:
            return None
        volume_ratio = curr_volume / volume_ma_value
    else:
        volume_ratio = 1.0  # treat as soft-pass for zero-volume instruments

    # --- Scoring + reason ----------------------------------------------------
    close_back_pct = abs(curr_close - level_price) / level_price * 100.0
    confidence = _compute_confidence(rsi_gap, volume_ratio, close_back_pct, volume_applicable)

    direction_words = (
        ("bullish", "LL", "HL")
        if direction == "LONG"
        else ("bearish", "HH", "LH")
    )
    volume_phrase = (
        f" Volume {volume_ratio:.1f}× average."
        if volume_applicable
        else " Volume data unavailable (treated neutral)."
    )
    reason = (
        f"Broke {level_type.lower()} {level_name.lower()} to {extreme_price:.5f}"
        f" then closed back at {curr_close:.5f}."
        f" RSI {direction_words[0]} divergence:"
        f" price {direction_words[1]}, RSI {direction_words[2]}."
        f"{volume_phrase}"
    )

    return ReversalSignal(
        ticker=ticker,
        ticker_display_name=ticker_name,
        direction=direction,
        level_type=level_type,
        level_name=level_name,
        level_price=float(level_price),
        entry_price=float(curr_close),
        stop_loss=0.0,
        tp1=0.0,
        tp2=0.0,
        confidence_score=round(confidence, 0),
        reason_string=reason,
        timestamp=datetime.now(timezone.utc),
    )


def detect_reversals(
    ticker: str,
    ticker_name: str,
    df: pd.DataFrame,
    levels: PriceLevels,
    rsi_series: pd.Series,
    volume_ma_series: pd.Series,
    atr_value: float,
    tolerance_pct: float = 0.001,
    swing_lookback: int = 5,
) -> List[ReversalSignal]:
    """Scan all level / direction combinations and return raw signals.

    The returned signals have SL/TP fields set to ``0.0`` — the risk manager is
    responsible for filling them in (it owns the ATR-based math and applies
    portfolio-level limits).

    Args:
        ticker: Yahoo-Finance symbol.
        ticker_name: Human-readable display name.
        df: OHLCV frame.
        levels: Pre-computed :class:`PriceLevels` for this ticker.
        rsi_series: Full RSI series, index-aligned with ``df``.
        volume_ma_series: Full Volume-MA series, index-aligned with ``df``.
        atr_value: Latest ATR value.
        tolerance_pct: Pierce tolerance (fraction; 0.001 = 0.1%). Defaults 0.001.
        swing_lookback: Window for divergence swing detection. Defaults 5.

    Returns:
        A list of zero or more :class:`ReversalSignal` instances.
    """
    signals: List[ReversalSignal] = []

    checks: List[Tuple[str, str, float, str]] = [
        ("Daily", "Low", levels.daily_low, "LONG"),
        ("Daily", "High", levels.daily_high, "SHORT"),
        ("Weekly", "Low", levels.weekly_low, "LONG"),
        ("Weekly", "High", levels.weekly_high, "SHORT"),
        ("Monthly", "Low", levels.monthly_low, "LONG"),
        ("Monthly", "High", levels.monthly_high, "SHORT"),
        ("Yearly", "Low", levels.yearly_low, "LONG"),
        ("Yearly", "High", levels.yearly_high, "SHORT"),
    ]

    for level_type, level_name, level_price, direction in checks:
        try:
            sig = _attempt_signal_for_level(
                ticker=ticker,
                ticker_name=ticker_name,
                df=df,
                rsi_series=rsi_series,
                volume_ma_series=volume_ma_series,
                atr_value=atr_value,
                level_price=level_price,
                level_type=level_type,
                level_name=level_name,
                direction=direction,
                tolerance_pct=tolerance_pct,
                swing_lookback=swing_lookback,
            )
        except Exception:  # noqa: BLE001 - never let one level kill the scan
            sig = None
        if sig is not None:
            signals.append(sig)

    return signals
