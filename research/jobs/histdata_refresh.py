"""PHASE 7 (Step A) — build a DEEP FX/metals lake from HistData (free, no key).

Rebuilds research/data/{class}/{SYM}_{tf}.csv.gz for FX majors, FX crosses, and metals (XAU/USD,
XAG/USD) from HistData 1-minute history resampled to 15min/1h/4h/1day — years of depth instead of
the Twelve-Data-free ~52d cap (D-005). This gives the gauntlet the statistical power every Phase-3/5
near-miss lacked. Oil (WTI/Brent) is NOT on HistData -> left on yfinance (logged, unchanged).

Overwrites the shallow TD/yfinance files in place so the existing sweeps read deep data. The deep
re-test is registered under a distinct phase/id (see deep_resweep) so old vs new stay comparable.

Usage:  python research/jobs/histdata_refresh.py --years 3 [--classes forex_majors,metals]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import histdata_client as H   # noqa: E402

CFG = yaml.safe_load((ROOT / "config.yaml").read_text("utf-8"))
TFS = ["15min", "1h", "4h", "1day"]
BLOCKERS = ROOT / "BLOCKERS.md"
# classes HistData can serve; metals pulled from HistData (incl. XAG, upgrading the yfinance proxy)
HD_CLASSES = {
    "forex_majors": CFG["universe"]["forex_majors"]["symbols"],
    "forex_crosses": CFG["universe"]["forex_crosses"]["symbols"],
    "metals": ["XAU/USD", "XAG/USD"],
}


def write_lake(lake: Path, aclass: str, symbol: str, m1: pd.DataFrame) -> dict:
    out = {}
    base = symbol.replace("/", "")
    (lake / aclass).mkdir(parents=True, exist_ok=True)
    for tf in TFS:
        bars = H.resample(m1, tf)
        if bars.empty:
            continue
        bars.to_csv(lake / aclass / f"{base}_{tf}.csv.gz", index=False, compression="gzip")
        out[tf] = len(bars)
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--years", type=int, default=3, help="how many years back to fetch")
    ap.add_argument("--classes", default="all")
    a = ap.parse_args()

    lake = Path(a.lake)
    now = datetime.now(timezone.utc)
    start_year = now.year - a.years
    classes = list(HD_CLASSES) if a.classes == "all" else [c.strip() for c in a.classes.split(",")]
    blockers = []
    print(f"HistData deep refresh: {start_year}..{now.year} -> {lake}")
    for cls in classes:
        for sym in HD_CLASSES.get(cls, []):
            m1 = H.fetch_m1(sym, start_year, now.year)
            if m1.empty:
                blockers.append(f"- {cls} {sym}: HistData returned no data ({start_year}..{now.year})")
                print(f"  MISS {cls:<13} {sym}"); continue
            counts = write_lake(lake, cls, sym, m1)
            span = f"{str(m1['time'].iloc[0])[:10]}..{str(m1['time'].iloc[-1])[:10]}"
            print(f"  ok   {cls:<13} {sym:<9} M1={len(m1):>7} {span} -> {counts}", flush=True)

    if blockers:
        with BLOCKERS.open("a", encoding="utf-8") as f:
            f.write(f"\n## HistData deep refresh {now:%Y-%m-%d} — unavailable series\n" + "\n".join(blockers) + "\n")
        print(f"logged {len(blockers)} blocker(s)")
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
