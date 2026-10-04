"""PHASE 9 / news layer — schema + no-lookahead join (standing rule D-021, spec NEWS_LAYER.md).

News is CONTEXT & FILTER, never a standalone signal. Every item carries UTC `published_at` and
`first_available_at`; a signal may only reference news with `first_available_at <= bar_open`. This
module defines the canonical news table schema and a strict as-of join so no future release leaks
into a decision bar.

Canonical columns (one row per event):
  event_id, source, name, instrument_class, published_at, first_available_at,
  actual, prior, forecast, surprise, impact
`surprise` = actual - forecast when a forecast exists, else actual - prior (direction of the beat).
`impact` in {high, medium, low}. Times are tz-naive UTC (matching the lake).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["event_id", "source", "name", "instrument_class", "published_at", "first_available_at",
           "actual", "prior", "forecast", "surprise", "impact"]


def empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce to the canonical schema: UTC tz-naive times, numeric values, dropped if undated."""
    if df is None or df.empty:
        return empty()
    out = df.copy()
    for c in COLUMNS:
        if c not in out.columns:
            out[c] = np.nan
    for c in ("published_at", "first_available_at"):
        out[c] = pd.to_datetime(out[c], utc=True, errors="coerce").dt.tz_localize(None)
    # no timestamp => unusable (D-021 §2): discard
    out = out.dropna(subset=["first_available_at"])
    for c in ("actual", "prior", "forecast", "surprise"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out.loc[out["surprise"].isna(), "surprise"] = out["actual"] - out["forecast"]
    out.loc[out["surprise"].isna(), "surprise"] = out["actual"] - out["prior"]
    return out[COLUMNS].sort_values("first_available_at").reset_index(drop=True)


def save(df: pd.DataFrame, path) -> None:
    normalize(df).to_csv(path, index=False, compression="gzip")


def load(path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return empty()
    df = pd.read_csv(p, compression="gzip")
    for c in ("published_at", "first_available_at"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def latest_asof(bars: pd.DataFrame, news: pd.DataFrame, names=None, max_age_days=None) -> pd.DataFrame:
    """For each bar, attach the most recent news item KNOWN at the bar open (first_available_at <=
    time). No-lookahead. Returns bars + columns: news_name, news_surprise, news_age_h. `names` filters
    to specific event names (e.g. ['CPI','NFP']). If `max_age_days` is set, a release older than that
    cap is EXCLUDED (NaN) rather than carried stale (per-type staleness rule; carry-forward learning #2 —
    e.g. ~45d for monthly CPI/NFP). Default None preserves prior behaviour for completed phases."""
    if bars.empty:
        return bars
    b = bars.sort_values("time").reset_index(drop=True)
    if news is None or news.empty:
        b["news_name"] = np.nan; b["news_surprise"] = np.nan; b["news_age_h"] = np.nan
        return b
    n = news.copy()
    if names:
        n = n[n["name"].isin(names)]
    n = n.dropna(subset=["first_available_at"]).sort_values("first_available_at")
    if n.empty:
        b["news_name"] = np.nan; b["news_surprise"] = np.nan; b["news_age_h"] = np.nan
        return b
    tol = pd.Timedelta(days=max_age_days) if max_age_days else None
    m = pd.merge_asof(b, n[["first_available_at", "name", "surprise"]],
                      left_on="time", right_on="first_available_at", direction="backward", tolerance=tol)
    m["news_name"] = m["name"]; m["news_surprise"] = m["surprise"]
    m["news_age_h"] = (m["time"] - m["first_available_at"]).dt.total_seconds() / 3600.0
    return m.drop(columns=["name", "surprise", "first_available_at"])


def minutes_to_next(bars: pd.DataFrame, news: pd.DataFrame, impact=("high",)) -> pd.Series:
    """Minutes from each bar open to the NEXT scheduled high-impact event (for the 30-min pre-release
    gate, D-021 §3). Uses first_available_at as the event time. inf when none ahead."""
    if bars.empty:
        return pd.Series(dtype=float)
    ev = news[news["impact"].isin(impact)].dropna(subset=["first_available_at"]) if news is not None and not news.empty else None
    b = bars.sort_values("time").reset_index(drop=True)
    if ev is None or ev.empty:
        return pd.Series(np.inf, index=b.index)
    et = np.sort(ev["first_available_at"].values.astype("datetime64[ns]"))
    bt = b["time"].values.astype("datetime64[ns]")
    idx = np.searchsorted(et, bt, side="left")
    out = np.full(len(bt), np.inf)
    valid = idx < len(et)
    out[valid] = (et[idx[valid]] - bt[valid]) / np.timedelta64(1, "m")
    return pd.Series(out, index=b.index)
