# PHASE 2 — Indicator / signal-primitive survey

Every primitive we may test, with **what it measures**, its **known failure modes**, and its
**parameter space**. All are implemented as portable functions in `research/src/indicators.py`
(so they run identically off-peak and interactively). Phase 3 tests each one SOLO first.

**Scope rules carried in:**
- **Volume primitives = FX / metals / oil only** (crypto has no volume on TD free — D-007).
- **Macro-event / sentiment** is **Bigdata.com, MCP-ONLY** (D-009) → interactive overlay, **excluded
  from off-peak sweeps**; listed here for completeness, not for portable backtesting.
- Horizons we optimise: **INTRADAY** (open→same-session close) and **SWING ≤5 trading days**.
- Intraday-depth limit: 15m ~52d (TD) / ~60d (yf) — thin for 15m walk-forward; 1h/4h/1D are deep.

Legend — Horizon fit: ◐ intraday · ◑ swing · ● both.

## 1. Trend
| Primitive | Measures | Failure modes | Param space | Fit | fn |
|---|---|---|---|:-:|---|
| SMA / EMA slope | direction of the mean | whipsaws in range; lag at turns | length 20–200; slope lookback | ● | `sma`,`ema` |
| EMA cross (fast/slow) | trend regime shift | late in choppy markets; many false crosses | (9,21),(20,50),(50,200) | ● | `ema` |
| ADX / DMI | trend **strength** (not direction) | lags; high ADX ≠ continuation | len 14; thresh 20/25 | ● | `adx` |
| Donchian mid slope | structural trend | breaks down in gaps | len 20–55 | ◑ | `donchian` |

## 2. Momentum
| Primitive | Measures | Failure modes | Param space | Fit | fn |
|---|---|---|---|:-:|---|
| RSI | normalised momentum / OB-OS | stays extreme in strong trends | len 7–21; OB/OS 70/30,80/20 | ● | `rsi` |
| MACD (line/signal/hist) | momentum vs its own EMA | lag; false hist flips in range | (12,26,9) and variants | ● | `macd` |
| ROC / momentum | raw % change over N | regime-dependent threshold | N 5–20 | ● | `roc` |
| Stochastic %K/%D | position in recent range | noisy intraday; OB-OS traps in trend | (14,3,3),(5,3,3) | ● | `stoch` |

## 3. Volatility
| Primitive | Measures | Failure modes | Param space | Fit | fn |
|---|---|---|---|:-:|---|
| ATR | average true range (sizing/stops) | not directional; regime-shifts | len 14 (Wilder) | ● | `atr` |
| Bollinger Bands | SD envelope around mean | band-ride in trends; width regime | len 20, k 2.0/2.5 | ● | `bbands` |
| Realised vol / ATR% | vol **state** for regime buckets | lookback choice dominates | 20/50-bar | ● | `atr_pct` |
| Vol expansion/contraction | squeeze → breakout setups | squeezes that fail | BB-width percentile | ◑ | `bb_width` |

## 4. Volume  _(FX/metals/oil only — D-007)_
| Primitive | Measures | Failure modes | Param space | Fit | fn |
|---|---|---|---|:-:|---|
| Volume spike | participation surge | tick-vol ≠ real vol on FX | mult 1.5–2.5× SMA(vol) | ● | `vol_spike` |
| OBV slope | cumulative vol pressure | drifts; broker-vol artefacts | slope lookback | ◑ | `obv` |

## 5. Mean-reversion
| Primitive | Measures | Failure modes | Param space | Fit | fn |
|---|---|---|---|:-:|---|
| Z-score of price vs MA | stretch from the mean | mean-revert fails in trends | MA 20–50; |z|>2 | ● | `zscore` |
| Band-touch fade | reversion from BB edge | band-ride losses in trend | k 2.0/2.5 | ● | `bbands` |
| Prior-session range revert | fade extension of yesterday's range | gaps/news break it | pct of ATR | ◐ | (compose) |

## 6. Structure
| Primitive | Measures | Failure modes | Param space | Fit | fn |
|---|---|---|---|:-:|---|
| Donchian breakout | N-bar high/low break | false breaks; whipsaw | len 20/55 | ● | `donchian` |
| Swing pivots / HH-LL | market structure | lag (needs right-bars to confirm) | left/right 2–5 | ● | `pivots` |
| Prior-day/-week H/L | reference S/R levels | round-number clustering | PDH/PDL/PWH/PWL | ● | (from 1D) |

## 7. Session / time-of-day  _(critical for intraday)_
| Primitive | Measures | Failure modes | Param space | Fit | fn |
|---|---|---|---|:-:|---|
| Session flags (Asia/London/NY) | which session a bar is in | DST; instrument hours differ | UTC windows | ◐ | `session_flags` |
| Hour-of-day / day-of-week | time-of-day edge | overfitting a single hour | 0–23 / 0–4 | ◐ | `time_features` |
| Opening-range breakout | break of first-N-min range | choppy opens; news | N 15/30/60m | ◐ | (compose) |

## 8. Macro-event / sentiment — **Bigdata.com, MCP-ONLY (D-009), NOT in sweeps**
| Primitive | Measures | Use (interactive only) |
|---|---|---|
| Economic calendar | scheduled high-impact events | mark no-trade windows / invalidation in the daily briefing |
| Premium-news / web | event & narrative context | qualitative regime (risk-on/off) labelling in Phase 4 |

> These inform the human-in-the-loop briefing and regime labels; they are **not** backtested
> factors (can't run in Actions, and metered PAYG). If a sentiment factor is ever wanted as a
> tradeable signal, it must first be reproduced as a portable, point-in-time time series.

---
**Next (Phase 3):** a portable no-lookahead, net-of-cost backtest engine tests each primitive
solo (≥100 trades, judged on the validation split), with buy-hold + random-entry benchmarks and
2×-cost / parameter-sensitivity / multiple-testing controls applied from the start.
