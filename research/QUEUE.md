# QUEUE — research task backlog

A job claims a task by marking it `in-progress` **in the same commit** (so two concurrent
runs never work the same task). Each task: id, phase, hypothesis/goal, params, data needed,
status (todo/in-progress/done/blocked), result link.

Status legend: ⬜ todo · 🔵 in-progress · ✅ done · ⛔ blocked

---

## Phase 1 — data foundation ✅ COMPLETE
- ✅ **T-101** Lake built: 27 instruments × 4 TFs (TD FX/gold/crypto + yfinance silver/oil). → DATA_MANIFEST.md
- ✅ **T-102** Reconcile TD vs yfinance: FX & crypto PASS; gold = spot/futures basis (D-010). → RECONCILE.md
- ✅ **T-103** Depths recorded: 15m ~52d(TD)/~60d(yf) binding; 1h/4h/1D deep. → DATA_MANIFEST.md

## Phase 2 — indicator survey (portable functions only)
- ✅ **T-201** Catalogue primitives + what each measures / failure modes / param space.
  → PHASE2_INDICATORS.md + `research/src/indicators.py` (portable). Volume = FX/metals/oil only (D-007).
  Macro-event/sentiment = Bigdata.com, MCP-ONLY interactive (D-009), excluded from sweeps.

## Phase 3 — single-factor testing (min 100 trades; judge on validation set)
- ✅ **T-300** Portable backtest engine built & validated: backtest.py/costs.py/single_factor.py
  (pooled, no-lookahead, net-of-cost, benchmarks, 60/20/20). D-011.
- ✅ **T-301** `jobs/sweep.py` built (idempotent/resumable `--max`; `src/factors.py` shared logic).
  Validated on real lake: FX pooled 91–279 trades; 0 PASS (naive factors negative — expected).
- ✅ **T-302** `research-sweep` nightly workflow: restores lake cache, bounded batch, lands registry
  as an auto PR (needs "Actions can create PRs" repo setting — noted in the workflow).
- ✅ **T-303** Robustness gauntlet RUN end-to-end in CI. Full grid swept (220 hypotheses → 17
  base-gate PASS), then 2× cost + sensitivity + Bonferroni + Deflated Sharpe (N=78 valid tests,
  SR*=0.33). **0 candidates** — no single factor cleared MTC. Leads logged in PROJECT_STATE +
  ROBUSTNESS.md. (`jobs/robustness.py` + `src/mtc.py` + `research-robustness` workflow; D-012.)

## Phase 4 (BUILT — combos × gates)
- 🔵 **T-401** `jobs/combo_sweep.py` + `src/factors.py` GATES + `research-combo-sweep` workflow;
  T-303 generalised with `--phase`. Gate catalogue: adx_lo20/lo25/hi25, trend_up, vol_lo/hi, ny
  (D-013). Local preview on real lake: 119 combos → 21 base-PASS, 13 survive 2× cost; best =
  crypto `donch_brk`+`vol_hi`/`ny` (Sharpe ≈0.18, DSR ≈0.66) — still 0 cleared MTC (power-limited).
  **Next: run research-combo-sweep in CI → merge results → research-robustness (phase=4).**
- ✅ **T-402** Power boost (Phase 4.5, D-014/D-015) RUN. Move 1 (cross-class) dead; Move 2 (crypto
  15m) looked strong on 9 coins (Sharpe 0.28, DSR 0.895) but Move 3 (widen 9→17) **collapsed it**
  (Sharpe 0.16, DSR 0.43) — the edge was small-sample luck. **No candidate. Breakout lead retired.**
- ✅ **T-403 / Phase 5** NEW factor families RUN in CI (D-016/D-017): 540 hypotheses → 58 base-PASS →
  T-303 phase=5 (N=288) → **0 candidates**. Best = `bb_breakout` FX 4h swing (Sharpe 0.10, p=0.11) —
  far from the bar. Single-factor family space exhausted; ~880 hypotheses across Phases 3–5, 0 edges.
- ✅ **T-404 / Phase 6** cross-sectional ranking RUN in CI (D-018/D-019): 320 configs → 25 base-PASS →
  T-303 phase=6 (N=132) → **0 candidates** (best crypto 15m momentum, Sharpe 0.078, p=0.22, DSR 0.002).
- ✅ **T-405 (SCOPED → DATA_OPTIONS.md)** Depth limiter was the *TD-free* cap, not free data. Reopen
  for ~$0. User chose **Both, A first**. (Dukascopy → HistData: Dukascopy ticks are 1 file/hour ≈ 90k
  requests, not Actions-friendly; HistData gives monthly M1 ZIPs — far more practical and FREE.)
- ✅ **T-406 / Phase 7 Step A — DEEP FX/metals (HistData)** DONE (D-020). Deep lake built (~21mo,
  5–8× depth), 480 configs re-swept (phase 7), T-303 N=230 → **0 candidates**. Depth REFUTED the
  "under-powered" hypothesis: high-n rules regressed to Sharpe ≈0.01 (p≈0.42). No FX/metals edge.
- 🔵 **T-407 / Phase 8 Step B — crypto alt-data** BUILT + validated: `src/cryptoalt_client.py` (Bybit),
  `src/cryptoalt.py` (enriched panel + families fund_rev/fund_mom/basis_rev, reuse SL/TP engine),
  `jobs/cryptoalt_refresh.py` (→ data/crypto_alt/), `jobs/alt_sweep.py` (phase 8), robustness phase-8
  re-eval path, + `research-cryptoalt-refresh` / `research-alt-sweep` workflows. Smoke-tested
  end-to-end (2-symbol lake: enrich, families fire, sweep writes 60 rows, phase-8 judge routes).
  B-004 RESOLVED (D-023): CoinGlass free tier is paid-gated ("401 Upgrade plan"), so funding (208 KB)
  was fetched via Bybit from a non-US box and COMMITTED to `research/altdata_committed/funding/` (17/18
  coins; MATIC n/a). `cryptoalt_refresh.py` joins committed funding to TD crypto bars — no key/network/
  geo issue. Validated end-to-end locally (fund_rev 4h-intraday-short Sharpe 0.20, +0.11R @2x, 0 survivors
  on 9 local coins). basis deferred. ✅ **DONE (D-024):** full 17-coin/2y run → 60 hypotheses → 2 base-PASS
  → T-303 phase=8 (N=26) → **0 candidates**. Best `fund_rev` short 4h-intraday (Sharpe 0.13, +0.06R @2x,
  param-robust) fails MTC (p=0.035 vs 0.0019, DSR 0.15). Funding signals behave like everything else.

## News / fundamental layer (STANDING RULE D-021 — spec: NEWS_LAYER.md). CONTEXT & FILTER, never standalone.
- ⛔ **N-1** FRED fetcher BUILT but BLOCKED (B-005): CI got HTTP 400 "api_key not a 32-char lowercase
  string" — the `FRED_API_KEY` secret is malformed. Re-add a valid key, re-dispatch. Code is correct.
- ✅ **N-2** EIA fetcher DONE: CI landed **195 weekly crude-inventory releases** (2023→now) with w/w
  surprise, Wed-10:30-ET UTC stamps → `research/altdata_committed/news/eia.csv.gz`. Validated.
- ⛔/accepted **N-3** Consensus-surprise calendar is PAYWALLED at $0 everywhere (D-026): CoinGlass 401,
  Finnhub premium, FMP **402 Restricted Endpoint**. `fetch_fmp` built + exits-clean (lights up on a paid
  FMP plan). **Decision: use the free actual-vs-PRIOR surprise proxy** (FRED/EIA), already studied in N-5.
  True consensus = a budget decision (D-003), not $0. FMP/FINNHUB keys unused — may delete.
- ✅ **N-4** `src/news.py` BUILT + validated: canonical schema, `latest_asof` no-lookahead join
  (`first_available_at <= bar_open`), `minutes_to_next` 30-min pre-release gate. + `research-news-refresh` workflow.
- ✅ **N-5** DONE (D-025): ran in CI on deep FX/metals 1h/4h + macro news (FRED 235 + EIA 195). 380
  base-vs-gated cells → 11 improve / 131 just-cut-trades / 48 hurt / 175 thin; **0 clear MTC** (N=196).
  News gates mostly cut trades; surprise-SIGN split + quiet regime are the real (coherent, non-significant)
  effects. News confirmed as REGIME TAG / context, not a standalone edge. Report: NEWS_STUDY.md.
- ✅ **N-6** DONE: `jobs/daily_brief.py` — forward event-risk calendar (projected from release cadence)
  + no-trades briefing + per-signal `brief_for_signal()` (news tag + next event risk) + the 30-min
  pre-release rule (§3/§9). Wired as a step in research-news-refresh. Validated on the live news table.
- ⬜ **N-7 (optional)** newsdata.io FORWARD collector (D-027): headlines-only, free=~48h/no archive/no
  sentiment (tested live) — can't backtest, but a scheduled collector would store each run's latest
  finance/crypto headlines (timestamped) to self-build an archive, feeding the briefing + a future
  self-computed keyword event-flow factor. Live/forward use only. `jobs/newsdata_probe.py` confirms the key.
- ⬜ **T-501** 60/20/20 split + walk-forward; holdout touched ONCE at the end.
- ⬜ **T-601** 4-week forward paper test; log every signal taken or not.
- ⬜ **T-701** Scanner + signal spec + daily morning routine.

## Bias-control tasks (apply throughout, report)
- ✅ **T-901** 2× transaction-cost re-run on any survivor — implemented in `jobs/robustness.py`.
- ✅ **T-902** Parameter sensitivity sweep (±1–2 around winners) — implemented in `jobs/robustness.py`.
- ✅ **T-903** Multiple-testing correction (Bonferroni + Deflated Sharpe) + count of hypotheses
  tested — implemented in `src/mtc.py` / `jobs/robustness.py` (D-012).
- ✅ **T-904** Benchmarks: buy-and-hold + random-entry control (same stop/target) — in the engine
  (`backtest.py`), recorded per hypothesis in HYPOTHESIS_REGISTRY.csv.
