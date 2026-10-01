"""Portable yfinance fetch for instruments not on Twelve Data free (B-003: silver, oil).

Returns the SAME normalised frame as the Twelve Data client — UTC (bar-open), columns
open/high/low/close/volume, ascending — so the lake format is identical regardless of source.
4h is resampled from 1h (yfinance has no native 4h). No API key needed ($0).

Known limits (recorded in DATA_MANIFEST): yfinance 15m history ~60d; 1h ~730d; these are the
SOLE source for silver/oil, so no TD cross-check is possible for them.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

COLS = ["time", "open", "high", "low", "close", "volume"]
# our tf -> (yfinance interval, period) for base pulls; 4h is resampled from 1h
BASE = {"15min": ("15m", "60d"), "1h": ("1h", "730d"), "1day": ("1d", "max")}


def _norm(raw) -> pd.DataFrame:
    if raw is None or len(raw) == 0:
        return pd.DataFrame(columns=COLS)
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower).reset_index()
    tcol = next((c for c in ("datetime", "date", "index") if c in df.columns), df.columns[0])
    out = pd.DataFrame({
        "time": pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None),
        "open": pd.to_numeric(df["open"], errors="coerce"),
        "high": pd.to_numeric(df["high"], errors="coerce"),
        "low": pd.to_numeric(df["low"], errors="coerce"),
        "close": pd.to_numeric(df["close"], errors="coerce"),
        "volume": pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0),
    })
    return out.dropna(subset=["open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)


def _dl(symbol, interval, period):
    return yf.download(symbol, interval=interval, period=period,
                       auto_adjust=False, progress=False, threads=False)


def fetch(yf_symbol: str, tf: str) -> pd.DataFrame:
    if tf == "4h":
        base = _norm(_dl(yf_symbol, "1h", "730d"))
        if base.empty:
            return base
        s = base.set_index("time")
        agg = pd.concat([
            s["open"].resample("4h").first(), s["high"].resample("4h").max(),
            s["low"].resample("4h").min(), s["close"].resample("4h").last(),
            s["volume"].resample("4h").sum(),
        ], axis=1)
        agg.columns = ["open", "high", "low", "close", "volume"]
        return agg.dropna(subset=["open", "high", "low", "close"]).reset_index().rename(columns={"index": "time"})[COLS]
    iv, per = BASE[tf]
    return _norm(_dl(yf_symbol, iv, per))
