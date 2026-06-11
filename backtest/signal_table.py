"""Print a per-signal blotter table per asset for review.

Usage:
    python backtest/signal_table.py fixed
    python backtest/signal_table.py existing
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "backtest" / "results"

NAMES = {
    "BTC-USD": "Bitcoin",
    "GC=F": "Gold",
    "SI=F": "Silver",
    "CL=F": "WTI Oil",
    "DX-Y.NYB": "Dollar Index",
}


def _fmt(v: float, ticker: str) -> str:
    """Format a price with per-asset precision."""
    if ticker in ("SI=F", "DX-Y.NYB"):
        return f"{v:,.3f}"
    if ticker == "GC=F":
        return f"{v:,.2f}"
    return f"{v:,.2f}"


def main(mode: str = "fixed") -> int:
    path = OUT / f"trades_{mode}.csv"
    if not path.exists():
        print(f"No blotter at {path}")
        return 1
    df = pd.read_csv(path, parse_dates=["signal_time", "entry_time"])
    if df.empty:
        print("No signals generated.")
        return 0

    print(f"\n################ PER-SIGNAL BLOTTER ({mode}) ################")
    for ticker in ["GC=F", "SI=F", "CL=F", "BTC-USD"]:
        sub = df[df.ticker == ticker].sort_values("signal_time")
        name = NAMES.get(ticker, ticker)
        if sub.empty:
            print(f"\n===== {name} ({ticker}) — 0 signals =====")
            continue
        closed = sub[sub.outcome != "open"]
        net = closed.pnl_usd.sum()
        wr = 100 * (closed.pnl_usd > 0).mean() if len(closed) else float("nan")
        print(f"\n===== {name} ({ticker}) — {len(sub)} signals, "
              f"{len(closed)} closed, net ${net:,.2f}, win {wr:.0f}% =====")
        rows = []
        for _, r in sub.iterrows():
            rows.append({
                "signal_time_UTC": r.signal_time.strftime("%Y-%m-%d %H:%M"),
                "tf": r.timeframe,
                "dir": r.direction,
                "level": f"{r.level_type[:1]}{r.level_name[:1]}",  # e.g. DL, WH
                "level_px": _fmt(r.level_price, ticker) if "level_price" in r else "",
                "entry": _fmt(r.entry, ticker),
                "sl": _fmt(r.sl, ticker),
                "tp1": _fmt(r.tp1, ticker),
                "tp2": _fmt(r.tp2, ticker),
                "outcome": r.outcome,
                "R": round(r.r_multiple, 2),
                "pnl$": round(r.pnl_usd, 2),
                "conf": int(r.confidence),
            })
        print(pd.DataFrame(rows).to_string(index=False))
    print("\nlevel key: D/W/M/Y = Daily/Weekly/Monthly/Yearly, "
          "L/H = Low/High.  outcome: sl=stopped, tp1_sl=TP1 then stop (+0.5R), "
          "tp2=full target (+3R), open=unresolved at data end.")
    return 0


if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "fixed"
    raise SystemExit(main(m))
