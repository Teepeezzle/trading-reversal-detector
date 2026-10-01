# BLOCKERS — what the project needs from the user (or is waiting on)

Open blockers at top. Jobs that hit a blocker log it here and exit cleanly (never fabricate).

---

## OPEN

### B-003 · Silver (XAG/USD) + oil (WTI, Brent) unavailable on Twelve Data free (404)
Core mission assets can't be sourced from TD free. **Decision needed** (DECISIONS pending):
- **(A, recommended)** yfinance fallback for these three — `SI=F` (silver), `CL=F` (WTI),
  `BZ=F` (Brent) work free and are already used elsewhere in this repo. Best-free-source-per-
  instrument; keeps metals+oil in scope at $0. Costs: dual-source (adds TD↔yfinance reconcile).
- (B) Fund a TD/Polygon plan with native commodities (breaks $0).
- (C) Drop silver + oil from scope.
**Owner:** user decision. **Status:** OPEN.

---

## RESOLVED
- **B-002 · Merge bootstrap PR to `main`** — ✅ 2026-10-01. PR #1 merged (`5e64aea`); scheduled
  workflow now live on the default branch.
- **B-001 · Twelve Data API key as GitHub Secret** — ✅ 2026-10-01. `TWELVEDATA_API_KEY` set by
  user; first `data_refresh` run authenticated successfully (36/800 calls used).
