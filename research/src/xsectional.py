"""PHASE 6 — cross-sectional relative-strength engine (portable, no-lookahead).

Structurally different from the per-instrument rules of Phases 3-5: each rebalance, rank the
instruments of an asset class by trailing momentum and hold a LONG top-k (optionally SHORT bottom-k)
book for H bars, then rebalance. Per-instrument signal rules cannot capture relative strength; this
can. One "observation" = one NON-OVERLAPPING rebalance period (so periods are ~independent, keeping
the Sharpe / multiple-testing inference honest). Period return is in DECIMAL units (not ATR-R).

No-lookahead: rank uses closes through bar t; the book is entered at bar t+1's OPEN and exited at
bar t+1+H's OPEN. Net of cost: one round-trip per period (whole book turns over) + an overnight-swap
estimate from the holding span. Benchmarks: equal-weight buy-&-hold of the class, and a random-pick
control with the same k / H.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import factors as F
import backtest as bt
import costs as cost_model

MIN_PERIODS = 100
BAR_HOURS = {"15min": 0.25, "1h": 1.0, "2h": 2.0, "3h": 3.0, "4h": 4.0, "1day": 24.0}


def load_panels(lake, aclass, tf):
    """Inner-join open+close across every instrument in the class on a common time index."""
    closes, opens = {}, {}
    for sym in F.get_symbols(aclass):
        try:
            df = F.load(lake, aclass, sym, tf)
        except Exception:
            continue
        df = df.dropna(subset=["open", "close"]).set_index("time")
        closes[sym] = df["close"]; opens[sym] = df["open"]
    if len(closes) < 3:
        return None, None
    close = pd.DataFrame(closes).dropna(how="any").sort_index()
    opn = pd.DataFrame(opens).reindex(close.index)
    return close, opn


def _periods(close, opn, L, H, k, mode, rt, swap_daily, nights_per_bar, pick="mom", seed=0):
    """Build the non-overlapping rebalance-period return series. pick='mom' ranks by momentum;
    'rand' picks at random (benchmark). Returns a trades-like DataFrame (entry_time, net_R)."""
    T = len(close); idx = close.index
    cols = close.columns
    mom = close / close.shift(L) - 1.0
    rng = np.random.default_rng(seed)
    rows = []
    t = L
    while t + 1 + H < T:
        m = mom.iloc[t].dropna()
        need = 2 * k if mode == "ls" else k           # enough ranked names to fill the book
        if len(m) >= need:
            names = list(m.index)
            if pick == "mom":
                ranked = m.sort_values(ascending=False).index
                longs = list(ranked[:k]); shorts = list(ranked[-k:]) if mode == "ls" else []
            else:
                perm = list(rng.permutation(names))
                longs = perm[:k]; shorts = perm[k:2 * k] if mode == "ls" else []
            ent = opn.iloc[t + 1]; ex = opn.iloc[t + 1 + H]
            def avg_ret(sel):
                r = (ex[sel] / ent[sel] - 1.0).replace([np.inf, -np.inf], np.nan).dropna()
                return float(r.mean()) if len(r) else np.nan
            gl = avg_ret(longs)
            gs = avg_ret(shorts) if shorts else 0.0
            if np.isfinite(gl) and np.isfinite(gs):
                gross = gl - gs
                cost = rt + swap_daily * (H * nights_per_bar)
                rows.append(dict(entry_time=idx[t + 1], net_R=round(gross - cost, 6), bars=H))
        t += H
    return pd.DataFrame(rows)


def evaluate_xs(lake, aclass, tf, L, H, k=2, mode="ls", cost_mult=1.0, rc_iters=8) -> dict:
    close, opn = load_panels(lake, aclass, tf)
    if close is None or len(close) < L + 2 * H + 10:
        return dict(n_syms=0, train=bt.stats(None), val=bt.stats(None), random_expR=np.nan,
                    buyhold_pct=np.nan, verdict="THIN")
    c = cost_model.get(aclass, cost_mult)
    nights_per_bar = BAR_HOURS.get(tf, 1.0) / 24.0

    tr = _periods(close, opn, L, H, k, mode, c["rt"], c["swap_daily"], nights_per_bar, pick="mom")
    if tr.empty:
        return dict(n_syms=close.shape[1], train=bt.stats(None), val=bt.stats(None),
                    random_expR=np.nan, buyhold_pct=np.nan, verdict="THIN")
    tr["split"] = bt.tag_split(tr, bt.split_masks(pd.DataFrame({"time": close.index})))
    st = bt.stats(tr[tr.split == "train"]); sv = bt.stats(tr[tr.split == "val"])

    # random-pick control (same k/H), validation expectancy, averaged over iters
    rnd = []
    for s in range(rc_iters):
        rr = _periods(close, opn, L, H, k, mode, c["rt"], c["swap_daily"], nights_per_bar, pick="rand", seed=s + 1)
        if not rr.empty:
            rr["split"] = bt.tag_split(rr, bt.split_masks(pd.DataFrame({"time": close.index})))
            e = bt.stats(rr[rr.split == "val"])["expR"]
            if np.isfinite(e):
                rnd.append(e)
    random_expR = round(float(np.mean(rnd)), 6) if rnd else np.nan

    # equal-weight buy-&-hold of the class over the full span
    bh = float(((close.iloc[-1] / close.iloc[0] - 1.0).mean()) * 100)

    passed = (sv["n"] >= MIN_PERIODS and np.isfinite(sv["expR"]) and sv["expR"] > 0
              and np.isfinite(sv["pf"]) and sv["pf"] > 1
              and (not np.isfinite(random_expR) or sv["expR"] > random_expR))
    verdict = "PASS" if passed else ("THIN" if sv["n"] < MIN_PERIODS else "FAIL")
    return dict(n_syms=close.shape[1], train=st, val=sv, random_expR=random_expR,
                buyhold_pct=round(bh, 1), verdict=verdict)
