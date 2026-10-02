# PROJECT_STATE — Short-Horizon Signal Research

> Read this file first every session. Resume from "Next", state a 3-line plan, then work.

**Mission:** rules-based, out-of-sample-validated, cost-aware signal system for
INTRADAY (open→same-session close) and SHORT SWING (≤5 trading days) across
Forex, Metals (XAU/XAG), Oil (WTI/Brent), and Crypto (BTC/ETH/liquid alts).
Success = documented edge net of costs + a daily top-5 actionable list.

**Current phase:** PHASE 3 — backtest engine BUILT & VALIDATED (pooled single-factor, no-lookahead,
net-of-cost, buy-hold + random-entry benchmarks, 60/20/20 split, ≥100-trade gate). Phases 0–2 done.
Next: systematic sweep across rules × params × classes × horizons + multiple-testing correction.

---

## Decisions locked (see DECISIONS.md)
- **Data layer (off-peak):** Twelve Data free API (portable, runs in Actions) as primary;
  yfinance as a free cross-check. Free limits: **8 req/min, 800 req/day** — hard-enforced.
- **Repo:** this repo (`trading-reversal-detector`), all research under `research/`,
  work lands via `research/*` branch → PR → user merges. **Never push to main.**
- **Budget:** **$0 — free tiers only.** Fail loudly + log to BLOCKERS.md before exceeding.

## Honest feasibility verdict (see DATA_MANIFEST.md)
- **5m deep history:** not achievable on free tiers → **5m is out of scope** for now
  (Twelve Data free 5min history is shallow; revisit only if budget changes).
- **Survivorship-free universe:** not available free → documented **known limitation**;
  universe = currently-listed liquid instruments only.
- **Working timeframes:** 15m, 1h, 4h, 1D. Intraday depth is the binding constraint.
- **Data ≠ broker feed:** Twelve Data/yfinance ≠ OANDA fills — all costs modelled, and
  live/forward reconciliation against the user's own charts stays mandatory.

---

## Done (Phase 0 → 1 kickoff)
- Architecture defined (3 planes: repo state / Actions off-peak / interactive MCP). See README.md.
- Persistent-state files created: PROJECT_STATE, DECISIONS, BLOCKERS, DATA_MANIFEST,
  HYPOTHESIS_REGISTRY.csv, CANDIDATES, QUEUE, DAILY_SIGNALS.
- Portable data layer written: `research/src/twelvedata_client.py` (rate+budget limited),
  `research/jobs/data_refresh.py` (idempotent lake builder), `research/config.yaml` (universe).
- Off-peak workflow written: `.github/workflows/research-data-refresh.yml` (session-aware).

## Status
- **Phase 1 COMPLETE + reconciled:** 27 instruments × 4 TFs in the lake (TD FX/gold/crypto +
  yfinance silver/oil). Sources agree (FX/crypto PASS; gold = spot/futures basis, D-010).
- **Phase 2 done:** indicator catalogue (PHASE2_INDICATORS.md) + portable `research/src/indicators.py`.
- Bigdata.com assessed → interactive macro-event overlay only, MCP-ONLY/PAYG (D-009). No open blockers.

## Done this session (Phase 3 engine)
- `research/src/backtest.py` (simulate/stats/split/benchmarks), `costs.py` (per-class net costs),
  `jobs/single_factor.py` (pooled tester, --symbol ALL). Verified on real lake data.
- Finding (D-011): pool a rule across the asset class for sample size; no naive factor passed.

## Next — PHASE 3 sweep
1. `research/jobs/sweep.py` — loop rules × params × asset-classes × horizons × TFs (from QUEUE),
   append each result row to HYPOTHESIS_REGISTRY.csv. Idempotent / resumable batches.
2. `research-sweep` workflow (nightly), matrix over asset classes; Actions cache for /data.
3. On the batch: apply **2× cost** re-run on anything positive, **parameter sensitivity**
   (±1–2 around any winner), and **multiple-testing correction** (Deflated Sharpe / Bonferroni);
   report how many hypotheses were tested. Judge PASS only on validation; holdout stays sealed.

## Open questions
- Exact Twelve Data symbols for WTI/Brent on the free plan (verify on first pull).
- How deep is Twelve Data free 15m/1h history in practice? (measure, record).
- Crypto alt universe + any delisting handling we can approximate.

_Last updated: 2026-10-01 (session 1)._
