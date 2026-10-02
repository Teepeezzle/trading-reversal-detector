"""PHASE 9 / N-5 — news-gate study: does a news filter improve expectancy, or just cut trades?

For each technical base rule with enough trades, compares BASE vs each NEWS-GATED variant on the
validation set (net of cost), across the asset classes that have news (oil=EIA; forex/metals=FRED).
Answers standing-rule D-021 §6. Writes research/NEWS_STUDY.md and appends the gated hypotheses to
HYPOTHESIS_REGISTRY.csv as phase 9 (entry_rule "<rule>+news:<gate>"), each judged by the same gauntlet
machinery (2x cost + Bonferroni + Deflated Sharpe) within the news-study MTC family.

A gate can only ever REDUCE trades (it filters entries); the question is whether the kept trades are
better. Verdict per cell: "improves" (gated expR clearly > base and positive), "just-cuts" (expR ~flat,
fewer trades), or "hurts".

Usage:  python research/jobs/news_study.py --lake <dir> [--max N]
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
import newsfactor as NF     # noqa: E402

REG = ROOT / "HYPOTHESIS_REGISTRY.csv"
REPORT = ROOT / "NEWS_STUDY.md"
MIN = NF.MIN_TRADES
PHASE = 9

BASES = [("donch_brk", {"n": 20}), ("rsi_rev", {"n": 14, "os": 30}),
         ("bb_breakout", {"n": 20, "kstd": 2.0}), ("zscore_rev", {"n": 20, "z": 2.0}),
         ("roc_mom", {"n": 10, "thr": 0.0})]
CLASSES = ["oil", "forex_majors", "forex_crosses", "metals"]
TFS = ["1h", "4h", "1day"]
HORIZONS = ["swing", "intraday"]


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

    news = NF.load_news()
    if news.empty:
        print("No news table (research/altdata_committed/news/) — run news_refresh first."); return 0
    classes = [c for c in CLASSES if NF.NEWS_NAMES.get(c) and
               news["name"].isin(NF.NEWS_NAMES[c]).any()]
    print(f"news classes with data: {classes}  (news rows: {len(news)})")
    done = existing_ids()
    cells = []            # for MTC + report
    n_new = 0
    for aclass in classes:
        for rule, params in BASES:
            for tf in TFS:
                for hz in HORIZONS:
                    base = NF._pooled(a.lake, aclass, rule, params, hz, tf, None, 1.0, news)
                    bv = bt.stats(base[base.split == "val"] if len(base) else base)
                    if bv["n"] < MIN:                       # base too thin to judge a filter
                        continue
                    for gate in NF.NEWS_GATES:
                        idv = f"{rule}+news:{gate}|{aclass}|{tf}|{hz}|{pstr(params)}|n9"
                        if idv in done:
                            continue
                        if a.max and n_new >= a.max:
                            print(f"hit --max {a.max}; stopping (resumable)"); _write(cells, a); return 0
                        gated = NF._pooled(a.lake, aclass, rule, params, hz, tf, NF.NEWS_GATES[gate], 1.0, news)
                        gv = bt.stats(gated[gated.split == "val"] if len(gated) else gated)
                        R = gated[gated.split == "val"]["net_R"].astype(float) if len(gated) else pd.Series(dtype=float)
                        p = mtc.p_value_one_sided(gv["sharpe"], gv["n"]) if gv["n"] >= 2 else np.nan
                        cells.append(dict(aclass=aclass, rule=rule, tf=tf, hz=hz, gate=gate, params=params,
                                          base=bv, gated=gv, p=p,
                                          skew=float(R.skew()) if len(R) > 2 else np.nan,
                                          kurt=(float(R.kurt()) + 3.0) if len(R) > 3 else np.nan, idv=idv))
                        append_row(dict(
                            id=idv, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=PHASE,
                            hypothesis=f"{rule}({pstr(params)}) & news:{gate}", asset_class=aclass,
                            symbols=f"{aclass}-ALL", timeframe=tf, horizon=hz, params=pstr(params),
                            entry_rule=f"{rule}+news:{gate}", exit_rule=f"SL1.5/TP3.0/{hz}", cost_model="x1.0-news",
                            sample_val=gv["n"], winrate_val=gv["win"], expectancy_R_val=gv["expR"],
                            profit_factor_val=gv["pf"], max_dd_R=gv["maxdd_R"], sharpe_val=gv["sharpe"],
                            survived="PASS" if (gv["n"] >= MIN and np.isfinite(gv["expR"]) and gv["expR"] > 0
                                                and gv["pf"] > 1) else ("THIN" if gv["n"] < MIN else "FAIL")))
                        done.add(idv); n_new += 1
                        print(f"{aclass:<13} {tf:<4} {hz:<8} {rule}+{gate:<10} base n={bv['n']} expR={fmt(bv['expR'])}"
                              f" | gated n={gv['n']} expR={fmt(gv['expR'])}", flush=True)
    _write(cells, a)
    print(f"\n=== news study: {n_new} new cells; report -> {REPORT.name} ===")
    return 0


def _verdict(bv, gv):
    if gv["n"] < MIN or not np.isfinite(gv["expR"]):
        return "thin-gated"
    if gv["expR"] > bv["expR"] + 0.02 and gv["expR"] > 0:
        return "IMPROVES"
    if abs(gv["expR"] - bv["expR"]) <= 0.02:
        return "just-cuts-trades"
    return "hurts"


def _write(cells, a):
    N = sum(1 for c in cells if c["gated"]["n"] >= MIN)
    bonf = a.alpha / max(N, 1)
    sr_var = np.nanvar([c["gated"]["sharpe"] for c in cells if c["gated"]["n"] >= MIN and np.isfinite(c["gated"]["sharpe"])]) if N > 1 else np.nan
    sr_star = mtc.expected_max_sharpe(float(sr_var) if np.isfinite(sr_var) else 0.0, N)
    lines = [
        "# NEWS_STUDY (N-5) — does a news gate improve expectancy, or just cut trades?",
        "",
        f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. Standing rule D-021 §6._",
        f"- Gated cells with n>=100 (MTC N): **{N}** -> Bonferroni p < {bonf:.4g}; DSR benchmark SR*={fmt(sr_star,3)} (>{a.dsr}).",
        "- A gate can only reduce trades; the question is whether the kept trades are better, net of cost.",
        "",
        "| class | tf | hz | rule + gate | base n | base expR | gated n | gated expR | p | verdict |",
        "|---|---|---|---|--:|--:|--:|--:|--:|:--|",
    ]
    improves = []
    for c in sorted(cells, key=lambda x: -(x["gated"]["expR"] if np.isfinite(x["gated"]["expR"]) else -9)):
        v = _verdict(c["base"], c["gated"])
        dsr = mtc.deflated_sharpe(c["gated"]["sharpe"], sr_star, c["gated"]["n"], c["skew"], c["kurt"]) if c["gated"]["n"] >= MIN else np.nan
        passes_mtc = c["gated"]["n"] >= MIN and np.isfinite(c["p"]) and c["p"] < bonf and np.isfinite(dsr) and dsr > a.dsr
        tag = v + (" ✓MTC" if passes_mtc else "")
        lines.append(f"| {c['aclass']} | {c['tf']} | {c['hz']} | {c['rule']}+{c['gate']} | {c['base']['n']} | "
                     f"{fmt(c['base']['expR'])} | {c['gated']['n']} | {fmt(c['gated']['expR'])} | {fmt(c['p'],4)} | {tag} |")
        if v == "IMPROVES":
            improves.append(c)
    lines += ["", "## Summary", "",
              f"- {len(cells)} gated cells judged against their base. {len(improves)} show improved expectancy.",
              "- 'just-cuts-trades' = the filter removed trades without raising expectancy (a valid, common result).",
              "- A gate is only a real edge if it also clears the MTC bar (✓MTC) — none unless marked."]
    if not cells:
        lines += ["", "_No base rule reached 100 validation trades on the classes with news yet "
                  "(oil is shallow; FX/metals macro arrives once FRED is fixed — B-005)._"]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
