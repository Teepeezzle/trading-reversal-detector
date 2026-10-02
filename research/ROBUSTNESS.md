# ROBUSTNESS (T-303) — multiple-testing correction + stress tests

_Generated 2026-10-02 16:01 UTC from `HYPOTHESIS_REGISTRY.csv`._

A base-gate PASS is only a lead. A **candidate** must additionally survive 2x cost, parameter sensitivity, and BOTH multiple-testing corrections below. Validation set only; holdout untouched.

## Selection context
- Valid tests (N, n>=100 — used for Bonferroni & the DSR benchmark): **230**  (configs attempted incl. THIN sub-100-trade: 472)
- Base-gate PASSes entering the gauntlet: **19**
- Family-wise alpha: 0.05 -> **Bonferroni per-hypothesis p < 0.000217**
- Trial-Sharpe variance: 0.0117 -> expected-max-Sharpe benchmark SR* = **0.3036** (per-trade)
- Deflated Sharpe Ratio threshold: **DSR > 0.95**

## Per-candidate gauntlet

### `rsi_rev|forex_majors|4h|intraday|n=7,os=30|deep`
- Rule: `rsi_rev(n=7,os=30)` · forex_majors · 4h · intraday
- Val @1x: n=139 expR=0.0214 pf=1.07 sharpe=0.025
- 2x cost: n=139 expR=-0.0159 pf=0.95 -> FAIL
- Sensitivity: 6/8 neighbors scored, 100% positive, median expR=0.0657 -> OK
- Bonferroni: p=0.38409 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.44, kurt=2.49) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|forex_majors|1h|intraday|n=20,thr=0.0|deep`
- Rule: `roc_mom(n=20,thr=0.0)` · forex_majors · 1h · intraday
- Val @1x: n=514 expR=0.0100 pf=1.02 sharpe=0.009
- 2x cost: n=514 expR=-0.0689 pf=0.88 -> FAIL
- Sensitivity: 4/4 neighbors scored, 25% positive, median expR=-0.0103 -> FAIL
- Bonferroni: p=0.41916 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.56, kurt=1.77) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|forex_majors|4h|swing|d=3,klen=14,os=20|deep`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · forex_majors · 4h · swing
- Val @1x: n=118 expR=0.0901 pf=1.15 sharpe=0.065
- 2x cost: n=118 expR=0.0243 pf=1.04 -> OK
- Sensitivity: 11/12 neighbors scored, 73% positive, median expR=0.0514 -> OK
- Bonferroni: p=0.24007 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.004 (skew=0.48, kurt=1.29) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|forex_majors|1h|intraday|d=3,klen=14,os=20|deep`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · forex_majors · 1h · intraday
- Val @1x: n=475 expR=0.0032 pf=1.01 sharpe=0.003
- 2x cost: n=475 expR=-0.0724 pf=0.87 -> FAIL
- Sensitivity: 12/12 neighbors scored, 33% positive, median expR=-0.0169 -> FAIL
- Bonferroni: p=0.47393 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.60, kurt=1.82) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|forex_majors|4h|intraday|d=3,klen=14,os=20|deep`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · forex_majors · 4h · intraday
- Val @1x: n=133 expR=0.1661 pf=1.71 sharpe=0.206
- 2x cost: n=133 expR=0.1285 pf=1.51 -> OK
- Sensitivity: 11/12 neighbors scored, 100% positive, median expR=0.1661 -> OK
- Bonferroni: p=0.00876 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.123 (skew=0.41, kurt=2.84) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|forex_majors|4h|intraday|d=3,klen=21,os=20|deep`
- Rule: `stoch_rev(d=3,klen=21,os=20)` · forex_majors · 4h · intraday
- Val @1x: n=113 expR=0.0825 pf=1.33 sharpe=0.112
- 2x cost: n=113 expR=0.0447 pf=1.17 -> OK
- Sensitivity: 11/12 neighbors scored, 100% positive, median expR=0.0777 -> OK
- Bonferroni: p=0.11691 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.021 (skew=0.15, kurt=2.72) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|forex_majors|4h|swing|fast=12,signal=9,slow=26|deep`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · forex_majors · 4h · swing
- Val @1x: n=124 expR=0.0043 pf=1.01 sharpe=0.003
- 2x cost: n=124 expR=-0.0676 pf=0.89 -> FAIL
- Sensitivity: 8/8 neighbors scored, 62% positive, median expR=0.0034 -> OK
- Bonferroni: p=0.48668 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.58, kurt=1.53) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|forex_majors|1h|intraday|fast=12,signal=9,slow=26|deep`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · forex_majors · 1h · intraday
- Val @1x: n=535 expR=0.0067 pf=1.01 sharpe=0.006
- 2x cost: n=535 expR=-0.0721 pf=0.87 -> FAIL
- Sensitivity: 8/8 neighbors scored, 62% positive, median expR=0.0034 -> OK
- Bonferroni: p=0.44481 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.60, kurt=1.84) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `rsi_rev|forex_crosses|15min|swing|n=14,os=20|deep`
- Rule: `rsi_rev(n=14,os=20)` · forex_crosses · 15min · swing
- Val @1x: n=122 expR=0.0243 pf=1.03 sharpe=0.016
- 2x cost: n=122 expR=-0.2548 pf=0.72 -> FAIL
- Sensitivity: 4/8 neighbors scored, 0% positive, median expR=-0.2007 -> FAIL
- Bonferroni: p=0.42986 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=0.27, kurt=1.06) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `rsi_rev|forex_crosses|15min|intraday|n=14,os=20|deep`
- Rule: `rsi_rev(n=14,os=20)` · forex_crosses · 15min · intraday
- Val @1x: n=122 expR=0.0240 pf=1.04 sharpe=0.018
- 2x cost: n=122 expR=-0.2329 pf=0.70 -> FAIL
- Sensitivity: 4/8 neighbors scored, 0% positive, median expR=-0.1888 -> FAIL
- Bonferroni: p=0.42120 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=0.24, kurt=1.24) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `donch_brk|metals|1h|intraday|n=20|deep`
- Rule: `donch_brk(n=20)` · metals · 1h · intraday
- Val @1x: n=111 expR=0.0429 pf=1.09 sharpe=0.036
- 2x cost: n=111 expR=0.0143 pf=1.03 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0789 -> OK
- Bonferroni: p=0.35224 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.002 (skew=0.59, kurt=1.74) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|metals|1h|intraday|n=10,thr=0.0|deep`
- Rule: `roc_mom(n=10,thr=0.0)` · metals · 1h · intraday
- Val @1x: n=184 expR=0.0751 pf=1.17 sharpe=0.066
- 2x cost: n=184 expR=0.0477 pf=1.10 -> OK
- Sensitivity: 4/4 neighbors scored, 75% positive, median expR=0.0262 -> OK
- Bonferroni: p=0.18532 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=0.56, kurt=1.86) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|metals|15min|swing|kstd=2.0,n=20|deep`
- Rule: `bb_breakout(kstd=2.0,n=20)` · metals · 15min · swing
- Val @1x: n=301 expR=0.0191 pf=1.03 sharpe=0.013
- 2x cost: n=301 expR=-0.0483 pf=0.93 -> FAIL
- Sensitivity: 8/8 neighbors scored, 62% positive, median expR=0.0169 -> OK
- Bonferroni: p=0.41078 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.58, kurt=1.32) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|metals|15min|intraday|kstd=2.0,n=20|deep`
- Rule: `bb_breakout(kstd=2.0,n=20)` · metals · 15min · intraday
- Val @1x: n=323 expR=0.0348 pf=1.06 sharpe=0.026
- 2x cost: n=323 expR=-0.0298 pf=0.95 -> FAIL
- Sensitivity: 8/8 neighbors scored, 88% positive, median expR=0.0280 -> OK
- Bonferroni: p=0.32015 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.56, kurt=1.48) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|metals|15min|swing|kstd=2.5,n=20|deep`
- Rule: `bb_breakout(kstd=2.5,n=20)` · metals · 15min · swing
- Val @1x: n=169 expR=0.0354 pf=1.05 sharpe=0.024
- 2x cost: n=169 expR=-0.0297 pf=0.96 -> FAIL
- Sensitivity: 7/8 neighbors scored, 86% positive, median expR=0.0453 -> OK
- Bonferroni: p=0.37752 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.56, kurt=1.29) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|metals|15min|intraday|kstd=2.5,n=20|deep`
- Rule: `bb_breakout(kstd=2.5,n=20)` · metals · 15min · intraday
- Val @1x: n=176 expR=0.0417 pf=1.07 sharpe=0.031
- 2x cost: n=176 expR=-0.0198 pf=0.97 -> FAIL
- Sensitivity: 7/8 neighbors scored, 100% positive, median expR=0.0477 -> OK
- Bonferroni: p=0.34044 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.54, kurt=1.42) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|metals|1h|intraday|d=3,klen=14,os=20|deep`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · metals · 1h · intraday
- Val @1x: n=120 expR=0.0399 pf=1.09 sharpe=0.036
- 2x cost: n=120 expR=0.0138 pf=1.03 -> OK
- Sensitivity: 10/12 neighbors scored, 80% positive, median expR=0.0335 -> OK
- Bonferroni: p=0.34666 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.002 (skew=0.57, kurt=1.92) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|metals|1h|swing|fast=12,signal=9,slow=26|deep`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · metals · 1h · swing
- Val @1x: n=107 expR=0.1344 pf=1.21 sharpe=0.092
- 2x cost: n=107 expR=0.0972 pf=1.15 -> OK
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.1231 -> OK
- Bonferroni: p=0.17064 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.013 (skew=0.46, kurt=1.19) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|metals|1h|intraday|fast=12,signal=9,slow=26|deep`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · metals · 1h · intraday
- Val @1x: n=142 expR=0.1027 pf=1.26 sharpe=0.095
- 2x cost: n=142 expR=0.0740 pf=1.18 -> OK
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.1031 -> OK
- Bonferroni: p=0.12881 vs 0.000217 -> FAIL
- Deflated Sharpe: DSR=0.006 (skew=0.52, kurt=1.96) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

## Summary

- 19 base-gate PASS -> **0 candidate(s)** after the full gauntlet.
- Nothing survived. No candidate is promoted — correct, disciplined outcome.
