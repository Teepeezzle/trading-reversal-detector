# Trading Reversal Detector

A Python tool that scans forex, metals, oil, and crypto for high-probability
reversal signals at significant horizontal price extremes (Daily / Weekly /
Monthly / Yearly highs and lows).

A signal is reported only when **all four** of these conditions are present
simultaneously:

| # | Condition           | Detail                                                                                   |
|---|---------------------|------------------------------------------------------------------------------------------|
| 1 | **Extreme touch**   | Previous candle's Low (longs) / High (shorts) pierced the level within 0.1% tolerance.   |
| 2 | **Close-back**      | Most-recent closed candle's Close is back inside the level (rejection).                  |
| 3 | **RSI divergence**  | Bullish (Price LL + RSI HL) for longs, bearish (Price HH + RSI LH) for shorts.           |
| 4 | **Volume confirm**  | Volume on the rejection candle is above its 20-period SMA.                               |

Each accepted signal returns an ATR-based stop-loss, two take-profit targets
(2R / 4R), position size, and a confidence score in [0, 100].

---

## Project layout

```
trading-reversal-detector/
├── SKILL.md
├── README.md
├── requirements.txt
├── main.py                       # CLI entry point
├── config/
│   └── config.yaml               # Watchlist + risk parameters
├── src/
│   ├── __init__.py
│   ├── data_fetcher.py           # yfinance with 5-minute TTL cache
│   ├── indicators.py             # Wilder RSI(14), Wilder ATR(14), Volume MA(20)
│   ├── price_levels.py           # D / W / M / Y high & low calculator
│   ├── reversal_detector.py      # 4-condition signal logic
│   ├── risk_manager.py           # SL/TP, sizing, session limits
│   └── signal_formatter.py       # Renders the alert block
├── logs/
│   ├── run.log                   # Full runtime log
│   └── signals.log               # Append-only signal history
└── tests/
    └── test_reversal.py          # 15 offline pytest tests
```

---

## Setup

```bash
cd trading-reversal-detector
pip install -r requirements.txt
```

Python 3.10+ is required.

---

## Running

### Scan everything in the config

```bash
python main.py --scan-all
```

### Scan a single ticker

```bash
python main.py --ticker GC=F            # Gold
python main.py --ticker EURUSD=X        # EUR/USD
python main.py --ticker BTC-USD --verbose
```

When a signal is found it is printed to stdout in the canonical alert block
format (see SKILL.md for an example) and appended to `logs/signals.log`.
If no signals fire, the tool prints `No reversal signals detected in this
scan.` and exits 0.

---

## Configuration

`config/config.yaml`:

```yaml
account_balance: 10000
risk_per_trade_pct: 2.0
max_daily_loss_pct: 6.0
max_concurrent_positions: 8
max_positions_per_class: 3
cache_duration_seconds: 300
extreme_touch_tolerance: 0.001     # 0.1%
swing_lookback: 5                  # candles either side for swing detection

tickers:
  forex:   ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
            "USDCAD=X", "NZDUSD=X", "USDCHF=X"]
  metals:  ["GC=F", "SI=F"]
  oil:     ["CL=F", "BZ=F"]
  crypto:  ["BTC-USD", "ETH-USD"]
```

Add or remove tickers as needed. Anything yfinance recognises will work — just
make sure to add a friendly `ticker_names` entry too.

---

## Risk model

| Quantity         | Formula                                         |
|------------------|-------------------------------------------------|
| Stop-loss        | `level ± 1.0 × ATR(14)` (beyond the extreme)    |
| Risk distance    | `abs(entry - stop_loss)`                        |
| Take-profit 1    | `entry ± 2 × risk_distance`  (close 50%)        |
| Take-profit 2    | `entry ± 4 × risk_distance`  (close 50%)        |
| Position units   | `(balance × risk_per_trade_pct) / risk_distance`|

Session guards (return a `blocked` signal with the reason rather than
silently dropping it):

- Daily loss ≥ `max_daily_loss_pct` of balance.
- Active signals ≥ `max_concurrent_positions`.
- Active signals for a single asset class ≥ `max_positions_per_class`.

---

## Tests

```bash
pytest tests/ -v
```

15 offline tests covering indicator bounds, swing-point detection, signal
trigger and no-trigger paths, risk math (long and short), and signal
formatting.

---

## Caveats

- yfinance reports zero volume for forex pairs (`*=X`); for those instruments
  the volume condition is treated as a soft pass and confidence is reduced.
- The fetcher caches data in-process for 5 minutes (configurable). Re-running
  during the same process re-uses cached frames.
- This tool surfaces *setups*; it does not place trades. Treat every output
  as a discretionary alert.
