"""Unit tests for the overnight-metals module (offline, synthetic)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.overnight_metals import (  # noqa: E402
    OvernightSignal,
    VALIDATED_DRIFT,
    build_overnight_signal,
    compute_atr,
)


def _frame(n=60, price=2000.0):
    rng = np.random.RandomState(1)
    closes = price + np.cumsum(rng.randn(n))
    idx = pd.date_range(end="2026-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"Open": closes, "High": closes + 2, "Low": closes - 2,
         "Close": closes, "Volume": np.full(n, 1000.0)},
        index=idx,
    )


def test_atr_positive():
    atr = compute_atr(_frame()).dropna()
    assert (atr >= 0).all() and atr.iloc[-1] > 0


def test_signal_for_validated_metal():
    df = _frame(price=2000.0)
    sig = build_overnight_signal("GC=F", "Gold", df)
    assert isinstance(sig, OvernightSignal)
    assert sig.direction == "LONG"
    assert sig.ticker == "GC=F"
    assert sig.entry_close == df["Close"].iloc[-1]
    assert sig.expected_drift_pct == VALIDATED_DRIFT["GC=F"] * 100.0


def test_no_signal_for_unvalidated_ticker():
    # Copper was negative in validation -> not in VALIDATED_DRIFT -> no signal.
    assert build_overnight_signal("HG=F", "Copper", _frame()) is None


def test_no_signal_insufficient_data():
    assert build_overnight_signal("GC=F", "Gold", _frame(n=10)) is None
