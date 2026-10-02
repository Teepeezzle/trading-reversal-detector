# ROBUSTNESS (T-303) — multiple-testing correction + stress tests

_Generated 2026-10-02 09:50 UTC from `HYPOTHESIS_REGISTRY.csv`._

A base-gate PASS is only a lead. A **candidate** must additionally survive 2x cost, parameter sensitivity, and BOTH multiple-testing corrections below. Validation set only; holdout untouched.

## Selection context
- Valid tests (N, n>=100 — used for Bonferroni & the DSR benchmark): **288**  (configs attempted incl. THIN sub-100-trade: 540)
- Base-gate PASSes entering the gauntlet: **58**
- Family-wise alpha: 0.05 -> **Bonferroni per-hypothesis p < 0.000174**
- Trial-Sharpe variance: 0.0213 -> expected-max-Sharpe benchmark SR* = **0.4205** (per-trade)
- Deflated Sharpe Ratio threshold: **DSR > 0.95**

## Per-candidate gauntlet

### `roc_mom|forex_majors|2h|swing|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · forex_majors · 2h · swing
- Val @1x: n=129 expR=0.0245 pf=1.04 sharpe=0.017
- 2x cost: n=129 expR=-0.0933 pf=0.87 -> FAIL
- Sensitivity: 4/4 neighbors scored, 0% positive, median expR=-0.0914 -> FAIL
- Bonferroni: p=0.42345 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.50, kurt=1.28) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|forex_majors|1day|swing|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · forex_majors · 1day · swing
- Val @1x: n=373 expR=0.0073 pf=1.02 sharpe=0.008
- 2x cost: n=373 expR=-0.0302 pf=0.92 -> FAIL
- Sensitivity: 4/4 neighbors scored, 25% positive, median expR=-0.0348 -> FAIL
- Bonferroni: p=0.43861 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.43, kurt=2.32) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|forex_majors|3h|intraday|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · forex_majors · 3h · intraday
- Val @1x: n=164 expR=0.0172 pf=1.05 sharpe=0.018
- 2x cost: n=164 expR=-0.0594 pf=0.85 -> FAIL
- Sensitivity: 4/4 neighbors scored, 25% positive, median expR=-0.0198 -> FAIL
- Bonferroni: p=0.40885 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.74, kurt=2.79) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|forex_majors|4h|swing|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · forex_majors · 4h · swing
- Val @1x: n=148 expR=0.1419 pf=1.24 sharpe=0.100
- 2x cost: n=148 expR=0.0728 pf=1.12 -> OK
- Sensitivity: 7/8 neighbors scored, 100% positive, median expR=0.1407 -> OK
- Bonferroni: p=0.11189 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.41, kurt=1.22) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|forex_majors|4h|intraday|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · forex_majors · 4h · intraday
- Val @1x: n=201 expR=0.0096 pf=1.03 sharpe=0.011
- 2x cost: n=201 expR=-0.0350 pf=0.90 -> FAIL
- Sensitivity: 7/8 neighbors scored, 86% positive, median expR=0.0266 -> OK
- Bonferroni: p=0.43804 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.74, kurt=3.14) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|forex_majors|1day|intraday|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · forex_majors · 1day · intraday
- Val @1x: n=211 expR=0.0227 pf=1.19 sharpe=0.061
- 2x cost: n=211 expR=0.0096 pf=1.08 -> OK
- Sensitivity: 7/8 neighbors scored, 71% positive, median expR=0.0086 -> OK
- Bonferroni: p=0.18779 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=-0.10, kurt=4.12) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|forex_majors|4h|swing|fast=12,signal=9,slow=26|c1.0`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · forex_majors · 4h · swing
- Val @1x: n=224 expR=0.0228 pf=1.04 sharpe=0.017
- 2x cost: n=224 expR=-0.0474 pf=0.93 -> FAIL
- Sensitivity: 8/8 neighbors scored, 50% positive, median expR=0.0020 -> FAIL
- Bonferroni: p=0.39958 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.57, kurt=1.42) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|forex_majors|2h|intraday|fast=12,signal=9,slow=26|c1.0`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · forex_majors · 2h · intraday
- Val @1x: n=116 expR=0.0349 pf=1.09 sharpe=0.034
- 2x cost: n=116 expR=-0.0560 pf=0.87 -> FAIL
- Sensitivity: 8/8 neighbors scored, 50% positive, median expR=0.0220 -> FAIL
- Bonferroni: p=0.35711 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.69, kurt=2.45) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|forex_majors|1day|intraday|fast=12,signal=9,slow=26|c1.0`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · forex_majors · 1day · intraday
- Val @1x: n=273 expR=0.0009 pf=1.01 sharpe=0.003
- 2x cost: n=273 expR=-0.0118 pf=0.89 -> FAIL
- Sensitivity: 8/8 neighbors scored, 0% positive, median expR=-0.0097 -> FAIL
- Bonferroni: p=0.48023 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=-0.16, kurt=6.10) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|metals|1h|swing|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · metals · 1h · swing
- Val @1x: n=117 expR=0.1730 pf=1.28 sharpe=0.117
- 2x cost: n=117 expR=0.1355 pf=1.21 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.1288 -> OK
- Bonferroni: p=0.10284 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.40, kurt=1.14) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|metals|2h|intraday|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · metals · 2h · intraday
- Val @1x: n=107 expR=0.0998 pf=1.28 sharpe=0.097
- 2x cost: n=107 expR=0.0671 pf=1.17 -> OK
- Sensitivity: 3/4 neighbors scored, 100% positive, median expR=0.1134 -> OK
- Bonferroni: p=0.15784 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.55, kurt=2.24) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|metals|4h|intraday|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · metals · 4h · intraday
- Val @1x: n=104 expR=0.0288 pf=1.09 sharpe=0.034
- 2x cost: n=104 expR=0.0065 pf=1.02 -> OK
- Sensitivity: 3/4 neighbors scored, 100% positive, median expR=0.0609 -> OK
- Bonferroni: p=0.36440 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.70, kurt=2.94) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|metals|1h|intraday|n=20,thr=0.0|c1.0`
- Rule: `roc_mom(n=20,thr=0.0)` · metals · 1h · intraday
- Val @1x: n=132 expR=0.0430 pf=1.09 sharpe=0.036
- 2x cost: n=132 expR=-0.0226 pf=0.96 -> FAIL
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=-0.0142 -> FAIL
- Bonferroni: p=0.33958 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.50, kurt=1.89) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|metals|1day|intraday|n=20,thr=0.0|c1.0`
- Rule: `roc_mom(n=20,thr=0.0)` · metals · 1day · intraday
- Val @1x: n=122 expR=0.0187 pf=1.15 sharpe=0.046
- 2x cost: n=122 expR=0.0045 pf=1.03 -> OK
- Sensitivity: 4/4 neighbors scored, 0% positive, median expR=-0.0347 -> FAIL
- Bonferroni: p=0.30570 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.08, kurt=4.68) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `ema_pullback|metals|1h|intraday|f=10,s=50|c1.0`
- Rule: `ema_pullback(f=10,s=50)` · metals · 1h · intraday
- Val @1x: n=117 expR=0.0467 pf=1.09 sharpe=0.039
- 2x cost: n=117 expR=-0.0064 pf=0.99 -> FAIL
- Sensitivity: 8/8 neighbors scored, 88% positive, median expR=0.0304 -> OK
- Bonferroni: p=0.33657 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.50, kurt=1.81) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|metals|1h|intraday|fast=12,signal=9,slow=26|c1.0`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · metals · 1h · intraday
- Val @1x: n=119 expR=0.2454 pf=1.61 sharpe=0.206
- 2x cost: n=119 expR=0.2113 pf=1.50 -> OK
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.2113 -> OK
- Bonferroni: p=0.01231 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.008 (skew=0.26, kurt=1.56) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|oil|1h|swing|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · oil · 1h · swing
- Val @1x: n=190 expR=0.0468 pf=1.07 sharpe=0.032
- 2x cost: n=190 expR=-0.0144 pf=0.98 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0572 -> OK
- Bonferroni: p=0.32957 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.55, kurt=1.30) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|oil|1day|swing|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · oil · 1day · swing
- Val @1x: n=113 expR=0.0359 pf=1.10 sharpe=0.040
- 2x cost: n=113 expR=0.0072 pf=1.02 -> OK
- Sensitivity: 3/4 neighbors scored, 67% positive, median expR=0.0209 -> OK
- Bonferroni: p=0.33534 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.31, kurt=2.10) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|oil|3h|intraday|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · oil · 3h · intraday
- Val @1x: n=127 expR=0.0474 pf=1.15 sharpe=0.055
- 2x cost: n=127 expR=0.0180 pf=1.06 -> OK
- Sensitivity: 4/4 neighbors scored, 75% positive, median expR=0.0630 -> OK
- Bonferroni: p=0.26769 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.58, kurt=2.71) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|oil|1day|intraday|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · oil · 1day · intraday
- Val @1x: n=146 expR=0.0522 pf=1.45 sharpe=0.142
- 2x cost: n=146 expR=0.0421 pf=1.35 -> OK
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0305 -> OK
- Bonferroni: p=0.04310 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=-0.47, kurt=3.28) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|oil|1h|swing|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · oil · 1h · swing
- Val @1x: n=120 expR=0.0814 pf=1.13 sharpe=0.056
- 2x cost: n=120 expR=0.0197 pf=1.03 -> OK
- Sensitivity: 7/8 neighbors scored, 14% positive, median expR=-0.0607 -> FAIL
- Bonferroni: p=0.26979 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.50, kurt=1.24) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|oil|1h|intraday|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · oil · 1h · intraday
- Val @1x: n=146 expR=0.0180 pf=1.04 sharpe=0.016
- 2x cost: n=146 expR=-0.0315 pf=0.93 -> FAIL
- Sensitivity: 7/8 neighbors scored, 0% positive, median expR=-0.0383 -> FAIL
- Bonferroni: p=0.42335 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.60, kurt=2.05) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `ema_pullback|oil|1day|intraday|f=10,s=50|c1.0`
- Rule: `ema_pullback(f=10,s=50)` · oil · 1day · intraday
- Val @1x: n=113 expR=0.0095 pf=1.06 sharpe=0.023
- 2x cost: n=113 expR=-0.0015 pf=0.99 -> FAIL
- Sensitivity: 7/8 neighbors scored, 86% positive, median expR=0.0125 -> OK
- Bonferroni: p=0.40342 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=-0.42, kurt=3.13) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|oil|1h|swing|d=3,klen=14,os=20|c1.0`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · oil · 1h · swing
- Val @1x: n=112 expR=0.3720 pf=1.68 sharpe=0.249
- 2x cost: n=112 expR=0.3046 pf=1.52 -> OK
- Sensitivity: 10/12 neighbors scored, 100% positive, median expR=0.3666 -> OK
- Bonferroni: p=0.00420 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.034 (skew=0.08, kurt=0.99) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|oil|1h|intraday|d=3,klen=14,os=20|c1.0`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · oil · 1h · intraday
- Val @1x: n=138 expR=0.1606 pf=1.47 sharpe=0.152
- 2x cost: n=138 expR=0.1066 pf=1.29 -> OK
- Sensitivity: 10/12 neighbors scored, 100% positive, median expR=0.1192 -> OK
- Bonferroni: p=0.03708 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=0.49, kurt=2.07) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|oil|1h|intraday|d=3,klen=21,os=20|c1.0`
- Rule: `stoch_rev(d=3,klen=21,os=20)` · oil · 1h · intraday
- Val @1x: n=117 expR=0.1526 pf=1.46 sharpe=0.150
- 2x cost: n=117 expR=0.0996 pf=1.28 -> OK
- Sensitivity: 10/12 neighbors scored, 90% positive, median expR=0.1272 -> OK
- Bonferroni: p=0.05235 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=0.51, kurt=2.20) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|oil|1h|swing|fast=12,signal=9,slow=26|c1.0`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · oil · 1h · swing
- Val @1x: n=161 expR=0.0119 pf=1.02 sharpe=0.008
- 2x cost: n=161 expR=-0.0487 pf=0.93 -> FAIL
- Sensitivity: 8/8 neighbors scored, 25% positive, median expR=-0.0258 -> FAIL
- Bonferroni: p=0.45957 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.60, kurt=1.36) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|crypto|1day|swing|n=10,thr=0.0|c1.0`
- Rule: `roc_mom(n=10,thr=0.0)` · crypto · 1day · swing
- Val @1x: n=509 expR=0.0623 pf=1.16 sharpe=0.061
- 2x cost: n=509 expR=0.0287 pf=1.07 -> OK
- Sensitivity: 4/4 neighbors scored, 75% positive, median expR=0.0309 -> OK
- Bonferroni: p=0.08438 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.62, kurt=2.20) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|crypto|15min|swing|n=20,thr=0.0|c1.0`
- Rule: `roc_mom(n=20,thr=0.0)` · crypto · 15min · swing
- Val @1x: n=438 expR=0.0966 pf=1.14 sharpe=0.064
- 2x cost: n=438 expR=-0.1219 pf=0.85 -> FAIL
- Sensitivity: 4/4 neighbors scored, 100% positive, median expR=0.0991 -> OK
- Bonferroni: p=0.09022 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.24, kurt=1.10) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|crypto|1day|swing|n=20,thr=0.0|c1.0`
- Rule: `roc_mom(n=20,thr=0.0)` · crypto · 1day · swing
- Val @1x: n=376 expR=0.0451 pf=1.12 sharpe=0.046
- 2x cost: n=376 expR=0.0106 pf=1.03 -> OK
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=-0.0026 -> FAIL
- Bonferroni: p=0.18620 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.63, kurt=2.31) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `roc_mom|crypto|15min|intraday|n=20,thr=0.0|c1.0`
- Rule: `roc_mom(n=20,thr=0.0)` · crypto · 15min · intraday
- Val @1x: n=489 expR=0.0380 pf=1.06 sharpe=0.027
- 2x cost: n=489 expR=-0.1868 pf=0.76 -> FAIL
- Sensitivity: 4/4 neighbors scored, 75% positive, median expR=0.0160 -> OK
- Bonferroni: p=0.27523 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.32, kurt=1.29) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|15min|swing|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · crypto · 15min · swing
- Val @1x: n=397 expR=0.0693 pf=1.10 sharpe=0.046
- 2x cost: n=397 expR=-0.1536 pf=0.81 -> FAIL
- Sensitivity: 8/8 neighbors scored, 88% positive, median expR=0.0722 -> OK
- Bonferroni: p=0.17969 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.27, kurt=1.13) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|1h|swing|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · crypto · 1h · swing
- Val @1x: n=348 expR=0.0164 pf=1.02 sharpe=0.011
- 2x cost: n=348 expR=-0.1569 pf=0.81 -> FAIL
- Sensitivity: 8/8 neighbors scored, 38% positive, median expR=-0.0318 -> FAIL
- Bonferroni: p=0.41871 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.42, kurt=1.19) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|2h|swing|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · crypto · 2h · swing
- Val @1x: n=177 expR=0.1306 pf=1.20 sharpe=0.088
- 2x cost: n=177 expR=0.0070 pf=1.01 -> OK
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.1794 -> OK
- Bonferroni: p=0.12085 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.34, kurt=1.12) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|3h|swing|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · crypto · 3h · swing
- Val @1x: n=126 expR=0.1750 pf=1.28 sharpe=0.119
- 2x cost: n=126 expR=0.0733 pf=1.11 -> OK
- Sensitivity: 7/8 neighbors scored, 71% positive, median expR=0.1782 -> OK
- Bonferroni: p=0.09081 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.31, kurt=1.10) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|1day|swing|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · crypto · 1day · swing
- Val @1x: n=256 expR=0.0934 pf=1.19 sharpe=0.077
- 2x cost: n=256 expR=0.0584 pf=1.11 -> OK
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.0418 -> OK
- Bonferroni: p=0.10897 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.55, kurt=1.65) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|2h|intraday|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · crypto · 2h · intraday
- Val @1x: n=205 expR=0.1799 pf=1.45 sharpe=0.154
- 2x cost: n=205 expR=0.0737 pf=1.16 -> OK
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.2094 -> OK
- Bonferroni: p=0.01373 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.40, kurt=1.69) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|3h|intraday|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · crypto · 3h · intraday
- Val @1x: n=159 expR=0.1281 pf=1.34 sharpe=0.117
- 2x cost: n=159 expR=0.0431 pf=1.10 -> OK
- Sensitivity: 7/8 neighbors scored, 100% positive, median expR=0.1196 -> OK
- Bonferroni: p=0.07006 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.57, kurt=1.99) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|1day|intraday|kstd=2.0,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.0,n=20)` · crypto · 1day · intraday
- Val @1x: n=319 expR=0.0231 pf=1.10 sharpe=0.035
- 2x cost: n=319 expR=0.0035 pf=1.01 -> OK
- Sensitivity: 8/8 neighbors scored, 88% positive, median expR=0.0185 -> OK
- Bonferroni: p=0.26595 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.96, kurt=4.29) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|1h|swing|kstd=2.5,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.5,n=20)` · crypto · 1h · swing
- Val @1x: n=229 expR=0.0429 pf=1.06 sharpe=0.029
- 2x cost: n=229 expR=-0.1193 pf=0.85 -> FAIL
- Sensitivity: 8/8 neighbors scored, 88% positive, median expR=0.0646 -> OK
- Bonferroni: p=0.33039 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.40, kurt=1.17) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|2h|swing|kstd=2.5,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.5,n=20)` · crypto · 2h · swing
- Val @1x: n=104 expR=0.3331 pf=1.58 sharpe=0.222
- 2x cost: n=104 expR=0.2111 pf=1.33 -> OK
- Sensitivity: 6/8 neighbors scored, 100% positive, median expR=0.2579 -> OK
- Bonferroni: p=0.01179 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.021 (skew=0.06, kurt=0.99) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|1day|swing|kstd=2.5,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.5,n=20)` · crypto · 1day · swing
- Val @1x: n=158 expR=0.0185 pf=1.03 sharpe=0.015
- 2x cost: n=158 expR=-0.0141 pf=0.97 -> FAIL
- Sensitivity: 7/8 neighbors scored, 57% positive, median expR=0.0161 -> FAIL
- Bonferroni: p=0.42522 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.64, kurt=1.72) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|2h|intraday|kstd=2.5,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.5,n=20)` · crypto · 2h · intraday
- Val @1x: n=115 expR=0.2198 pf=1.52 sharpe=0.182
- 2x cost: n=115 expR=0.1161 pf=1.24 -> OK
- Sensitivity: 6/8 neighbors scored, 100% positive, median expR=0.2039 -> OK
- Bonferroni: p=0.02548 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.004 (skew=0.33, kurt=1.53) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `bb_breakout|crypto|1day|intraday|kstd=2.5,n=20|c1.0`
- Rule: `bb_breakout(kstd=2.5,n=20)` · crypto · 1day · intraday
- Val @1x: n=179 expR=0.0584 pf=1.22 sharpe=0.076
- 2x cost: n=179 expR=0.0397 pf=1.14 -> OK
- Sensitivity: 7/8 neighbors scored, 100% positive, median expR=0.0377 -> OK
- Bonferroni: p=0.15462 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.77, kurt=3.31) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `ema_pullback|crypto|15min|swing|f=10,s=50|c1.0`
- Rule: `ema_pullback(f=10,s=50)` · crypto · 15min · swing
- Val @1x: n=383 expR=0.0435 pf=1.06 sharpe=0.029
- 2x cost: n=383 expR=-0.1664 pf=0.80 -> FAIL
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.0454 -> OK
- Bonferroni: p=0.28517 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.31, kurt=1.16) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `ema_pullback|crypto|1day|swing|f=10,s=50|c1.0`
- Rule: `ema_pullback(f=10,s=50)` · crypto · 1day · swing
- Val @1x: n=273 expR=0.0317 pf=1.08 sharpe=0.031
- 2x cost: n=273 expR=-0.0021 pf=1.00 -> FAIL
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.0258 -> OK
- Bonferroni: p=0.30425 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.66, kurt=2.19) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `ema_pullback|crypto|15min|swing|f=20,s=100|c1.0`
- Rule: `ema_pullback(f=20,s=100)` · crypto · 15min · swing
- Val @1x: n=314 expR=0.1575 pf=1.24 sharpe=0.104
- 2x cost: n=314 expR=-0.0513 pf=0.93 -> FAIL
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.1544 -> OK
- Bonferroni: p=0.03267 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.17, kurt=1.07) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `ema_pullback|crypto|4h|swing|f=20,s=100|c1.0`
- Rule: `ema_pullback(f=20,s=100)` · crypto · 4h · swing
- Val @1x: n=149 expR=0.0409 pf=1.06 sharpe=0.029
- 2x cost: n=149 expR=-0.0297 pf=0.96 -> FAIL
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.0377 -> OK
- Bonferroni: p=0.36167 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.55, kurt=1.32) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `ema_pullback|crypto|15min|intraday|f=20,s=100|c1.0`
- Rule: `ema_pullback(f=20,s=100)` · crypto · 15min · intraday
- Val @1x: n=341 expR=0.0577 pf=1.09 sharpe=0.041
- 2x cost: n=341 expR=-0.1522 pf=0.80 -> FAIL
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.0590 -> OK
- Bonferroni: p=0.22449 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.30, kurt=1.27) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `ema_pullback|crypto|4h|intraday|f=20,s=100|c1.0`
- Rule: `ema_pullback(f=20,s=100)` · crypto · 4h · intraday
- Val @1x: n=209 expR=0.0229 pf=1.07 sharpe=0.026
- 2x cost: n=209 expR=-0.0303 pf=0.91 -> FAIL
- Sensitivity: 8/8 neighbors scored, 88% positive, median expR=0.0290 -> OK
- Bonferroni: p=0.35350 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.67, kurt=2.87) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|crypto|3h|swing|d=3,klen=14,os=20|c1.0`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · crypto · 3h · swing
- Val @1x: n=173 expR=0.0691 pf=1.11 sharpe=0.048
- 2x cost: n=173 expR=-0.0352 pf=0.95 -> FAIL
- Sensitivity: 11/12 neighbors scored, 82% positive, median expR=0.0446 -> OK
- Bonferroni: p=0.26391 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.45, kurt=1.23) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|crypto|1day|swing|d=3,klen=14,os=20|c1.0`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · crypto · 1day · swing
- Val @1x: n=303 expR=0.1013 pf=1.33 sharpe=0.112
- 2x cost: n=303 expR=0.0694 pf=1.21 -> OK
- Sensitivity: 11/12 neighbors scored, 100% positive, median expR=0.1013 -> OK
- Bonferroni: p=0.02561 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.53, kurt=2.53) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|crypto|4h|intraday|d=3,klen=14,os=20|c1.0`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · crypto · 4h · intraday
- Val @1x: n=673 expR=0.0021 pf=1.01 sharpe=0.002
- 2x cost: n=673 expR=-0.0392 pf=0.89 -> FAIL
- Sensitivity: 12/12 neighbors scored, 42% positive, median expR=-0.0121 -> FAIL
- Bonferroni: p=0.47931 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.69, kurt=2.93) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|crypto|1day|intraday|d=3,klen=14,os=20|c1.0`
- Rule: `stoch_rev(d=3,klen=14,os=20)` · crypto · 1day · intraday
- Val @1x: n=313 expR=0.0401 pf=1.28 sharpe=0.090
- 2x cost: n=313 expR=0.0244 pf=1.16 -> OK
- Sensitivity: 12/12 neighbors scored, 100% positive, median expR=0.0433 -> OK
- Bonferroni: p=0.05566 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.47, kurt=4.88) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|crypto|1day|swing|d=3,klen=21,os=20|c1.0`
- Rule: `stoch_rev(d=3,klen=21,os=20)` · crypto · 1day · swing
- Val @1x: n=246 expR=0.0576 pf=1.18 sharpe=0.066
- 2x cost: n=246 expR=0.0259 pf=1.08 -> OK
- Sensitivity: 11/12 neighbors scored, 100% positive, median expR=0.0609 -> OK
- Bonferroni: p=0.15029 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.59, kurt=2.68) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `stoch_rev|crypto|1day|intraday|d=3,klen=21,os=20|c1.0`
- Rule: `stoch_rev(d=3,klen=21,os=20)` · crypto · 1day · intraday
- Val @1x: n=267 expR=0.0365 pf=1.24 sharpe=0.080
- 2x cost: n=267 expR=0.0208 pf=1.13 -> OK
- Sensitivity: 11/12 neighbors scored, 100% positive, median expR=0.0365 -> OK
- Bonferroni: p=0.09557 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.44, kurt=4.51) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|crypto|1day|swing|fast=12,signal=9,slow=26|c1.0`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · crypto · 1day · swing
- Val @1x: n=341 expR=0.1205 pf=1.31 sharpe=0.112
- 2x cost: n=341 expR=0.0872 pf=1.21 -> OK
- Sensitivity: 8/8 neighbors scored, 100% positive, median expR=0.1184 -> OK
- Bonferroni: p=0.01931 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.54, kurt=1.94) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `macd_mom|crypto|1day|intraday|fast=12,signal=9,slow=26|c1.0`
- Rule: `macd_mom(fast=12,signal=9,slow=26)` · crypto · 1day · intraday
- Val @1x: n=355 expR=0.0028 pf=1.01 sharpe=0.005
- 2x cost: n=355 expR=-0.0144 pf=0.93 -> FAIL
- Sensitivity: 8/8 neighbors scored, 75% positive, median expR=0.0232 -> OK
- Bonferroni: p=0.46247 vs 0.000174 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=1.04, kurt=6.09) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

## Summary

- 58 base-gate PASS -> **0 candidate(s)** after the full gauntlet.
- Nothing survived. No candidate is promoted — correct, disciplined outcome.
