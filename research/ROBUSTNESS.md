# ROBUSTNESS (T-303) — multiple-testing correction + stress tests

_Generated 2026-10-02 19:18 UTC from `HYPOTHESIS_REGISTRY.csv`._

A base-gate PASS is only a lead. A **candidate** must additionally survive 2x cost, parameter sensitivity, and BOTH multiple-testing corrections below. Validation set only; holdout untouched.

## Selection context
- Valid tests (N, n>=100 — used for Bonferroni & the DSR benchmark): **26**  (configs attempted incl. THIN sub-100-trade: 36)
- Base-gate PASSes entering the gauntlet: **2**
- Family-wise alpha: 0.05 -> **Bonferroni per-hypothesis p < 0.00192**
- Trial-Sharpe variance: 0.0107 -> expected-max-Sharpe benchmark SR* = **0.2083** (per-trade)
- Deflated Sharpe Ratio threshold: **DSR > 0.95**

## Per-candidate gauntlet

### `fund_rev|crypto|4h|swing|n=48,side=short,z=1.5|alt`
- Rule: `fund_rev(n=48,side=short,z=1.5)` · crypto · 4h · swing
- Val @1x: n=139 expR=0.0163 pf=1.03 sharpe=0.012
- 2x cost: n=139 expR=-0.0475 pf=0.93 -> FAIL
- Sensitivity: 6/8 neighbors scored, 50% positive, median expR=0.0122 -> FAIL
- Bonferroni: p=0.44375 vs 0.00192 -> FAIL
- Deflated Sharpe: DSR=0.010 (skew=0.59, kurt=1.42) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `fund_rev|crypto|4h|intraday|n=48,side=short,z=1.5|alt`
- Rule: `fund_rev(n=48,side=short,z=1.5)` · crypto · 4h · intraday
- Val @1x: n=184 expR=0.1068 pf=1.42 sharpe=0.134
- 2x cost: n=184 expR=0.0605 pf=1.22 -> OK
- Sensitivity: 6/8 neighbors scored, 100% positive, median expR=0.1114 -> OK
- Bonferroni: p=0.03456 vs 0.00192 -> FAIL
- Deflated Sharpe: DSR=0.149 (skew=0.57, kurt=3.16) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

## Summary

- 2 base-gate PASS -> **0 candidate(s)** after the full gauntlet.
- Nothing survived. No candidate is promoted — correct, disciplined outcome.
