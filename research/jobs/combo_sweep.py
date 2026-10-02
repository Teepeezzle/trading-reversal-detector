"""PHASE 4 / T-401 — combination sweep: Phase-3 LEADS x regime gates (idempotent, resumable).

Phase 3 left 0 standalone candidates — only leads (single factors that survived 2x cost +
parameter sensitivity but not the multiple-testing bar). Phase 4 asks: does a confirming regime
gate concentrate a lead's edge enough to clear the gauntlet?

For every phase-3 base-gate PASS already in HYPOTHESIS_REGISTRY.csv (read dynamically — no
cherry-picking), this crosses it with each gate in factors.GATES and evaluates the combined rule
(base & gate) pooled, no-lookahead, net-of-cost, with benchmarks. Appends one phase-4 row per
(lead x gate). Idempotent (skips ids already present) and resumable (--max N per run).

The combined hypothesis is identified by entry_rule = "<rule>+<gate>"; `params` stays the base
rule's numeric params so T-303's parameter-sensitivity sweep still perturbs them correctly.

Usage:
  python research/jobs/combo_sweep.py --lake <dir> [--max 60] [--rc_iters 8]
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

REG = ROOT / "HYPOTHESIS_REGISTRY.csv"


def pstr(p: dict) -> str:
    return ",".join(f"{k}={p[k]}" for k in sorted(p))


def parse_params(s: str) -> dict:
    out: dict = {}
    for part in str(s).split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        try:
            out[k] = int(v)
        except ValueError:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


def read_leads() -> list[dict]:
    """Phase-3 base-gate PASSes = the leads to gate. De-duped on (rule, params, class, tf, hz)."""
    try:
        reg = pd.read_csv(REG)
    except Exception:
        return []
    reg = reg[(reg.get("phase").astype(str) == "3") & (reg.get("survived") == "PASS")]
    leads, seen = [], set()
    for _, r in reg.iterrows():
        rule = str(r["entry_rule"]).split("+", 1)[0].strip()   # defensive: never gate a gated row
        if rule not in F.RULES:
            continue
        p = parse_params(r["params"])
        key = (rule, pstr(p), str(r["asset_class"]), str(r["timeframe"]), str(r["horizon"]))
        if key in seen:
            continue
        seen.add(key)
        leads.append(dict(rule=rule, params=p, aclass=str(r["asset_class"]).strip(),
                          tf=str(r["timeframe"]).strip(), hz=str(r["horizon"]).strip()))
    return leads


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
    ap.add_argument("--max", type=int, default=0, help="max NEW hypotheses this run (0=unlimited)")
    ap.add_argument("--rc_iters", type=int, default=8)
    a = ap.parse_args()

    if not any(Path(a.lake).rglob("*.csv.gz")):
        print(f"No lake data under {a.lake} — nothing to sweep (run data-refresh first)."); return 0
    leads = read_leads()
    if not leads:
        print("No phase-3 base-gate PASS leads in the registry — run the Phase-3 sweep first."); return 0

    done = existing_ids()
    combos = [(ld, gate) for ld in leads for gate in F.GATES]
    print(f"{len(leads)} leads x {len(F.GATES)} gates = {len(combos)} phase-4 hypotheses")

    n_new = n_skip = 0; verdicts = {"PASS": 0, "FAIL": 0, "THIN": 0}; passes = []
    for ld, gate in combos:
        rule, p, cls, tf, hz = ld["rule"], ld["params"], ld["aclass"], ld["tf"], ld["hz"]
        idv = f"{rule}+{gate}|{cls}|{tf}|{hz}|{pstr(p)}|c1.0"
        if idv in done:
            n_skip += 1; continue
        if a.max and n_new >= a.max:
            print(f"hit --max {a.max}; stopping (resumable — re-run to continue)"); break
        try:
            r = F.evaluate(a.lake, cls, rule, p, hz, tf, rc_iters=a.rc_iters, gate=gate)
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {idv}: {exc}"); continue
        st, sv = r["train"], r["val"]
        append_row(dict(
            id=idv, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=4,
            hypothesis=f"{rule}({pstr(p)})+{gate}", asset_class=cls, symbols=f"{cls}-ALL",
            timeframe=tf, horizon=hz, params=pstr(p), entry_rule=f"{rule}+{gate}",
            exit_rule=f"SL1.5/TP3.0/{hz}", cost_model="x1.0",
            sample_train=st["n"], sample_val=sv["n"], winrate_train=st["win"], winrate_val=sv["win"],
            expectancy_R_train=st["expR"], expectancy_R_val=sv["expR"], profit_factor_val=sv["pf"],
            max_dd_R=sv["maxdd_R"], sharpe_val=sv["sharpe"], benchmark_bh_R=r["buyhold_pct"],
            benchmark_random_R=r["random_expR"], survived=r["verdict"]))
        done.add(idv); n_new += 1; verdicts[r["verdict"]] += 1
        if r["verdict"] == "PASS":
            passes.append(f"{idv}  valExpR={sv['expR']} pf={sv['pf']} n={sv['n']}")
        print(f"{r['verdict']:<4} {cls:<13} {tf} {hz:<8} {rule}+{gate} ({pstr(p)}) "
              f"valN={sv['n']} expR={sv['expR']} (rnd {r['random_expR']})", flush=True)

    print(f"\n=== combo sweep done: {n_new} new, {n_skip} already-done, {len(combos)} in grid ===")
    print(f"verdicts: {verdicts}")
    if passes:
        print("PASS (validation — NOT candidates; feed to T-303 with --phase 4):")
        for x in passes:
            print("  " + x)
    else:
        print("No validation PASS in this batch — gates did not lift any lead over the base gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
