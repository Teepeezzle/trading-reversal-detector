"""Snapshot each pair's CURRENT confluence state for the dashboard (Option B).

Uses the scanner's own machinery (aligned V5 divergence + DRS-loose + chart-native
trend). For every configured asset it computes, as of the latest bar:
  - trend per timeframe (close vs that TF's chart-native 200-SMA),
  - nearest DRS support & resistance (any TF, within zone_max_days) + distance,
  - most recent aligned divergence in an allowed direction,
  - the freshest confluence SETUP (aligned div at a DRS zone) with entry/SL/TP,
  - a status: SETUP (fresh trigger) / NEAR (price at a level, watching) / QUIET.

Writes data.js (window.CONFLUENCE_STATE = {...}) for the dashboard artifact.
Only validated components -- no Daily pass, no TD tag, no PR (all disproven).
"""
from __future__ import annotations
import bisect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import (          # noqa: E402
    atr_wilder, attach_trade_levels, detect_divergences, drop_incomplete_last_bar,
    fetch_ohlcv, parse_tf_minutes, resample_ohlcv,
)
from src.v5_confluence import drs_signals            # noqa: E402

CFG = yaml.safe_load((ROOT / "config" / "v5_confluence_scanner.yaml").read_text("utf-8"))
DIV = dict(CFG["divergence"]); DIV["aligned_only"] = True
TF_CFG = CFG["timeframes"]; ASSETS = CFG["assets"]
ZONE_DAYS = int(CFG["drs"]["zone_max_days"]); BUF = float(CFG["drs"]["buffer_atr"])
SL_ATR = float(DIV["sl_atr_mult"]); TP_ATR = float(DIV["tp_atr_mult"])
SMA_LEN = int(DIV["trend_sma"]); MERGE_ATR = 0.75
FRESH_BARS = 5           # setup counts as "live" if triggered within this many bars
NEAR_ATR = 1.5           # price within this many ATR of an allowed-dir zone = NEAR
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "logs" / "dashboard_data.js")
TF_ORDER = list(TF_CFG)


def build_frames(ticker, anchor, cache, now):
    frames = {}
    for tf, spec in TF_CFG.items():
        src = str(spec["source_interval"]); per = str(spec["period"]); rule = spec.get("resample")
        ck = (ticker, src, per)
        if ck not in cache:
            cache[ck] = fetch_ohlcv(ticker, src, per)
        base = cache[ck]
        if base is None or base.empty:
            continue
        has_vol = ("Volume" in base) and float(np.nansum(base["Volume"].to_numpy())) > 0
        frame = resample_ohlcv(base, rule, anchor) if rule else base
        frame = drop_incomplete_last_bar(frame, parse_tf_minutes(tf), now)
        if len(frame) >= 220:
            frames[tf] = (frame, has_vol)
    return frames


def distinct(reds, atrv):
    if not reds:
        return 0
    tol = MERGE_ATR * atrv; kept = []
    for r in sorted(reds):
        if not kept or abs(r - kept[-1]) > tol:
            kept.append(r)
    return len(kept)


def asset_state(asset, spec, cache, now):
    tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
    allowed = [str(x).lower() for x in spec.get("dirs", ["buy", "sell"])]
    frames = build_frames(tk, anchor, cache, now)
    if not frames:
        return None
    # price/atr from the frame with the most recent last bar
    ptf = max(frames, key=lambda t: frames[t][0].index[-1])
    pframe = frames[ptf][0]
    price = float(pframe["Close"].iloc[-1])
    patr = float(atr_wilder(pframe, 14)[-1])
    last_ts = pframe.index[-1]

    # trend per TF (chart-native 200-SMA)
    trends = {}
    for tf, (frame, _) in frames.items():
        sma = frame["Close"].rolling(SMA_LEN).mean().to_numpy()
        c = float(frame["Close"].iloc[-1]); s = sma[-1]
        trends[tf] = ("up" if c > s else "down") if np.isfinite(s) else "na"

    # DRS zones (support = long-red, resistance = short-red) within window
    sup, res = [], []
    for tf, (frame, has_vol) in frames.items():
        lc, sc, atr = drs_signals(frame, has_vol)
        idx = frame.index; low = frame["Low"].to_numpy(); high = frame["High"].to_numpy()
        for i in range(len(frame)):
            if not np.isfinite(atr[i]) or atr[i] <= 0 or (now - idx[i]) > pd.Timedelta(days=ZONE_DAYS):
                continue
            if lc[i]:
                sup.append(low[i] - 1.5 * atr[i])
            if sc[i]:
                res.append(high[i] + 1.5 * atr[i])
    sup_below = [x for x in sup if x <= price]
    res_above = [x for x in res if x >= price]
    nearest_sup = max(sup_below) if sup_below else None
    nearest_res = min(res_above) if res_above else None

    def pack_level(lvl):
        if lvl is None:
            return None
        return dict(level=round(lvl, 6), dist_pct=round(abs(price - lvl) / price * 100, 2),
                    dist_atr=round(abs(price - lvl) / patr, 2) if patr > 0 else None)

    # zones for the confluence check, per direction, sorted by time
    zones = {"long": ([], []), "short": ([], [])}
    for tf, (frame, has_vol) in frames.items():
        lc, sc, atr = drs_signals(frame, has_vol)
        idx = frame.index; low = frame["Low"].to_numpy(); high = frame["High"].to_numpy()
        for i in range(len(frame)):
            if not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            if lc[i]:
                zones["long"][0].append(idx[i]); zones["long"][1].append(low[i] - 1.5 * atr[i])
            if sc[i]:
                zones["short"][0].append(idx[i]); zones["short"][1].append(high[i] + 1.5 * atr[i])
    for d in ("long", "short"):
        order = np.argsort(zones[d][0])
        zones[d] = ([zones[d][0][k] for k in order], [zones[d][1][k] for k in order])

    # most recent aligned divergence + freshest confluence setup (allowed dirs)
    last_div = None; setup = None
    for tf, (frame, _) in frames.items():
        bmin = parse_tf_minutes(tf); nbar = len(frame) - 1
        sigs = detect_divergences(frame, asset, tk, tf, bmin, DIV)
        sigs = attach_trade_levels(sigs, frame, int(DIV["atr_len"]), SL_ATR, TP_ATR)
        posmap = {t: k for k, t in enumerate(frame.index)}
        for s in sigs:
            direction = "long" if s.direction == "BULL" else "short"
            want = "buy" if direction == "long" else "sell"
            if want not in allowed or (now - s.confirm_time) > pd.Timedelta(days=ZONE_DAYS):
                continue
            bars_ago = nbar - posmap[s.confirm_time]
            if last_div is None or s.confirm_time > last_div["_t"]:
                last_div = dict(_t=s.confirm_time, dir=want, tf=tf, bars_ago=int(bars_ago))
            # confluence qualify
            if s.stop is None or s.atr is None:
                continue
            times, reds = zones[direction]
            k = bisect.bisect_right(times, s.confirm_time) - 1
            qual = []; kk = k
            while kk >= 0 and (s.confirm_time - times[kk]) <= pd.Timedelta(days=ZONE_DAYS):
                ok = (s.close <= reds[kk] + BUF * s.atr) if direction == "long" else (s.close >= reds[kk] - BUF * s.atr)
                if ok:
                    qual.append(reds[kk])
                kk -= 1
            if qual and (setup is None or s.confirm_time > setup["_t"]):
                setup = dict(_t=s.confirm_time, side=want.upper(), tf=tf, bars_ago=int(bars_ago),
                             entry=round(float(s.close), 6), stop=round(float(s.stop), 6),
                             target=round(float(s.target), 6), zones=distinct(qual, s.atr))
    if last_div:
        last_div.pop("_t")
    if setup:
        setup.pop("_t")

    # nearest allowed-direction zone distance (for NEAR status)
    near_atr = None
    if "buy" in allowed and nearest_sup is not None:
        near_atr = abs(price - nearest_sup) / patr if patr > 0 else None
    if "sell" in allowed and nearest_res is not None:
        d2 = abs(price - nearest_res) / patr if patr > 0 else None
        near_atr = d2 if near_atr is None else min(near_atr, d2)

    if setup and setup["bars_ago"] <= FRESH_BARS:
        status = "SETUP"
    elif near_atr is not None and near_atr <= NEAR_ATR:
        status = "NEAR"
    else:
        status = "QUIET"

    up = sum(1 for v in trends.values() if v == "up"); dn = sum(1 for v in trends.values() if v == "down")
    return dict(asset=asset, ticker=tk, dirs=allowed, price=round(price, 6),
                updated=str(last_ts), price_tf=ptf, atr=round(patr, 6),
                trends=trends, trend_bias=("up" if up > dn else "down" if dn > up else "mixed"),
                support=pack_level(nearest_sup), resistance=pack_level(nearest_res),
                near_atr=round(near_atr, 2) if near_atr is not None else None,
                last_div=last_div, setup=setup, status=status)


def main():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}; out = []
    for asset, spec in ASSETS.items():
        st = asset_state(asset, spec, cache, now)
        if st:
            out.append(st)
            print(f"{asset:<8} {st['status']:<6} bias {st['trend_bias']:<5} "
                  f"{'SETUP '+st['setup']['side'] if st['setup'] else 'no setup'}", flush=True)
    rank = {"SETUP": 0, "NEAR": 1, "QUIET": 2}
    out.sort(key=lambda a: (rank[a["status"]], a["asset"]))
    data = {"generated": now.strftime("%Y-%m-%d %H:%M UTC"),
            "tf_order": TF_ORDER,
            "counts": {"setup": sum(1 for a in out if a["status"] == "SETUP"),
                       "near": sum(1 for a in out if a["status"] == "NEAR"),
                       "quiet": sum(1 for a in out if a["status"] == "QUIET")},
            "assets": out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("window.CONFLUENCE_STATE = " + json.dumps(data, separators=(",", ":")) + ";",
                   encoding="utf-8")
    print(f"\nWrote {OUT}  ({len(out)} assets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
