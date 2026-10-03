"""Deterministic test of the forward shadow-test engine (record -> resolve -> report).

Monkeypatches the signal source (dashboard_data.asset_state) and the price feed (fetch_ohlcv) so no
network is used and the result is fixed. Proves: a fresh SETUP is logged once with its point-in-time
context + the three shadow decisions; resolve fills a correct first-touch outcome; report writes
STATUS.md. Uses temp paths so the real forward log is never touched.

Run:  python forward_test/test_forward_log.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "backtest")); sys.path.insert(0, str(ROOT / "forward_test"))
import forward_log as fl   # noqa: E402

TMP = Path(__file__).resolve().parent / "_test_tmp"
TMP.mkdir(exist_ok=True)
fl.SIGNALS = TMP / "signals.csv"; fl.SHADOW = TMP / "shadow.csv"; fl.STATUS = TMP / "STATUS.md"
for p in (fl.SIGNALS, fl.SHADOW, fl.STATUS):
    if p.exists():
        p.unlink()

CONFIRM = "2026-09-01 12:00:00"
UNIV = {"EURUSD": {"ticker": "EURUSD=X", "anchor": "ny17", "dirs": ["sell"]}}


def fake_asset_state(asset, tk, anchor, allowed, watch, cache, now):
    cache[(tk, "1h", "120d")] = pd.DataFrame(
        {"Open": np.ones(300), "High": np.ones(300) * 1.01, "Low": np.ones(300) * 0.99,
         "Close": np.ones(300), "Volume": np.ones(300)},
        index=pd.date_range(end=pd.Timestamp(CONFIRM), periods=300, freq="1h"))
    return {"asset": asset, "ticker": tk, "status": "SETUP", "updated": CONFIRM,
            "setup": {"side": "SELL", "tf": "4h", "bars_ago": 1, "entry": 1.0740,
                      "stop": 1.0810, "target": 1.0530, "zones": 2}}


def fake_fetch(ticker, interval, period, retries=3):
    # bars after entry that hit the SELL target (low <= 1.0530) -> a win
    idx = pd.date_range(start=pd.Timestamp(CONFIRM) + pd.Timedelta(hours=1), periods=200, freq="1h")
    close = np.linspace(1.0740, 1.0500, 200)
    return pd.DataFrame({"Open": close, "High": close + 0.001, "Low": close - 0.001,
                         "Close": close, "Volume": np.ones(200)}, index=idx)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    fl.dd.asset_state = fake_asset_state
    fl.fetch_ohlcv = fake_fetch
    ok = True

    n1 = fl.record(UNIV)
    n2 = fl.record(UNIV)                       # idempotent: same setup must not double-log
    sig = pd.read_csv(fl.SIGNALS); sha = pd.read_csv(fl.SHADOW)
    if not (n1 == 1 and n2 == 0 and len(sig) == 1 and len(sha) == 1):
        ok = False; print(f"  FAIL record: n1={n1} n2={n2} sig={len(sig)} sha={len(sha)}")
    else:
        print(f"  OK record: 1 logged, re-run added 0 (idempotent)")
    r = sig.iloc[0]
    for col in ("macro_rates", "usd_backdrop", "context_json", "entry", "stop", "target"):
        if pd.isna(r.get(col)) or r.get(col) == "":
            ok = False; print(f"  FAIL: context/level field missing: {col}")
    if "not validated" not in str(r["context_json"]).lower():
        ok = False; print("  FAIL: context_json missing the 'not validated' label")
    sh = sha.iloc[0]
    if sh["gate_pass"] not in (True, False, "True", "False"):
        ok = False; print("  FAIL: shadow gate not recorded")
    print(f"  shadow: gate_pass={sh['gate_pass']} score={sh['score_delta']} tag={sh['tag']}")

    nres = fl.resolve(UNIV)
    sig = pd.read_csv(fl.SIGNALS); r = sig.iloc[0]
    if not (nres == 1 and r["outcome"] == "win" and abs(float(r["R"]) - fl.R_WIN) < 1e-6):
        ok = False; print(f"  FAIL resolve: n={nres} outcome={r['outcome']} R={r['R']} (want win {fl.R_WIN})")
    else:
        print(f"  OK resolve: outcome=win R={r['R']}")

    fl.report()
    txt = fl.STATUS.read_text(encoding="utf-8")
    if "Signals logged: **1**" not in txt or "n=100" not in txt:
        ok = False; print("  FAIL report: STATUS.md missing expected content")
    else:
        print("  OK report: STATUS.md written with milestone gates")

    print("=== PASS: forward shadow-test engine works end-to-end ===" if ok else "=== FAIL ===")
    # cleanup temp
    for p in (fl.SIGNALS, fl.SHADOW, fl.STATUS):
        try: p.unlink()
        except Exception: pass
    try: TMP.rmdir()
    except Exception: pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
