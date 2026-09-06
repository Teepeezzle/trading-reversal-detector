"""4-way confluence: aligned V5 AND TD (same dir) + DRS zone + 200-SMA trend.

Stricter than combo_study.py: an entry requires BOTH a V5 aligned divergence
AND a TD setup-9 of the same direction to fire on the same asset within
WINDOW_DAYS of each other (any timeframe), while price is in the DRS zone
(at/below red for buys, at/above red for sells) and the 200-SMA agrees.

Anchored on the V5 signal (entry at the V5 bar, requiring a TD signal nearby),
since V5 was the cleaner trigger. Exit: SL 1.5xATR / TP 4.0xATR (+2.667R/-1R).
"""
from __future__ import annotations
import sys, bisect
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import (          # noqa: E402
    atr_wilder, detect_divergences, drop_incomplete_last_bar, fetch_ohlcv, resample_ohlcv,
)
from backtest.drs_range_study import signals as drs_signals   # noqa: E402
from backtest.td_sequential_study import td_setups            # noqa: E402

TFS = ["15m", "30m", "45m", "1h", "2h", "3h", "4h", "1d"]
TF_SPEC = {"15m": ("15m", None, "60d"), "30m": ("30m", None, "60d"),
           "45m": ("15m", "45min", "60d"), "1h": ("1h", None, "730d"),
           "2h": ("1h", "2h", "730d"), "3h": ("1h", "3h", "730d"),
           "4h": ("1h", "4h", "730d"), "1d": ("1d", None, "10y")}
TF_MIN = {"15m": 15, "30m": 30, "45m": 45, "1h": 60, "2h": 120, "3h": 180, "4h": 240, "1d": 1440}
SL_ATR, TP_ATR = 1.5, 4.0
R_WIN, R_LOSS = TP_ATR/SL_ATR, -1.0
ZONE_MAX_DAYS, BUF_ATR = 30, 0.5
WINDOW = pd.Timedelta(days=3)


def score(high, low, close, i, direction, entry, atrv):
    n = len(close)
    if direction == "long":
        sl, tp = entry-SL_ATR*atrv, entry+TP_ATR*atrv
    else:
        sl, tp = entry+SL_ATR*atrv, entry-TP_ATR*atrv
    for j in range(i+1, n):
        if direction == "long":
            if low[j] <= sl:
                return R_LOSS
            if high[j] >= tp:
                return R_WIN
        else:
            if high[j] >= sl:
                return R_LOSS
            if low[j] <= tp:
                return R_WIN
    mv = (close[-1]-entry) if direction == "long" else (entry-close[-1])
    return mv/(SL_ATR*atrv)


def near(times, t):
    if not times:
        return False
    k = bisect.bisect_left(times, t)
    for cand in (k-1, k):
        if 0 <= cand < len(times) and abs(times[cand]-t) <= WINDOW:
            return True
    return False


def main():
    cfg = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))
    assets = cfg["assets"]
    dcfg = dict(yaml.safe_load((ROOT/"config"/"v5_winners_scanner.yaml").read_text("utf-8"))["divergence"])
    dcfg["aligned_only"] = True
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}; rows = []

    for asset, spec in assets.items():
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        frames = {}; drs_long = []; drs_short = []
        v5 = []                         # (time, tf, dir, entry, atr, sma, i)
        td_long_t = {}; td_short_t = []  # per-TF not needed; pool times
        td_long_times = []; td_short_times = []
        for tf in TFS:
            src, rule, per = TF_SPEC[tf]
            ck = (tk, src, per)
            if ck not in cache:
                cache[ck] = fetch_ohlcv(tk, src, per)
            base = cache[ck]
            if base is None or base.empty:
                continue
            has_vol = ("Volume" in base) and float(np.nansum(base["Volume"].to_numpy())) > 0
            frame = base if (tf == "1d" or not rule) else resample_ohlcv(base, rule, anchor)
            frame = drop_incomplete_last_bar(frame, TF_MIN[tf], now)
            if len(frame) < 220:
                continue
            frames[tf] = frame
            close = frame["Close"].to_numpy(); high = frame["High"].to_numpy(); low = frame["Low"].to_numpy()
            idx = frame.index
            atr14 = atr_wilder(frame, 14)
            sma = frame["Close"].rolling(200).mean().to_numpy()
            lc, sc, datr = drs_signals(frame, has_vol)
            for i in range(len(frame)):
                if np.isfinite(datr[i]) and datr[i] > 0:
                    if lc[i]:
                        drs_long.append((idx[i], low[i]-1.5*datr[i]))
                    if sc[i]:
                        drs_short.append((idx[i], high[i]+1.5*datr[i]))
            tb, ts = td_setups(close)
            for i in tb:
                if i > 210:
                    td_long_times.append(idx[i])
            for i in ts:
                if i > 210:
                    td_short_times.append(idx[i])
            sigs = detect_divergences(frame, asset, tk, tf, TF_MIN[tf], dcfg)
            pos = {t: k for k, t in enumerate(idx)}
            for s in sigs:
                ci = pos.get(s.confirm_time)
                if ci is None or ci <= 210 or not np.isfinite(atr14[ci]) or atr14[ci] <= 0:
                    continue
                d = "long" if s.direction == "BULL" else "short"
                v5.append((idx[ci], tf, d, close[ci], atr14[ci], sma[ci], ci))

        drs_long.sort(); drs_short.sort()
        dl_t = [t for t, _ in drs_long]; dl_r = [r for _, r in drs_long]
        ds_t = [t for t, _ in drs_short]; ds_r = [r for _, r in drs_short]
        td_long_times.sort(); td_short_times.sort()

        def active(zt, zr, ttime, entry, direction, atrv):
            k = bisect.bisect_right(zt, ttime) - 1
            while k >= 0:
                if (ttime - zt[k]) > pd.Timedelta(days=ZONE_MAX_DAYS):
                    return False
                red = zr[k]
                if direction == "long" and entry <= red + BUF_ATR*atrv:
                    return True
                if direction == "short" and entry >= red - BUF_ATR*atrv:
                    return True
                k -= 1
            return False

        for (ttime, tf, direction, entry, atrv, sma_i, i) in v5:
            frame = frames[tf]
            high = frame["High"].to_numpy(); low = frame["Low"].to_numpy(); close = frame["Close"].to_numpy()
            trend_ok = np.isfinite(sma_i) and ((direction == "long" and entry > sma_i) or
                                               (direction == "short" and entry < sma_i))
            zt, zr = (dl_t, dl_r) if direction == "long" else (ds_t, ds_r)
            zone_ok = active(zt, zr, ttime, entry, direction, atrv)
            td_ok = near(td_long_times if direction == "long" else td_short_times, ttime)
            r = score(high, low, close, i, direction, entry, atrv)
            rows.append(dict(asset=asset, tf=tf, dir=direction, trend_ok=trend_ok,
                             zone_ok=zone_ok, td_ok=td_ok, R=r))
        print(f"{asset:<8} v5={len(v5)}", flush=True)

    d = pd.DataFrame(rows)
    d.to_csv(ROOT/"logs"/"combo2_signals.csv", index=False)
    full = d[d.trend_ok & d.zone_ok & d.td_ok]

    def st(s):
        if len(s) == 0:
            return dict(n=0)
        r = s.R.to_numpy()
        return dict(n=len(s), win=round(100*(r > 0).mean(), 1),
                    expR=round(float(r.mean()), 3), totR=round(float(r.sum()), 1))

    print("\n=== 4-WAY: V5 + TD + DRS zone + 200SMA (pooled) ===")
    print("  BUY :", st(full[full.dir == "long"]))
    print("  SELL:", st(full[full.dir == "short"]))
    for lbl, dr in (("BUY", "long"), ("SELL", "short")):
        print(f"\n=== {lbl} by asset (n>=4) ===")
        rr = []
        for a in assets:
            s = full[(full.asset == a) & (full.dir == dr)]
            if len(s) >= 4:
                rr.append(dict(asset=a, **st(s)))
        print(pd.DataFrame(rr).sort_values("expR", ascending=False).to_string(index=False) if rr else "  none n>=4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
