"""Portable crypto alt-data fetcher (PHASE 8 / Step B) — Bybit v5 public API, no key.

Bybit is chosen over Binance because GitHub Actions runners are US-based and Binance's global API
(api.binance.com / fapi.binance.com) geo-blocks US IPs (HTTP 451); Bybit public market data is
US-reachable. Fetches, for each USDT-perp:
  - perpetual OHLCV (category=linear) and spot OHLCV (category=spot) -> perp/spot BASIS
  - funding-rate history (8-hourly) -> carry / funding-momentum / funding-reversion signals
These are economic signals the OHLCV-only Phases 3-7 could not express.

All no-lookahead downstream: a signal on bar t uses values known at t's close; the backtest still
enters at t+1's open. Timestamps are UTC ms. Lake-format OHLCV (time,open,high,low,close,volume).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://api.bybit.com"
UA = {"User-Agent": "Mozilla/5.0 (research; portable fetcher)"}
IV = {"15min": "15", "1h": "60", "4h": "240", "1day": "D"}       # lake tf -> Bybit interval
IV_MS = {"15min": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1day": 86_400_000}


def bybit_symbol(symbol: str) -> str:
    """'BTC/USD' -> 'BTCUSDT' (Bybit USDT perp/spot)."""
    base = symbol.split("/")[0].upper()
    return f"{base}USDT"


def _get(path: str, params: dict, retries: int = 4):
    for a in range(retries):
        try:
            r = requests.get(BASE + path, params=params, headers=UA, timeout=30)
            if r.status_code == 200:
                j = r.json()
                if j.get("retCode") == 0:
                    return j["result"]
            time.sleep(1.0 * (a + 1))
        except Exception:
            time.sleep(1.0 * (a + 1))
    return None


def klines(symbol: str, tf: str, start_ms: int, end_ms: int, category: str = "linear") -> pd.DataFrame:
    """OHLCV for a lake timeframe over [start_ms, end_ms]. Bybit returns <=1000 newest-first;
    we page backwards by moving `end` to just before the oldest row returned."""
    sym = bybit_symbol(symbol); iv = IV[tf]; step = IV_MS[tf]
    rows = {}
    end = end_ms
    while end > start_ms:
        res = _get("/v5/market/kline", {"category": category, "symbol": sym, "interval": iv,
                                        "start": start_ms, "end": end, "limit": 1000})
        lst = (res or {}).get("list") or []
        if not lst:
            break
        for k in lst:                              # [start, o, h, l, c, vol, turnover]
            rows[int(k[0])] = (float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]))
        oldest = min(int(k[0]) for k in lst)
        if oldest >= end:                          # no progress
            break
        end = oldest - step
        time.sleep(0.25)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([(t, *v) for t, v in sorted(rows.items())],
                      columns=["ms", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["ms"], unit="ms", utc=True).dt.tz_localize(None)
    return df.drop(columns="ms")[["time", "open", "high", "low", "close", "volume"]]


def funding(symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    """Funding-rate history (8-hourly). Returns time, funding (decimal)."""
    sym = bybit_symbol(symbol)
    rows = {}
    end = end_ms
    while end > start_ms:
        res = _get("/v5/market/funding/history", {"category": "linear", "symbol": sym,
                                                  "startTime": start_ms, "endTime": end, "limit": 200})
        lst = (res or {}).get("list") or []
        if not lst:
            break
        for k in lst:
            rows[int(k["fundingRateTimestamp"])] = float(k["fundingRate"])
        oldest = min(int(k["fundingRateTimestamp"]) for k in lst)
        if oldest >= end:
            break
        end = oldest - 1
        time.sleep(0.25)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(sorted(rows.items()), columns=["ms", "funding"])
    df["time"] = pd.to_datetime(df["ms"], unit="ms", utc=True).dt.tz_localize(None)
    return df.drop(columns="ms")[["time", "funding"]]


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def years_ago_ms(years: float) -> int:
    return now_ms() - int(years * 365.25 * 86_400_000)
