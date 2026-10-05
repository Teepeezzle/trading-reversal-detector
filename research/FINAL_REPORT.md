# FINAL REPORT — Short-Horizon Signal Research Program

_Concluded 2026-10-05. Author: automated research program (repo = state, GitHub Actions = off-peak
compute). This is the program's terminal deliverable._

---

## 1. Verdict (plainly)

**No reliable short-horizon trading edge was found.** Across **2,479 tested hypotheses** spanning every
structurally-distinct approach we could implement, **zero survived the full robustness gauntlet.**
`CANDIDATES.md` is empty. Under the program's constraints — **$0 / free data**, net of realistic costs,
strict no-look-ahead, and multiple-testing correction — **no robust intraday or short-swing edge exists
in this data for these instruments.**

This is a **negative result, and it is the honest one.** It is more valuable than a system that looks
good in a backtest and fails live: the entire gauntlet was built to refuse to bless noise, and it did.
The sealed holdout was **never touched** — so if a credible candidate ever emerges (e.g. from paid data
or a longer horizon), one clean out-of-sample confirmation remains available.

---

## 2. Scope

- **Mission:** a rules-based, out-of-sample-validated, cost-aware signal system for **intraday**
  (open→same-session close) and **short swing** (≤5 trading days).
- **Universe:** Forex majors + crosses, Metals (XAU/XAG), Oil (WTI/Brent), Crypto (BTC/ETH + liquid
  alts). Timeframes 15m / 1h / 4h / 1D (5m out of scope — not achievable free).
- **Constraint:** **$0 budget, free data only** (Twelve Data / yfinance / HistData / committed Bybit
  funding / FRED / EIA / Alpha Vantage sentiment). Read-only, paper only; no live keys, no live orders.

## 3. What makes a verdict here trustworthy (the gauntlet)

A hypothesis is only a *candidate* if it clears **all** of the following. These are the guardrails, not
decoration — they are why a null result here means something.

- **No look-ahead.** Every value carries `available_at`; entries at next-bar open; news/sentiment joined
  as-of with a per-type **staleness cap** (stale → excluded, never carried).
- **Net of realistic costs.** Spread + commission + slippage + overnight financing, per asset class.
- **≥100 trades** on the validation set before any judgement (thin cells are reported but never judged).
- **60/20/20 split**; the **holdout is sealed and never touched**.
- **Benchmarks:** must beat **buy-and-hold** and **random-entry with matched stop/target**.
- **Robustness (T-303):** survive **2× transaction cost**, **parameter sensitivity** (a plateau, not a
  spike), **Bonferroni** (one-sided p < α/N over N valid tests), and the **Deflated Sharpe Ratio**
  (Bailey & López de Prado — deflated for the number of trials and for skew/fat tails).
- Judged on **validation only**. Abandon anything that dies at 2× cost, fails the holdout, or depends on
  a single instrument, date range, or parameter.

## 4. Results by phase

| Phase | Approach | Hypotheses | Base-gate PASS | Survived gauntlet |
|---|---|--:|--:|--:|
| 3 | Single technical factors (RSI/Donchian/EMA/… pooled per class) | 220 | 17 | **0** |
| 4 | Combinations × regime gates (ADX / trend / vol / session) | 119 | 21 | **0** |
| 4.5 | Power boosts (cross-class, crypto 15m, universe widening) | — | — | **0** (edge was small-sample luck) |
| 5 | New factor families (BB/z-score/stoch/ROC… on 15m–1D) | 540 | 58 | **0** |
| 6 | Cross-sectional ranking (long top-k / short bottom-k) | 320 | 25 | **0** |
| 7 | Deep FX/metals from HistData (~21 mo, 5–8× depth) | 480 | 19 | **0** |
| 8 | Crypto alt-data (perp funding / basis) | 60 | 2 | **0** |
| 9 | News gates / regime tags (FRED macro + EIA oil) | 380 | 73 | **0** |
| 10 | Alpha Vantage news-sentiment factor (3.75-yr archive) | 360 | 16 | **0** |
| **Total** | | **2,479** | **231** | **0** |

(Phase 1–2 = data + indicator foundation. Phase 11 `fund_direction` = registered but **not run** — the
one remaining structurally-distinct idea; see §7.)

## 5. The near-misses — and why none held

231 configurations passed the base validation gate (≥100 trades, positive net expectancy, beat random);
**none** survived multiple-testing correction. The strongest base-gate results of the whole program:

| phase | cell | n | expectancy | val Sharpe | outcome |
|---|---|--:|--:|--:|---|
| 10 | crypto · 4h · intraday · `sent_mom` | 238 | +0.36R | 0.340 | died under Bonferroni + DSR |
| 10 | crypto · 4h · swing · `sent_mom` | 211 | +0.43R | 0.294 | died under Bonferroni + DSR |
| 5 | oil · 1h · swing · `stoch_rev` | 112 | +0.37R | 0.249 | died under MTC |
| 3 | oil · 1h · swing · `rsi_rev` | 122 | +0.36R | 0.242 | died under MTC |
| 4 | crypto · 1h · intraday · `donch_brk`+`vol_hi` | 104 | +0.29R | 0.238 | died under MTC |

Two honest observations:
- **News-sentiment was the *best* naive family** (the top two base-gate Sharpes, ~0.34/0.29, on real
  n≈200+). It still did not clear the gauntlet — the correction for ~55 valid trials deflates a 0.34
  Sharpe below significance. A real signal would have cleared it; this didn't.
- **Earlier "near-misses" were small-sample inflation.** Phase 7 (deep HistData) specifically *refuted*
  the "we're under-powered" hypothesis: with 5–8× the data, the promising shallow-sample rules regressed
  to Sharpe ≈0.01 / p≈0.42. The two-zone DRS and Predictive-Range refinements (scanner side) looked
  positive at n≈10 and **inverted** a week later. Thin cells lie; the gauntlet is right to ignore them.

## 6. What this does and does not say

- **It says:** naive and moderately-engineered rules, on free OHLCV + free macro/sentiment/funding, net
  of cost, do not yield a short-horizon edge that survives honest correction for these instruments.
- **It does not say** no edge exists anywhere. The result is bounded by the constraints:
  - **$0 / free data** — no tick data, no true order-flow, no survivorship-free universe, no licensed
    consensus forecasts; non-US central-bank data was not even reachable keyless.
  - **Short horizon** — intraday / ≤5-day only; longer horizons were out of scope.
  - **This gauntlet** — deliberately strict; it optimises for *surviving live*, not for backtest optics.

## 7. What would be needed to change the answer (honest paths)

1. **Paid / higher-quality data** (budget decision): tick & order-flow, point-in-time fundamentals with
   consensus, a survivorship-free universe. Most retail "edges" live in data retail can't see free.
2. **A different horizon or objective** — trend-following over weeks/months (the breakout basket showed a
   real but *thin, de-biased* PF ≈1.05–1.10 on trending classes — outside this program's intraday scope),
   or portfolio/vol-targeting rather than per-trade signals.
3. **Forward evidence over time** — the parallel shadow-test pattern (built for the board's fundamentals)
   accumulates a real out-of-sample sample instead of re-mining history; the only honest way to validate
   a thin-cell effect without paying for data.
4. **Phase 11 — `fund_direction`** (registered, pending): the board's per-asset fundamental-trend factor,
   to be judged with **pooled estimation** across instruments. It is the last untested structural idea.
   Given the record, the prior is another 0 — but it is available if you want the stone turned.

## 8. Reproducibility & state

- Every hypothesis is in `HYPOTHESIS_REGISTRY.csv` (2,481 rows) with its stats, benchmarks, and verdict.
- Decisions and their rationale are in `DECISIONS.md` (D-001 … D-035).
- The gauntlet is `jobs/robustness.py` + `src/mtc.py`; sweeps under `jobs/`; data provenance in
  `DATA_MANIFEST.md`. Off-peak jobs ran in GitHub Actions; the AV sentiment archive is complete
  (2023-01 → 2026-10, committed).
- **Holdout: never touched.** Available for exactly one clean confirmation if a credible candidate ever
  arises.

## 9. Recommendation

**Conclude the free-data short-horizon search.** Do not deploy anything — there is nothing that earned
it. Keep the infrastructure (it is reusable and cheap): if the budget or horizon changes, the registry,
the gauntlet, and the sealed holdout are ready to test the next idea properly. The most valuable output
of this program is the discipline that produced an honest "no," not a fabricated "yes."

_Off-peak pipeline: with the search concluded, the nightly sweeps / data-refresh and the 3×/day AV
harvester have no remaining work — they should be wound down to stop consuming Actions minutes (the
backfill is complete; only a 1×/day refresh is needed if the archive is to be kept current at all)._
