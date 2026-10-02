"""PHASE 10 / N-8 — sentiment factor sweep: does AV news-sentiment carry a tradable edge?

Sweeps the sentiment factor families (sent_rev = fade extremes, sent_mom = follow momentum), each
side, over a small z-threshold grid × asset class × timeframe × horizon, pooled and net of cost, on the
committed daily AV sentiment series (altdata_committed/news/av_sentiment.csv.gz, no-lookahead join).
Appends every cell to HYPOTHESIS_REGISTRY.csv as phase 10 and writes research/SENT_STUDY.md with an
inline MTC view (Bonferroni + Deflated-Sharpe benchmark over the phase-10 trial family). The binding
verdict is the shared gauntlet: `robustness.py --phase 10` (2x cost + sensitivity + Bonferroni + DSR).

Until the sentiment archive has accrued (free tier backfills ~25 windows/day via the harvester), most
cells are THIN and the honest output is "no data yet / nothing significant". News = context/filter
(D-021): a sentiment factor is only an edge if it clears the gauntlet.

Usage:  python research/jobs/sent_sweep.py --lake <dir> [--max N]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import backtest as bt       # noqa: E402
import mtc                  # noqa: E402
import sentfactor as SENT   # noqa: E402

REG = ROOT / "HYPOTHESIS_REGISTRY.csv"
REPORT = ROOT / "SENT_STUDY.md"
MIN = SENT.MIN_TRADES
PHASE = 10

CLASSES = ["forex_majors", "forex_crosses", "metals", "oil", "crypto"]
TFS = ["1h", "4h", "1day"]
HORIZONS = ["swing", "intraday"]
GRID = {"sent_rev": [{"side": s, "z": z} for s in ("long", "short") for z in (1.0, 1.5, 2.0)],
        "sent_mom": [{"side": s, "z": z} for s in ("long", "short") for z in (0.25, 0.5, 1.0)]}


def pstr(p): return ",".join(f"{k}={p[k]}" for k in sorted(p))
def fmt(x, nd=4):
    try:
        return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{float(x):.{nd}f}"
    except Exception:
        return str(x)


def existing_ids():
    try:
        return set(pd.read_csv(REG, usecols=["id"])["id"].astype(str))
    except Exception:
        return set()


def append_row(d):
    hdr = pd.read_csv(REG, nrows=0).columns.tolist()
    pd.DataFrame([{k: d.get(k, "") for k in hdr}]).to_csv(REG, mode="a", header=False, index=False)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--dsr", type=float, default=0.95)
    a = ap.parse_args()

    sent = SENT.load_sentiment()
    if sent.empty:
        REPORT.write_text(
            "# SENT_STUDY (N-8) — AV news-sentiment factor sweep\n\n"
            f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}._\n\n"
            "**No sentiment data yet.** The Alpha Vantage sentiment archive "
            "(`altdata_committed/news/av_sentiment.csv.gz`) is empty — the free-tier harvester "
            "(`research-avsentiment-refresh`, ~25 windows/day) is still backfilling. Re-run this sweep "
            "once the archive has ~1y of daily sentiment. Nothing evaluated; nothing claimed.\n",
            encoding="utf-8")
        print("SENT_STUDY: sentiment archive empty — wrote 'no data yet' report, nothing to sweep."); return 0
    classes = [c for c in CLASSES if SENT.CLASS_SENT.get(c) and
               (sent["instrument_class"] == SENT.CLASS_SENT[c]).any()]
    span = f"{sent['date'].min().date()} .. {sent['date'].max().date()}"
    print(f"sentiment span {span}; classes with data: {classes} (rows: {len(sent)})")

    done = existing_ids()
    cells = []
    n_new = 0
    for aclass in classes:
        for rule, plist in GRID.items():
            for params in plist:
                for tf in TFS:
                    for hz in HORIZONS:
                        idv = f"{rule}|{aclass}|{tf}|{hz}|{pstr(params)}|n10"
                        if idv in done:
                            continue
                        if a.max and n_new >= a.max:
                            print(f"hit --max {a.max}; stopping (resumable)"); _write(cells, a, span); return 0
                        res = SENT.evaluate_sent(a.lake, aclass, rule, params, hz, tf, 1.0)
                        sv = res["val"]
                        vtr = SENT.pooled_val_sent(a.lake, aclass, rule, params, hz, tf, 1.0, sent=sent)
                        R = vtr["net_R"].astype(float) if len(vtr) else pd.Series(dtype=float)
                        p = mtc.p_value_one_sided(sv["sharpe"], sv["n"]) if sv["n"] >= 2 else np.nan
                        cells.append(dict(aclass=aclass, rule=rule, tf=tf, hz=hz, params=params, val=sv, p=p,
                                          skew=float(R.skew()) if len(R) > 2 else np.nan,
                                          kurt=(float(R.kurt()) + 3.0) if len(R) > 3 else np.nan, idv=idv))
                        append_row(dict(
                            id=idv, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=PHASE,
                            hypothesis=f"{rule}({pstr(params)}) on AV sentiment", asset_class=aclass,
                            symbols=f"{aclass}-ALL", timeframe=tf, horizon=hz, params=pstr(params),
                            entry_rule=rule, exit_rule=f"SL1.5/TP3.0/{hz}", cost_model="x1.0-sent",
                            sample_val=sv["n"], winrate_val=sv["win"], expectancy_R_val=sv["expR"],
                            profit_factor_val=sv["pf"], max_dd_R=sv["maxdd_R"], sharpe_val=sv["sharpe"],
                            benchmark_random_R=res["random_expR"], benchmark_bh_R=res["buyhold_pct"],
                            survived=res["verdict"]))
                        done.add(idv); n_new += 1
                        print(f"{aclass:<13} {tf:<4} {hz:<8} {rule}({pstr(params)}): n={sv['n']} "
                              f"expR={fmt(sv['expR'])} pf={fmt(sv['pf'],2)} -> {res['verdict']}", flush=True)
    _write(cells, a, span)
    print(f"\n=== sentiment sweep: {n_new} new cells; report -> {REPORT.name} "
          f"(run robustness.py --phase 10 for the gauntlet) ===")
    return 0


def _write(cells, a, span):
    N = sum(1 for c in cells if c["val"]["n"] >= MIN)
    bonf = a.alpha / max(N, 1)
    sr_var = np.nanvar([c["val"]["sharpe"] for c in cells
                        if c["val"]["n"] >= MIN and np.isfinite(c["val"]["sharpe"])]) if N > 1 else np.nan
    sr_star = mtc.expected_max_sharpe(float(sr_var) if np.isfinite(sr_var) else 0.0, N)
    lines = [
        "# SENT_STUDY (N-8) — AV news-sentiment factor sweep",
        "",
        f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. Sentiment span {span}. Standing rule D-021._",
        f"- Phase-10 cells with n>=100 (MTC N): **{N}** -> Bonferroni p < {bonf:.4g}; "
        f"DSR benchmark SR*={fmt(sr_star,3)} (>{a.dsr}).",
        "- Factor families: `sent_rev` (fade z-score extremes), `sent_mom` (follow z momentum); "
        "no-lookahead daily join (day-D sentiment usable from D+1).",
        "- Binding verdict is the shared gauntlet: `robustness.py --phase 10`.",
        "",
        "| class | tf | hz | rule(params) | n | expR | pf | sharpe | p | verdict |",
        "|---|---|---|---|--:|--:|--:|--:|--:|:--|",
    ]
    for c in sorted(cells, key=lambda x: -(x["val"]["expR"] if np.isfinite(x["val"]["expR"]) else -9)):
        v = c["val"]
        dsr = mtc.deflated_sharpe(v["sharpe"], sr_star, v["n"], c["skew"], c["kurt"]) if v["n"] >= MIN else np.nan
        passes_mtc = v["n"] >= MIN and np.isfinite(c["p"]) and c["p"] < bonf and np.isfinite(dsr) and dsr > a.dsr
        tag = ("PASS" if v["n"] >= MIN and np.isfinite(v["expR"]) and v["expR"] > 0 and v["pf"] > 1
               else ("THIN" if v["n"] < MIN else "FAIL")) + (" ✓MTC" if passes_mtc else "")
        lines.append(f"| {c['aclass']} | {c['tf']} | {c['hz']} | {c['rule']}({pstr(c['params'])}) | {v['n']} | "
                     f"{fmt(v['expR'])} | {fmt(v['pf'],2)} | {fmt(v['sharpe'],3)} | {fmt(c['p'],4)} | {tag} |")
    lines += ["", "## Summary", "",
              f"- {len(cells)} sentiment cells evaluated. A cell is a real edge only if it also clears the "
              "gauntlet (✓MTC here, then `robustness.py --phase 10`) — none unless marked."]
    if not cells:
        lines += ["", "_No cell reached evaluation (archive still backfilling / classes without sentiment)._"]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
