"""PHASE 9 / N-5 — news as a GATE + regime-tag on technical rules (standing rule D-021).

News is CONTEXT & FILTER, never a standalone signal: a news hypothesis = (technical base rule) AND
(a news condition). This module enriches price bars with no-lookahead news features and defines
testable, non-discretionary news gates, then evaluates BASE vs GATED so we can answer D-021 §6:
does the gate improve expectancy after cost, or merely cut trade count?

News features on each bar (all no-lookahead, from src/news.py):
  - news_surprise : signed surprise of the most recent relevant release known at the bar open
  - news_age_h    : hours since that release
  - mins_to_next_h: minutes to the next scheduled high-impact release (inf if none ahead)

Gates (generic, non-discretionary — the backtest decides what helps; no human view imposed):
  - avoid_pre : skip entries within 30 min before a high-impact release (the mandatory §3 gate)
  - quiet     : only when no high event in the next 4h AND none in the last 24h (calm regime)
  - post_event: only within 24h AFTER a release (post-surprise regime)
  - surp_pos / surp_neg : only when the last relevant surprise was positive / negative (regime split)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import indicators as ind
import backtest as bt
import costs as cost_model
import factors as F
import news as NW

ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = ROOT / "altdata_committed" / "news"
MIN_TRADES = 100

# which release names apply to each asset class
MACRO = ["CPI", "PCE", "NFP", "GDP", "Unemployment", "FedFunds"]
NEWS_NAMES = {"oil": ["CrudeInventories"], "forex_majors": MACRO,
              "forex_crosses": MACRO, "metals": MACRO}


def load_news() -> pd.DataFrame:
    frames = []
    for f in ("fred.csv.gz", "eia.csv.gz"):
        p = NEWS_DIR / f
        if p.exists():
            frames.append(NW.load(p))
    return pd.concat(frames, ignore_index=True) if frames else NW.empty()


def enrich_news(bars: pd.DataFrame, news: pd.DataFrame, aclass: str) -> pd.DataFrame:
    names = NEWS_NAMES.get(aclass, [])
    sub = news[news["name"].isin(names)] if (news is not None and not news.empty and names) else NW.empty()
    out = NW.latest_asof(bars, sub, names=names)              # adds news_name/news_surprise/news_age_h
    out["mins_to_next_h"] = NW.minutes_to_next(bars, sub, impact=("high",)).values
    return out


# ---- gates: enriched df -> bool mask (True = entry allowed) ----
def g_avoid_pre(df):   return ~((df["mins_to_next_h"] >= 0) & (df["mins_to_next_h"] < 30))
def g_quiet(df):       return (df["mins_to_next_h"] > 240) & ((df["news_age_h"] > 24) | df["news_age_h"].isna())
def g_post_event(df):  return df["news_age_h"] <= 24
def g_surp_pos(df):    return df["news_surprise"] > 0
def g_surp_neg(df):    return df["news_surprise"] < 0

NEWS_GATES = {"avoid_pre": g_avoid_pre, "quiet": g_quiet, "post_event": g_post_event,
              "surp_pos": g_surp_pos, "surp_neg": g_surp_neg}


def _pooled(lake, aclass, rule, params, hz, tf, gate_fn, cost_mult, news):
    """Pooled trades across the class for base (gate_fn=None) or gated entries. Returns trades df."""
    rule_fn = F.RULES[rule]; c = cost_model.get(aclass, cost_mult)
    frames = []
    for sym in F.get_symbols(aclass):
        try:
            df = F.load(lake, aclass, sym, tf)
        except Exception:
            continue
        df = enrich_news(df, news, aclass)
        entries, direction = rule_fn(df, params)
        entries = entries.fillna(False)
        if gate_fn is not None:
            entries = entries & gate_fn(df).reindex(entries.index).fillna(False).astype(bool)
        atr = ind.atr(df, 14)
        tr = bt.simulate(df, entries, direction, atr, 1.5, 3.0, hz, c["rt"], c["swap_daily"])
        if not tr.empty:
            tr["split"] = bt.tag_split(tr, bt.split_masks(df)); frames.append(tr)
    if not frames:
        return pd.DataFrame({"split": [], "net_R": []})
    return pd.concat(frames, ignore_index=True)


def evaluate_news_gate(lake, aclass, rule, params, hz, tf, gate, cost_mult=1.0, news=None) -> dict:
    """BASE vs GATED on validation (D-021 §6). Returns both stats + the gated val R (for MTC)."""
    if news is None:
        news = load_news()
    gate_fn = NEWS_GATES[gate]
    base = _pooled(lake, aclass, rule, params, hz, tf, None, cost_mult, news)
    gated = _pooled(lake, aclass, rule, params, hz, tf, gate_fn, cost_mult, news)
    bv = bt.stats(base[base.split == "val"] if len(base) else base)
    gv = bt.stats(gated[gated.split == "val"] if len(gated) else gated)
    return dict(base=bv, gated=gv, gated_val=(gated[gated.split == "val"] if len(gated) else gated))
