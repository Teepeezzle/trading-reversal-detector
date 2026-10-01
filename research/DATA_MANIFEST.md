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

## Actual coverage (auto-filled after first refresh)

| Symbol | tf | bars | first | last | source | pull date | gaps notes |
|---|---|---|---|---|---|---|---|
| _pending first run_ | | | | | | | |

## Known limitations
- Survivorship not corrected (DECISIONS D-004): currently-listed instruments only.
- Twelve Data free history depth is finite (≤5000 bars/call); true intraday depth per
  timeframe is measured and recorded here on first pull.
- Data source ≠ OANDA execution feed; divergence vs the user's charts is expected and
  reconciled interactively.
