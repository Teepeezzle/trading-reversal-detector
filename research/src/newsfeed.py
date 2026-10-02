"""PHASE 9 / N-7 — newsdata.io forward headline collector (standing rule D-021 §4, source §8).

newsdata.io free = /latest (~48h), no archive, no sentiment (D-027). So this is a FORWARD collector:
each scheduled run fetches the latest finance-relevant headlines (timestamped) and APPENDS new ones
(dedup by article_id) to a committed archive, self-building a timestamped corpus over time for a
future programmatic keyword/event-flow factor and for live briefing context. It does NOT backfill
history and carries no backtest edge on its own. Compact rows only (no article body); sentiment is
paid and omitted — any sentiment/flow signal must be computed by us, timestamped, never discretionary.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

BASE = "https://newsdata.io/api/1/latest"
UA = {"User-Agent": "Mozilla/5.0 (research)"}
ARCHIVE = Path(__file__).resolve().parent.parent / "altdata_committed" / "news" / "headlines.csv.gz"
COLUMNS = ["article_id", "published_at", "query_tag", "instrument_class", "title",
           "source_id", "country", "category", "keywords", "link"]

# query -> (tag, instrument_class). Each query costs ~1 credit / 10 articles (free = 200 credits/day).
QUERIES = [
    ({"category": "business", "language": "en"}, ("business", "general")),
    ({"q": "federal reserve OR inflation OR interest rate OR jobs report", "language": "en"}, ("macro", "forex_macro")),
    ({"q": "OPEC OR crude oil OR oil inventories OR refinery", "language": "en"}, ("oil", "oil")),
    ({"q": "bitcoin OR ethereum OR crypto ETF OR stablecoin", "language": "en"}, ("crypto", "crypto")),
]


def _join(v) -> str:
    if isinstance(v, (list, tuple)):
        return "|".join(str(x) for x in v if x)
    return "" if v is None else str(v)


def fetch(api_key: str, params: dict) -> list[dict]:
    try:
        r = requests.get(BASE, params={**params, "apikey": api_key}, headers=UA, timeout=30)
        if r.status_code != 200:
            print(f"    newsdata HTTP {r.status_code}: {r.text[:160]!r}"); return []
        return (r.json() or {}).get("results") or []
    except Exception as exc:  # noqa: BLE001
        print(f"    newsdata error: {exc}"); return []


def to_rows(results: list[dict], tag: str, aclass: str) -> pd.DataFrame:
    rows = []
    for a in results:
        aid = a.get("article_id")
        if not aid:
            continue
        rows.append(dict(article_id=aid,
                         published_at=pd.to_datetime(a.get("pubDate"), utc=True, errors="coerce"),
                         query_tag=tag, instrument_class=aclass,
                         title=str(a.get("title") or "")[:200], source_id=a.get("source_id"),
                         country=_join(a.get("country")), category=_join(a.get("category")),
                         keywords=_join(a.get("keywords")), link=a.get("link")))
    df = pd.DataFrame(rows, columns=COLUMNS)
    if not df.empty:
        df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce").dt.tz_localize(None)
        df = df.dropna(subset=["published_at"])
    return df


def load_archive() -> pd.DataFrame:
    if not ARCHIVE.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(ARCHIVE, compression="gzip")
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    return df


def append_archive(new: pd.DataFrame) -> tuple[int, int]:
    """Append new rows, dedup by article_id. Returns (added, total)."""
    old = load_archive()
    before = len(old)
    combined = pd.concat([old, new], ignore_index=True) if not old.empty else new
    combined = combined.drop_duplicates(subset=["article_id"], keep="first").sort_values("published_at")
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(ARCHIVE, index=False, compression="gzip")
    return len(combined) - before, len(combined)


def collect(api_key: str) -> tuple[int, int, int]:
    """Run all queries, append new rows. Returns (fetched, added, total)."""
    frames = []
    for params, (tag, aclass) in QUERIES:
        res = fetch(api_key, params)
        print(f"  {tag:<8} fetched {len(res)}")
        if res:
            frames.append(to_rows(res, tag, aclass))
        time.sleep(0.5)
    fetched = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    added, total = append_archive(fetched) if not fetched.empty else (0, len(load_archive()))
    return len(fetched), added, total
