"""Build the TD Sequential study workbook from logs/td_grid.csv."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
g = pd.read_csv(ROOT/"logs"/"td_grid.csv")
TFS = ["15m", "30m", "45m", "1h", "2h", "3h", "4h", "1d"]
assets = list(dict.fromkeys(g.asset))


def tier(n):
    return "high" if n >= 50 else "med" if n >= 20 else "low" if n >= 8 else "tiny"


g["conf"] = g.n.apply(tier)

# ---- 1) Best (tf, filter) per asset by ATR expectancy, n>=8 ----
best = []
for a in assets:
    sub = g[(g.asset == a) & (g.n >= 8)]
    if sub.empty:
        continue
    top = sub.sort_values("atr_expR", ascending=False).iloc[0]
    # a 'recommended' pick preferring sample size (n>=20 if any positive)
    rec_pool = sub[(sub.n >= 20) & (sub.atr_expR > 0)]
    rec = (rec_pool.sort_values("atr_expR", ascending=False).iloc[0]
           if not rec_pool.empty else top)
    best.append(dict(
        asset=a,
        best_tf=top.tf, best_filter=top["filter"], n=int(top.n),
        conf=tier(top.n), atr_winpct=top.atr_win, atr_expR=top.atr_expR,
        atr_totR=top.atr_totR, atr_pf=top.atr_pf,
        hold_expR=top.hold_expR, hold_winpct=top.hold_win,
        recommend_tf=rec.tf, recommend_filter=rec["filter"],
        recommend_n=int(rec.n), recommend_expR=rec.atr_expR))
best = pd.DataFrame(best)

# ---- 2) Filter verdict: how each filter does vs raw (cells with n>=20) ----
verdict_rows = []
for f in ["raw", "trend", "vol", "rsi"]:
    sub = g[(g["filter"] == f) & (g.n >= 20)]
    if sub.empty:
        verdict_rows.append(dict(filter=f, cells=0)); continue
    best_counts = (best.best_filter == f).sum()
    verdict_rows.append(dict(
        filter=f, cells=len(sub),
        mean_expR=round(sub.atr_expR.mean(), 3),
        median_expR=round(sub.atr_expR.median(), 3),
        pct_cells_positive=round(100*(sub.atr_expR > 0).mean(), 1),
        mean_winpct=round(sub.atr_win.mean(), 1),
        times_best_of_asset=int(best_counts)))
verdict = pd.DataFrame(verdict_rows)

# ---- 3) Trend-filter: best timeframe per asset (the practical answer) ----
trend_best = []
for a in assets:
    sub = g[(g.asset == a) & (g["filter"] == "trend") & (g.n >= 8)]
    if sub.empty:
        continue
    top = sub.sort_values("atr_expR", ascending=False).iloc[0]
    byR = sub.sort_values("atr_totR", ascending=False).iloc[0]
    trend_best.append(dict(
        asset=a, best_tf_by_edge=top.tf, edge_n=int(top.n), edge_conf=tier(top.n),
        edge_expR=top.atr_expR, edge_winpct=top.atr_win,
        best_tf_by_totalR=byR.tf, totalR=byR.atr_totR, totalR_n=int(byR.n)))
trend_best = pd.DataFrame(trend_best)

# ---- 4) Full grids (pivot-friendly, sorted) ----
atr_cols = ["asset", "tf", "filter", "n", "conf", "atr_win", "atr_expR", "atr_totR", "atr_pf"]
hold_cols = ["asset", "tf", "filter", "n", "conf", "hold_win", "hold_expR", "hold_totR", "hold_pf"]
g_atr = g[atr_cols].copy()
g_hold = g[hold_cols].copy()
g_atr["tf"] = pd.Categorical(g_atr.tf, TFS, ordered=True)
g_hold["tf"] = pd.Categorical(g_hold.tf, TFS, ordered=True)
g_atr = g_atr.sort_values(["asset", "filter", "tf"])
g_hold = g_hold.sort_values(["asset", "filter", "tf"])

readme = pd.DataFrame({"Enhanced TD Sequential study — read me": [
    "SIGNAL: TD setup-9. BUY = 9 consecutive closes < close[4] -> mean-reversion LONG.",
    "        SELL = 9 consecutive closes > close[4] -> mean-reversion SHORT. Countdown excluded (broken in the script).",
    "",
    "FILTERS (each a subset, compared vs raw):",
    "  raw   = every setup-9.",
    "  trend = aligned with chart-native 200-SMA (LONG above / SHORT below = buy dips in uptrends, sell rallies in downtrends).",
    "  vol   = setup bar volume > 1.5x SMA(vol,14). N/A for Yahoo FX (=X) feeds (no real volume).",
    "  rsi   = non-extreme directional: LONG if RSI<50, SHORT if RSI>50.",
    "",
    "EXIT MODELS:",
    "  ATR  = enter at setup-9 close, SL 1.5xATR, TP 4.0xATR (1:2.67). Win=+2.667R, Loss=-1R, unresolved=mark-to-market R.",
    "  HOLD = hold until the opposite setup-9 fires; R = favourable move / (1.5 x ATR at entry).",
    "",
    "CONFIDENCE by sample size n:  high>=50, med>=20, low>=8, tiny<8 (excluded from 'best').",
    "'best_*' = highest ATR expectancy at n>=8. 'recommend_*' prefers n>=20 positive cells (more trustworthy).",
    "",
    "CAVEATS:",
    "  - Data is yfinance with proxies: XAUUSD=GC=F, XAGUSD=SI=F, NAS100=NQ=F, DXY=DX-Y.NYB, XBRUSD=BZ=F. Not your OANDA feed.",
    "  - 15m/30m/45m history capped ~60d; 1h-derived ~730d; 1d ~10y. So intraday cells have fewer months than higher TFs.",
    "  - 1d bars are CALENDAR-day (not NY-close anchored); intraday uses ny17/utc anchors like the scanner.",
    "  - FX (=X) has no usable volume, so 'vol' rows are empty for those pairs.",
    "  - Positive expectancy at 30-45% win rate comes from the 1:2.67 payoff, not from being right often. Expect losing streaks.",
    "  - Small-sample 'best' cells (low/tiny) are directional hints, not proven edges.",
]})

out = ROOT/"logs"/"td_sequential_study.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as xl:
    best.to_excel(xl, sheet_name="Best per asset", index=False)
    verdict.to_excel(xl, sheet_name="Filter verdict", index=False)
    trend_best.to_excel(xl, sheet_name="Trend best TF per asset", index=False)
    g_atr.to_excel(xl, sheet_name="Full grid ATR", index=False)
    g_hold.to_excel(xl, sheet_name="Full grid HOLD", index=False)
    readme.to_excel(xl, sheet_name="README", index=False)

print("BEST PER ASSET:")
print(best[["asset", "best_tf", "best_filter", "n", "conf", "atr_expR",
            "atr_winpct", "recommend_tf", "recommend_filter", "recommend_n"]].to_string(index=False))
print("\nFILTER VERDICT:")
print(verdict.to_string(index=False))
print(f"\nWorkbook -> {out}")
