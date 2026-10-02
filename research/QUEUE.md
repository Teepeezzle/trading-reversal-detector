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
- 🔴 **T-405 (DECISION — $0 space exhausted)** Phases 3–6 = ~1,200 hypotheses, every structurally-
  distinct approach, **0 deployable edges**. Only lever left is **data/budget** (D-003): deeper
  intraday history / survivorship-aware universe / more instruments / alternative data. User's call —
  I can scope providers + costs on request. Holdout still sealed for a genuine future candidate.
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
