"""PROPER combined test — this time using the actual best of each system.

V5 role: fires the DIVERGENCE PIVOT EVENT (aligned + span 6-50). This is the
  SETUP bar (state = 'watching').

SCALPR role: REGIME GATE. Only allow trades when ADX >= 20 (SCALPR's
  strong-trend zone) AND EMA9/EMA21 side matches trade direction.

Koh3 role: CONFIRMATION CANDLE, checked bar-by-bar for up to 5 bars AFTER the
  divergence pivot. A confirmation candle is one that shows any of:
    * rejection wick in trade direction
    * RSI hook back from extreme
    * exhaustion (N consecutive same-color candles + body shrinking + vol drying)
    * liquidity sweep of recent extreme
  Entry occurs on the confirmation candle's CLOSE, not on the divergence bar.

Exit: SCALPR SL 1.5xATR / TP 3.0xATR (1:2 R:R). Exit-on-opposite ON.

Compare 4 configs per timeframe (2H, 4H, 1H) x 5 assets:
  A) FULL COMBINED (all three roles: V5 + SCALPR gate + Koh3 confirm)
  B) V5 + SCALPR gate only (skip Koh3 confirmation candle)
  C) V5 + Koh3 confirmation only (skip SCALPR regime gate)
  D) V5 baseline (fires on divergence bar directly)
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
KOH3_WINDOW = 5              # confirmation candle allowed within 5 bars after pivot
COMMISSION = 0.0005
SLIP_TICKS = 2
INITIAL_EQ = 10_000.0


def fetch(ticker, interval, periods):
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


def resample(h, rule):
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return h.resample(rule).agg(agg).dropna(subset=["Open", "High", "Low", "Close"])


def macd_line(c):
    return c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()


def wilder(s, n):
    return s.ewm(alpha=1.0/n, adjust=False).mean()


def atr_s(df, n=ATR_LEN):
    tr = pd.concat([df["High"]-df["Low"],
                    (df["High"]-df["Close"].shift()).abs(),
                    (df["Low"]-df["Close"].shift()).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def adx_s(df, n=14):
    up = df["High"].diff(); dn = -df["Low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([df["High"]-df["Low"],
                    (df["High"]-df["Close"].shift()).abs(),
                    (df["Low"]-df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, n)
    pdi = 100 * wilder(pd.Series(pdm, index=df.index), n) / atr
    mdi = 100 * wilder(pd.Series(mdm, index=df.index), n) / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return wilder(dx.fillna(0), n)


def rsi_s(c, n=14):
    d = c.diff()
    g = wilder(d.clip(lower=0), n)
    l = wilder(-d.clip(upper=0), n)
    rs = g / l.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)


def pivots(vals, macd, L, kind):
    out = []
    n = len(vals)
    for i in range(L, n-L):
        w = vals[i-L:i+L+1]
        if (kind == "high" and vals[i] == w.max()) or (kind == "low" and vals[i] == w.min()):
            out.append((i+L, i, float(vals[i]), float(macd[i])))
    return out


def koh3_confirm_long(df, i, rsi, vol_ema, vol_std):
    """Return True if bar i shows a Koh3-style bullish confirmation candle."""
    if i < 20 or i >= len(df):
        return False
    O = df["Open"].iloc[i]; C = df["Close"].iloc[i]
    H = df["High"].iloc[i]; L = df["Low"].iloc[i]; V = df["Volume"].iloc[i]
    body = abs(C - O)
    lower_wick = min(C, O) - L
    candle_range = H - L
    # Rejection wick (bullish hammer)
    if candle_range > 0 and lower_wick > candle_range * 0.6 and lower_wick > body * 2 and V > vol_ema[i] * 1.2:
        return True
    # Liquidity sweep low: made a new N-bar low, closed back inside
    if i >= 10:
        recent_lo = df["Low"].iloc[i-10:i].min()
        if L < recent_lo and C > recent_lo and V > vol_ema[i] * 1.3:
            return True
    # RSI hook up from oversold
    if i >= 2 and rsi.iloc[i] < 35 and rsi.iloc[i] > rsi.iloc[i-1] and rsi.iloc[i-1] < rsi.iloc[i-2]:
        return True
    # RSI extreme low + bull candle
    if rsi.iloc[i] < 25 and C > O:
        return True
    return False


def koh3_confirm_short(df, i, rsi, vol_ema, vol_std):
    if i < 20 or i >= len(df):
        return False
    O = df["Open"].iloc[i]; C = df["Close"].iloc[i]
    H = df["High"].iloc[i]; L = df["Low"].iloc[i]; V = df["Volume"].iloc[i]
    body = abs(C - O)
    upper_wick = H - max(C, O)
    candle_range = H - L
    if candle_range > 0 and upper_wick > candle_range * 0.6 and upper_wick > body * 2 and V > vol_ema[i] * 1.2:
        return True
    if i >= 10:
        recent_hi = df["High"].iloc[i-10:i].max()
        if H > recent_hi and C < recent_hi and V > vol_ema[i] * 1.3:
            return True
    if i >= 2 and rsi.iloc[i] > 65 and rsi.iloc[i] < rsi.iloc[i-1] and rsi.iloc[i-1] > rsi.iloc[i-2]:
        return True
    if rsi.iloc[i] > 75 and C < O:
        return True
    return False


def gen_signals(df, asset):
    """For each divergence pivot, find entry bar based on config filters."""
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    macd = macd_line(df["Close"]).to_numpy()
    sma = df["Close"].rolling(SMA_LEN).mean().to_numpy()
    atr = atr_s(df).to_numpy()
    adx = adx_s(df).to_numpy()
    rsi = rsi_s(df["Close"])
    ema9 = df["Close"].ewm(span=9, adjust=False).mean().to_numpy()
    ema21 = df["Close"].ewm(span=21, adjust=False).mean().to_numpy()
    vol_ema = df["Volume"].ewm(span=20, adjust=False).mean().to_numpy()
    vol_std = df["Volume"].rolling(20).std().to_numpy()
    n = len(close); idx = df.index

    divs = []
    for kind, direction in (("high", "short"), ("low", "long")):
        vals = high if kind == "high" else low
        pv = pivots(vals, macd, PIVOT_LEN, kind)
        for k in range(1, len(pv)):
            c1, i1, p1, m1 = pv[k-1]
            c2, i2, p2, m2 = pv[k]
            reg = (p2 > p1 and m2 < m1) if direction == "short" else (p2 < p1 and m2 > m1)
            span = i2 - i1
            if not reg or not (SPAN_LO <= span <= SPAN_HI):
                continue
            if c2 >= n or not np.isfinite(sma[c2]) or not np.isfinite(atr[c2]) or atr[c2] <= 0:
                continue
            up = close[c2] > sma[c2]
            aligned = (direction == "long" and up) or (direction == "short" and not up)
            if not aligned:
                continue
            divs.append({"pivot_bar": c2, "dir": direction})

    # Now build entry lists for each config
    signals = {"full": [], "v5_scalpr": [], "v5_koh3": [], "v5_only": []}

    for d in divs:
        pb = d["pivot_bar"]; direction = d["dir"]

        # ---- V5 only: enter on the pivot confirmation bar directly ----
        signals["v5_only"].append({"bar": pb, "dir": direction,
                                    "close": float(close[pb]), "atr": float(atr[pb])})

        # ---- V5 + SCALPR regime gate: enter on pivot bar IF ADX >= 20
        #      AND (EMA9>EMA21 for long, EMA9<EMA21 for short) ----
        adx_ok = np.isfinite(adx[pb]) and adx[pb] >= 20.0
        ema_ok = (direction == "long" and ema9[pb] > ema21[pb]) or \
                 (direction == "short" and ema9[pb] < ema21[pb])
        scalpr_gate_ok = adx_ok and ema_ok
        if scalpr_gate_ok:
            signals["v5_scalpr"].append({"bar": pb, "dir": direction,
                                          "close": float(close[pb]), "atr": float(atr[pb])})

        # ---- V5 + Koh3 confirmation: scan for Koh3 candle in [pb, pb+KOH3_WINDOW] ----
        for j in range(pb, min(pb + KOH3_WINDOW + 1, n)):
            if direction == "long" and koh3_confirm_long(df, j, rsi, vol_ema, vol_std):
                signals["v5_koh3"].append({"bar": j, "dir": direction,
                                             "close": float(close[j]),
                                             "atr": float(atr[j]) if np.isfinite(atr[j]) else float(atr[pb])})
                break
            if direction == "short" and koh3_confirm_short(df, j, rsi, vol_ema, vol_std):
                signals["v5_koh3"].append({"bar": j, "dir": direction,
                                             "close": float(close[j]),
                                             "atr": float(atr[j]) if np.isfinite(atr[j]) else float(atr[pb])})
                break

        # ---- FULL: both SCALPR gate AND Koh3 confirmation ----
        if scalpr_gate_ok:
            for j in range(pb, min(pb + KOH3_WINDOW + 1, n)):
                if direction == "long" and koh3_confirm_long(df, j, rsi, vol_ema, vol_std):
                    signals["full"].append({"bar": j, "dir": direction,
                                              "close": float(close[j]),
                                              "atr": float(atr[j]) if np.isfinite(atr[j]) else float(atr[pb])})
                    break
                if direction == "short" and koh3_confirm_short(df, j, rsi, vol_ema, vol_std):
                    signals["full"].append({"bar": j, "dir": direction,
                                              "close": float(close[j]),
                                              "atr": float(atr[j]) if np.isfinite(atr[j]) else float(atr[pb])})
                    break

    for k in signals:
        signals[k].sort(key=lambda s: s["bar"])
    return signals


def simulate(df, sigs, tick):
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

    sig_iter = iter(sigs)
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
                    av = next_sig["atr"]
                    if direction == "long":
                        sl = entry_price - SL_ATR * av; tp = entry_price + TP_ATR * av
                    else:
                        sl = entry_price + SL_ATR * av; tp = entry_price - TP_ATR * av
                    open_trade = {"dir": direction, "entry_bar": i, "entry": entry_price,
                                  "sl": sl, "tp": tp, "size": size}
            next_sig = next(sig_iter, None)

    if open_trade is not None:
        close_trade(n-1, close[n-1], "end")
    return trades


def metrics(trades):
    if not trades:
        return None
    pnl = np.array([t["pnl"] for t in trades])
    wins = pnl[pnl > 0]; losses = pnl[pnl <= 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
    eq = np.array([t["equity"] for t in trades])
    eq_all = np.concatenate([[INITIAL_EQ], eq])
    peak = np.maximum.accumulate(eq_all)
    dd = 100 * (eq_all - peak) / peak
    return {"n": len(pnl), "win_pct": round(100*len(wins)/len(pnl), 1),
            "pf": pf if pf == float("inf") else round(pf, 2),
            "net_pct": round(100*(eq[-1]/INITIAL_EQ - 1), 1),
            "max_dd": round(float(dd.min()), 1),
            "final_eq": round(eq[-1], 0)}


def run_tf(tf, rule):
    print(f"\n############################ TIMEFRAME: {tf} ############################")
    all_sigs = {}; dfs = {}
    for tk, name in ASSETS.items():
        h = fetch(tk, "1h", ("720d", "365d"))
        if h is None:
            print(f"  {name}: no data"); continue
        df = h if tf == "1h" else resample(h, rule)
        dfs[name] = (df, TICK.get(tk, 0.01))
        all_sigs[name] = gen_signals(df, name)

    for cfg_key, cfg_label in (("full",      "A) FULL COMBINED — V5 + SCALPR gate + Koh3 confirm candle"),
                                ("v5_scalpr", "B) V5 + SCALPR regime gate only"),
                                ("v5_koh3",   "C) V5 + Koh3 confirmation candle only"),
                                ("v5_only",   "D) V5 baseline")):
        print(f"\n  {cfg_label}")
        print(f"     {'asset':<9}{'n':>5}{'win%':>7}{'PF':>7}{'net%':>8}{'maxDD':>8}{'finalEq':>10}")
        tot_final = 0; tot_init = 0; all_pnl = []
        for name in ASSETS.values():
            if name not in all_sigs:
                continue
            df, tick = dfs[name]
            trades = simulate(df, all_sigs[name][cfg_key], tick)
            m = metrics(trades)
            if m is None:
                print(f"     {name:<9}   no trades")
                continue
            print(f"     {name:<9}{m['n']:>5}{m['win_pct']:>6.1f}%"
                  f"{str(m['pf']):>7}{m['net_pct']:>+7.1f}%{m['max_dd']:>+7.1f}%${m['final_eq']:>9,.0f}")
            tot_final += m["final_eq"]; tot_init += INITIAL_EQ
            all_pnl.extend([t["pnl"] for t in trades])
        if tot_init > 0:
            ret = 100 * (tot_final / tot_init - 1)
            arr = np.array(all_pnl)
            win = 100 * (arr > 0).sum() / len(arr) if len(arr) else 0
            pf = arr[arr > 0].sum() / -arr[arr <= 0].sum() if (arr <= 0).any() and arr[arr <= 0].sum() < 0 else float("inf")
            print(f"     PORTFOLIO: ${tot_init:,.0f} -> ${tot_final:,.0f}  return {ret:+.1f}%  "
                  f"agg win={win:.1f}%  PF={pf if pf==float('inf') else round(pf,2)}")


def main():
    print("PROPER combined test: V5 pivot + SCALPR regime gate + Koh3 confirmation candle")
    print(f"Koh3 confirmation window: up to {KOH3_WINDOW} bars after divergence pivot")
    print(f"Exit: SL {SL_ATR}xATR, TP {TP_ATR}xATR (1:2)")
    for tf, rule in (("2h", "2h"), ("4h", "4h"), ("1h", None)):
        run_tf(tf, rule)


if __name__ == "__main__":
    main()
