# POWER-BOOST confirmation — regime-gated breakout (Phase 4.5)

Pre-registered test of **donch_brk(n=20) & {gate}**, long, swing, under data configs that add trades per hypothesis.

- Confirmation cells with n>=100 (Bonferroni N): **13**  -> p < 0.003846
- DSR deflation benchmark (fixed at Phase-4 expected-max-Sharpe): SR* = **0.17** · DSR>0.95
- Validation set only; holdout sealed. Each instrument carries its own asset-class cost.

| gate | config | n | expR | PF | Sharpe | 2x expR | p | DSR | verdict |
|---|---|--:|--:|--:|--:|--:|--:|--:|:--|
| vol_hi | crypto@1h (phase-4 baseline) | 115 | 0.2670 | 1.44 | 0.177 | 0.1253 | 0.02884 | 0.530 | reject: p, DSR |
| vol_hi | crypto@15m (Move2) | 133 | 0.4220 | 1.77 | 0.281 | 0.2425 | 0.00060 | 0.895 | reject: DSR |
| vol_hi | crypto@4h | 82 | — | — | — | — | — | — | THIN (n<100) |
| vol_hi | allclass@1h (Move1) | 421 | -0.0474 | 0.93 | -0.033 | -0.1779 | 0.75083 | 0.000 | reject: cost, p, DSR |
| vol_hi | allclass@15m (Move1+2) | 323 | -0.0775 | 0.90 | -0.053 | -0.2788 | 0.82959 | 0.000 | reject: cost, p, DSR |
| ny | crypto@1h (phase-4 baseline) | 130 | 0.2694 | 1.44 | 0.177 | 0.0850 | 0.02179 | 0.532 | reject: p, DSR |
| ny | crypto@15m (Move2) | 112 | 0.3436 | 1.58 | 0.224 | 0.1337 | 0.00888 | 0.713 | reject: p, DSR |
| ny | crypto@4h | 147 | -0.5367 | 0.36 | -0.499 | -0.5995 | 1.00000 | 0.000 | reject: cost, p, DSR |
| ny | allclass@1h (Move1) | 436 | -0.0976 | 0.87 | -0.068 | -0.2410 | 0.92218 | 0.000 | reject: cost, p, DSR |
| ny | allclass@15m (Move1+2) | 245 | -0.1306 | 0.84 | -0.086 | -0.3754 | 0.91087 | 0.000 | reject: cost, p, DSR |
| adx_hi25 | crypto@1h (phase-4 baseline) | 106 | 0.1782 | 1.28 | 0.119 | 0.0262 | 0.11025 | 0.298 | reject: p, DSR |
| adx_hi25 | crypto@15m (Move2) | 124 | 0.1766 | 1.27 | 0.117 | -0.0259 | 0.09631 | 0.276 | reject: cost, p, DSR |
| adx_hi25 | crypto@4h | 79 | — | — | — | — | — | — | THIN (n<100) |
| adx_hi25 | allclass@1h (Move1) | 390 | -0.0768 | 0.90 | -0.053 | -0.2093 | 0.85237 | 0.000 | reject: cost, p, DSR |
| adx_hi25 | allclass@15m (Move1+2) | 300 | -0.1520 | 0.81 | -0.102 | -0.4041 | 0.96136 | 0.000 | reject: cost, p, DSR |

## Verdict

**0 configs cleared the bar.** More data (Moves 1–2) alone was not enough.
- Best: vol_hi · crypto@15m (Move2) — n=133, Sharpe=0.281, p=0.00060 (need <0.003846), DSR=0.895 (need >0.95).
- Next lever: widen the crypto alt universe (Move 3, needs a CI data-refresh) or proceed to Phase-5 walk-forward on the best-powered config.
