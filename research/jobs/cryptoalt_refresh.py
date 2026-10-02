"""PHASE 8 / Step B — build the crypto ALT lake (perp OHLCV + funding + perp/spot basis) from Bybit.

For each crypto symbol: fetch 1h perp klines, 1h spot klines, and funding history (Bybit v5, no key,
US-reachable), enrich into OHLCV+funding+basis at 1h, and resample to 4h/1D. Writes
research/data/crypto_alt/{SYM}_{tf}.csv.gz (under the main lake, so it rides the research-lake- cache).

Usage:  python research/jobs/cryptoalt_refresh.py --years 2 [--symbols BTC/USD,ETH/USD]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import cryptoalt_client as C   # noqa: E402
import cryptoalt as A          # noqa: E402

BLOCKERS = ROOT / "BLOCKERS.md"
RESAMPLE = {"4h": "4h", "1day": "1D"}
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
       "funding": "last", "basis": "last"}


def resample_alt(df1h: pd.DataFrame, tf: str) -> pd.DataFrame:
    g = df1h.set_index("time").resample(RESAMPLE[tf], label="left", closed="left").agg(AGG)
    return g.dropna(subset=["open", "high", "low", "close"]).reset_index()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--years", type=float, default=2.0)
    ap.add_argument("--symbols", default="all")
    a = ap.parse_args()

    lake = Path(a.lake); (lake / A.SUBDIR).mkdir(parents=True, exist_ok=True)
    syms = A.crypto_symbols() if a.symbols == "all" else [s.strip() for s in a.symbols.split(",")]
    end = C.now_ms(); start = C.years_ago_ms(a.years)
    blockers = []
    print(f"Bybit alt refresh: {a.years}y -> {lake / A.SUBDIR}  ({len(syms)} symbols)")
    for sym in syms:
        perp = C.klines(sym, "1h", start, end, "linear")
        spot = C.klines(sym, "1h", start, end, "spot")
        fund = C.funding(sym, start, end)
        if perp.empty or fund.empty:
            blockers.append(f"- {sym}: perp={len(perp)} spot={len(spot)} funding={len(fund)} (incomplete)")
            print(f"  MISS {sym}: perp={len(perp)} spot={len(spot)} funding={len(fund)}"); continue
        df1h = A.enrich(perp, spot, fund)
        base = sym.replace("/", "")
        df1h.to_csv(lake / A.SUBDIR / f"{base}_1h.csv.gz", index=False, compression="gzip")
        counts = {"1h": len(df1h)}
        for tf in RESAMPLE:
            r = resample_alt(df1h, tf)
            r.to_csv(lake / A.SUBDIR / f"{base}_{tf}.csv.gz", index=False, compression="gzip")
            counts[tf] = len(r)
        span = f"{str(df1h['time'].iloc[0])[:10]}..{str(df1h['time'].iloc[-1])[:10]}"
        print(f"  ok   {sym:<9} {span} funding_nn={int(df1h['funding'].notna().sum())} -> {counts}", flush=True)

    if blockers:
        with BLOCKERS.open("a", encoding="utf-8") as f:
            f.write("\n## Bybit alt refresh — incomplete series\n" + "\n".join(blockers) + "\n")
        print(f"logged {len(blockers)} blocker(s)")
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
