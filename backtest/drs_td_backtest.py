"""DRS-loose confluence + fixed TD countdown — does the countdown help?

DRS-loose zone = ANY same-dir DRS red in the last 30d whose level satisfies the
price condition (buy entry <= red+0.5ATR / sell entry >= red-0.5ATR).

Triggers tested (all in the DRS zone; exit SL 1.5xATR / TP 4xATR):
  V5        = aligned V5 divergence in zone            (the current DRS-loose baseline)
  TDcd      = fixed TD countdown-13 completion in zone (countdown as the trigger)
  V5+cd     = a V5-in-zone entry that ALSO has a TD countdown-13 (same asset/dir)
              within +/-3 days  (countdown as CONFIRMATION of the V5 entry)

All 15 assets x 7 TFs (15m-4h), last 730d by entry. $ = static $50/trade.
Reports overall per-variant + per-asset, and a PRUNED view (user's set + positives).
"""
from __future__ import annotations
import bisect, sys
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import (atr_wilder, attach_trade_levels, detect_divergences,  # noqa: E402
                               drop_incomplete_last_bar, fetch_ohlcv, resample_ohlcv)
from src.v5_confluence import drs_signals   # noqa: E402
from backtest.pr_td_backtest import td_full  # noqa: E402
from backtest.pr_confluence_backtest import score, agg, TF_SPEC, TF_MIN  # noqa: E402

ASSETS = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))["assets"]
DIV = dict(yaml.safe_load((ROOT/"config"/"v5_winners_scanner.yaml").read_text("utf-8"))["divergence"])
DIV["aligned_only"] = True
ZONE_DAYS, BUF, RISK_D = 30, 0.5, 50.0
LOOKBACK = pd.Timedelta(days=730)
CONFIRM = pd.Timedelta(days=3)
PRUNED = ["XAUUSD", "GBPUSD", "USDJPY", "NAS100", "BTCUSD", "DOGEUSD", "EURUSD", "NZDJPY"]


def in_zone(times, reds, T, entry, atr, direction):
    k = bisect.bisect_right(times, T) - 1
    while k >= 0 and (T - times[k]) <= pd.Timedelta(days=ZONE_DAYS):
        red = reds[k]
        if direction == "long" and entry <= red + BUF*atr:
            return True
        if direction == "short" and entry >= red - BUF*atr:
            return True
        k -= 1
    return False


def run():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}; rows = []
    for asset, spec in ASSETS.items():
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        frames = {}
        for tf, (src, rule, per) in TF_SPEC.items():
            ck = (tk, src, per)
            if ck not in cache:
                cache[ck] = fetch_ohlcv(tk, src, per)
            base = cache[ck]
            if base is None or base.empty:
                continue
            has_vol = ("Volume" in base) and float(np.nansum(base["Volume"].to_numpy())) > 0
            frame = resample_ohlcv(base, rule, anchor) if rule else base
            frame = drop_incomplete_last_bar(frame, TF_MIN[tf], now)
            if len(frame) >= 260:
                frames[tf] = (frame, has_vol)
        if not frames:
            continue
        # DRS zones per dir
        drs = {"long": ([], []), "short": ([], [])}
        for tf, (frame, hv) in frames.items():
            lc, sc, atr = drs_signals(frame, hv)
            idx = frame.index; low = frame["Low"].to_numpy(); high = frame["High"].to_numpy()
            for i in range(len(frame)):
                if not np.isfinite(atr[i]) or atr[i] <= 0:
                    continue
                if lc[i]:
                    drs["long"][0].append(idx[i]); drs["long"][1].append(low[i]-1.5*atr[i])
                if sc[i]:
                    drs["short"][0].append(idx[i]); drs["short"][1].append(high[i]+1.5*atr[i])
        for dctn in ("long", "short"):
            o = np.argsort(drs[dctn][0])
            drs[dctn] = ([drs[dctn][0][k] for k in o], [drs[dctn][1][k] for k in o])

        # all TD countdown-13 times per dir (for the confirmation check)
        cd_times = {"long": [], "short": []}
        # gather triggers
        v5_trigs = []; cd_trigs = []
        for tf, (frame, _) in frames.items():
            close = frame["Close"].to_numpy(); high = frame["High"].to_numpy(); low = frame["Low"].to_numpy()
            atr14 = atr_wilder(frame, int(DIV["atr_len"]))
            idx = frame.index
            td = td_full(close, high, low)
            for c in td["cd_buy"]:
                cd_times["long"].append(idx[c])
            for c in td["cd_sell"]:
                cd_times["short"].append(idx[c])
            for c in td["cd_buy"] + td["cd_sell"]:
                d = "long" if c in td["cd_buy"] else "short"
                if c > 210 and np.isfinite(atr14[c]) and atr14[c] > 0:
                    cd_trigs.append((idx[c], tf, d, close[c], atr14[c], c, frame))
            sigs = detect_divergences(frame, asset, tk, tf, TF_MIN[tf], DIV)
            sigs = attach_trade_levels(sigs, frame, int(DIV["atr_len"]), 1.5, 4.0)
            pos = {t: k for k, t in enumerate(idx)}
            for s in sigs:
                if s.stop is None:
                    continue
                d = "long" if s.direction == "BULL" else "short"
                c = pos[s.confirm_time]
                if c > 210 and s.atr:
                    v5_trigs.append((s.confirm_time, tf, d, s.close, s.atr, c, frame))
        for d in ("long", "short"):
            cd_times[d].sort()

        def emit(trigs, source):
            for (T, tf, d, entry, atr, c, frame) in trigs:
                if not np.isfinite(atr) or atr <= 0:
                    continue
                if not in_zone(drs[d][0], drs[d][1], T, entry, atr, d):
                    continue
                entry_t = T + pd.Timedelta(minutes=TF_MIN[tf])
                if entry_t < now - LOOKBACK:
                    continue
                outcome, R, xt = score(frame, c, d, entry, atr)
                # countdown confirmation within +/-3d (for V5 rows)
                ct = cd_times[d]
                k = bisect.bisect_left(ct, T)
                cd_confirm = any(0 <= j < len(ct) and abs(ct[j]-T) <= CONFIRM for j in (k-1, k))
                rows.append(dict(source=source, asset=asset, tf=tf,
                                 side=("BUY" if d == "long" else "SELL"),
                                 entry_time=entry_t, outcome=outcome, R=round(R, 3),
                                 pnl_usd=round(R*RISK_D, 2), cd_confirm=cd_confirm))
        emit(v5_trigs, "V5")
        emit(cd_trigs, "TDcd")
        print(f"{asset:<8} v5={len(v5_trigs)} cd={len(cd_trigs)}", flush=True)
    return pd.DataFrame(rows), now


def main():
    d, now = run()
    if d.empty:
        print("No trades."); return 0
    v5 = d[d.source == "V5"]
    tdcd = d[d.source == "TDcd"]
    v5cd = v5[v5.cd_confirm]

    def block(name, sub, assets=None):
        if assets is not None:
            sub = sub[sub.asset.isin(assets)]
        return dict(variant=name, **agg(sub))

    variants = pd.DataFrame([
        block("V5+DRS (baseline)", v5),
        block("TDcd+DRS", tdcd),
        block("V5+DRS +countdown-confirm", v5cd),
        block("-- PRUNED SET --", d[d.asset.isin(PRUNED)][d.source == "V5"]) if False else
        block("V5+DRS (PRUNED)", v5, PRUNED),
        block("TDcd+DRS (PRUNED)", tdcd, PRUNED),
        block("V5+DRS +cd-confirm (PRUNED)", v5cd, PRUNED),
    ])

    def per_asset(sub):
        return pd.DataFrame([dict(asset=a, **agg(sub[sub.asset == a])) for a in ASSETS if not sub[sub.asset == a].empty]).sort_values("total_R", ascending=False)
    ba_v5 = per_asset(v5); ba_cd = per_asset(tdcd)
    with pd.ExcelWriter(ROOT/"logs"/"drs_td_backtest.xlsx", engine="openpyxl") as xl:
        variants.to_excel(xl, sheet_name="Variants", index=False)
        ba_v5.to_excel(xl, sheet_name="V5+DRS by asset", index=False)
        ba_cd.to_excel(xl, sheet_name="TDcd+DRS by asset", index=False)
        d.to_excel(xl, sheet_name="All trades", index=False)
    print("\nVARIANTS:\n", variants.to_string(index=False))
    print("\nV5+DRS by asset:\n", ba_v5.to_string(index=False))
    print("\nTDcd+DRS by asset:\n", ba_cd.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
