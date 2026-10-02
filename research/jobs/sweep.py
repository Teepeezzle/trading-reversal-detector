"""PHASE 3 — systematic single-factor SWEEP (idempotent, resumable).

Loops a GRID of rules × params × asset-classes × horizons × timeframes, evaluates each pooled
(no-lookahead, net-of-cost, benchmarks) and APPENDS one row per hypothesis to HYPOTHESIS_REGISTRY.csv.
Idempotent: a hypothesis whose `id` is already in the registry is skipped, so re-runs never
double-count. Resumable: `--max N` processes at most N new hypotheses per run (for Actions limits).

Grid size (default): ~220 hypotheses. Baseline cost (1x); the 2x-cost / parameter-sensitivity /
multiple-testing passes (T-303) run separately on whatever survives validation here.

Usage:
  python research/jobs/sweep.py --lake <dir> [--aclass crypto] [--max 60] [--rc_iters 8]
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
import factors as F   # noqa: E402

GRID_RULES = {
    "rsi_rev":   [{"n": 7, "os": 30}, {"n": 14, "os": 30}, {"n": 14, "os": 20}, {"n": 21, "os": 30}],
    "donch_brk": [{"n": 20}, {"n": 55}],
    "ema_cross": [{"f": 20, "s": 50}, {"f": 50, "s": 200}],
    "zscore_rev": [{"n": 20, "z": 2.0}, {"n": 20, "z": 2.5}, {"n": 50, "z": 2.0}],
}
HORIZONS = ["swing", "intraday"]
TFS = ["1h", "4h"]
ACLASSES = ["forex_majors", "forex_crosses", "metals", "oil", "crypto"]
REG = ROOT / "HYPOTHESIS_REGISTRY.csv"


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
    ap.add_argument("--max", type=int, default=0, help="max NEW hypotheses this run (0=unlimited)")
    ap.add_argument("--rc_iters", type=int, default=8, help="random-control iterations (speed)")
    a = ap.parse_args()

    if not any(Path(a.lake).rglob("*.csv.gz")):
        print(f"No lake data under {a.lake} — nothing to sweep (run data-refresh first)."); return 0
    classes = ACLASSES if a.aclass == "all" else [c.strip() for c in a.aclass.split(",")]
    done = existing_ids()
    combos = [(cls, rule, p, hz, tf)
              for cls in classes
              for rule, plist in GRID_RULES.items()
              for p in plist for hz in HORIZONS for tf in TFS]

    n_new = n_skip = 0; verdicts = {"PASS": 0, "FAIL": 0, "THIN": 0}
    passes = []
    for cls, rule, p, hz, tf in combos:
        idv = f"{rule}|{cls}|{tf}|{hz}|{pstr(p)}|c1.0"
        if idv in done:
            n_skip += 1; continue
        if a.max and n_new >= a.max:
            print(f"hit --max {a.max}; stopping (resumable — re-run to continue)"); break
        try:
            r = F.evaluate(a.lake, cls, rule, p, hz, tf, rc_iters=a.rc_iters)
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {idv}: {exc}"); continue
        st, sv = r["train"], r["val"]
        append_row(dict(
            id=idv, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=3,
            hypothesis=f"{rule}({pstr(p)})", asset_class=cls, symbols=f"{cls}-ALL",
            timeframe=tf, horizon=hz, params=pstr(p), entry_rule=rule,
            exit_rule=f"SL1.5/TP3.0/{hz}", cost_model="x1.0",
            sample_train=st["n"], sample_val=sv["n"], winrate_train=st["win"], winrate_val=sv["win"],
            expectancy_R_train=st["expR"], expectancy_R_val=sv["expR"], profit_factor_val=sv["pf"],
            max_dd_R=sv["maxdd_R"], sharpe_val=sv["sharpe"], benchmark_bh_R=r["buyhold_pct"],
            benchmark_random_R=r["random_expR"], survived=r["verdict"]))
        done.add(idv); n_new += 1; verdicts[r["verdict"]] += 1
        if r["verdict"] == "PASS":
            passes.append(f"{idv}  valExpR={sv['expR']} pf={sv['pf']} n={sv['n']}")
        print(f"{r['verdict']:<4} {cls:<13} {tf} {hz:<8} {rule}({pstr(p)}) "
              f"valN={sv['n']} expR={sv['expR']} (rnd {r['random_expR']})", flush=True)

    print(f"\n=== sweep done: {n_new} new, {n_skip} already-done, {len(combos)} in grid ===")
    print(f"verdicts: {verdicts}")
    if passes:
        print("PASS (validation — NOT yet candidates; need 2x-cost + sensitivity + MTC):")
        for x in passes:
            print("  " + x)
    else:
        print("No validation PASS in this batch — the honest expected result for naive single factors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
