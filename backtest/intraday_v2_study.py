"""Two genuinely new intraday hypotheses (OODA round 2), tested honestly.

Both are WITH-trend and use the winning concepts, not the losing ones:

  A) PDH-BREAKOUT: in a confirmed daily uptrend (prior daily close > daily
     SMA200), go LONG on the 1h when price first breaks above the PRIOR DAY's
     high (a level traders/algos actually watch). Momentum, not reversal.

  B) WITH-TREND DIVERGENCE PULLBACK: in a daily uptrend, go LONG when a 1h
     pivot low prints a bullish MACD divergence (price lower-low, MACD
     higher-low) — the user's repeated-swings + divergence idea, but used to
     BUY DIPS in an uptrend instead of shorting tops.

Exits: SL = sl*ATR(1h), TP = tp*ATR(1h), or a time stop. Grid both.
Non-repainting: daily context uses the prior completed day; pivots are
confirmed; entries use the current closed 1h bar. Costs 0.05% + 2 ticks.

Decisive: pooled expectancy (avg R) > 0 AND consistent across assets, vs the
daily benchmark of +0.32 to +0.38 R.
"""

from __future__ import annotations

import time
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "backtest" / "results"
BASKET = {"BTC-USD": ("Bitcoin", 0.01), "ETH-USD": ("Ethereum", 0.01),
          "GC=F": ("Gold", 0.10), "SI=F": ("Silver", 0.005),
          "CL=F": ("WTI Oil", 0.01), "NQ=F": ("Nasdaq100", 0.25)}
COMMISSION = 0.0005
SLIP_TICKS = 2
TP_MULTS = [2.0, 3.0, 4.0]
SL_MULTS = [1.0, 1.5]
TIME_STOPS = [12, 24]
PIVOT_LEN = 5


def _fetch(ticker, interval, periods) -> Optional[pd.DataFrame]:
    for period in periods:
        for _ in range(3):
            try:
                raw = yf.download(ticker, period=period, interval=interval,
                                  progress=False, auto_adjust=False, threads=False)
            except Exception:
                raw = None
            if raw is not None and not raw.empty:
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna(
                    subset=["Open", "High", "Low", "Close"])
                if df.index.tz is not None:
                    df.index = df.index.tz_convert("UTC").tz_localize(None)
                if len(df) >= 250:
                    return df
            time.sleep(1.2)
    return None


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def macd_line(c):
    return c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()


def atr_series(df, n=14):
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def daily_context(daily: pd.DataFrame):
    """Return {date: (macroUp, prior_day_high, prior_day_low)} keyed by date."""
    sma = daily["Close"].rolling(200).mean()
    up = (daily["Close"] > sma).shift(1)
    pdh = daily["High"].shift(1)
    pdl = daily["Low"].shift(1)
    out = {}
    for d in daily.index:
        out[d.normalize()] = (
            bool(up.get(d, False)) if pd.notna(up.get(d, np.nan)) else False,
            float(pdh.get(d, np.nan)),
            float(pdl.get(d, np.nan)),
        )
    return out


def pivots_low(low, macd, L):
    out = []
    n = len(low)
    for i in range(L, n - L):
        w = low[i - L:i + L + 1]
        if low[i] == w.min():
            out.append((i + L, float(low[i]), float(macd[i])))  # confirmed at i+L
    return out


def sim(close, high, low, i, entry, sl, tp, T, slip):
    risk = entry - sl
    if risk <= 0:
        return None
    n = len(close)
    for j in range(i + 1, min(i + 1 + T, n)):
        if low[j] <= sl:
            return -(risk + slip) / risk
        if high[j] >= tp:
            return (tp - entry) / risk
    j = min(i + T, n - 1)
    return (close[j] - entry) / risk


def entries_pdh(h, ctx):
    """First break above prior-day high each day, in a daily uptrend."""
    close = h["Close"].to_numpy(); idx = h.index
    days = idx.normalize()
    out = []
    fired_day = None
    for i in range(1, len(close)):
        d = days[i]
        macroUp, pdh, _ = ctx.get(d, (False, np.nan, np.nan))
        if not macroUp or not np.isfinite(pdh):
            continue
        if fired_day == d:
            continue
        if close[i] > pdh and close[i - 1] <= pdh:
            out.append(i)
            fired_day = d
    return out


def entries_div(h, ctx):
    """Bullish MACD divergence at 1h pivot lows, in a daily uptrend."""
    low = h["Low"].to_numpy(); macd = macd_line(h["Close"]).to_numpy()
    days = h.index.normalize()
    pl = pivots_low(low, macd, PIVOT_LEN)
    out = []
    for k in range(1, len(pl)):
        ci, price, m = pl[k]
        _, pprice, pm = pl[k - 1]
        if not (price < pprice and m > pm):   # bullish divergence
            continue
        if ci >= len(low):
            continue
        macroUp, _, _ = ctx.get(days[ci], (False, np.nan, np.nan))
        if macroUp:
            out.append(ci)
    return out


def evaluate(h, tick, entries):
    close = h["Close"].to_numpy(); high = h["High"].to_numpy(); low = h["Low"].to_numpy()
    atrv = atr_series(h).to_numpy()
    slip = SLIP_TICKS * tick
    grid = {}
    for tp_m, sl_m, T in product(TP_MULTS, SL_MULTS, TIME_STOPS):
        Rs = []
        for i in entries:
            if np.isnan(atrv[i]) or atrv[i] <= 0:
                continue
            entry = close[i] + slip
            r = sim(close, high, low, i, entry, entry - sl_m*atrv[i], entry + tp_m*atrv[i], T, slip)
            if r is not None:
                Rs.append(r - COMMISSION * 2 * entry / (sl_m*atrv[i]))
        grid[(tp_m, sl_m, T)] = Rs
    return grid


def stat(Rs):
    if not Rs:
        return None
    R = np.array(Rs); w = R[R > 0]; l = R[R <= 0]
    pf = w.sum()/-l.sum() if l.sum() < 0 else float("inf")
    return len(R), round(100*np.mean(R > 0)), round(float(R.mean()), 3), \
        (round(pf, 2) if pf != float("inf") else "inf")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = {}
    for tk, (name, tick) in BASKET.items():
        daily = _fetch(tk, "1d", ("3y", "5y"))
        h = _fetch(tk, "1h", ("720d", "365d"))
        if daily is None or h is None:
            print(f"  {name}: missing data, skipped")
            continue
        data[tk] = (name, tick, h, daily_context(daily))
        print(f"  loaded {name}: {len(h)} 1h bars")

    for hyp_name, entry_fn in [("A) PDH-BREAKOUT (long, daily uptrend)", entries_pdh),
                               ("B) WITH-TREND DIVERGENCE PULLBACK (long)", entries_div)]:
        print(f"\n################ {hyp_name} ################")
        pooled = {(tp, sl, T): [] for tp, sl, T in product(TP_MULTS, SL_MULTS, TIME_STOPS)}
        print(f"  {'asset':<11}{'entries':>8}{'bestCfg':>16}{'n':>5}{'win%':>7}{'expR':>9}")
        for tk, (name, tick, h, ctx) in data.items():
            ents = entry_fn(h, ctx)
            grid = evaluate(h, tick, ents)
            best = None
            for cfg, Rs in grid.items():
                pooled[cfg] += Rs
                s = stat(Rs)
                if s and (best is None or s[2] > best[1][2]):
                    best = (cfg, s)
            if best:
                print(f"  {name:<11}{len(ents):>8}{str(best[0]):>16}{best[1][0]:>5}{best[1][1]:>6}%{best[1][2]:>9}")
            else:
                print(f"  {name:<11}{len(ents):>8}   no trades")
        print(f"  {'-- POOLED, top configs by expR --':<40}")
        print(f"  {'tp':>4}{'sl':>5}{'T':>4}{'n':>6}{'win%':>7}{'expR':>9}{'PF':>7}{'verdict':>9}")
        ranked = sorted(pooled.items(), key=lambda kv: -(np.mean(kv[1]) if kv[1] else -9))
        for cfg, Rs in ranked[:5]:
            s = stat(Rs)
            if not s:
                continue
            v = "EDGE" if s[2] > 0.10 and s[0] >= 40 else ("+" if s[2] > 0 else "loses")
            print(f"  {cfg[0]:>4}{cfg[1]:>5}{cfg[2]:>4}{s[0]:>6}{s[1]:>6}%{s[2]:>9}{str(s[3]):>7}{v:>9}")
    print("\n  Daily benchmark: +0.32 to +0.38 R.  (>0.10 pooled + consistent across assets = worth building)")


if __name__ == "__main__":
    main()
