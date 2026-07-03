"""New entry rule (v7): divergence + span 6-50 + close is NEAR the 200-SMA
regardless of which side (above OR below).

This DROPS the strict trend-alignment filter that v6 required (close>SMA for long,
close<SMA for short). Now the SMA is a proximity zone, not a directional gate:
  * Bull divergence + |close - SMA| <= K * ATR  ->  LONG
  * Bear divergence + |close - SMA| <= K * ATR  ->  SHORT

Everything else matches v6:
  * Span 6-50 pivot-to-pivot filter kept
  * SCALPR SL/TP: SL = 1.5 * ATR, TP = 3.0 * ATR
  * Exit-on-opposite ON, pyramiding 0, 100% equity per trade
  * 5 assets, 4H + 1H, ~2y intraday window (yfinance cap)

Reports A) raw H=20 hit rate by K, B) full strategy metrics with SCALPR SL/TP.
Head-to-head vs the previous v6 (trend-aligned) result is printed at the end.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

ASSETS = {"GC=F": "Gold", "SI=F": "Silver", "BTC-USD": "Bitcoin",
          "CL=F": "WTI Oil", "NQ=F": "NAS100"}
TICK = {"GC=F": 0.10, "SI=F": 0.005, "BTC-USD": 0.01, "CL=F": 0.01, "NQ=F": 0.25}
PIVOT_LEN = 5
SMA_LEN = 200
SPAN_LO, SPAN_HI = 6, 50
ATR_LEN = 14
SL_ATR = 1.5
TP_ATR = 3.0
H = 20
K_VALUES = [0.5, 1.0, 1.5, 2.0]
COMMISSION = 0.0005
SLIP_TICKS = 2
INITIAL_EQ = 10_000.0


def fetch(ticker, interval, periods) -> Optional[pd.DataFrame]:
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
            time.sleep(1.0)
    return None


def resample_4h(h):
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return h.resample("4h").agg(agg).dropna(subset=["Open", "High", "Low", "Close"])


def macd_line(c):
    return c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def atr_series(df, n=ATR_LEN):
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
            out.append((i + L, i, float(vals[i]), float(macd[i])))
    return out


def gen_signals(df, asset):
    """Divergences with span 6-50; direction from divergence type; NO trend
    alignment. dist_atr computed for filtering later. Also carry side info so
    we can post-hoc split by side if needed."""
    high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    close = df["Close"].to_numpy()
    macd = macd_line(df["Close"]).to_numpy()
    sma = df["Close"].rolling(SMA_LEN).mean().to_numpy()
    atr = atr_series(df).to_numpy()
    n = len(close); idx = df.index
    out = []
    for kind, direction in (("high", "short"), ("low", "long")):
        vals = high if kind == "high" else low
        pv = pivots(vals, macd, PIVOT_LEN, kind)
        for k in range(1, len(pv)):
            c1, i1, p1, m1 = pv[k - 1]
            c2, i2, p2, m2 = pv[k]
            reg = (p2 > p1 and m2 < m1) if direction == "short" else (p2 < p1 and m2 > m1)
            span = i2 - i1
            if not reg or not (SPAN_LO <= span <= SPAN_HI):
                continue
            if c2 >= n or not np.isfinite(sma[c2]) or not np.isfinite(atr[c2]) or atr[c2] <= 0:
                continue
            dist_atr = abs(close[c2] - sma[c2]) / atr[c2]
            side_above = close[c2] > sma[c2]
            trend_aligned = ((direction == "long" and side_above) or
                             (direction == "short" and not side_above))
            if c2 + H < n:
                fwd = (close[c2 + H] - close[c2]) / close[c2]
                tr_H = (fwd if direction == "long" else -fwd) * 100.0
            else:
                tr_H = np.nan
            out.append({"bar": c2, "dir": direction, "close": float(close[c2]),
                        "sma": float(sma[c2]), "atr": float(atr[c2]),
                        "dist_atr": float(dist_atr), "side_above": bool(side_above),
                        "trend_aligned": bool(trend_aligned),
                        "tr_H": float(tr_H), "asset": asset, "time": idx[c2]})
    return out


def simulate(df, sigs, tick, K):
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    n = len(close)
    trades = []
    open_trade = None
    slip = SLIP_TICKS * tick
    equity = INITIAL_EQ

    def close_trade(exit_bar, exit_price, reason):
        nonlocal open_trade, equity
        entry = open_trade["entry"]
        direction = open_trade["dir"]
        size = open_trade["size"]
        if direction == "long":
            pnl = size * (exit_price - entry) - COMMISSION * size * (entry + exit_price)
        else:
            pnl = size * (entry - exit_price) - COMMISSION * size * (entry + exit_price)
        equity += pnl
        trades.append({"dir": direction, "pnl": pnl, "reason": reason, "equity": equity})
        open_trade = None

    filt = [s for s in sigs if s["dist_atr"] <= K]
    filt.sort(key=lambda s: s["bar"])
    sig_iter = iter(filt)
    next_sig = next(sig_iter, None)

    for i in range(n):
        if open_trade is not None and i > open_trade["entry_bar"]:
            hi = high[i]; lo = low[i]
            if open_trade["dir"] == "long":
                hit_sl = lo <= open_trade["sl"]; hit_tp = hi >= open_trade["tp"]
            else:
                hit_sl = hi >= open_trade["sl"]; hit_tp = lo <= open_trade["tp"]
            if hit_sl:
                close_trade(i, open_trade["sl"] + (slip if open_trade["dir"] == "short" else -slip), "SL")
            elif hit_tp:
                close_trade(i, open_trade["tp"], "TP")

        while next_sig is not None and next_sig["bar"] == i:
            direction = next_sig["dir"]
            entry_price = next_sig["close"] + (slip if direction == "long" else -slip)
            if open_trade is not None and open_trade["dir"] != direction:
                close_trade(i, entry_price, "flip")
            if open_trade is None:
                size = equity / entry_price if entry_price > 0 else 0
                if size > 0:
                    atr_val = next_sig["atr"]
                    if direction == "long":
                        sl = entry_price - SL_ATR * atr_val
                        tp = entry_price + TP_ATR * atr_val
                    else:
                        sl = entry_price + SL_ATR * atr_val
                        tp = entry_price - TP_ATR * atr_val
                    open_trade = {"dir": direction, "entry_bar": i, "entry": entry_price,
                                  "sl": sl, "tp": tp, "size": size}
            next_sig = next(sig_iter, None)

    if open_trade is not None:
        close_trade(n - 1, close[n - 1], "end")
    return trades


def wilson_ci(hits, n):
    if n == 0:
        return (0.0, 0.0)
    p = hits / n
    z = 1.96; denom = 1 + z*z/n
    center = (p + z*z/(2*n)) / denom
    half = z * np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    return (max(0, (center - half) * 100), min(100, (center + half) * 100))


def strat_m(trades):
    if not trades:
        return None
    pnl = np.array([t["pnl"] for t in trades])
    wins = pnl[pnl > 0]; losses = pnl[pnl <= 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
    eq = np.array([t["equity"] for t in trades])
    eq_all = np.concatenate([[INITIAL_EQ], eq])
    peak = np.maximum.accumulate(eq_all)
    dd = 100 * (eq_all - peak) / peak
    return {"n": len(pnl), "win_pct": round(100 * len(wins) / len(pnl), 1),
            "pf": pf if pf == float("inf") else round(pf, 2),
            "net_pct": round(100 * (eq[-1] / INITIAL_EQ - 1), 1),
            "max_dd": round(float(dd.min()), 1),
            "final_eq": round(eq[-1], 0)}


def run_tf(tf):
    print(f"\n############################ TIMEFRAME: {tf} ############################")
    all_sigs = {}; dfs = {}
    for tk, name in ASSETS.items():
        h = fetch(tk, "1h", ("720d", "365d"))
        if h is None:
            print(f"  {name}: no data"); continue
        df = h if tf == "1h" else resample_4h(h)
        dfs[name] = (df, TICK.get(tk, 0.01))
        all_sigs[name] = gen_signals(df, name)

    # A) Raw H=20 hit rate by K (no side restriction, no trend alignment)
    print("\n  A) Raw H=20 hit rate — NO trend alignment, proximity to SMA only")
    print(f"     {'K (ATR)':<10}{'n':>5}{'hit%':>7}{'CI95':>14}{'mean%':>10}{'med%':>9}")
    for K in K_VALUES:
        pooled = []
        for name, sigs in all_sigs.items():
            for s in sigs:
                if s["dist_atr"] <= K and np.isfinite(s["tr_H"]):
                    pooled.append(s["tr_H"])
        if not pooled:
            print(f"     K={K:<7}   0"); continue
        arr = np.array(pooled)
        wins = (arr > 0).sum()
        ci = wilson_ci(wins, len(arr))
        print(f"     K={K:<7}{len(arr):>5}{100*wins/len(arr):>6.0f}%"
              f"{f'{ci[0]:>3.0f}-{ci[1]:>3.0f}%':>14}"
              f"{arr.mean():>10.3f}{np.median(arr):>9.3f}")

    # A2) Side split at K=1.0 to see if 'both sides' really matters
    print(f"\n  A2) At K=1.0 — split by SIDE (side_above / side_below)")
    print(f"     {'side':<10}{'n':>5}{'hit%':>7}{'CI95':>14}{'mean%':>10}")
    for tag, pred in (("above SMA", lambda s: s["side_above"]),
                       ("below SMA", lambda s: not s["side_above"])):
        pooled = [s["tr_H"] for name, sigs in all_sigs.items() for s in sigs
                  if s["dist_atr"] <= 1.0 and np.isfinite(s["tr_H"]) and pred(s)]
        if not pooled:
            print(f"     {tag:<10}   0"); continue
        arr = np.array(pooled); wins = (arr > 0).sum()
        ci = wilson_ci(wins, len(arr))
        print(f"     {tag:<10}{len(arr):>5}{100*wins/len(arr):>6.0f}%"
              f"{f'{ci[0]:>3.0f}-{ci[1]:>3.0f}%':>14}{arr.mean():>10.3f}")

    # A3) At K=1.0 — trend-aligned vs counter-trend (both included in v7 by design)
    print(f"\n  A3) At K=1.0 — split by TREND-ALIGNMENT")
    print(f"     {'align':<10}{'n':>5}{'hit%':>7}{'CI95':>14}{'mean%':>10}")
    for tag, pred in (("aligned",     lambda s: s["trend_aligned"]),
                       ("counter",    lambda s: not s["trend_aligned"])):
        pooled = [s["tr_H"] for name, sigs in all_sigs.items() for s in sigs
                  if s["dist_atr"] <= 1.0 and np.isfinite(s["tr_H"]) and pred(s)]
        if not pooled:
            print(f"     {tag:<10}   0"); continue
        arr = np.array(pooled); wins = (arr > 0).sum()
        ci = wilson_ci(wins, len(arr))
        print(f"     {tag:<10}{len(arr):>5}{100*wins/len(arr):>6.0f}%"
              f"{f'{ci[0]:>3.0f}-{ci[1]:>3.0f}%':>14}{arr.mean():>10.3f}")

    # B) Full strategy metrics at K = 1.0
    K_P = 1.0
    print(f"\n  B) Full strategy (SL {SL_ATR}xATR, TP {TP_ATR}xATR) — K={K_P}")
    print(f"     {'asset':<9}{'n':>5}{'win%':>7}{'PF':>7}{'net%':>8}{'maxDD':>8}{'finalEq':>10}")
    tot_final = 0; tot_init = 0
    for name, sigs in all_sigs.items():
        df, tick = dfs[name]
        trades = simulate(df, sigs, tick, K_P)
        m = strat_m(trades)
        if m is None:
            print(f"     {name:<9}   no trades"); continue
        print(f"     {name:<9}{m['n']:>5}{m['win_pct']:>6.1f}%"
              f"{str(m['pf']):>7}{m['net_pct']:>+7.1f}%{m['max_dd']:>+7.1f}%${m['final_eq']:>9,.0f}")
        tot_final += m["final_eq"]; tot_init += INITIAL_EQ
    if tot_init > 0:
        ret = 100 * (tot_final / tot_init - 1)
        print(f"\n     PORTFOLIO: ${tot_init:,.0f} -> ${tot_final:,.0f}  return {ret:+.1f}%")

    # K-sensitivity summary
    print(f"\n  K-sensitivity portfolio return (simple sum, $10k/asset):")
    for K in K_VALUES:
        tf_final = 0; tf_init = 0
        for name, sigs in all_sigs.items():
            df, tick = dfs[name]
            trades = simulate(df, sigs, tick, K)
            m = strat_m(trades)
            if m is None:
                continue
            tf_final += m["final_eq"]; tf_init += INITIAL_EQ
        if tf_init > 0:
            r = 100 * (tf_final / tf_init - 1)
            print(f"     K={K:>4}   return={r:+.1f}%")


def main():
    for tf in ("4h", "1h"):
        run_tf(tf)


if __name__ == "__main__":
    main()
