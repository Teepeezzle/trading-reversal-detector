"""Does divergence become tradeable when filtered by LEVEL proximity and the
MACRO-trend gate? Decomposes the edge across four variants:

  A: divergence only                         (baseline — already no edge)
  B: divergence + macro gate                 (don't short an uptrend)
  C: divergence + level proximity            (only at a real prior W/M/Y level)
  D: divergence + macro + level              (the full confluence)

Decisive metric for a SHORT is the MEAN forward return: it must be NEGATIVE
(price actually falls on average), not merely a >50% down-rate. Plain
divergence failed precisely because its mean forward return was POSITIVE.

Non-repainting: forward returns measured from the pivot CONFIRMATION bar; all
levels/macro evaluated from data available at that bar.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "backtest" / "results"

ASSETS = {"BTC-USD": "Bitcoin", "GC=F": "Gold", "CL=F": "WTI Oil"}
HORIZONS = [5, 10, 20]
PIVOT_LEN = 5
LEVEL_TOL_PCT = 1.0     # "testing" a level = within 1.0% of it
MACRO_SMA = 200
MACRO_SLOPE_LB = 20


def fetch(ticker: str) -> Optional[pd.DataFrame]:
    try:
        raw = yf.download(ticker, period="10y", interval="1d",
                          progress=False, auto_adjust=False, threads=False)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {ticker}: {exc}")
        return None
    if raw is None or raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return raw[["Open", "High", "Low", "Close", "Volume"]].dropna(
        subset=["Open", "High", "Low", "Close"])


def macd_line(close: pd.Series) -> pd.Series:
    return close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()


def prior_period_levels(df: pd.DataFrame) -> pd.DataFrame:
    """Attach prior-week/month/year highs & lows to each daily bar."""
    out = pd.DataFrame(index=df.index)
    for code, tag in [("W", "w"), ("M", "m"), ("Y", "y")]:
        per = df.index.to_period(code)
        grp = df.groupby(per).agg(H=("High", "max"), L=("Low", "min"))
        ph = grp["H"].shift(1)
        pl = grp["L"].shift(1)
        out[f"p{tag}h"] = per.map(ph).astype(float)
        out[f"p{tag}l"] = per.map(pl).astype(float)
    return out


def macro_series(close: pd.Series) -> pd.DataFrame:
    sma = close.rolling(MACRO_SMA).mean()
    slope = (sma - sma.shift(MACRO_SLOPE_LB)) / sma
    up = (close > sma) & (slope > 0.002)
    down = (close < sma) & (slope < -0.002)
    return pd.DataFrame({"up": up.fillna(False), "down": down.fillna(False)})


def find_pivots(values: np.ndarray, macd: np.ndarray, length: int, kind: str):
    out = []
    n = len(values)
    for i in range(length, n - length):
        win = values[i - length:i + length + 1]
        if kind == "high" and values[i] == win.max() and values[i] > values[i - 1]:
            out.append((i, i + length, float(values[i]), float(macd[i])))
        elif kind == "low" and values[i] == win.min() and values[i] < values[i - 1]:
            out.append((i, i + length, float(values[i]), float(macd[i])))
    return out


def near_level(price: float, levels: List[float], tol_pct: float) -> bool:
    tol = tol_pct / 100.0 * price
    return any(np.isfinite(lv) and abs(price - lv) <= tol for lv in levels)


def base_rate(close: np.ndarray, h: int, direction: str) -> float:
    n = len(close)
    hits = total = 0
    for t in range(n - h):
        total += 1
        fwd = close[t + h] - close[t]
        if (direction == "down" and fwd < 0) or (direction == "up" and fwd > 0):
            hits += 1
    return hits / total if total else float("nan")


def z_test(p_hat: float, p0: float, n: int) -> float:
    if n == 0 or p0 <= 0 or p0 >= 1:
        return float("nan")
    return (p_hat - p0) / np.sqrt(p0 * (1 - p0) / n)


def evaluate(close, pivots, levels_df, macro_df, direction, use_macro, use_level):
    """Return {H: {'rets': [...], 'down_or_up': [...]}} for the chosen variant."""
    n = len(close)
    res = {h: {"rets": [], "hits": 0, "n": 0} for h in HORIZONS}
    lvl_cols_res = ["pwh", "pmh", "pyh"]
    lvl_cols_sup = ["pwl", "pml", "pyl"]
    for k in range(1, len(pivots)):
        (pi0, _, price0, macd0) = pivots[k - 1]
        (pi, conf, price, macd) = pivots[k]
        if direction == "down":
            if not (price > price0 and macd < macd0):
                continue
            if use_level:
                levels = [levels_df.iloc[pi][c] for c in lvl_cols_res]
                if not near_level(price, levels, LEVEL_TOL_PCT):
                    continue
        else:
            if not (price < price0 and macd > macd0):
                continue
            if use_level:
                levels = [levels_df.iloc[pi][c] for c in lvl_cols_sup]
                if not near_level(price, levels, LEVEL_TOL_PCT):
                    continue
        if conf >= n:
            continue
        if use_macro:
            if direction == "down" and bool(macro_df.iloc[conf]["up"]):
                continue   # don't short an uptrend
            if direction == "up" and bool(macro_df.iloc[conf]["down"]):
                continue   # don't long a downtrend
        c0 = close[conf]
        for h in HORIZONS:
            if conf + h >= n:
                continue
            fwd = close[conf + h] - c0
            res[h]["rets"].append(fwd / c0 * 100.0)
            res[h]["n"] += 1
            if (direction == "down" and fwd < 0) or (direction == "up" and fwd > 0):
                res[h]["hits"] += 1
    return res


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    variants = [("A div-only", False, False), ("B div+macro", True, False),
                ("C div+level", False, True), ("D div+macro+level", True, True)]
    pooled = {v[0]: {h: {"rets": [], "hits": 0, "n": 0} for h in HORIZONS} for v in variants}
    pooled_base = {h: [] for h in HORIZONS}
    rows = []

    for ticker, name in ASSETS.items():
        df = fetch(ticker)
        if df is None or len(df) < 400:
            print(f"[{name}] insufficient data")
            continue
        close = df["Close"].to_numpy()
        macd = macd_line(df["Close"]).to_numpy()
        levels_df = prior_period_levels(df)
        macro_df = macro_series(df["Close"])
        ph = find_pivots(df["High"].to_numpy(), macd, PIVOT_LEN, "high")

        bases = {h: 100 * base_rate(close, h, "down") for h in HORIZONS}
        for h in HORIZONS:
            for t in range(len(close) - h):
                pooled_base[h].append((close[t + h] - close[t]) / close[t] * 100.0)

        print(f"\n################ {name} ({ticker}) — SHORT side "
              f"(higher-high + MACD bear div) ################")
        print(f"   base down-rate  H5={bases[5]:.1f}%  H10={bases[10]:.1f}%  H20={bases[20]:.1f}%")
        for vlabel, um, ul in variants:
            res = evaluate(close, ph, levels_df, macro_df, "down", um, ul)
            line = f"   {vlabel:<18}"
            for h in HORIZONS:
                c = res[h]
                # accumulate pooled
                pooled[vlabel][h]["rets"] += c["rets"]
                pooled[vlabel][h]["hits"] += c["hits"]
                pooled[vlabel][h]["n"] += c["n"]
                if c["n"] == 0:
                    line += f"  H{h}: n=0"
                    continue
                hit = 100 * c["hits"] / c["n"]
                mean = float(np.mean(c["rets"]))
                line += f"  H{h}: n={c['n']:>3} down={hit:4.0f}% mean={mean:+5.1f}%"
                rows.append({"asset": name, "variant": vlabel, "H": h, "n": c["n"],
                             "down_pct": round(hit, 1), "mean_fwd_pct": round(mean, 2),
                             "base_pct": round(bases[h], 1)})
            print(line)

    # Pooled summary — the decisive view (mean must be negative for a short)
    print("\n\n================ POOLED (all 3 assets) — SHORT side ================")
    print("decisive metric = mean forward return (NEGATIVE = shorting makes money)\n")
    for h in HORIZONS:
        pbase_down = 100 * np.mean(np.array(pooled_base[h]) < 0)
        pbase_mean = float(np.mean(pooled_base[h]))
        print(f"-- Horizon {h} bars --  (base: down={pbase_down:.1f}%, mean={pbase_mean:+.2f}%)")
        for vlabel, _, _ in variants:
            c = pooled[vlabel][h]
            if c["n"] == 0:
                print(f"   {vlabel:<18} n=0")
                continue
            hit = 100 * c["hits"] / c["n"]
            mean = float(np.mean(c["rets"]))
            z = z_test(c["hits"] / c["n"], pbase_down / 100, c["n"])
            verdict = "TRADEABLE EDGE" if (mean < -1.0 and hit > pbase_down + 5 and c["n"] >= 20) else ""
            print(f"   {vlabel:<18} n={c['n']:>3}  down={hit:4.0f}%  "
                  f"mean={mean:+5.2f}%  z(down)={z:+.2f}  {verdict}")
        print("")

    if rows:
        pd.DataFrame(rows).to_csv(OUT / "divergence_confluence.csv", index=False)
        print(f"Saved {OUT / 'divergence_confluence.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
