"""Proper test of INTRADAY TREND-CONTINUATION: buy pullbacks in a confirmed
higher-timeframe uptrend (the only intraday style consistent with our findings:
trade WITH the trend, not against it).

Setup (bullish, on 1h):
  * MACRO uptrend: most-recent COMPLETED daily close > daily SMA200.
  * INTRADAY uptrend: EMA20(1h) > EMA50(1h).
  * PULLBACK + RESUME: RSI(14) crosses back up through 40 (a dip that is
    reasserting), with close still above EMA50 (the pullback held the trend)
    and an up candle.
  * Entry LONG at that bar's close. SL = sl*ATR, TP = tp*ATR, or time stop.
Everything non-repainting (daily macro uses the prior completed day; entry uses
the current closed 1h bar). Costs 0.05% + 2 ticks. Grid TP/SL/time.

Decisive metric: pooled expectancy (avg R) > 0 AND consistent across assets.
"""

from __future__ import annotations

import time
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "backtest" / "results"
BASKET = {"BTC-USD": ("Bitcoin", 0.01), "ETH-USD": ("Ethereum", 0.01),
          "GC=F": ("Gold", 0.10), "SI=F": ("Silver", 0.005),
          "CL=F": ("WTI Oil", 0.01), "NQ=F": ("Nasdaq100", 0.25)}
COMMISSION = 0.0005
SLIP_TICKS = 2
TP_MULTS = [1.5, 2.0, 3.0]
SL_MULTS = [1.0, 1.5]
TIME_STOPS = [10, 20, 40]


def _fetch(ticker: str, interval: str, periods) -> Optional[pd.DataFrame]:
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
                if len(df) >= 300:
                    return df
            time.sleep(1.2)
    return None


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def rsi(c, n=14):
    d = c.diff()
    g = wilder(d.clip(lower=0), n)
    l = wilder(-d.clip(upper=0), n)
    rs = g / l.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def atr(df, n=14):
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def macro_map(daily: pd.DataFrame) -> Dict[pd.Timestamp, bool]:
    sma = daily["Close"].rolling(200).mean()
    up = (daily["Close"] > sma).shift(1)  # prior completed day -> no lookahead
    return {d.normalize(): bool(v) for d, v in up.items() if pd.notna(v)}


def gen_entries(h: pd.DataFrame, macro: Dict[pd.Timestamp, bool]) -> List[int]:
    c = h["Close"]; o = h["Open"]
    ema20 = c.ewm(span=20, adjust=False).mean().to_numpy()
    ema50 = c.ewm(span=50, adjust=False).mean().to_numpy()
    r = rsi(c).to_numpy()
    close = c.to_numpy(); openp = o.to_numpy()
    days = h.index.normalize()
    out = []
    for i in range(55, len(close) - 1):
        if not macro.get(days[i], False):
            continue
        if ema20[i] <= ema50[i]:
            continue
        if close[i] <= ema50[i]:
            continue
        if not (r[i] > 40 and r[i - 1] <= 40):
            continue
        if close[i] <= openp[i]:
            continue
        out.append(i)
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = {}
    for tk, (name, tick) in BASKET.items():
        daily = _fetch(tk, "1d", ("5y", "10y"))
        h = _fetch(tk, "1h", ("720d", "365d"))
        if daily is None or h is None:
            print(f"  {name}: missing data, skipped")
            continue
        data[tk] = (name, tick, h, macro_map(daily))
        print(f"  loaded {name}: {len(h)} 1h bars")

    pooled = {(tp, sl, T): [] for tp, sl, T in product(TP_MULTS, SL_MULTS, TIME_STOPS)}
    per_asset_best = {}
    for tk, (name, tick, h, macro) in data.items():
        close = h["Close"].to_numpy(); high = h["High"].to_numpy(); low = h["Low"].to_numpy()
        atrv = atr(h).to_numpy()
        slip = SLIP_TICKS * tick
        entries = gen_entries(h, macro)
        best = None
        for tp_m, sl_m, T in pooled:
            Rs = []
            for i in entries:
                if np.isnan(atrv[i]) or atrv[i] <= 0:
                    continue
                entry = close[i] + slip
                r = sim(close, high, low, i, entry, entry - sl_m*atrv[i], entry + tp_m*atrv[i], T, slip)
                if r is not None:
                    Rs.append(r - COMMISSION * 2 * entry / (sl_m*atrv[i]))
            pooled[(tp_m, sl_m, T)] += Rs
            if Rs:
                e = float(np.mean(Rs))
                if best is None or e > best[1]:
                    best = ((tp_m, sl_m, T), e, len(Rs), 100*np.mean(np.array(Rs) > 0))
        per_asset_best[name] = (len(entries), best)

    print("\n================ per-asset (best config by expR) ================")
    print(f"  {'asset':<11}{'entries':>8}{'bestCfg':>16}{'n':>5}{'win%':>7}{'expR':>9}")
    for name, (ne, best) in per_asset_best.items():
        if best:
            cfg, e, n, w = best
            print(f"  {name:<11}{ne:>8}{str(cfg):>16}{n:>5}{w:>6.0f}%{e:>9.3f}")
        else:
            print(f"  {name:<11}{ne:>8}   no trades")

    print("\n================ POOLED across basket — top configs by expR ================")
    print(f"  {'tp':>4}{'sl':>5}{'T':>4}{'n':>6}{'win%':>7}{'expR':>9}{'PF':>7}{'verdict':>9}")
    rows = []
    for (tp_m, sl_m, T), Rs in sorted(pooled.items(), key=lambda kv: -(np.mean(kv[1]) if kv[1] else -9)):
        if not Rs:
            continue
        R = np.array(Rs); w = R[R > 0]; l = R[R <= 0]
        pf = w.sum()/-l.sum() if l.sum() < 0 else float("inf")
        e = float(R.mean())
        v = "EDGE" if e > 0.08 and len(R) >= 40 else ("+" if e > 0 else "loses")
        print(f"  {tp_m:>4}{sl_m:>5}{T:>4}{len(R):>6}{100*np.mean(R>0):>6.0f}%{e:>9.3f}"
              f"{(round(pf,2) if pf!=float('inf') else 'inf'):>7}{v:>9}")
        rows.append({"tp": tp_m, "sl": sl_m, "T": T, "n": len(R),
                     "win_pct": round(100*np.mean(R>0)), "expR": round(e, 3)})
    pd.DataFrame(rows).to_csv(OUT / "trend_continuation.csv", index=False)
    print("\n  Daily breakout benchmark: +0.32 to +0.38 R.  (>0.08 pooled + consistent = worth building)")


if __name__ == "__main__":
    main()
