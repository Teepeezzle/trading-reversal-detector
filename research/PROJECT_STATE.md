# PROJECT_STATE — Short-Horizon Signal Research

> Read this file first every session. Resume from "Next", state a 3-line plan, then work.

## ⏸ PAUSED 2026-10-03 — scoped digression (Confluence Board fundamentals study)
This multi-week project is **paused, not abandoned**, for a scoped evaluation: *does incorporating
fundamental data improve the live Confluence Board's signals?* (backtest + report only, no deployment).
Work is isolated on branch `research/fundamentals-augmentation`; main research branch/data untouched;
off-peak Actions left running (the N-8 AV-sentiment harvester keeps self-advancing on main per D-031).
See **D-032**. Digression deliverable = `research/fundamentals/RESULTS.md`.

> **RESUME HERE (main project, after the digression resolves):** N-8 / Phase 10 is built and merged; the
> AV daily-sentiment backfill is **self-advancing** (D-031) — the 05:45 UTC cron harvests ~20 windows/day
> AND auto-squash-merges its archive PR to main. As of 2026-10-03 the archive is at **1,087 rows, span
> 2023-01 → 2024-02** (~98 of 138 windows remaining; ~5 days to ~present). **Exact next action:** once the
> span reaches ~present, dispatch `research-sent-sweep` (runs `--refresh`) → then `research-robustness`
> with `phase=10`, and report the Phase-10 verdict. Nothing else is in flight. Program tally: 2,120
> hypotheses across Phases 3–9, 0 deployable edges; CANDIDATES.md empty.

**Mission:** rules-based, out-of-sample-validated, cost-aware signal system for
INTRADAY (open→same-session close) and SHORT SWING (≤5 trading days) across
Forex, Metals (XAU/XAG), Oil (WTI/Brent), and Crypto (BTC/ETH/liquid alts).
Success = documented edge net of costs + a daily top-5 actionable list.

**Current phase:** PHASE 6 COMPLETE (D-019) — cross-sectional ran in CI: 320 configs → 25 base-PASS →
T-303 phase=6 (N=132) → **0 candidates** (best crypto 15m momentum, Sharpe 0.078, p=0.22, DSR 0.002).
**PROGRAM RESULT: ~1,200 hypotheses across Phases 3–6, every structurally-distinct approach, 0
deployable edges.** No robust short-horizon technical edge exists under the $0/free-data constraints
with this gauntlet. Holdout NEVER touched. **Phase 7 (reopen for ~$0) — user chose Both, A first.** T-405 scoped (DATA_OPTIONS.md).
**Step A DONE (T-406, D-020):** deep FX/metals from HistData (~21mo, 5–8× depth) re-swept — 480
configs → 19 base-PASS → T-303 phase=7 (N=230) → **0 candidates**. Depth REFUTED "under-powered":
high-n rules regressed to Sharpe ≈0.01 / p≈0.42 — the old near-misses were small-sample inflation.
No FX/metals single-factor edge, confirmed with real power. Oil not on HistData (unchanged).
**NEXT = Step B (T-407) BUILT + validated:** crypto alt-data. `src/cryptoalt_client.py` (Bybit v5),
`src/cryptoalt.py` (enriched perp OHLCV + funding + basis; families fund_rev/fund_mom/basis_rev reusing
the SL/TP engine), `jobs/cryptoalt_refresh.py` (→ data/crypto_alt/), `jobs/alt_sweep.py` (phase 8),
robustness phase-8 path, + refresh/sweep workflows. Smoke-tested end-to-end on a 2-symbol lake.
NEW economic signals (funding/basis), not price-only, so Step A's null doesn't predict them.
**Step B DONE (D-024):** crypto funding families ran in CI on the 17-coin/2y committed-funding lake →
60 hypotheses → 2 base-PASS → T-303 phase=8 (N=26) → **0 candidates**. Best `fund_rev` short 4h-intraday
(fade crowded longs) is coherent — Sharpe 0.13, +0.06R at 2× cost, param-robust, beats random — but
fails MTC (p=0.035 vs 0.0019, DSR 0.15). (Funding via committed Bybit data, D-023; CoinGlass free tier
was paid-gated; COINGLASS_API_KEY now unused — user may delete.) basis_rev deferred (NaN).
**PROGRAM TALLY (Phases 3–8): ~1,740 hypotheses, 0 deployable edges.**
**NEWS LAYER (D-021) STARTED.** Built + validated: `src/news.py` (N-4 — canonical schema,
`latest_asof` no-lookahead join, `minutes_to_next` 30-min pre-release gate) + `jobs/news_refresh.py`
(N-1 FRED macro first-release; N-2 EIA weekly crude) + `research-news-refresh` workflow. FRED/EIA keys
set. CI validation: **EIA ✅ (195 crude-inventory releases landed)**; **FRED ⛔ B-005** — the
`FRED_API_KEY` secret is malformed (HTTP 400 "not a 32-char lowercase string"); re-add a valid key
(https://fredaccount.stlouisfed.org/apikeys) + re-dispatch. NEXT: fix FRED; N-3 (economic calendar w/
forecast→surprise, needs a Finnhub/FMP key); N-5 (news gate + regime-tag as registry hypotheses, own
MTC family); N-6 (DAILY_SIGNALS briefing line). **N-5 DONE (D-025):** ran in CI on deep FX/metals
1h/4h + macro news (FRED 235 + EIA 195). 380 base-vs-gated cells → 11 improve / 131 just-cut / 48 hurt
/ 175 thin; **0 clear MTC**. News gates mostly cut trades; the surprise-SIGN split + quiet regime are
the real (coherent, non-significant) effects → news confirmed as REGIME TAG / context, not a standalone
edge. **NEWS LAYER COMPLETE at $0 (D-026).** N-4 schema + no-lookahead join; N-1 FRED (235 events) + N-2 EIA
(195) live; N-5 gate/regime-tag study (news mostly cuts trades; surprise-SIGN tilt coherent, 0 MTC);
N-6 daily briefing + forward event-risk calendar. **N-3 (true consensus surprise) is PAYWALLED at $0
everywhere** — CoinGlass 401, Finnhub premium, FMP 402 Restricted; `fetch_fmp` stays (lights up on a
paid plan). Free reality = actual-vs-PRIOR surprise proxy (already studied, N-5). FMP/FINNHUB keys
unused (may delete). News = CONTEXT & FILTER, confirmed as a regime tag, not a standalone edge.
Holdout untouched. True consensus surprise = a future budget decision (D-003).
**newsdata.io (tested, D-027):** headline aggregator, not economic data — free = ~48h live, no archive,
sentiment paid. Fit = optional FORWARD headline collector (N-7). **FXMacroData (tested, D-028/D-029):**
free data is ~90d-capped + forecasts plan-gated → NOT a historical/consensus source (so "do both" #1/#2
not viable at $0; FRED stays historical macro; consensus = budget D-003). BUT its FREE `/calendar/usd`
official forward schedule (exact times, no key) now powers N-6's event-risk calendar. CONSENSUS CONFIRMED
PAID AT 5/5 providers (CoinGlass, Finnhub, FMP, FXMacroData, + newsdata sentiment).
**N-7 BUILT:** newsdata.io forward headline collector (`src/newsfeed.py` + `jobs/newsdata_collect.py` +
`research-newsdata-collect` daily cron → PRs `altdata_committed/news/headlines.csv.gz`; daily_brief shows
48h headline flow). Forward-only, no backfill/sentiment; seeds a future keyword event-flow factor (N-8).
Dispatch once to seed + confirm the NEWSDATAIO_API_KEY live, then it accumulates nightly.
**N-8 / PHASE 10 BUILT (D-030):** Alpha Vantage `NEWS_SENTIMENT` — the first $0 historical + UTC-timestamped
+ pre-scored sentiment feed (D-021's programmatic-SENTIMENT use, finally at $0). `src/avsentiment.py` (keyed
REST client, runs in Actions; relevance-weighted DAILY per-class aggregation; economy_macro→forex_macro,
energy_transportation→oil, blockchain→crypto), `jobs/avsentiment_refresh.py` (resumable 25/day harvester →
committed `altdata_committed/news/av_sentiment.csv.gz`), `src/sentfactor.py` (strict no-lookahead D+1 join;
families `sent_rev` fade / `sent_mom` follow; pooled, net-of-cost, shared SL/TP engine), `jobs/sent_sweep.py`
(phase-10 registry rows + SENT_STUDY.md), robustness phase-10 re-eval path, + `research-avsentiment-refresh`
workflow (daily 05:45 UTC + dispatch, PRs the archive). Validated locally: all files compile; N-8 smoke test
PASS (weighting + bad-row drop, strict no-lookahead, rule alignment, empty-archive guards); sweep on the empty
archive writes the honest "no data yet" report. Harvest uses REST not MCP (MCP can't run in CI, D-001/D-009)
— same data, resumable. ALPHAVANTAGE_API_KEY + POLYGON_API_KEY secrets added (Polygon reserved for a later
macro feature; unused by N-8). The factor sweep runs meaningfully only after the archive accrues (~1y).

**NEW STANDING RULE (D-021, spec: NEWS_LAYER.md):** a fundamental/news layer — CONTEXT & FILTER, never
a standalone signal; strict UTC timestamping/no-lookahead; forward event calendar (30-min pre-release
gate); GATE / REGIME-TAG / programmatic-SENTIMENT only; every news factor a registry hypothesis judged
by the gauntlet; API-sourced (off-peak); sources FRED/EIA/economic-calendar; DAILY_SIGNALS briefing line.
Build = tasks N-1..N-6 (needs FRED_API_KEY, EIA_API_KEY, a calendar key). Starts after Step B unblocks.
Holdout untouched.
Next: merge the N-8 chain, then dispatch `research-avsentiment-refresh` to validate ALPHAVANTAGE_API_KEY and
seed the resumable backfill (~25 windows/day). Once `av_sentiment.csv.gz` has ~1y depth, run `sent_sweep.py`
then `robustness.py --phase 10` for the gauntlet verdict. (Also still pending: dispatch N-7 `research-newsdata-
collect` to seed headlines; CANDIDATES.md remains empty — 0 edges across ~1,740 hypotheses, Phases 3–8.)

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

_Last updated: 2026-10-02 (session 2 — N-7 newsdata forward headline collector built; dispatch to seed)._
