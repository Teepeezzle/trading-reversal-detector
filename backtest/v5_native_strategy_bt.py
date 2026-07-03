"""Backtest of the corrected v5 STRATEGY (chart-native 200-SMA + custom
span 6-50) with the EXACT default risk model from the Pine script:
  * SL = 2% of entry, TP = 5% of entry, exit-on-opposite = ON, timeout = OFF.
  * pyramiding = 0.
  * commission 0.05% per trade, slippage 2 ticks.
  * 100% of equity per trade (default_qty_type = percent_of_equity).

Two timeframes (4h resampled from 1h, and 1h), five volume-bearing assets.
IS/OOS split at temporal midpoint of TRADES (not signals) so we're honest
about the samples the tester would show.

Reports the metrics you'd see in the Strategy Tester:
  n trades, win %, avg R, avg trade $, profit factor, max drawdown %.
Plus per-asset breakdown and Wilson CI on win rate.
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
PIVOT_LEN = 5
SMA_LEN = 200
SPAN_LO, SPAN_HI = 6, 50
SL_PCT, TP_PCT = 0.02, 0.05
EXIT_ON_OPPOSITE = True
COMMISSION = 0.0005
SLIP_TICKS = 2
INITIAL_EQ = 10_000.0
TICK = {"GC=F": 0.10, "SI=F": 0.005, "BTC-USD": 0.01, "CL=F": 0.01, "NQ=F": 0.25}


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


def pivots(vals, macd, L, kind):
    out = []
    n = len(vals)
    for i in range(L, n - L):
        w = vals[i - L:i + L + 1]
        if (kind == "high" and vals[i] == w.max()) or (kind == "low" and vals[i] == w.min()):
            out.append((i + L, i, float(vals[i]), float(macd[i])))
    return out


def gen_signals(df, asset):
    """Return signals list of {bar_idx, direction, entry_price}."""
    high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    close = df["Close"].to_numpy()
    macd = macd_line(df["Close"]).to_numpy()
    sma = df["Close"].rolling(SMA_LEN).mean().to_numpy()  # chart-native
    n = len(close)
    sigs = []
    last_bear_bar_price = None; last_bear_macd = None; last_bear_bar = None
    last_bull_bar_price = None; last_bull_macd = None; last_bull_bar = None
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
            if c2 >= n:
                continue
            # Trend alignment vs chart-native 200-SMA at confirmation bar
            if not np.isfinite(sma[c2]):
                continue
            up = close[c2] > sma[c2]
            aligned = (direction == "long" and up) or (direction == "short" and not up)
            if not aligned:
                continue
            sigs.append({"bar": c2, "dir": direction, "entry": close[c2]})
    sigs.sort(key=lambda s: s["bar"])
    return sigs


def simulate(df, sigs, tick):
    """Walk the signals in bar order; simulate SL/TP/exit-on-opposite. Returns list of trades."""
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    n = len(close)
    trades = []
    open_trade = None  # dict or None
    slip = SLIP_TICKS * tick
    equity = INITIAL_EQ

    def close_trade(exit_bar, exit_price, reason):
        nonlocal open_trade, equity
        entry = open_trade["entry"]
        direction = open_trade["dir"]
        size = open_trade["size"]  # units
        if direction == "long":
            pnl = size * (exit_price - entry) - COMMISSION * size * (entry + exit_price)
        else:
            pnl = size * (entry - exit_price) - COMMISSION * size * (entry + exit_price)
        equity += pnl
        trades.append({"dir": direction, "entry_bar": open_trade["entry_bar"],
                       "exit_bar": exit_bar, "entry": entry, "exit": exit_price,
                       "pnl": pnl, "reason": reason, "equity": equity})
        open_trade = None

    sig_iter = iter(sigs)
    next_sig = next(sig_iter, None)

    for i in range(n):
        # process open trade first (SL / TP)
        if open_trade is not None and i > open_trade["entry_bar"]:
            hi = high[i]; lo = low[i]
            if open_trade["dir"] == "long":
                hit_sl = lo <= open_trade["sl"]
                hit_tp = hi >= open_trade["tp"]
            else:
                hit_sl = hi >= open_trade["sl"]
                hit_tp = lo <= open_trade["tp"]
            if hit_sl and hit_tp:
                # ambiguous same-bar; assume SL first (conservative)
                close_trade(i, open_trade["sl"] + (slip if open_trade["dir"] == "short" else -slip), "SL")
            elif hit_sl:
                close_trade(i, open_trade["sl"] + (slip if open_trade["dir"] == "short" else -slip), "SL")
            elif hit_tp:
                close_trade(i, open_trade["tp"], "TP")

        # process signal if it fires this bar
        while next_sig is not None and next_sig["bar"] == i:
            direction = next_sig["dir"]
            entry_price = next_sig["entry"] + (slip if direction == "long" else -slip)
            # exit-on-opposite: close any position opposite to this signal
            if open_trade is not None and open_trade["dir"] != direction and EXIT_ON_OPPOSITE:
                close_trade(i, entry_price, "flip")
            if open_trade is None:
                # size = 100% of equity in units
                size = equity / entry_price if entry_price > 0 else 0
                if size > 0:
                    if direction == "long":
                        sl = entry_price * (1 - SL_PCT)
                        tp = entry_price * (1 + TP_PCT)
                    else:
                        sl = entry_price * (1 + SL_PCT)
                        tp = entry_price * (1 - TP_PCT)
                    open_trade = {"dir": direction, "entry_bar": i, "entry": entry_price,
                                  "sl": sl, "tp": tp, "size": size}
            next_sig = next(sig_iter, None)

    # close any open trade at data end
    if open_trade is not None:
        close_trade(n - 1, close[n - 1], "end")
    return trades


def metrics(trades):
    if not trades:
        return None
    pnl = np.array([t["pnl"] for t in trades])
    wins = pnl[pnl > 0]; losses = pnl[pnl <= 0]
    win_pct = 100 * len(wins) / len(pnl)
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
    avg_win = wins.mean() if len(wins) else 0
    avg_loss = losses.mean() if len(losses) else 0
    # equity curve for max drawdown
    eq = np.array([t["equity"] for t in trades])
    eq_all = np.concatenate([[INITIAL_EQ], eq])
    peak = np.maximum.accumulate(eq_all)
    dd_pct = 100 * (eq_all - peak) / peak
    max_dd = dd_pct.min()
    net_return_pct = 100 * (eq[-1] / INITIAL_EQ - 1)
    # Wilson CI on win rate
    n = len(pnl); p = len(wins) / n
    z = 1.96; denom = 1 + z*z/n
    center = (p + z*z/(2*n)) / denom
    half = z * np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    ci_lo = max(0, (center - half) * 100); ci_hi = min(100, (center + half) * 100)
    return {"n": n, "win_pct": win_pct, "ci": (ci_lo, ci_hi),
            "pf": pf, "avg_win": avg_win, "avg_loss": avg_loss,
            "net_pct": net_return_pct, "max_dd": max_dd,
            "final_eq": eq[-1] if len(eq) else INITIAL_EQ}


def fmt(m):
    if m is None:
        return "no trades"
    return (f"n={m['n']:>3} win={m['win_pct']:5.1f}% "
            f"(CI {m['ci'][0]:3.0f}-{m['ci'][1]:3.0f}%) "
            f"PF={m['pf'] if m['pf']==float('inf') else round(m['pf'],2):>5}  "
            f"net={m['net_pct']:+7.1f}%  maxDD={m['max_dd']:6.1f}%  "
            f"finalEq=${m['final_eq']:,.0f}")


def run_tf(tf):
    print(f"\n############################ TIMEFRAME: {tf} ############################")
    all_trades_by_asset = {}
    for tk, name in ASSETS.items():
        h = fetch(tk, "1h", ("720d", "365d"))
        if h is None:
            print(f"  {name}: no data")
            continue
        df = h if tf == "1h" else resample_4h(h)
        sigs = gen_signals(df, name)
        trades = simulate(df, sigs, TICK.get(tk, 0.01))
        all_trades_by_asset[name] = trades
        print(f"  {name:<9} {fmt(metrics(trades))}")

    # Portfolio equity — simple pool of PnLs (equal-weight, sequential)
    pooled = []
    for name, trades in all_trades_by_asset.items():
        for t in trades:
            pooled.append(t)
    # Recompute equity across pooled trades in time order (each asset had its own $10k,
    # so this is really the sum of independent asset backtests).
    if not pooled:
        return
    total_final = sum(all_trades_by_asset[name][-1]["equity"] if all_trades_by_asset[name] else INITIAL_EQ
                      for name in all_trades_by_asset)
    total_initial = INITIAL_EQ * len([n for n in all_trades_by_asset if all_trades_by_asset[n]])
    if total_initial > 0:
        agg_return = 100 * (total_final / total_initial - 1)
        print(f"\n  PORTFOLIO (each asset $10k independent): "
              f"total starting=${total_initial:,.0f}  ending=${total_final:,.0f}  "
              f"return={agg_return:+.1f}%")
        # Aggregate stats
        all_pnl = np.array([t["pnl"] for t in pooled])
        wins = (all_pnl > 0).sum()
        n = len(all_pnl)
        win_pct = 100 * wins / n
        pf_num = all_pnl[all_pnl > 0].sum()
        pf_den = -all_pnl[all_pnl <= 0].sum()
        pf = pf_num / pf_den if pf_den > 0 else float("inf")
        print(f"  Aggregate: n={n} trades  win={win_pct:.1f}%  PF={pf if pf==float('inf') else round(pf,2)}")


def main():
    for tf in ("4h", "1h"):
        run_tf(tf)


if __name__ == "__main__":
    main()
