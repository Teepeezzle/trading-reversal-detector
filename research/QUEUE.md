# QUEUE — research task backlog

A job claims a task by marking it `in-progress` **in the same commit** (so two concurrent
runs never work the same task). Each task: id, phase, hypothesis/goal, params, data needed,
status (todo/in-progress/done/blocked), result link.

Status legend: ⬜ todo · 🔵 in-progress · ✅ done · ⛔ blocked

---

## Phase 1 — data foundation
- ⛔ **T-101** Build `/research/data` lake for the full universe (15m/1h/4h/1D).
  _Blocked on B-001 (Twelve Data key) + B-002 (merge to main)._ → DATA_MANIFEST.md
- ⬜ **T-102** Reconcile Twelve Data vs yfinance on EUR/USD 1h + BTC/USD 1h; record tolerance. → DECISIONS.md
- ⬜ **T-103** Measure & record real free-tier history depth per timeframe. → DATA_MANIFEST.md

## Phase 2 — indicator survey (portable functions only)
- ⬜ **T-201** Catalogue primitives: trend (EMA/SMA/ADX), momentum (RSI/MACD/ROC/Stoch),
  volatility (ATR/BB/Keltner), volume (OBV/vol-spike), mean-reversion (z-score/VWAP dev),
  structure (Donchian/pivots/HH-LL), session/time-of-day. For each: what it measures,
  failure modes, parameter space. → `research/src/indicators.py` + registry notes.

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
