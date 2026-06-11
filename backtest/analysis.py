"""Loss-pattern analysis over the trade blotter produced by run_backtest.py."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "backtest" / "results"


def _hour_bucket(h: int) -> str:
    """Map a UTC hour to a coarse session bucket."""
    if 0 <= h < 7:
        return "Asian 00-07"
    if 7 <= h < 12:
        return "London 07-12"
    if 12 <= h < 20:
        return "NewYork 12-20"
    return "LateUS 20-24"


def _regime(er: float) -> str:
    """Classify the efficiency ratio into trend vs range."""
    if not np.isfinite(er):
        return "n/a"
    if er >= 0.45:
        return "trending"
    if er <= 0.20:
        return "ranging/chop"
    return "mixed"


def main(mode: str = "existing") -> int:
    path = OUT / f"trades_{mode}.csv"
    if not path.exists():
        print(f"No blotter at {path}; run run_backtest.py --mode {mode} first.")
        return 1
    df = pd.read_csv(path, parse_dates=["signal_time", "entry_time"])
    df = df[df["outcome"] != "open"].copy()
    if df.empty:
        print("No closed trades.")
        return 1

    df["session"] = df["hour_utc"].apply(_hour_bucket)
    df["regime"] = df["efficiency_ratio"].apply(_regime)

    print(f"\n===== LOSS-PATTERN ANALYSIS ({mode}) =====")
    print(f"Closed trades: {len(df)}  |  Net P&L: ${df.pnl_usd.sum():,.2f}  |  "
          f"Win rate: {100*(df.pnl_usd>0).mean():.1f}%")

    def block(title: str, col: str) -> None:
        g = df.groupby(col).agg(
            trades=("pnl_usd", "size"),
            win_rate=("pnl_usd", lambda s: round(100 * (s > 0).mean(), 1)),
            net=("pnl_usd", lambda s: round(s.sum(), 2)),
            avg=("pnl_usd", lambda s: round(s.mean(), 2)),
        ).sort_values("net")
        print(f"\n--- by {title} ---")
        print(g.to_string())

    block("asset × timeframe", "ticker")
    # cell-level worst
    cell = df.groupby(["ticker", "timeframe"]).agg(
        trades=("pnl_usd", "size"),
        win_rate=("pnl_usd", lambda s: round(100 * (s > 0).mean(), 1)),
        net=("pnl_usd", lambda s: round(s.sum(), 2)),
        pf=("pnl_usd", lambda s: round(s[s > 0].sum() / max(-s[s <= 0].sum(), 1e-9), 2)),
    ).sort_values("net")
    print("\n--- by asset × timeframe (worst first) ---")
    print(cell.to_string())

    block("timeframe", "timeframe")
    block("session (UTC)", "session")
    block("market regime (Kaufman ER)", "regime")
    block("level type", "level_type")

    # self-touch (vacuous level) share + performance
    st = df.groupby("self_touch").agg(
        trades=("pnl_usd", "size"),
        win_rate=("pnl_usd", lambda s: round(100 * (s > 0).mean(), 1)),
        net=("pnl_usd", lambda s: round(s.sum(), 2)),
    )
    print("\n--- self_touch (level == prev bar's own extreme: vacuous) ---")
    print(st.to_string())
    print(f"\nShare of signals that are self-touch (vacuous): "
          f"{100*df.self_touch.mean():.1f}%")
    return 0


if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "existing"
    raise SystemExit(main(m))
