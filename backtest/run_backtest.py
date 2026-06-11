"""Driver: fetch history, replay the deployed logic, print metrics.

Honest data limitations (yfinance, free tier):
    * 5m  : max ~60 days of history.
    * 15m : max ~60 days of history.
    * 1h  : max ~730 days — we use ~365.
    * 1d  : multi-year.
A "1 full year" backtest is therefore only possible at 1h and 1d. The 5m/15m
cells are ~60-day samples and are labelled as such. This is a real limitation
of free OHLCV data, not a modelling choice.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backtest.engine import CellResult, replay, trades_to_frame  # noqa: E402

# yfinance fetch plan per timeframe: (interval, period). 4h is resampled from
# 1h. yfinance caps: 5m/15m -> 60d max; 1h -> 730d (~2y) max; 1d -> full.
FETCH_PLAN: Dict[str, tuple] = {
    "5m": ("5m", "60d"),
    "15m": ("15m", "60d"),
    "1h": ("1h", "730d"),    # ~2 years — the longest intraday yfinance allows
    "4h": ("1h", "730d"),    # fetch 1h over ~2y, then resample to 4h
    "1d": ("1d", "2y"),
}

ASSETS = ["BTC-USD", "GC=F", "SI=F", "CL=F"]
OUT_DIR = REPO_ROOT / "backtest" / "results"


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance MultiIndex columns and keep OHLCV."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    cols = ["Open", "High", "Low", "Close", "Volume"]
    df = df[[c for c in cols if c in df.columns]].copy()
    return df.dropna(subset=["Open", "High", "Low", "Close"])


def fetch(ticker: str, interval: str, period: str) -> Optional[pd.DataFrame]:
    """Fetch one OHLCV frame, with a single retry."""
    for attempt in range(2):
        try:
            raw = yf.download(
                ticker, period=period, interval=interval,
                progress=False, auto_adjust=False, threads=False,
            )
            if raw is not None and not raw.empty:
                return _flatten(raw)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {ticker} {interval}/{period} attempt {attempt+1}: {exc}")
        time.sleep(1.0)
    print(f"  ! {ticker} {interval}/{period}: no data")
    return None


def resample_4h(hourly: pd.DataFrame) -> pd.DataFrame:
    """Resample 1h -> 4h exactly as deployed (first/max/min/last/sum)."""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return hourly.resample("4h").agg(agg).dropna(subset=["Open", "High", "Low", "Close"])


def run(mode: str, timeframes: List[str], assets: List[str]) -> List[CellResult]:
    """Run the full grid and return one CellResult per (asset, timeframe)."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results: List[CellResult] = []

    for ticker in assets:
        daily = fetch(ticker, "1d", "2y")
        if daily is None:
            print(f"[{ticker}] no daily data — skipping asset")
            continue

        for tf in timeframes:
            interval, period = FETCH_PLAN[tf]
            if tf == "1d":
                intra = daily
            elif tf == "4h":
                hourly = fetch(ticker, "1h", period)
                intra = resample_4h(hourly) if hourly is not None else None
            else:
                intra = fetch(ticker, interval, period)
            if intra is None or len(intra) < 100:
                print(f"[{ticker} {tf}] insufficient data ({0 if intra is None else len(intra)} bars)")
                continue

            t0 = time.time()
            cell = replay(ticker, tf, intra, daily, mode=mode)
            dt = time.time() - t0
            m = cell.metrics()
            print(
                f"[{ticker} {tf}] {len(intra)} bars -> "
                f"{m['signals']} sigs, {m['closed_trades']} closed, "
                f"net ${m['net_pnl_usd']}, PF {m['profit_factor']}, "
                f"win {m['win_rate_pct']}%  ({dt:.0f}s)"
            )
            results.append(cell)

    # Persist a tidy metrics table + the raw trade blotter.
    metrics_df = pd.DataFrame([c.metrics() for c in results])
    metrics_df.to_csv(OUT_DIR / f"metrics_{mode}.csv", index=False)
    trades_to_frame(results).to_csv(OUT_DIR / f"trades_{mode}.csv", index=False)
    print(f"\nSaved: {OUT_DIR / f'metrics_{mode}.csv'}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["existing", "fixed", "macro"], default="existing")
    parser.add_argument("--timeframes", default="5m,15m,1h")
    parser.add_argument("--assets", default=",".join(ASSETS))
    args = parser.parse_args()
    tfs = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    assets = [a.strip() for a in args.assets.split(",") if a.strip()]
    print(f"=== Backtest mode={args.mode} timeframes={tfs} assets={assets} ===")
    run(args.mode, tfs, assets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
