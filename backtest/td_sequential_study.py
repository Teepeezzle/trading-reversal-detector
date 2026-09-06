"""Enhanced TD Sequential — extensive setup-9 study across assets x timeframes.

Signal (from the user's Pine indicator):
  BUY SETUP  = 9 consecutive bars with close < close[4]  -> mean-reversion LONG
  SELL SETUP = 9 consecutive bars with close > close[4]  -> mean-reversion SHORT
  (the script's countdown logic is broken, so it is excluded.)

For every completed setup-9 we test, per asset x timeframe:
  Filters (each tested as its own subset, vs the raw baseline):
    raw    - every setup-9
    trend  - aligned with the chart-native 200-SMA
             (LONG only if close > SMA200 = buy the dip in an uptrend;
              SHORT only if close < SMA200 = sell the rally in a downtrend)
    vol    - the setup bar had a volume spike (vol > 1.5 x SMA(vol,14));
             N/A for Yahoo FX (=X) feeds, which carry no real volume
    rsi    - non-extreme directional RSI: LONG if RSI<50, SHORT if RSI>50
  Exit models (both, compared):
    ATR    - enter at setup-9 close, SL 1.5xATR, TP 4.0xATR (1:2.67);
             win = +2.667R, loss = -1R, unresolved = mark-to-market in R
    HOLD   - hold until the opposite setup-9 fires, exit at that close;
             R = favourable move / (1.5 x ATR at entry)

Timeframes: 15m 30m 45m 1h 2h 3h 4h 1d.
Data: yfinance, same proxies + ny17/utc session anchoring as the scanner.
      15m/30m/45m capped at ~60d history; 1h-derived to ~730d; 1d to ~10y
      (calendar-day bars, NOT ny-close — flagged as a caveat).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.v5_divergence import (          # noqa: E402
    atr_wilder, drop_incomplete_last_bar, fetch_ohlcv, resample_ohlcv,
)

SL_ATR, TP_ATR = 1.5, 4.0
R_WIN = TP_ATR / SL_ATR              # +2.667R on a target
R_LOSS = -1.0
LOOKBACK = 4                        # TD price-flip lookback
SETUP_TARGET = 9
RSI_LEN, SMA_LEN, VOL_LEN, ATR_LEN = 14, 200, 14, 14
VOL_MULT = 1.5
MIN_BARS = SMA_LEN + 30
MIN_N = 8                           # min signals for a cell to be "trusted"

TFS = ["15m", "30m", "45m", "1h", "2h", "3h", "4h", "1d"]
# (source_interval, resample_rule, fetch_period)
TF_SPEC = {
    "15m": ("15m", None,  "60d"),
    "30m": ("30m", None,  "60d"),
    "45m": ("15m", "45min", "60d"),
    "1h":  ("1h",  None,  "730d"),
    "2h":  ("1h",  "2h",  "730d"),
    "3h":  ("1h",  "3h",  "730d"),
    "4h":  ("1h",  "4h",  "730d"),
    "1d":  ("1d",  None,  "10y"),
}
TF_MIN = {"15m": 15, "30m": 30, "45m": 45, "1h": 60, "2h": 120,
          "3h": 180, "4h": 240, "1d": 1440}


def rsi_wilder(close: pd.Series, n: int = 14) -> np.ndarray:
    d = close.diff()
    g = d.clip(lower=0).ewm(alpha=1.0/n, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1.0/n, adjust=False).mean()
    rs = g / l.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50).to_numpy()


def td_setups(close: np.ndarray):
    """Return (buy_bars, sell_bars): indices where setup reached 9."""
    n = len(close)
    buy = np.zeros(n, dtype=int)
    sell = np.zeros(n, dtype=int)
    bc = sc = 0
    buy_bars, sell_bars = [], []
    for i in range(n):
        if i >= LOOKBACK and close[i] < close[i-LOOKBACK]:
            bc += 1
        else:
            bc = 0
        if i >= LOOKBACK and close[i] > close[i-LOOKBACK]:
            sc += 1
        else:
            sc = 0
        buy[i], sell[i] = bc, sc
        if bc == SETUP_TARGET:
            buy_bars.append(i)
        if sc == SETUP_TARGET:
            sell_bars.append(i)
    return buy_bars, sell_bars


def score_atr(high, low, close, i, direction, entry, atr_val):
    n = len(close)
    if direction == "long":
        sl, tp = entry - SL_ATR*atr_val, entry + TP_ATR*atr_val
    else:
        sl, tp = entry + SL_ATR*atr_val, entry - TP_ATR*atr_val
    for j in range(i+1, n):
        if direction == "long":
            hit_sl, hit_tp = low[j] <= sl, high[j] >= tp
        else:
            hit_sl, hit_tp = high[j] >= sl, low[j] <= tp
        if hit_sl:
            return R_LOSS, "SL"
        if hit_tp:
            return R_WIN, "TP"
    mv = (close[-1]-entry) if direction == "long" else (entry-close[-1])
    return mv/(SL_ATR*atr_val), "OPEN"


def score_hold(close, i, direction, entry, atr_val, opp_bars):
    j = next((b for b in opp_bars if b > i), None)
    exit_px = close[j] if j is not None else close[-1]
    mv = (exit_px-entry) if direction == "long" else (entry-exit_px)
    return mv/(SL_ATR*atr_val), (mv/entry*100.0)


def analyse(df: pd.DataFrame, asset: str, tf: str):
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    vol = df["Volume"].to_numpy() if "Volume" in df else np.zeros(len(df))
    has_vol = np.nansum(vol) > 0
    atr = atr_wilder(df, ATR_LEN)
    rsi = rsi_wilder(df["Close"], RSI_LEN)
    sma = df["Close"].rolling(SMA_LEN).mean().to_numpy()
    vavg = pd.Series(vol).rolling(VOL_LEN).mean().to_numpy()
    buy_bars, sell_bars = td_setups(close)

    rows = []
    for bars, direction, opp in ((buy_bars, "long", sell_bars),
                                 (sell_bars, "short", buy_bars)):
        for i in bars:
            if i < MIN_BARS or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            entry = close[i]
            trend_ok = (np.isfinite(sma[i]) and
                        ((direction == "long" and entry > sma[i]) or
                         (direction == "short" and entry < sma[i])))
            vol_ok = has_vol and np.isfinite(vavg[i]) and vol[i] > VOL_MULT*vavg[i]
            rsi_ok = (rsi[i] < 50) if direction == "long" else (rsi[i] > 50)
            r_atr, res = score_atr(high, low, close, i, direction, entry, atr[i])
            r_hold, pct_hold = score_hold(close, i, direction, entry, atr[i], opp)
            rows.append(dict(asset=asset, tf=tf, direction=direction,
                             trend_ok=trend_ok, vol_ok=vol_ok, rsi_ok=rsi_ok,
                             has_vol=has_vol, r_atr=r_atr, res=res,
                             r_hold=r_hold, pct_hold=pct_hold))
    return rows


def agg(sub: pd.DataFrame, rcol: str) -> dict:
    n = len(sub)
    if n == 0:
        return None
    r = sub[rcol].to_numpy()
    wins = (r > 0).sum()
    pos = r[r > 0].sum(); neg = -r[r < 0].sum()
    pf = (pos/neg) if neg > 0 else float("inf")
    return dict(n=n, win_pct=round(100*wins/n, 1),
                exp_R=round(float(r.mean()), 3), total_R=round(float(r.sum()), 1),
                pf=(round(pf, 2) if pf != float("inf") else "inf"))


def main():
    cfg = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))
    assets = cfg["assets"]
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    fetch_cache = {}
    all_rows = []

    for asset, spec in assets.items():
        ticker = spec["ticker"]; anchor = spec.get("anchor", "utc")
        print(f"== {asset} ({ticker}, {anchor}) ==", flush=True)
        for tf in TFS:
            source, rule, period = TF_SPEC[tf]
            ck = (ticker, source, period)
            if ck not in fetch_cache:
                fetch_cache[ck] = fetch_ohlcv(ticker, source, period)
                time.sleep(0.3)
            base = fetch_cache[ck]
            if base is None or base.empty:
                print(f"   {tf:<4} no data"); continue
            if tf == "1d":
                frame = base                      # calendar-day bars
            elif rule:
                frame = resample_ohlcv(base, rule, anchor)
            else:
                frame = base
            frame = drop_incomplete_last_bar(frame, TF_MIN[tf], now)
            if len(frame) < MIN_BARS:
                print(f"   {tf:<4} only {len(frame)} bars"); continue
            rows = analyse(frame, asset, tf)
            all_rows.extend(rows)
            print(f"   {tf:<4} bars={len(frame):<6} signals={len(rows)}", flush=True)

    d = pd.DataFrame(all_rows)
    d.to_parquet(ROOT/"logs"/"td_signals_raw.parquet") if False else None
    d.to_csv(ROOT/"logs"/"td_signals_raw.csv", index=False)
    print(f"\nTotal signals: {len(d)}")

    # Build the filter x exit grid
    filters = {
        "raw":   lambda x: x,
        "trend": lambda x: x[x.trend_ok],
        "vol":   lambda x: x[x.vol_ok],
        "rsi":   lambda x: x[x.rsi_ok],
    }
    grid = []
    for asset in assets:
        for tf in TFS:
            cell = d[(d.asset == asset) & (d.tf == tf)]
            if cell.empty:
                continue
            for fname, ffn in filters.items():
                sub = ffn(cell)
                a_atr = agg(sub, "r_atr")
                a_hold = agg(sub, "r_hold")
                if a_atr is None:
                    continue
                grid.append(dict(
                    asset=asset, tf=tf, filter=fname,
                    n=a_atr["n"],
                    atr_win=a_atr["win_pct"], atr_expR=a_atr["exp_R"],
                    atr_totR=a_atr["total_R"], atr_pf=a_atr["pf"],
                    hold_win=a_hold["win_pct"], hold_expR=a_hold["exp_R"],
                    hold_totR=a_hold["total_R"], hold_pf=a_hold["pf"]))
    g = pd.DataFrame(grid)
    g.to_csv(ROOT/"logs"/"td_grid.csv", index=False)

    # Best (tf, filter) per asset by ATR expectancy, min sample
    best = []
    for asset in assets:
        sub = g[(g.asset == asset) & (g.n >= MIN_N)]
        if sub.empty:
            sub = g[g.asset == asset]
        if sub.empty:
            continue
        top = sub.sort_values("atr_expR", ascending=False).iloc[0]
        best.append(dict(asset=asset, best_tf=top.tf, best_filter=top["filter"],
                         n=int(top.n), atr_win=top.atr_win, atr_expR=top.atr_expR,
                         atr_totR=top.atr_totR, atr_pf=top.atr_pf,
                         hold_expR=top.hold_expR, hold_win=top.hold_win,
                         trusted=("yes" if top.n >= MIN_N else "LOW-N")))
    b = pd.DataFrame(best)
    b.to_csv(ROOT/"logs"/"td_best.csv", index=False)

    print("\n=== BEST (tf, filter) per asset — by ATR expectancy (min n=%d) ===" % MIN_N)
    print(b.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
