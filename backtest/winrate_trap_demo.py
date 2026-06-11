"""Demonstration: you CAN make MACD divergence hit a >70% win rate intraday —
but it LOSES money. Win rate and expectancy are different things.

The mechanism: shrink the take-profit and widen the stop, and the win rate
climbs toward 100% (you bank tiny gains, rarely get stopped) — but each rare
loss is huge, so expectancy (avg R per trade) goes negative. This script sweeps
TP/SL on plain MACD divergence (1h, BTC/Gold/Oil) and prints win% next to
expectancy so the trade-off is undeniable.
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
ASSETS = {"BTC-USD": 0.01, "GC=F": 0.10, "CL=F": 0.01}
PIVOT_LEN = 5
COMMISSION = 0.0005
SLIP_TICKS = 2
TP_MULTS = [0.25, 0.5, 1.0, 2.0]
SL_MULTS = [1.0, 2.0, 3.0]
MAX_HOLD = 60


def fetch(ticker: str) -> Optional[pd.DataFrame]:
    for period in ("720d", "365d"):
        for _ in range(2):
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
            time.sleep(1.0)
    return None


def macd_line(c: pd.Series) -> pd.Series:
    return c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def atr_series(df, n=14):
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def pivots(vals, macd, L, kind):
    out = []
    n = len(vals)
    for i in range(L, n - L):
        w = vals[i - L:i + L + 1]
        if (kind == "high" and vals[i] == w.max()) or (kind == "low" and vals[i] == w.min()):
            out.append((i, i + L, float(vals[i]), float(macd[i])))
    return out


def sim(close, high, low, i, direction, entry, sl, tp, slip):
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    n = len(close)
    for j in range(i + 1, min(i + 1 + MAX_HOLD, n)):
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
    j = min(i + MAX_HOLD, n - 1)
    return ((entry - close[j]) if direction == "short" else (close[j] - entry)) / risk


def main():
    pooled = {(tp, sl): [] for tp, sl in product(TP_MULTS, SL_MULTS)}
    for ticker, tick in ASSETS.items():
        df = fetch(ticker)
        if df is None:
            continue
        close, high, low = df["Close"].to_numpy(), df["High"].to_numpy(), df["Low"].to_numpy()
        macd = macd_line(df["Close"]).to_numpy()
        atrv = atr_series(df).to_numpy()
        ph = pivots(high, macd, PIVOT_LEN, "high")
        pl = pivots(low, macd, PIVOT_LEN, "low")
        slip = SLIP_TICKS * tick
        shorts = [p[1] for k, p in enumerate(ph) if k > 0 and p[2] > ph[k-1][2] and p[3] < ph[k-1][3]]
        longs = [p[1] for k, p in enumerate(pl) if k > 0 and p[2] < pl[k-1][2] and p[3] > pl[k-1][3]]
        for tp_m, sl_m in pooled:
            for ci in shorts:
                if ci >= len(close) or np.isnan(atrv[ci]) or atrv[ci] <= 0:
                    continue
                e = close[ci] - slip
                r = sim(close, high, low, ci, "short", e, e + sl_m*atrv[ci], e - tp_m*atrv[ci], slip)
                if r is not None:
                    pooled[(tp_m, sl_m)].append(r - COMMISSION*2*e/(sl_m*atrv[ci]))
            for ci in longs:
                if ci >= len(close) or np.isnan(atrv[ci]) or atrv[ci] <= 0:
                    continue
                e = close[ci] + slip
                r = sim(close, high, low, ci, "long", e, e - sl_m*atrv[ci], e + tp_m*atrv[ci], slip)
                if r is not None:
                    pooled[(tp_m, sl_m)].append(r - COMMISSION*2*e/(sl_m*atrv[ci]))

    print("\nMACD DIVERGENCE — win rate vs expectancy (pooled BTC/Gold/Oil, 1h)\n")
    print(f"{'TP(ATR)':>8}{'SL(ATR)':>8}{'R:R':>7}{'trades':>8}{'WIN%':>7}{'expR':>9}{'verdict':>12}")
    rows = []
    for (tp_m, sl_m), Rs in sorted(pooled.items(), key=lambda kv: -np.mean([1 if r > 0 else 0 for r in kv[1]]) if kv[1] else 0):
        if not Rs:
            continue
        Rs = np.array(Rs)
        win = 100 * np.mean(Rs > 0)
        exp = float(Rs.mean())
        rr = f"1:{tp_m/sl_m:.2f}"
        verdict = "PROFIT" if exp > 0 else "LOSES $"
        print(f"{tp_m:>8}{sl_m:>8}{rr:>7}{len(Rs):>8}{win:>6.0f}%{exp:>9.3f}{verdict:>12}")
        rows.append({"tp": tp_m, "sl": sl_m, "trades": len(Rs), "win_pct": round(win,0),
                     "expR": round(exp,3)})
    pd.DataFrame(rows).to_csv(OUT / "winrate_trap.csv", index=False)
    print("\nNote: as TP shrinks / SL widens, WIN% rises toward 100% but expR stays NEGATIVE.")


if __name__ == "__main__":
    main()
