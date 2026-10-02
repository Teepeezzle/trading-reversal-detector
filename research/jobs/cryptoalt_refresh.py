"""PHASE 8 / Step B — build the crypto ALT lake (OHLCV + funding) for US GitHub Actions.

Geo note (B-004 / D-022): Bybit & Binance block US IPs, so funding comes from CoinGlass (a
US-reachable data vendor, free tier, interval >= 4h; funding is 8-hourly so 8h is native). Price
BARS come from the existing crypto OHLCV lake (Twelve Data, which works in US CI). We enrich each
crypto bar with the funding rate known at/before its close (ffilled, no-lookahead). perp/spot BASIS
is deferred (needs a perp-price endpoint) -> basis stays NaN, so basis_rev simply yields no trades.

Writes research/data/crypto_alt/{SYM}_{tf}.csv.gz. Needs COINGLASS_API_KEY in the env; if missing,
logs a blocker and exits cleanly (never fabricates).

Usage:  python research/jobs/cryptoalt_refresh.py --years 2 [--symbols BTC/USD,ETH/USD]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import cryptoalt_client as C   # noqa: E402
import cryptoalt as A          # noqa: E402

BLOCKERS = ROOT / "BLOCKERS.md"
TFS = ["1h", "4h", "1day"]


def load_bars(lake: Path, symbol: str, tf: str) -> pd.DataFrame:
    path = lake / "crypto" / f"{symbol.replace('/', '')}_{tf}.csv.gz"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, compression="gzip", parse_dates=["time"]).sort_values("time").reset_index(drop=True)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--years", type=float, default=2.0)
    ap.add_argument("--symbols", default="all")
    ap.add_argument("--exchange", default="Binance")
    a = ap.parse_args()

    api_key = os.environ.get("COINGLASS_API_KEY", "")
    if not api_key:
        msg = "- Phase 8: COINGLASS_API_KEY not set — cannot fetch funding (see D-022). Add the repo secret."
        with BLOCKERS.open("a", encoding="utf-8") as f:
            f.write("\n## Bybit/CoinGlass alt refresh\n" + msg + "\n")
        print("COINGLASS_API_KEY missing — logged blocker, exiting cleanly."); return 0

    lake = Path(a.lake); (lake / A.SUBDIR).mkdir(parents=True, exist_ok=True)
    syms = A.crypto_symbols() if a.symbols == "all" else [s.strip() for s in a.symbols.split(",")]
    end = C.now_ms(); start = C.years_ago_ms(a.years)
    blockers = []
    print(f"CoinGlass alt refresh ({a.exchange}, 8h funding) + TD bars: {a.years}y -> {lake / A.SUBDIR}")
    for sym in syms:
        fund = C.coinglass_funding(sym, start, end, api_key, exchange=a.exchange, interval="8h")
        if fund.empty:
            blockers.append(f"- {sym}: CoinGlass funding empty (symbol/exchange/plan?)")
            print(f"  MISS {sym}: no funding"); continue
        wrote = {}
        for tf in TFS:
            bars = load_bars(lake, sym, tf)
            if bars.empty:
                continue
            df = A.enrich(bars, None, fund)          # spot=None -> basis NaN (deferred); funding ffilled
            bars_out = df.dropna(subset=["funding"])
            if bars_out.empty:
                continue
            bars_out.to_csv(lake / A.SUBDIR / f"{sym.replace('/', '')}_{tf}.csv.gz", index=False, compression="gzip")
            wrote[tf] = len(bars_out)
        span = f"{str(fund['time'].iloc[0])[:10]}..{str(fund['time'].iloc[-1])[:10]}"
        print(f"  ok   {sym:<9} funding={len(fund)} [{span}] -> bars {wrote}", flush=True)

    if blockers:
        with BLOCKERS.open("a", encoding="utf-8") as f:
            f.write("\n## CoinGlass alt refresh — incomplete\n" + "\n".join(blockers) + "\n")
        print(f"logged {len(blockers)} blocker(s)")
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
