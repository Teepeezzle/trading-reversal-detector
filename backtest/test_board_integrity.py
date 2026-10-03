"""PROOF (fix/board-data-integrity): fail-loud + freshness are additive; signals unchanged.

Deterministic (synthetic data, mocked spot). Shows:
  1. An asset whose fetch FAILS renders as a NODATA card (visible "data unavailable"), never dropped.
  2. attach_health adds freshness (+ crypto spot) without changing any signal field.
  3. Succeeding assets keep byte-identical signal fields.

Run:  python backtest/test_board_integrity.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "backtest"))
import dashboard_data as dd   # noqa: E402
import board_health as HEALTH  # noqa: E402

NOW = pd.Timestamp("2026-09-15 00:00:00")
SIGNAL_KEYS = ["asset", "price", "price_tf", "atr", "trends", "trend_bias", "support", "resistance",
               "near_atr", "last_div", "setup", "status"]
FAIL = {"GC=F"}   # simulate yfinance failing for XAUUSD


def synth(ticker, interval, period, retries=3):
    if ticker in FAIL:
        return None
    freq = {"15m": "15min", "30m": "30min", "45m": "45min", "1h": "1h", "1d": "1D"}.get(interval, "1h")
    idx = pd.date_range(end=NOW, periods=400, freq=freq)
    seed = abs(hash((ticker, interval))) % (2**31)
    rng = np.random.default_rng(seed)
    c = np.abs(100 + np.sin(np.linspace(0, 10, 400)) + rng.normal(0, .5, 400).cumsum()) + 50
    o = np.concatenate([[c[0]], c[:-1]])
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c) + .5, "Low": np.minimum(o, c) - .5,
                         "Close": c, "Volume": np.ones(400)}, index=idx)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    dd.fetch_ohlcv = synth
    HEALTH.crypto_spots = lambda assets: {"BTCUSD": (151.0, 1.0)}   # deterministic spot (no network)
    ok = True

    roster = [("BTCUSD", "BTC-USD", "utc", ["buy"], False),
              ("XAUUSD", "GC=F", "ny17", ["sell"], False),       # will fail -> must become NODATA
              ("EURUSD", "EURUSD=X", "ny17", ["sell"], False)]
    cache = {}; out = []
    for asset, tk, anchor, allowed, watch in roster:
        reason = None
        try:
            st = dd.asset_state(asset, tk, anchor, allowed, watch, cache, NOW)
            if st is None:
                reason = "no usable OHLCV"
        except Exception as exc:  # noqa: BLE001
            st = None; reason = f"error: {exc}"
        out.append(st if st else dd._nodata_card(asset, tk, allowed, watch, reason))

    present = {c["asset"] for c in out}
    if present != {"BTCUSD", "XAUUSD", "EURUSD"}:
        ok = False; print(f"  FAIL: not all assets rendered: {present}")
    nod = [c for c in out if c["status"] == "NODATA"]
    if not (len(nod) == 1 and nod[0]["asset"] == "XAUUSD" and nod[0].get("error")):
        ok = False; print(f"  FAIL: failed asset not surfaced as NODATA with reason: {nod}")
    else:
        print(f"  OK fail-loud: XAUUSD (fetch failed) -> NODATA card, reason={nod[0]['error']!r} (not dropped)")

    signals_before = copy.deepcopy({c["asset"]: {k: c.get(k) for k in SIGNAL_KEYS} for c in out})
    HEALTH.attach_health(out, NOW)
    for c in out:
        for k in SIGNAL_KEYS:
            if c.get(k) != signals_before[c["asset"]][k]:
                ok = False; print(f"  SIGNAL CHANGED {c['asset']}.{k}")
        if "bar_age_min" not in c or "stale" not in c or "fetched_at" not in c:
            ok = False; print(f"  FAIL: freshness fields missing on {c['asset']}")
    btc = next(c for c in out if c["asset"] == "BTCUSD")
    if "spot_price" not in btc:
        ok = False; print("  FAIL: crypto spot cross-check not attached to BTCUSD")
    nod0 = next(c for c in out if c["asset"] == "XAUUSD")
    if nod0.get("stale") is not True:
        ok = False; print("  FAIL: NODATA card not flagged stale")
    if ok:
        print(f"  OK freshness: all cards got bar_age_min/stale/fetched_at; BTC spot={btc.get('spot_price')}; "
              "no signal field changed")

    print("=== PASS: fail-loud + freshness are additive; signals unchanged ===" if ok
          else "=== FAIL ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
