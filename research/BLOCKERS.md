# BLOCKERS — what the project needs from the user (or is waiting on)

Open blockers at top. Jobs that hit a blocker log it here and exit cleanly (never fabricate).

---

## OPEN
- **B-005 · FRED_API_KEY is malformed** — News layer N-1. The CI news refresh got HTTP 400 from FRED
  on every series: *"The value for variable api_key is not a 32 character alpha-numeric lower-case
  string."* So the stored `FRED_API_KEY` secret is not a valid FRED key. **Fix:** get the exact 32-char
  lowercase key from https://fredaccount.stlouisfed.org/apikeys (My Account → API Keys), re-add it as
  the `FRED_API_KEY` secret (no quotes/spaces/newline), then re-dispatch research-news-refresh. (EIA
  worked — 195 crude-inventory releases landed; only FRED is blocked.)

---

## RESOLVED
- **B-004 · Crypto funding geo-blocked from US Actions + CoinGlass free tier paid-gated** — ✅
  2026-10-02 (D-023). Bybit/Binance 451 from US runners; CoinGlass historical funding = "401 Upgrade
  plan" on free. Funding (208 KB) fetched once via Bybit from a non-US box and COMMITTED to
  `research/altdata_committed/funding/`; CI joins it to TD crypto bars. No key/network/geo issue.
- **B-003 · Silver + oil not on Twelve Data free** — ✅ 2026-10-01. User chose yfinance fallback
  (D-008): XAG/USD=SI=F, WTI/USD=CL=F, BRENT/USD=BZ=F. Verified locally (silver daily to 2000,
  WTI 1h to 2024). Sole-source (no TD cross-check for these three).
- **B-002 · Merge bootstrap PR to `main`** — ✅ 2026-10-01 (PR #1).
- **B-001 · Twelve Data API key as GitHub Secret** — ✅ 2026-10-01. First run authenticated.
