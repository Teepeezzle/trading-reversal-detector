# Fundamentals Augmentation — Confluence Board — EVALUATION REPORT

_Branch `research/fundamentals-augmentation`. Scoped digression (D-032). Evaluation only — **nothing on
the live board is changed**. Generated 2026-10-03. All data access was read-only._

## 0. TL;DR — verdict

**INCONCLUSIVE — the exercise is NOT VIABLE on the data that exists today.** Stopped at the Step-1
viability gate, as the brief instructs ("if the data audit shows the exercise is not viable, stop early
and say so"). The Confluence Board produces **65 signals** over its entire reconstructable history
across the whole 10-asset validated universe — against a required **≥200 total (or ≥100 per asset
class)**. The richest fundamental series (Alpha Vantage daily sentiment) **does not overlap the signal
window at all**, and there is **no oil instrument** for EIA to attach to. No pre-registration, backtest,
ablation, or robustness run was performed — doing so on a sample this thin would manufacture false
precision, exactly the n≈10 trap this project has already been burned by twice (PR gate, two-zone DRS).

**Recommendation: DO NOT INCORPORATE now / revisit only if the data gaps below close.**

---

## 1. Data audit

### 1a. The Confluence Board is a live *snapshot*, not a signal log
The board (`.github/workflows/confluence_board_pages.yml` → `backtest/dashboard_data.py` →
`dashboard/data.js`, redeployed to GitHub Pages every 2h) renders each pair's **current** confluence
state. It does **not** persist a signal history. So a "signal history" has to be *reconstructed* by
running the frozen confluence logic (`src/v5_confluence.py` + `src/v5_divergence.py`, driver
`backtest/confluence_backtest.py`) over historical prices. That reconstruction inherits the data
source's depth limits (below). No existing signal logic was modified; the audit only *ran* it.

### 1b. Signal universe (validated) — `config/v5_confluence_scanner.yaml`
10 assets, **direction-restricted** and asset-pruned from a prior 2y per-asset study (the config itself
says this selection is **selection-biased** and is forward-tracked for that reason):

| class | assets (dirs) | overlapping fundamental |
|---|---|---|
| FX | NZDJPY(buy), AUDUSD(buy), GBPUSD(buy), EURUSD(sell), USDJPY(buy/sell) | FRED macro |
| Crypto | BTCUSD(buy), DOGEUSD(sell), ETHUSD(buy/sell) | crypto funding |
| Metals | XAUUSD(sell) | FRED macro (USD) |
| Index | NAS100(buy) | FRED macro |
| **Oil** | **— none —** | **(EIA has no asset to attach to)** |

The board additionally shows ~8 watch-only FX pairs (`WATCHLIST` in `dashboard_data.py`) that are
explicitly **unvalidated and excluded from the email signals** — not part of the signal set.

### 1c. Signal history depth (the binding limit)
Price source = yfinance proxies. `confluence_backtest.py` windows the last **730 days by entry time**;
by its own documented limits, **15m/30m/45m have only ~60 days** of intraday history, so the deep part
of the window (≈**2024-10-03 → 2026-10-03**) is carried by the **1h–4h** family only.

### 1d. Fundamental records inventory (read-only, `research/altdata_committed/`)

| series | source | id / scope | freq | coverage (UTC) | units | **vintage?** | class |
|---|---|---|---|---|---|---|---|
| Macro (CPI, PCE, NFP, Unemployment, GDP, FedFunds) | FRED | 6 series, `fred.csv.gz` (235 rows) | per-release | **2023-02-01 → 2026-10-02** | index/%/000s | **POINT-IN-TIME (first release, `output_type=4`)** | forex_macro |
| Crude stocks ex-SPR | EIA | WCESTUS1, `eia.csv.gz` (195) | weekly | 2023-01-11 → 2026-09-30 | kbbl | release-week print (~PIT; minor later revisions) | oil |
| News sentiment | Alpha Vantage | `av_sentiment.csv.gz` (1,087) | daily | **2023-01-01 → 2024-02-29** | score ∈[-1,1] | POINT-IN-TIME (article timestamps) | crypto / forex_macro / oil |
| Perp funding | Bybit | 17 coins, `funding/*.csv.gz` | 8h | 2024-10-02 → 2026-10-02 | rate | POINT-IN-TIME (not revised) | crypto |
| Headlines | newsdata.io | `headlines.csv.gz` (38) | forward-only | 2026-10-02 only | text | PIT | all |

### 1e. VINTAGE CHECK (non-negotiable) — **PASS (the good case)**
The macro series are **first-release / point-in-time**, not revised-to-date: `news_refresh.py` queries
FRED with `output_type=4` + `realtime_start`, so each value is the figure as first published, stamped at
its release datetime. **No look-ahead inflation from revisions** — results would *not* need an
"optimistic upper bound" caveat on that account. EIA stores the release-week print (EIA makes small
later revisions; immaterial here and EIA is unusable anyway, see below). AV sentiment and funding are
point-in-time by construction. **Nothing is interpolated, extrapolated, or back-filled.**

---

## 2. Overlap window — the valid backtest period

Intersection of (a) reconstructable signal window ≈ **2024-10-03 → 2026-10-03** and (b) each
fundamental's coverage, restricted to classes that have both an asset and a fundamental:

| fundamental | overlaps signal window? | applies to | signals in overlap |
|---|---|---|---|
| **FRED macro** | ✅ full | FX + metals + index | **53** (FX 47 + metals 6 + index 0) |
| **Crypto funding** | ✅ full | crypto | **12** |
| AV sentiment | ❌ ends 2024-02 — **zero overlap** with the signal window | (crypto/macro) | **0** |
| EIA crude | ❌ no oil asset in the universe | — | **0** |
| Headlines | ❌ forward-only, 1 day | — | **0** |

### Measured signal counts (this run, deployed "LOOSER any-zone-30d" rule; authoritative)
Total across the full universe/window: **n = 65** (baseline: win 32.8%, +0.20R/trade — audit context
only, not a pre-registered result). By asset: USDJPY 27, DOGEUSD 9, EURUSD 8, NZDJPY 6, XAUUSD 6,
AUDUSD 4, BTCUSD 3, GBPUSD 2, NAS100 0, ETHUSD 0. (Older "latest-band" variant: n = 20.)

By class: **FX 47 · crypto 12 · metals 6 · index 0.**

---

## 3. Viability gate — **FAIL → STOP**

Required: ≥200 signals total, **or** ≥100 per asset class to be tested.

- Total reconstructable signals: **65** (< 200). ❌
- Best class: FX **47** (< 100). Crypto 12, metals 6, index 0. ❌
- The two fundamentals that *do* overlap can be applied to at most **53** (FRED×FX+metals+index) and
  **12** (funding×crypto) signals respectively — both far below any threshold at which a gate/score/tag
  study could survive a multiple-testing correction, an out-of-sample split, and a "not driven by one
  instrument / date range" check (criterion iv). USDJPY alone is 27 of the 47 FX signals — any FX result
  would be a single-instrument artifact by construction.
- The richest potential breadth-adder, **AV daily sentiment, has no overlap** with the signal window
  (it ends 2024-02; the signal window starts 2024-10). It contributes **nothing** today.

This is not a close call. Proceeding would mean pre-registering metrics and then computing
augmented-vs-baseline deltas on ~12–47 trades per cell — the exact small-sample regime that produced
two **false positives** in this project's own history (`research_pr_and_two_zone`: the two-zone DRS gate
looked great at n≈10 and **inverted** a week later on a shifted window; the PR gate "lift" was n=22
noise). Forcing a number here would repeat that error with a fundamental label on it.

### Not reached (by design)
Step 3 (pre-registration), Step 4 (baseline-vs-augmented, the gate/score/tag ablation, 2× cost,
revision sensitivity, random-entry benchmark), and the `HYPOTHESIS_REGISTRY.csv` logging were
**deliberately not executed** — the Step-1 gate terminates the flow before any augmented result is
computed, so there is no result to pre-register against and nothing to correct for. **No hypotheses were
tested; the registry is untouched.**

---

## 4. What would make this viable (revisit criteria)

1. **Signal breadth.** The confluence is a *rare* setup (~30 triggers/year across 10 assets). Reaching
   200 needs either ~6+ years of intraday history (yfinance caps 1h at ~730d, 15–45m at ~60d — a paid
   intraday feed would be required) or a materially broader *validated* universe (not the watch-list,
   which reintroduces selection bias). Neither exists at $0 today.
2. **Sentiment overlap.** AV daily sentiment only becomes testable once its backfill reaches the signal
   window (≥2024-10). The N-8 harvester is self-advancing (~20 windows/day) and is at 2024-02 now; in a
   few days it will cover 2024-10→present and **then overlaps**. That removes the *overlap* problem for
   crypto/macro sentiment — but **not** the thin-signal problem (still ~12 crypto / ~53 macro signals).
3. **Oil.** To use EIA, add a validated oil instrument (WTI/Brent) to the confluence universe. Even then
   it is one asset → far from 100.

Bluntly: the gating constraint is **signal count**, not fundamental coverage. More/longer fundamentals
do not fix a 65-signal sample.

---

## 5. Honest caveats
- The 65 is itself on a **selection-biased, direction-restricted** universe (the config says so); an
  unbiased universe would likely yield *fewer* usable positive-expectancy signals, not more.
- yfinance intraday history "rolls" weekly; the exact count drifts run-to-run (±a handful). The verdict
  (≪200) is robust to that drift.
- Baseline confluence expectancy itself is documented as **modest and week-to-week drifting**
  (`research_pr_and_two_zone`), so even the control is noisy.

## 6. Recommendation

**INCONCLUSIVE / DO NOT INCORPORATE** — the Confluence Board does not generate enough signals, over the
period where fundamentals exist, to evaluate whether fundamentals help *with any statistical honesty*.
The vintage situation is actually favourable (point-in-time macro), so this is purely a sample-size
problem. Revisit only if signal breadth materially increases (see §4); fundamental coverage alone will
not change the answer.
