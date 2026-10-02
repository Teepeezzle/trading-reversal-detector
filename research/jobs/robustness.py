"""PHASE 3 / T-303 — robustness gauntlet + multiple-testing correction on the sweep registry.

A hypothesis that merely PASSed the base validation gate (>=100 trades, positive net expectancy,
beat random) is NOT yet a candidate. This job subjects every base-gate PASS to three further,
independent tests and promotes only what survives ALL of them:

  1. 2x transaction cost (T-901)  — re-run on validation at double cost; still n>=100, expR>0, pf>1?
  2. Parameter sensitivity (T-902) — perturb each numeric param +/-1..2; is the edge a plateau, not a spike?
  3. Multiple-testing correction (T-903):
        - Bonferroni: one-sided p-value < alpha / N, where N = number of hypotheses actually tested.
        - Deflated Sharpe Ratio (Bailey & Lopez de Prado): DSR > threshold, deflating for N trials
          and for skew / fat tails.

Judged on the VALIDATION set only; the holdout is never touched here. Reads the data lake (built by
research-data-refresh) and HYPOTHESIS_REGISTRY.csv (populated by the sweep). Writes a full report to
research/ROBUSTNESS.md always; with --promote, writes survivors into research/CANDIDATES.md. Honest
by construction: if nothing survives (the expected early result), it says so and promotes nothing.

Usage:
  python research/jobs/robustness.py --lake <dir> [--alpha 0.05] [--dsr 0.95] [--promote]
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
import factors as F        # noqa: E402  (shares rule builders + load/run_one with the sweep)
import backtest as bt      # noqa: E402
import costs as cost_model  # noqa: E402
import mtc                  # noqa: E402
import xsectional as X      # noqa: E402  (phase-6 cross-sectional re-evaluation)

REG = ROOT / "HYPOTHESIS_REGISTRY.csv"
CAND = ROOT / "CANDIDATES.md"
REPORT = ROOT / "ROBUSTNESS.md"
BLOCKERS = ROOT / "BLOCKERS.md"
SL, TP = 1.5, 3.0
MIN_TRADES = F.MIN_TRADES

# per-param perturbation steps for the sensitivity sweep (+/- each step, one param at a time)
STEP = {"n": [1, 2], "f": [1, 2], "s": [2, 5], "len": [1, 2], "os": [5, 10], "z": [0.25, 0.5],
        "kstd": [0.25, 0.5], "klen": [2, 4], "d": [1, 2], "fast": [2, 4], "slow": [4, 8]}


# ----------------------------- helpers -----------------------------
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


def pstr(p: dict) -> str:
    return ",".join(f"{k}={p[k]}" for k in sorted(p))


def pooled_val(lake, aclass, rule, params, horizon, tf, cost_mult, gate=None) -> pd.DataFrame:
    """Rebuild the pooled VALIDATION trades for one hypothesis (reusing the sweep's own rule/engine)."""
    rule_fn = F.RULES[rule]
    gate_fn = F.GATES[gate] if gate else None
    c = cost_model.get(aclass, cost_mult)
    frames = []
    for sym in F.get_symbols(aclass):
        try:
            df = F.load(lake, aclass, sym, tf)
        except Exception:
            continue
        trades_i, _, _ = F.run_one(df, rule_fn, params, horizon, SL, TP, c, gate_fn)
        if not trades_i.empty:
            frames.append(trades_i)
    if not frames:
        return pd.DataFrame({"split": [], "net_R": []})
    t = pd.concat(frames, ignore_index=True)
    return t[t.split == "val"] if "split" in t else pd.DataFrame({"split": [], "net_R": []})


def xs_neighbors(p: dict) -> list[dict]:
    """Parameter perturbations for a cross-sectional config: vary lookback L and hold H."""
    L = int(p["L"]); H = int(p["H"]); out = []
    for Ln in {max(2, L // 2), L * 2}:
        if Ln != L:
            q = dict(p); q["L"] = Ln; out.append(q)
    for Hn in {max(2, H - 2), H + 5}:
        if Hn != H:
            q = dict(p); q["H"] = Hn; out.append(q)
    return out


def xs_val(lake, aclass, tf, p: dict, cost_mult) -> pd.DataFrame:
    return X.val_trades(lake, aclass, tf, int(p["L"]), int(p["H"]),
                        k=int(p.get("k", 2)), mode=str(p.get("mode", "ls")), cost_mult=cost_mult)


def neighbors(params: dict) -> list[dict]:
    """Univariate +/- perturbations of each numeric param (period-/threshold-aware steps)."""
    out = []
    for k, v in params.items():
        if k not in STEP or not isinstance(v, (int, float)):
            continue
        for d in STEP[k]:
            for cand in (v - d, v + d):
                if cand <= 0:
                    continue
                if k == "os" and cand >= 100:
                    continue
                q = dict(params)
                q[k] = int(cand) if isinstance(v, int) else round(float(cand), 4)
                if q != params:
                    out.append(q)
    # de-dupe while preserving order
    seen, uniq = set(), []
    for q in out:
        key = pstr(q)
        if key not in seen:
            seen.add(key); uniq.append(q)
    return uniq


def fmt(x, nd=4):
    try:
        if x is None or (isinstance(x, float) and not np.isfinite(x)):
            return "n/a"
        return f"{float(x):.{nd}f}"
    except Exception:
        return str(x)


# ----------------------------- main -----------------------------
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--registry", default=str(REG))
    ap.add_argument("--alpha", type=float, default=0.05, help="family-wise error rate (Bonferroni)")
    ap.add_argument("--dsr", type=float, default=0.95, help="min Deflated Sharpe Ratio to pass")
    ap.add_argument("--sens_min_frac", type=float, default=0.6,
                    help="min fraction of parameter neighbors that must stay positive")
    ap.add_argument("--phase", default="3", help="trial family to judge: '3', '4', or 'all'")
    ap.add_argument("--promote", action="store_true", help="write survivors into CANDIDATES.md")
    a = ap.parse_args()

    if not any(Path(a.lake).rglob("*.csv.gz")):
        msg = f"T-303: no lake data under {a.lake} — run data-refresh first (nothing to do)."
        print(msg)
        return 0

    try:
        reg = pd.read_csv(a.registry)
    except Exception as exc:  # noqa: BLE001
        print(f"T-303: cannot read registry {a.registry}: {exc}")
        return 0

    # evaluated hypotheses in the selected trial family: a real verdict + a finite validation sample
    reg["sample_val"] = pd.to_numeric(reg.get("sample_val"), errors="coerce")
    reg["sharpe_val"] = pd.to_numeric(reg.get("sharpe_val"), errors="coerce")
    phase_sel = [p.strip() for p in str(a.phase).split(",")]
    in_family = reg.get("phase").astype(str).isin(phase_sel) if a.phase != "all" \
        else reg.get("phase").astype(str).isin(["3", "4"])
    fam = reg[in_family
              & (reg.get("survived").isin(["PASS", "FAIL", "THIN"]))
              & (reg["sample_val"].fillna(0) > 0)].copy()
    n_attempts = len(fam)
    # A THIN config (n < MIN_TRADES) is NOT a valid statistical test — it never cleared the
    # pre-declared sample gate, and its tiny-n Sharpe estimate is noise. Counting such rows in N
    # (Bonferroni) over-corrects, and their Sharpes wildly inflate the DSR deflation benchmark
    # (that is what produced an absurd SR* earlier). So the trial set = valid tests only (n>=MIN).
    tested = fam[fam["sample_val"] >= MIN_TRADES].copy()
    n_trials = len(tested)

    # deflation benchmark: expected max Sharpe across N valid trials, from their Sharpe spread
    trial_sharpes = tested["sharpe_val"].dropna()
    var_trials = float(trial_sharpes.var(ddof=1)) if len(trial_sharpes) > 1 else float("nan")
    sr_star = mtc.expected_max_sharpe(var_trials, n_trials)
    bonf_alpha = mtc.bonferroni_alpha(n_trials, a.alpha)

    passes = tested[tested.survived == "PASS"].copy()

    header = [
        "# ROBUSTNESS (T-303) — multiple-testing correction + stress tests",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from "
        f"`{Path(a.registry).name}`._",
        "",
        "A base-gate PASS is only a lead. A **candidate** must additionally survive 2x cost, "
        "parameter sensitivity, and BOTH multiple-testing corrections below. Validation set only; "
        "holdout untouched.",
        "",
        "## Selection context",
        f"- Valid tests (N, n>=100 — used for Bonferroni & the DSR benchmark): **{n_trials}**  "
        f"(configs attempted incl. THIN sub-100-trade: {n_attempts})",
        f"- Base-gate PASSes entering the gauntlet: **{len(passes)}**",
        f"- Family-wise alpha: {a.alpha} -> **Bonferroni per-hypothesis p < {bonf_alpha:.3g}**",
        f"- Trial-Sharpe variance: {fmt(var_trials)} -> expected-max-Sharpe benchmark SR* = "
        f"**{fmt(sr_star)}** (per-trade)",
        f"- Deflated Sharpe Ratio threshold: **DSR > {a.dsr}**",
        "",
    ]
    lines = list(header)
    survivors = []

    if n_trials == 0:
        lines += ["## Result", "",
                  "No evaluated hypotheses in the registry yet — run the sweep first, then re-run T-303."]
    elif passes.empty:
        lines += ["## Result", "",
                  "**0 base-gate PASSes.** Nothing to promote. This is the honest, expected early "
                  "result for naive single factors net of cost — the engine refused to bless noise."]
    else:
        lines += ["## Per-candidate gauntlet", ""]
        for _, row in passes.iterrows():
            rule, _, gate = str(row["entry_rule"]).strip().partition("+")  # "<rule>" or "<rule>+<gate>"
            gate = gate or None
            aclass = str(row["asset_class"]).strip()
            tf = str(row["timeframe"]).strip()
            hz = str(row["horizon"]).strip()
            params = parse_params(row["params"])
            idv = str(row["id"])
            is_xs = (rule == "xs_mom")                     # phase-6 cross-sectional
            label = (f"xs_mom({pstr(params)})" if is_xs
                     else f"{rule}({pstr(params)})" + (f" & {gate}" if gate else ""))
            lines += [f"### `{idv}`", f"- Rule: `{label}` · {aclass} · {tf} · {hz}"]

            if not is_xs and (rule not in F.RULES or (gate and gate not in F.GATES)):
                lines += [f"- SKIPPED: unknown rule/gate `{row['entry_rule']}`.", ""]
                continue

            # re-evaluate the VALIDATION trades — cross-sectional engine for xs rows, else the sweep's
            def val_at(cost_mult, p=params):
                return xs_val(a.lake, aclass, tf, p, cost_mult) if is_xs \
                    else pooled_val(a.lake, aclass, rule, p, hz, tf, cost_mult, gate)

            # (0) baseline 1x re-derivation (sanity + raw R for DSR)
            v1 = val_at(1.0); s1 = bt.stats(v1)
            # (1) 2x cost
            v2 = val_at(2.0); s2 = bt.stats(v2)
            cost2_ok = bool(s2["n"] >= MIN_TRADES and np.isfinite(s2["expR"])
                            and s2["expR"] > 0 and np.isfinite(s2["pf"]) and s2["pf"] > 1)
            # (2) parameter sensitivity (perturb L/H for xs; base params for a rule; gate held fixed)
            nbrs = xs_neighbors(params) if is_xs else neighbors(params)
            nbr_exp = []
            for q in nbrs:
                sv = bt.stats(val_at(1.0, q))
                if sv["n"] >= MIN_TRADES and np.isfinite(sv["expR"]):
                    nbr_exp.append(sv["expR"])
            frac_pos = (float(np.mean([e > 0 for e in nbr_exp])) if nbr_exp else 0.0)
            med_nbr = (float(np.median(nbr_exp)) if nbr_exp else float("nan"))
            # no perturbable params (e.g. all thresholds fixed) -> sensitivity is N/A, don't penalise
            sens_na = (len(nbrs) == 0)
            sens_ok = sens_na or bool(nbr_exp and frac_pos >= a.sens_min_frac and med_nbr > 0)
            # (3) multiple-testing correction on the 1x validation result
            pval = mtc.p_value_one_sided(s1["sharpe"], s1["n"])
            bonf_ok = bool(np.isfinite(pval) and pval < bonf_alpha)
            R = v1["net_R"].astype(float) if len(v1) else pd.Series(dtype=float)
            skew = float(R.skew()) if len(R) > 2 else float("nan")
            kurt_pearson = (float(R.kurt()) + 3.0) if len(R) > 3 else float("nan")  # pandas kurt = excess
            dsr = mtc.deflated_sharpe(s1["sharpe"], sr_star, s1["n"], skew, kurt_pearson)
            dsr_ok = bool(np.isfinite(dsr) and dsr > a.dsr)

            survived = cost2_ok and sens_ok and bonf_ok and dsr_ok
            reasons = []
            if not cost2_ok: reasons.append("dies at 2x cost")
            if not sens_ok: reasons.append("parameter-fragile")
            if not bonf_ok: reasons.append("fails Bonferroni")
            if not dsr_ok: reasons.append("fails Deflated Sharpe")

            lines += [
                f"- Val @1x: n={s1['n']} expR={fmt(s1['expR'])} pf={fmt(s1['pf'],2)} "
                f"sharpe={fmt(s1['sharpe'],3)}",
                f"- 2x cost: n={s2['n']} expR={fmt(s2['expR'])} pf={fmt(s2['pf'],2)} "
                f"-> {'OK' if cost2_ok else 'FAIL'}",
                f"- Sensitivity: {len(nbr_exp)}/{len(nbrs)} neighbors scored, "
                f"{frac_pos*100:.0f}% positive, median expR={fmt(med_nbr)} "
                f"-> {'N/A' if sens_na else ('OK' if sens_ok else 'FAIL')}",
                f"- Bonferroni: p={fmt(pval,5)} vs {bonf_alpha:.3g} -> {'OK' if bonf_ok else 'FAIL'}",
                f"- Deflated Sharpe: DSR={fmt(dsr,3)} (skew={fmt(skew,2)}, kurt={fmt(kurt_pearson,2)}) "
                f"-> {'OK' if dsr_ok else 'FAIL'}",
                f"- **VERDICT: {'SURVIVES -> candidate' if survived else 'REJECT (' + ', '.join(reasons) + ')'}**",
                "",
            ]
            if survived:
                survivors.append(dict(id=idv, rule=rule, gate=gate, params=params, aclass=aclass,
                                      tf=tf, hz=hz, s1=s1, s2=s2, pval=pval, dsr=dsr,
                                      bh=row.get("benchmark_bh_R"), rnd=row.get("benchmark_random_R"),
                                      frac_pos=frac_pos, med_nbr=med_nbr))

        lines += ["## Summary", "",
                  f"- {len(passes)} base-gate PASS -> **{len(survivors)} candidate(s)** after the full gauntlet."]
        if not survivors:
            lines += ["- Nothing survived. No candidate is promoted — correct, disciplined outcome."]

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"T-303: N tested={n_trials}, base PASS={len(passes) if n_trials else 0}, "
          f"survivors={len(survivors)}. Report -> {REPORT.name}")
    for s in survivors:
        print(f"  SURVIVOR {s['id']}: val expR={fmt(s['s1']['expR'])} DSR={fmt(s['dsr'],3)} "
              f"p={fmt(s['pval'],5)}")

    if a.promote:
        _promote(survivors)
    elif survivors:
        print("  (survivors found — re-run with --promote to write them into CANDIDATES.md)")
    return 0


def _promote(survivors: list[dict]):
    """Rewrite CANDIDATES.md: preserve its intro + Template, refresh the promoted list."""
    try:
        txt = CAND.read_text(encoding="utf-8")
    except Exception:
        txt = "# CANDIDATES — surviving strategies\n\n---\n\n### Template\n"
    intro = txt.split("\n---\n", 1)[0].rstrip()
    # drop any stale "_No candidates ..._" placeholder so the body is the single source of truth
    intro = "\n".join(ln for ln in intro.splitlines()
                       if not ln.strip().startswith("_No candidates")).rstrip()
    template = ("### Template" + txt.split("### Template", 1)[1]) if "### Template" in txt else "### Template\n"

    if not survivors:
        body = ("_No candidates yet — nothing has survived the full robustness gauntlet "
                "(2x cost + parameter sensitivity + Bonferroni + Deflated Sharpe)._")
    else:
        blocks = []
        for i, s in enumerate(survivors, 1):
            s1, s2 = s["s1"], s["s2"]
            gate = s.get("gate")
            is_xs = (s["rule"] == "xs_mom")
            name = f"{s['rule']}({pstr(s['params'])})" + (f" & {gate}" if gate and not is_xs else "")
            rule_line = (f"- Rule: cross-sectional momentum, long top-k / short bottom-k, rebalance per "
                         f"`{s['params'].get('H')}` bars; net of turnover + swap"
                         if is_xs else
                         f"- Rule: {s['rule']} entry" + (f", gated on `{gate}`" if gate else "")
                         + f"; stop {SL}xATR; target {TP}xATR; "
                         f"{'session close' if s['hz']=='intraday' else '5-day hard'} invalidation")
            blocks.append("\n".join([
                f"### C-{i:03d} · {name} — {s['aclass']} {s['tf']} {s['hz']}",
                f"- Source hypothesis: `{s['id']}`",
                f"- Universe / timeframe / horizon: {s['aclass']} (pooled) / {s['tf']} / {s['hz']}",
                rule_line,
                f"- Net stats (val): trades {s1['n']}, winrate {fmt(s1['win'],1)}%, "
                f"expectancy {fmt(s1['expR'])}R, PF {fmt(s1['pf'],2)}, maxDD {fmt(s1['maxdd_R'],1)}R, "
                f"Sharpe {fmt(s1['sharpe'],3)}",
                f"- Benchmarks beaten: buy-and-hold {fmt(s['bh'],1)}% / random-entry {fmt(s['rnd'])}R",
                f"- Robustness: 2x cost expR {fmt(s2['expR'])}R (pf {fmt(s2['pf'],2)}) · "
                f"sensitivity {s['frac_pos']*100:.0f}% neighbors positive (median {fmt(s['med_nbr'])}R) · "
                f"Bonferroni p={fmt(s['pval'],5)} · DSR={fmt(s['dsr'],3)}",
                "- Economic rationale (why it should work): _fill in before forward-paper_",
                "- Known weaknesses: selection survived N-trial correction but NOT yet confirmed on the "
                "sealed holdout or in forward paper",
                "- Status: validation (awaiting walk-forward / holdout)",
                "",
            ]))
        body = "\n".join(blocks)

    CAND.write_text(intro + "\n\n" + body + "\n\n---\n\n" + template, encoding="utf-8")
    print(f"T-303: CANDIDATES.md updated ({len(survivors)} promoted).")


if __name__ == "__main__":
    sys.exit(main())
