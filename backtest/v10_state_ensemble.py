"""v10 — STATE-BASED ensemble of V5 + SCALPR + Koh3.

Key architectural change from v9:
  v9 required all three systems to fire as EVENTS in a narrow time window
  (pivot completes AND SCALPR gate is on AND Koh3 candle within 5 bars).
  Three events aligning is exponentially rare -> only 2-9 trades over 2 years.

  v10 converts each system into a per-bar STATE (long / short / neutral),
  then takes trades when >=2 of 3 (or 3 of 3) states agree.  States can
  persist for many bars, so state alignment is much more common than event
  alignment.

Per-bar states:
  V5 state:      look back over the last DIVERGENCE_LOOKBACK bars for the most
                 recent aligned divergence pivot.  If found and trend still
                 agrees, state = long/short.  Otherwise neutral.
  SCALPR state:  standalone SCALPR-style bias — long if (EMA9>EMA21 and ADX>=20
                 and RSI not in overbought), short if mirror, else neutral.
  Koh3 state:    composite score across bullish signals (rejection wick,
                 liquidity sweep, RSI hook, RSI extreme reversal) over the last
                 KOH3_LOOKBACK bars.  Score cell = +1 per bullish signal,
                 -1 per bearish.  Threshold >= KOH3_THR -> long state; <= -KOH3_THR
                 -> short state; else neutral.

Configs tested per timeframe x asset:
  1) 3-of-3 (strict, all systems agree)
  2) 2-of-3 (majority)
  3) V5 solo
  4) SCALPR solo
  5) Koh3 solo

Entry: on state-transition into long/short (i.e. bar where state flips FROM
       non-agreement TO agreement).
Exit:  SL 1.5xATR, TP 3.0xATR, plus exit-on-opposite state.
"""

from __future__ import annotations

import time
from typing import Dict, List

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

DIVERGENCE_LOOKBACK = 30  # V5 state persists this long after a pivot
KOH3_LOOKBACK = 10        # rolling window Koh3 scores over
KOH3_THR = 2              # composite score threshold for Koh3 long/short state

COMMISSION = 0.0005
SLIP_TICKS = 2
INITIAL_EQ = 10_000.0


# ---------------- fetch / indicators (same as v9) ----------------

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


# ---------------- STATE builders ----------------

def build_v5_state(df):
    """Per-bar state: +1 long after aligned bull div (persists), -1 short after
    aligned bear div, 0 neutral. State expires after DIVERGENCE_LOOKBACK bars
    or when trend flips."""
    n = len(df)
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    macd = macd_line(df["Close"]).to_numpy()
    sma = df["Close"].rolling(SMA_LEN).mean().to_numpy()

    state = np.zeros(n, dtype=np.int8)
    ph = pivots(high, macd, PIVOT_LEN, "high")  # (confirm_bar, i, price, macd)
    pl = pivots(low, macd, PIVOT_LEN, "low")

    def emit(direction, confirm_bar):
        for j in range(confirm_bar, min(confirm_bar + DIVERGENCE_LOOKBACK, n)):
            if not np.isfinite(sma[j]):
                continue
            up = close[j] > sma[j]
            if direction == "long" and not up:
                break
            if direction == "short" and up:
                break
            if state[j] == 0:
                state[j] = 1 if direction == "long" else -1

    for k in range(1, len(ph)):
        c1, i1, p1, m1 = ph[k-1]
        c2, i2, p2, m2 = ph[k]
        span = i2 - i1
        if not (SPAN_LO <= span <= SPAN_HI):
            continue
        if not (p2 > p1 and m2 < m1):
            continue
        if c2 >= n or not np.isfinite(sma[c2]):
            continue
        if close[c2] > sma[c2]:
            continue
        emit("short", c2)

    for k in range(1, len(pl)):
        c1, i1, p1, m1 = pl[k-1]
        c2, i2, p2, m2 = pl[k]
        span = i2 - i1
        if not (SPAN_LO <= span <= SPAN_HI):
            continue
        if not (p2 < p1 and m2 > m1):
            continue
        if c2 >= n or not np.isfinite(sma[c2]):
            continue
        if close[c2] < sma[c2]:
            continue
        emit("long", c2)

    return state


def build_scalpr_state(df):
    """+1 long: EMA9>EMA21 AND ADX>=20 AND RSI<80.  -1 short: mirror. 0 else."""
    n = len(df)
    ema9 = df["Close"].ewm(span=9, adjust=False).mean().to_numpy()
    ema21 = df["Close"].ewm(span=21, adjust=False).mean().to_numpy()
    adx = adx_s(df).to_numpy()
    rsi = rsi_s(df["Close"]).to_numpy()

    state = np.zeros(n, dtype=np.int8)
    for i in range(n):
        if not np.isfinite(adx[i]) or adx[i] < 20:
            continue
        if ema9[i] > ema21[i] and rsi[i] < 80:
            state[i] = 1
        elif ema9[i] < ema21[i] and rsi[i] > 20:
            state[i] = -1
    return state


def build_koh3_state(df):
    """Rolling composite score over last KOH3_LOOKBACK bars.
    Each bar contributes +1 per bullish signal, -1 per bearish."""
    n = len(df)
    O = df["Open"].to_numpy(); C = df["Close"].to_numpy()
    H = df["High"].to_numpy(); L = df["Low"].to_numpy()
    V = df["Volume"].to_numpy()
    rsi = rsi_s(df["Close"]).to_numpy()
    vol_ema = df["Volume"].ewm(span=20, adjust=False).mean().to_numpy()

    bar_signal = np.zeros(n, dtype=np.int8)

    for i in range(20, n):
        body = abs(C[i] - O[i])
        candle_range = H[i] - L[i]
        lower_wick = min(C[i], O[i]) - L[i]
        upper_wick = H[i] - max(C[i], O[i])
        v_ok = vol_ema[i] > 0 and V[i] > vol_ema[i] * 1.2

        # --- bullish contributions
        if candle_range > 0 and lower_wick > candle_range * 0.6 and lower_wick > body * 2 and v_ok:
            bar_signal[i] += 1
        recent_lo = L[max(0, i-10):i].min() if i >= 10 else np.nan
        if np.isfinite(recent_lo) and L[i] < recent_lo and C[i] > recent_lo and vol_ema[i] > 0 and V[i] > vol_ema[i] * 1.3:
            bar_signal[i] += 1
        if i >= 2 and rsi[i] < 35 and rsi[i] > rsi[i-1] and rsi[i-1] < rsi[i-2]:
            bar_signal[i] += 1
        if rsi[i] < 25 and C[i] > O[i]:
            bar_signal[i] += 1

        # --- bearish contributions
        if candle_range > 0 and upper_wick > candle_range * 0.6 and upper_wick > body * 2 and v_ok:
            bar_signal[i] -= 1
        recent_hi = H[max(0, i-10):i].max() if i >= 10 else np.nan
        if np.isfinite(recent_hi) and H[i] > recent_hi and C[i] < recent_hi and vol_ema[i] > 0 and V[i] > vol_ema[i] * 1.3:
            bar_signal[i] -= 1
        if i >= 2 and rsi[i] > 65 and rsi[i] < rsi[i-1] and rsi[i-1] > rsi[i-2]:
            bar_signal[i] -= 1
        if rsi[i] > 75 and C[i] < O[i]:
            bar_signal[i] -= 1

    # Rolling sum over KOH3_LOOKBACK
    state = np.zeros(n, dtype=np.int8)
    cs = np.cumsum(bar_signal)
    for i in range(n):
        lo = max(0, i - KOH3_LOOKBACK + 1)
        rolling = cs[i] - (cs[lo-1] if lo > 0 else 0)
        if rolling >= KOH3_THR:
            state[i] = 1
        elif rolling <= -KOH3_THR:
            state[i] = -1
    return state


# ---------------- Vote-combine into per-bar target state ----------------

def combine_states(v5, scalpr, koh3, min_votes: int):
    """For each bar, compute target state.
    long_votes = count of (v5==+1) + (scalpr==+1) + (koh3==+1); mirror short.
    If long_votes >= min_votes -> +1; short_votes >= min_votes -> -1; else 0."""
    long_v = (v5 == 1).astype(np.int8) + (scalpr == 1).astype(np.int8) + (koh3 == 1).astype(np.int8)
    short_v = (v5 == -1).astype(np.int8) + (scalpr == -1).astype(np.int8) + (koh3 == -1).astype(np.int8)
    out = np.zeros_like(v5, dtype=np.int8)
    out[long_v >= min_votes] = 1
    out[short_v >= min_votes] = -1
    # If both sides meet (rare), keep the majority side, else neutral
    conflict = (long_v >= min_votes) & (short_v >= min_votes)
    if conflict.any():
        out[conflict & (long_v > short_v)] = 1
        out[conflict & (short_v > long_v)] = -1
        out[conflict & (long_v == short_v)] = 0
    return out


# ---------------- Simulator (state-driven entries + ATR exits) ----------------

def simulate_state(df, state, tick):
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    atr = atr_s(df).to_numpy()
    n = len(close)
    slip = SLIP_TICKS * tick
    equity = INITIAL_EQ

    trades = []
    open_trade = None

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

    prev_state = 0
    for i in range(n):
        # First: check exits on current bar (SL/TP/opposite state)
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

        # State-transition detection
        s = int(state[i])
        entered_new_direction = (s != 0 and s != prev_state)

        # Exit-on-opposite state
        if open_trade is not None and s != 0 and s != (1 if open_trade["dir"] == "long" else -1):
            exit_price = close[i] + (slip if open_trade["dir"] == "short" else -slip)
            close_trade(i, exit_price, "flip")

        if entered_new_direction and open_trade is None:
            if not np.isfinite(atr[i]) or atr[i] <= 0:
                prev_state = s; continue
            direction = "long" if s == 1 else "short"
            entry_price = close[i] + (slip if direction == "long" else -slip)
            size = equity / entry_price if entry_price > 0 else 0
            if size > 0:
                av = atr[i]
                if direction == "long":
                    sl = entry_price - SL_ATR * av; tp = entry_price + TP_ATR * av
                else:
                    sl = entry_price + SL_ATR * av; tp = entry_price - TP_ATR * av
                open_trade = {"dir": direction, "entry_bar": i, "entry": entry_price,
                              "sl": sl, "tp": tp, "size": size}
        prev_state = s

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
    all_states = {}; dfs = {}
    for tk, name in ASSETS.items():
        h = fetch(tk, "1h", ("720d", "365d"))
        if h is None:
            print(f"  {name}: no data"); continue
        df = h if tf == "1h" else resample(h, rule)
        dfs[name] = (df, TICK.get(tk, 0.01))
        v5 = build_v5_state(df)
        sc = build_scalpr_state(df)
        k3 = build_koh3_state(df)
        all_states[name] = (v5, sc, k3)

    configs = [
        ("3of3", "1) 3-of-3 ENSEMBLE (all three agree)",
            lambda v, s, k: combine_states(v, s, k, 3)),
        ("2of3", "2) 2-of-3 ENSEMBLE (majority)",
            lambda v, s, k: combine_states(v, s, k, 2)),
        ("v5",   "3) V5 solo (divergence state alone)",
            lambda v, s, k: v),
        ("scalpr","4) SCALPR solo (regime state alone)",
            lambda v, s, k: s),
        ("koh3", "5) Koh3 solo (composite state alone)",
            lambda v, s, k: k),
    ]

    for key, label, mk in configs:
        print(f"\n  {label}")
        print(f"     {'asset':<9}{'n':>5}{'win%':>7}{'PF':>7}{'net%':>8}{'maxDD':>8}{'finalEq':>10}")
        tot_final = 0; tot_init = 0; all_pnl = []
        for name in ASSETS.values():
            if name not in all_states:
                continue
            df, tick = dfs[name]
            v5, sc, k3 = all_states[name]
            state = mk(v5, sc, k3)
            trades = simulate_state(df, state, tick)
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
                  f"agg win={win:.1f}%  PF={pf if pf==float('inf') else round(pf,2)}  n={len(all_pnl)}")


def main():
    print("v10 STATE ENSEMBLE test: V5 + SCALPR + Koh3 as per-bar STATES")
    print(f"V5 state lookback: {DIVERGENCE_LOOKBACK} bars.  Koh3 rolling window: {KOH3_LOOKBACK} bars, threshold ±{KOH3_THR}")
    print(f"Exit: SL {SL_ATR}xATR, TP {TP_ATR}xATR, plus exit-on-opposite-state.")
    for tf, rule in (("2h", "2h"), ("4h", "4h"), ("1h", None)):
        run_tf(tf, rule)


if __name__ == "__main__":
    main()
