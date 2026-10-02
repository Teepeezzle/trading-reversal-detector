"""PHASE 8 / Step B — crypto alternative-data factor families (funding rate + perp/spot basis).

Economic signals the OHLCV-only search could not express. Each instrument's bar is enriched with:
  - funding: the last 8-hourly funding rate known at/before the bar close (ffilled, no-lookahead)
  - basis:   perp_close / spot_close - 1  (perpetual premium/discount)
Families (each a single side per hypothesis, chosen by params['side']):
  - fund_rev:  fade funding EXTREMES (z-score) — crowded longs (high +funding) -> short; crowded
               shorts (deep -funding) -> long. Mean-reversion on positioning.
  - fund_mom:  funding sign flip as a sentiment/carry trend — funding crosses >0 long, <0 short.
  - basis_rev: fade perp premium/discount z-score — rich perp -> short, cheap perp -> long.
Entries feed the SAME no-lookahead SL/TP engine (bt.simulate; ATR stop, next-bar-open entry), pooled
across the crypto universe, net of crypto cost, with buy-hold + random benchmarks. Judged on validation.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import indicators as ind
import backtest as bt
import costs as cost_model

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text("utf-8"))
MIN_TRADES = 100
ACLASS = "crypto"


def crypto_symbols() -> list[str]:
    return list(CFG.get("universe", {}).get("crypto", {}).get("symbols", []))


def enrich(perp: pd.DataFrame, spot: pd.DataFrame, fund: pd.DataFrame) -> pd.DataFrame:
    """Build a bar frame with OHLCV + funding (ffilled) + perp/spot basis. No-lookahead (backward asof)."""
    df = perp.dropna(subset=["open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)
    if spot is not None and not spot.empty:
        s = spot[["time", "close"]].rename(columns={"close": "spot_close"}).sort_values("time")
        df = pd.merge_asof(df, s, on="time", direction="backward")
        df["basis"] = df["close"] / df["spot_close"] - 1.0
    else:
        df["basis"] = np.nan
    if fund is not None and not fund.empty:
        f = fund[["time", "funding"]].sort_values("time")
        df = pd.merge_asof(df, f, on="time", direction="backward")
        df["funding"] = df["funding"].ffill()
    else:
        df["funding"] = np.nan
    return df


SUBDIR = "crypto_alt"       # lives under the main lake so it rides the research-lake- cache


def load_alt(lake, symbol: str, tf: str) -> pd.DataFrame:
    path = Path(lake) / SUBDIR / f"{symbol.replace('/', '')}_{tf}.csv.gz"
    return pd.read_csv(path, compression="gzip", parse_dates=["time"]).sort_values("time").reset_index(drop=True)


# ---- rule builders: (df, params) -> (entries bool Series, direction) ----
def fund_rev(df, p):
    n = int(p.get("n", 48)); z = float(p.get("z", 1.5)); side = p.get("side", "long")
    fz = ind.zscore(df["funding"], n)
    if side == "short":
        return (fz.shift(1) <= z) & (fz > z), "short"          # crowded longs -> fade down
    return (fz.shift(1) >= -z) & (fz < -z), "long"             # crowded shorts -> squeeze up


def fund_mom(df, p):
    side = p.get("side", "long")
    f = df["funding"]
    if side == "short":
        return (f.shift(1) >= 0) & (f < 0), "short"            # sentiment flips negative
    return (f.shift(1) <= 0) & (f > 0), "long"                 # sentiment flips positive


def basis_rev(df, p):
    n = int(p.get("n", 48)); z = float(p.get("z", 1.5)); side = p.get("side", "long")
    bz = ind.zscore(df["basis"], n)
    if side == "short":
        return (bz.shift(1) <= z) & (bz > z), "short"          # perp premium -> fade down
    return (bz.shift(1) >= -z) & (bz < -z), "long"             # perp discount -> up


RULES = {"fund_rev": fund_rev, "fund_mom": fund_mom, "basis_rev": basis_rev}


def run_one(df, rule_fn, params, horizon, sl, tp, c):
    entries, direction = rule_fn(df, params)
    atr = ind.atr(df, 14)
    trades = bt.simulate(df, entries.fillna(False), direction, atr, sl, tp, horizon, c["rt"], c["swap_daily"])
    if not trades.empty:
        trades["split"] = bt.tag_split(trades, bt.split_masks(df))
    return trades, direction, atr


def pooled_val_alt(lake, rule, params, horizon, tf, cost_mult=1.0) -> pd.DataFrame:
    """Pooled VALIDATION trades for one alt hypothesis (for the T-303 phase-8 judge)."""
    rule_fn = RULES[rule]; c = cost_model.get(ACLASS, cost_mult)
    frames = []
    for sym in crypto_symbols():
        try:
            df = load_alt(lake, sym, tf)
        except Exception:
            continue
        tr, _, _ = run_one(df, rule_fn, params, horizon, 1.5, 3.0, c)
        if not tr.empty:
            frames.append(tr[tr.split == "val"])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame({"split": [], "net_R": []})


def evaluate_alt(lake, rule, params, horizon, tf, sl=1.5, tp=3.0, cost_mult=1.0, rc_iters=8) -> dict:
    rule_fn = RULES[rule]; c = cost_model.get(ACLASS, cost_mult)
    all_trades, rnd_e, rnd_w, bh = [], [], [], []
    for sym in crypto_symbols():
        try:
            df = load_alt(lake, sym, tf)
        except Exception:
            continue
        trades_i, direction, atr = run_one(df, rule_fn, params, horizon, sl, tp, c)
        if not trades_i.empty:
            trades_i["symbol"] = sym; all_trades.append(trades_i)
        vn = int((trades_i.split == "val").sum()) if not trades_i.empty else 0
        r = bt.random_control(df, vn or 100, direction, atr, sl, tp, horizon, c["rt"], c["swap_daily"], iters=rc_iters)
        if np.isfinite(r["expR"]):
            rnd_e.append(r["expR"]); rnd_w.append(max(vn, 1))
        bh.append(bt.buy_hold_pct(df))

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame({"split": []})
    tr = trades[trades.split == "train"] if len(trades) else trades
    va = trades[trades.split == "val"] if len(trades) else trades
    st, sv = bt.stats(tr), bt.stats(va)
    rnd = round(float(np.average(rnd_e, weights=rnd_w)), 4) if rnd_e else np.nan
    bhm = round(float(np.mean(bh)), 1) if bh else np.nan
    passed = (sv["n"] >= MIN_TRADES and np.isfinite(sv["expR"]) and sv["expR"] > 0
              and np.isfinite(sv["pf"]) and sv["pf"] > 1 and (not np.isfinite(rnd) or sv["expR"] > rnd))
    verdict = "PASS" if passed else ("THIN" if sv["n"] < MIN_TRADES else "FAIL")
    return dict(n_syms=len(crypto_symbols()), train=st, val=sv, random_expR=rnd, buyhold_pct=bhm, verdict=verdict)
