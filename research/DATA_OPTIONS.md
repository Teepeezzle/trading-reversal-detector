# DATA / BUDGET OPTIONS — scoping memo (T-405)

_Decision input for reopening the search after Phases 3–6 found 0 edges under the $0/free-tier
constraints (~1,200 hypotheses). Compiled 2026-10-02 from current provider info (sources at bottom).
No money has been spent; nothing here changes D-003 until you approve it._

## TL;DR — you probably don't need to spend much (or anything)

The binding limiter was **intraday depth + universe breadth + no alternative data**, caused specifically
by the *Twelve Data free* tier (5000-bar cap → ~52d of 15m; D-005). That is NOT a free-data limit in
general. Two $0 sources break it, and the single most promising *new* direction (crypto
funding/basis/OI) is free-to-cheap:

1. **Dukascopy — FREE, no API key:** 15–20 years of tick/OHLC for **FX, metals, oil (CFDs), indices**
   (EUR/USD 2006→now; metals back to 2000–2012). Gives real 5m/15m depth → the power the gauntlet lacked.
2. **Exchange public APIs (Binance/Bybit) — FREE:** deep crypto OHLCV since listing (far past TD's cap),
   and **funding rates / open interest / perp basis / liquidations** — signal families OHLCV can't express.
3. **Databento — pay-as-you-go ~$0.50/GB:** true **CME/NYMEX/COMEX futures** (gold, silver, WTI, Brent)
   + FX + crypto at tick/MBP/OHLCV. A few dollars one-off if the Dukascopy CFD-proxy basis matters.

Institutional crypto feeds (Kaiko ~$12k–55k/yr, Amberdata enterprise) are **overkill** for a retail
$0-null-result follow-up and are not recommended. Unified paid APIs (Twelve Data Grow $79/mo,
Polygon/Massive $29–99/mo) are **convenient but largely unnecessary** given 1–3 above (and TD Grow's
intraday only reaches back to 2022 anyway).

## What each constraint we hit needs, and the cheapest fix

| Constraint (from DATA_MANIFEST / D-004/005/007/008) | What relieves it | Cost |
|---|---|---|
| 15m depth ~52d (TD free 5000-bar cap) → no statistical power | **Dukascopy** FX/metals/oil 5m/15m, 15–20y; **Binance** crypto klines since listing | **$0** |
| 5m excluded entirely (D-005) | Same — Dukascopy/Binance give deep 5m (even tick) | **$0** |
| Universe too small (17 crypto, 7 FX, gold only) | Dukascopy adds more FX/metals/energy; Binance adds the full alt universe incl. delisted | **$0** |
| No *alternative* data — only OHLCV families, all exhausted | **CoinGlass / CoinAPI free tier / exchange APIs**: funding, OI, basis, liquidations, long/short | **$0–cheap** |
| Silver/oil are yfinance futures *proxies* (D-008); gold spot vs futures basis (D-010) | **Databento** real CME/COMEX/NYMEX futures | **~$ single digits PAYG** |
| Survivorship not corrected (D-004) | Partial: include delisted coins from Binance history; true survivorship-free crypto only from Kaiko ($$$) | $0 partial / $$$ full |

## Recommended sequence (cheapest, highest-information first)

- **Step A — $0, biggest lever.** Add a portable **Dukascopy fetcher** (HTTP, CSV, no key — like
  `yfinance_client.py`) for FX + metals + oil at 5m/15m/1h with *years* of depth. **Re-run the entire
  Phases 3–6 gauntlet** on real depth. Power was the thing that killed every near-miss; this is the
  honest test of whether an edge was there but under-sampled. Reconcile vs OANDA later (CFD basis, like D-010).
- **Step B — $0, most *novel*.** Add **Binance** (deep crypto OHLCV + the full alt universe) and a
  **funding-rate / open-interest / basis** feed (CoinGlass or CoinAPI free). Build genuinely new factor
  families the OHLCV search could not: carry/funding-momentum, perp-basis mean-reversion, OI-confirmed
  breakouts. This is the most likely place a real edge still hides.
- **Step C — optional, ~$ trivial.** **Databento PAYG** for true metals/oil (and FX/crypto) futures if
  Step A's CFD proxy proves materially off in reconciliation.
- **Do NOT** buy Kaiko/Amberdata or a monthly unified API yet — unjustified by a null result; revisit
  only if Steps A–B surface something that specifically needs institutional depth/survivorship.

## Integration effort & caveats
- Each source is a new portable fetcher writing the existing lake format (`time,open,high,low,close,volume`);
  ~the size of `yfinance_client.py`. The sweep/gauntlet/registry/workflows are source-agnostic and reused as-is.
- Dukascopy = dealer/CFD prices, not a centralized exchange → model/reconcile basis (precedent: D-010). Fine
  for technical signals; live/forward reconciliation vs the user's own broker stays mandatory.
- Alt-data (funding/OI) needs its own no-lookahead care (publication lag) and its own MTC family.
- GitHub Actions still runs the compute $0; only data acquisition is in question, and A+B are $0.

## Sources
- [Twelve Data pricing](https://twelvedata.com/pricing) · [TD historical-prices support](https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices)
- [Dukascopy Historical Data Export](https://www.dukascopy.com/swiss/english/marketwatch/historical/) · [dukascopy-node](https://github.com/Leo4815162342/dukascopy-node) · [duka-data (Python)](https://github.com/dela-99/duka-data)
- [Polygon.io / Massive pricing (2026)](https://qveris.ai/guides/polygon-pricing-optimized/) · [Polygon review 2026](https://tradingtoolshub.com/review/polygon-io/)
- [Databento futures](https://databento.com/futures) · [Databento CME pricing](https://databento.com/blog/introducing-new-cme-pricing-plans)
- [CoinGlass funding-rate OHLC API](https://docs.coinglass.com/reference/fr-ohlc-histroy) · [CoinAPI funding rates](https://www.coinapi.io/blog/historical-crypto-funding-rates-api-coinapi) · [Tardis.dev](https://tardis.dev/)
- [Best historical crypto data APIs 2026 (CoinGecko)](https://www.coingecko.com/learn/best-historical-crypto-data-apis) · [CoinAPI market-data pricing](https://www.coinapi.io/products/market-data-api/pricing)
