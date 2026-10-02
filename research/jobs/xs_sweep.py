"""PHASE 6 — cross-sectional relative-strength SWEEP (idempotent, resumable).

Grid over asset-class x timeframe x (lookback L, hold H) x k x mode, evaluated with the portable
cross-sectional engine (research/src/xsectional.py): rank the class's instruments by trailing
momentum, hold long top-k (/ short bottom-k) for H bars, non-overlapping rebalances, no-lookahead,
net of cost. Appends one phase-6 row per config to HYPOTHESIS_REGISTRY.csv. Classes with <3
instruments (metals, oil on free data) auto-skip as THIN. Judge with robustness.py --phase 6.

Usage:  python research/jobs/xs_sweep.py --lake <dir> [--max 80] [--rc_iters 8]
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
import xsectional as X   # noqa: E402

TFS = ["15min", "1h", "4h", "1day"]
LH = [(12, 3), (24, 5), (48, 10), (96, 20)]
KS = [1, 2]
MODES = ["ls", "lo"]
ACLASSES = ["crypto", "forex_majors", "forex_crosses", "metals", "oil"]
REG = ROOT / "HYPOTHESIS_REGISTRY.csv"
PHASE = 6


def params_str(L, H, k, mode) -> str:
    return f"H={H},L={L},k={k},mode={mode}"


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
        print(f"No lake data under {a.lake} — nothing to sweep (run data-refresh first)."); return 0
    classes = ACLASSES if a.aclass == "all" else [c.strip() for c in a.aclass.split(",")]
    done = existing_ids()
    combos = [(cls, tf, L, H, k, mode)
              for cls in classes for tf in TFS for (L, H) in LH for k in KS for mode in MODES]

    n_new = n_skip = 0; verdicts = {"PASS": 0, "FAIL": 0, "THIN": 0}; passes = []
    for cls, tf, L, H, k, mode in combos:
        ps = params_str(L, H, k, mode)
        idv = f"xs_mom|{cls}|{tf}|{ps}|c1.0"
        if idv in done:
            n_skip += 1; continue
        if a.max and n_new >= a.max:
            print(f"hit --max {a.max}; stopping (resumable)"); break
        try:
            r = X.evaluate_xs(a.lake, cls, tf, L, H, k=k, mode=mode, rc_iters=a.rc_iters)
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {idv}: {exc}"); continue
        st, sv = r["train"], r["val"]
        append_row(dict(
            id=idv, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=PHASE,
            hypothesis=f"xs_mom({ps})", asset_class=cls, symbols=f"{cls}-ALL",
            timeframe=tf, horizon=f"H{H}", params=ps, entry_rule="xs_mom",
            exit_rule=f"rebalance/{H}bars", cost_model="x1.0",
            sample_train=st["n"], sample_val=sv["n"], winrate_train=st["win"], winrate_val=sv["win"],
            expectancy_R_train=st["expR"], expectancy_R_val=sv["expR"], profit_factor_val=sv["pf"],
            max_dd_R=sv["maxdd_R"], sharpe_val=sv["sharpe"], benchmark_bh_R=r["buyhold_pct"],
            benchmark_random_R=r["random_expR"], survived=r["verdict"]))
        done.add(idv); n_new += 1; verdicts[r["verdict"]] += 1
        if r["verdict"] == "PASS":
            passes.append(f"{idv}  valExpR={sv['expR']} pf={sv['pf']} n={sv['n']}")
        print(f"{r['verdict']:<4} {cls:<13} {tf:<5} {ps:<22} valN={sv['n']} expR={sv['expR']} "
              f"(rnd {r['random_expR']})", flush=True)

    print(f"\n=== xs sweep done: {n_new} new, {n_skip} already-done, {len(combos)} in grid ===")
    print(f"verdicts: {verdicts}")
    if passes:
        print("PASS (validation — NOT candidates; judge with robustness.py --phase 6):")
        for x in passes:
            print("  " + x)
    else:
        print("No validation PASS in this batch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
