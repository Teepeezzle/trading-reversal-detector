"""Build the DRS range-coverage workbook from logs/drs_grid.csv + drs_signals.csv."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
g = pd.read_csv(ROOT/"logs"/"drs_grid.csv")
d = pd.read_csv(ROOT/"logs"/"drs_signals.csv")
TFS = ["15m", "30m", "45m", "1h", "2h", "3h", "4h", "1d"]
assets = list(dict.fromkeys(g.asset))
var_map = g[["asset", "variant"]].drop_duplicates().set_index("asset")["variant"].to_dict()


def tier(n):
    return "high" if n >= 50 else "med" if n >= 20 else "low" if n >= 10 else "tiny"


g["conf"] = g.n.apply(tier)

# Verdict: the 80% claim vs reality
dv = d.merge(g[["asset", "variant"]].drop_duplicates(), on="asset")
rows = [dict(scope="ALL signals", n=len(d),
             covered_pct=round(100*d.covered.mean(), 1),
             reached_green_pct=round(100*d.reached_green.mean(), 1),
             green_first_pct=round(100*d.green_first.mean(), 1),
             red_then_green_pct=round(100*d.red_first_then_green.mean(), 1),
             tradeable_expR=round(d.tradeR.mean(), 3))]
for v in ["native", "no-vol(FX/idx)"]:
    s = dv[dv.variant == v]
    rows.append(dict(scope=v, n=len(s),
                     covered_pct=round(100*s.covered.mean(), 1),
                     reached_green_pct=round(100*s.reached_green.mean(), 1),
                     green_first_pct=round(100*s.green_first.mean(), 1),
                     red_then_green_pct=round(100*s.red_first_then_green.mean(), 1),
                     tradeable_expR=round(s.tradeR.mean(), 3)))
verdict = pd.DataFrame(rows)

best_cov = g[g.n >= 10].sort_values("covered_pct", ascending=False).head(15).copy()
best_trade = g[g.n >= 15].sort_values("tradeable_expR", ascending=False).head(15).copy()

full = g.copy()
full["tf"] = pd.Categorical(full.tf, TFS, ordered=True)
full = full.sort_values(["asset", "tf"])

readme = pd.DataFrame({"Daily Reversal Pro — range-coverage validation — read me": [
    "CLAIM TESTED: once a signal draws the RED (stop, 1.5xATR) and GREEN (target, 3xATR) lines,",
    "price 'covers the range' (touches both) >80% of the time, usually traversing red->green.",
    "",
    "RESULT: the 80% claim is NOT supported.",
    "  covered (touched BOTH red and green) = 35.7% pooled (best single cell ~64%, never ~80%).",
    "  reached GREEN eventually (any order)  = 63.1% pooled.",
    "  the specific 'dip to red then recover to green' traverse = ~15% (the minority case).",
    "  -> The 80% impression is most likely eyeball/recall bias (remembering the covers, not the fails).",
    "",
    "BUT — the genuinely useful finding: as a STRAIGHT TRADE it is POSITIVE expectancy.",
    "  Enter on signal, target = green (3xATR), stop = red (1.5xATR):",
    "  green-before-red = 45.7% pooled (49.9% on volume assets); with the 2:1 payoff that is",
    "  tradeable_expR = +0.485R pooled, +0.597R on volume assets. Standouts: BTC 1h +1.0R,",
    "  NAS100 1h +0.88R, GBPUSD 1h +0.85R.  So it is a real signal — just not an 80% range-coverer.",
    "",
    "SIGNAL LOGIC (faithful to the Pine): emaBull(9/21 cross) AND 3-bar low AND volume spike AND",
    "  strong-up ATR bar, all on the SAME bar (mirror for shorts). These conditions nearly conflict",
    "  (an EMA up-cross on a fresh 3-bar low), so the signal is RARE: ~5-18 per timeframe over 2y on",
    "  volume assets. FX has no volume, so it was tested with the volume condition DROPPED ('no-vol').",
    "",
    "COLUMNS: covered_pct=touched both; reached_green_pct=hit green eventually; green_first_pct=green",
    "  before red (tradeable win); red_then_green_pct=wicked the stop then recovered; tradeable_expR=",
    "  +2R per green-first, -1R per red-first, 0 otherwise.",
    "CONFIDENCE n: high>=50, med>=20, low>=10, tiny<10. DATA: yfinance proxies; 15m/30m/45m ~60d,",
    "  1h-derived ~730d, 1d ~10y (calendar-day). Your OANDA feed will differ at the margin.",
]})

out = ROOT/"logs"/"drs_range_study.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as xl:
    verdict.to_excel(xl, sheet_name="Verdict (80pct claim)", index=False)
    best_trade.to_excel(xl, sheet_name="Best cells (tradeable)", index=False)
    best_cov.to_excel(xl, sheet_name="Best cells (coverage)", index=False)
    full.to_excel(xl, sheet_name="Full grid", index=False)
    readme.to_excel(xl, sheet_name="README", index=False)

print("VERDICT:")
print(verdict.to_string(index=False))
print(f"\nWorkbook -> {out}")
