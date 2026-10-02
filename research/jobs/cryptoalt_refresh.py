"""PHASE 8 / Step B — build the crypto ALT lake (OHLCV + funding) for US GitHub Actions.

Geo saga (B-004 / D-022 / D-023): Bybit & Binance block US IPs, and CoinGlass's historical-funding
endpoint is paid-only ("401 Upgrade plan") on the free tier. Resolution: funding is TINY (8h x 2y x
17 coins ~= 208 KB), so it is fetched once from a non-US box (Bybit) and COMMITTED to the repo at
research/altdata_committed/funding/{SYM}.csv.gz. This job joins that committed funding to the crypto
price BARS already in the lake (Twelve Data, US-OK) and writes research/data/crypto_alt/{SYM}_{tf}.
No network, no key, no geo-block in CI. perp/spot BASIS is deferred (NaN) -> basis_rev yields no trades.

Usage:  python research/jobs/cryptoalt_refresh.py [--symbols BTC/USD,ETH/USD]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import cryptoalt as A          # noqa: E402

BLOCKERS = ROOT / "BLOCKERS.md"
FUND_DIR = ROOT / "altdata_committed" / "funding"
TFS = ["1h", "4h", "1day"]


def load_bars(lake: Path, symbol: str, tf: str) -> pd.DataFrame:
    path = lake / "crypto" / f"{symbol.replace('/', '')}_{tf}.csv.gz"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, compression="gzip", parse_dates=["time"]).sort_values("time").reset_index(drop=True)


def load_committed_funding(symbol: str) -> pd.DataFrame:
    p = FUND_DIR / f"{symbol.replace('/', '')}.csv.gz"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, compression="gzip", parse_dates=["time"]).sort_values("time").reset_index(drop=True)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--symbols", default="all")
    a = ap.parse_args()

    lake = Path(a.lake); (lake / A.SUBDIR).mkdir(parents=True, exist_ok=True)
    syms = A.crypto_symbols() if a.symbols == "all" else [s.strip() for s in a.symbols.split(",")]
    blockers = []
    print(f"Crypto alt lake: committed funding (+ TD bars) -> {lake / A.SUBDIR}  ({len(syms)} symbols)")
    for sym in syms:
        fund = load_committed_funding(sym)
        if fund.empty:
            blockers.append(f"- {sym}: no committed funding file (research/altdata_committed/funding/)")
            print(f"  MISS {sym}: no committed funding"); continue
        wrote = {}
        for tf in TFS:
            bars = load_bars(lake, sym, tf)
            if bars.empty:
                continue
            df = A.enrich(bars, None, fund)          # spot=None -> basis NaN (deferred); funding ffilled
            out = df.dropna(subset=["funding"])
            if out.empty:
                continue
            out.to_csv(lake / A.SUBDIR / f"{sym.replace('/', '')}_{tf}.csv.gz", index=False, compression="gzip")
            wrote[tf] = len(out)
        span = f"{str(fund['time'].iloc[0])[:10]}..{str(fund['time'].iloc[-1])[:10]}"
        print(f"  ok   {sym:<9} funding={len(fund)} [{span}] -> bars {wrote}", flush=True)

    if blockers:
        with BLOCKERS.open("a", encoding="utf-8") as f:
            f.write("\n## Crypto alt refresh — missing committed funding\n" + "\n".join(blockers) + "\n")
        print(f"logged {len(blockers)} blocker(s)")
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
