"""Counter-trend pullback SCALP test.

Hypothesis (user's): in a confirmed trend, a MACD divergence reversal candle
produces a SMALL counter-trend move that can be scalped with a tight target and
a TIME STOP, exiting before the original trend resumes. This is the opposite of
holding for the 'big reversal' (which failed every prior test).

Setup (bearish scalp, taken only in an UPTREND):
  * Trend filter: EMA9 > EMA21 AND ADX > adx_min  (trending, per the user's
    SCALPR regime logic; the pattern is explicitly NOT for ranges).
  * Trigger: a new local high above the last confirmed pivot high (len=3) WITH
    MACD lower than at that pivot high (bearish divergence) AND a bearish
    candle (close < open). Enter SHORT at that bar's close.
  * Exit: TP = tp_mult x ATR (small), SL = sl_mult x ATR, or a TIME STOP after
    T bars at market — whichever comes first. Same-bar SL+TP -> SL (conservative).
Bullish mirror in a DOWNTREND.

Everything is non-repainting: the pivot reference is confirmed; entry uses only
the current closed bar. Costs: 0.05% commission round-trip-ish + 2-tick slippage.

Reported per config: trades, win%, avg R, expectancy (avg R = the number that
matters), profit factor. A scalp 'works' only if avg R > 0 after costs with a
usable sample.
"""

from __future__ import annotations

import sys
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "backtest" / "results"

ASSETS = {"BTC-USD": "Bitcoin", "GC=F": "Gold", "CL=F": "WTI Oil"}
TICK = {"BTC-USD": 0.01, "GC=F": 0.10, "CL=F": 0.01}

PIVOT_LEN = 3
ADX_MIN = 20.0
COMMISSION = 0.0005
SLIP_TICKS = 2

# Grid: small targets + short time stops (the scalp thesis)
TP_MULTS = [0.5, 1.0, 1.5]
SL_MULTS = [1.0, 1.5]
TIME_STOPS = [3, 5, 8]


def fetch(ticker: str) -> Optional[pd.DataFrame]:
    import time
    for period in ("720d", "700d", "365d"):
        for attempt in range(2):
            try:
                raw = yf.download(ticker, period=period, interval="1h",
                                  progress=False, auto_adjust=False, threads=False)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {ticker} {period} attempt {attempt+1}: {exc}")
                raw = None
            if raw is not None and not raw.empty:
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna(
                    subset=["Open", "High", "Low", "Close"])
                if df.index.tz is not None:
                    df.index = df.index.tz_convert("UTC").tz_localize(None)
                if len(df) >= 500:
                    print(f"  fetched {ticker}: {len(df)} 1h bars (period={period})")
                    return df
            time.sleep(1.5)
    return None


def macd_line(close: pd.Series) -> pd.Series:
    return close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()


def wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up = df["High"].diff()
    dn = -df["Low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr = wilder(tr, n)
    plus_di = 100 * wilder(pd.Series(plus_dm, index=df.index), n) / atr
    minus_di = 100 * wilder(pd.Series(minus_dm, index=df.index), n) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return wilder(dx.fillna(0), n)


def atr_series(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return wilder(tr, n)


def confirmed_pivots(values: np.ndarray, length: int, kind: str):
    """Return array aligned to bars: at bar i, the most recent CONFIRMED pivot
    value (confirmed = length bars after the extreme)."""
    n = len(values)
    piv_at_extreme = np.full(n, np.nan)
    for i in range(length, n - length):
        win = values[i - length:i + length + 1]
        if kind == "high" and values[i] == win.max():
            piv_at_extreme[i] = values[i]
        elif kind == "low" and values[i] == win.min():
            piv_at_extreme[i] = values[i]
    # shift forward by `length` so it's only KNOWN at confirmation, then ffill
    known = np.full(n, np.nan)
    for i in range(n):
        src = i - length
        if src >= 0 and not np.isnan(piv_at_extreme[src]):
            known[i] = piv_at_extreme[src]
    return pd.Series(known).ffill().to_numpy()


def simulate(close, high, low, openp, entry_i, direction, entry, sl, tp, tstop, slip):
    """Walk forward and return realized R (after slippage on stop)."""
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    n = len(close)
    for j in range(entry_i + 1, min(entry_i + 1 + tstop, n)):
        if direction == "short":
            if high[j] >= sl:                      # stop first (conservative)
                return -(risk + slip) / risk
            if low[j] <= tp:
                return (entry - tp) / risk
        else:
            if low[j] <= sl:
                return -(risk + slip) / risk
            if high[j] >= tp:
                return (tp - entry) / risk
    # time stop -> exit at close
    j = min(entry_i + tstop, n - 1)
    if direction == "short":
        return (entry - close[j]) / risk
    return (close[j] - entry) / risk


def run_asset(name, df):
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    openp = df["Open"].to_numpy()
    macd = macd_line(df["Close"]).to_numpy()
    ema9 = ta_ema(df["Close"], 9)
    ema21 = ta_ema(df["Close"], 21)
    adxv = adx(df).to_numpy()
    atrv = atr_series(df).to_numpy()
    pHigh = confirmed_pivots(high, PIVOT_LEN, "high")
    pLow = confirmed_pivots(low, PIVOT_LEN, "low")
    pHighMacd = pivot_macd(high, macd, PIVOT_LEN, "high")
    pLowMacd = pivot_macd(low, macd, PIVOT_LEN, "low")

    n = len(close)
    up = (ema9 > ema21) & (adxv > ADX_MIN)
    down = (ema9 < ema21) & (adxv > ADX_MIN)

    # collect entries (index, direction)
    shorts, longs = [], []
    for i in range(30, n - 1):
        if np.isnan(atrv[i]) or atrv[i] <= 0:
            continue
        # bearish scalp in uptrend
        if up[i] and not np.isnan(pHigh[i]) and not np.isnan(pHighMacd[i]):
            if high[i] > pHigh[i] and macd[i] < pHighMacd[i] and close[i] < openp[i]:
                shorts.append(i)
        # bullish scalp in downtrend
        if down[i] and not np.isnan(pLow[i]) and not np.isnan(pLowMacd[i]):
            if low[i] < pLow[i] and macd[i] > pLowMacd[i] and close[i] > openp[i]:
                longs.append(i)
    return dict(close=close, high=high, low=low, openp=openp, atrv=atrv,
                shorts=shorts, longs=longs, name=name, ticker_n=n)


def ta_ema(s: pd.Series, n: int) -> np.ndarray:
    return s.ewm(span=n, adjust=False).mean().to_numpy()


def pivot_macd(values, macd, length, kind):
    n = len(values)
    at = np.full(n, np.nan)
    for i in range(length, n - length):
        win = values[i - length:i + length + 1]
        if (kind == "high" and values[i] == win.max()) or (kind == "low" and values[i] == win.min()):
            at[i] = macd[i]
    known = np.full(n, np.nan)
    for i in range(n):
        src = i - length
        if src >= 0 and not np.isnan(at[src]):
            known[i] = at[src]
    return pd.Series(known).ffill().to_numpy()


def evaluate_grid(data, tick):
    close, high, low = data["close"], data["high"], data["low"]
    openp, atrv = data["openp"], data["atrv"]
    slip = SLIP_TICKS * tick
    results = []
    for tp_m, sl_m, T in product(TP_MULTS, SL_MULTS, TIME_STOPS):
        Rs = []
        for i in data["shorts"]:
            entry = close[i] - slip  # adverse fill
            a = atrv[i]
            sl = entry + sl_m * a
            tp = entry - tp_m * a
            r = simulate(close, high, low, openp, i, "short", entry, sl, tp, T, slip)
            if r is not None:
                Rs.append(r - COMMISSION * 2 * entry / (sl_m * a))
        for i in data["longs"]:
            entry = close[i] + slip
            a = atrv[i]
            sl = entry - sl_m * a
            tp = entry + tp_m * a
            r = simulate(close, high, low, openp, i, "long", entry, sl, tp, T, slip)
            if r is not None:
                Rs.append(r - COMMISSION * 2 * entry / (sl_m * a))
        if not Rs:
            continue
        Rs = np.array(Rs)
        wins = Rs[Rs > 0]
        losses = Rs[Rs <= 0]
        pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
        results.append({
            "tp": tp_m, "sl": sl_m, "T": T, "n": len(Rs),
            "win%": round(100 * len(wins) / len(Rs), 0),
            "avgR": round(float(Rs.mean()), 3),
            "totR": round(float(Rs.sum()), 1),
            "PF": round(pf, 2) if pf != float("inf") else "inf",
        })
    return results


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    pooled: Dict[tuple, List[float]] = {}
    for ticker, name in ASSETS.items():
        df = fetch(ticker)
        if df is None or len(df) < 500:
            print(f"[{name}] insufficient data")
            continue
        data = run_asset(name, df)
        res = evaluate_grid(data, TICK[ticker])
        res.sort(key=lambda r: r["avgR"], reverse=True)
        print(f"\n################ {name} ({ticker}) — {data['ticker_n']} 1h bars, "
              f"{len(data['shorts'])} short + {len(data['longs'])} long scalp triggers ################")
        print("  best configs by avg R (after costs):")
        print(f"  {'tp':>4}{'sl':>5}{'T':>4}{'n':>6}{'win%':>7}{'avgR':>8}{'totR':>8}{'PF':>7}")
        for r in res[:6]:
            print(f"  {r['tp']:>4}{r['sl']:>5}{r['T']:>4}{r['n']:>6}{r['win%']:>7}"
                  f"{r['avgR']:>8}{r['totR']:>8}{str(r['PF']):>7}")
        for r in res:
            r2 = dict(r); r2["asset"] = name
            all_rows.append(r2)
            pooled.setdefault((r["tp"], r["sl"], r["T"]), []).append(r["avgR"])

    print("\n\n================ POOLED — mean avg-R across the 3 assets per config ================")
    print("  (positive AND consistent across assets = a real scalp edge)")
    print(f"  {'tp':>4}{'sl':>5}{'T':>4}{'meanAvgR':>10}{'assets+':>9}")
    pooled_rows = []
    for key, vals in pooled.items():
        mean_r = float(np.mean(vals))
        pos = sum(1 for v in vals if v > 0)
        pooled_rows.append((key, mean_r, pos, len(vals)))
    pooled_rows.sort(key=lambda x: x[1], reverse=True)
    for (tp_m, sl_m, T), mean_r, pos, tot in pooled_rows:
        print(f"  {tp_m:>4}{sl_m:>5}{T:>4}{round(mean_r,3):>10}{f'{pos}/{tot}':>9}")

    if all_rows:
        pd.DataFrame(all_rows).to_csv(OUT / "scalp_study.csv", index=False)
        print(f"\nSaved {OUT / 'scalp_study.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
