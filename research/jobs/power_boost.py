"""PHASE 4.5 — power-boost confirmation of the regime-gated breakout lead.

Phase 4 found a real but power-limited edge: crypto donch_brk(20) gated on a regime (vol_hi / ny /
adx_hi25), swing — Sharpe ~0.18, DSR ~0.66, ~120 validation trades. It failed the gauntlet on
statistical POWER, not direction. The fix is more trades PER hypothesis (bigger n shrinks the
p-value at the same Sharpe), NOT more hypotheses (that only raises the bar).

This is a PRE-REGISTERED confirmation of ONE idea under data configs that add trades:
  - cross-asset-class pooling (Move 1): pool crypto + FX + metals + oil into one sample.
  - faster timeframe (Move 2): 15m has ~4x the bars of 1h -> more breakout signals.
Each instrument keeps its own asset-class cost (net-R is comparable across the pool).

Deflation benchmark is FIXED at the Phase-4 expected-max-Sharpe (SR*=0.17) — we ask whether the
expanded-data version beats the benchmark the original search already had to beat, rather than
re-deriving a benchmark from these highly-correlated configs (which would violate DSR independence).
Bonferroni N = the confirmation cells actually tested (n>=100). Validation set only; holdout sealed.

Usage:  python research/jobs/power_boost.py --lake <dir>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import factors as F        # noqa: E402
import backtest as bt      # noqa: E402
import costs as cost_model  # noqa: E402
import mtc                  # noqa: E402

REPORT = ROOT / "POWER_BOOST.md"
SL, TP = 1.5, 3.0
MIN = F.MIN_TRADES
SR_STAR = 0.17                       # Phase-4 expected-max-Sharpe benchmark (fixed deflation bar)
ALL = ["crypto", "forex_majors", "forex_crosses", "metals", "oil"]

LEAD = dict(rule="donch_brk", params={"n": 20}, horizon="swing")
GATES_TEST = ["vol_hi", "ny", "adx_hi25"]
CONFIGS = {                          # name -> (classes, timeframe)
    "crypto@1h (phase-4 baseline)": (["crypto"], "1h"),
    "crypto@15m (Move2)":           (["crypto"], "15min"),
    "crypto@4h":                    (["crypto"], "4h"),
    "allclass@1h (Move1)":          (ALL, "1h"),
    "allclass@15m (Move1+2)":       (ALL, "15min"),
}


def pool(lake, classes, tf, params, horizon, gate, cost_mult) -> pd.DataFrame:
    rule_fn = F.RULES[LEAD["rule"]]; gate_fn = F.GATES[gate]
    frames = []
    for cls in classes:
        c = cost_model.get(cls, cost_mult)
        for sym in F.get_symbols(cls):
            try:
                df = F.load(lake, cls, sym, tf)
            except Exception:
                continue
            tr, _, _ = F.run_one(df, rule_fn, params, horizon, SL, TP, c, gate_fn)
            if not tr.empty:
                frames.append(tr[tr.split == "val"])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame({"net_R": []})


def fmt(x, nd=4):
    try:
        if x is None or (isinstance(x, float) and not np.isfinite(x)):
            return "n/a"
        return f"{float(x):.{nd}f}"
    except Exception:
        return str(x)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--dsr", type=float, default=0.95)
    a = ap.parse_args()
    if not any(Path(a.lake).rglob("*.csv.gz")):
        print(f"No lake under {a.lake}."); return 0

    cells = []
    for gate in GATES_TEST:
        for cfg, (classes, tf) in CONFIGS.items():
            v1 = pool(a.lake, classes, tf, LEAD["params"], LEAD["horizon"], gate, 1.0)
            s1 = bt.stats(v1)
            if s1["n"] < MIN:
                cells.append(dict(gate=gate, cfg=cfg, n=s1["n"], thin=True)); continue
            v2 = pool(a.lake, classes, tf, LEAD["params"], LEAD["horizon"], gate, 2.0)
            s2 = bt.stats(v2)
            R = v1["net_R"].astype(float)
            skew = float(R.skew()) if len(R) > 2 else 0.0
            kurt = (float(R.kurt()) + 3.0) if len(R) > 3 else 3.0
            p = mtc.p_value_one_sided(s1["sharpe"], s1["n"])
            dsr = mtc.deflated_sharpe(s1["sharpe"], SR_STAR, s1["n"], skew, kurt)
            cells.append(dict(gate=gate, cfg=cfg, n=s1["n"], thin=False, expR=s1["expR"],
                              pf=s1["pf"], sharpe=s1["sharpe"], exp2=s2["expR"], pf2=s2["pf"],
                              p=p, dsr=dsr))

    valid = [c for c in cells if not c["thin"]]
    N = len(valid)
    bonf = a.alpha / max(N, 1)
    for c in valid:
        c["cost2_ok"] = bool(c["exp2"] > 0 and np.isfinite(c["pf2"]) and c["pf2"] > 1)
        c["bonf_ok"] = bool(np.isfinite(c["p"]) and c["p"] < bonf)
        c["dsr_ok"] = bool(np.isfinite(c["dsr"]) and c["dsr"] > a.dsr)
        c["survive"] = c["cost2_ok"] and c["bonf_ok"] and c["dsr_ok"]

    lines = [
        "# POWER-BOOST confirmation — regime-gated breakout (Phase 4.5)",
        "",
        f"Pre-registered test of **{LEAD['rule']}({','.join(f'{k}={v}' for k,v in LEAD['params'].items())})"
        f" & {{gate}}**, long, {LEAD['horizon']}, under data configs that add trades per hypothesis.",
        "",
        f"- Confirmation cells with n>=100 (Bonferroni N): **{N}**  -> p < {bonf:.4g}",
        f"- DSR deflation benchmark (fixed at Phase-4 expected-max-Sharpe): SR* = **{SR_STAR}** · DSR>{a.dsr}",
        "- Validation set only; holdout sealed. Each instrument carries its own asset-class cost.",
        "",
        "| gate | config | n | expR | PF | Sharpe | 2x expR | p | DSR | verdict |",
        "|---|---|--:|--:|--:|--:|--:|--:|--:|:--|",
    ]
    for c in cells:
        if c["thin"]:
            lines.append(f"| {c['gate']} | {c['cfg']} | {c['n']} | — | — | — | — | — | — | THIN (n<100) |")
        else:
            v = ("**SURVIVES**" if c["survive"] else
                 "reject: " + ", ".join(x for x, ok in
                 [("2xcost", c["cost2_ok"]), ("bonf", c["bonf_ok"]), ("dsr", c["dsr_ok"])] if not ok)
                 .replace("2xcost", "cost").replace("bonf", "p").replace("dsr", "DSR"))
            lines.append(f"| {c['gate']} | {c['cfg']} | {c['n']} | {fmt(c['expR'])} | {fmt(c['pf'],2)} | "
                         f"{fmt(c['sharpe'],3)} | {fmt(c['exp2'])} | {fmt(c['p'],5)} | {fmt(c['dsr'],3)} | {v} |")

    survivors = [c for c in valid if c["survive"]]
    lines += ["", "## Verdict", ""]
    if survivors:
        lines.append(f"**{len(survivors)} config(s) cleared the full bar** — promote via T-303/Phase 5:")
        for c in survivors:
            lines.append(f"- {c['gate']} · {c['cfg']}: n={c['n']} Sharpe={fmt(c['sharpe'],3)} "
                         f"p={fmt(c['p'],5)} DSR={fmt(c['dsr'],3)}")
    else:
        best = max(valid, key=lambda c: (c["dsr"] if np.isfinite(c["dsr"]) else -1)) if valid else None
        lines.append("**0 configs cleared the bar.** More data (Moves 1–2) alone was not enough.")
        if best:
            lines.append(f"- Best: {best['gate']} · {best['cfg']} — n={best['n']}, Sharpe={fmt(best['sharpe'],3)}, "
                         f"p={fmt(best['p'],5)} (need <{bonf:.4g}), DSR={fmt(best['dsr'],3)} (need >{a.dsr}).")
        lines.append("- Next lever: widen the crypto alt universe (Move 3, needs a CI data-refresh) "
                     "or proceed to Phase-5 walk-forward on the best-powered config.")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n-> {REPORT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
