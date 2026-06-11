"""Can the VALIDATED daily breakout be used intraday? Test the exact config
(ADX<20 regime, Donchian-20 breakout, 200-period SMA macro filter, 1.5/3.0 ATR)
on 1h and 4h across the basket, and compare to its daily benchmark.

Data caveat: yfinance intraday is capped (~1-2y of 1h), so these samples are
recent-regime only and smaller than the 25y daily test.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "backtest" / "results"
BASKET = {"BTC-USD": ("Bitcoin", 0.01), "ETH-USD": ("Ethereum", 0.01),
          "GC=F": ("Gold", 0.10), "SI=F": ("Silver", 0.005),
          "CL=F": ("WTI Oil", 0.01), "NQ=F": ("Nasdaq100", 0.25)}
SL_MULT, TP_MULT = 1.5, 3.0
ADX_RANGING = 20.0
COMMISSION = 0.0005
SLIP_TICKS = 2
MAX_HOLD = 60


def fetch_1h(ticker: str) -> Optional[pd.DataFrame]:
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
                if df.index.tz is not None:
                    df.index = df.index.tz_convert("UTC").tz_localize(None)
                if len(df) >= 500:
                    return df
            time.sleep(1.2)
    return None


def to_4h(h: pd.DataFrame) -> pd.DataFrame:
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return h.resample("4h").agg(agg).dropna(subset=["Open", "High", "Low", "Close"])


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def gen_trades(df: pd.DataFrame, tick: float, donch: int = 20) -> List[Tuple[pd.Timestamp, float]]:
    up = df["High"].diff(); dn = -df["Low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, 14).to_numpy()
    pdi = 100 * wilder(pd.Series(pdm, index=df.index), 14) / wilder(tr, 14)
    mdi = 100 * wilder(pd.Series(mdm, index=df.index), 14) / wilder(tr, 14)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    adxv = wilder(dx.fillna(0), 14).to_numpy()
    sma = df["Close"].rolling(200).mean().to_numpy()
    dh = df["High"].rolling(donch).max().shift(1).to_numpy()
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    idx = df.index; slip = SLIP_TICKS * tick; n = len(close)
    trades = []
    i = 210
    while i < n - 1:
        if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(adxv[i]) or np.isnan(dh[i]) or np.isnan(sma[i]):
            i += 1; continue
        if adxv[i] < ADX_RANGING and close[i] > dh[i] and close[i] > sma[i]:
            entry = close[i] + slip; sl = entry - SL_MULT*atr[i]; tp = entry + TP_MULT*atr[i]
            risk = entry - sl; r = None; ex = None
            for j in range(i+1, min(i+1+MAX_HOLD, n)):
                if low[j] <= sl:
                    r = -(risk+slip)/risk; ex = j; break
                if high[j] >= tp:
                    r = (tp-entry)/risk; ex = j; break
            if r is None:
                ex = min(i+MAX_HOLD, n-1); r = (close[ex]-entry)/risk
            trades.append((idx[ex], r - COMMISSION*2*entry/risk)); i = ex+1
        else:
            i += 1
    return trades


def stat(Rs):
    if not Rs:
        return None
    R = np.array(Rs); w = R[R > 0]; l = R[R <= 0]
    pf = w.sum()/-l.sum() if l.sum() < 0 else float("inf")
    return len(R), round(100*len(w)/len(R)), round(float(R.mean()), 3), \
        (round(pf, 2) if pf != float("inf") else "inf")


def main():
    for tf in ("1h", "4h"):
        print(f"\n################ VALIDATED BREAKOUT on {tf} ################")
        print(f"  {'asset':<11}{'n':>5}{'win%':>7}{'expR':>9}{'PF':>7}")
        pooled = []
        for tk, (name, tick) in BASKET.items():
            h = fetch_1h(tk)
            if h is None:
                print(f"  {name:<11}  no data")
                continue
            df = h if tf == "1h" else to_4h(h)
            tr = gen_trades(df, tick)
            pooled += [r for _, r in tr]
            s = stat([r for _, r in tr])
            if s:
                print(f"  {name:<11}{s[0]:>5}{s[1]:>6}%{s[2]:>9}{str(s[3]):>7}")
            else:
                print(f"  {name:<11}    0  (no trades)")
        ps = stat(pooled)
        if ps:
            v = "PROFIT" if ps[2] > 0 else "LOSES"
            print(f"  {'POOLED':<11}{ps[0]:>5}{ps[1]:>6}%{ps[2]:>9}{str(ps[3]):>7}   -> {v}")
    print("\n  Daily benchmark (validated): pooled OOS expR +0.32 to +0.38, PF ~1.6-1.7.")


if __name__ == "__main__":
    main()
