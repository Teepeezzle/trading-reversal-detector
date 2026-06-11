"""Backtest the SCALPR AI logic AS A STRATEGY (it ships as an indicator, so its
real expectancy has never been measured).

Faithful to the script's rules:
  Regime: isRanging = ADX(14) < 20 ; trending = ADX >= 20.
  TREND entries (only when trending):
     LONG  = bullTrend(ema9>ema21) and (RSI crosses up 20  OR golden cross)
     SHORT = bearTrend(ema9<ema21) and (RSI crosses down 80 OR death cross)
  BREAKOUT entries (only when ranging):
     LONG  = close > Donchian_high(20)[1]
     SHORT = close < Donchian_low(20)[1]
  Risk: SL = 1.5*ATR, TP = 3.0*ATR  (fixed 1:2 R:R from the script).
One position at a time. Entry at signal-bar close with adverse slippage.
Costs: 0.05% commission (round-trip-ish) + 2 ticks slippage.

Reported per asset/timeframe and split by direction x signal-type so you can see
WHICH part of your script (trend-cross vs breakout, long vs short) carries it.
Break-even win rate at 1:2 R:R is 33.3%.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "backtest" / "results"

ASSETS = {"BTC-USD": "Bitcoin", "GC=F": "Gold", "CL=F": "WTI Oil"}
TICK = {"BTC-USD": 0.01, "GC=F": 0.10, "CL=F": 0.01}

SL_MULT, TP_MULT = 1.5, 3.0
ADX_RANGING = 20.0
DONCHIAN = 20
COMMISSION = 0.0005
SLIP_TICKS = 2
MAX_HOLD = 300


def fetch(ticker: str, interval: str, periods: Tuple[str, ...]) -> Optional[pd.DataFrame]:
    for period in periods:
        for _ in range(2):
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
                if len(df) >= 400:
                    return df
            time.sleep(1.0)
    return None


def resample_4h(h: pd.DataFrame) -> pd.DataFrame:
    """Resample 1h -> 4h (first/max/min/last/sum)."""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return h.resample("4h").agg(agg).dropna(subset=["Open", "High", "Low", "Close"])


def wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up = df["High"].diff()
    dn = -df["Low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, n)
    plus_di = 100 * wilder(pd.Series(plus_dm, index=df.index), n) / atr
    minus_di = 100 * wilder(pd.Series(minus_dm, index=df.index), n) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return wilder(dx.fillna(0), n)


def atr_series(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def simulate(close, high, low, i, direction, entry, sl, tp, slip):
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    n = len(close)
    for j in range(i + 1, min(i + 1 + MAX_HOLD, n)):
        if direction == "long":
            if low[j] <= sl:
                return j, -(risk + slip) / risk
            if high[j] >= tp:
                return j, (tp - entry) / risk
        else:
            if high[j] >= sl:
                return j, -(risk + slip) / risk
            if low[j] <= tp:
                return j, (entry - tp) / risk
    j = min(i + MAX_HOLD, n - 1)
    r = (close[j] - entry) / risk if direction == "long" else (entry - close[j]) / risk
    return j, r


def run(df: pd.DataFrame, tick: float) -> List[dict]:
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    ema9 = df["Close"].ewm(span=9, adjust=False).mean().to_numpy()
    ema21 = df["Close"].ewm(span=21, adjust=False).mean().to_numpy()
    rsi = (100 - 100 / (1 + (df["Close"].diff().clip(lower=0).ewm(alpha=1/14, adjust=False).mean() /
           (-df["Close"].diff().clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()))).to_numpy()
    adxv = adx(df).to_numpy()
    atrv = atr_series(df).to_numpy()
    dHigh = df["High"].rolling(DONCHIAN).max().to_numpy()
    dLow = df["Low"].rolling(DONCHIAN).min().to_numpy()

    slip = SLIP_TICKS * tick
    n = len(close)
    trades: List[dict] = []
    i = 30
    while i < n - 1:
        if np.isnan(atrv[i]) or atrv[i] <= 0 or np.isnan(adxv[i]):
            i += 1
            continue
        ranging = adxv[i] < ADX_RANGING
        bull = ema9[i] > ema21[i]
        bear = ema9[i] < ema21[i]
        golden = ema9[i] > ema21[i] and ema9[i-1] <= ema21[i-1]
        death = ema9[i] < ema21[i] and ema9[i-1] >= ema21[i-1]
        rsi_up = rsi[i] > 20 and rsi[i-1] <= 20
        rsi_dn = rsi[i] < 80 and rsi[i-1] >= 80

        long_trend = (not ranging) and bull and (rsi_up or golden)
        short_trend = (not ranging) and bear and (rsi_dn or death)
        long_bo = ranging and not np.isnan(dHigh[i-1]) and close[i] > dHigh[i-1]
        short_bo = ranging and not np.isnan(dLow[i-1]) and close[i] < dLow[i-1]

        direction = stype = None
        if long_trend or long_bo:
            direction, stype = "long", ("trend" if long_trend else "breakout")
        elif short_trend or short_bo:
            direction, stype = "short", ("trend" if short_trend else "breakout")

        if direction is None:
            i += 1
            continue

        a = atrv[i]
        if direction == "long":
            entry = close[i] + slip
            sl, tp = entry - SL_MULT * a, entry + TP_MULT * a
        else:
            entry = close[i] - slip
            sl, tp = entry + SL_MULT * a, entry - TP_MULT * a

        out = simulate(close, high, low, i, direction, entry, sl, tp, slip)
        if out is None:
            i += 1
            continue
        exit_i, r = out
        r -= COMMISSION * 2 * entry / (SL_MULT * a)
        trades.append({"dir": direction, "type": stype, "R": r})
        i = exit_i + 1  # one position at a time
    return trades


def summarize(trades: List[dict], label: str) -> dict:
    if not trades:
        print(f"  {label:<22} no trades")
        return {}
    R = np.array([t["R"] for t in trades])
    wins = R[R > 0]
    losses = R[R <= 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
    # max drawdown in R
    eq = np.cumsum(R)
    peak = np.maximum.accumulate(np.concatenate([[0], eq]))
    dd = (np.concatenate([[0], eq]) - peak).min()
    exp = float(R.mean())
    print(f"  {label:<22} n={len(R):>4}  win={100*len(wins)/len(R):4.0f}%  "
          f"expR={exp:+.3f}  totR={R.sum():+7.1f}  PF={pf if pf==float('inf') else round(pf,2)}  "
          f"maxDD={dd:.1f}R")
    return {"label": label, "n": len(R), "win_%": round(100*len(wins)/len(R), 0),
            "expR": round(exp, 3), "totR": round(float(R.sum()), 1),
            "PF": round(pf, 2) if pf != float("inf") else "inf", "maxDD_R": round(dd, 1)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    plans = [("1h", ("720d", "365d")), ("4h", ("720d", "365d")), ("1d", ("10y",))]
    rows = []
    for ticker, name in ASSETS.items():
        for tf, periods in plans:
            if tf == "4h":
                hourly = fetch(ticker, "1h", periods)
                df = resample_4h(hourly) if hourly is not None else None
            else:
                df = fetch(ticker, tf, periods)
            if df is None:
                print(f"[{name} {tf}] no data")
                continue
            trades = run(df, TICK[ticker])
            print(f"\n################ {name} ({ticker}) {tf} — {len(df)} bars ################")
            r = summarize(trades, "ALL")
            if r:
                r.update(asset=name, tf=tf); rows.append(r)
            for d in ("long", "short"):
                for st in ("trend", "breakout"):
                    sub = [t for t in trades if t["dir"] == d and t["type"] == st]
                    rr = summarize(sub, f"{d}/{st}")
                    if rr:
                        rr.update(asset=name, tf=tf); rows.append(rr)
    if rows:
        pd.DataFrame(rows).to_csv(OUT / "scalpr_strategy.csv", index=False)
        print(f"\nSaved {OUT / 'scalpr_strategy.csv'}")
        print("\nNote: break-even win rate at 1.5/3.0 ATR (1:2 R:R) is 33.3%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
