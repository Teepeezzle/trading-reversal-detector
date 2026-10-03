# Fundamentals v1 — Confluence Board (feature/fundamentals-v1)

Reframe of the fundamentals question (D-032 → D-033 → **D-034**): we cannot *prove* fundamentals improve
the board's signals on the thin sample (65 signals; D-033), so we **use them correctly now** and **build
the evidence base** that can produce a real verdict later. Three tracks. **No performance claim is made;
nothing is merged to main or changes the live board without explicit approval.**

## Track A — Context layer (ships) ✅
Fundamentals added to the board as **display-only context** — no gating, scoring, filtering, or signal
change. Each card gains the macro regime (rates/inflation direction, USD backdrop, DXY trend, vol
regime), the latest **point-in-time** fundamental values (with `available_at` + stale flags), and the
next projected high-impact event. Labelled **"Context — not validated"**, toggleable (default ON, one
click to hide).
- `backtest/fundamentals.py` — read-only context module (strict as-of; no interpolation/back-fill).
- `backtest/dashboard_data.py` — additive `_attach_context` post-step; **signal path byte-for-byte
  unchanged** (`asset_state` untouched).
- `dashboard/index.html` — context panel + toggle + footer note.
- **Proof:** `backtest/test_context_identical.py` → PASS (context adds only a `context` key; every signal
  field identical). Verified live in-browser (panel renders, toggle works, setups/levels unchanged).

## Track B — Forward shadow test (the real path to proof) ✅
- `forward_test/forward_log.py` — `record` (idempotent) logs each fresh SETUP + full point-in-time
  context + the three shadow uses (gate/score/tag, recorded never acted on); `resolve` fills first-touch
  SL/TP outcomes (bars only after entry); `report` → `STATUS.md` (running stats + milestone status).
- `forward_test/SHADOW_TEST.md` — honest framing (verbatim), shadow definitions, no-look-ahead
  guarantees, milestone gates. `signals.csv`/`shadow.csv` schema seeded.
- `.github/workflows/fundamentals-forward-test.yml` — weekly; persists via a PR on `forward-test-data`
  (not auto-merged). Dormant until the feature PR merges (schedules fire only from main).
- **Proof:** `forward_test/test_forward_log.py` → PASS (record/resolve/report end-to-end).

## Track C — Broaden the base ✅ (in priority order)
1. **Instrument expansion (done first — highest leverage).** `config/fundamentals_eval_universe.yaml`:
   a **separate, direction-unrestricted** eval universe of **22 instruments** (live scanner config
   untouched). **+12 vs the live universe**, including **WTI (CL=F) and Brent (BZ=F)** → EIA crude data
   is now attachable (it previously had no instrument). **Verified: 12/12 new instruments produce valid
   signal output** on live data (XTIUSD/XBRUSD/XAGUSD/US30USD/SPX500/USDCAD/NZDUSD/USDCHF/EURJPY/GBPJPY/
   SOLUSD/XRPUSD). Signal parameters are inherited from the live scanner config (identical definition).
2. **Pooled estimation (widen the model before widening data).** `backtest/pooled_estimate.py` — a
   DerSimonian-Laird random-effects meta-analysis across cells (asset classes) for each shadow use
   (gate, score). Reports **per-cell AND pooled** effect with 95% CI, τ², I², Q. Validated on synthetic
   data: a consistent weak effect pools tight (I²≈0, z high); sign-inconsistent cells pool to ~0 with
   wide CI (I²≈95) — it won't manufacture significance from disagreement.
3. **Sentiment backfill.** Fold AV sentiment in once N-8 reaches ≥2024-10 (self-advancing, D-031). This
   fixes **overlap, not sample size** — the binding constraint remains signal count.
4. **Backtest only when pooled n ≥ 200** (D-034). Logged and held to.

### Current n
Forward log: **0 resolved** (just seeded). Backtest base (whole validated universe, D-033): **65**.
Eval universe raises the *potential* capture rate (22 vs 10 instruments, both directions), but the
confluence still fires ~30×/yr/instrument, so n=200 remains a multi-quarter-to-year horizon — which is
why we forward-test rather than over-read a thin backtest.

## Guardrails honored
No claim that context improves signals. No augmented-vs-baseline backtest until pooled n ≥ 200. Live
board/signals/workflows unchanged. `available_at` on every value; macro is first-release (point-in-time);
nothing interpolated or back-filled. Branch `feature/fundamentals-v1` — **PR opened, awaiting approval.**
