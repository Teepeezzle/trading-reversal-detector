"""PHASE 10 / N-8 — Alpha Vantage NEWS_SENTIMENT harvest + daily aggregation (portable REST).

AV NEWS_SENTIMENT is the first FREE, historical, timestamped, pre-scored sentiment feed we found
(overall_sentiment_score per article + topics + per-asset ticker_sentiment incl FOREX:/CRYPTO:). This
module fetches it via the REST API (key from env, so it runs in Actions) and aggregates to a DAILY,
relevance-weighted sentiment series per instrument class. Free tier = 25 req/day → the harvester is
windowed + resumable (bounded batch per run). No-lookahead downstream: a day's sentiment is only
usable at that day's close (the factor joins it with a 1-day lag / asof backward).

Topic -> instrument class (macro news drives FX/metals via the USD; energy -> oil; blockchain -> crypto):
  economy_macro / economy_monetary -> forex_macro ;  energy_transportation -> oil ;  blockchain -> crypto
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://www.alphavantage.co/query"
UA = {"User-Agent": "Mozilla/5.0 (research)"}
# one primary topic per class (keeps free-tier call count bounded)
TOPIC_CLASS = {"economy_macro": "forex_macro", "energy_transportation": "oil", "blockchain": "crypto"}
RATE_SLEEP = 15.0        # AV free ~5/min; stay well under


def _is_limit(j: dict) -> bool:
    txt = " ".join(str(j.get(k, "")) for k in ("Note", "Information", "Error Message")).lower()
    return bool(txt) and ("limit" in txt or "thank you" in txt or "higher api call" in txt)


def fetch_window(api_key: str, topic: str, time_from: str, time_to: str, limit: int = 1000):
    """Returns (feed_list, limited_bool). feed is AV NEWS_SENTIMENT articles for the window."""
    try:
        r = requests.get(BASE, params={"function": "NEWS_SENTIMENT", "topics": topic,
                                       "time_from": time_from, "time_to": time_to,
                                       "limit": limit, "sort": "EARLIEST", "apikey": api_key},
                         headers=UA, timeout=40)
        if r.status_code != 200:
            print(f"    AV HTTP {r.status_code}: {r.text[:140]!r}"); return [], False
        j = r.json() or {}
        if _is_limit(j):
            print(f"    AV rate limit: {str(j)[:160]}"); return [], True
        return (j.get("feed") or []), False
    except Exception as exc:  # noqa: BLE001
        print(f"    AV error: {exc}"); return [], False


def aggregate_daily(feed: list, aclass: str) -> pd.DataFrame:
    """Relevance-weighted daily mean sentiment + article count for one class, from one topic's feed."""
    rows = []
    for a in feed:
        t = pd.to_datetime(a.get("time_published"), format="%Y%m%dT%H%M%S", errors="coerce")
        if pd.isna(t):
            continue
        s = a.get("overall_sentiment_score")
        if s is None:
            continue
        # weight by this topic's relevance within the article (fallback 0.5)
        w = 0.5
        for tp in (a.get("topics") or []):
            if tp.get("topic") and tp["topic"].lower().startswith(aclass_topic(aclass)[:6]):
                try:
                    w = float(tp.get("relevance_score", 0.5))
                except (TypeError, ValueError):
                    w = 0.5
                break
        rows.append((t.normalize(), float(s), w))
    if not rows:
        return pd.DataFrame(columns=["date", "instrument_class", "sent_wmean", "n_articles"])
    df = pd.DataFrame(rows, columns=["date", "s", "w"])
    g = df.groupby("date").apply(
        lambda x: pd.Series({"sent_wmean": (x["s"] * x["w"]).sum() / max(x["w"].sum(), 1e-9),
                             "n_articles": len(x)}), include_groups=False).reset_index()
    g["instrument_class"] = aclass
    return g[["date", "instrument_class", "sent_wmean", "n_articles"]]


def aclass_topic(aclass: str) -> str:
    for topic, cls in TOPIC_CLASS.items():
        if cls == aclass:
            return topic
    return ""


def months(start: str) -> list[tuple[str, str, str]]:
    """List (topic-agnostic) month windows [start .. now] as (ym, time_from, time_to) AV strings."""
    out = []
    cur = pd.Timestamp(start).normalize().replace(day=1)
    end = pd.Timestamp(datetime.now(timezone.utc).date()).replace(day=1)
    while cur <= end:
        nxt = (cur + pd.offsets.MonthEnd(1))
        out.append((cur.strftime("%Y%m"), cur.strftime("%Y%m%dT0000"), nxt.strftime("%Y%m%dT2359")))
        cur = cur + pd.offsets.MonthBegin(1)
    return out
