"""PHASE 3 — single-factor tester (CLI over research/src/factors.evaluate).

Tests ONE rule on ONE asset class / timeframe / horizon, POOLED across the class's instruments
(D-011), no-lookahead and net-of-cost. Reports TRAIN + VALIDATION stats and the buy-&-hold +
random-entry benchmarks. Judged PASS only on validation (>=100 trades, expR>0, PF>1, beats random).
The HOLDOUT (last 20%) is never touched here.

Usage:
  python research/jobs/single_factor.py --lake <dir> --aclass crypto --rule rsi_rev \
      --horizon swing --tf 1h --p "n=14,os=30" [--record]
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


def parse_params(s: str) -> dict:
    out = {}
    for kv in (s or "").split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            try:
                out[k.strip()] = int(v) if v.strip().lstrip("-").isdigit() else float(v)
            except ValueError:
                out[k.strip()] = v.strip()
    return out


def record_row(reg: Path, d: dict):
    hdr = pd.read_csv(reg, nrows=0).columns.tolist()
    pd.DataFrame([{k: d.get(k, "") for k in hdr}]).to_csv(reg, mode="a", header=False, index=False)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--aclass", required=True)
    ap.add_argument("--rule", required=True, choices=list(F.RULES))
    ap.add_argument("--horizon", default="swing", choices=["intraday", "swing"])
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--sl", type=float, default=1.5)
    ap.add_argument("--tp", type=float, default=3.0)
    ap.add_argument("--p", default="")
    ap.add_argument("--cost_mult", type=float, default=1.0)
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args()

    params = parse_params(a.p)
    r = F.evaluate(a.lake, a.aclass, a.rule, params, a.horizon, a.tf, a.sl, a.tp, a.cost_mult)
    st, sv = r["train"], r["val"]
    print(f"\n{a.aclass}-ALL({r['n_syms']}) {a.tf} {a.horizon} · {a.rule}({a.p}) "
          f"SL{a.sl}/TP{a.tp} costx{a.cost_mult}")
    print(f"  TRAIN n={st['n']:<4} win={st['win']}% expR={st['expR']} pf={st['pf']} dd={st['maxdd_R']}R")
    print(f"  VAL   n={sv['n']:<4} win={sv['win']}% expR={sv['expR']} pf={sv['pf']} "
          f"sharpe={sv['sharpe']} dd={sv['maxdd_R']}R")
    print(f"  bench random expR={r['random_expR']} · buy-hold {r['buyhold_pct']}%")
    print(f"  => {r['verdict']}  (judged on validation; holdout untouched)")

    if a.record:
        record_row(ROOT / "HYPOTHESIS_REGISTRY.csv", dict(
            id=f"{a.rule}|{a.aclass}|{a.tf}|{a.horizon}|{a.p}|c{a.cost_mult}",
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=3,
            hypothesis=f"{a.rule}({a.p})", asset_class=a.aclass, symbols=f"{a.aclass}-ALL",
            timeframe=a.tf, horizon=a.horizon, params=a.p, entry_rule=a.rule,
            exit_rule=f"SL{a.sl}/TP{a.tp}/{a.horizon}", cost_model=f"x{a.cost_mult}",
            sample_train=st["n"], sample_val=sv["n"], winrate_train=st["win"], winrate_val=sv["win"],
            expectancy_R_train=st["expR"], expectancy_R_val=sv["expR"], profit_factor_val=sv["pf"],
            max_dd_R=sv["maxdd_R"], sharpe_val=sv["sharpe"], benchmark_bh_R=r["buyhold_pct"],
            benchmark_random_R=r["random_expR"], survived=r["verdict"]))
        print("  recorded -> HYPOTHESIS_REGISTRY.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
