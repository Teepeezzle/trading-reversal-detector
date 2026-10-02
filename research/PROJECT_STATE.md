# PROJECT_STATE — Short-Horizon Signal Research

> Read this file first every session. Resume from "Next", state a 3-line plan, then work.

**Mission:** rules-based, out-of-sample-validated, cost-aware signal system for
INTRADAY (open→same-session close) and SHORT SWING (≤5 trading days) across
Forex, Metals (XAU/XAG), Oil (WTI/Brent), and Crypto (BTC/ETH/liquid alts).
Success = documented edge net of costs + a daily top-5 actionable list.

**Current phase:** PHASE 3 — engine + SWEEP built & validated (jobs/sweep.py idempotent/resumable;
research-sweep nightly workflow lands registry as a PR). Phases 0–2 done. Next: run the sweep in
CI to populate HYPOTHESIS_REGISTRY, then T-303 (2×-cost + sensitivity + multiple-testing correction).

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

## Done (Phase 3 engine + sweep)
- Engine: `src/backtest.py`, `costs.py`, `src/factors.py` (shared), `jobs/single_factor.py`.
- Sweep: `jobs/sweep.py` (idempotent/resumable) + `.github/workflows/research-sweep.yml` (lands
  results as an auto PR). Validated on real lake: pooled 91–279 trades, 0 PASS (naive = negative).
- Findings: D-011 (pool per class). Engine refuses to bless noise — honest "no edge yet" result.

## Next
1. **Run the sweep in CI** (dispatch research-sweep) to populate HYPOTHESIS_REGISTRY across the grid
   (~220 hypotheses; resumes nightly). Needs the "Actions can create PRs" repo setting for the PR step.
2. **T-303** on the populated registry: 2×-cost re-run on anything positive, parameter sensitivity
   (±1–2 around winners), multiple-testing correction (Deflated Sharpe / Bonferroni), # hypotheses
   reported. Only then does anything reach CANDIDATES.md. Holdout stays sealed until the very end.

## Open questions
- Exact Twelve Data symbols for WTI/Brent on the free plan (verify on first pull).
- How deep is Twelve Data free 15m/1h history in practice? (measure, record).
- Crypto alt universe + any delisting handling we can approximate.

_Last updated: 2026-10-01 (session 1)._
