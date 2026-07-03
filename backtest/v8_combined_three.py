"""Combined test: V5 Divergence + SCALPR + Koh3 confluence.

Signal (LONG example — SHORT is mirror):
  * V5 fires: regular bull MACD divergence + span 6-50 + trend-aligned
    (close > chart-native 200-SMA)
  * SCALPR confirms: buy signal within last 5 bars (not ranging (ADX>=20)
    AND EMA9>EMA21 AND (RSI cross up 20 OR golden cross in recent bars))
  * Koh3 confirms: composite bull score >= min_score (3) at confirmation bar

All three MUST fire in the same direction for a trade.

Exit: SCALPR SL/TP (1.5 x ATR SL, 3.0 x ATR TP)
Exit-on-opposite ON. Commission 0.05%, slippage 2 ticks. 100% equity per trade.

Timeframes: 2H (primary — user's claim), 4H, 1H.
Assets: BTC, Gold, Silver, WTI, NAS100 (all with real volume).
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
CONFIRM_WINDOW = 5              # SCALPR must fire within this many bars
KOH3_MIN_SCORE = 3
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


def compute_koh3_bull_score(df, i, rsi, atr, vol_ema, vol_std):
    """Bull confirmation score. Higher = more confluence."""
    if i < 20:
        return 0
    score = 0
    body = abs(df["Close"].iloc[i] - df["Open"].iloc[i])
    upper_wick = df["High"].iloc[i] - max(df["Close"].iloc[i], df["Open"].iloc[i])
    lower_wick = min(df["Close"].iloc[i], df["Open"].iloc[i]) - df["Low"].iloc[i]
    candle_range = df["High"].iloc[i] - df["Low"].iloc[i]
    bull = df["Close"].iloc[i] > df["Open"].iloc[i]
    bear = df["Close"].iloc[i] < df["Open"].iloc[i]
    vol = df["Volume"].iloc[i]

    # Lower rejection wick
    if candle_range > 0 and lower_wick > candle_range * 0.6 and lower_wick > body * 2 and vol > vol_ema[i] * 1.2:
        score += 2

    # Liquidity sweep low
    if i >= 10:
        recent_lo = df["Low"].iloc[i-10:i].min()
        if df["Low"].iloc[i] < recent_lo and df["Close"].iloc[i] > recent_lo and vol > vol_ema[i] * 1.3:
            score += 2

    # Momentum collapse low
    if i >= 3:
        rsi_slope = rsi.iloc[i] - rsi.iloc[i-3]
        price_slope_dn = df["Close"].iloc[i-3] - df["Close"].iloc[i]
        if price_slope_dn > 0 and rsi_slope > 2 and rsi.iloc[i] < 45:
            score += 1

    # Volume climax up (bear candle on huge volume)
    if bear and np.isfinite(vol_std[i]) and vol > vol_ema[i] + 2.5 * vol_std[i]:
        score += 1

    # RSI hook up
    if i >= 2 and rsi.iloc[i] < 35 and rsi.iloc[i] > rsi.iloc[i-1] and rsi.iloc[i-1] < rsi.iloc[i-2]:
        score += 1

    # RSI extreme low
    if rsi.iloc[i] < 25:
        score += 1

    return score


def compute_koh3_bear_score(df, i, rsi, atr, vol_ema, vol_std):
    if i < 20:
        return 0
    score = 0
    body = abs(df["Close"].iloc[i] - df["Open"].iloc[i])
    upper_wick = df["High"].iloc[i] - max(df["Close"].iloc[i], df["Open"].iloc[i])
    lower_wick = min(df["Close"].iloc[i], df["Open"].iloc[i]) - df["Low"].iloc[i]
    candle_range = df["High"].iloc[i] - df["Low"].iloc[i]
    bull = df["Close"].iloc[i] > df["Open"].iloc[i]
    vol = df["Volume"].iloc[i]

    if candle_range > 0 and upper_wick > candle_range * 0.6 and upper_wick > body * 2 and vol > vol_ema[i] * 1.2:
        score += 2

    if i >= 10:
        recent_hi = df["High"].iloc[i-10:i].max()
        if df["High"].iloc[i] > recent_hi and df["Close"].iloc[i] < recent_hi and vol > vol_ema[i] * 1.3:
            score += 2

    if i >= 3:
        rsi_slope = rsi.iloc[i] - rsi.iloc[i-3]
        price_slope_up = df["Close"].iloc[i] - df["Close"].iloc[i-3]
        if price_slope_up > 0 and rsi_slope < -2 and rsi.iloc[i] > 55:
            score += 1

    if bull and np.isfinite(vol_std[i]) and vol > vol_ema[i] + 2.5 * vol_std[i]:
        score += 1

    if i >= 2 and rsi.iloc[i] > 65 and rsi.iloc[i] < rsi.iloc[i-1] and rsi.iloc[i-1] > rsi.iloc[i-2]:
        score += 1

    if rsi.iloc[i] > 75:
        score += 1

    return score


def scalpr_signals(df, adx, rsi, ema9, ema21):
    """Return arrays of bool: was there a SCALPR buy/sell signal at bar i?"""
    n = len(df)
    ranging = adx < 20
    bull_trend = ema9 > ema21
    bear_trend = ema9 < ema21
    golden = (ema9 > ema21) & (ema9.shift(1) <= ema21.shift(1))
    death = (ema9 < ema21) & (ema9.shift(1) >= ema21.shift(1))
    rsi_up = (rsi > 20) & (rsi.shift(1) <= 20)
    rsi_dn = (rsi < 80) & (rsi.shift(1) >= 80)
    buy = (~ranging) & bull_trend & (rsi_up | golden)
    sell = (~ranging) & bear_trend & (rsi_dn | death)
    return buy.values, sell.values


def gen_combined_signals(df, asset):
    """Return list of {bar, dir, entry, atr, v5, scalpr, koh3, all3}"""
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    macd = macd_line(df["Close"]).to_numpy()
    sma = df["Close"].rolling(SMA_LEN).mean().to_numpy()
    atr = atr_s(df).to_numpy()
    adx = adx_s(df)
    rsi = rsi_s(df["Close"])
    ema9 = df["Close"].ewm(span=9, adjust=False).mean()
    ema21 = df["Close"].ewm(span=21, adjust=False).mean()
    vol_ema = df["Volume"].ewm(span=20, adjust=False).mean().to_numpy()
    vol_std = df["Volume"].rolling(20).std().to_numpy()
    scalpr_buy, scalpr_sell = scalpr_signals(df, adx, rsi, ema9, ema21)
    n = len(close); idx = df.index

    out = []
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

            # V5: trend-aligned (chart-native SMA)
            v5_up = close[c2] > sma[c2]
            v5_aligned = (direction == "long" and v5_up) or (direction == "short" and not v5_up)
            if not v5_aligned:
                continue

            # SCALPR: was signal fired within last CONFIRM_WINDOW bars?
            lo_idx = max(0, c2 - CONFIRM_WINDOW)
            if direction == "long":
                scalpr_ok = bool(scalpr_buy[lo_idx:c2+1].any())
            else:
                scalpr_ok = bool(scalpr_sell[lo_idx:c2+1].any())

            # Koh3: score at confirmation bar
            if direction == "long":
                koh3_score = compute_koh3_bull_score(df, c2, rsi, atr, vol_ema, vol_std)
            else:
                koh3_score = compute_koh3_bear_score(df, c2, rsi, atr, vol_ema, vol_std)
            koh3_ok = koh3_score >= KOH3_MIN_SCORE

            all_three = v5_aligned and scalpr_ok and koh3_ok

            out.append({"bar": c2, "dir": direction, "close": float(close[c2]),
                        "atr": float(atr[c2]), "asset": asset,
                        "v5": True, "scalpr": scalpr_ok, "koh3": koh3_ok,
                        "koh3_score": koh3_score, "all_three": all_three,
                        "time": idx[c2]})
    return out


def simulate(df, sigs, tick, filter_mode="all_three"):
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

    if filter_mode == "all_three":
        filt = [s for s in sigs if s["all_three"]]
    elif filter_mode == "v5_only":
        filt = list(sigs)
    elif filter_mode == "v5_scalpr":
        filt = [s for s in sigs if s["scalpr"]]
    elif filter_mode == "v5_koh3":
        filt = [s for s in sigs if s["koh3"]]
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
        all_sigs[name] = gen_combined_signals(df, name)

    for mode, label in (("all_three",   "V5 + SCALPR + Koh3 (ALL THREE — the ask)"),
                         ("v5_scalpr",   "V5 + SCALPR only"),
                         ("v5_koh3",     "V5 + Koh3 only"),
                         ("v5_only",     "V5 only (baseline)")):
        print(f"\n  === {label} ===")
        print(f"     {'asset':<9}{'n':>5}{'win%':>7}{'PF':>7}{'net%':>8}{'maxDD':>8}{'finalEq':>10}")
        tot_final = 0; tot_init = 0; all_pnl = []
        for name, sigs in all_sigs.items():
            df, tick = dfs[name]
            trades = simulate(df, sigs, tick, mode)
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
            print(f"\n     PORTFOLIO: ${tot_init:,.0f} -> ${tot_final:,.0f}  return {ret:+.1f}%  "
                  f"agg win={win:.1f}%  PF={pf if pf==float('inf') else round(pf,2)}")


def main():
    print("Combined V5 + SCALPR + Koh3 test — user's ask")
    print(f"Confluence window: SCALPR must fire within last {CONFIRM_WINDOW} bars of divergence")
    print(f"Koh3 confirmation: composite bull/bear score >= {KOH3_MIN_SCORE}")
    print(f"Exit: SL {SL_ATR}xATR, TP {TP_ATR}xATR (R:R 1:2)")
    for tf, rule in (("2h", "2h"), ("4h", "4h"), ("1h", None)):
        run_tf(tf, rule)


if __name__ == "__main__":
    main()
