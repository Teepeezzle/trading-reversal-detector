> "Fundamentals are displayed as context today because the sample cannot support a validation claim.
> Proof will come from the forward shadow test, not from a backtest on 12 trades. Milestone gates:
> n=100 (read), n=200 (significance), n=400 (walk-forward). Until then, no claim is made either way."

# Forward Shadow Test — fundamentals on the Confluence Board

Purpose: accumulate a **real forward sample** of confluence signals, each tagged with its point-in-time
fundamental context and with three *shadow* fundamental uses recorded in parallel — so that, when the
sample is large enough, we can test honestly whether any fundamental use would have helped. We do this
because the backtest sample (65 signals across the whole validated universe; D-033) is an order of
magnitude too small for a significance claim, and the one rich fundamental series (AV sentiment) does
not even overlap the signal window yet.

**Nothing here is acted on.** The live board and the email scanner are unchanged. Shadow decisions are
recorded only. No verdict is produced until the milestone gates below are reached.

## What is logged (`forward_log.py`)
For every fresh confluence **SETUP** (status==SETUP) from now on, one row in `signals.csv`:
- signal identity + trade levels: instrument, asset_class, direction, tf, confirm_time, entry, stop,
  target, horizon (SL 1.5×ATR / TP 4×ATR = +2.667R / −1R, 30-day resolution cap).
- the full **point-in-time fundamental context vector** (`context_json`) plus flattened fields: macro
  regime (rates/inflation direction, USD backdrop, DXY trend, vol regime), the latest fundamental
  values, and the next projected high-impact event — **every value carries its `available_at`**.
- outcome fields, filled later by `resolve`: outcome (win/loss/expired), exit_time, exit_price, R.

And one row in `shadow.csv` with the three shadow USES (decisions only, never applied):

### Shadow variant definitions (mechanical, non-discretionary)
- **(a) hard gate** — `gate_pass` ∈ {true,false}. Blocks the signal if a high-impact event for its class
  is scheduled **within the holding horizon** (projected from release cadence; e.g. CPI/NFP/FedFunds for
  FX/metals/indices, EIA for oil) — i.e. known event risk that could invalidate the trade before its
  target. `gate_reason` records why.
- **(b) score adjustment** — `score_delta` ∈ [−1,+1]. A bounded confidence tilt from macro-backdrop
  alignment with the trade direction (hawkish-USD vs the pair's USD leg) plus the sign of the latest
  relevant surprise. Recorded, not applied to ranking.
- **(c) regime tag** — `tag`, a label only: `pre-event` (if event in horizon), `rates-<dir>`,
  `infl-<dir>`, and for crypto `funding±`. No action; used later to bucket outcomes by regime.

At the gates we compare the baseline signal outcomes against: gated-only (gate_pass), score-weighted,
and per-regime — each a registered hypothesis under multiple-testing correction.

## No-look-ahead guarantees
- A signal's context uses only fundamental records with `available_at <= confirm_time` (macro = FRED
  first-release / point-in-time; EIA release-week print; sentiment D+1; funding as-stamped). Nothing is
  interpolated, extrapolated, or back-filled — a missing record is left null and flagged stale.
- Outcomes use only price bars strictly **after** entry.
- If any series is revised-to-date rather than point-in-time, results built on it will be labelled
  "optimistic upper bound." (Current macro source is first-release, so this does not apply today.)

## Milestone gates (held to; see DECISIONS D-034)
| milestone | resolved n | what we do |
|---|--:|---|
| read | 100 | preliminary read only — **no verdict**, no significance test |
| significance | 200 | first significance test **with multiple-testing correction** across all recorded variants |
| walk-forward | 400 | walk-forward validation on the accumulated shadow log |

**We do NOT run the augmented-vs-baseline backtest until pooled n ≥ 200** (D-034). The confluence fires
~30×/yr across the validated universe, so n=200 is a multi-quarter-to-year horizon — that patience is
the whole point: a sample we can actually test on, not significance squeezed from 12 trades.

## Operation
Weekly GitHub Actions job (`.github/workflows/fundamentals-forward-test.yml`) runs
`python forward_test/forward_log.py all` = record (new setups) → resolve (matured) → report
(`STATUS.md`), and persists the updated log. Read-only data access; all secrets in Actions Secrets.
Until the feature PR is approved and merged to main, the workflow is dormant (schedules only fire from
the default branch) — by design, nothing runs against main without approval.
