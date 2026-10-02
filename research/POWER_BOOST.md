# POWER-BOOST confirmation — regime-gated breakout (Phase 4.5)

Pre-registered test of **donch_brk(n=20) & {gate}**, long, swing, under data configs that add trades per hypothesis.

- Confirmation cells with n>=100 (Bonferroni N): **15**  -> p < 0.003333
- DSR deflation benchmark (fixed at Phase-4 expected-max-Sharpe): SR* = **0.17** · DSR>0.95
- Validation set only; holdout sealed. Each instrument carries its own asset-class cost.

| gate | config | n | expR | PF | Sharpe | 2x expR | p | DSR | verdict |
|---|---|--:|--:|--:|--:|--:|--:|--:|:--|
| vol_hi | crypto@1h (phase-4 baseline) | 245 | 0.1360 | 1.21 | 0.091 | -0.0014 | 0.07717 | 0.105 | reject: cost, p, DSR |
| vol_hi | crypto@15m (Move2) | 284 | 0.2432 | 1.39 | 0.160 | 0.0499 | 0.00351 | 0.433 | reject: p, DSR |
| vol_hi | crypto@4h | 156 | -0.4937 | 0.41 | -0.429 | -0.5547 | 1.00000 | 0.000 | reject: cost, p, DSR |
| vol_hi | allclass@1h (Move1) | 555 | -0.0232 | 0.97 | -0.016 | -0.1544 | 0.64689 | 0.000 | reject: cost, p, DSR |
| vol_hi | allclass@15m (Move1+2) | 480 | -0.0230 | 0.97 | -0.015 | -0.2272 | 0.62878 | 0.000 | reject: cost, p, DSR |
| ny | crypto@1h (phase-4 baseline) | 233 | 0.1078 | 1.16 | 0.072 | -0.0591 | 0.13588 | 0.066 | reject: cost, p, DSR |
| ny | crypto@15m (Move2) | 214 | 0.1840 | 1.28 | 0.120 | -0.0198 | 0.03959 | 0.231 | reject: cost, p, DSR |
| ny | crypto@4h | 270 | -0.3957 | 0.51 | -0.327 | -0.4655 | 1.00000 | 0.000 | reject: cost, p, DSR |
| ny | allclass@1h (Move1) | 538 | -0.0955 | 0.87 | -0.066 | -0.2393 | 0.93710 | 0.000 | reject: cost, p, DSR |
| ny | allclass@15m (Move1+2) | 347 | -0.1006 | 0.87 | -0.067 | -0.3338 | 0.89400 | 0.000 | reject: cost, p, DSR |
| adx_hi25 | crypto@1h (phase-4 baseline) | 217 | 0.0128 | 1.02 | 0.009 | -0.1357 | 0.44726 | 0.009 | reject: cost, p, DSR |
| adx_hi25 | crypto@15m (Move2) | 240 | 0.1058 | 1.16 | 0.071 | -0.0884 | 0.13568 | 0.061 | reject: cost, p, DSR |
| adx_hi25 | crypto@4h | 163 | -0.2297 | 0.69 | -0.176 | -0.2971 | 0.98768 | 0.000 | reject: cost, p, DSR |
| adx_hi25 | allclass@1h (Move1) | 504 | -0.0865 | 0.88 | -0.060 | -0.2221 | 0.91101 | 0.000 | reject: cost, p, DSR |
| adx_hi25 | allclass@15m (Move1+2) | 416 | -0.0952 | 0.88 | -0.064 | -0.3297 | 0.90411 | 0.000 | reject: cost, p, DSR |

## Verdict

**0 configs cleared the bar.** More data (Moves 1–2) alone was not enough.
- Best: vol_hi · crypto@15m (Move2) — n=284, Sharpe=0.160, p=0.00351 (need <0.003333), DSR=0.433 (need >0.95).
- Next lever: widen the crypto alt universe (Move 3, needs a CI data-refresh) or proceed to Phase-5 walk-forward on the best-powered config.
