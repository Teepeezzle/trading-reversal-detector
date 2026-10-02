# BLOCKERS — what the project needs from the user (or is waiting on)

Open blockers at top. Jobs that hit a blocker log it here and exit cleanly (never fabricate).

---

## OPEN
- **B-004 · Crypto funding/perp data is geo-blocked from US GitHub Actions** — Phase 8 Step B.
  The Bybit refresh returned 0 rows for all 18 symbols in CI. Cause: Bybit's public API geo-blocks
  US IPs — and GitHub's runners are US-based. (Binance's global API does the same.) The local de-risk
  passed only because this dev box is not a US IP. So the funding/basis fetch cannot run in the $0
  US-Actions pipeline as built. **Decision needed — pick one:**
  (a) **CoinGlass free API + a `COINGLASS_API_KEY` repo secret** — a US-accessible *data vendor* (not
      an exchange) with historical funding; I rewire `cryptoalt_client.py` to it. Keeps the Actions
      architecture; needs the user to create a free key + add the secret (like TWELVEDATA_API_KEY).
  (b) **Fetch the alt lake locally (non-US) and commit the small CSVs** (~10-15 MB) so CI reads them
      from the checkout — one-time, overrides D-006 (lake-out-of-git) for this dataset only.
  (c) **Drop Step B** — conclude crypto funding/basis isn't reachable at $0 from US Actions; the
      engine (`src/cryptoalt.py`, families, sweep, judge) stays ready for whenever data is available.
  The code is built and smoke-tested; only the data source is blocked.

---

## RESOLVED
- **B-003 · Silver + oil not on Twelve Data free** — ✅ 2026-10-01. User chose yfinance fallback
  (D-008): XAG/USD=SI=F, WTI/USD=CL=F, BRENT/USD=BZ=F. Verified locally (silver daily to 2000,
  WTI 1h to 2024). Sole-source (no TD cross-check for these three).
- **B-002 · Merge bootstrap PR to `main`** — ✅ 2026-10-01 (PR #1).
- **B-001 · Twelve Data API key as GitHub Secret** — ✅ 2026-10-01. First run authenticated.
