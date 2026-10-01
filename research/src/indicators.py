"""Portable signal primitives (PHASE 2). Pure pandas/numpy — identical off-peak & interactive.

Conventions:
- Input frames use the lake schema: columns time, open, high, low, close, volume (UTC, bar-open).
- Everything is NO-LOOKAHEAD: value at bar i uses only data up to and including bar i. Wilder
  smoothing via ewm(alpha=1/n, adjust=False). Rolling windows use the trailing window only.
- `pivots` is the one exception to "usable at i": a pivot centred at i is only CONFIRMED `right`
  bars later — consumers must apply that lag (Phase 3 backtest does). See its docstring.
- Volume primitives are valid for FX/metals/oil only (crypto has no volume on TD free — D-007).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------- trend ----------------
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def ema_cross(close: pd.Series, fast: int, slow: int) -> pd.Series:
    """+1 fast>slow, -1 fast<slow (regime); diff() of it marks the cross bar."""
    return np.sign(ema(close, fast) - ema(close, slow))


# ---------------- volatility ----------------
def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift(1)
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                      (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def atr_pct(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return 100 * atr(df, n) / df["close"]


def bbands(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return mid, mid + k * sd, mid - k * sd


def bb_width(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.Series:
    mid, up, lo = bbands(close, n, k)
    return (up - lo) / mid


# ---------------- momentum ----------------
def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    gain = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = gain / loss                         # loss==0 -> inf -> RSI 100; warmup/flat -> NaN
    return 100 - 100 / (1 + rs)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, sig, line - sig


def roc(close: pd.Series, n: int = 10) -> pd.Series:
    return 100 * (close / close.shift(n) - 1)


def stoch(df: pd.DataFrame, k: int = 14, d: int = 3, smooth: int = 3):
    ll = df["low"].rolling(k, min_periods=k).min()
    hh = df["high"].rolling(k, min_periods=k).max()
    fast_k = 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
    kk = fast_k.rolling(smooth, min_periods=smooth).mean()
    return kk, kk.rolling(d, min_periods=d).mean()


# ---------------- mean-reversion ----------------
def zscore(close: pd.Series, n: int = 20) -> pd.Series:
    m = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return (close - m) / sd.replace(0, np.nan)


# ---------------- structure ----------------
def donchian(df: pd.DataFrame, n: int = 20):
    up = df["high"].rolling(n, min_periods=n).max()
    lo = df["low"].rolling(n, min_periods=n).min()
    return up, lo, (up + lo) / 2


def pivots(df: pd.DataFrame, left: int = 2, right: int = 2):
    """Strict swing pivots (ta.pivothigh/low style). Returns (ph, pl) Series with the pivot
    PRICE at the CENTRE bar, NaN elsewhere. NOTE: a pivot centred at bar i is only knowable at
    bar i+right — consumers MUST shift by `right` (or read with that lag) to stay no-lookahead."""
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df); ph = np.full(n, np.nan); pl = np.full(n, np.nan)
    for i in range(left, n - right):
        if all(h[i] > h[i - j] for j in range(1, left + 1)) and all(h[i] > h[i + j] for j in range(1, right + 1)):
            ph[i] = h[i]
        if all(l[i] < l[i - j] for j in range(1, left + 1)) and all(l[i] < l[i + j] for j in range(1, right + 1)):
            pl[i] = l[i]
    return pd.Series(ph, index=df.index), pd.Series(pl, index=df.index)


def adx(df: pd.DataFrame, n: int = 14):
    up = df["high"].diff(); dn = -df["low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(df)
    atr_ = tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / atr_
    mdi = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / atr_
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean(), pdi, mdi


# ---------------- volume (FX/metals/oil only — D-007) ----------------
def obv(df: pd.DataFrame) -> pd.Series:
    return (np.sign(df["close"].diff()).fillna(0) * df["volume"]).cumsum()


def vol_spike(df: pd.DataFrame, n: int = 14, mult: float = 1.5) -> pd.Series:
    return df["volume"] > df["volume"].rolling(n, min_periods=n).mean() * mult


# ---------------- session / time-of-day ----------------
def time_features(idx: pd.DatetimeIndex) -> pd.DataFrame:
    t = pd.DatetimeIndex(idx)
    return pd.DataFrame({"hour": t.hour, "dow": t.dayofweek}, index=idx)


def session_flags(idx: pd.DatetimeIndex) -> pd.DataFrame:
    """Approx UTC session windows (DST-agnostic — caveat). Not mutually exclusive (overlaps)."""
    h = pd.DatetimeIndex(idx).hour
    return pd.DataFrame({
        "asia": (h >= 0) & (h < 9),
        "london": (h >= 7) & (h < 16),
        "ny": (h >= 12) & (h < 21),
    }, index=idx)
