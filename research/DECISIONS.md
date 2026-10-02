# DECISIONS — every judgment call, with the why

Append-only. Newest at top. Each entry: date · decision · why · reversible?

---

### 2026-10-02 · D-012 · T-303 promotion gate = 2× cost + sensitivity + Bonferroni + Deflated Sharpe
A base-gate PASS (≥100 val trades, positive net expectancy, beat random) is only a lead; the
winner of a ~220-hypothesis sweep is inflated by selection alone. **Decision:** a hypothesis
becomes a CANDIDATE only if it survives ALL four independent checks, judged on validation:
(1) **2× transaction cost** still n≥100, expR>0, PF>1; (2) **parameter sensitivity** — ≥60% of
±1–2 neighbors stay positive with positive median (edge is a plateau, not a spike); (3)
**Bonferroni** one-sided p < 0.05 / N where N = hypotheses actually tested; (4) **Deflated Sharpe
Ratio > 0.95** (Bailey & López de Prado — deflates for N trials via the expected-max-Sharpe
benchmark and for skew/fat tails). p-values use the normal approximation to the t-distribution,
valid at n≥100. All math is stdlib (`research/src/mtc.py`, `statistics.NormalDist`) — no scipy, so
it runs identically off-peak. Implemented in `research/jobs/robustness.py`; nothing reaches
CANDIDATES.md otherwise. _Reversible: yes (thresholds are CLI args)._

### 2026-10-01 · D-011 · Phase-3 tests POOL a rule across an asset class (sample size)
Engine validation showed single-instrument rules fire only 8–54 trades (val 8–21) — far below
the 100-trade minimum. **Decision:** every single-factor test pools a rule across ALL instruments
in its asset class (each split on its own 60/20/20 timeline, trades pooled by split tag). This
reaches ~85–432 trades. Note: crypto (9 syms) & FX-intraday still land ~85–96 val — to clear 100
reliably, pool FX majors+crosses together or add 4h. Benchmark = trade-weighted avg of per-
instrument random-entry controls. Engine (backtest.py/costs.py/single_factor.py) verified on real
lake data; no naive factor passed (expected). _Reversible: yes._

### 2026-10-01 · D-010 · Sources reconciled (T-102); gold is spot, silver/oil are futures
TD vs yfinance 1h close, inner-joined: **EUR/USD PASS** (median 0.027%, p95 0.038%), **BTC/USD
PASS** (0.058% / 0.154%) → like-for-like sources agree tightly, **mixed lake validated**. XAU/USD
"FAIL" (0.46% / 1.36%) is the **spot-vs-futures basis** (TD XAU/USD = spot; yfinance GC=F =
futures), not a data error. **Consequence to carry:** gold = spot (TD); silver/oil = futures
(yfinance). Fine for short-horizon technical signals (basis slow-moving); model roll/financing
per instrument when costs are applied. See RECONCILE.md. _Reversible: yes (could switch gold to GC=F)._

### 2026-10-01 · D-009 · Bigdata.com = interactive macro-event/news overlay only (MCP-ONLY, PAYG)
User added the Bigdata.com connector. Assessment: it's an **equities-focused** news/sentiment/
fundamentals service (packages: company-sentiment, earnings, filings, economic-calendar,
premium-news, web, …; PAYG 1000 credits). For this FX/metals/oil/crypto PRICE project its useful
surface is narrow — **economic-calendar + premium-news/web for macro-event context**. It is
**MCP-ONLY** (no portable API → excluded from off-peak Actions sweeps per architecture) and
**metered** (burning credits in bulk breaks the $0 spirit). **Decision:** use it only at the
INTERACTIVE layer — event-awareness for the daily briefing (Phase 6) and qualitative regime
labelling (Phase 4) — never as a price source and never in backtests/sweeps. _Reversible: yes._

### 2026-10-01 · D-008 · Silver + oil sourced from yfinance (not on TD free)
Twelve Data free returns 404 for XAG/USD, WTI/USD, BRENT/USD. User chose the yfinance fallback
(B-003 option A): `SI=F` (silver), `CL=F` (WTI), `BZ=F` (Brent) — free, already used in this repo,
same lake format via `research/src/yfinance_client.py` (4h resampled from 1h). These three are
**sole-source** (no TD cross-check) and inherit yfinance limits (15m ~60d). _Reversible: yes._

### 2026-10-01 · D-007 · Volume features restricted to FX/metals/oil (crypto has no free volume)
First live run confirmed Twelve Data free crypto quotes omit `volume`. **Decision:** volume
primitives (OBV, volume-spike, VWAP-by-volume) are tested on FX/metals/oil only; crypto uses
price/volatility/structure primitives. The client now tolerates missing volume (sets 0.0).
Revisit if a crypto volume source is added. _Reversible: yes._

### 2026-10-01 · D-006 · Lake persisted via Actions cache + artifact (not git) for now
The OHLCV lake is kept out of git (`research/.gitignore`) and persisted via Actions
**cache** (fast, free) + an uploaded **artifact** (downloadable, 14-day retention). Reason:
we don't yet know the lake's on-disk size, and committing large data to a public repo is
wasteful/irreversible. After the first refresh we measure size and decide whether to also
git-commit it (to a data branch) for long-term durability. _Reversible: yes._

### 2026-10-01 · D-005 · 5-minute timeframe excluded from scope (for now)
Deep 5m history is not available on free data tiers (Twelve Data free 5min is shallow;
yfinance 5m is a few days). Per the mission's "say so and request a decision" rule, we
flagged it; user chose $0 budget. **Decision:** scope = 15m / 1h / 4h / 1D. Revisit only
if the budget decision changes. _Reversible: yes (budget-gated)._

### 2026-10-01 · D-004 · Survivorship bias accepted as a documented limitation
A survivorship-free universe (delisted crypto/pairs, changed tickers) is not obtainable
on free tiers. **Decision:** universe = currently-listed liquid instruments; every
performance claim carries a "survivorship-not-corrected" caveat. Mitigation: favour
instruments with long continuous listings; note any known delistings qualitatively.
_Reversible: yes (paid data would fix)._

### 2026-10-01 · D-003 · Budget = $0, free tiers only
User choice. Enforced in code: Twelve Data capped at 8 req/min & 800 req/day via a
persisted daily counter; on exhaustion the job logs to BLOCKERS and exits cleanly.
Public-repo Actions minutes are free, so compute is not the binding cost. _Reversible: yes._

### 2026-10-01 · D-002 · Build in existing repo under `research/`, land via PR
User choice. Reuses the existing yfinance pipeline, backtest harness, and Actions/caching.
All research isolated under `research/`. Work pushes to `research/*` branches and lands as
PRs the user merges; **never a direct push to main.** Note: scheduled workflows run only
from the default branch, so workflow files must be merged to main to fire. _Reversible: yes._

### 2026-10-01 · D-001 · Twelve Data (free) as primary off-peak data layer; yfinance as cross-check
User choice. Twelve Data is portable (plain HTTPS API → works inside GitHub Actions, unlike
MCP servers) and covers FX/metals/oil/crypto + indicators. yfinance stays as a free second
source for reconciliation. MCP servers (TradingView/OANDA) remain the **interactive** layer
only and are never relied on inside Actions. _Reversible: yes._
