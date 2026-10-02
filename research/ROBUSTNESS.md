# ROBUSTNESS (T-303) — multiple-testing correction + stress tests

_Generated 2026-10-02 07:49 UTC from `HYPOTHESIS_REGISTRY.csv`._

A base-gate PASS is only a lead. A **candidate** must additionally survive 2x cost, parameter sensitivity, and BOTH multiple-testing corrections below. Validation set only; holdout untouched.

## Selection context
- Valid tests (N, n>=100 — used for Bonferroni & the DSR benchmark): **28**  (configs attempted incl. THIN sub-100-trade: 119)
- Base-gate PASSes entering the gauntlet: **21**
- Family-wise alpha: 0.05 -> **Bonferroni per-hypothesis p < 0.00179**
- Trial-Sharpe variance: 0.0068 -> expected-max-Sharpe benchmark SR* = **0.1687** (per-trade)
- Deflated Sharpe Ratio threshold: **DSR > 0.95**

## Per-candidate gauntlet

### `donch_brk+trend_up|forex_majors|4h|swing|n=20|c1.0`
- Rule: `donch_brk(n=20) & trend_up` · forex_majors · 4h · swing
- Val @1x: n=126 expR=0.1011 pf=1.17 sharpe=0.074
- 2x cost: n=126 expR=0.0280 pf=1.05 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0924 -> OK
- Bonferroni: p=0.20309 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.141 (skew=0.46, kurt=1.34) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+ny|forex_majors|4h|swing|n=20|c1.0`
- Rule: `donch_brk(n=20) & ny` · forex_majors · 4h · swing
- Val @1x: n=132 expR=0.1165 pf=1.20 sharpe=0.085
- 2x cost: n=132 expR=0.0403 pf=1.07 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1235 -> OK
- Bonferroni: p=0.16439 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.165 (skew=0.43, kurt=1.32) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+adx_lo25|forex_majors|4h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20) & adx_lo25` · forex_majors · 4h · intraday
- Val @1x: n=130 expR=0.0736 pf=1.24 sharpe=0.083
- 2x cost: n=130 expR=0.0288 pf=1.09 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0584 -> OK
- Bonferroni: p=0.17199 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.159 (skew=0.64, kurt=2.79) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+trend_up|forex_majors|4h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20) & trend_up` · forex_majors · 4h · intraday
- Val @1x: n=193 expR=0.0392 pf=1.13 sharpe=0.047
- 2x cost: n=193 expR=-0.0046 pf=0.99 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0328 -> OK
- Bonferroni: p=0.25690 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.044 (skew=0.61, kurt=2.97) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+vol_hi|forex_majors|4h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20) & vol_hi` · forex_majors · 4h · intraday
- Val @1x: n=129 expR=0.0534 pf=1.20 sharpe=0.067
- 2x cost: n=129 expR=0.0128 pf=1.04 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0505 -> OK
- Bonferroni: p=0.22334 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.119 (skew=0.73, kurt=3.33) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+ny|forex_majors|4h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20) & ny` · forex_majors · 4h · intraday
- Val @1x: n=174 expR=0.0078 pf=1.03 sharpe=0.011
- 2x cost: n=174 expR=-0.0362 pf=0.86 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0174 -> OK
- Bonferroni: p=0.44232 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.019 (skew=0.90, kurt=4.44) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+trend_up|metals|1h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20) & trend_up` · metals · 1h · intraday
- Val @1x: n=104 expR=0.1143 pf=1.24 sharpe=0.094
- 2x cost: n=104 expR=0.0618 pf=1.12 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1074 -> OK
- Bonferroni: p=0.16888 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.220 (skew=0.37, kurt=1.74) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+trend_up|oil|1h|intraday|n=55|c1.0`
- Rule: `donch_brk(n=55) & trend_up` · oil · 1h · intraday
- Val @1x: n=100 expR=0.0152 pf=1.03 sharpe=0.013
- 2x cost: n=100 expR=-0.0302 pf=0.94 -> FAIL
- Sensitivity: 2/4 neighbors scored, 50% positive, median expR=0.0047 -> FAIL
- Bonferroni: p=0.44828 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.060 (skew=0.65, kurt=1.83) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+adx_lo25|crypto|1h|swing|n=20|c1.0`
- Rule: `donch_brk(n=20) & adx_lo25` · crypto · 1h · swing
- Val @1x: n=110 expR=0.0321 pf=1.05 sharpe=0.022
- 2x cost: n=110 expR=-0.1630 pf=0.80 -> FAIL
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=0.0194 -> FAIL
- Bonferroni: p=0.40876 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.062 (skew=0.37, kurt=1.12) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+adx_hi25|crypto|1h|swing|n=20|c1.0`
- Rule: `donch_brk(n=20) & adx_hi25` · crypto · 1h · swing
- Val @1x: n=106 expR=0.1787 pf=1.28 sharpe=0.119
- 2x cost: n=106 expR=0.0272 pf=1.04 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1672 -> OK
- Bonferroni: p=0.11025 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.303 (skew=0.23, kurt=1.02) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+trend_up|crypto|1h|swing|n=20|c1.0`
- Rule: `donch_brk(n=20) & trend_up` · crypto · 1h · swing
- Val @1x: n=148 expR=0.0948 pf=1.14 sharpe=0.063
- 2x cost: n=148 expR=-0.0673 pf=0.91 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0864 -> OK
- Bonferroni: p=0.22171 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.098 (skew=0.33, kurt=1.09) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+vol_hi|crypto|1h|swing|n=20|c1.0`
- Rule: `donch_brk(n=20) & vol_hi` · crypto · 1h · swing
- Val @1x: n=116 expR=0.2811 pf=1.47 sharpe=0.187
- 2x cost: n=116 expR=0.1398 pf=1.21 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.2692 -> OK
- Bonferroni: p=0.02200 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.578 (skew=0.11, kurt=0.98) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+ny|crypto|1h|swing|n=20|c1.0`
- Rule: `donch_brk(n=20) & ny` · crypto · 1h · swing
- Val @1x: n=130 expR=0.2694 pf=1.44 sharpe=0.177
- 2x cost: n=130 expR=0.0850 pf=1.12 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.2592 -> OK
- Bonferroni: p=0.02179 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.538 (skew=0.06, kurt=0.99) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+adx_hi25|crypto|1h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20) & adx_hi25` · crypto · 1h · intraday
- Val @1x: n=115 expR=0.2348 pf=1.52 sharpe=0.182
- 2x cost: n=115 expR=0.0977 pf=1.18 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.2107 -> OK
- Bonferroni: p=0.02548 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.558 (skew=0.27, kurt=1.35) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+trend_up|crypto|1h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20) & trend_up` · crypto · 1h · intraday
- Val @1x: n=168 expR=0.1199 pf=1.25 sharpe=0.096
- 2x cost: n=168 expR=-0.0254 pf=0.96 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1145 -> OK
- Bonferroni: p=0.10669 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.169 (skew=0.40, kurt=1.52) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+vol_hi|crypto|1h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20) & vol_hi` · crypto · 1h · intraday
- Val @1x: n=135 expR=0.2021 pf=1.45 sharpe=0.162
- 2x cost: n=135 expR=0.0788 pf=1.15 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1975 -> OK
- Bonferroni: p=0.02990 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.468 (skew=0.33, kurt=1.45) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+ny|crypto|1h|intraday|n=20|c1.0`
- Rule: `donch_brk(n=20) & ny` · crypto · 1h · intraday
- Val @1x: n=141 expR=0.0752 pf=1.16 sharpe=0.063
- 2x cost: n=141 expR=-0.0917 pf=0.84 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0602 -> OK
- Bonferroni: p=0.22720 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.102 (skew=0.44, kurt=1.68) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+trend_up|crypto|1h|swing|n=55|c1.0`
- Rule: `donch_brk(n=55) & trend_up` · crypto · 1h · swing
- Val @1x: n=110 expR=0.1867 pf=1.29 sharpe=0.124
- 2x cost: n=110 expR=0.0371 pf=1.05 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1870 -> OK
- Bonferroni: p=0.09671 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.318 (skew=0.22, kurt=1.02) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+trend_up|crypto|1h|intraday|n=55|c1.0`
- Rule: `donch_brk(n=55) & trend_up` · crypto · 1h · intraday
- Val @1x: n=125 expR=0.2303 pf=1.53 sharpe=0.184
- 2x cost: n=125 expR=0.0967 pf=1.19 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.2287 -> OK
- Bonferroni: p=0.01983 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.569 (skew=0.30, kurt=1.43) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk+vol_hi|crypto|1h|intraday|n=55|c1.0`
- Rule: `donch_brk(n=55) & vol_hi` · crypto · 1h · intraday
- Val @1x: n=104 expR=0.2941 pf=1.74 sharpe=0.238
- 2x cost: n=104 expR=0.1741 pf=1.38 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.2941 -> OK
- Bonferroni: p=0.00761 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.765 (skew=0.23, kurt=1.41) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `zscore_rev+adx_hi25|crypto|4h|intraday|n=50,z=2.0|c1.0`
- Rule: `zscore_rev(n=50,z=2.0) & adx_hi25` · crypto · 4h · intraday
- Val @1x: n=122 expR=0.1002 pf=1.35 sharpe=0.117
- 2x cost: n=122 expR=0.0668 pf=1.22 -> OK
- Sensitivity: 7/8 neighbors scored, 71% positive, median expR=0.0563 -> OK
- Bonferroni: p=0.09813 vs 0.00179 -> FAIL
- Deflated Sharpe: DSR=0.279 (skew=0.56, kurt=2.87) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

## Summary

- 21 base-gate PASS -> **0 candidate(s)** after the full gauntlet.
- Nothing survived. No candidate is promoted — correct, disciplined outcome.
