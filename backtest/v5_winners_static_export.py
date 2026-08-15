"""Static (non-compounding) winners backtest -> Excel.

Model (per user's revised spec):
  * STATIC base equity $1,000. Risk per trade is a CONSTANT dollar amount =
    risk% x $1,000 (NOT % of current equity) -> 5% = $50/trade, 10% = $100/trade.
    No compounding: win = +2 x risk$, loss = -1 x risk$, open = R x risk$.
  * Running equity = $1,000 + cumulative P&L. Profits just accumulate and are
    tracked (no re-sizing off the growth).
  * 40% loss warning measured from the STATIC $1,000 base: fires when equity
    falls to <= $600 (net loss >= $400). Trading CONTINUES; we only flag/count.
  * Window: last 90 days, winners basket, risk 5% and 10%.

Because risk$ is constant, the final total is order-independent; only the
drawdown path and when the $600 warning fires depend on sequence, so the equity
curve is walked in trade-CLOSE order.

Output: logs/v5_winners_static_90d.xlsx
  Summary        — 5% vs 10% headline (final, net profit, max DD, $600 breaches).
  Trades 5/10pct — per signal: times, prices, R, constant risk$, $ P&L, equity
                   after close, and a flag when that close leaves equity <= $600.
  Equity 5/10pct — equity curve in close order with peak, drawdown-from-peak %,
                   and a below-$600 flag.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.v5_winners_equity_risk import build_signals   # noqa: E402

BASE_EQ = 1000.0
WARN_LEVEL = 0.40 * BASE_EQ        # equity <= $600 -> 40% loss warning
WARN_FLOOR = BASE_EQ - WARN_LEVEL  # $600


def run(sigs, risk_pct):
    risk_d = risk_pct * BASE_EQ                 # constant $ per trade
    # per-trade rows (entry order)
    trades = []
    for i, s in enumerate(sigs):
        pnl = s["R"] * risk_d
        trades.append(dict(
            n=i + 1, entry_time_utc=s["entry_t"],
            exit_time_utc=(pd.NaT if s["outcome"] == "OPEN" else s["exit_t"]),
            asset=s["asset"], tf=s["tf"], side=s["side"], outcome=s["outcome"],
            entry_price=s["entry_price"], stop_price=s["stop_price"],
            target_price=s["target_price"], R=round(s["R"], 3),
            risk_dollars=round(risk_d, 2), pnl_dollars=round(pnl, 2),
            equity_after_close=None, warn_below_600="",
            _exit=s["exit_t"], _pnl=pnl))

    # walk in CLOSE order for the equity path / warning timing
    order = sorted(range(len(trades)), key=lambda k: trades[k]["_exit"])
    equity = BASE_EQ
    peak = BASE_EQ
    max_dd = 0.0
    min_eq = BASE_EQ
    breaches = 0
    prev_below = False
    curve = [dict(step=0, time=pd.NaT, event="start", equity=round(equity, 2),
                  peak=round(peak, 2), drawdown_from_peak_pct=0.0, below_600="")]
    for step, k in enumerate(order, start=1):
        equity += trades[k]["_pnl"]
        peak = max(peak, equity)
        dd = (equity - peak) / peak if peak > 0 else 0.0
        max_dd = min(max_dd, dd)
        min_eq = min(min_eq, equity)
        below = equity <= WARN_FLOOR
        if below and not prev_below:
            breaches += 1
        prev_below = below
        trades[k]["equity_after_close"] = round(equity, 2)
        trades[k]["warn_below_600"] = "YES" if below else ""
        curve.append(dict(step=step, time=trades[k]["_exit"],
                          event=f"close {trades[k]['asset']} {trades[k]['tf']} "
                                f"{trades[k]['outcome']}",
                          equity=round(equity, 2), peak=round(peak, 2),
                          drawdown_from_peak_pct=round(dd * 100, 2),
                          below_600=("YES" if below else "")))

    wins = sum(1 for t in trades if t["outcome"] == "TP")
    losses = sum(1 for t in trades if t["outcome"] == "SL")
    opens = sum(1 for t in trades if t["outcome"] == "OPEN")
    tdf = pd.DataFrame([{k: v for k, v in t.items() if not k.startswith("_")}
                        for t in trades])
    cdf = pd.DataFrame(curve)
    summary = dict(
        risk_pct=f"{risk_pct*100:.0f}%", risk_per_trade=f"${risk_d:,.0f}",
        final_equity=round(equity, 2), net_profit=round(equity - BASE_EQ, 2),
        return_pct_on_1000=round(100 * (equity - BASE_EQ) / BASE_EQ, 1),
        wins=wins, losses=losses, open=opens, signals=len(trades),
        max_drawdown_from_peak_pct=round(max_dd * 100, 1),
        min_equity=round(min_eq, 2),
        hit_40pct_loss=("YES" if min_eq <= WARN_FLOOR else "NO"),
        times_warning_fired=breaches)
    return tdf, cdf, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    args = ap.parse_args()

    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    sigs = build_signals(now, args.days)
    s15 = [s for s in sigs if s["tf"] == "15m"]
    cov15 = (now - min(s["entry_t"] for s in s15)).days if s15 else 0

    results = {rp: run(sigs, rp) for rp in (0.10, 0.05)}

    out = ROOT / "logs" / f"v5_winners_static_{args.days}d.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        summ = pd.DataFrame([results[0.10][2], results[0.05][2]])
        summ.to_excel(xl, sheet_name="Summary", index=False, startrow=2)
        ws = xl.sheets["Summary"]
        ws.cell(row=1, column=1,
                value=(f"STATIC $1,000 base | NON-compounding | risk = fixed $ "
                       f"(risk% x $1,000) | last {args.days}d | 15m capped at "
                       f"{cov15}d, 1h-4h full {args.days}d | SL 1.5xATR / TP 3xATR "
                       f"(+2R/-1R)"))
        ws.cell(row=2, column=1,
                value="40% warning = equity <= $600 (loss of $400 from the $1,000 "
                      "base). Trading continues; column counts how many times it fired.")
        for rp, label in ((0.10, "10"), (0.05, "5")):
            tdf, cdf, _ = results[rp]
            tdf.to_excel(xl, sheet_name=f"Trades {label}pct", index=False)
            cdf.to_excel(xl, sheet_name=f"Equity {label}pct", index=False)

    print(f"Signals: {len(sigs)}  (15m coverage {cov15}d)  static $1,000 base\n")
    for rp in (0.10, 0.05):
        s = results[rp][2]
        print(f"{s['risk_pct']:>4} (${s['risk_per_trade']}/trade): "
              f"final ${s['final_equity']:,.2f}  net {s['net_profit']:+,.2f}  "
              f"({s['return_pct_on_1000']:+.1f}%)  | maxDD-from-peak "
              f"{s['max_drawdown_from_peak_pct']:.1f}%  min ${s['min_equity']:,.2f}  "
              f"| hit -40%? {s['hit_40pct_loss']} ({s['times_warning_fired']}x)  "
              f"| W{s['wins']}/L{s['losses']}/O{s['open']}")
    print(f"\nWorkbook -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
