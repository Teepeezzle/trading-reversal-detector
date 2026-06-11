"""Validate the expansion before committing it.

Part A — BREAKOUT on a wide candidate universe (~30 liquid daily markets):
  run the validated daily breakout (ADX<20, Donchian-20 > prior, close>SMA200,
  SL 1.5xATR / TP 3xATR) on each and KEEP only those that are positive with a
  usable sample. Honest portfolio construction, not blind inclusion.

Part B — OVERNIGHT drift across the metals complex, NET OF COSTS and split
  in-sample / out-of-sample, to confirm which metals to trade close->open.

Slippage modelled as 2 bps of price (generic across instruments); commission
0.05% per trade for breakout, 0.02% round-trip for overnight (liquid futures).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "backtest" / "results"

CANDIDATES = {
    # crypto
    "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana",
    "BNB-USD": "BNB", "XRP-USD": "XRP", "LTC-USD": "Litecoin",
    # fx majors (no volume on yfinance, but breakout uses ADX/Donchian/SMA)
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY",
    "AUDUSD=X": "AUD/USD", "USDCAD=X": "USD/CAD",
    # metals
    "GC=F": "Gold", "SI=F": "Silver", "PL=F": "Platinum", "HG=F": "Copper",
    # energy
    "CL=F": "WTI Oil", "BZ=F": "Brent", "NG=F": "NatGas", "RB=F": "Gasoline",
    # equity indices
    "ES=F": "S&P500", "NQ=F": "Nasdaq100", "YM=F": "DowJones", "RTY=F": "Russell2000",
    # ags
    "ZC=F": "Corn", "ZW=F": "Wheat", "ZS=F": "Soybeans",
}
METALS = {"GC=F": "Gold", "SI=F": "Silver", "PL=F": "Platinum", "HG=F": "Copper"}

SL_MULT, TP_MULT = 1.5, 3.0
ADX_RANGING = 20.0
DONCH = 20
SLIP_BPS = 0.0002
COMMISSION = 0.0005
ON_COST = 0.0002
MAX_HOLD = 60
IS_FRAC = 0.65


def fetch(ticker, interval="1d"):
    for period in ("max", "15y", "10y", "5y"):
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
                if len(df) >= 300:
                    return df
            time.sleep(1.0)
    return None


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def breakout_trades(df):
    up = df["High"].diff(); dn = -df["Low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, 14).to_numpy()
    pdi = 100 * wilder(pd.Series(pdm, index=df.index), 14) / wilder(tr, 14)
    mdi = 100 * wilder(pd.Series(mdm, index=df.index), 14) / wilder(tr, 14)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    adxv = wilder(dx.fillna(0), 14).to_numpy()
    sma = df["Close"].rolling(200).mean().to_numpy()
    dh = df["High"].rolling(DONCH).max().shift(1).to_numpy()
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    n = len(close); Rs = []
    i = 210
    while i < n - 1:
        if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(adxv[i]) or np.isnan(dh[i]) or np.isnan(sma[i]):
            i += 1; continue
        if adxv[i] < ADX_RANGING and close[i] > dh[i] and close[i] > sma[i]:
            slip = SLIP_BPS * close[i]
            entry = close[i] + slip; sl = entry - SL_MULT*atr[i]; tp = entry + TP_MULT*atr[i]
            risk = entry - sl; r = None; ex = None
            for j in range(i+1, min(i+1+MAX_HOLD, n)):
                if low[j] <= sl:
                    r = -(risk+slip)/risk; ex = j; break
                if high[j] >= tp:
                    r = (tp-entry)/risk; ex = j; break
            if r is None:
                ex = min(i+MAX_HOLD, n-1); r = (close[ex]-entry)/risk
            Rs.append(r - COMMISSION*2*entry/risk); i = ex+1
        else:
            i += 1
    return Rs


def stat(Rs):
    if not Rs:
        return None
    R = np.array(Rs); w = R[R > 0]; l = R[R <= 0]
    pf = w.sum()/-l.sum() if l.sum() < 0 else float("inf")
    return len(R), round(100*np.mean(R > 0)), round(float(R.mean()), 3), \
        (round(pf, 2) if pf != float("inf") else "inf")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("################ PART A — BREAKOUT on candidate universe ################")
    print(f"  {'asset':<13}{'ticker':<10}{'n':>5}{'win%':>7}{'expR':>9}{'PF':>7}{'keep?':>7}")
    keep = []
    rows = []
    for tk, name in CANDIDATES.items():
        df = fetch(tk)
        if df is None:
            print(f"  {name:<13}{tk:<10}  no data")
            continue
        s = stat(breakout_trades(df))
        if not s:
            print(f"  {name:<13}{tk:<10}  no trades")
            continue
        keepit = s[2] > 0 and s[0] >= 12
        if keepit:
            keep.append((tk, name))
        print(f"  {name:<13}{tk:<10}{s[0]:>5}{s[1]:>6}%{s[2]:>9}{str(s[3]):>7}{('YES' if keepit else 'no'):>7}")
        rows.append({"ticker": tk, "name": name, "n": s[0], "win": s[1], "expR": s[2], "keep": keepit})
    print(f"\n  KEEP ({len(keep)}): " + ", ".join(t for t, _ in keep))
    pd.DataFrame(rows).to_csv(OUT / "expand_breakout.csv", index=False)

    print("\n################ PART B — OVERNIGHT drift across metals (net of cost, IS/OOS) ################")
    print(f"  {'metal':<11}{'n':>6}{'net mean%':>11}{'Sharpe':>8}{'IS mean%':>10}{'OOS mean%':>11}{'keep?':>7}")
    on_keep = []
    for tk, name in METALS.items():
        df = fetch(tk)
        if df is None:
            print(f"  {name:<11}  no data")
            continue
        o = df["Open"].to_numpy(); c = df["Close"].to_numpy()
        on = (o[1:] / c[:-1] - 1.0) - ON_COST
        if len(on) < 200:
            continue
        sharpe = on.mean() / on.std() * np.sqrt(252) if on.std() > 0 else float("nan")
        split = int(len(on) * IS_FRAC)
        is_m = on[:split].mean() * 100
        oos_m = on[split:].mean() * 100
        keepit = oos_m > 0 and on.mean() > 0
        if keepit:
            on_keep.append((tk, name))
        print(f"  {name:<11}{len(on):>6}{on.mean()*100:>10.4f}{sharpe:>8.2f}"
              f"{is_m:>10.4f}{oos_m:>11.4f}{('YES' if keepit else 'no'):>7}")
    print(f"\n  OVERNIGHT KEEP ({len(on_keep)}): " + ", ".join(t for t, _ in on_keep))


if __name__ == "__main__":
    main()
