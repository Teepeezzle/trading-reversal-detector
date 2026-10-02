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
- 🔵 **T-303** Robustness gauntlet BUILT (`jobs/robustness.py` + `src/mtc.py` + `research-robustness`
  workflow): 2× cost + parameter sensitivity + Bonferroni + Deflated Sharpe, promotes survivors →
  CANDIDATES.md, full report → ROBUSTNESS.md (D-012). Validated on a synthetic PASS (correctly
  rejected: dies at 2× cost, p=0.38, DSR=0.05). **Waiting on the sweep to populate the registry**,
  then dispatch `research-robustness` to run it for real.

## Phase 4+ (queued, not started)
- ⬜ **T-401** Combine Phase-3 survivors across regime buckets (trend/range, vol hi/lo, risk on/off).
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
