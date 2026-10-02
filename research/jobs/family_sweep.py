"""PHASE 5 — NEW factor-family sweep (idempotent, resumable).

The breakout/mean-reversion lines (Phases 3-4.5) produced 0 robust edges. This opens a fresh search
over factor families we have NOT tested — momentum ignition (ROC), volatility breakout (Bollinger),
trend-pullback (EMA), stochastic reversal, MACD momentum — across six timeframes 15m/1h/2h/3h/4h/1D
(2h and 3h are resampled from 1h in factors.load). Same engine: pooled per asset class, no-lookahead,
net-of-cost, benchmarks, 60/20/20. Appends phase-5 rows to HYPOTHESIS_REGISTRY.csv.

Idempotent (skips ids already present) and resumable (--max N per run — the grid is large, ~540).
These are their OWN multiple-testing family: judge with `robustness.py --phase 5`.

NOTE on breadth: 2h/3h are resampled from 1h and are highly correlated with it, and six TFs multiply
the trial count — both make the multiple-testing bar harder, by design. A lead here must be strong
AND survive a broad cross-section, exactly as the retired breakout lead failed to.

Usage:  python research/jobs/family_sweep.py --lake <dir> [--max 80] [--rc_iters 8]
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
    "roc_mom":      [{"n": 10, "thr": 0.0}, {"n": 20, "thr": 0.0}],
    "bb_breakout":  [{"n": 20, "kstd": 2.0}, {"n": 20, "kstd": 2.5}],
    "ema_pullback": [{"f": 10, "s": 50}, {"f": 20, "s": 100}],
    "stoch_rev":    [{"klen": 14, "d": 3, "os": 20}, {"klen": 21, "d": 3, "os": 20}],
    "macd_mom":     [{"fast": 12, "slow": 26, "signal": 9}],
}
HORIZONS = ["swing", "intraday"]
TFS = ["15min", "1h", "2h", "3h", "4h", "1day"]
ACLASSES = ["forex_majors", "forex_crosses", "metals", "oil", "crypto"]
REG = ROOT / "HYPOTHESIS_REGISTRY.csv"
PHASE = 5


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
    ap.add_argument("--rc_iters", type=int, default=8)
    a = ap.parse_args()

    if not any(Path(a.lake).rglob("*.csv.gz")):
        print(f"No lake data under {a.lake} — nothing to sweep (run data-refresh first)."); return 0
    classes = ACLASSES if a.aclass == "all" else [c.strip() for c in a.aclass.split(",")]
    done = existing_ids()
    combos = [(cls, rule, p, hz, tf)
              for cls in classes
              for rule, plist in GRID_RULES.items()
              for p in plist for hz in HORIZONS for tf in TFS]

    n_new = n_skip = 0; verdicts = {"PASS": 0, "FAIL": 0, "THIN": 0}; passes = []
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
            id=idv, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=PHASE,
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
        print(f"{r['verdict']:<4} {cls:<13} {tf:<5} {hz:<8} {rule}({pstr(p)}) "
              f"valN={sv['n']} expR={sv['expR']} (rnd {r['random_expR']})", flush=True)

    print(f"\n=== family sweep done: {n_new} new, {n_skip} already-done, {len(combos)} in grid ===")
    print(f"verdicts: {verdicts}")
    if passes:
        print("PASS (validation — NOT candidates; judge with robustness.py --phase 5):")
        for x in passes:
            print("  " + x)
    else:
        print("No validation PASS in this batch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
