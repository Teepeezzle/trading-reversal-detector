# PROJECT_STATE — Short-Horizon Signal Research

> Read this file first every session. Resume from "Next", state a 3-line plan, then work.

**Mission:** rules-based, out-of-sample-validated, cost-aware signal system for
INTRADAY (open→same-session close) and SHORT SWING (≤5 trading days) across
Forex, Metals (XAU/XAG), Oil (WTI/Brent), and Crypto (BTC/ETH/liquid alts).
Success = documented edge net of costs + a daily top-5 actionable list.

**Current phase:** PHASE 3 COMPLETE — swept the full grid (220 hypotheses) and ran the T-303
gauntlet end-to-end in CI. **Result: 0 candidates.** 17 base-gate PASSes, but none cleared the
multiple-testing bar (78 valid tests → Bonferroni p<0.00064; DSR>0.95 vs SR*=0.33). Honest, expected.
Next: **Phase 4** — combine the strongest single-factor LEADS (below) with filters/regimes, since
no standalone factor is deployable. Holdout still sealed.

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

## Phase-3 LEADS (survived 2× cost + parameter sensitivity; failed only the N=78 MTC)
Not candidates, but the raw material for Phase 4. Clear theme: **oil mean-reversion**.
- `rsi_rev(n=7,os=30)` **oil 1h→swing** — val expR **+0.360R**, PF 1.66, 2× cost +0.296R (strongest)
- `zscore_rev(n=20,z=2.0)` oil 1h→swing — +0.277R, PF 1.49
- `rsi_rev(n=7,os=30)` oil 1h→intraday — +0.189R, PF 1.54
- `donch_brk(n=55)` crypto 1h→intraday — +0.163R, PF 1.35
- `zscore_rev(n=50,z=2.0)` forex_majors 1h→swing — +0.165R, PF 1.26
- `donch_brk(n=20)` forex_majors 4h→swing — +0.118R, PF 1.21 · `donch_brk(n=20)` metals 1h→intraday — +0.093R
Full per-candidate report: `research/ROBUSTNESS.md`. All 220 rows: `HYPOTHESIS_REGISTRY.csv`.

## Next — PHASE 4 (combinations / regimes)
1. **T-401** Take the leads above and add a confirming factor or regime gate (trend/range via ADX or
   SMA200 slope; vol hi/lo via ATR%; session). Hypothesis: a filter lifts the oil/crypto mean-reversion
   edge enough to clear MTC. Register each combo in HYPOTHESIS_REGISTRY (phase 4), re-run T-303.
2. Keep pooling per asset class for sample size (D-011). Costs/no-lookahead/benchmarks unchanged.
3. Only a Phase-4 survivor of the full gauntlet → CANDIDATES.md → **Phase 5** (walk-forward, then the
   sealed holdout touched ONCE) → **Phase 6** (4-week forward paper) → **Phase 7** (deploy to scanner).

## Open questions
- Exact Twelve Data symbols for WTI/Brent on the free plan (verify on first pull).
- How deep is Twelve Data free 15m/1h history in practice? (measure, record).
- Crypto alt universe + any delisting handling we can approximate.

_Last updated: 2026-10-02 (session 2 — Phase 3 complete: 220 swept, T-303 run, 0 candidates, leads logged)._
