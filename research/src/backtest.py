"""Portable backtest engine (PHASE 3) — no-lookahead, net-of-cost, two horizons.

Hard rules enforced here:
- NO LOOK-AHEAD: a signal on bar t (computed from its close) is acted on at bar t+1's OPEN.
- NET OF COSTS: every trade deducts round-trip cost + overnight swap (research/src/costs.py).
- HORIZONS: 'intraday' = exit by same session close (session = UTC calendar day here — an
  approximation, documented); 'swing' = hard exit after `max_days` trading days, or SL/TP.
- One position at a time (no overlapping entries); SL-first on ambiguous bars (conservative).
Returns are expressed in R (R = net move / initial risk, initial risk = sl_mult*ATR at signal).

Also provides: time split (train/val/holdout), buy-&-hold and random-entry benchmarks, and a
stats summary (n, win%, expectancy, profit factor, max DD, Sharpe, avg hold).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DAY = np.timedelta64(1, "D")


def simulate(df: pd.DataFrame, entries: pd.Series, direction: str, atr: pd.Series,
             sl_mult: float, tp_mult: float, horizon: str, rt: float, swap_daily: float,
             max_days: int = 5) -> pd.DataFrame:
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy(); c = df["close"].to_numpy()
    tt = df["time"].to_numpy()
    dates = df["time"].dt.normalize().to_numpy()
    ent = entries.to_numpy(bool); av = atr.to_numpy()
    n = len(df); sgn = 1 if direction == "long" else -1
    trades = []; i = 0
    while i < n - 1:
        if not (ent[i] and np.isfinite(av[i]) and av[i] > 0):
            i += 1; continue
        ei = i + 1                                  # enter NEXT bar's open (no look-ahead)
        entry = o[ei]
        if not np.isfinite(entry):
            i += 1; continue
        risk = sl_mult * av[i]
        sl = entry - sgn * risk
        tp = entry + sgn * tp_mult * av[i]
        xi = exit_px = reason = None

        if horizon == "intraday":
            sess = dates[ei]
            for j in range(ei, n):
                if dates[j] != sess:
                    xi, exit_px, reason = j - 1, c[j - 1], "session_close"; break
                if sgn == 1:
                    if l[j] <= sl: xi, exit_px, reason = j, sl, "SL"; break
                    if h[j] >= tp: xi, exit_px, reason = j, tp, "TP"; break
                else:
                    if h[j] >= sl: xi, exit_px, reason = j, sl, "SL"; break
                    if l[j] <= tp: xi, exit_px, reason = j, tp, "TP"; break
            if xi is None:
                xi, exit_px, reason = n - 1, c[-1], "end"
        else:                                        # swing
            last = dates[ei]; days = 0
            for j in range(ei, n):
                if dates[j] != last:
                    days += 1; last = dates[j]
                if sgn == 1:
                    if l[j] <= sl: xi, exit_px, reason = j, sl, "SL"; break
                    if h[j] >= tp: xi, exit_px, reason = j, tp, "TP"; break
                else:
                    if h[j] >= sl: xi, exit_px, reason = j, sl, "SL"; break
                    if l[j] <= tp: xi, exit_px, reason = j, tp, "TP"; break
                if days >= max_days:
                    xi, exit_px, reason = j, c[j], "time"; break
            if xi is None:
                xi, exit_px, reason = n - 1, c[-1], "end"

        nights = int((dates[xi] - dates[ei]) / DAY)
        gross_R = sgn * (exit_px - entry) / risk
        cost_R = (rt * entry + swap_daily * entry * nights) / risk
        trades.append(dict(entry_time=pd.Timestamp(tt[ei]), exit_time=pd.Timestamp(tt[xi]),
                           dir=direction, entry=round(float(entry), 6), exit=round(float(exit_px), 6),
                           reason=reason, nights=nights, bars=int(xi - ei),
                           gross_R=round(float(gross_R), 4), net_R=round(float(gross_R - cost_R), 4)))
        i = xi + 1                                   # resume after exit (no overlap)
    return pd.DataFrame(trades)


def stats(trades: pd.DataFrame) -> dict:
    if trades is None or trades.empty:
        return dict(n=0, win=np.nan, expR=np.nan, pf=np.nan, maxdd_R=np.nan,
                    sharpe=np.nan, avg_bars=np.nan, totR=0.0)
    R = trades.net_R.to_numpy()
    pos, neg = R[R > 0].sum(), -R[R < 0].sum()
    cum = np.cumsum(R); dd = float((cum - np.maximum.accumulate(cum)).min())
    return dict(n=len(R), win=round(100 * (R > 0).mean(), 1),
                expR=round(float(R.mean()), 4),
                pf=round(float(pos / neg), 2) if neg > 0 else np.inf,
                maxdd_R=round(dd, 1), avg_bars=round(float(trades.bars.mean()), 1),
                sharpe=round(float(R.mean() / R.std(ddof=1)), 3) if len(R) > 1 and R.std(ddof=1) > 0 else np.nan,
                totR=round(float(R.sum()), 1))


def split_masks(df: pd.DataFrame, train=0.6, val=0.2):
    """Time-ordered 60/20/20. Holdout is the last 20% — DO NOT touch in Phase 3."""
    n = len(df); a = int(n * train); b = int(n * (train + val))
    t = df["time"]
    return {"train_end": t.iloc[a], "val_end": t.iloc[b]}


def tag_split(trades: pd.DataFrame, bounds: dict) -> pd.Series:
    def which(ts):
        if ts < bounds["train_end"]:
            return "train"
        if ts < bounds["val_end"]:
            return "val"
        return "holdout"
    return trades["entry_time"].map(which)


def buy_hold_pct(df: pd.DataFrame) -> float:
    c = df["close"].to_numpy()
    return round(100 * (c[-1] / c[0] - 1), 1)


def random_control(df, n_trades, direction, atr, sl_mult, tp_mult, horizon, rt, swap_daily,
                   max_days=5, iters=20, seed=7) -> dict:
    """Benchmark: same stop/target/horizon, entries placed at RANDOM bars. Averaged over iters."""
    rng = np.random.default_rng(seed); n = len(df)
    valid = np.where(np.isfinite(atr.to_numpy()) & (atr.to_numpy() > 0))[0]
    valid = valid[(valid > 20) & (valid < n - 2)]
    if len(valid) < n_trades or n_trades <= 0:
        return dict(expR=np.nan, win=np.nan, n=0)
    exps, wins = [], []
    for _ in range(iters):
        pick = np.sort(rng.choice(valid, size=min(n_trades, len(valid)), replace=False))
        e = pd.Series(False, index=df.index); e.iloc[pick] = True
        s = stats(simulate(df, e, direction, atr, sl_mult, tp_mult, horizon, rt, swap_daily, max_days))
        if s["n"]:
            exps.append(s["expR"]); wins.append(s["win"])
    return dict(expR=round(float(np.mean(exps)), 4) if exps else np.nan,
                win=round(float(np.mean(wins)), 1) if wins else np.nan, n=int(np.mean([len(valid)])))
