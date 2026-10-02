"""Portable HistData.com fetcher (PHASE 7 deep-data re-test) — FREE, no API key.

HistData publishes 1-minute OHLC history (FX majors/crosses, metals XAU/XAG, some energy/indices) as
monthly ASCII ZIPs via a two-step token flow: GET the download page (carries a hidden `tk` token),
then POST it to get.php to receive the ZIP. This breaks the Twelve-Data-free depth cap (D-005): FX
majors reach back ~2000, so the gauntlet can finally run with real statistical power.

Line format inside the ZIP: `YYYYMMDD HHMMSS;open;high;low;close;volume` (volume is 0 for FX/metals).
HistData timestamps are US Eastern Standard Time (no DST); we convert to UTC with a fixed +5h to match
the rest of the lake (approximate — documented caveat, like the TD/yfinance basis in D-010). We then
resample 1-minute bars to the lake timeframes (bar-open label, no-lookahead).
"""
from __future__ import annotations

import io
import re
import time
import zipfile
from datetime import timedelta

import pandas as pd
import requests

PAGE = ("https://www.histdata.com/download-free-forex-historical-data/"
        "?/ascii/1-minute-bar-quotes/{sym}/{year}/{month}")
GET = "https://www.histdata.com/get.php"
UA = {"User-Agent": "Mozilla/5.0 (research; portable fetcher)"}
EST_TO_UTC = timedelta(hours=5)          # HistData = EST no-DST -> UTC (fixed offset, documented)
_TK = re.compile(r'id="tk"\s+value="([0-9a-f]+)"')

LAKE_TF = {"15min": "15min", "1h": "1h", "4h": "4h", "1day": "1D"}   # resampled from M1
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def hd_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()


def fetch_m1_month(symbol: str, year: int, month: int, session: requests.Session | None = None,
                   retries: int = 3) -> pd.DataFrame:
    """One month of 1-minute bars for `symbol` (e.g. 'EUR/USD'). Empty frame if unavailable."""
    s = session or requests.Session()
    sym = hd_symbol(symbol)
    page = PAGE.format(sym=sym.lower(), year=year, month=month)
    for attempt in range(retries):
        try:
            r = s.get(page, headers=UA, timeout=30)
            if r.status_code != 200:
                return pd.DataFrame()
            m = _TK.search(r.text)
            if not m:
                return pd.DataFrame()
            tk = m.group(1)
            data = {"tk": tk, "date": str(year), "datemonth": f"{year}{month:02d}",
                    "platform": "ASCII", "timeframe": "M1", "fxpair": sym}
            pr = s.post(GET, data=data, headers={**UA, "Referer": page}, timeout=60)
            if pr.status_code != 200 or len(pr.content) < 200:
                return pd.DataFrame()
            zf = zipfile.ZipFile(io.BytesIO(pr.content))
            csv = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            raw = zf.read(csv).decode("utf-8", "ignore")
            return _parse_m1(raw)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return pd.DataFrame()


def _parse_m1(raw: str) -> pd.DataFrame:
    rows = []
    for ln in raw.splitlines():
        if not ln:
            continue
        p = ln.split(";")
        if len(p) < 6:
            continue
        rows.append((p[0], float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[5])))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    t = pd.to_datetime(df["ts"], format="%Y%m%d %H%M%S", errors="coerce") + EST_TO_UTC
    df["time"] = t
    return df.dropna(subset=["time"]).drop(columns="ts").sort_values("time").reset_index(drop=True)


def fetch_m1(symbol: str, start_year: int, end_year: int) -> pd.DataFrame:
    """Concatenate monthly M1 from start_year..end_year (inclusive). Skips months that 404."""
    s = requests.Session()
    frames = []
    for y in range(start_year, end_year + 1):
        for mth in range(1, 13):
            d = fetch_m1_month(symbol, y, mth, session=s)
            if not d.empty:
                frames.append(d)
            time.sleep(0.3)                 # be polite
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True).drop_duplicates("time").sort_values("time")
    return out.reset_index(drop=True)


def resample(m1: pd.DataFrame, tf: str) -> pd.DataFrame:
    """M1 -> lake timeframe OHLCV (bar-open label, no-lookahead)."""
    if m1.empty:
        return m1
    g = m1.set_index("time").resample(LAKE_TF[tf], label="left", closed="left").agg(AGG)
    return g.dropna(subset=["open", "high", "low", "close"]).reset_index()
