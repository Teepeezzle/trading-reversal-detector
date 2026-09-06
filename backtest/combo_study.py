"""Three-way confluence backtest:

  DRS zone (any TF)  +  200-SMA trend  +  TD/V5 buy 'at or below red' (any TF)

Faithful to the user's logic:
  * A Daily Reversal Pro signal on ANY timeframe draws a red/green band and a
    directional bias (long: red below green). The band is 'active' from the DRS
    signal until superseded, capped at 30 days.
  * TREND: 200-SMA on the trigger's timeframe must agree (long: close > SMA200).
  * TRIGGER: a TD-Sequential setup-9 buy OR a V5 winners (aligned) bull divergence,
    on ANY timeframe, firing while price is AT OR BELOW red (entry <= red + 0.5*ATR).
  * EXIT (per user): fixed SL 1.5xATR / TP 4.0xATR  -> +2.667R win, -1R loss.
  * Mirror for shorts (DRS short zone, downtrend, TD sell / V5 bear, at/above red).

Reports the full combo (T2) against controls so the DRS contribution is visible:
  T0 = raw trigger (TD/V5 buy), no context
  T1 = trigger + 200-SMA trend agreement
  T2 = trigger + trend + active DRS zone + at/below red   (the full combo)
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
    atr_wilder, detect_divergences, drop_incomplete_last_bar, fetch_ohlcv,
    resample_ohlcv,
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
ZONE_MAX_DAYS = 30
BUF_ATR = 0.5


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


def main():
    cfg = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))
    assets = cfg["assets"]
    div_cfg = dict(yaml.safe_load((ROOT/"config"/"v5_winners_scanner.yaml").read_text("utf-8"))["divergence"])
    div_cfg["aligned_only"] = True
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}
    rows = []

    for asset, spec in assets.items():
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        frames = {}
        drs_long, drs_short = [], []     # (time, red)
        triggers = []                    # (time, tf, dir, entry, atr, sma200, i)
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
            atr = atr_wilder(frame, 20)
            sma = frame["Close"].rolling(200).mean().to_numpy()

            # DRS zones on this TF
            lc, sc, datr = drs_signals(frame, has_vol)
            for i in range(len(frame)):
                if not np.isfinite(datr[i]) or datr[i] <= 0:
                    continue
                if lc[i]:
                    drs_long.append((idx[i], low[i]-1.5*datr[i]))
                if sc[i]:
                    drs_short.append((idx[i], high[i]+1.5*datr[i]))

            # TD buy/sell triggers
            tdbuy, tdsell = td_setups(close)
            atr14 = atr_wilder(frame, 14)
            for i in tdbuy:
                if i > 210 and np.isfinite(atr14[i]) and atr14[i] > 0:
                    triggers.append((idx[i], tf, "long", close[i], atr14[i], sma[i], i, "TD"))
            for i in tdsell:
                if i > 210 and np.isfinite(atr14[i]) and atr14[i] > 0:
                    triggers.append((idx[i], tf, "short", close[i], atr14[i], sma[i], i, "TD"))

            # V5 divergence triggers
            sigs = detect_divergences(frame, asset, tk, tf, TF_MIN[tf], div_cfg)
            pos = {t: k for k, t in enumerate(idx)}
            for s in sigs:
                ci = pos.get(s.confirm_time)
                if ci is None or ci <= 210 or not np.isfinite(atr14[ci]) or atr14[ci] <= 0:
                    continue
                d = "long" if s.direction == "BULL" else "short"
                triggers.append((idx[ci], tf, d, close[ci], atr14[ci], sma[ci], ci, "V5"))

        drs_long.sort(); drs_short.sort()
        dl_t = [t for t, _ in drs_long]; dl_r = [r for _, r in drs_long]
        ds_t = [t for t, _ in drs_short]; ds_r = [r for _, r in drs_short]

        def active_red(zt, zr, ttime, entry, direction, atrv):
            # latest zone with time <= ttime, within 30d, price at/below(above) red
            import bisect
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

        for (ttime, tf, direction, entry, atrv, sma_i, i, srcname) in triggers:
            frame = frames[tf]
            high = frame["High"].to_numpy(); low = frame["Low"].to_numpy(); close = frame["Close"].to_numpy()
            trend_ok = np.isfinite(sma_i) and ((direction == "long" and entry > sma_i) or
                                               (direction == "short" and entry < sma_i))
            if direction == "long":
                zone_ok = active_red(dl_t, dl_r, ttime, entry, "long", atrv)
            else:
                zone_ok = active_red(ds_t, ds_r, ttime, entry, "short", atrv)
            r = score(high, low, close, i, direction, entry, atrv)
            rows.append(dict(asset=asset, tf=tf, dir=direction, src=srcname,
                             trend_ok=trend_ok, zone_ok=zone_ok, R=r))
        print(f"{asset:<8} triggers={len(triggers)} drsL={len(drs_long)} drsS={len(drs_short)}", flush=True)

    d = pd.DataFrame(rows)
    d.to_csv(ROOT/"logs"/"combo_signals.csv", index=False)

    def stat(sub, label):
        if len(sub) == 0:
            return dict(config=label, n=0)
        r = sub.R.to_numpy()
        return dict(config=label, n=len(sub),
                    win_pct=round(100*(r > 0).mean(), 1),
                    exp_R=round(float(r.mean()), 3), total_R=round(float(r.sum()), 1))

    print("\n=== POOLED (all assets, both directions) ===")
    tbl = pd.DataFrame([
        stat(d, "T0 raw trigger"),
        stat(d[d.trend_ok], "T1 + 200SMA trend"),
        stat(d[d.trend_ok & d.zone_ok], "T2 + DRS zone at/below red (FULL COMBO)"),
        stat(d[d.zone_ok], "DRS zone only (no trend)"),
    ])
    print(tbl.to_string(index=False))

    print("\n=== T2 full combo by trigger source ===")
    full = d[d.trend_ok & d.zone_ok]
    print(pd.DataFrame([stat(full[full.src == "TD"], "TD trigger"),
                        stat(full[full.src == "V5"], "V5 trigger")]).to_string(index=False))

    print("\n=== T2 full combo by asset (n>=5) ===")
    ba = []
    for a in assets:
        s = full[full.asset == a]
        if len(s) >= 5:
            ba.append(stat(s, a))
    print(pd.DataFrame(ba).to_string(index=False) if ba else "  none with n>=5")

    tbl.to_csv(ROOT/"logs"/"combo_summary.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
