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


# ---- PHASE 5 new factor families (genuinely different from the mean-reversion/breakout already
#      tested). All no-lookahead: a signal on bar t is computed from closes through t, acted at t+1. ----
def roc_mom(df, p):
    """Momentum ignition: rate-of-change crosses up through a threshold."""
    n = int(p.get("n", 10)); thr = float(p.get("thr", 0.0))
    r = ind.roc(df["close"], n)
    return (r.shift(1) <= thr) & (r > thr), "long"


def bb_breakout(df, p):
    """Volatility breakout: close crosses above the upper Bollinger band (distinct from Donchian)."""
    n = int(p.get("n", 20)); kstd = float(p.get("kstd", 2.0))
    _, up, _ = ind.bbands(df["close"], n, kstd)
    return (df["close"].shift(1) <= up.shift(1)) & (df["close"] > up), "long"


def ema_pullback(df, p):
    """Trend continuation: in an EMA-fast>EMA-slow uptrend, buy a pullback that closes back above EMA-fast."""
    f = int(p.get("f", 10)); s = int(p.get("s", 50))
    ef, es = ind.ema(df["close"], f), ind.ema(df["close"], s)
    uptrend = ef > es
    cross_back = (df["close"].shift(1) < ef.shift(1)) & (df["close"] > ef)
    return uptrend & cross_back, "long"


def stoch_rev(df, p):
    """Stochastic oversold reversal: %K crosses up through the oversold line."""
    klen = int(p.get("klen", 14)); d = int(p.get("d", 3)); os = float(p.get("os", 20))
    kk, _ = ind.stoch(df, klen, d)
    return (kk.shift(1) < os) & (kk >= os), "long"


def macd_mom(df, p):
    """Momentum turn: MACD histogram crosses up through zero."""
    fast = int(p.get("fast", 12)); slow = int(p.get("slow", 26)); sig = int(p.get("signal", 9))
    _, _, hist = ind.macd(df["close"], fast, slow, sig)
    return (hist.shift(1) <= 0) & (hist > 0), "long"


RULES = {"rsi_rev": rsi_rev, "donch_brk": donch_brk, "ema_cross": ema_cross, "zscore_rev": zscore_rev,
         "roc_mom": roc_mom, "bb_breakout": bb_breakout, "ema_pullback": ema_pullback,
         "stoch_rev": stoch_rev, "macd_mom": macd_mom}


# ---- PHASE 4 gates: df -> bool Series (True = regime allows the entry). No-lookahead: the value
#      at bar t uses only closes through t, and the trade is still taken at t+1's open. A combined
#      hypothesis is base_rule & gate. Warmup / NaN comparisons evaluate False (entry suppressed). ----
def _adx(df, n=14):
    return ind.adx(df, n)[0]


def g_adx_lo20(df):  return _adx(df) < 20          # ranging regime -> favours mean-reversion
def g_adx_lo25(df):  return _adx(df) < 25
def g_adx_hi25(df):  return _adx(df) > 25          # trending regime -> favours breakout
def g_trend_up(df):  return df["close"] > ind.sma(df["close"], 200)   # long with the higher-TF trend


def g_vol_lo(df):
    ap = ind.atr_pct(df, 14)
    return ap < ap.rolling(100, min_periods=100).median()            # calm regime


def g_vol_hi(df):
    ap = ind.atr_pct(df, 14)
    return ap > ap.rolling(100, min_periods=100).median()            # volatile regime


def g_ny(df):
    h = pd.to_datetime(df["time"]).dt.hour
    return (h >= 12) & (h < 21)                                      # NY-session liquidity window (UTC)


GATES = {"adx_lo20": g_adx_lo20, "adx_lo25": g_adx_lo25, "adx_hi25": g_adx_hi25,
         "trend_up": g_trend_up, "vol_lo": g_vol_lo, "vol_hi": g_vol_hi, "ny": g_ny}


def get_symbols(aclass: str) -> list[str]:
    syms = list(CFG.get("universe", {}).get(aclass, {}).get("symbols", []))
    syms += [y["symbol"] for y in CFG.get("yfinance", []) if y.get("asset_class") == aclass]
    return syms


# TFs served by resampling 1h (the lake stores only 15min/1h/4h/1day). Bar-open convention: a 2h/3h
# bar is labelled at its OPEN (label='left'), so no future information leaks into bar t.
_RESAMPLE = {"2h": "2h", "3h": "3h"}


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, compression="gzip", parse_dates=["time"]).sort_values("time").reset_index(drop=True)


def load(lake: Path, aclass: str, symbol: str, tf: str) -> pd.DataFrame:
    base = f"{symbol.replace('/', '')}"
    if tf in _RESAMPLE:                                   # resample 2h/3h from 1h (portable, no-lookahead)
        df = _read(Path(lake) / aclass / f"{base}_1h.csv.gz").set_index("time")
        agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        out = (df.resample(_RESAMPLE[tf], label="left", closed="left").agg(agg)
               .dropna(subset=["open", "high", "low", "close"]).reset_index())
        return out
    return _read(Path(lake) / aclass / f"{base}_{tf}.csv.gz")


def run_one(df, rule_fn, params, horizon, sl, tp, c, gate_fn=None):
    entries, direction = rule_fn(df, params)
    entries = entries.fillna(False)
    if gate_fn is not None:                       # PHASE 4: require the regime gate at the signal bar
        g = gate_fn(df).reindex(entries.index).fillna(False).astype(bool)
        entries = entries & g
    atr = ind.atr(df, 14)
    trades = bt.simulate(df, entries, direction, atr, sl, tp, horizon, c["rt"], c["swap_daily"])
    if not trades.empty:
        trades["split"] = bt.tag_split(trades, bt.split_masks(df))
    return trades, direction, atr


def evaluate(lake, aclass, rule, params, horizon, tf, sl=1.5, tp=3.0, cost_mult=1.0, rc_iters=20,
             gate=None) -> dict:
    rule_fn = RULES[rule]; c = cost_model.get(aclass, cost_mult)
    gate_fn = GATES[gate] if gate else None
    symbols = get_symbols(aclass)
    all_trades, rnd_e, rnd_w, bh = [], [], [], []
    for sym in symbols:
        try:
            df = load(lake, aclass, sym, tf)
        except Exception:
            continue
        trades_i, direction, atr = run_one(df, rule_fn, params, horizon, sl, tp, c, gate_fn)
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
