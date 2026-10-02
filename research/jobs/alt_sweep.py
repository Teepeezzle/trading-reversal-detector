"""PHASE 8 / Step B — crypto alt-data sweep (funding / basis families).

Grid over families x params(n,z,side) x timeframe x horizon, evaluated with research/src/cryptoalt.py
(enriched perp OHLCV + funding + basis; SL/TP engine; pooled across the crypto universe; net of cost;
benchmarks). Appends phase-8 rows (id suffix |alt) to HYPOTHESIS_REGISTRY.csv. Idempotent + resumable.
Judge with robustness.py --phase 8. Needs the alt lake (research/data/crypto_alt/, built by
cryptoalt_refresh).

Usage:  python research/jobs/alt_sweep.py --lake <dir> [--max 40] [--rc_iters 8]
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
import cryptoalt as A   # noqa: E402

GRID = {
    "fund_rev":  [{"n": 48, "z": 1.5, "side": s} for s in ("long", "short")]
               + [{"n": 48, "z": 2.0, "side": s} for s in ("long", "short")],
    "fund_mom":  [{"side": s} for s in ("long", "short")],
    "basis_rev": [{"n": 48, "z": 1.5, "side": s} for s in ("long", "short")]
               + [{"n": 48, "z": 2.0, "side": s} for s in ("long", "short")],
}
HORIZONS = ["swing", "intraday"]
TFS = ["1h", "4h", "1day"]
REG = ROOT / "HYPOTHESIS_REGISTRY.csv"
PHASE = 8


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
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--rc_iters", type=int, default=8)
    a = ap.parse_args()

    if not any((Path(a.lake) / A.SUBDIR).glob("*.csv.gz")):
        print(f"No alt lake under {Path(a.lake) / A.SUBDIR} — run cryptoalt_refresh first."); return 0
    done = existing_ids()
    combos = [(rule, p, hz, tf) for rule, plist in GRID.items() for p in plist
              for hz in HORIZONS for tf in TFS]

    n_new = n_skip = 0; verdicts = {"PASS": 0, "FAIL": 0, "THIN": 0}; passes = []
    for rule, p, hz, tf in combos:
        idv = f"{rule}|crypto|{tf}|{hz}|{pstr(p)}|alt"
        if idv in done:
            n_skip += 1; continue
        if a.max and n_new >= a.max:
            print(f"hit --max {a.max}; stopping (resumable)"); break
        try:
            r = A.evaluate_alt(a.lake, rule, p, hz, tf, rc_iters=a.rc_iters)
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {idv}: {exc}"); continue
        st, sv = r["train"], r["val"]
        append_row(dict(
            id=idv, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=PHASE,
            hypothesis=f"{rule}({pstr(p)})", asset_class="crypto", symbols="crypto-ALL",
            timeframe=tf, horizon=hz, params=pstr(p), entry_rule=rule,
            exit_rule=f"SL1.5/TP3.0/{hz}", cost_model="x1.0-alt",
            sample_train=st["n"], sample_val=sv["n"], winrate_train=st["win"], winrate_val=sv["win"],
            expectancy_R_train=st["expR"], expectancy_R_val=sv["expR"], profit_factor_val=sv["pf"],
            max_dd_R=sv["maxdd_R"], sharpe_val=sv["sharpe"], benchmark_bh_R=r["buyhold_pct"],
            benchmark_random_R=r["random_expR"], survived=r["verdict"]))
        done.add(idv); n_new += 1; verdicts[r["verdict"]] += 1
        if r["verdict"] == "PASS":
            passes.append(f"{idv}  valExpR={sv['expR']} pf={sv['pf']} n={sv['n']}")
        print(f"{r['verdict']:<4} crypto {tf:<5} {hz:<8} {rule}({pstr(p)}) "
              f"valN={sv['n']} expR={sv['expR']} (rnd {r['random_expR']})", flush=True)

    print(f"\n=== alt sweep done: {n_new} new, {n_skip} already-done, {len(combos)} in grid ===")
    print(f"verdicts: {verdicts}")
    if passes:
        print("PASS (validation — judge with robustness.py --phase 8):")
        for x in passes:
            print("  " + x)
    else:
        print("No validation PASS in this batch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
