"""Out-of-sample validation of the DAILY LONG BREAKOUT (the one edge that passed).

The danger with any single positive backtest is that it's curve-fit to the
period. The honest check: split each asset's full daily history into
  IN-SAMPLE  (earliest 65%)  and  OUT-OF-SAMPLE (latest 35%).
If the edge survives on OOS data it never 'saw', it's plausibly durable.
If OOS collapses, it was regime luck -> do NOT trade it.

Strategy (the winning SCALPR component, isolated):
  * regime: ADX(14) < 20 (a low-ADX consolidation)
  * entry : close > Donchian-high(N)[1]  (breakout up out of the range)
  * risk  : SL = 1.5*ATR, TP = 3.0*ATR (1:2), one position at a time
  * macro variant: also require close > SMA200 (don't buy breakouts in a
    downtrend) — test whether it helps.

Also runs a small Donchian-length sweep on IN-SAMPLE only, locks the best, and
reports its OUT-OF-SAMPLE result — a true train/test to catch overfitting.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "backtest" / "results"
ASSETS = {"BTC-USD": ("Bitcoin", 0.01), "GC=F": ("Gold", 0.10), "CL=F": ("WTI Oil", 0.01)}
SL_MULT, TP_MULT = 1.5, 3.0
ADX_RANGING = 20.0
COMMISSION = 0.0005
SLIP_TICKS = 2
MAX_HOLD = 60
IS_FRACTION = 0.65


def fetch(ticker: str) -> Optional[pd.DataFrame]:
    for period in ("max", "20y", "10y"):
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
                if len(df) >= 800:
                    return df
            time.sleep(1.5)
    return None


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def adx(df, n=14):
    up = df["High"].diff()
    dn = -df["Low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, n)
    pdi = 100 * wilder(pd.Series(plus_dm, index=df.index), n) / atr
    mdi = 100 * wilder(pd.Series(minus_dm, index=df.index), n) / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return wilder(dx.fillna(0), n)


def atr_series(df, n=14):
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def build(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["atr"] = atr_series(df)
    out["adx"] = adx(df)
    out["sma200"] = df["Close"].rolling(200).mean()
    return out


def run_breakout(df: pd.DataFrame, donch: int, tick: float, use_macro: bool,
                 lo: int, hi: int) -> List[float]:
    """Return list of trade R-multiples over bar index range [lo, hi)."""
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    atrv = df["atr"].to_numpy()
    adxv = df["adx"].to_numpy()
    sma = df["sma200"].to_numpy()
    dHigh = pd.Series(high).rolling(donch).max().shift(1).to_numpy()
    slip = SLIP_TICKS * tick
    Rs: List[float] = []
    i = max(lo, 210)
    while i < hi - 1:
        if np.isnan(atrv[i]) or atrv[i] <= 0 or np.isnan(adxv[i]) or np.isnan(dHigh[i]):
            i += 1
            continue
        ranging = adxv[i] < ADX_RANGING
        macro_ok = (not use_macro) or (not np.isnan(sma[i]) and close[i] > sma[i])
        if ranging and close[i] > dHigh[i] and macro_ok:
            entry = close[i] + slip
            sl = entry - SL_MULT * atrv[i]
            tp = entry + TP_MULT * atrv[i]
            risk = entry - sl
            exit_i = None
            r = None
            for j in range(i + 1, min(i + 1 + MAX_HOLD, hi)):
                if low[j] <= sl:
                    r = -(risk + slip) / risk
                    exit_i = j
                    break
                if high[j] >= tp:
                    r = (tp - entry) / risk
                    exit_i = j
                    break
            if r is None:
                exit_i = min(i + MAX_HOLD, hi - 1)
                r = (close[exit_i] - entry) / risk
            Rs.append(r - COMMISSION * 2 * entry / risk)
            i = exit_i + 1
        else:
            i += 1
    return Rs


def stats(Rs: List[float]) -> dict:
    if not Rs:
        return {"n": 0, "win": "—", "expR": "—", "PF": "—", "totR": 0.0}
    R = np.array(Rs)
    w = R[R > 0]
    l = R[R <= 0]
    pf = w.sum() / -l.sum() if l.sum() < 0 else float("inf")
    return {"n": len(R), "win": round(100 * len(w) / len(R), 0),
            "expR": round(float(R.mean()), 3),
            "PF": round(pf, 2) if pf != float("inf") else "inf",
            "totR": round(float(R.sum()), 1)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pooled_is = {"base": [], "macro": []}
    pooled_oos = {"base": [], "macro": []}

    for ticker, (name, tick) in ASSETS.items():
        raw = fetch(ticker)
        if raw is None:
            print(f"[{name}] no data")
            continue
        df = build(raw)
        n = len(df)
        split = int(n * IS_FRACTION)
        is_start = df.index[210].date() if n > 210 else df.index[0].date()
        is_end = df.index[split].date()
        oos_end = df.index[-1].date()
        print(f"\n################ {name} ({ticker}) — {n} daily bars "
              f"| IS {is_start}->{is_end} | OOS {is_end}->{oos_end} ################")

        for use_macro, key in [(False, "base"), (True, "macro")]:
            is_R = run_breakout(df, 20, tick, use_macro, 0, split)
            oos_R = run_breakout(df, 20, tick, use_macro, split, n)
            pooled_is[key] += is_R
            pooled_oos[key] += oos_R
            si, so = stats(is_R), stats(oos_R)
            tag = "base " if key == "base" else "macro"
            print(f"  [{tag}] IN-SAMPLE : n={si['n']:>3} win={si['win']}% expR={si['expR']} PF={si['PF']} totR={si['totR']}")
            print(f"  [{tag}] OUT-SAMPLE: n={so['n']:>3} win={so['win']}% expR={so['expR']} PF={so['PF']} totR={so['totR']}")

        # Train/test: sweep Donchian on IS, lock best, report OOS (base)
        best_len, best_exp = None, -9.0
        for dl in (10, 20, 55):
            r = stats(run_breakout(df, dl, tick, False, 0, split))
            if r["n"] >= 10 and isinstance(r["expR"], float) and r["expR"] > best_exp:
                best_exp, best_len = r["expR"], dl
        if best_len:
            oos = stats(run_breakout(df, best_len, tick, False, split, n))
            print(f"  [train/test] best Donchian on IS = {best_len} (IS expR={best_exp}); "
                  f"its OOS -> n={oos['n']} win={oos['win']}% expR={oos['expR']} PF={oos['PF']}")

    print("\n\n================ POOLED IN-SAMPLE vs OUT-OF-SAMPLE ================")
    for key in ("base", "macro"):
        si, so = stats(pooled_is[key]), stats(pooled_oos[key])
        print(f"\n  --- {key} ---")
        print(f"    IN-SAMPLE : n={si['n']:>3} win={si['win']}% expR={si['expR']} PF={si['PF']} totR={si['totR']}")
        print(f"    OUT-SAMPLE: n={so['n']:>3} win={so['win']}% expR={so['expR']} PF={so['PF']} totR={so['totR']}")
        if isinstance(si["expR"], float) and isinstance(so["expR"], float):
            verdict = "HOLDS (durable)" if so["expR"] > 0.05 else ("WEAKENS" if so["expR"] > 0 else "COLLAPSES (was regime luck)")
            print(f"    VERDICT: {verdict}  (IS {si['expR']} -> OOS {so['expR']})")


if __name__ == "__main__":
    main()
