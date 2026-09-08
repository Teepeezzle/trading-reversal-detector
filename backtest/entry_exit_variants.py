"""Confirmation-entry and partial-profit variants on the pruned V5+DRS confluence.

Base   = enter at divergence-confirm close; SL 1.5xATR / TP 4xATR (+2.667R/-1R).
Confirm= only enter if the NEXT bar closes in the trade direction; enter at that
         close (fewer trades, meant to raise quality/win rate). Same exit.
Partial= enter at confirm close; bank HALF at +1R (1.5xATR), move the rest to
         breakeven, let it run to +2.667R (4xATR).
           full loss (SL before TP1)        -> -1.0R
           TP1 then breakeven               -> +0.5R
           TP1 then TP2                      -> +1.833R
$ = fixed $50 risk/trade (1R). Pruned asset set, both directions, 2y.
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
from backtest.pr_confluence_backtest import TF_SPEC, TF_MIN  # noqa: E402

ASSETS = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))["assets"]
DIV = dict(yaml.safe_load((ROOT/"config"/"v5_winners_scanner.yaml").read_text("utf-8"))["divergence"])
DIV["aligned_only"] = True
ZONE_DAYS, BUF, RISK_D = 30, 0.5, 50.0
SL_M, TP_M = 1.5, 4.0
LOOKBACK = pd.Timedelta(days=730)
PRUNED = ["XAUUSD", "GBPUSD", "USDJPY", "NAS100", "BTCUSD", "DOGEUSD", "EURUSD", "NZDJPY", "ETHUSD", "AUDUSD"]


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


def base_R(hi, lo, cl, c, d, entry, a):
    n = len(cl)
    sl = entry-SL_M*a if d == "long" else entry+SL_M*a
    tp = entry+TP_M*a if d == "long" else entry-TP_M*a
    for j in range(c+1, n):
        if d == "long":
            if lo[j] <= sl:
                return -1.0
            if hi[j] >= tp:
                return TP_M/SL_M
        else:
            if hi[j] >= sl:
                return -1.0
            if lo[j] <= tp:
                return TP_M/SL_M
    fav = (cl[-1]-entry) if d == "long" else (entry-cl[-1])
    return fav/(SL_M*a)


def partial_R(hi, lo, cl, c, d, entry, a):
    n = len(cl); risk = SL_M*a
    sl = entry-risk if d == "long" else entry+risk
    tp1 = entry+risk if d == "long" else entry-risk        # +1R
    tp2 = entry+TP_M*a if d == "long" else entry-TP_M*a    # +2.667R
    for j in range(c+1, n):
        if d == "long":
            hit_sl, hit_tp1 = lo[j] <= sl, hi[j] >= tp1
        else:
            hit_sl, hit_tp1 = hi[j] >= sl, lo[j] <= tp1
        if hit_sl:
            return -1.0
        if hit_tp1:
            for k in range(j+1, n):        # phase 2: half runs, stop = breakeven
                if d == "long":
                    hit_be, hit_tp2 = lo[k] <= entry, hi[k] >= tp2
                else:
                    hit_be, hit_tp2 = hi[k] >= entry, lo[k] <= tp2
                if hit_tp2:
                    return 0.5 + 0.5*(TP_M/SL_M)
                if hit_be:
                    return 0.5
            fav = (cl[-1]-entry) if d == "long" else (entry-cl[-1])
            return 0.5 + 0.5*(fav/risk)
    fav = (cl[-1]-entry) if d == "long" else (entry-cl[-1])
    return fav/risk


def collect():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}; sigs = []
    for asset, spec in ASSETS.items():
        if asset not in PRUNED:
            continue
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        frames = {}
        for tf, (src, rule, per) in TF_SPEC.items():
            ck = (tk, src, per)
            if ck not in cache:
                cache[ck] = fetch_ohlcv(tk, src, per)
            base = cache[ck]
            if base is None or base.empty:
                continue
            hv = ("Volume" in base) and float(np.nansum(base["Volume"].to_numpy())) > 0
            frame = resample_ohlcv(base, rule, anchor) if rule else base
            frame = drop_incomplete_last_bar(frame, TF_MIN[tf], now)
            if len(frame) >= 260:
                frames[tf] = (frame, hv)
        if not frames:
            continue
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
        for d in ("long", "short"):
            o = np.argsort(drs[d][0]); drs[d] = ([drs[d][0][k] for k in o], [drs[d][1][k] for k in o])
        for tf, (frame, _) in frames.items():
            hi = frame["High"].to_numpy(); lo = frame["Low"].to_numpy(); cl = frame["Close"].to_numpy()
            atr14 = atr_wilder(frame, int(DIV["atr_len"]))
            ss = detect_divergences(frame, asset, tk, tf, TF_MIN[tf], DIV)
            ss = attach_trade_levels(ss, frame, int(DIV["atr_len"]), SL_M, TP_M)
            pos = {t: k for k, t in enumerate(frame.index)}
            for s in ss:
                if s.stop is None or not s.atr:
                    continue
                d = "long" if s.direction == "BULL" else "short"
                if not in_zone(drs[d][0], drs[d][1], s.confirm_time, s.close, s.atr, d):
                    continue
                c = pos[s.confirm_time]
                if c <= 210:
                    continue
                et = s.confirm_time + pd.Timedelta(minutes=TF_MIN[tf])
                if et < now - LOOKBACK:
                    continue
                sigs.append((hi, lo, cl, atr14, c, d, s.close, s.atr, asset))
        print(f"{asset:<8} sigs={sum(1 for x in sigs if x[8]==asset)}", flush=True)
    return sigs


def stats(name, results):
    r = np.array([x for x in results if x is not None])
    n = len(r); wins = int((r > 0).sum())
    total = float((r*RISK_D).sum())
    return dict(variant=name, n=n, positive_pct=round(100*wins/n, 1) if n else 0,
                total_usd=round(total, 0), exp_usd=round(total/n, 2) if n else 0,
                expR=round(float(r.mean()), 3) if n else 0)


def main():
    sigs = collect()
    base = [base_R(hi, lo, cl, c, d, entry, a) for (hi, lo, cl, atr, c, d, entry, a, _) in sigs]
    part = [partial_R(hi, lo, cl, c, d, entry, a) for (hi, lo, cl, atr, c, d, entry, a, _) in sigs]
    conf = []
    for (hi, lo, cl, atr, c, d, entry, a, _) in sigs:
        if c+1 >= len(cl):
            conf.append(None); continue
        ok = (cl[c+1] > cl[c]) if d == "long" else (cl[c+1] < cl[c])
        if not ok or not np.isfinite(atr[c+1]) or atr[c+1] <= 0:
            conf.append(None); continue
        conf.append(base_R(hi, lo, cl, c+1, d, cl[c+1], atr[c+1]))

    comp = pd.DataFrame([
        stats("BASE (enter@confirm, 1:2.67)", base),
        stats("CONFIRMATION entry (+1 bar)", conf),
        stats("PARTIAL (half@1R, BE, run 2.67R)", part),
    ])
    with pd.ExcelWriter(ROOT/"logs"/"entry_exit_variants.xlsx", engine="openpyxl") as xl:
        comp.to_excel(xl, sheet_name="Compare", index=False)
    print("\n=== VARIANTS (pruned set) ===")
    print(comp.to_string(index=False))
    print("\n(positive_pct = % of trades ending green; for PARTIAL that includes half-wins.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
