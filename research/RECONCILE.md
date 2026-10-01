# RECONCILE — Twelve Data vs yfinance (T-102)
_Run 2026-10-01 15:36 UTC, 1h close, inner-join on bar time._

Tolerance: FX/gold median<0.10% & p95<0.50%; crypto median<0.25% & p95<1.0%.

| pair    | status   |    n |   median_pct |   p95_pct |   max_pct | tol              |
|:--------|:---------|-----:|-------------:|----------:|----------:|:-----------------|
| EUR/USD | PASS     | 3528 |       0.0269 |    0.0385 |     0.26  | med<0.1/p95<0.5  |
| XAU/USD | FAIL     | 3303 |       0.4641 |    1.3636 |     1.666 | med<0.1/p95<0.5  |
| BTC/USD | PASS     | 4965 |       0.0581 |    0.1542 |     0.409 | med<0.25/p95<1.0 |

**Interpretation:** FX & crypto are like-for-like (spot vs spot) and agree to <0.16% p95 → the mixed TD+yfinance lake is validated. The XAU/USD 'FAIL' is the **spot-vs-futures basis** (TD XAU/USD = spot gold; yfinance GC=F = gold futures, ~0.46% apart) — not a data error. NB: gold is spot (TD); silver/oil are futures (yfinance). Acceptable for short-horizon technical signals; roll/cost handled per instrument.
