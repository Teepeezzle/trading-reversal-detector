"""Walk-forward stability test of the validated daily long-breakout edge.

Two questions:
  (A) STABILITY: is the edge positive period-by-period across 26 years, or did
      one era carry a single IS/OOS split? Pool trades across the 6-asset basket
      and report expectancy per calendar year and per consecutive 3-year block.
  (B) ANTI-OVERFIT: a true rolling walk-forward that re-optimizes the Donchian
      length on each 5y train window and tests on the next 2y — compared with
      the FIXED Donchian-20. If fixed >= optimized, re-tuning adds nothing
      (overfits), confirming we should not optimize.

Fixed validated config: ADX<20 regime, close>DonchHigh(N)[1], close>SMA200,
SL 1.5*ATR, TP 3.0*ATR, one trade/asset, costs 0.05% + 2 ticks. Expectancy in R.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def fetch(ticker: str) -> Optional[pd.DataFrame]:
    for period in ("max", "15y", "10y"):
        for _ in range(3):
            try:
                raw = yf.download(ticker, period=period, interval="1d",
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


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def indicators(df, donch):
    up = df["High"].diff(); dn = -df["Low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, 14)
    pdi = 100 * wilder(pd.Series(pdm, index=df.index), 14) / atr
    mdi = 100 * wilder(pd.Series(mdm, index=df.index), 14) / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return atr.to_numpy(), wilder(dx.fillna(0), 14).to_numpy(), \
        df["Close"].rolling(200).mean().to_numpy(), \
        df["High"].rolling(donch).max().shift(1).to_numpy()


def gen_trades(df: pd.DataFrame, tick: float, donch: int) -> List[Tuple[pd.Timestamp, float]]:
    """All breakout trades -> list of (exit_date, R)."""
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    atrv, adxv, sma, dh = indicators(df, donch)
    idx = df.index
    slip = SLIP_TICKS * tick
    n = len(close)
    trades = []
    i = 210
    while i < n - 1:
        if np.isnan(atrv[i]) or atrv[i] <= 0 or np.isnan(adxv[i]) or np.isnan(dh[i]) or np.isnan(sma[i]):
            i += 1; continue
        if adxv[i] < ADX_RANGING and close[i] > dh[i] and close[i] > sma[i]:
            entry = close[i] + slip
            sl = entry - SL_MULT * atrv[i]; tp = entry + TP_MULT * atrv[i]
            risk = entry - sl
            r = None; ex = None
            for j in range(i + 1, min(i + 1 + MAX_HOLD, n)):
                if low[j] <= sl:
                    r = -(risk + slip) / risk; ex = j; break
                if high[j] >= tp:
                    r = (tp - entry) / risk; ex = j; break
            if r is None:
                ex = min(i + MAX_HOLD, n - 1); r = (close[ex] - entry) / risk
            trades.append((idx[ex], r - COMMISSION * 2 * entry / risk))
            i = ex + 1
        else:
            i += 1
    return trades


def stat(Rs):
    if not Rs:
        return None
    R = np.array(Rs); w = R[R > 0]; l = R[R <= 0]
    pf = w.sum() / -l.sum() if l.sum() < 0 else float("inf")
    return len(R), round(100*len(w)/len(R)), round(float(R.mean()), 3), \
        (round(pf, 2) if pf != float("inf") else "inf")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = {}
    for tk, (name, tick) in BASKET.items():
        df = fetch(tk)
        if df is not None:
            frames[tk] = (name, tick, df)
            print(f"  loaded {name}: {len(df)} bars")

    # ---- pooled trades, fixed Donchian=20 ----
    pooled = []
    for tk, (name, tick, df) in frames.items():
        for ex, r in gen_trades(df, tick, 20):
            pooled.append((ex, r))
    pooled.sort()
    tdf = pd.DataFrame(pooled, columns=["exit", "R"]).set_index("exit")

    print("\n================ (A) STABILITY — pooled expectancy by CALENDAR YEAR ================")
    print(f"  {'year':>6}{'n':>5}{'win%':>7}{'expR':>8}{'PF':>7}")
    pos_years = tot_years = 0
    for yr, g in tdf.groupby(tdf.index.year):
        s = stat(list(g["R"]))
        if s and s[0] >= 3:
            tot_years += 1
            pos_years += 1 if s[2] > 0 else 0
            print(f"  {yr:>6}{s[0]:>5}{s[1]:>6}%{s[2]:>8}{str(s[3]):>7}")
    print(f"\n  positive years: {pos_years}/{tot_years} ({100*pos_years/max(tot_years,1):.0f}%)")

    print("\n================ pooled expectancy by 3-YEAR BLOCK ================")
    print(f"  {'block':>11}{'n':>5}{'win%':>7}{'expR':>8}{'PF':>7}")
    yrs = sorted(set(tdf.index.year))
    y0, y1 = yrs[0], yrs[-1]
    pos_b = tot_b = 0
    for start in range(y0 - (y0 % 3), y1 + 1, 3):
        g = tdf[(tdf.index.year >= start) & (tdf.index.year < start + 3)]
        s = stat(list(g["R"]))
        if s and s[0] >= 5:
            tot_b += 1; pos_b += 1 if s[2] > 0 else 0
            print(f"  {f'{start}-{start+2}':>11}{s[0]:>5}{s[1]:>6}%{s[2]:>8}{str(s[3]):>7}")
    print(f"\n  positive blocks: {pos_b}/{tot_b} ({100*pos_b/max(tot_b,1):.0f}%)")

    # ---- (B) walk-forward optimization vs fixed ----
    print("\n================ (B) WALK-FORWARD: re-optimized Donchian vs FIXED-20 ================")
    print("  train 5y -> pick best Donchian{10,20,55} (pooled) -> test next 2y\n")
    print(f"  {'test window':>13}{'bestN':>7}{'opt expR':>10}{'fixed20 expR':>14}")
    by_asset_trades = {tk: {dl: gen_trades(df, tick, dl) for dl in (10, 20, 55)}
                       for tk, (name, tick, df) in frames.items()}

    def pooled_R(donch, lo, hi):
        out = []
        for tk in frames:
            for ex, r in by_asset_trades[tk][donch]:
                if lo <= ex.year < hi:
                    out.append(r)
        return out

    opt_all, fix_all = [], []
    for test_start in range(y0 + 5, y1 - 1, 2):
        tr_lo, tr_hi = test_start - 5, test_start
        best_n, best_e = 20, -9
        for dl in (10, 20, 55):
            R = pooled_R(dl, tr_lo, tr_hi)
            if len(R) >= 10 and np.mean(R) > best_e:
                best_e, best_n = np.mean(R), dl
        opt_test = pooled_R(best_n, test_start, test_start + 2)
        fix_test = pooled_R(20, test_start, test_start + 2)
        if opt_test and fix_test:
            opt_all += opt_test; fix_all += fix_test
            print(f"  {f'{test_start}-{test_start+1}':>13}{best_n:>7}"
                  f"{round(float(np.mean(opt_test)),3):>10}{round(float(np.mean(fix_test)),3):>14}")
    if opt_all and fix_all:
        print(f"\n  AGGREGATE  re-optimized expR={np.mean(opt_all):+.3f}  "
              f"vs  FIXED-20 expR={np.mean(fix_all):+.3f}")
        print("  -> " + ("fixed wins/ties: re-optimizing does NOT help (overfits)"
                          if np.mean(fix_all) >= np.mean(opt_all) - 0.02
                          else "re-optimizing helped this time"))


if __name__ == "__main__":
    main()
