# Per-Asset Fundamental Trend — design, data, and honest limits

Display-only context enhancement (`backtest/fundtrend.py`). Replaces the generic USD macro block with a
per-asset **FUNDAMENTAL TREND** (BULLISH / BEARISH / NEUTRAL + strength), computed from each asset's own
fundamentals. It is a **factual read of the data, not a prediction, not validated, and not a signal** —
the "FUNDAMENTAL TREND - NOT VALIDATED" label stays. No gating, no scoring of signals, no change to
signal generation (`asset_state` has zero diff).

## Hard rules honored
- **available_at on every value** — each component shows the date its data became known; the shadow/no-
  lookahead discipline carries over (crypto sentiment joined at D+1).
- **Staleness → EXCLUDE, never substitute.** Max-age per data type (below). A component older than its
  max-age is dropped and flagged with its age/reason. This fixes the XRP `news_sentiment stale 825d`
  bug — it is now excluded and shown as `Excluded: News sentiment (stale 825d)`, never displayed as
  current.
- **No interpolation / back-fill / guessing.** A missing value is a gap.
- **No proxying.** A non-US currency's rates/inflation are **never** replaced with USD — if there is no
  reachable free source, the leg is excluded and said so.
- **< 2 usable components → NEUTRAL (insufficient data).**

## Max-age per data type
| data | max age |
|---|---|
| FRED CPI / NFP / FedFunds (monthly) | 45 days |
| FRED GDP (quarterly) | 100 days |
| Yahoo yields / DXY / commodities (daily) | 4 days (covers weekends) |
| Funding rate | 1 day |
| News sentiment | 7 days |

## Data reachability — the binding constraint (verified empirically)
The board workflow runs **keyless** (no secrets), and this environment can only reach some hosts.
**Reachable + keyless (used):** Yahoo (US yields `^TNX`, DXY `DX-Y.NYB`, commodities `GC=F`/`CL=F`/`SI=F`),
committed archives (US FRED macro = first-release **point-in-time**, EIA oil, per-coin funding, AV
sentiment), CoinGecko. **NOT reachable keyless here (probed):** DBnomics, ECB, IMF, World Bank, Bank of
England, RBA — all DNS-blocked; stooq (which has global sovereign yields) is **bot-blocked** (returns
HTML, not CSV); FRED direct needs a key the keyless board doesn't have.

**Consequence:** there is **no reachable free source for non-US central-bank rates/inflation**. Those
legs are **excluded** (never proxied with USD). This is stated on every affected card. To light them up
later, a committed per-country rates/CPI archive would be harvested from an unrestricted box (the same
pattern as the committed Bybit funding) — noted as a follow-up, not faked here.

## Drivers used per asset class (reachable only)
- **FX pairs** — per leg, combined as base-strength minus quote-strength:
  - **USD**: Fed rate path (FedFunds trajectory), US inflation (CPI yoy accel/decel), US labor (NFP), US
    real yield (10y − CPI). All point-in-time from the committed FRED archive.
  - **JPY**: US 10y yield / risk (carry — higher US yields → JPY weaker). [BoJ rate/inflation EXCLUDED]
  - **AUD**: gold terms-of-trade (`GC=F`). [RBA EXCLUDED]  ·  **CAD**: oil terms-of-trade (`CL=F`). [BoC EXCLUDED]
  - **NZD, EUR, GBP, CHF, NGN**: no reachable driver → EXCLUDED.
  - *Rate-differential (2y yield spread) is EXCLUDED everywhere* — no reachable non-US 2y yields.
- **Metals (XAU/XAG)**: US real yield (inverse) + DXY (inverse) [+ gold/silver ratio for XAG; industrial
  demand EXCLUDED].
- **Oil (WTI/Brent)**: EIA crude inventory w/w (draw = bullish) + DXY (inverse) [OPEC+/refinery/
  geopolitics EXCLUDED].
- **Crypto**: US rates + DXY (risk, inverse) + per-coin funding (extreme = contrarian) + AV sentiment
  (7-day staleness → excluded when stale) [ETF flows / asset-specific EXCLUDED].

## Strength
From the number of **used** components and their agreement (`|net vote| / used`): strong (≥0.75 and ≥3
used), moderate (≥0.5), else weak. `< 2` used → NEUTRAL "insufficient data". Near-max-age components
still count only while within their window.

## Where exclusions are logged (visible)
- **Per card**: an `Excluded: …` line listing each dropped component and its reason.
- **Board run log**: `fundtrend exclusions (N): …` summarizing every exclusion across all cards.
- **Payload**: `context.fundamental_trend.excluded[]` in `data.js`.

## Verified (examples, live data)
Distinct per-asset directions (not the same USD block): **USDJPY** BULLISH (US hiking + JPY pressured),
**AUDUSD** BEARISH, **XAUUSD** BEARISH (real yield rising + DXY), **XTIUSD** BEARISH (EIA build + DXY),
**XRPUSD** BEARISH (rates/DXY; sentiment **excluded, stale 825d**), **NZDJPY** NEUTRAL (JPY/US-yield
only; NZD excluded), **EURNZD** NEUTRAL (both legs excluded — no reachable source). Signal output is
byte-identical (context is additive; `asset_state` untouched).
