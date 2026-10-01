# DAILY_SIGNALS — live output (top 5 max, ranked by expectancy)

Nothing trades unless it appears here. Empty is valid: "no trades today" is a real output.
Generated pre-dawn by the `briefing` workflow (Phase 6+). Until a validated candidate
exists, this stays empty by design.

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

Ranking: by **expectancy**, not chart aesthetics. Horizon ∈ {intraday, swing(≤5d)}.
All levels net-of-cost aware. Intraday signals assume same-session exit; swing ≤5 trading days hard.
