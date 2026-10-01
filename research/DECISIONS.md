# DECISIONS — every judgment call, with the why

Append-only. Newest at top. Each entry: date · decision · why · reversible?

---

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
