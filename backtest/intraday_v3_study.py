"""OODA round 3 — the two market-maker-flavored intraday ideas not yet tested:

  C) VWAP MEAN-REVERSION (the retail analog of market-making): in a ranging
     session, when price is stretched far from session VWAP (fair value) and a
     reversal bar prints, fade it back toward VWAP. Long below, short above.

  D) OPENING-RANGE BREAKOUT (session momentum): the first N hours set a range;
     trade a break of it in the direction of the daily trend.

Both use session/VWAP structure, NOT divergence or static levels. Honest test:
pooled expectancy across the basket, non-repainting, costs 0.05% + 2 ticks.
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

# C) VWAP reversion grid
DEV_K = [1.5, 2.0, 2.5]          # how stretched from VWAP (in ATR) to act
C_SL = [1.0, 1.5]
C_TP = [1.0, 1.5, 2.0]
C_T = [12, 24]
ADX_RANGE_MAX = 25.0

# D) ORB grid
OR_BARS = [2, 3]                 # first N hourly bars define the range
D_SL = [1.0, 1.5]
D_TP = [2.0, 3.0]
D_T = [12, 24]


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


def atr_series(df, n=14):
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def adx_series(df, n=14):
    up = df["High"].diff(); dn = -df["Low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, n)
    pdi = 100 * wilder(pd.Series(pdm, index=df.index), n) / atr
    mdi = 100 * wilder(pd.Series(mdm, index=df.index), n) / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return wilder(dx.fillna(0), n)


def session_vwap(df: pd.DataFrame) -> np.ndarray:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    pv = tp * df["Volume"]
    day = df.index.normalize()
    cum_pv = pv.groupby(day).cumsum()
    cum_v = df["Volume"].groupby(day).cumsum().replace(0, np.nan)
    return (cum_pv / cum_v).to_numpy()


def macro_map(daily: pd.DataFrame) -> Dict[pd.Timestamp, int]:
    sma = daily["Close"].rolling(200).mean()
    up = (daily["Close"] > sma).shift(1)
    out = {}
    for d in daily.index:
        v = up.get(d, np.nan)
        out[d.normalize()] = (1 if (pd.notna(v) and v) else (-1 if pd.notna(v) else 0))
    return out


def sim(close, high, low, i, direction, entry, sl, tp, T, slip):
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    n = len(close)
    for j in range(i + 1, min(i + 1 + T, n)):
        if direction == "long":
            if low[j] <= sl:
                return -(risk + slip) / risk
            if high[j] >= tp:
                return (tp - entry) / risk
        else:
            if high[j] >= sl:
                return -(risk + slip) / risk
            if low[j] <= tp:
                return (entry - tp) / risk
    j = min(i + T, n - 1)
    return ((close[j] - entry) if direction == "long" else (entry - close[j])) / risk


def stat(Rs):
    if not Rs:
        return None
    R = np.array(Rs); w = R[R > 0]; l = R[R <= 0]
    pf = w.sum()/-l.sum() if l.sum() < 0 else float("inf")
    return len(R), round(100*np.mean(R > 0)), round(float(R.mean()), 3), \
        (round(pf, 2) if pf != float("inf") else "inf")


def run_vwap(h, tick):
    close = h["Close"].to_numpy(); high = h["High"].to_numpy(); low = h["Low"].to_numpy()
    openp = h["Open"].to_numpy()
    atrv = atr_series(h).to_numpy(); adxv = adx_series(h).to_numpy()
    vwap = session_vwap(h)
    slip = SLIP_TICKS * tick
    pooled = {c: [] for c in product(DEV_K, C_SL, C_TP, C_T)}
    for k, sl_m, tp_m, T in pooled:
        Rs = []
        for i in range(30, len(close) - 1):
            if np.isnan(atrv[i]) or atrv[i] <= 0 or np.isnan(vwap[i]) or np.isnan(adxv[i]):
                continue
            if adxv[i] > ADX_RANGE_MAX:
                continue
            dev = (close[i] - vwap[i]) / atrv[i]
            if dev <= -k and close[i] > openp[i]:          # stretched below + up bar -> long
                e = close[i] + slip
                r = sim(close, high, low, i, "long", e, e - sl_m*atrv[i], e + tp_m*atrv[i], T, slip)
            elif dev >= k and close[i] < openp[i]:          # stretched above + down bar -> short
                e = close[i] - slip
                r = sim(close, high, low, i, "short", e, e + sl_m*atrv[i], e - tp_m*atrv[i], T, slip)
            else:
                continue
            if r is not None:
                Rs.append(r - COMMISSION * 2 * e / (sl_m*atrv[i]))
        pooled[(k, sl_m, tp_m, T)] = Rs
    return pooled


def run_orb(h, tick, macro):
    close = h["Close"].to_numpy(); high = h["High"].to_numpy(); low = h["Low"].to_numpy()
    atrv = atr_series(h).to_numpy()
    days = h.index.normalize()
    slip = SLIP_TICKS * tick
    # group bar positions by day
    day_groups: Dict[pd.Timestamp, List[int]] = {}
    for i, d in enumerate(days):
        day_groups.setdefault(d, []).append(i)
    pooled = {c: [] for c in product(OR_BARS, D_SL, D_TP, D_T)}
    for nbar, sl_m, tp_m, T in pooled:
        Rs = []
        for d, idxs in day_groups.items():
            if len(idxs) < nbar + 2:
                continue
            tr = macro.get(d, 0)
            or_hi = max(high[j] for j in idxs[:nbar])
            or_lo = min(low[j] for j in idxs[:nbar])
            fired = False
            for i in idxs[nbar:]:
                if fired or np.isnan(atrv[i]) or atrv[i] <= 0:
                    continue
                if tr > 0 and close[i] > or_hi:             # long breakout in uptrend
                    e = close[i] + slip
                    r = sim(close, high, low, i, "long", e, e - sl_m*atrv[i], e + tp_m*atrv[i], T, slip)
                    fired = True
                elif tr < 0 and close[i] < or_lo:           # short breakout in downtrend
                    e = close[i] - slip
                    r = sim(close, high, low, i, "short", e, e + sl_m*atrv[i], e - tp_m*atrv[i], T, slip)
                    fired = True
                else:
                    continue
                if r is not None:
                    Rs.append(r - COMMISSION * 2 * e / (sl_m*atrv[i]))
        pooled[(nbar, sl_m, tp_m, T)] = Rs
    return pooled


def report(title, per_asset_pooled):
    print(f"\n################ {title} ################")
    # merge pooled across assets
    merged: Dict = {}
    print(f"  {'asset':<11}{'bestCfg':>22}{'n':>5}{'win%':>7}{'expR':>9}")
    for name, pooled in per_asset_pooled.items():
        best = None
        for cfg, Rs in pooled.items():
            merged.setdefault(cfg, []).extend(Rs)
            s = stat(Rs)
            if s and (best is None or s[2] > best[1][2]):
                best = (cfg, s)
        if best:
            print(f"  {name:<11}{str(best[0]):>22}{best[1][0]:>5}{best[1][1]:>6}%{best[1][2]:>9}")
    print(f"  -- POOLED, top configs by expR --")
    print(f"  {'cfg':>22}{'n':>6}{'win%':>7}{'expR':>9}{'PF':>7}{'verdict':>9}")
    for cfg, Rs in sorted(merged.items(), key=lambda kv: -(np.mean(kv[1]) if kv[1] else -9))[:5]:
        s = stat(Rs)
        if not s:
            continue
        v = "EDGE" if s[2] > 0.10 and s[0] >= 40 else ("+" if s[2] > 0 else "loses")
        print(f"  {str(cfg):>22}{s[0]:>6}{s[1]:>6}%{s[2]:>9}{str(s[3]):>7}{v:>9}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    vwap_all, orb_all = {}, {}
    for tk, (name, tick) in BASKET.items():
        h = _fetch(tk, "1h", ("720d", "365d"))
        daily = _fetch(tk, "1d", ("3y", "5y"))
        if h is None or daily is None:
            print(f"  {name}: missing data, skipped")
            continue
        print(f"  loaded {name}: {len(h)} 1h bars")
        vwap_all[name] = run_vwap(h, tick)
        orb_all[name] = run_orb(h, tick, macro_map(daily))
    report("C) VWAP MEAN-REVERSION (market-maker style)", vwap_all)
    report("D) OPENING-RANGE BREAKOUT (session momentum)", orb_all)
    print("\n  Daily benchmark: +0.32 to +0.38 R.  (>0.10 pooled + consistent = worth building)")


if __name__ == "__main__":
    main()
