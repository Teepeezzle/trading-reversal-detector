"""Market-maker setup test: LIQUIDITY SWEEP + DIVERGENCE REJECTION (intraday).

Thesis (why this differs from plain divergence, which lost):
  Big traders fade STOP HUNTS, not random momentum divergence. The setup:
    BEARISH:
      * price wicks ABOVE a recent swing high (sweeps the stops resting there)
      * but CLOSES back below it (failed breakout / rejection candle)
      * MACD is LOWER than at that swept high (momentum exhaustion / divergence)
      * enter SHORT at the rejection close
      * STOP just above the sweep wick (the exact invalidation) -> tight risk
      * TARGET a multiple of that tight risk (opposing liquidity below)
    BULLISH: mirror (sweep below a swing low, close back above, MACD higher).
  The tight stop is the point: risk = wick-to-close, so modest reversions pay
  well in R. Everything non-repainting (swept high is a confirmed prior pivot;
  entry uses only the current closed bar).

Decisive metric: expectancy (avg R/trade) after costs. >0 and consistent across
assets with a usable sample = a real edge worth building.
"""

from __future__ import annotations

import time
from itertools import product
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "backtest" / "results"
ASSETS = {"BTC-USD": ("Bitcoin", 0.01), "GC=F": ("Gold", 0.10), "CL=F": ("WTI Oil", 0.01)}
PIVOT_LEN = 5
BUFFER_ATR = 0.10          # stop sits this far above the sweep wick
TP_R = [1.0, 1.5, 2.0, 3.0]
TIME_STOP = [10, 20]
COMMISSION = 0.0005
SLIP_TICKS = 2


def fetch(ticker: str) -> Optional[pd.DataFrame]:
    for period in ("720d", "365d"):
        for _ in range(3):
            try:
                raw = yf.download(ticker, period=period, interval="1h",
                                  progress=False, auto_adjust=False, threads=False)
            except Exception:
                raw = None
            if raw is not None and not raw.empty:
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna(
                    subset=["Open", "High", "Low", "Close"])
                if len(df) >= 400:
                    return df
            time.sleep(1.5)
    return None


def macd_line(c):
    return c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def atr_series(df, n=14):
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def last_confirmed(values, macd, L, kind):
    """At each bar, the most recent CONFIRMED pivot value and its MACD."""
    n = len(values)
    at_val = np.full(n, np.nan)
    at_macd = np.full(n, np.nan)
    for i in range(L, n - L):
        w = values[i - L:i + L + 1]
        if (kind == "high" and values[i] == w.max()) or (kind == "low" and values[i] == w.min()):
            at_val[i] = values[i]
            at_macd[i] = macd[i]
    known_val = np.full(n, np.nan)
    known_macd = np.full(n, np.nan)
    for i in range(n):
        src = i - L
        if src >= 0 and not np.isnan(at_val[src]):
            known_val[i] = at_val[src]
            known_macd[i] = at_macd[src]
    return (pd.Series(known_val).ffill().to_numpy(),
            pd.Series(known_macd).ffill().to_numpy())


def sim(close, high, low, i, direction, entry, sl, tp, T, slip):
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    n = len(close)
    for j in range(i + 1, min(i + 1 + T, n)):
        if direction == "short":
            if high[j] >= sl:
                return -(risk + slip) / risk
            if low[j] <= tp:
                return (entry - tp) / risk
        else:
            if low[j] <= sl:
                return -(risk + slip) / risk
            if high[j] >= tp:
                return (tp - entry) / risk
    j = min(i + T, n - 1)
    return ((entry - close[j]) if direction == "short" else (close[j] - entry)) / risk


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pooled = {(r, t): [] for r, t in product(TP_R, TIME_STOP)}
    per_asset = {}
    for ticker, (name, tick) in ASSETS.items():
        df = fetch(ticker)
        if df is None:
            print(f"[{name}] no data")
            continue
        close, high, low, openp = (df[c].to_numpy() for c in ["Close", "High", "Low", "Open"])
        macd = macd_line(df["Close"]).to_numpy()
        atrv = atr_series(df).to_numpy()
        shVal, shMacd = last_confirmed(high, macd, PIVOT_LEN, "high")
        slVal, slMacd = last_confirmed(low, macd, PIVOT_LEN, "low")
        slip = SLIP_TICKS * tick
        n = len(close)

        # collect sweep-rejection entries
        shorts, longs = [], []
        for i in range(30, n - 1):
            if np.isnan(atrv[i]) or atrv[i] <= 0:
                continue
            # bearish: wick above swing high, close back below, MACD lower, red candle
            if not np.isnan(shVal[i]) and high[i] > shVal[i] and close[i] < shVal[i] \
               and macd[i] < shMacd[i] and close[i] < openp[i]:
                shorts.append(i)
            # bullish: wick below swing low, close back above, MACD higher, green candle
            if not np.isnan(slVal[i]) and low[i] < slVal[i] and close[i] > slVal[i] \
               and macd[i] > slMacd[i] and close[i] > openp[i]:
                longs.append(i)

        asset_rows = []
        for r_mult, T in pooled:
            Rs = []
            for i in shorts:
                entry = close[i] - slip
                sl = high[i] + BUFFER_ATR * atrv[i]
                risk = sl - entry
                tp = entry - r_mult * risk
                rr = sim(close, high, low, i, "short", entry, sl, tp, T, slip)
                if rr is not None:
                    Rs.append(rr - COMMISSION * 2 * entry / risk)
            for i in longs:
                entry = close[i] + slip
                sl = low[i] - BUFFER_ATR * atrv[i]
                risk = entry - sl
                tp = entry + r_mult * risk
                rr = sim(close, high, low, i, "long", entry, sl, tp, T, slip)
                if rr is not None:
                    Rs.append(rr - COMMISSION * 2 * entry / risk)
            if Rs:
                Rs = np.array(Rs)
                pooled[(r_mult, T)] += list(Rs)
                asset_rows.append((r_mult, T, len(Rs), 100*np.mean(Rs > 0), float(Rs.mean()), float(Rs.sum())))
        per_asset[name] = (len(shorts), len(longs), asset_rows)

    for name, (ns, nl, rows) in per_asset.items():
        print(f"\n################ {name} — {ns} short + {nl} long sweep-rejections ################")
        print(f"  {'TPx':>5}{'T':>4}{'n':>6}{'win%':>7}{'expR':>9}{'totR':>8}")
        for r_mult, T, n_, win, exp, tot in sorted(rows, key=lambda x: -x[4]):
            print(f"  {r_mult:>5}{T:>4}{n_:>6}{win:>6.0f}%{exp:>9.3f}{tot:>8.1f}")

    print("\n\n================ POOLED (all 3 assets) ================")
    print(f"  {'TPx':>5}{'T':>4}{'n':>6}{'win%':>7}{'expR':>9}{'verdict':>10}")
    best = None
    for (r_mult, T), Rs in sorted(pooled.items(), key=lambda kv: -(np.mean(kv[1]) if kv[1] else -9)):
        if not Rs:
            continue
        Rs = np.array(Rs)
        exp = float(Rs.mean())
        v = "EDGE" if exp > 0.05 and len(Rs) >= 30 else ("+" if exp > 0 else "loses")
        print(f"  {r_mult:>5}{T:>4}{len(Rs):>6}{100*np.mean(Rs>0):>6.0f}%{exp:>9.3f}{v:>10}")
        if best is None:
            best = (r_mult, T, exp, len(Rs))
    if best:
        print(f"\n  best pooled config: TP={best[0]}R, T={best[1]} -> expR={best[2]:+.3f} on n={best[3]}")
    pd.DataFrame([(r, t, len(v), float(np.mean(v)) if v else None) for (r, t), v in pooled.items()],
                 columns=["tp_R", "time_stop", "n", "expR"]).to_csv(OUT / "liquidity_sweep.csv", index=False)


if __name__ == "__main__":
    main()
