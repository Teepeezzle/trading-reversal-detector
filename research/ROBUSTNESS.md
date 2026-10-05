# ROBUSTNESS (T-303) — multiple-testing correction + stress tests

_Generated 2026-10-05 12:30 UTC from `HYPOTHESIS_REGISTRY.csv`._

A base-gate PASS is only a lead. A **candidate** must additionally survive 2x cost, parameter sensitivity, and BOTH multiple-testing corrections below. Validation set only; holdout untouched.

## Selection context
- Valid tests (N, n>=100 — used for Bonferroni & the DSR benchmark): **55**  (configs attempted incl. THIN sub-100-trade: 162)
- Base-gate PASSes entering the gauntlet: **16**
- Family-wise alpha: 0.05 -> **Bonferroni per-hypothesis p < 0.000909**
- Trial-Sharpe variance: 0.0272 -> expected-max-Sharpe benchmark SR* = **0.3812** (per-trade)
- Deflated Sharpe Ratio threshold: **DSR > 0.95**

## Per-candidate gauntlet

### `sent_mom|forex_crosses|1day|swing|side=long,z=0.25|n10`
- Rule: `sent_mom(side=long,z=0.25)` · forex_crosses · 1day · swing
- Val @1x: n=125 expR=0.1396 pf=1.43 sharpe=0.147
- 2x cost: n=125 expR=0.0697 pf=1.20 -> OK
- Sensitivity: 2/2 neighbors scored, 100% positive, median expR=0.0883 -> OK
- Bonferroni: p=0.05014 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.004 (skew=0.32, kurt=2.11) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|forex_crosses|1day|intraday|side=long,z=0.25|n10`
- Rule: `sent_mom(side=long,z=0.25)` · forex_crosses · 1day · intraday
- Val @1x: n=224 expR=0.0195 pf=1.12 sharpe=0.043
- 2x cost: n=224 expR=-0.0046 pf=0.97 -> FAIL
- Sensitivity: 2/2 neighbors scored, 50% positive, median expR=0.0202 -> FAIL
- Bonferroni: p=0.25993 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.89, kurt=5.20) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|forex_crosses|1day|swing|side=long,z=0.5|n10`
- Rule: `sent_mom(side=long,z=0.5)` · forex_crosses · 1day · swing
- Val @1x: n=123 expR=0.1112 pf=1.37 sharpe=0.124
- 2x cost: n=123 expR=0.0419 pf=1.13 -> OK
- Sensitivity: 2/3 neighbors scored, 100% positive, median expR=0.1026 -> OK
- Bonferroni: p=0.08453 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.002 (skew=0.31, kurt=2.35) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|forex_crosses|1day|intraday|side=long,z=0.5|n10`
- Rule: `sent_mom(side=long,z=0.5)` · forex_crosses · 1day · intraday
- Val @1x: n=203 expR=0.0484 pf=1.32 sharpe=0.103
- 2x cost: n=203 expR=0.0241 pf=1.15 -> OK
- Sensitivity: 2/3 neighbors scored, 50% positive, median expR=0.0057 -> FAIL
- Bonferroni: p=0.07112 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.74, kurt=5.02) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|forex_crosses|1day|intraday|side=short,z=0.5|n10`
- Rule: `sent_mom(side=short,z=0.5)` · forex_crosses · 1day · intraday
- Val @1x: n=181 expR=0.0232 pf=1.16 sharpe=0.059
- 2x cost: n=181 expR=-0.0012 pf=0.99 -> FAIL
- Sensitivity: 2/3 neighbors scored, 50% positive, median expR=-0.0026 -> FAIL
- Bonferroni: p=0.21367 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.00, kurt=2.94) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_rev|crypto|4h|swing|side=long,z=1.0|n10`
- Rule: `sent_rev(side=long,z=1.0)` · crypto · 4h · swing
- Val @1x: n=102 expR=0.0874 pf=1.14 sharpe=0.062
- 2x cost: n=102 expR=0.0228 pf=1.03 -> OK
- Sensitivity: 4/4 neighbors scored, 25% positive, median expR=-0.0566 -> FAIL
- Bonferroni: p=0.26560 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=0.50, kurt=1.27) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_rev|crypto|1day|intraday|side=short,z=1.0|n10`
- Rule: `sent_rev(side=short,z=1.0)` · crypto · 1day · intraday
- Val @1x: n=831 expR=0.0059 pf=1.04 sharpe=0.013
- 2x cost: n=831 expR=-0.0100 pf=0.94 -> FAIL
- Sensitivity: 4/4 neighbors scored, 0% positive, median expR=-0.0120 -> FAIL
- Bonferroni: p=0.35392 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.58, kurt=5.66) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|4h|swing|side=long,z=0.25|n10`
- Rule: `sent_mom(side=long,z=0.25)` · crypto · 4h · swing
- Val @1x: n=211 expR=0.4317 pf=1.85 sharpe=0.294
- 2x cost: n=211 expR=0.3701 pf=1.69 -> OK
- Sensitivity: 2/2 neighbors scored, 50% positive, median expR=0.0334 -> FAIL
- Bonferroni: p=0.00001 vs 0.000909 -> OK
- Deflated Sharpe: DSR=0.103 (skew=0.01, kurt=1.02) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Deflated Sharpe)**

### `sent_mom|crypto|4h|intraday|side=long,z=0.25|n10`
- Rule: `sent_mom(side=long,z=0.25)` · crypto · 4h · intraday
- Val @1x: n=238 expR=0.3619 pf=2.35 sharpe=0.340
- 2x cost: n=238 expR=0.3164 pf=2.10 -> OK
- Sensitivity: 2/2 neighbors scored, 50% positive, median expR=-0.0009 -> FAIL
- Bonferroni: p=0.00000 vs 0.000909 -> OK
- Deflated Sharpe: DSR=0.254 (skew=0.32, kurt=1.79) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Deflated Sharpe)**

### `sent_mom|crypto|1day|intraday|side=long,z=0.25|n10`
- Rule: `sent_mom(side=long,z=0.25)` · crypto · 1day · intraday
- Val @1x: n=1673 expR=0.0046 pf=1.03 sharpe=0.010
- 2x cost: n=1673 expR=-0.0116 pf=0.93 -> FAIL
- Sensitivity: 2/2 neighbors scored, 0% positive, median expR=-0.0095 -> FAIL
- Bonferroni: p=0.34126 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.52, kurt=5.53) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|4h|swing|side=long,z=0.5|n10`
- Rule: `sent_mom(side=long,z=0.5)` · crypto · 4h · swing
- Val @1x: n=162 expR=0.2264 pf=1.39 sharpe=0.156
- 2x cost: n=162 expR=0.1668 pf=1.27 -> OK
- Sensitivity: 3/3 neighbors scored, 33% positive, median expR=-0.1518 -> FAIL
- Bonferroni: p=0.02354 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.002 (skew=0.29, kurt=1.09) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|4h|intraday|side=long,z=0.5|n10`
- Rule: `sent_mom(side=long,z=0.5)` · crypto · 4h · intraday
- Val @1x: n=170 expR=0.1284 pf=1.37 sharpe=0.128
- 2x cost: n=170 expR=0.0830 pf=1.23 -> OK
- Sensitivity: 3/3 neighbors scored, 33% positive, median expR=-0.1302 -> FAIL
- Bonferroni: p=0.04757 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.57, kurt=2.23) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|1day|swing|side=long,z=1.0|n10`
- Rule: `sent_mom(side=long,z=1.0)` · crypto · 1day · swing
- Val @1x: n=642 expR=0.0232 pf=1.06 sharpe=0.025
- 2x cost: n=642 expR=-0.0082 pf=0.98 -> FAIL
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=0.0358 -> FAIL
- Bonferroni: p=0.26322 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.56, kurt=2.41) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|4h|swing|side=short,z=0.25|n10`
- Rule: `sent_mom(side=short,z=0.25)` · crypto · 4h · swing
- Val @1x: n=205 expR=0.0463 pf=1.07 sharpe=0.033
- 2x cost: n=205 expR=-0.0129 pf=0.98 -> FAIL
- Sensitivity: 2/2 neighbors scored, 0% positive, median expR=-0.2247 -> FAIL
- Bonferroni: p=0.31829 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.53, kurt=1.34) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|1day|swing|side=short,z=0.5|n10`
- Rule: `sent_mom(side=short,z=0.5)` · crypto · 1day · swing
- Val @1x: n=880 expR=0.0466 pf=1.12 sharpe=0.048
- 2x cost: n=880 expR=0.0144 pf=1.04 -> OK
- Sensitivity: 3/3 neighbors scored, 33% positive, median expR=-0.0202 -> FAIL
- Bonferroni: p=0.07724 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.49, kurt=2.19) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `sent_mom|crypto|1day|intraday|side=short,z=1.0|n10`
- Rule: `sent_mom(side=short,z=1.0)` · crypto · 1day · intraday
- Val @1x: n=885 expR=0.0067 pf=1.04 sharpe=0.016
- 2x cost: n=885 expR=-0.0098 pf=0.94 -> FAIL
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=0.0028 -> FAIL
- Bonferroni: p=0.31704 vs 0.000909 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=-0.29, kurt=3.67) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

## Summary

- 16 base-gate PASS -> **0 candidate(s)** after the full gauntlet.
- Nothing survived. No candidate is promoted — correct, disciplined outcome.
