# Research backtest — HH-RUN/SPAN parity (H1) + multi-timeframe counter-signal exit (H2)

**Status: RESEARCH ONLY. Nothing deployed, no scanner shipped.**
Run date 2026-10-10. Engine, data and code are all in `backtest/parity_mtf/`.

## What was tested

Two user hypotheses on V5 Swing + MACD regular divergences (same engine as the
live scanner: LEFT/RIGHT 2/2 pivots, MACD 12/26/9, chart-native SMA-200,
span 6–50, regular divergence only, entry at the confirming-bar close).

- **H1 (entry filter):** a divergence "qualifies" when **run ∈ {2,4}** (consecutive
  higher-highs for BEAR / lower-lows for BULL) **AND span is even AND span > run
  AND span ≤ 20.**
- **H2 (multi-timeframe exit):** instead of a fixed target, exit at the **first
  opposite-direction divergence that confirms on ANY in-scope timeframe** for the
  same asset, after entry ("counter-signal exit"). Tested with no stop (pure),
  with a 1.5×ATR stop, and against a **control: a dumb fixed 20-bar hold**.

Baseline exit = the live model: SL 1.5×ATR / TP 4.0×ATR (1:2.67). R is in
stop-units (win cap +2.67R, loss −1R), costs 0.12% round-trip.

## Data

- **Source: Twelve Data** (Yahoo/yfinance is blocked by this environment's egress
  policy). 45m & 1h are native; **2h/3h/4h are resampled from 1h** (UTC binning).
- **Window: ~24 months, 2024-10-16 → 2026-10-10.**
- **Assets: BTCUSD, ETHUSD, XAUUSD (gold spot), QQQ (NAS100 proxy).**
  Silver and oil are gated behind a paid Twelve Data plan and were excluded;
  NAS100 is only available as the **QQQ regular-hours ETF**, not the 24h CFD.
- 2,914 divergences detected (BTC 941 / ETH 918 / gold 854 / QQQ 201 across 5 TFs).

## H1 — parity entry filter

| Universe | group | n | win% | PF | avg R |
|---|---|---|---|---|---|
| aligned (live scanner) | ALL divergences | 745 | 30.7 | 0.87 | **−0.113** |
| aligned | **H1 qualifying** | 334 | 31.1 | 0.95 | **−0.041** |
| aligned | non-H1 (rest) | 411 | 30.4 | 0.82 | −0.172 |
| all (aligned+counter) | H1 qualifying | 1164 | 27.6 | 0.81 | −0.164 |
| all | non-H1 | 1750 | 27.8 | 0.73 | −0.253 |

**Verdict: H1 is NOT a profitable standalone edge.** It is consistently *less bad*
than non-qualifying divergences (−0.041 vs −0.172R aligned), but still a **net
loser** (PF < 1). Three reasons it is not the edge it looks like:

- **The parity logic is not what helps.** Parity grid (all divs): even-run/even-span
  avg R **−0.235** (one of the *worst* cells); odd-run/even-span is the least bad
  (−0.090). "Even is effective" does **not** hold — same conclusion the project
  reached before.
- **Run value, not parity, carries the signal.** Run=4 is the least-bad run
  (−0.080), run=2 is among the worst (−0.240). H1's {2,4} mixes the two.
- **Most of H1's "improvement" is avoiding gold's terrible non-H1 signals**
  (gold non-H1 = −0.623R, PF 0.51, n=132). It is a junk-filter, not an alpha filter.

By timeframe (aligned), H1 is negative on 45m/1h, positive on 2h/3h — but so is
*non*-H1 on 2h/3h, so that is a **timeframe effect, not an H1 effect**, and the
2h/3h/4h samples are tiny (n=16–57).

## H2 — multi-timeframe counter-signal exit

| Universe | exit rule | n | win% | PF | avg R | med bars |
|---|---|---|---|---|---|---|
| aligned ALL | FIXED 1:2.67 | 745 | 30.7 | 0.87 | −0.113 | 10 |
| aligned ALL | **MTF pure (counter-signal)** | 745 | 52.9 | 1.41 | **+0.522** | 23 |
| aligned ALL | MTF + 1.5×ATR stop | 745 | 33.8 | 0.74 | −0.192 | 8 |
| aligned ALL | **CONTROL: dumb 20-bar hold** | 745 | 47.2 | 1.40 | **+0.449** | 20 |

At first glance H2 looks like a real edge: the counter-signal exit turns the
−0.113R fixed-target loser into **+0.522R (PF 1.41, 53% win)**. **But it does not
survive scrutiny:**

1. **It barely beats a dumb timer.** A fixed 20-bar hold on the *same entries*
   makes **+0.449R** — the counter-signal adds only ~0.07R over holding blindly.
   ~85% of the "edge" is just *holding longer in an aligned trend*, not the
   signal's timing. Add a 1.5×ATR stop and the whole thing dies (−0.192R).
2. **Essentially all the profit is ONE asset in ONE regime — gold.**

   | asset | n | PF | avg R | total R |
   |---|---|---|---|---|
   | **XAUUSD** | 229 | **2.22** | **+2.127** | **+487** |
   | ETHUSD | 226 | 1.03 | +0.031 | +7 |
   | BTCUSD | 254 | 0.77 | −0.204 | −52 |
   | QQQ | 36 | 0.46 | −1.483 | −53 |

   Gold alone is +487R; everything else nets **negative**. Gold ran ~$2,500 →
   ~$5,500 (>2×) over this exact window — a historic bull market. **Any**
   "hold long in an aligned uptrend" rule prints money on gold 2024–26. This is
   regime/selection dependence, not a transferable edge. It fails on BTC and QQQ
   and is flat on ETH.
3. **It needs the stop removed** (uncapped risk; max drawdown −201R; trades held
   40+ bars), so it is not directly tradeable as written.
4. On the **H1-filtered** entries the counter-signal exit is *negative* (−0.113R)
   and worse than the dumb hold (+0.281R) — the two hypotheses do not combine.

## Bottom line (the brutally honest read)

Neither observation is a validated, robust edge on 24 months of real BTC/ETH/
gold/QQQ across 45m–4h:

- **H1 parity filter:** still a net loser; the parity ("even") premise is false in
  the data; what little it does is avoid junk, and it is confounded with timeframe
  and with gold.
- **H2 counter-signal exit:** the headline +0.52R is ~entirely (a) a long-hold
  trend-drift effect that a dumb 20-bar timer captures just as well, and (b) the
  2024–26 gold bull market. Strip either away and it is flat-to-negative.

What a top-0.1% systematic trader would say: *you have re-discovered that holding
aligned trades longer worked during a monster gold trend. That is beta/trend
exposure in one regime, dressed up as a signal. The pivot-count parity has no
mechanism and no edge. Do not build a scanner around either as an alpha claim.*

## Honest limitations (could change the verdict)

- **Instruments differ from your charts:** Twelve Data spot/ETF, not your broker's
  CFDs. NAS100 = QQQ **regular-hours ETF** (not the 24h index), silver & oil
  missing (paid plan). 2h/3h/4h are **resampled from 1h with UTC binning**, not
  TradingView session anchoring — so signals won't match your charts one-for-one.
- **One regime only** (~2 years, including an extreme gold rally). No 2018–2022
  data, no bear phase of comparable size.
- Higher-TF samples are small (4h aligned n≈43).

## If you want to push further

1. **Give me CSV exports** (TradingView/your broker) for the *real* instruments —
   especially silver, oil and the true NAS100 — and I'll re-run on exactly what you
   trade.
2. **Longer / multi-regime window** (upgrade Twelve Data, or CSVs) to test out of
   the gold bull market.
3. **If the interest is the trend-hold effect** (which is the only thing that
   "worked"), test it honestly as a trend-following exit with a real stop and
   position sizing — and expect it to be regime-dependent.

Artifacts: `logs/parity_mtf_results.xlsx` (all tables + every trade),
`logs/parity_mtf_equity.png`. Code: `backtest/parity_mtf/run_backtest.py`;
data cache: `backtest/parity_mtf/data/raw/`.
