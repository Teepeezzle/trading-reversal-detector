# PROJECT_STATE — Short-Horizon Signal Research

> Read this file first every session. Resume from "Next", state a 3-line plan, then work.

**Mission:** rules-based, out-of-sample-validated, cost-aware signal system for
INTRADAY (open→same-session close) and SHORT SWING (≤5 trading days) across
Forex, Metals (XAU/XAG), Oil (WTI/Brent), and Crypto (BTC/ETH/liquid alts).
Success = documented edge net of costs + a daily top-5 actionable list.

**Current phase:** PHASE 6 COMPLETE (D-019) — cross-sectional ran in CI: 320 configs → 25 base-PASS →
T-303 phase=6 (N=132) → **0 candidates** (best crypto 15m momentum, Sharpe 0.078, p=0.22, DSR 0.002).
**PROGRAM RESULT: ~1,200 hypotheses across Phases 3–6, every structurally-distinct approach, 0
deployable edges.** No robust short-horizon technical edge exists under the $0/free-data constraints
with this gauntlet. Holdout NEVER touched. **Phase 7 (reopen for ~$0) — user chose Both, A first.** T-405 scoped (DATA_OPTIONS.md).
**Step A BUILT (T-406):** deep FX/metals from **HistData** (free M1 → 15m/1h/4h/1D, years of depth) —
`src/histdata_client.py` (validated live) + `jobs/histdata_refresh.py` + `research-histdata-refresh`
workflow. (Switched Dukascopy→HistData: Dukascopy ticks are 1 file/hour ≈ unusable in Actions;
HistData = monthly ZIPs. Oil not on HistData → stays yfinance.) NEXT: dispatch the deep refresh (3y)
→ verify depth → `deep_resweep` (re-run phase-3 + phase-5 grids on deep FX/metals as phase 7) →
robustness phase=7 — the honest retest of whether edges were real-but-under-sampled. Then **Step B**
(T-407): Binance deep crypto + funding/OI/basis alt-data families.
Next: run research-combo-sweep in CI → merge results → research-robustness `phase=4`; then Phase 5.

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

## Done (Phase 4 / T-401 — combos × gates) — D-013
- `jobs/combo_sweep.py` (leads × `factors.GATES`, idempotent/resumable), `src/factors.py` gate
  catalogue + gated `run_one`/`evaluate`, `jobs/robustness.py` generalised (`--phase`, parses
  `rule+gate`, gated pooled_val), `.github/workflows/research-combo-sweep.yml`,
  `research-robustness.yml` gains a `phase` input.
- Local preview (real lake): 119 combos → 21 base-PASS → 13 survive 2× cost → **0 cleared MTC**.

## Phase-4 / 4.5 leads — RETIRED (D-015)
Gated crypto breakout (`donch_brk(20)` & `vol_hi`/`ny`/`adx_hi25`) was the best line: on 9 coins it
reached Sharpe 0.28 / DSR 0.895 (15m). Widening to 17 coins collapsed it to Sharpe 0.16 / DSR 0.43 —
small-sample luck, not an edge. Cross-class pooling was dead (dilution). Reports: `POWER_BOOST.md`,
`ROBUSTNESS.md`. All hypotheses: `HYPOTHESIS_REGISTRY.csv` (phase 3: 220, phase 4: 119).

## Next (T-403) — DECIDE WITH THE USER; breakout line is exhausted
Across Phases 3–4.5 (~340 hypotheses) the gauntlet found **0 deployable edges** — a real, useful
result. Do NOT grind the dead breakout lead. Genuinely new directions to choose between:
1. **New factor families** on the same engine: momentum/continuation, volatility-regime breakout with
   different exits (trailing/time), cross-sectional ranking (long strongest / short weakest in a class),
   time-of-day / session-open effects, mean-reversion with a volatility filter. Each is a fresh sweep →
   T-303 → (if it survives a BROAD cross-section) Phase 5.
2. **Reconsider the data/budget constraint.** Free intraday depth (15m ~52d) and a ~17-name crypto
   universe may be the binding limiter on finding a *robustly significant* short-horizon edge. A budget
   decision (paid data / deeper history / survivorship-aware universe) could change feasibility.
Pipeline once something truly survives: → CANDIDATES.md → Phase 5 (walk-forward, holdout ONCE) →
Phase 6 (4-week forward paper) → Phase 7 (deploy). Keep pooling per class (D-011); holdout still sealed.

## Open questions
- Exact Twelve Data symbols for WTI/Brent on the free plan (verify on first pull).
- How deep is Twelve Data free 15m/1h history in practice? (measure, record).
- Crypto alt universe + any delisting handling we can approximate.

_Last updated: 2026-10-02 (session 2 — Phase 7 Step A built: HistData deep FX/metals fetcher, ready to fetch + re-sweep)._
