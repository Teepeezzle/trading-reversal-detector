# PROJECT_STATE — Short-Horizon Signal Research

> Read this file first every session. Resume from "Next", state a 3-line plan, then work.

**Mission:** rules-based, out-of-sample-validated, cost-aware signal system for
INTRADAY (open→same-session close) and SHORT SWING (≤5 trading days) across
Forex, Metals (XAU/XAG), Oil (WTI/Brent), and Crypto (BTC/ETH/liquid alts).
Success = documented edge net of costs + a daily top-5 actionable list.

**Current phase:** PHASE 3 — engine + SWEEP + T-303 robustness gauntlet all built & validated.
Phases 0–2 done. The sweep (research-sweep) landed on main and was dispatched to populate
HYPOTHESIS_REGISTRY; T-303 (jobs/robustness.py + src/mtc.py + research-robustness workflow) is
ready to run the moment the registry has rows. Next: confirm the sweep produced results, then
dispatch research-robustness to promote any survivors into CANDIDATES.md.

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

## Done (Phase 3 engine + sweep + T-303)
- Engine: `src/backtest.py`, `costs.py`, `src/factors.py` (shared), `jobs/single_factor.py`.
- Sweep: `jobs/sweep.py` (idempotent/resumable) + `research-sweep.yml` (lands results as an auto PR).
  Merged to main (PR #7) and dispatched. Validated on real lake: pooled 91–279 trades, 0 PASS.
- T-303 gauntlet: `jobs/robustness.py` + `src/mtc.py` (Bonferroni + Deflated Sharpe, stdlib-only) +
  `research-robustness.yml`. 2×-cost + sensitivity + MTC; survivors → CANDIDATES.md, report →
  ROBUSTNESS.md (D-012). Validated on a synthetic PASS (correctly rejected on every statistical gate).
- Findings: D-011 (pool per class), D-012 (promotion gate). Engine refuses to bless noise.

## Next
1. **Confirm the sweep populated HYPOTHESIS_REGISTRY** (research-sweep run / its auto-PR). The sweep
   depends on the data-refresh having warmed the lake cache first; if the cache was empty it no-ops
   cleanly ("nothing to sweep") — in that case let research-data-refresh run first, then re-dispatch.
2. **Dispatch research-robustness** (T-303) on the populated registry → promotes survivors to
   CANDIDATES.md. Expected early result: 0 survivors (honest). Holdout stays sealed until the very end.
3. If/when candidates exist → **Phase 4** (combinations/regimes) then **Phase 5** (OOS/walk-forward).

## Open questions
- Exact Twelve Data symbols for WTI/Brent on the free plan (verify on first pull).
- How deep is Twelve Data free 15m/1h history in practice? (measure, record).
- Crypto alt universe + any delisting handling we can approximate.

_Last updated: 2026-10-02 (session 2 — sweep merged + T-303 built)._
