"""PHASE 10 / N-8 — sentiment factor families on the AV daily sentiment series (gauntlet-judged).

Enriches price bars with the committed daily per-class sentiment (av_sentiment.csv.gz) using a strict
NO-LOOKAHEAD join: sentiment aggregated on calendar day D is only available from D+1, so a bar never
sees same-day-later news. Factor families (single side per hypothesis via params['side']):
  - sent_rev : fade sentiment extremes (z-score) — crowd too bearish -> long; too bullish -> short
  - sent_mom : follow sentiment momentum — z crosses up -> long; crosses down -> short
Entries feed the same SL/TP engine (bt.simulate), pooled across the asset class, net of cost, with
benchmarks. News = context/filter (D-021): every rule is a registry hypothesis judged on validation.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import indicators as ind
import backtest as bt
import costs as cost_model
import factors as F

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "altdata_committed" / "news" / "av_sentiment.csv.gz"
MIN_TRADES = 100
# which sentiment series drives each tradable class (macro news -> USD -> FX/metals)
CLASS_SENT = {"forex_majors": "forex_macro", "forex_crosses": "forex_macro", "metals": "forex_macro",
              "oil": "oil", "crypto": "crypto"}


def load_sentiment() -> pd.DataFrame:
    if not ARCHIVE.exists():
        return pd.DataFrame(columns=["date", "instrument_class", "sent_wmean", "n_articles"])
    df = pd.read_csv(ARCHIVE)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"])


def class_series(sent: pd.DataFrame, aclass: str) -> pd.DataFrame:
    src = CLASS_SENT.get(aclass)
    if sent is None or sent.empty or not src:
        return pd.DataFrame(columns=["date", "sent_wmean", "n_articles"])
    s = sent[sent["instrument_class"] == src][["date", "sent_wmean", "n_articles"]].sort_values("date")
    return s.reset_index(drop=True)


MAX_AGE_DAYS = 7          # per-type staleness cap (sentiment): older than this => EXCLUDED, never used


def enrich(bars: pd.DataFrame, sent_sub: pd.DataFrame, zwin: int = 20, max_age_days: int = MAX_AGE_DAYS) -> pd.DataFrame:
    """Attach no-lookahead sentiment to bars: day-D sentiment is available only from D+1 (asof backward),
    AND only if it is fresher than `max_age_days` (merge_asof `tolerance`). A bar whose nearest available
    sentiment is older than the cap gets NaN (no trade) — never a stale value used as if current. This is
    the research-side fix for the board's 825-day staleness bug (carry-forward learning #2)."""
    df = bars.sort_values("time").reset_index(drop=True)
    if sent_sub is None or sent_sub.empty:
        df["sent"] = np.nan; df["sent_z"] = np.nan; return df
    s = sent_sub.copy()
    s["avail"] = s["date"] + pd.Timedelta(days=1)          # known only the next day (no-lookahead)
    s = s.sort_values("avail")
    s["sent_z"] = ind.zscore(s["sent_wmean"], zwin)         # rolling z over trailing days
    m = pd.merge_asof(df, s[["avail", "sent_wmean", "sent_z"]], left_on="time", right_on="avail",
                      direction="backward", tolerance=pd.Timedelta(days=max_age_days))   # stale => NaN
    df["sent"] = m["sent_wmean"].values
    df["sent_z"] = m["sent_z"].values
    return df


# ---- rule builders: (df, params) -> (entries bool Series, direction) ----
def sent_rev(df, p):
    z = float(p.get("z", 1.5)); side = p.get("side", "long")
    sz = df["sent_z"]
    if side == "short":
        return (sz.shift(1) <= z) & (sz > z), "short"      # over-bullish -> fade down
    return (sz.shift(1) >= -z) & (sz < -z), "long"         # over-bearish -> bounce up


def sent_mom(df, p):
    z = float(p.get("z", 0.5)); side = p.get("side", "long")
    sz = df["sent_z"]
    if side == "short":
        return (sz.shift(1) >= -z) & (sz < -z), "short"    # sentiment turning down
    return (sz.shift(1) <= z) & (sz > z), "long"           # sentiment turning up


RULES = {"sent_rev": sent_rev, "sent_mom": sent_mom}


def _run(df, rule_fn, params, horizon, c):
    entries, direction = rule_fn(df, params)
    atr = ind.atr(df, 14)
    tr = bt.simulate(df, entries.fillna(False), direction, atr, 1.5, 3.0, horizon, c["rt"], c["swap_daily"])
    if not tr.empty:
        tr["split"] = bt.tag_split(tr, bt.split_masks(df))
    return tr, direction, atr


def pooled_val_sent(lake, aclass, rule, params, horizon, tf, cost_mult=1.0, sent=None) -> pd.DataFrame:
    if sent is None:
        sent = load_sentiment()
    rule_fn = RULES[rule]; c = cost_model.get(aclass, cost_mult); ss = class_series(sent, aclass)
    frames = []
    for sym in F.get_symbols(aclass):
        try:
            df = F.load(lake, aclass, sym, tf)
        except Exception as exc:  # noqa: BLE001  fail LOUD — a missing symbol is a visible gap, not clean data
            print(f"sentfactor: SKIP {aclass}/{sym} {tf} ({exc})", flush=True); continue
        df = enrich(df, ss)
        tr, _, _ = _run(df, rule_fn, params, horizon, c)
        if not tr.empty:
            frames.append(tr[tr.split == "val"])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame({"split": [], "net_R": []})


def evaluate_sent(lake, aclass, rule, params, horizon, tf, cost_mult=1.0, rc_iters=8) -> dict:
    sent = load_sentiment()
    rule_fn = RULES[rule]; c = cost_model.get(aclass, cost_mult); ss = class_series(sent, aclass)
    all_t, rnd_e, rnd_w, bh = [], [], [], []
    for sym in F.get_symbols(aclass):
        try:
            df = F.load(lake, aclass, sym, tf)
        except Exception as exc:  # noqa: BLE001  fail LOUD — a missing symbol is a visible gap, not clean data
            print(f"sentfactor: SKIP {aclass}/{sym} {tf} ({exc})", flush=True); continue
        df = enrich(df, ss)
        tr, direction, atr = _run(df, rule_fn, params, horizon, c)
        if not tr.empty:
            all_t.append(tr)
        vn = int((tr.split == "val").sum()) if not tr.empty else 0
        r = bt.random_control(df, vn or 100, direction, atr, 1.5, 3.0, horizon, c["rt"], c["swap_daily"], iters=rc_iters)
        if np.isfinite(r["expR"]):
            rnd_e.append(r["expR"]); rnd_w.append(max(vn, 1))
        bh.append(bt.buy_hold_pct(df))
    trades = pd.concat(all_t, ignore_index=True) if all_t else pd.DataFrame({"split": []})
    st = bt.stats(trades[trades.split == "train"] if len(trades) else trades)
    sv = bt.stats(trades[trades.split == "val"] if len(trades) else trades)
    rnd = round(float(np.average(rnd_e, weights=rnd_w)), 4) if rnd_e else np.nan
    passed = (sv["n"] >= MIN_TRADES and np.isfinite(sv["expR"]) and sv["expR"] > 0
              and np.isfinite(sv["pf"]) and sv["pf"] > 1 and (not np.isfinite(rnd) or sv["expR"] > rnd))
    verdict = "PASS" if passed else ("THIN" if sv["n"] < MIN_TRADES else "FAIL")
    return dict(train=st, val=sv, random_expR=rnd, buyhold_pct=round(float(np.mean(bh)), 1) if bh else np.nan,
                verdict=verdict)
