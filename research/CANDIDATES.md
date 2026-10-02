# CANDIDATES — surviving strategies

Only strategies that passed Phase-3 validation (≥100 trades, positive net expectancy on
the **validation** set, an economic rationale) appear here. Each must list known weaknesses.
A candidate is removed the moment it fails holdout, dies at 2× costs, or depends on one
instrument / date range / parameter value.

_No candidates yet — nothing has survived the full robustness gauntlet (2x cost + parameter sensitivity + Bonferroni + Deflated Sharpe)._

---

### Template
**C-xxx · <name>**
- Universe / timeframe / horizon:
- Rule (entry / stop / target / invalidation):
- Net stats (val): trades, winrate, expectancy R, profit factor, max DD, Sharpe
- Benchmarks beaten: buy-and-hold ___ / random-entry ___
- Robustness: 2× cost result ___ · parameter sensitivity ___ · regimes it works/fails in ___
- Economic rationale (why it should work):
- Known weaknesses:
- Status: validation / walk-forward / forward-paper / deployed
