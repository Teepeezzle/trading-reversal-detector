"""Unit tests for the validated daily breakout detector (offline, synthetic)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.breakout_detector import (  # noqa: E402
    BreakoutSignal,
    compute_adx,
    compute_atr,
    detect_breakout,
)


def _frame(closes, highs=None, lows=None):
    n = len(closes)
    closes = np.asarray(closes, float)
    highs = closes + 1.0 if highs is None else np.asarray(highs, float)
    lows = closes - 1.0 if lows is None else np.asarray(lows, float)
    idx = pd.date_range(end="2026-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes,
         "Volume": np.full(n, 1000.0)},
        index=idx,
    )


def test_atr_positive():
    np.random.seed(0)
    c = 100 + np.cumsum(np.random.randn(300))
    df = _frame(c, c + np.random.rand(300), c - np.random.rand(300))
    atr = compute_atr(df).dropna()
    assert (atr >= 0).all() and atr.iloc[-1] > 0


def test_adx_bounded():
    np.random.seed(1)
    c = 100 + np.cumsum(np.random.randn(300))
    df = _frame(c)
    adx = compute_adx(df).dropna()
    assert (adx >= 0).all() and (adx <= 100).all()


def test_insufficient_data_returns_none():
    df = _frame(np.linspace(100, 110, 50))
    assert detect_breakout("X", "X", df) is None


def test_breakout_fires_on_constructed_setup():
    """A low-ADX sideways base above the 200-SMA that breaks its 20-day high."""
    n = 260
    rng = np.random.RandomState(7)
    # 1) short ramp up to lift price above where the 200-SMA will settle
    ramp = np.linspace(85.0, 100.0, 60)
    # 2) long flat NOISE range (mean-reverting) -> keeps ADX < 20, 20-day high ~101
    sideways = 100.0 + rng.randn(n - 61) * 0.4
    # 3) final bar breaks cleanly above the range high
    closes = np.concatenate([ramp, sideways, [103.0]])
    highs = closes + 0.3
    lows = closes - 0.3
    highs[-1] = 103.5
    df = _frame(closes, highs, lows)

    sig = detect_breakout("BTC-USD", "Bitcoin", df)
    assert sig is not None, "Expected a breakout on the constructed setup"
    assert isinstance(sig, BreakoutSignal)
    assert sig.direction == "LONG"
    assert sig.entry_price == pytest.approx(103.0)
    # SL below entry, TP above, 1:2 geometry
    assert sig.stop_loss < sig.entry_price < sig.take_profit
    risk = sig.entry_price - sig.stop_loss
    reward = sig.take_profit - sig.entry_price
    assert reward == pytest.approx(2 * risk, rel=1e-6)
    assert sig.adx < 20.0
    assert sig.entry_price > sig.sma200


def test_no_breakout_when_below_200sma():
    """Same breakout shape but price below the 200-SMA must NOT fire."""
    n = 260
    # Downtrend: price ends below its 200-SMA, so macro filter blocks it.
    closes = np.linspace(200.0, 100.0, n)
    closes[-1] = closes[-2] + 5.0  # local pop, still below long SMA
    highs = closes + 0.3
    lows = closes - 0.3
    df = _frame(closes, highs, lows)
    sig = detect_breakout("X", "X", df)
    assert sig is None


def test_no_breakout_when_no_new_high():
    """Strong uptrend (high ADX) and no fresh 20-day high -> no signal."""
    n = 260
    closes = np.linspace(80.0, 160.0, n)  # steady strong trend -> ADX high
    closes[-1] = closes[-2] - 2.0  # last bar pulls back, no breakout
    df = _frame(closes)
    sig = detect_breakout("X", "X", df)
    assert sig is None
