"""PROOF (Track A): the fundamentals context layer does not change any signal.

Deterministic test. yfinance is replaced with a fixed synthetic OHLCV generator so two runs see
byte-identical input. We build the board's per-asset cards with the real signal machinery
(`asset_state`), snapshot them, then run `_attach_context`. The test asserts that after attaching
context, every signal field is byte-identical to the snapshot and the ONLY difference is an added
`context` key carrying the "not validated" label. Combined with the git diff (which shows
`asset_state` and the signal path are untouched — the edits are imports + a toggle + an additive
post-step), this demonstrates the existing signals produce identical output before/after.

Run:  python backtest/test_context_identical.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_data as dd   # noqa: E402

SIGNAL_KEYS = ["asset", "ticker", "dirs", "watch", "price", "updated", "price_tf", "atr",
               "trends", "trend_bias", "support", "resistance", "near_atr", "last_div",
               "setup", "status"]

_PERIOD_DAYS = {"30d": 30, "60d": 60, "120d": 120, "150d": 150, "180d": 180, "1y": 365}
_FREQ = {"15m": "15min", "30m": "30min", "45m": "45min", "1h": "1h", "1d": "1D"}
NOW = pd.Timestamp("2026-09-15 00:00:00")      # fixed reference so both passes are identical


def synth_fetch(ticker, interval, period, retries=3):
    """Deterministic synthetic OHLCV (UTC-naive index), same shape as src.fetch_ohlcv."""
    days = _PERIOD_DAYS.get(str(period), 120)
    freq = _FREQ.get(str(interval), "1h")
    idx = pd.date_range(end=NOW, periods=0, freq=freq)  # placeholder
    idx = pd.date_range(start=NOW - pd.Timedelta(days=days), end=NOW, freq=freq)
    if len(idx) < 260:
        idx = pd.date_range(end=NOW, periods=260, freq=freq)
    seed = (abs(hash((ticker, interval))) % (2**31))
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1.0, len(idx)).cumsum()
    base = 100.0 + 10.0 * np.sin(np.linspace(0, 12, len(idx))) + steps  # trend + waves -> some pivots
    close = np.abs(base) + 50.0
    openp = np.concatenate([[close[0]], close[:-1]])
    spread = 0.5 + 0.5 * rng.random(len(idx))
    high = np.maximum(openp, close) + spread
    low = np.minimum(openp, close) - spread
    vol = rng.integers(1000, 5000, len(idx)).astype(float)
    return pd.DataFrame({"Open": openp, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def build_cards(roster, now):
    cache = {}
    cards = []
    for asset, tk, anchor, allowed, watch in roster:
        st = dd.asset_state(asset, tk, anchor, allowed, watch, cache, now)
        if st:
            cards.append(st)
    return cards, cache


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    dd.fetch_ohlcv = synth_fetch          # monkeypatch the data layer (build_frames + _attach_context)

    # a representative roster: validated (both dir-restricted) + crypto + oil watch + fx watch
    roster = [
        ("BTCUSD", "BTC-USD", "utc", ["buy"], False),
        ("EURUSD", "EURUSD=X", "ny17", ["sell"], False),
        ("XAUUSD", "GC=F", "ny17", ["sell"], False),
        ("XTIUSD", "CL=F", "ny17", ["buy", "sell"], True),
        ("USDJPY", "USDJPY=X", "ny17", ["buy", "sell"], False),
    ]

    cards, cache = build_cards(roster, NOW)
    if not cards:
        print("FAIL: no cards built (synthetic data produced no valid frames)"); return 1
    baseline = copy.deepcopy(cards)       # snapshot BEFORE context (no 'context' key present)
    assert all("context" not in c for c in baseline), "baseline unexpectedly has context"

    dd._attach_context(cards, cache, NOW)  # the additive step under test

    ok = True
    for b, c in zip(baseline, cards):
        stripped = {k: v for k, v in c.items() if k != "context"}
        if stripped != b:
            ok = False
            diffk = [k for k in set(stripped) | set(b) if stripped.get(k) != b.get(k)]
            print(f"  MUTATION on {c.get('asset')}: changed signal keys {diffk}")
        if "context" not in c:
            print(f"  note: {c.get('asset')} has no context attached (allowed on failure, but signal intact)")
        else:
            lab = c["context"].get("label", "")
            if "not validated" not in lab.lower():
                ok = False; print(f"  MISSING LABEL on {c.get('asset')}: {lab!r}")

    n_ctx = sum(1 for c in cards if "context" in c)
    print(f"\ncards={len(cards)}  context_attached={n_ctx}")
    # also confirm every declared signal key is present and unchanged on each card
    for b, c in zip(baseline, cards):
        for k in SIGNAL_KEYS:
            if k in b and c.get(k) != b.get(k):
                ok = False; print(f"  SIGNAL FIELD CHANGED {c.get('asset')}.{k}")
    print("=== PASS: context is additive; all signal fields byte-identical ===" if ok
          else "=== FAIL: signal output changed ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
