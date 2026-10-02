# ROBUSTNESS (T-303) — multiple-testing correction + stress tests

_Generated 2026-10-02 06:46 UTC from `HYPOTHESIS_REGISTRY.csv`._

A base-gate PASS is only a lead. A **candidate** must additionally survive 2x cost, parameter sensitivity, and BOTH multiple-testing corrections below. Validation set only; holdout untouched.

## Selection context
- Hypotheses actually tested (N): **220**
- Base-gate PASSes entering the gauntlet: **17**
- Family-wise alpha: 0.05 -> **Bonferroni per-hypothesis p < 0.000227**
- Trial-Sharpe variance: 5.5388 -> expected-max-Sharpe benchmark SR* = **6.5815** (per-trade)
- Deflated Sharpe Ratio threshold: **DSR > 0.95**

## Per-candidate gauntlet

### `donch_brk|forex_majors|4h|swing|n=20|c1.0`
- Rule: `donch_brk(n=20)` · forex_majors · 4h · swing
- Val @1x: n=164 expR=0.1182 pf=1.21 sharpe=0.086
- 2x cost: n=164 expR=0.0444 pf=1.07 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1191 -> OK
- Bonferroni: p=0.13537 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.44, kurt=1.32) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk|forex_majors|4h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20)` · forex_majors · 4h · intraday
- Val @1x: n=259 expR=0.0269 pf=1.09 sharpe=0.032
- 2x cost: n=259 expR=-0.0172 pf=0.95 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0263 -> OK
- Bonferroni: p=0.30328 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.63, kurt=3.00) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk|forex_majors|4h|intraday|n=55|c1.0`
- Rule: `donch_brk(n=55)` · forex_majors · 4h · intraday
- Val @1x: n=152 expR=0.0129 pf=1.04 sharpe=0.016
- 2x cost: n=152 expR=-0.0303 pf=0.91 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0128 -> OK
- Bonferroni: p=0.42181 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.53, kurt=2.91) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `zscore_rev|forex_majors|1h|swing|n=50,z=2.0|c1.0`
- Rule: `zscore_rev(n=50,z=2.0)` · forex_majors · 1h · swing
- Val @1x: n=122 expR=0.1649 pf=1.26 sharpe=0.110
- 2x cost: n=122 expR=0.0265 pf=1.04 -> OK
- Sensitivity: 7/8 neighbors scored, 100% positive, median expR=0.1369 -> OK
- Bonferroni: p=0.11219 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.27, kurt=1.04) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `zscore_rev|forex_majors|1h|intraday|n=50,z=2.0|c1.0`
- Rule: `zscore_rev(n=50,z=2.0)` · forex_majors · 1h · intraday
- Val @1x: n=136 expR=0.0143 pf=1.03 sharpe=0.013
- 2x cost: n=136 expR=-0.1041 pf=0.80 -> FAIL
- Sensitivity: 8/8 neighbors scored, 75% positive, median expR=0.0253 -> OK
- Bonferroni: p=0.43975 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.60, kurt=2.02) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk|metals|1h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20)` · metals · 1h · intraday
- Val @1x: n=121 expR=0.0927 pf=1.20 sharpe=0.078
- 2x cost: n=121 expR=0.0440 pf=1.09 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0862 -> OK
- Bonferroni: p=0.19545 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.41, kurt=1.81) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `rsi_rev|oil|1h|swing|n=7,os=30|c1.0`
- Rule: `rsi_rev(n=7,os=30)` · oil · 1h · swing
- Val @1x: n=122 expR=0.3604 pf=1.66 sharpe=0.242
- 2x cost: n=122 expR=0.2959 pf=1.51 -> OK
- Sensitivity: 5/8 neighbors scored, 100% positive, median expR=0.3128 -> OK
- Bonferroni: p=0.00376 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.10, kurt=1.00) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `rsi_rev|oil|1h|intraday|n=7,os=30|c1.0`
- Rule: `rsi_rev(n=7,os=30)` · oil · 1h · intraday
- Val @1x: n=145 expR=0.1890 pf=1.54 sharpe=0.176
- 2x cost: n=145 expR=0.1394 pf=1.38 -> OK
- Sensitivity: 5/8 neighbors scored, 100% positive, median expR=0.1528 -> OK
- Bonferroni: p=0.01703 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.43, kurt=1.93) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk|oil|1h|intraday|n=55|c1.0`
- Rule: `donch_brk(n=55)` · oil · 1h · intraday
- Val @1x: n=102 expR=0.0038 pf=1.01 sharpe=0.003
- 2x cost: n=102 expR=-0.0422 pf=0.92 -> FAIL
- Sensitivity: 4/4 neighbors scored, 75% positive, median expR=0.0070 -> OK
- Bonferroni: p=0.48791 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.67, kurt=1.84) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `zscore_rev|oil|1h|swing|n=20,z=2.0|c1.0`
- Rule: `zscore_rev(n=20,z=2.0)` · oil · 1h · swing
- Val @1x: n=105 expR=0.2769 pf=1.49 sharpe=0.189
- 2x cost: n=105 expR=0.2131 pf=1.36 -> OK
- Sensitivity: 6/8 neighbors scored, 100% positive, median expR=0.2982 -> OK
- Bonferroni: p=0.02639 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.22, kurt=1.05) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `zscore_rev|oil|1h|intraday|n=20,z=2.0|c1.0`
- Rule: `zscore_rev(n=20,z=2.0)` · oil · 1h · intraday
- Val @1x: n=119 expR=0.0465 pf=1.14 sharpe=0.049
- 2x cost: n=119 expR=-0.0004 pf=1.00 -> FAIL
- Sensitivity: 6/8 neighbors scored, 100% positive, median expR=0.0837 -> OK
- Bonferroni: p=0.29649 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.73, kurt=2.77) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk|crypto|1h|swing|n=20|c1.0`
- Rule: `donch_brk(n=20)` · crypto · 1h · swing
- Val @1x: n=185 expR=0.1245 pf=1.19 sharpe=0.083
- 2x cost: n=185 expR=-0.0484 pf=0.94 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1153 -> OK
- Bonferroni: p=0.12947 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.27, kurt=1.07) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk|crypto|1h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20)` · crypto · 1h · intraday
- Val @1x: n=220 expR=0.0678 pf=1.13 sharpe=0.054
- 2x cost: n=220 expR=-0.0887 pf=0.85 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0481 -> OK
- Bonferroni: p=0.21158 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.45, kurt=1.58) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk|crypto|1h|swing|n=55|c1.0`
- Rule: `donch_brk(n=55)` · crypto · 1h · swing
- Val @1x: n=118 expR=0.1123 pf=1.17 sharpe=0.075
- 2x cost: n=118 expR=-0.0467 pf=0.94 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1235 -> OK
- Bonferroni: p=0.20762 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.31, kurt=1.08) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk|crypto|1h|intraday|n=55|c1.0`
- Rule: `donch_brk(n=55)` · crypto · 1h · intraday
- Val @1x: n=134 expR=0.1630 pf=1.35 sharpe=0.131
- 2x cost: n=134 expR=0.0205 pf=1.04 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1688 -> OK
- Bonferroni: p=0.06470 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.36, kurt=1.51) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `zscore_rev|crypto|1h|swing|n=20,z=2.5|c1.0`
- Rule: `zscore_rev(n=20,z=2.5)` · crypto · 1h · swing
- Val @1x: n=118 expR=0.0713 pf=1.11 sharpe=0.049
- 2x cost: n=118 expR=-0.0894 pf=0.88 -> FAIL
- Sensitivity: 6/8 neighbors scored, 33% positive, median expR=-0.0605 -> FAIL
- Bonferroni: p=0.29727 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.37, kurt=1.12) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `zscore_rev|crypto|4h|intraday|n=50,z=2.0|c1.0`
- Rule: `zscore_rev(n=50,z=2.0)` · crypto · 4h · intraday
- Val @1x: n=168 expR=0.0264 pf=1.08 sharpe=0.030
- 2x cost: n=168 expR=-0.0088 pf=0.98 -> FAIL
- Sensitivity: 8/8 neighbors scored, 38% positive, median expR=-0.0007 -> FAIL
- Bonferroni: p=0.34870 vs 0.000227 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.52, kurt=2.61) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

## Summary

- 17 base-gate PASS -> **0 candidate(s)** after the full gauntlet.
- Nothing survived. No candidate is promoted — correct, disciplined outcome.
