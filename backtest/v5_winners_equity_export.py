"""Export the 90-day winners risk-based equity sim to an Excel workbook.

$1,000 start, winners basket, last 90 days, risk-per-trade 5% AND 10% (compounding,
take-all with a 40% open-risk warning). Produces logs/v5_winners_equity_90d.xlsx:

  Summary        — headline metrics for 5% and 10% side by side.
  Trades 10% / 5% — one row per signal (entry order) with entry/exit times,
                    entry/SL/TP prices, outcome, R, the equity used to size it,
                    $ risk, $ P&L, the open-risk % it created, and a 40% flag.
  Equity 10% / 5% — the realised equity curve (one row per trade close) with
                    running peak and drawdown %, so the -69% / -93% drawdown is
                    visible step by step.

Run: python backtest/v5_winners_equity_export.py [--days 90]
"""
from __future__ import annotations

import argparse
import heapq
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.v5_winners_equity_risk import (   # noqa: E402
    build_signals, START_EQ, RISK_CEILING,
)


def detailed_sim(sigs, risk_pct):
    """Return (trades_df, curve_df, summary_dict)."""
    equity = START_EQ
    open_heap = []                 # (exit_t, pnl, risk_dollars, trade_idx)
    open_risk = 0.0
    peak = equity; max_dd = 0.0
    warns = 0; peak_risk = 0.0
    trades = []
    curve = [dict(step=0, time=pd.NaT, event="start", equity=round(equity, 2),
                  peak=round(peak, 2), drawdown_pct=0.0)]
    step = 0

    def realize_until(t):
        nonlocal equity, open_risk, peak, max_dd, step
        while open_heap and open_heap[0][0] <= t:
            xt, pnl, rd, idx = heapq.heappop(open_heap)
            equity += pnl
            open_risk -= rd
            peak = max(peak, equity)
            dd = (equity - peak) / peak if peak > 0 else 0.0
            max_dd = min(max_dd, dd)
            step += 1
            trades[idx]["equity_after_close"] = round(equity, 2)
            curve.append(dict(step=step, time=xt,
                              event=f"close {trades[idx]['asset']} {trades[idx]['tf']} "
                                    f"{trades[idx]['outcome']}",
                              equity=round(equity, 2), peak=round(peak, 2),
                              drawdown_pct=round(dd * 100, 2)))

    for s in sigs:
        realize_until(s["entry_t"])
        risk_d = risk_pct * equity
        total_after = open_risk + risk_d
        open_risk_pct = (total_after / equity * 100) if equity > 0 else 0.0
        warned = open_risk_pct > RISK_CEILING * 100
        if warned:
            warns += 1
        peak_risk = max(peak_risk, open_risk_pct)
        pnl = s["R"] * risk_d
        idx = len(trades)
        trades.append(dict(
            n=idx + 1,
            entry_time_utc=s["entry_t"],
            exit_time_utc=(pd.NaT if s["outcome"] == "OPEN" else s["exit_t"]),
            asset=s["asset"], tf=s["tf"], side=s["side"], outcome=s["outcome"],
            entry_price=s["entry_price"], stop_price=s["stop_price"],
            target_price=s["target_price"], R=round(s["R"], 3),
            equity_at_entry=round(equity, 2),
            risk_dollars=round(risk_d, 2),
            pnl_dollars=round(pnl, 2),
            open_risk_pct=round(open_risk_pct, 1),
            over_40pct=("YES" if warned else ""),
            equity_after_close=None,
        ))
        heapq.heappush(open_heap, (s["exit_t"], pnl, risk_d, idx))
        open_risk += risk_d

    # flush remaining opens
    realize_until(pd.Timestamp.max)

    wins = sum(1 for t in trades if t["outcome"] == "TP")
    losses = sum(1 for t in trades if t["outcome"] == "SL")
    opens = sum(1 for t in trades if t["outcome"] == "OPEN")
    summary = dict(risk_pct=f"{risk_pct*100:.0f}%",
                   final_equity=round(equity, 2),
                   return_pct=round(100 * (equity / START_EQ - 1), 1),
                   max_drawdown_pct=round(max_dd * 100, 1),
                   warnings_over_40pct=warns,
                   peak_concurrent_risk_pct=round(peak_risk, 1),
                   wins=wins, losses=losses, open=opens, signals=len(trades))
    return pd.DataFrame(trades), pd.DataFrame(curve), summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    args = ap.parse_args()

    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    sigs = build_signals(now, args.days)
    s15 = [s for s in sigs if s["tf"] == "15m"]
    cov15 = (now - min(s["entry_t"] for s in s15)).days if s15 else 0

    results = {}
    for rp in (0.10, 0.05):
        results[rp] = detailed_sim(sigs, rp)

    out = ROOT / "logs" / f"v5_winners_equity_{args.days}d.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        summ = pd.DataFrame([results[0.10][2], results[0.05][2]])
        summ.to_excel(xl, sheet_name="Summary", index=False, startrow=1)
        ws = xl.sheets["Summary"]
        ws.cell(row=1, column=1,
                value=(f"Winners basket | ${START_EQ:.0f} start | last {args.days}d "
                       f"| 15m capped at {cov15}d, 1h-4h full {args.days}d "
                       f"| entry=bar close, SL 1.5xATR / TP 3xATR (+2R/-1R) "
                       f"| compounding, take-all, 40% open-risk warning"))
        r = len(summ) + 4
        ws.cell(row=r, column=1, value="READ THIS: the return column is what the "
                "curve ENDED at; the max_drawdown column is what you'd have had to "
                "survive on the way. -93% means the account fell to ~7% of its peak "
                "at the worst point. Hindsight-picked winners, single 90d window.")

        for rp, label in ((0.10, "10"), (0.05, "5")):
            tdf, cdf, _ = results[rp]
            tdf.to_excel(xl, sheet_name=f"Trades {label}pct", index=False)
            cdf.to_excel(xl, sheet_name=f"Equity {label}pct", index=False)

    print(f"Signals: {len(sigs)}  (15m coverage {cov15}d)")
    for rp in (0.10, 0.05):
        s = results[rp][2]
        print(f"  {s['risk_pct']:>4} -> ${s['final_equity']:,.2f} "
              f"({s['return_pct']:+.1f}%), maxDD {s['max_drawdown_pct']:.1f}%, "
              f"{s['warnings_over_40pct']} warns, peak risk {s['peak_concurrent_risk_pct']:.0f}%")
    print(f"Workbook -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
