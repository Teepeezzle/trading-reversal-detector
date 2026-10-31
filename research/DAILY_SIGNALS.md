# DAILY_SIGNALS — live output (top 5 max, ranked by expectancy)

Nothing trades unless it appears here. Empty is valid: "no trades today" is a real output.
Generated pre-dawn by the `briefing` workflow (Phase 6+). Until a validated candidate
exists, this stays empty by design.


## Briefing 2026-10-29
**No trades today.** No validated candidate exists yet (Phases 3–9 found 0 MTC-significant edges); an empty list is the honest output. The event-risk calendar below is live.

### Event-risk calendar (next 14 days — 10 official FXMacroData times, rest projected)
| event | class | next (UTC) | source |
|---|---|---|---|
| trade_balance | forex_macro | 2026-11-04 13:30 | official |
| CrudeInventories ⚠high | oil | 2026-11-04 14:30 ~ | projected |
| business_confidence | forex_macro | 2026-11-05 15:00 | official |
| employment ⚠high | forex_macro | 2026-11-06 13:30 | official |
| non_farm_payrolls ⚠high | forex_macro | 2026-11-06 13:30 | official |
| non_farm_payrolls_change ⚠high | forex_macro | 2026-11-06 13:30 | official |
| unemployment ⚠high | forex_macro | 2026-11-06 13:30 | official |
| wages | forex_macro | 2026-11-06 13:30 | official |
| consumer_confidence | forex_macro | 2026-11-09 16:00 | official |
| core_inflation ⚠high | forex_macro | 2026-11-10 13:30 | official |
| inflation ⚠high | forex_macro | 2026-11-10 13:30 | official |

_Per-signal briefing (once candidates are live): `news: <tag>; next event risk: <event ~date>` — see brief_for_signal(). No new intraday entry within 30 min of a ⚠high event; no holding a fresh position through one without a logged reason (D-021 §3)._

---

## 2026-10-01
**No trades today.** — No validated candidate exists yet; the project is at Phase 1 (data
foundation). An empty list is the correct, honest output at this stage.

---

### Output format (populated once candidates are live)

| Symbol | Asset | Dir | Setup | Entry | Stop | Target | R:R | Horizon | Invalidation | Confidence | Historical stats |
|--------|-------|-----|-------|-------|------|--------|-----|---------|--------------|------------|------------------|

For each signal, also record:
- **Regime context** (trend/range, vol state, risk-on/off).
- **Why now** (the exact condition that just triggered).
- **Early-exit condition** (the specific thing that voids the thesis before stop/target).
- **News context + event risk** (standing rule D-021 / NEWS_LAYER.md §9): the news-context tag for the
  trade, and any scheduled high-impact event that could invalidate it before its target horizon
  (e.g. "CPI in 2h — no new entry", "post-FOMC risk-off tag").

Ranking: by **expectancy**, not chart aesthetics. Horizon ∈ {intraday, swing(≤5d)}.
All levels net-of-cost aware. Intraday signals assume same-session exit; swing ≤5 trading days hard.
