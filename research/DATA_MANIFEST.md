# DATA_MANIFEST — what's cached, coverage, source, pull date

The `/research/data` lake is built by `jobs/data_refresh.py`. This file is
auto-appended after each refresh. Until the first run it shows the PLAN only.

**Timezone policy:** all bars stored in **UTC**, timestamp = bar OPEN. Twelve Data returns
exchange-local or UTC depending on symbol — the client normalises everything to UTC.
Partial/forming bars are dropped (no look-ahead).

**Storage format:** `research/data/<asset_class>/<SYMBOL>_<tf>.csv.gz`, columns
`time,open,high,low,close,volume`. Idempotent: refreshes merge + dedupe on `time`.

**Working timeframes:** 15m, 1h, 4h, 1D. (5m excluded — see DECISIONS D-005.)

---

## Planned universe (see config.yaml — exact Twelve Data symbols verified on first pull)

| Asset class | Instruments (intended) | Session (for refresh timing) |
|---|---|---|
| Forex majors | EUR/USD, GBP/USD, USD/JPY, USD/CHF, USD/CAD, AUD/USD, NZD/USD | London+NY |
| Forex crosses | EUR/JPY, GBP/JPY, EUR/GBP, AUD/JPY, EUR/NZD, GBP/NZD, GBP/AUD | London+NY |
| Metals | XAU/USD, XAG/USD | London+NY |
| Oil | WTI/USD, BRENT/USD *(symbol strings TBD on free plan)* | NY |
| Crypto | BTC/USD, ETH/USD, SOL/USD, XRP/USD, BNB/USD, DOGE/USD, AVAX/USD, LINK/USD, LTC/USD | 24/7 |

## Actual coverage (first refresh 2026-10-01, Twelve Data free)

**Depth is ~5000 bars/call (free cap).** Single-call reach per timeframe:

| tf | bars/call | ≈ reach |
|---|--:|---|
| 15min | 4,999 | **~52 days** (binding constraint for OOS/walk-forward) |
| 1h | 4,999 | ~208 days |
| 4h | 4,999 | ~2.3 years |
| 1day | 4,999 (FX/gold) · 2,100–3,300 (crypto) | ~20y FX/gold; crypto = coin age |

**✅ Pulled OK (24 instruments × 4 tf):** EUR/USD, GBP/USD, USD/JPY, USD/CHF, USD/CAD,
AUD/USD, NZD/USD, EUR/JPY, GBP/JPY, EUR/GBP, AUD/JPY, EUR/NZD, GBP/NZD, GBP/AUD, **XAU/USD**,
BTC/USD, ETH/USD, SOL/USD, XRP/USD, BNB/USD, DOGE/USD, AVAX/USD, LINK/USD, LTC/USD.
Crypto carries no volume (D-007). Budget used today: 144/800.

**Silver + oil via yfinance (D-008 — not on TD free):** XAG/USD=`SI=F` (daily to 2000),
WTI/USD=`CL=F` (1h to 2024, ~2.3y), BRENT/USD=`BZ=F`; 4h resampled from 1h; yfinance 15m ~60d.
**Sole-source** (no TD cross-check for these three).
Deeper 15m history would require paginating (end_date walk) = extra calls; deferred under $0.

## Known limitations
- **Spot vs futures mix (D-010):** gold = **spot** (TD XAU/USD); silver + oil = **futures**
  (yfinance SI=F/CL=F/BZ=F). ~0.46% basis vs spot — fine for short-horizon technical signals;
  model roll/financing per instrument in cost accounting.
- **No crypto volume on Twelve Data free** (confirmed first run 2026-10-01): crypto quotes
  omit the `volume` column → volume-based indicators (OBV, volume-spike) are **unavailable for
  crypto** on this tier. Volume features are FX/metals/oil-only unless sourced elsewhere.
- Survivorship not corrected (DECISIONS D-004): currently-listed instruments only.
- Twelve Data free history depth is finite (≤5000 bars/call); true intraday depth per
  timeframe is measured and recorded here on first pull.
- Data source ≠ OANDA execution feed; divergence vs the user's charts is expected and
  reconciled interactively.
