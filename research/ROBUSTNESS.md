# ROBUSTNESS (T-303) — multiple-testing correction + stress tests

_Generated 2026-10-02 14:23 UTC from `HYPOTHESIS_REGISTRY.csv`._

A base-gate PASS is only a lead. A **candidate** must additionally survive 2x cost, parameter sensitivity, and BOTH multiple-testing corrections below. Validation set only; holdout untouched.

## Selection context
- Valid tests (N, n>=100 — used for Bonferroni & the DSR benchmark): **132**  (configs attempted incl. THIN sub-100-trade: 192)
- Base-gate PASSes entering the gauntlet: **25**
- Family-wise alpha: 0.05 -> **Bonferroni per-hypothesis p < 0.000379**
- Trial-Sharpe variance: 0.0190 -> expected-max-Sharpe benchmark SR* = **0.3617** (per-trade)
- Deflated Sharpe Ratio threshold: **DSR > 0.95**

## Per-candidate gauntlet

### `xs_mom|crypto|15min|H=10,L=48,k=1,mode=lo|c1.0`
- Rule: `xs_mom(H=10,L=48,k=1,mode=lo)` · crypto · 15min · H10
- Val @1x: n=100 expR=0.0021 pf=1.32 sharpe=0.078
- 2x cost: n=100 expR=0.0009 pf=1.12 -> OK
- Sensitivity: 2/4 neighbors scored, 100% positive, median expR=0.0034 -> OK
- Bonferroni: p=0.21770 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.002 (skew=0.85, kurt=12.21) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|15min|H=10,L=48,k=2,mode=lo|c1.0`
- Rule: `xs_mom(H=10,L=48,k=2,mode=lo)` · crypto · 15min · H10
- Val @1x: n=100 expR=0.0008 pf=1.16 sharpe=0.044
- 2x cost: n=100 expR=-0.0004 pf=0.93 -> FAIL
- Sensitivity: 2/4 neighbors scored, 50% positive, median expR=0.0010 -> FAIL
- Bonferroni: p=0.32997 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=0.10, kurt=11.59) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1h|H=3,L=12,k=1,mode=lo|c1.0`
- Rule: `xs_mom(H=3,L=12,k=1,mode=lo)` · crypto · 1h · H3
- Val @1x: n=333 expR=0.0006 pf=1.13 sharpe=0.038
- 2x cost: n=333 expR=-0.0006 pf=0.88 -> FAIL
- Sensitivity: 4/4 neighbors scored, 25% positive, median expR=-0.0002 -> FAIL
- Bonferroni: p=0.24402 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=1.61, kurt=14.55) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1h|H=5,L=24,k=1,mode=ls|c1.0`
- Rule: `xs_mom(H=5,L=24,k=1,mode=ls)` · crypto · 1h · H5
- Val @1x: n=200 expR=0.0003 pf=1.06 sharpe=0.019
- 2x cost: n=200 expR=-0.0009 pf=0.86 -> FAIL
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=0.0001 -> FAIL
- Bonferroni: p=0.39408 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=1.66, kurt=9.97) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1h|H=10,L=48,k=1,mode=ls|c1.0`
- Rule: `xs_mom(H=10,L=48,k=1,mode=ls)` · crypto · 1h · H10
- Val @1x: n=100 expR=0.0032 pf=1.38 sharpe=0.123
- 2x cost: n=100 expR=0.0019 pf=1.21 -> OK
- Sensitivity: 3/4 neighbors scored, 100% positive, median expR=0.0016 -> OK
- Bonferroni: p=0.10935 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.007 (skew=0.49, kurt=3.33) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1h|H=10,L=48,k=1,mode=lo|c1.0`
- Rule: `xs_mom(H=10,L=48,k=1,mode=lo)` · crypto · 1h · H10
- Val @1x: n=100 expR=0.0025 pf=1.33 sharpe=0.102
- 2x cost: n=100 expR=0.0011 pf=1.14 -> OK
- Sensitivity: 3/4 neighbors scored, 67% positive, median expR=0.0003 -> OK
- Bonferroni: p=0.15386 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.004 (skew=0.82, kurt=4.20) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1h|H=10,L=48,k=2,mode=ls|c1.0`
- Rule: `xs_mom(H=10,L=48,k=2,mode=ls)` · crypto · 1h · H10
- Val @1x: n=100 expR=0.0002 pf=1.03 sharpe=0.010
- 2x cost: n=100 expR=-0.0012 pf=0.84 -> FAIL
- Sensitivity: 3/4 neighbors scored, 100% positive, median expR=0.0014 -> OK
- Bonferroni: p=0.46017 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.31, kurt=4.14) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1h|H=10,L=48,k=2,mode=lo|c1.0`
- Rule: `xs_mom(H=10,L=48,k=2,mode=lo)` · crypto · 1h · H10
- Val @1x: n=100 expR=0.0020 pf=1.34 sharpe=0.103
- 2x cost: n=100 expR=0.0006 pf=1.10 -> OK
- Sensitivity: 3/4 neighbors scored, 100% positive, median expR=0.0011 -> OK
- Bonferroni: p=0.15151 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.004 (skew=0.95, kurt=4.97) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1day|H=3,L=12,k=1,mode=ls|c1.0`
- Rule: `xs_mom(H=3,L=12,k=1,mode=ls)` · crypto · 1day · H3
- Val @1x: n=131 expR=0.0038 pf=1.11 sharpe=0.029
- 2x cost: n=131 expR=0.0017 pf=1.05 -> OK
- Sensitivity: 3/4 neighbors scored, 67% positive, median expR=0.0007 -> OK
- Bonferroni: p=0.36997 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=3.56, kurt=25.23) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1day|H=3,L=12,k=1,mode=lo|c1.0`
- Rule: `xs_mom(H=3,L=12,k=1,mode=lo)` · crypto · 1day · H3
- Val @1x: n=131 expR=0.0101 pf=1.32 sharpe=0.070
- 2x cost: n=131 expR=0.0080 pf=1.24 -> OK
- Sensitivity: 3/4 neighbors scored, 100% positive, median expR=0.0085 -> OK
- Bonferroni: p=0.21151 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=4.60, kurt=33.30) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1day|H=3,L=12,k=2,mode=ls|c1.0`
- Rule: `xs_mom(H=3,L=12,k=2,mode=ls)` · crypto · 1day · H3
- Val @1x: n=131 expR=0.0037 pf=1.15 sharpe=0.040
- 2x cost: n=131 expR=0.0016 pf=1.06 -> OK
- Sensitivity: 3/4 neighbors scored, 67% positive, median expR=0.0003 -> OK
- Bonferroni: p=0.32354 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=2.72, kurt=19.83) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|crypto|1day|H=3,L=12,k=2,mode=lo|c1.0`
- Rule: `xs_mom(H=3,L=12,k=2,mode=lo)` · crypto · 1day · H3
- Val @1x: n=131 expR=0.0095 pf=1.36 sharpe=0.088
- 2x cost: n=131 expR=0.0074 pf=1.27 -> OK
- Sensitivity: 3/4 neighbors scored, 100% positive, median expR=0.0088 -> OK
- Bonferroni: p=0.15692 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=3.35, kurt=21.50) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_majors|4h|H=3,L=12,k=1,mode=ls|c1.0`
- Rule: `xs_mom(H=3,L=12,k=1,mode=ls)` · forex_majors · 4h · H3
- Val @1x: n=331 expR=0.0002 pf=1.14 sharpe=0.045
- 2x cost: n=331 expR=0.0000 pf=1.03 -> FAIL
- Sensitivity: 4/4 neighbors scored, 75% positive, median expR=0.0001 -> OK
- Bonferroni: p=0.20648 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.31, kurt=5.64) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_majors|4h|H=3,L=12,k=1,mode=lo|c1.0`
- Rule: `xs_mom(H=3,L=12,k=1,mode=lo)` · forex_majors · 4h · H3
- Val @1x: n=331 expR=0.0001 pf=1.09 sharpe=0.030
- 2x cost: n=331 expR=-0.0001 pf=0.91 -> FAIL
- Sensitivity: 4/4 neighbors scored, 0% positive, median expR=-0.0001 -> FAIL
- Bonferroni: p=0.29260 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.27, kurt=4.87) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_majors|4h|H=3,L=12,k=2,mode=ls|c1.0`
- Rule: `xs_mom(H=3,L=12,k=2,mode=ls)` · forex_majors · 4h · H3
- Val @1x: n=331 expR=0.0002 pf=1.17 sharpe=0.052
- 2x cost: n=331 expR=0.0001 pf=1.04 -> OK
- Sensitivity: 4/4 neighbors scored, 75% positive, median expR=0.0002 -> OK
- Bonferroni: p=0.17206 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.42, kurt=7.04) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_majors|4h|H=3,L=12,k=2,mode=lo|c1.0`
- Rule: `xs_mom(H=3,L=12,k=2,mode=lo)` · forex_majors · 4h · H3
- Val @1x: n=331 expR=0.0001 pf=1.19 sharpe=0.060
- 2x cost: n=331 expR=-0.0000 pf=0.97 -> FAIL
- Sensitivity: 4/4 neighbors scored, 0% positive, median expR=-0.0001 -> FAIL
- Bonferroni: p=0.13750 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.38, kurt=5.82) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_majors|4h|H=10,L=48,k=2,mode=lo|c1.0`
- Rule: `xs_mom(H=10,L=48,k=2,mode=lo)` · forex_majors · 4h · H10
- Val @1x: n=100 expR=0.0001 pf=1.07 sharpe=0.025
- 2x cost: n=100 expR=-0.0001 pf=0.93 -> FAIL
- Sensitivity: 1/4 neighbors scored, 100% positive, median expR=0.0001 -> OK
- Bonferroni: p=0.40129 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.26, kurt=3.12) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_majors|1day|H=3,L=12,k=1,mode=ls|c1.0`
- Rule: `xs_mom(H=3,L=12,k=1,mode=ls)` · forex_majors · 1day · H3
- Val @1x: n=327 expR=0.0006 pf=1.10 sharpe=0.034
- 2x cost: n=327 expR=0.0003 pf=1.05 -> OK
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=-0.0001 -> FAIL
- Bonferroni: p=0.26933 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.59, kurt=7.94) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_majors|1day|H=3,L=12,k=1,mode=lo|c1.0`
- Rule: `xs_mom(H=3,L=12,k=1,mode=lo)` · forex_majors · 1day · H3
- Val @1x: n=327 expR=0.0005 pf=1.13 sharpe=0.046
- 2x cost: n=327 expR=0.0002 pf=1.05 -> OK
- Sensitivity: 4/4 neighbors scored, 75% positive, median expR=0.0002 -> OK
- Bonferroni: p=0.20275 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.53, kurt=5.30) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_majors|1day|H=3,L=12,k=2,mode=ls|c1.0`
- Rule: `xs_mom(H=3,L=12,k=2,mode=ls)` · forex_majors · 1day · H3
- Val @1x: n=327 expR=0.0006 pf=1.12 sharpe=0.040
- 2x cost: n=327 expR=0.0003 pf=1.06 -> OK
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=0.0000 -> FAIL
- Bonferroni: p=0.23474 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.34, kurt=7.63) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_majors|1day|H=3,L=12,k=2,mode=lo|c1.0`
- Rule: `xs_mom(H=3,L=12,k=2,mode=lo)` · forex_majors · 1day · H3
- Val @1x: n=327 expR=0.0004 pf=1.13 sharpe=0.044
- 2x cost: n=327 expR=0.0001 pf=1.02 -> OK
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=-0.0000 -> FAIL
- Bonferroni: p=0.21312 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.20, kurt=5.25) -> FAIL
- **VERDICT: REJECT (parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_crosses|1day|H=5,L=24,k=1,mode=lo|c1.0`
- Rule: `xs_mom(H=5,L=24,k=1,mode=lo)` · forex_crosses · 1day · H5
- Val @1x: n=200 expR=0.0003 pf=1.06 sharpe=0.023
- 2x cost: n=200 expR=-0.0005 pf=0.89 -> FAIL
- Sensitivity: 4/4 neighbors scored, 50% positive, median expR=0.0002 -> FAIL
- Bonferroni: p=0.37249 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.70, kurt=6.08) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_crosses|1day|H=10,L=48,k=1,mode=ls|c1.0`
- Rule: `xs_mom(H=10,L=48,k=1,mode=ls)` · forex_crosses · 1day · H10
- Val @1x: n=100 expR=0.0004 pf=1.03 sharpe=0.012
- 2x cost: n=100 expR=-0.0009 pf=0.92 -> FAIL
- Sensitivity: 3/4 neighbors scored, 33% positive, median expR=-0.0016 -> FAIL
- Bonferroni: p=0.45224 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.000 (skew=0.79, kurt=4.67) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_crosses|1day|H=10,L=48,k=1,mode=lo|c1.0`
- Rule: `xs_mom(H=10,L=48,k=1,mode=lo)` · forex_crosses · 1day · H10
- Val @1x: n=100 expR=0.0016 pf=1.24 sharpe=0.078
- 2x cost: n=100 expR=0.0003 pf=1.04 -> OK
- Sensitivity: 3/4 neighbors scored, 67% positive, median expR=0.0012 -> OK
- Bonferroni: p=0.21770 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.002 (skew=0.64, kurt=4.85) -> FAIL
- **VERDICT: REJECT (fails Bonferroni, fails Deflated Sharpe)**

### `xs_mom|forex_crosses|1day|H=10,L=48,k=2,mode=lo|c1.0`
- Rule: `xs_mom(H=10,L=48,k=2,mode=lo)` · forex_crosses · 1day · H10
- Val @1x: n=100 expR=0.0006 pf=1.10 sharpe=0.036
- 2x cost: n=100 expR=-0.0007 pf=0.88 -> FAIL
- Sensitivity: 3/4 neighbors scored, 0% positive, median expR=-0.0004 -> FAIL
- Bonferroni: p=0.35942 vs 0.000379 -> FAIL
- Deflated Sharpe: DSR=0.001 (skew=0.17, kurt=3.92) -> FAIL
- **VERDICT: REJECT (dies at 2x cost, parameter-fragile, fails Bonferroni, fails Deflated Sharpe)**

## Summary

- 25 base-gate PASS -> **0 candidate(s)** after the full gauntlet.
- Nothing survived. No candidate is promoted — correct, disciplined outcome.
