# NEWS / FUNDAMENTAL LAYER — standing spec

> **Standing rule (user-directed, 2026-10-02).** Technical research continues unchanged. The
> fundamental/news layer is **CONTEXT AND FILTER, never a standalone entry signal.** Every news
> rule is a testable, reproducible, timestamped hypothesis logged in HYPOTHESIS_REGISTRY.csv and
> judged by the same gauntlet. No discretionary news trading; no look-ahead; API-sourced (off-peak
> compatible), never MCP-only for sweeps.

## 1. Coverage per instrument class
- **Forex / Metals:** central-bank decisions, rate expectations, CPI/PCE, NFP, GDP, PMI, geopolitical
  risk, DXY direction.
- **Oil:** OPEC+ decisions, EIA/inventory reports, supply disruptions, refinery outages.
- **Crypto:** ETF flows, exchange listings/delistings, protocol events, regulatory news, macro
  liquidity (rates, DXY).

## 2. Timestamping is MANDATORY (no look-ahead)
Every item gets `published_at` (UTC) and `first_available_at` (UTC). A signal may only reference news
known **before** the decision bar. If the publish time is unknown, the item is **unusable → discard**.
Store news in its own lake table(s) with these fields; the backtest joins on `first_available_at <= bar_open`.

## 3. Event calendar (forward)
Maintain a rolling forward calendar of scheduled releases tagged high/medium/low impact. Rules:
- **No new intraday entry within 30 min before a high-impact release** on the affected instrument.
- **No holding a fresh position through** a high-impact release without an explicit, logged reason.

## 4. How news is used (three modes only)
- **GATE:** block technical setups that contradict an imminent high-impact event.
- **REGIME TAG:** label each trade with its news context (e.g. "hawkish CB surprise", "risk-off macro",
  "quiet session") so results bucket later.
- **SENTIMENT INPUT:** only if measured programmatically and timestamped — never from reading headlines.

## 5. No discretionary news trading
We do not opine on what news "means". We record it, timestamp it, tag it, and let the backtest decide
whether it adds edge. Every news-based rule is a reproducible condition.

## 6. Validation (same bar as technicals)
Each news factor is a hypothesis logged in HYPOTHESIS_REGISTRY.csv. Test: does the news filter improve
expectancy **after costs**, or merely reduce trade count? Both outcomes are valid, reportable results.
Judged by T-303 (2x cost + sensitivity + Bonferroni + Deflated Sharpe); its own MTC family.

## 7. Off-peak compatibility
News is pulled via **API** (direct calls or committed to /data), never local MCP, so GitHub Actions
jobs can run it. An MCP-only source is **interactive-only** and excluded from off-peak sweeps (cf. D-009 Bigdata).

## 8. Sources (prefer structured, timestamped, official)
Log the source and pull time for every item. Exclude unreliable or undated sources.
- **FRED API** (free key) — US macro release values + **release dates** (CPI, PCE, GDP, NFP via BLS,
  rates). Timestamped, official. → forex/metals.
- **EIA API** (free key) — weekly petroleum status / crude inventories (Wed 10:30 ET), official. → oil.
- **Economic calendar API** (Finnhub or FMP free tier) — forward scheduled events + forecast/actual,
  ISO-8601 UTC. → the event calendar (§3) + CB/PMI across classes.
- **Crypto events** — CoinGecko events / exchange announcement endpoints (listings/delistings);
  ETF-flow + regulatory feeds TBD. Lower priority; add once FX/oil macro is proven.
- Headlines/sentiment: only via a programmatic, timestamped feed — deferred.

## 9. Daily briefing
DAILY_SIGNALS.md gains one line per signal: the **news-context tag** and any **scheduled event** that
could invalidate the trade before its target horizon.

---

## Build plan (phased; each source = a portable fetcher + a registry-logged hypothesis)
- **N-1** FRED fetcher → macro-release calendar+surprises table (`data/news/fred_*.csv.gz`); needs `FRED_API_KEY` secret.
- **N-2** EIA fetcher → oil inventory releases + surprise vs forecast; needs `EIA_API_KEY` secret.
- **N-3** Economic-calendar fetcher (Finnhub/FMP) → forward high/med/low events; needs that key.
- **N-4** News schema + no-lookahead join helper (`src/news.py`): `first_available_at <= bar_open`.
- **N-5** Gate + regime-tag integration into the backtest/gauntlet (news factor = hypothesis, own MTC family).
- **N-6** DAILY_SIGNALS briefing line (§9).
Status: SPEC captured 2026-10-02 (D-021). Not yet built — starts after Step B (crypto funding) is unblocked.
