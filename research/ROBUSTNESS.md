# ROBUSTNESS (T-303) — multiple-testing correction + stress tests

_Generated 2026-10-04 06:59 UTC from `HYPOTHESIS_REGISTRY.csv`._

A base-gate PASS is only a lead. A **candidate** must additionally survive 2x cost, parameter sensitivity, and BOTH multiple-testing corrections below. Validation set only; holdout untouched.

## Selection context
- Valid tests (N, n>=100 — used for Bonferroni & the DSR benchmark): **37**  (configs attempted incl. THIN sub-100-trade: 96)
- Base-gate PASSes entering the gauntlet: **12**
- Family-wise alpha: 0.05 -> **Bonferroni per-hypothesis p < 0.00135**
- Trial-Sharpe variance: 0.0083 -> expected-max-Sharpe benchmark SR* = **0.1972** (per-trade)
- Deflated Sharpe Ratio threshold: **DSR > 0.95**

## Per-candidate gauntlet

### `sent_mom|forex_crosses|1day|swing|side=long,z=0.25|n10`
- Rule: `sent_mom(side=long,z=0.25)` · forex_crosses · 1day · swing
- Val @1x: n=124 expR=0.1406 pf=1.43 sharpe=0.148
- 2x cost: n=124 expR=0.0708 pf=1.20 -> OK
- Sensitivity: 2/2 neighbors scored, 100% positive, median expR=0.0887 -> OK
- Bonferroni: p=0.04967 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.289 (skew=0.32, kurt=2.09) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|forex_crosses|1day|intraday|side=long,z=0.25|n10`
- Rule: `sent_mom(side=long,z=0.25)` · forex_crosses · 1day · intraday
- Val @1x: n=223 expR=0.0165 pf=1.10 sharpe=0.037
- 2x cost: n=223 expR=-0.0076 pf=0.96 -> FAIL
- Sensitivity: 2/2 neighbors scored, 50% positive, median expR=0.0185 -> FAIL
- Bonferroni: p=0.29029 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.008 (skew=0.91, kurt=5.29) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|forex_crosses|1day|swing|side=long,z=0.5|n10`
- Rule: `sent_mom(side=long,z=0.5)` · forex_crosses · 1day · swing
- Val @1x: n=122 expR=0.1120 pf=1.37 sharpe=0.125
- 2x cost: n=122 expR=0.0428 pf=1.13 -> OK
- Sensitivity: 2/3 neighbors scored, 100% positive, median expR=0.1031 -> OK
- Bonferroni: p=0.08369 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.210 (skew=0.30, kurt=2.33) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|forex_crosses|1day|intraday|side=long,z=0.5|n10`
- Rule: `sent_mom(side=long,z=0.5)` · forex_crosses · 1day · intraday
- Val @1x: n=202 expR=0.0452 pf=1.30 sharpe=0.096
- 2x cost: n=202 expR=0.0209 pf=1.13 -> OK
- Sensitivity: 2/3 neighbors scored, 50% positive, median expR=0.0042 -> FAIL
- Bonferroni: p=0.08622 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.069 (skew=0.75, kurt=5.09) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|forex_crosses|1day|intraday|side=short,z=0.5|n10`
- Rule: `sent_mom(side=short,z=0.5)` · forex_crosses · 1day · intraday
- Val @1x: n=175 expR=0.0045 pf=1.03 sharpe=0.012
- 2x cost: n=175 expR=-0.0198 pf=0.88 -> FAIL
- Sensitivity: 2/3 neighbors scored, 0% positive, median expR=-0.0246 -> FAIL
- Bonferroni: p=0.43693 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.007 (skew=-0.02, kurt=2.97) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_rev|crypto|1day|intraday|side=short,z=1.0|n10`
- Rule: `sent_rev(side=short,z=1.0)` · crypto · 1day · intraday
- Val @1x: n=683 expR=0.0231 pf=1.15 sharpe=0.048
- 2x cost: n=683 expR=0.0059 pf=1.04 -> OK
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=-0.0067 -> FAIL
- Bonferroni: p=0.10484 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.65, kurt=5.58) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_rev|crypto|1day|swing|side=short,z=1.5|n10`
- Rule: `sent_rev(side=short,z=1.5)` · crypto · 1day · swing
- Val @1x: n=285 expR=-0.1498 pf=0.69 sharpe=-0.153
- 2x cost: n=285 expR=-0.1809 pf=0.64 -> FAIL
- Sensitivity: 3/4 neighbors scored, 33% positive, median expR=-0.0834 -> FAIL
- Bonferroni: p=0.99510 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.99, kurt=2.87) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_rev|crypto|1day|intraday|side=short,z=1.5|n10`
- Rule: `sent_rev(side=short,z=1.5)` · crypto · 1day · intraday
- Val @1x: n=330 expR=0.0039 pf=1.02 sharpe=0.008
- 2x cost: n=330 expR=-0.0120 pf=0.93 -> FAIL
- Sensitivity: 3/4 neighbors scored, 67% positive, median expR=0.0231 -> OK
- Bonferroni: p=0.44223 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.82, kurt=6.35) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|1day|swing|side=long,z=0.25|n10`
- Rule: `sent_mom(side=long,z=0.25)` · crypto · 1day · swing
- Val @1x: n=862 expR=0.0196 pf=1.05 sharpe=0.020
- 2x cost: n=862 expR=-0.0154 pf=0.96 -> FAIL
- Sensitivity: 2/2 neighbors scored, 50% positive, median expR=-0.0035 -> FAIL
- Bonferroni: p=0.27854 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.68, kurt=2.37) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|1day|swing|side=long,z=0.5|n10`
- Rule: `sent_mom(side=long,z=0.5)` · crypto · 1day · swing
- Val @1x: n=749 expR=-0.0157 pf=0.96 sharpe=-0.016
- 2x cost: n=749 expR=-0.0504 pf=0.89 -> FAIL
- Sensitivity: 3/3 neighbors scored, 100% positive, median expR=0.0196 -> OK
- Bonferroni: p=0.66927 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.66, kurt=2.35) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|1day|swing|side=long,z=1.0|n10`
- Rule: `sent_mom(side=long,z=1.0)` · crypto · 1day · swing
- Val @1x: n=528 expR=0.0660 pf=1.18 sharpe=0.069
- 2x cost: n=528 expR=0.0325 pf=1.09 -> OK
- Sensitivity: 4/4 neighbors scored, 75% positive, median expR=0.0561 -> OK
- Bonferroni: p=0.05643 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=0.48, kurt=2.33) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|1day|swing|side=short,z=0.5|n10`
- Rule: `sent_mom(side=short,z=0.5)` · crypto · 1day · swing
- Val @1x: n=737 expR=0.0446 pf=1.11 sharpe=0.044
- 2x cost: n=737 expR=0.0103 pf=1.02 -> OK
- Sensitivity: 3/3 neighbors scored, 33% positive, median expR=-0.0191 -> FAIL
- Bonferroni: p=0.11614 vs 0.00135 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.52, kurt=2.11) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

## Summary

- 12 base-gate PASS -> **0 candidate(s)** after the full gauntlet.
- Nothing survived. No candidate is promoted — correct, disciplined outcome.
