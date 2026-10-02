"""PHASE 7 (Step A) — re-run the single-factor grids on the DEEP HistData FX/metals lake.

The honest retest: every Phase-3/5 near-miss died on statistical POWER (~100-300 pooled trades from
~52d of 15m / ~200d of 1h). With years of HistData depth, the SAME rules fire thousands of times, so
a real edge can finally clear a strict multiple-testing bar — and a fake one is exposed harder.

Re-runs the combined phase-3 + phase-5 rule grids (imported, not duplicated) across the DEEPENED
classes (forex_majors, forex_crosses, metals) at 15m/1h/4h/1D, both horizons. Writes rows tagged
**phase 7** with an id suffix `|deep` so they never collide with the shallow-data rows and form their
own multiple-testing family. Judge with robustness.py --phase 7. Idempotent + resumable (--max).

Usage:  python research/jobs/deep_resweep.py --lake <dir> [--max 120] [--rc_iters 8]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
import factors as F        # noqa: E402
import sweep as S3         # noqa: E402  (phase-3 GRID_RULES)
import family_sweep as S5  # noqa: E402  (phase-5 GRID_RULES)

GRID_RULES = {**S3.GRID_RULES, **S5.GRID_RULES}
HORIZONS = ["swing", "intraday"]
TFS = ["15min", "1h", "4h", "1day"]
ACLASSES = ["forex_majors", "forex_crosses", "metals"]   # the HistData-deepened classes
REG = ROOT / "HYPOTHESIS_REGISTRY.csv"
PHASE = 7


def pstr(p: dict) -> str:
    return ",".join(f"{k}={p[k]}" for k in sorted(p))


def existing_ids() -> set:
    try:
        return set(pd.read_csv(REG, usecols=["id"])["id"].astype(str))
    except Exception:
        return set()


def append_row(d: dict):
    hdr = pd.read_csv(REG, nrows=0).columns.tolist()
    pd.DataFrame([{k: d.get(k, "") for k in hdr}]).to_csv(REG, mode="a", header=False, index=False)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--aclass", default="all")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--rc_iters", type=int, default=8)
    a = ap.parse_args()

    if not any(Path(a.lake).rglob("*.csv.gz")):
        print(f"No lake data under {a.lake} — run the deep refresh first."); return 0
    classes = ACLASSES if a.aclass == "all" else [c.strip() for c in a.aclass.split(",")]
    done = existing_ids()
    combos = [(cls, rule, p, hz, tf)
              for cls in classes
              for rule, plist in GRID_RULES.items()
              for p in plist for hz in HORIZONS for tf in TFS]

    n_new = n_skip = 0; verdicts = {"PASS": 0, "FAIL": 0, "THIN": 0}; passes = []
    for cls, rule, p, hz, tf in combos:
        idv = f"{rule}|{cls}|{tf}|{hz}|{pstr(p)}|deep"
        if idv in done:
            n_skip += 1; continue
        if a.max and n_new >= a.max:
            print(f"hit --max {a.max}; stopping (resumable)"); break
        try:
            r = F.evaluate(a.lake, cls, rule, p, hz, tf, rc_iters=a.rc_iters)
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {idv}: {exc}"); continue
        st, sv = r["train"], r["val"]
        append_row(dict(
            id=idv, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=PHASE,
            hypothesis=f"{rule}({pstr(p)}) [deep]", asset_class=cls, symbols=f"{cls}-ALL",
            timeframe=tf, horizon=hz, params=pstr(p), entry_rule=rule,
            exit_rule=f"SL1.5/TP3.0/{hz}", cost_model="x1.0-deep",
            sample_train=st["n"], sample_val=sv["n"], winrate_train=st["win"], winrate_val=sv["win"],
            expectancy_R_train=st["expR"], expectancy_R_val=sv["expR"], profit_factor_val=sv["pf"],
            max_dd_R=sv["maxdd_R"], sharpe_val=sv["sharpe"], benchmark_bh_R=r["buyhold_pct"],
            benchmark_random_R=r["random_expR"], survived=r["verdict"]))
        done.add(idv); n_new += 1; verdicts[r["verdict"]] += 1
        if r["verdict"] == "PASS":
            passes.append(f"{idv}  valExpR={sv['expR']} pf={sv['pf']} n={sv['n']}")
        print(f"{r['verdict']:<4} {cls:<13} {tf:<5} {hz:<8} {rule}({pstr(p)}) "
              f"valN={sv['n']} expR={sv['expR']} (rnd {r['random_expR']})", flush=True)

    print(f"\n=== deep resweep done: {n_new} new, {n_skip} already-done, {len(combos)} in grid ===")
    print(f"verdicts: {verdicts}")
    if passes:
        print("PASS (validation — judge with robustness.py --phase 7):")
        for x in passes:
            print("  " + x)
    else:
        print("No validation PASS in this batch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
