"""Shared Phase-3 factor logic — rule builders + pooled evaluation (used by single_factor & sweep).

Keeps the CLI tester and the batch sweep DRY and identical. A rule returns (entries, direction);
`evaluate` runs it across every instrument in an asset class (each split on its own 60/20/20
timeline, trades pooled by split tag) and returns net-of-cost train/val stats plus the buy-&-hold
and random-entry benchmarks and a verdict. Judged on VALIDATION; holdout untouched.
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


# ---- rule builders: (df, params) -> (entries bool Series, direction) ----
def rsi_rev(df, p):
    n = int(p.get("n", 14)); os = float(p.get("os", 30))
    r = ind.rsi(df["close"], n)
    return (r.shift(1) < os) & (r >= os), "long"


def donch_brk(df, p):
    n = int(p.get("n", 20))
    up, _, _ = ind.donchian(df, n)
    return df["close"] > up.shift(1), "long"


def ema_cross(df, p):
    f = int(p.get("f", 20)); s = int(p.get("s", 50))
    x = ind.ema_cross(df["close"], f, s)
    return (x.shift(1) <= 0) & (x > 0), "long"


def zscore_rev(df, p):
    n = int(p.get("n", 20)); zt = float(p.get("z", 2.0))
    z = ind.zscore(df["close"], n)
    return (z.shift(1) < -zt) & (z >= -zt), "long"


RULES = {"rsi_rev": rsi_rev, "donch_brk": donch_brk, "ema_cross": ema_cross, "zscore_rev": zscore_rev}


def get_symbols(aclass: str) -> list[str]:
    syms = list(CFG.get("universe", {}).get(aclass, {}).get("symbols", []))
    syms += [y["symbol"] for y in CFG.get("yfinance", []) if y.get("asset_class") == aclass]
    return syms


def load(lake: Path, aclass: str, symbol: str, tf: str) -> pd.DataFrame:
    path = Path(lake) / aclass / f"{symbol.replace('/', '')}_{tf}.csv.gz"
    return pd.read_csv(path, compression="gzip", parse_dates=["time"]).sort_values("time").reset_index(drop=True)


def run_one(df, rule_fn, params, horizon, sl, tp, c):
    entries, direction = rule_fn(df, params)
    atr = ind.atr(df, 14)
    trades = bt.simulate(df, entries.fillna(False), direction, atr, sl, tp, horizon, c["rt"], c["swap_daily"])
    if not trades.empty:
        trades["split"] = bt.tag_split(trades, bt.split_masks(df))
    return trades, direction, atr


def evaluate(lake, aclass, rule, params, horizon, tf, sl=1.5, tp=3.0, cost_mult=1.0, rc_iters=20) -> dict:
    rule_fn = RULES[rule]; c = cost_model.get(aclass, cost_mult)
    symbols = get_symbols(aclass)
    all_trades, rnd_e, rnd_w, bh = [], [], [], []
    for sym in symbols:
        try:
            df = load(lake, aclass, sym, tf)
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
              and sv["pf"] > 1 and (not np.isfinite(rnd) or sv["expR"] > rnd))
    verdict = "PASS" if passed else ("THIN" if sv["n"] < MIN_TRADES else "FAIL")
    return dict(n_syms=len(symbols), train=st, val=sv, random_expR=rnd, buyhold_pct=bhm, verdict=verdict)
