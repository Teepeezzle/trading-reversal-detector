"""PHASE 9 / news layer — fetch macro release data (N-1 FRED, N-2 EIA) into the news table.

Standing rule D-021 (spec NEWS_LAYER.md): API-sourced, timestamped, no-lookahead. Writes
research/data/news/{fred,eia}.csv.gz in the canonical schema (src/news.py). Needs FRED_API_KEY /
EIA_API_KEY in the env; if a key is missing, that source is skipped and logged (never fabricated).

FRED: first-release ("output_type=4") observations for key US macro series, so each value's
realtime_start is the actual first-publication date; stamped at the standard US release time (ET).
EIA: weekly crude-oil stocks ex-SPR; the release lands the following Wednesday 10:30 ET (approx).
Time-of-day is a documented approximation (ET->UTC fixed +5/+4h); only the 30-min pre-release gate is
time-sensitive, and it has margin.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import news as N   # noqa: E402

BLOCKERS = ROOT / "BLOCKERS.md"
UA = {"User-Agent": "Mozilla/5.0 (research)"}
ET_OFFSET = pd.Timedelta(hours=4)        # ET->UTC (EDT); documented ~1h approximation across DST

# FRED series -> (event name, release time ET, impact). forex/metals macro.
FRED_SERIES = {
    "CPIAUCSL": ("CPI", "08:30", "high"),
    "PCEPI":    ("PCE", "08:30", "high"),
    "PAYEMS":   ("NFP", "08:30", "high"),
    "UNRATE":   ("Unemployment", "08:30", "medium"),
    "GDPC1":    ("GDP", "08:30", "high"),
    "FEDFUNDS": ("FedFunds", "14:00", "medium"),
}


def log_blocker(msg: str):
    with BLOCKERS.open("a", encoding="utf-8") as f:
        f.write(f"\n## News refresh\n- {msg}\n")
    print(msg)


def fetch_fred(start: str) -> pd.DataFrame:
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        log_blocker("N-1 FRED: FRED_API_KEY not set — skipped."); return N.empty()
    rows = []
    for sid, (name, et, impact) in FRED_SERIES.items():
        try:
            r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                             params={"series_id": sid, "api_key": key, "file_type": "json",
                                     "realtime_start": start, "realtime_end": "9999-12-31",
                                     "output_type": 4, "observation_start": start},
                             headers=UA, timeout=30)
            if r.status_code != 200:
                print(f"    FRED {sid}: HTTP {r.status_code} {r.text[:160]!r}"); continue
            obs = (r.json() or {}).get("observations") or []
            hh, mm = et.split(":")
            for o in obs:
                val = o.get("value")
                if val in (None, ".", ""):
                    continue
                rel = pd.to_datetime(o.get("realtime_start"), errors="coerce")
                if pd.isna(rel):
                    continue
                pub = rel + pd.Timedelta(hours=int(hh), minutes=int(mm)) + ET_OFFSET
                rows.append(dict(event_id=f"FRED:{sid}:{o['date']}", source="FRED", name=name,
                                 instrument_class="forex_macro", published_at=pub, first_available_at=pub,
                                 actual=float(val), prior=None, forecast=None, surprise=None, impact=impact))
        except Exception as exc:  # noqa: BLE001
            print(f"    FRED {sid}: ERR {exc}")
    df = N.normalize(pd.DataFrame(rows))
    # prior = previous actual for the same series/name (for surprise-vs-prior direction)
    if not df.empty:
        df["prior"] = df.groupby("name")["actual"].shift(1)
        df.loc[df["surprise"].isna(), "surprise"] = df["actual"] - df["prior"]
    print(f"  FRED: {len(df)} release events across {df['name'].nunique() if len(df) else 0} series")
    return df


def fetch_eia(start: str) -> pd.DataFrame:
    key = os.environ.get("EIA_API_KEY", "")
    if not key:
        log_blocker("N-2 EIA: EIA_API_KEY not set — skipped."); return N.empty()
    try:
        r = requests.get("https://api.eia.gov/v2/petroleum/stoc/wstk/data/",
                         params={"api_key": key, "frequency": "weekly", "data[0]": "value",
                                 "facets[series][]": "WCESTUS1", "start": start,
                                 "sort[0][column]": "period", "sort[0][direction]": "asc", "length": 5000},
                         headers=UA, timeout=30)
        if r.status_code != 200:
            print(f"    EIA: HTTP {r.status_code} {r.text[:160]!r}"); return N.empty()
        data = ((r.json() or {}).get("response") or {}).get("data") or []
    except Exception as exc:  # noqa: BLE001
        print(f"    EIA: ERR {exc}"); return N.empty()
    rows = []
    for d in data:
        period = pd.to_datetime(d.get("period"), errors="coerce")
        val = d.get("value")
        if pd.isna(period) or val in (None, ""):
            continue
        pub = period + pd.Timedelta(days=5, hours=10, minutes=30) + ET_OFFSET  # ~ following Wed 10:30 ET
        rows.append(dict(event_id=f"EIA:WCESTUS1:{d.get('period')}", source="EIA",
                         name="CrudeInventories", instrument_class="oil", published_at=pub,
                         first_available_at=pub, actual=float(val), prior=None, forecast=None,
                         surprise=None, impact="high"))
    df = N.normalize(pd.DataFrame(rows))
    if not df.empty:
        df["prior"] = df["actual"].shift(1)
        df["surprise"] = df["actual"] - df["prior"]       # weekly build/draw
    print(f"  EIA: {len(df)} weekly crude-inventory releases")
    return df


def _num(v):
    """Parse FMP numeric-ish values: 3.2, '3.2%', '200K', '1.5M', '-0.3B' -> float (NaN if unparseable)."""
    if v is None or v == "":
        return float("nan")
    try:
        return float(v)
    except (TypeError, ValueError):
        pass
    s = str(v).strip().replace(",", "").replace("%", "")
    mult = 1.0
    if s[-1:].upper() in ("K", "M", "B", "T"):
        mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[s[-1].upper()]; s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return float("nan")


def fetch_fmp(start: str) -> pd.DataFrame:
    """N-3 — FMP economic calendar: US macro events with TRUE consensus surprise (actual - estimate).
    Free Finnhub cannot serve this (premium-gated); FMP free Basic covers it. Needs FMP_API_KEY."""
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        log_blocker("N-3 FMP: FMP_API_KEY not set — skipped (Finnhub economic calendar is premium-gated)."); return N.empty()
    rows = []
    cur = pd.Timestamp(start)                                    # tz-naive
    end = pd.Timestamp.now("UTC").tz_localize(None).normalize() + pd.Timedelta(days=14)  # tz-naive UTC
    while cur < end:
        nxt = min(cur + pd.Timedelta(days=90), end)
        try:
            r = requests.get("https://financialmodelingprep.com/stable/economic-calendar",
                             params={"from": cur.date().isoformat(), "to": nxt.date().isoformat(), "apikey": key},
                             headers=UA, timeout=30)
            if r.status_code != 200:
                print(f"    FMP: HTTP {r.status_code} {r.text[:160]!r}"); break
            data = r.json()
            if isinstance(data, dict):           # error object (e.g. premium/limit)
                print(f"    FMP: {str(data)[:180]}"); break
        except Exception as exc:  # noqa: BLE001
            print(f"    FMP: ERR {exc}"); break
        for d in data:
            if (d.get("country") or "").upper() not in ("US", "USA", "UNITED STATES"):
                continue
            impact = (d.get("impact") or "").lower()
            if impact not in ("high", "medium"):
                continue
            t = pd.to_datetime(d.get("date"), errors="coerce", utc=True)
            if pd.isna(t):
                continue
            rows.append(dict(event_id=f"FMP:{d.get('event')}:{d.get('date')}", source="FMP",
                             name=str(d.get("event"))[:48], instrument_class="forex_macro",
                             published_at=t.tz_localize(None), first_available_at=t.tz_localize(None),
                             actual=_num(d.get("actual")), prior=_num(d.get("previous")),
                             forecast=_num(d.get("estimate")), surprise=None,
                             impact="high" if impact == "high" else "medium"))
        cur = nxt
    df = N.normalize(pd.DataFrame(rows))        # surprise = actual - forecast (true consensus) in normalize
    print(f"  FMP: {len(df)} US macro calendar events (consensus surprise)")
    return df


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-01-01")
    a = ap.parse_args()
    out = ROOT / "altdata_committed" / "news"; out.mkdir(parents=True, exist_ok=True)  # tracked (small, static)

    fred = fetch_fred(a.start)
    if not fred.empty:
        N.save(fred, out / "fred.csv.gz")
    eia = fetch_eia(a.start)
    if not eia.empty:
        N.save(eia, out / "eia.csv.gz")
    fmp = fetch_fmp(a.start)
    if not fmp.empty:
        N.save(fmp, out / "fmp_calendar.csv.gz")
    print(f"done. fred={len(fred)} eia={len(eia)} fmp={len(fmp)} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
