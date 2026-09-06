"""TD Sequential study workbook v2 — HOLD-to-opposite lens as primary.

Re-ranks the existing grid (logs/td_grid.csv) so each asset's 'best timeframe'
reflects the HOLD-to-opposite exit (hold until the opposite setup-9 fires) —
the lens that matches how the user reads these signals on the chart — with the
tight-ATR-stop lens kept alongside and a side-by-side agreement sheet.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
g = pd.read_csv(ROOT/"logs"/"td_grid.csv")
TFS = ["15m", "30m", "45m", "1h", "2h", "3h", "4h", "1d"]
assets = list(dict.fromkeys(g.asset))


def tier(n):
    return "high" if n >= 50 else "med" if n >= 20 else "low" if n >= 8 else "tiny"


g["conf"] = g.n.apply(tier)


def best_by(metric, minn_best=8, minn_rec=30):
    rows = []
    for a in assets:
        sub = g[(g.asset == a) & (g.n >= minn_best)]
        if sub.empty:
            continue
        top = sub.sort_values(metric, ascending=False).iloc[0]
        pool = sub[(sub.n >= minn_rec) & (sub[metric] > 0)]
        rec = pool.sort_values(metric, ascending=False).iloc[0] if not pool.empty else top
        rows.append(dict(asset=a, best_tf=top.tf, best_filter=top["filter"],
                         n=int(top.n), conf=tier(top.n),
                         hold_winpct=top.hold_win, hold_expR=top.hold_expR,
                         hold_totR=top.hold_totR,
                         atr_winpct=top.atr_win, atr_expR=top.atr_expR,
                         recommend_tf=rec.tf, recommend_filter=rec["filter"],
                         recommend_n=int(rec.n), recommend_metric=round(rec[metric], 3)))
    return pd.DataFrame(rows)


best_hold = best_by("hold_expR")
best_atr = best_by("atr_expR")

# ---- Side-by-side: does the best TF agree across lenses? ----
side = []
for a in assets:
    sub = g[(g.asset == a) & (g.n >= 8)]
    if sub.empty:
        continue
    h = sub.sort_values("hold_expR", ascending=False).iloc[0]
    t = sub.sort_values("atr_expR", ascending=False).iloc[0]
    side.append(dict(
        asset=a,
        HOLD_tf=h.tf, HOLD_filter=h["filter"], HOLD_expR=h.hold_expR,
        HOLD_win=h.hold_win, HOLD_n=int(h.n),
        ATR_tf=t.tf, ATR_filter=t["filter"], ATR_expR=t.atr_expR,
        ATR_win=t.atr_win, ATR_n=int(t.n),
        agree_tf=("YES" if h.tf == t.tf else "no"),
        note=("both lenses agree" if h.tf == t.tf
              else f"HOLD favours {h.tf}, ATR favours {t.tf} — use HOLD for swing style")))
side = pd.DataFrame(side)

# ---- Filter verdict under HOLD (cells n>=20) ----
verdict = []
for f in ["raw", "trend", "vol", "rsi"]:
    sub = g[(g["filter"] == f) & (g.n >= 20)]
    if sub.empty:
        verdict.append(dict(filter=f, cells=0)); continue
    verdict.append(dict(
        filter=f, cells=len(sub),
        HOLD_mean_expR=round(sub.hold_expR.mean(), 3),
        HOLD_median_expR=round(sub.hold_expR.median(), 3),
        HOLD_pct_positive=round(100*(sub.hold_expR > 0).mean(), 1),
        HOLD_mean_win=round(sub.hold_win.mean(), 1),
        ATR_mean_expR=round(sub.atr_expR.mean(), 3),
        times_best_HOLD=int((best_hold.best_filter == f).sum())))
verdict = pd.DataFrame(verdict)

# ---- Full grids ----
gc_atr = ["asset", "tf", "filter", "n", "conf", "atr_win", "atr_expR", "atr_totR", "atr_pf"]
gc_hold = ["asset", "tf", "filter", "n", "conf", "hold_win", "hold_expR", "hold_totR", "hold_pf"]
ga = g[gc_atr].copy(); gh = g[gc_hold].copy()
for gg in (ga, gh):
    gg["tf"] = pd.Categorical(gg.tf, TFS, ordered=True)
ga = ga.sort_values(["asset", "filter", "tf"])
gh = gh.sort_values(["asset", "filter", "tf"])

readme = pd.DataFrame({"TD Sequential study v2 — HOLD-primary — read me": [
    "CHANGE FROM v1: assets are now ranked by the HOLD-to-opposite exit (the lens that matches",
    "reading the chart), not the tight 1.5xATR stop. The ATR lens is kept alongside for comparison.",
    "",
    "WHY: TD setups are swing/mean-reversion signals. A 1.5xATR stop gets knocked out on the pullback",
    "BEFORE the move you capture by holding, so ATR win rates look low (19-31%) even where the setups",
    "clearly work. Example: XAUUSD 3h raw = 26.6% win / -0.02R under ATR, but 66.9% win / +0.32R under",
    "HOLD (n=139). The chart shows the HOLD reality; the ATR lens buried it.",
    "",
    "SHEETS:",
    "  Best by HOLD  = each asset's best (tf, filter) by hold expectancy. THE headline now.",
    "  Best by ATR   = same but under the tight-stop lens (v1's ranking).",
    "  Both lenses   = side by side; 'agree_tf'=YES means both lenses pick the same timeframe (trust those most).",
    "  Filter verdict= which filter helps, under both lenses (cells n>=20).",
    "  Full grid ATR / HOLD = every asset x tf x filter cell.",
    "",
    "HOLD lens definition: enter at setup-9 close, exit when the opposite setup-9 fires.",
    "  hold_expR = favourable move / (1.5 x ATR at entry).  hold_win = % of holds ending favourable.",
    "",
    "IMPORTANT CAVEAT ON HOLD: it has NO stop, so a hold can sit through a large adverse move before the",
    "opposite setup appears. High hold win-rate does NOT mean low drawdown. You must be able to hold through",
    "the pain. If you can't, you need a wider stop than 1.5xATR (e.g. 3-4xATR) — a middle ground we can test.",
    "",
    "CONFIDENCE: high n>=50, med n>=20, low n>=8, tiny<8. 'recommend_*' prefers n>=30 positive cells.",
    "DATA CAVEATS: proxies (XAUUSD=GC=F futures vs your OANDA spot, etc.); 15m/30m/45m ~60d, 1h-derived ~730d,",
    "  1d ~10y (calendar-day, not NY-close); FX has no volume so 'vol' rows are empty for =X pairs.",
]})

out = ROOT/"logs"/"td_sequential_study_v2.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as xl:
    best_hold.to_excel(xl, sheet_name="Best by HOLD", index=False)
    best_atr.to_excel(xl, sheet_name="Best by ATR", index=False)
    side.to_excel(xl, sheet_name="Both lenses", index=False)
    verdict.to_excel(xl, sheet_name="Filter verdict", index=False)
    ga.to_excel(xl, sheet_name="Full grid ATR", index=False)
    gh.to_excel(xl, sheet_name="Full grid HOLD", index=False)
    readme.to_excel(xl, sheet_name="README", index=False)

print("=== BEST BY HOLD (per asset) ===")
print(best_hold[["asset", "best_tf", "best_filter", "n", "conf", "hold_winpct",
                 "hold_expR", "hold_totR", "recommend_tf", "recommend_filter",
                 "recommend_n"]].to_string(index=False))
print("\n=== BOTH LENSES (agreement) ===")
print(side[["asset", "HOLD_tf", "HOLD_win", "HOLD_expR", "ATR_tf", "ATR_expR", "agree_tf"]].to_string(index=False))
print("\n=== FILTER VERDICT ===")
print(verdict.to_string(index=False))
print(f"\nWorkbook -> {out}")
