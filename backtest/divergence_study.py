"""Forensic test of the 'higher-high + MACD bearish divergence -> price falls'
observation (and its bullish mirror) on BTC, Gold, Oil.

Method (deliberately conservative / non-repainting):
  * Pivot highs/lows via a symmetric length L. A pivot at bar i is only KNOWN
    at bar i+L (confirmation). All forward returns are measured from the
    CONFIRMATION bar's close, never from the pivot bar — so there is no
    look-ahead and no repaint.
  * Bearish signal: the latest confirmed pivot high is a HIGHER high than the
    previous pivot high, while the MACD line at the pivot is LOWER than at the
    previous pivot high (classic bearish divergence). Optional 'exhaustion'
    filter requires >=2 consecutive higher pivot highs into the signal
    (the user's '2-4 repeated highs exceeding previous').
  * Bullish signal: mirror (lower low + higher MACD).
  * For each signal we record forward returns at H in {5,10,20} bars and ask:
      - directional hit rate (bearish: P(price lower after H bars))
      - mean forward return
    compared against the UNCONDITIONAL base rate over the same horizon.
  * Significance via a one-proportion z-test vs the base rate.

'Edge' = signal hit rate materially above the base rate with enough samples.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "backtest" / "results"

ASSETS = {"BTC-USD": "Bitcoin", "GC=F": "Gold", "CL=F": "WTI Oil"}
HORIZONS = [5, 10, 20]
PIVOT_LEN = 5
MACD_FAST, MACD_SLOW, MACD_SIG = 12, 26, 9


def fetch(ticker: str, period: str = "10y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fetch OHLCV; flatten columns; drop incomplete rows."""
    try:
        raw = yf.download(ticker, period=period, interval=interval,
                          progress=False, auto_adjust=False, threads=False)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {ticker}: {exc}")
        return None
    if raw is None or raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna(
        subset=["Open", "High", "Low", "Close"])
    return df


def macd_line(close: pd.Series) -> pd.Series:
    """Standard MACD line (12 EMA - 26 EMA)."""
    return close.ewm(span=MACD_FAST, adjust=False).mean() - close.ewm(span=MACD_SLOW, adjust=False).mean()


@dataclass
class Pivot:
    idx: int          # bar index of the pivot extreme
    conf_idx: int     # bar index at which it is confirmed (idx + L)
    price: float
    macd: float


def find_pivots(values: np.ndarray, macd: np.ndarray, length: int, kind: str) -> List[Pivot]:
    """Return confirmed pivots. kind='high' or 'low'."""
    out: List[Pivot] = []
    n = len(values)
    for i in range(length, n - length):
        win = values[i - length:i + length + 1]
        if kind == "high" and values[i] == win.max() and values[i] > values[i - 1]:
            out.append(Pivot(i, i + length, float(values[i]), float(macd[i])))
        elif kind == "low" and values[i] == win.min() and values[i] < values[i - 1]:
            out.append(Pivot(i, i + length, float(values[i]), float(macd[i])))
    return out


def base_rate(close: np.ndarray, horizon: int, direction: str) -> float:
    """Unconditional P(move in `direction`) over `horizon` bars, all bars."""
    n = len(close)
    hits = 0
    total = 0
    for t in range(n - horizon):
        total += 1
        fwd = close[t + horizon] - close[t]
        if direction == "down" and fwd < 0:
            hits += 1
        elif direction == "up" and fwd > 0:
            hits += 1
    return hits / total if total else float("nan")


def z_test(p_hat: float, p0: float, n: int) -> float:
    """One-proportion z vs base rate p0."""
    if n == 0 or p0 <= 0 or p0 >= 1:
        return float("nan")
    return (p_hat - p0) / np.sqrt(p0 * (1 - p0) / n)


def study_side(close: np.ndarray, pivots: List[Pivot], direction: str,
               exhaustion: bool) -> dict:
    """Evaluate bearish (direction='down') or bullish (direction='up') signals."""
    n = len(close)
    results = {h: {"hits": 0, "n": 0, "rets": []} for h in HORIZONS}

    for k in range(1, len(pivots)):
        prev, curr = pivots[k - 1], pivots[k]
        if direction == "down":          # bearish: higher high + lower MACD
            structural = curr.price > prev.price
            divergence = curr.macd < prev.macd
        else:                            # bullish: lower low + higher MACD
            structural = curr.price < prev.price
            divergence = curr.macd > prev.macd
        if not (structural and divergence):
            continue
        if exhaustion and k >= 2:
            p2 = pivots[k - 2]
            if direction == "down" and not (prev.price > p2.price):
                continue
            if direction == "up" and not (prev.price < p2.price):
                continue
        elif exhaustion and k < 2:
            continue

        c0_idx = curr.conf_idx           # measure from CONFIRMATION, no lookahead
        if c0_idx >= n:
            continue
        c0 = close[c0_idx]
        for h in HORIZONS:
            if c0_idx + h >= n:
                continue
            fwd = close[c0_idx + h] - c0
            results[h]["n"] += 1
            results[h]["rets"].append(fwd / c0 * 100.0)
            if direction == "down" and fwd < 0:
                results[h]["hits"] += 1
            elif direction == "up" and fwd > 0:
                results[h]["hits"] += 1
    return results


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for ticker, name in ASSETS.items():
        df = fetch(ticker)
        if df is None or len(df) < 300:
            print(f"[{name}] insufficient data")
            continue
        close = df["Close"].to_numpy()
        highs = df["High"].to_numpy()
        lows = df["Low"].to_numpy()
        macd = macd_line(df["Close"]).to_numpy()

        ph = find_pivots(highs, macd, PIVOT_LEN, "high")
        pl = find_pivots(lows, macd, PIVOT_LEN, "low")

        print(f"\n################ {name} ({ticker}) — {len(df)} daily bars, "
              f"{len(ph)} pivot highs, {len(pl)} pivot lows ################")

        for label, pivots, direction in [
            ("BEARISH (higher-high + MACD lower-high)", ph, "down"),
            ("BULLISH (lower-low + MACD higher-low)", pl, "up"),
        ]:
            for exh in (False, True):
                tag = label + ("  [+exhaustion >=2]" if exh else "")
                res = study_side(close, pivots, direction, exh)
                print(f"\n  {tag}")
                for h in HORIZONS:
                    cell = res[h]
                    nn = cell["n"]
                    if nn == 0:
                        print(f"    H={h:>2}:  no signals")
                        continue
                    hit = 100 * cell["hits"] / nn
                    base = 100 * base_rate(close, h, direction)
                    mean_ret = float(np.mean(cell["rets"]))
                    z = z_test(cell["hits"] / nn, base / 100, nn)
                    edge = hit - base
                    flag = "EDGE" if (z is not None and z > 1.64 and edge > 3) else ""
                    print(f"    H={h:>2}:  n={nn:>4}  hit={hit:5.1f}%  "
                          f"base={base:5.1f}%  edge={edge:+5.1f}pp  "
                          f"meanFwd={mean_ret:+5.2f}%  z={z:+.2f}  {flag}")
                    rows.append({"asset": name, "signal": tag, "H": h, "n": nn,
                                 "hit_%": round(hit, 1), "base_%": round(base, 1),
                                 "edge_pp": round(edge, 1), "mean_fwd_%": round(mean_ret, 2),
                                 "z": round(z, 2)})
    if rows:
        pd.DataFrame(rows).to_csv(OUT / "divergence_study.csv", index=False)
        print(f"\nSaved {OUT / 'divergence_study.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
