"""OODA round 4 — two DOCUMENTED anomalies (not parameter sweeps), tested with
anti-overfit discipline (one rule, whole basket, in-sample vs out-of-sample).

  E) INTRADAY MOMENTUM (Gao, Han, Li & Zhou, RFS 2018): the first half of a
     session's return predicts the second half. Tradeable: at mid-session, take
     a position in the direction of the morning move, exit at the session close
     (a session-close time stop), with an ATR stop for risk. R-based.

  F) OVERNIGHT EFFECT: hold close -> next open. Documented to capture most of
     the drift in equity indices with less volatility. Return-based, validated
     on ~25y of daily data, in-sample vs out-of-sample.

Discipline: a SINGLE pre-committed rule each (minimal grid), reported pooled AND
split IS(first 65%)/OOS(last 35%). Crossing +0.10 only counts if it ALSO holds
out-of-sample and is consistent across assets — otherwise it's noise.
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
COMMISSION = 0.0005
SLIP_TICKS = 2
MOM_THRESH = 0.001        # min morning move to act (pre-committed)
MOM_SL = 1.5              # ATR stop (pre-committed)
IS_FRAC = 0.65


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


def stat_R(Rs):
    if not Rs:
        return None
    R = np.array(Rs); w = R[R > 0]
    l = R[R <= 0]
    pf = w.sum()/-l.sum() if l.sum() < 0 else float("inf")
    return len(R), round(100*np.mean(R > 0)), round(float(R.mean()), 3), \
        (round(pf, 2) if pf != float("inf") else "inf")


# ---------------- E) Intraday momentum ----------------
def momentum_trades(h: pd.DataFrame, tick: float) -> List[Tuple[pd.Timestamp, float]]:
    close = h["Close"].to_numpy(); high = h["High"].to_numpy()
    low = h["Low"].to_numpy(); openp = h["Open"].to_numpy()
    atrv = atr_series(h).to_numpy()
    days = h.index.normalize()
    slip = SLIP_TICKS * tick
    by_day: Dict[pd.Timestamp, List[int]] = {}
    for i, d in enumerate(days):
        by_day.setdefault(d, []).append(i)
    out = []
    for d, idxs in by_day.items():
        if len(idxs) < 6:
            continue
        K = len(idxs) // 2
        sig_i = idxs[K - 1]
        if np.isnan(atrv[sig_i]) or atrv[sig_i] <= 0:
            continue
        morning = close[sig_i] / openp[idxs[0]] - 1.0
        if abs(morning) < MOM_THRESH:
            continue
        direction = "long" if morning > 0 else "short"
        entry = close[sig_i] + (slip if direction == "long" else -slip)
        risk = MOM_SL * atrv[sig_i]
        sl = entry - risk if direction == "long" else entry + risk
        # walk the rest of the session; stop or exit at session close
        r = None
        for j in idxs[K:]:
            if direction == "long" and low[j] <= sl:
                r = -(risk + slip) / risk; break
            if direction == "short" and high[j] >= sl:
                r = -(risk + slip) / risk; break
        if r is None:
            exit_px = close[idxs[-1]]
            r = ((exit_px - entry) if direction == "long" else (entry - exit_px)) / risk
        out.append((h.index[idxs[-1]], r - COMMISSION * 2 * entry / risk))
    return out


# ---------------- F) Overnight effect ----------------
def overnight_returns(daily: pd.DataFrame):
    o = daily["Open"].to_numpy(); c = daily["Close"].to_numpy()
    on = o[1:] / c[:-1] - 1.0            # close[t] -> open[t+1]
    intr = c[1:] / o[1:] - 1.0           # open[t+1] -> close[t+1]
    dates = daily.index[1:]
    return dates, on, intr


def ret_stats(r):
    r = np.asarray(r)
    if len(r) < 20:
        return None
    sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else float("nan")
    return len(r), round(100*np.mean(r > 0)), round(float(r.mean()*100), 4), round(float(sharpe), 2)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # ===== E) Intraday momentum =====
    print("################ E) INTRADAY MOMENTUM (morning -> close) ################")
    print(f"  rule: at mid-session, trade morning direction, exit at close, SL {MOM_SL}xATR")
    print(f"  {'asset':<11}{'IS n':>6}{'IS expR':>9}{'OOS n':>7}{'OOS expR':>10}")
    pooled_is, pooled_oos = [], []
    for tk, (name, tick) in BASKET.items():
        h = _fetch(tk, "1h", ("720d", "365d"))
        if h is None:
            print(f"  {name:<11}  no data")
            continue
        trades = momentum_trades(h, tick)
        if not trades:
            print(f"  {name:<11}  no trades")
            continue
        split = int(len(trades) * IS_FRAC)
        is_R = [r for _, r in trades[:split]]
        oos_R = [r for _, r in trades[split:]]
        pooled_is += is_R; pooled_oos += oos_R
        si, so = stat_R(is_R), stat_R(oos_R)
        print(f"  {name:<11}{(si[0] if si else 0):>6}{(si[2] if si else 0):>9}"
              f"{(so[0] if so else 0):>7}{(so[2] if so else 0):>10}")
    si, so = stat_R(pooled_is), stat_R(pooled_oos)
    if si and so:
        print(f"\n  POOLED IS : n={si[0]} win={si[1]}% expR={si[2]} PF={si[3]}")
        print(f"  POOLED OOS: n={so[0]} win={so[1]}% expR={so[2]} PF={so[3]}")
        verdict = ("EDGE (clears +0.10 OOS)" if so[2] > 0.10
                   else "below bar / likely noise" if so[2] > 0 else "loses OOS")
        print(f"  VERDICT: {verdict}")

    # ===== F) Overnight effect =====
    print("\n################ F) OVERNIGHT EFFECT (close -> next open) ################")
    print(f"  {'asset':<11}{'n':>6}{'ON win%':>9}{'ON mean%':>10}{'ON Sharpe':>11}{'  vs intraday mean%':>20}")
    for tk, (name, tick) in BASKET.items():
        daily = _fetch(tk, "1d", ("max", "15y"))
        if daily is None:
            print(f"  {name:<11}  no data")
            continue
        dates, on, intr = overnight_returns(daily)
        s_on = ret_stats(on); s_in = ret_stats(intr)
        if not s_on:
            continue
        # OOS check on overnight
        split = int(len(on) * IS_FRAC)
        oos = ret_stats(on[split:])
        oos_mean = oos[2] if oos else float("nan")
        print(f"  {name:<11}{s_on[0]:>6}{s_on[1]:>8}%{s_on[2]:>10}{s_on[3]:>11}"
              f"{(s_in[2] if s_in else 0):>13}   (OOS ON mean% {oos_mean})")
    print("\n  Note: overnight is a SHORT HOLD (hours), documented strong for equity indices.")
    print("  Daily breakout benchmark: +0.32-0.38 R.  +0.10 R OOS + consistent = worth building.")


if __name__ == "__main__":
    main()
