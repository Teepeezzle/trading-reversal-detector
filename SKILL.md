---
name: trading-reversal-detector
description: Scan forex, metals, oil, and crypto for reversal signals at significant Daily / Weekly / Monthly / Yearly extremes. A signal fires only when all four conditions are present — extreme touch, close-back rejection, RSI divergence, and volume confirmation — and the tool returns full entry, stop-loss, and take-profit levels with position sizing.
---

# Trading Reversal Detector

## What this skill does

Monitors price action across a configurable list of liquid instruments and
alerts when a high-probability reversal is forming at a *significant* horizontal
extreme. The detector requires four simultaneous conditions before firing:

1. The previous candle's wick pierced a Daily / Weekly / Monthly / Yearly
   high or low (within 0.1% tolerance).
2. The most-recent closed candle closed back inside the level (rejection).
3. RSI divergence between the last two swing points
   (bullish for longs, bearish for shorts).
4. Volume on the rejection candle is above its 20-period moving average.

Each signal is returned with entry, ATR-based stop-loss, two take-profits,
position size, and a confidence score in [0, 100].

## When to invoke

Invoke this skill when the user asks to:
- "Scan for reversals" / "find reversal signals" / "check for pin bars".
- Analyse a specific ticker (e.g. *"is there a reversal setup on Gold?"*).
- Build a daily watchlist of mean-reversion trade ideas.

## How to invoke

The skill is delivered as a standalone Python project. After installing
dependencies (see *Setup* below), run it from the project root:

```bash
# Scan every configured ticker
python main.py --scan-all

# Scan a single ticker (any yfinance symbol)
python main.py --ticker GC=F
python main.py --ticker BTC-USD --verbose
```

## Setup

```bash
cd trading-reversal-detector
pip install -r requirements.txt
```

Tested on Python 3.10+.

## What outputs to expect

Each detected signal is printed to stdout as an alert block, e.g.:

```
═══════════════════════════════════════
🔔 REVERSAL SIGNAL DETECTED
═══════════════════════════════════════
Asset:        Gold (GC=F)
Direction:    LONG 📈
Level:        Monthly Low @ $1,920.50
Entry Price:  $1,922.30
Stop Loss:    $1,918.20  (-0.21% | -$4.10)
Take Profit 1: $1,928.60  (+0.42% | +$8.10)  → Close 50%
Take Profit 2: $1,935.80  (+0.84% | +$16.30) → Close 50%
Confidence:   78%
Reason:       Broke monthly low to $1,919.80 then closed back at $1,922.30.
              RSI bullish divergence: price LL, RSI HL. Volume 1.4× average.
Timestamp:    2025-01-15 14:32:00 UTC
═══════════════════════════════════════
```

Signals are also appended to `logs/signals.log` in a parsable single-line
format for downstream pipelines.

When no signals fire, the tool prints
`No reversal signals detected in this scan.` and exits 0.

## Dependencies

- Python 3.10+
- `yfinance`, `pandas`, `numpy`, `pyyaml`, `ta`, `pytest`

All declared in `requirements.txt`.

## Configuration

`config/config.yaml` holds the watchlist, display names, account balance, and
risk limits. Edit it to add tickers, change risk per trade, or tighten the
concurrent-signal caps.

## Tests

```bash
pytest tests/ -v
```

Tests are fully offline — they use hand-crafted OHLCV frames to verify both
the indicator math and the four-condition signal logic.
