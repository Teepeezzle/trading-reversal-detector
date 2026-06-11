"""Why does the reversal logic fit Oil but fail Gold?

Two lenses:
  1. ASSET CHARACTER over the test window — net drift, and how trending vs
     mean-reverting the price path is (Kaufman efficiency ratio + return
     autocorrelation). Reversals-at-extremes is a mean-reversion bet; it dies
     in trends and thrives in ranges.
  2. SIGNAL ALIGNMENT — each fixed-mode trade tagged as with-trend or
     counter-trend (vs the 100-bar SMA slope on the trade's timeframe), with
     win rate and net for each bucket.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "backtest" / "results"

ASSETS = {"GC=F": "Gold", "SI=F": "Silver", "CL=F": "WTI Oil", "BTC-USD": "Bitcoin"}
FETCH = {"1h": ("1h", "730d"), "4h": ("1h", "730d"), "1d": ("1d", "2y")}


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def _naive(df: pd.DataFrame) -> pd.DataFrame:
    if df.index.tz is not None:
        df = df.copy()
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    return df


def _resample_4h(h: pd.DataFrame) -> pd.DataFrame:
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return h.resample("4h").agg(agg).dropna()


def fetch(ticker: str, tf: str) -> pd.DataFrame | None:
    interval, period = FETCH[tf]
    try:
        raw = yf.download(ticker, period=period, interval=interval,
                          progress=False, auto_adjust=False, threads=False)
    except Exception:
        return None
    if raw is None or raw.empty:
        return None
    df = _naive(_flatten(raw))
    return _resample_4h(df) if tf == "4h" else df


def efficiency_ratio_series(close: pd.Series, window: int = 20) -> pd.Series:
    """Rolling Kaufman efficiency ratio."""
    direction = (close - close.shift(window)).abs()
    path = close.diff().abs().rolling(window).sum()
    return (direction / path.replace(0, np.nan)).clip(0, 1)


def character(ticker: str) -> dict:
    """Trend/range character of the 1d series over the window."""
    d = fetch(ticker, "1d")
    if d is None or len(d) < 50:
        return {}
    c = d["Close"]
    rets = c.pct_change().dropna()
    er = efficiency_ratio_series(c, 20).dropna()
    drift = (c.iloc[-1] / c.iloc[0] - 1) * 100
    # Lag-1 autocorrelation of returns: >0 = trend persistence, <0 = mean-revert
    autocorr = rets.autocorr(lag=1)
    return {
        "asset": ASSETS[ticker],
        "start": round(float(c.iloc[0]), 2),
        "end": round(float(c.iloc[-1]), 2),
        "net_drift_%": round(float(drift), 1),
        "ann_vol_%": round(float(rets.std() * np.sqrt(252) * 100), 1),
        "median_ER": round(float(er.median()), 3),
        "trending_share_%": round(float((er >= 0.45).mean() * 100), 1),
        "ranging_share_%": round(float((er <= 0.20).mean() * 100), 1),
        "ret_autocorr_lag1": round(float(autocorr), 3),
    }


def trend_at(df: pd.DataFrame, ts: pd.Timestamp, window: int = 100) -> int:
    """+1 if 100-bar SMA is rising at ts, -1 if falling, 0 if flat/unknown."""
    sub = df.loc[:ts]
    if len(sub) < window + 5:
        return 0
    sma = sub["Close"].rolling(window).mean()
    slope = sma.iloc[-1] - sma.iloc[-6]
    if not np.isfinite(slope) or sma.iloc[-1] == 0:
        return 0
    rel = slope / sma.iloc[-1]
    return 1 if rel > 0.001 else (-1 if rel < -0.001 else 0)


def alignment(mode: str = "fixed") -> pd.DataFrame:
    """Tag each fixed trade as with/counter-trend and aggregate."""
    blot = OUT / f"trades_{mode}.csv"
    if not blot.exists():
        return pd.DataFrame()
    tr = pd.read_csv(blot, parse_dates=["signal_time"])
    tr = tr[tr.outcome != "open"].copy()

    price_cache: dict = {}
    rows = []
    for _, r in tr.iterrows():
        key = (r.ticker, r.timeframe)
        if key not in price_cache:
            price_cache[key] = fetch(r.ticker, r.timeframe)
        df = price_cache[key]
        if df is None:
            continue
        tdir = trend_at(df, r.signal_time)
        sig_dir = 1 if r.direction == "LONG" else -1
        if tdir == 0:
            align = "flat"
        elif sig_dir == tdir:
            align = "with-trend"
        else:
            align = "counter-trend"
        rows.append({"asset": ASSETS.get(r.ticker, r.ticker),
                     "direction": r.direction, "align": align, "pnl": r.pnl_usd})
    return pd.DataFrame(rows)


def main() -> int:
    print("\n===== ASSET CHARACTER over the 2-year window (1d) =====")
    char = pd.DataFrame([character(t) for t in ASSETS])
    print(char.to_string(index=False))

    print("\n===== SIGNAL DIRECTIONAL BIAS (fixed trades) =====")
    al = alignment("fixed")
    if al.empty:
        print("no fixed trades found")
        return 0
    bias = al.groupby(["asset", "direction"]).size().unstack(fill_value=0)
    print(bias.to_string())

    print("\n===== WIN RATE & NET by TREND ALIGNMENT (fixed trades) =====")
    g = al.groupby(["asset", "align"]).agg(
        trades=("pnl", "size"),
        win_rate=("pnl", lambda s: round(100 * (s > 0).mean(), 0)),
        net=("pnl", lambda s: round(s.sum(), 2)),
    )
    print(g.to_string())

    print("\n===== overall by alignment =====")
    go = al.groupby("align").agg(
        trades=("pnl", "size"),
        win_rate=("pnl", lambda s: round(100 * (s > 0).mean(), 0)),
        net=("pnl", lambda s: round(s.sum(), 2)),
    )
    print(go.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
