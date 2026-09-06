"""Daily Reversal Pro System — validate the red/green 'range' coverage claim.

Reproduces the exact Pine signal logic:
  emaBull = crossover(EMA9, EMA21);  emaBear = crossunder
  bullDiv = low <= lowest(low,3)  (rsi>=lowest(rsi,3) is always true, so this
            reduces to 'current bar is a 3-bar low');  bearDiv = 3-bar high
  volSpike = volume > SMA(vol,14)*1.8   (DROPPED for no-volume assets: FX, DXY)
  atrBull = close > close[1] + ATR(20)*0.3;  atrBear = mirror
  longCondition  = emaBull and bullDiv and volSpike and atrBull
  shortCondition = emaBear and bearDiv and volSpike and atrBear
On a signal it draws RED = stop (1.5xATR) and GREEN = target (3xATR).

For every signal we measure, over the range's life (until the next signal, cap
200 bars), the 'full traverse' the user described:
  covered           = price touched BOTH the red and green levels
  green_first        = reached GREEN before RED  (tradeable win if red = stop)
  red_first_then_grn = touched RED first, then still reached GREEN (wick-out-then-recover)
  reached_green      = reached GREEN eventually, any order
  tradeable_expR     = red as a hard 1.5xATR stop, green a 3xATR target: +2R / -1R / 0
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import (          # noqa: E402
    atr_wilder, drop_incomplete_last_bar, fetch_ohlcv, resample_ohlcv,
)

TFS = ["15m", "30m", "45m", "1h", "2h", "3h", "4h", "1d"]
TF_SPEC = {"15m": ("15m", None, "60d"), "30m": ("30m", None, "60d"),
           "45m": ("15m", "45min", "60d"), "1h": ("1h", None, "730d"),
           "2h": ("1h", "2h", "730d"), "3h": ("1h", "3h", "730d"),
           "4h": ("1h", "4h", "730d"), "1d": ("1d", None, "10y")}
TF_MIN = {"15m": 15, "30m": 30, "45m": 45, "1h": 60, "2h": 120, "3h": 180, "4h": 240, "1d": 1440}
MAXWIN = 200


def rsi_w(c, n=7):
    d = c.diff(); g = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return (100-100/(1+g/l.replace(0, np.nan))).fillna(50)


def signals(df, has_vol):
    c, h, l = df["Close"], df["High"], df["Low"]
    v = df["Volume"] if "Volume" in df else pd.Series(0, index=df.index)
    fe = c.ewm(span=9, adjust=False).mean(); se = c.ewm(span=21, adjust=False).mean()
    emaBull = (fe > se) & (fe.shift() <= se.shift())
    emaBear = (fe < se) & (fe.shift() >= se.shift())
    bullDiv = l <= l.rolling(3).min()
    bearDiv = h >= h.rolling(3).max()
    volSpike = (v > v.rolling(14).mean()*1.8) if has_vol else pd.Series(True, index=df.index)
    atr = atr_wilder(df, 20)
    atrS = pd.Series(atr, index=df.index)
    atrBull = c > c.shift() + atrS*0.3
    atrBear = c < c.shift() - atrS*0.3
    longc = (emaBull & bullDiv & volSpike & atrBull).to_numpy()
    shortc = (emaBear & bearDiv & volSpike & atrBear).to_numpy()
    return longc, shortc, atr


def study(df, asset, tf, has_vol):
    close = df["Close"].to_numpy(); high = df["High"].to_numpy(); low = df["Low"].to_numpy()
    longc, shortc, atr = signals(df, has_vol)
    n = len(df)
    sig_bars = sorted([i for i in range(n) if longc[i] or shortc[i]])
    sig_set = set(sig_bars)
    rows = []
    for k, i in enumerate(sig_bars):
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        is_long = longc[i]
        entry = close[i]
        if is_long:
            red = low[i] - 1.5*atr[i]; green = close[i] + 3*atr[i]
        else:
            red = high[i] + 1.5*atr[i]; green = close[i] - 3*atr[i]
        nxt = sig_bars[k+1] if k+1 < len(sig_bars) else n-1
        end = min(nxt, i+MAXWIN, n-1)
        first_red = first_green = None
        for j in range(i+1, end+1):
            if is_long:
                hit_red = low[j] <= red; hit_green = high[j] >= green
            else:
                hit_red = high[j] >= red; hit_green = low[j] <= green
            if hit_red and first_red is None:
                first_red = j
            if hit_green and first_green is None:
                first_green = j
            if first_red is not None and first_green is not None:
                break
        reached_green = first_green is not None
        reached_red = first_red is not None
        green_first = reached_green and (first_red is None or first_green < first_red)
        red_first = reached_red and (first_green is None or first_red < first_green)
        covered = reached_green and reached_red
        r = 2.0 if green_first else (-1.0 if red_first else 0.0)
        rows.append(dict(asset=asset, tf=tf, side=("long" if is_long else "short"),
                         covered=covered, green_first=green_first,
                         reached_green=reached_green,
                         red_first_then_green=(red_first and reached_green),
                         tradeR=r))
    return rows


def main():
    cfg = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))
    assets = cfg["assets"]
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}; all_rows = []; variant = {}
    for asset, spec in assets.items():
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        for tf in TFS:
            src, rule, per = TF_SPEC[tf]
            ck = (tk, src, per)
            if ck not in cache:
                cache[ck] = fetch_ohlcv(tk, src, per)
            base = cache[ck]
            if base is None or base.empty:
                continue
            has_vol = ("Volume" in base) and float(np.nansum(base["Volume"].to_numpy())) > 0
            variant[asset] = "native" if has_vol else "no-vol(FX/idx)"
            frame = base if (tf == "1d" or not rule) else resample_ohlcv(base, rule, anchor)
            frame = drop_incomplete_last_bar(frame, TF_MIN[tf], now)
            if len(frame) < 60:
                continue
            all_rows.extend(study(frame, asset, tf, has_vol))
        print(f"{asset:<8} done ({variant.get(asset,'?')})", flush=True)

    d = pd.DataFrame(all_rows)
    d.to_csv(ROOT/"logs"/"drs_signals.csv", index=False)
    print(f"\nTotal signals across all assets x TFs: {len(d)}")

    # aggregate per asset x tf
    grid = []
    for asset in assets:
        for tf in TFS:
            sub = d[(d.asset == asset) & (d.tf == tf)]
            if sub.empty:
                continue
            n = len(sub)
            grid.append(dict(asset=asset, tf=tf, variant=variant.get(asset, "?"), n=n,
                             covered_pct=round(100*sub.covered.mean(), 1),
                             green_first_pct=round(100*sub.green_first.mean(), 1),
                             reached_green_pct=round(100*sub.reached_green.mean(), 1),
                             red_then_green_pct=round(100*sub.red_first_then_green.mean(), 1),
                             tradeable_expR=round(sub.tradeR.mean(), 3)))
    g = pd.DataFrame(grid)
    g.to_csv(ROOT/"logs"/"drs_grid.csv", index=False)

    print("\nSignals per asset (summed over all TFs):")
    print(d.groupby("asset").size().reindex(list(assets)).fillna(0).astype(int).to_string())
    print("\nCells with n>=10 (enough to say anything):")
    big = g[g.n >= 10].sort_values("covered_pct", ascending=False)
    print(big.to_string(index=False) if not big.empty else "  NONE — every asset/TF cell has < 10 signals.")
    print("\nPooled over ALL signals:")
    print(f"  n={len(d)}  covered={100*d.covered.mean():.1f}%  "
          f"green_first={100*d.green_first.mean():.1f}%  "
          f"reached_green_eventually={100*d.reached_green.mean():.1f}%  "
          f"tradeable_expR={d.tradeR.mean():+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
