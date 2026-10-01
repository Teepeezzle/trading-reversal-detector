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
- ⬜ **T-301** For each primitive, fixed simple rule, both horizons, per asset class.
  Log hitrate/expectancy/PF/maxDD/trades/avg-hold to HYPOTHESIS_REGISTRY. Discard on val.

## Phase 4+ (queued, not started)
- ⬜ **T-401** Combine Phase-3 survivors across regime buckets (trend/range, vol hi/lo, risk on/off).
- ⬜ **T-501** 60/20/20 split + walk-forward; holdout touched ONCE at the end.
- ⬜ **T-601** 4-week forward paper test; log every signal taken or not.
- ⬜ **T-701** Scanner + signal spec + daily morning routine.

## Bias-control tasks (apply throughout, report)
- ⬜ **T-901** 2× transaction-cost re-run on any survivor.
- ⬜ **T-902** Parameter sensitivity sweep (±1–2 around winners).
- ⬜ **T-903** Multiple-testing correction (Deflated Sharpe / Bonferroni) + count of hypotheses tested.
- ⬜ **T-904** Benchmarks: buy-and-hold + random-entry control (same stop/target).
