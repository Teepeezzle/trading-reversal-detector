"""Exit-ratio sweep on the V5 + DRS-loose confluence — win rate vs profit.

Collect every V5-in-DRS-zone signal (all 15 assets, both dir, 2y), then re-score
under many SL/TP configs. $ risk is FIXED at $50/trade (position sized to the SL
distance), so configs are directly comparable:
  win $  = 50 * (TP_mult / SL_mult)   (reward:risk)
  loss $ = -50
As TP moves CLOSER / SL WIDER, win% rises but reward per win falls — the sweep
shows where net expectancy peaks.
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
LOOKBACK = pd.Timedelta(days=730)
PRUNED = ["XAUUSD", "GBPUSD", "USDJPY", "NAS100", "BTCUSD", "DOGEUSD", "EURUSD", "NZDJPY", "ETHUSD", "AUDUSD"]
# (SL_mult, TP_mult) grid
CONFIGS = [(1.5, 4.0), (1.5, 3.0), (1.5, 2.0), (1.5, 1.5),
           (2.0, 3.0), (2.0, 2.0), (2.0, 1.5), (2.0, 1.0),
           (2.5, 1.5), (3.0, 2.0), (1.0, 1.0)]


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


def outcome(high, low, close, i, direction, entry, atr, sl_m, tp_m):
    n = len(close)
    if direction == "long":
        sl, tp = entry-sl_m*atr, entry+tp_m*atr
    else:
        sl, tp = entry+sl_m*atr, entry-tp_m*atr
    for j in range(i+1, n):
        if direction == "long":
            if low[j] <= sl:
                return "SL"
            if high[j] >= tp:
                return "TP"
        else:
            if high[j] >= sl:
                return "SL"
            if low[j] <= tp:
                return "TP"
    return "OPEN"


def collect():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}; sigs = []
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
            ss = detect_divergences(frame, asset, tk, tf, TF_MIN[tf], DIV)
            ss = attach_trade_levels(ss, frame, int(DIV["atr_len"]), 1.5, 4.0)
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
                sigs.append((hi, lo, cl, c, d, s.close, s.atr, asset))
        print(f"{asset:<8} sigs={sum(1 for x in sigs if x[7]==asset)}", flush=True)
    return sigs


def sweep(sigs, label):
    print(f"\n=== EXIT SWEEP ({label}, n={len(sigs)}) ===")
    print(f"{'SL':>4}{'TP':>5}{'R:R':>8}{'win%':>8}{'winsPerLoss':>12}{'total$':>11}{'exp$/trade':>12}")
    rows = []
    for sl_m, tp_m in CONFIGS:
        win = loss = opn = 0; total = 0.0
        rr = tp_m/sl_m; win_amt = RISK_D*rr
        for (hi, lo, cl, c, d, entry, atr, _) in sigs:
            o = outcome(hi, lo, cl, c, d, entry, atr, sl_m, tp_m)
            if o == "TP":
                win += 1; total += win_amt
            elif o == "SL":
                loss += 1; total -= RISK_D
            else:
                opn += 1
        res = win + loss
        wr = 100*win/res if res else 0
        exp = total/len(sigs) if sigs else 0
        rows.append(dict(SL=sl_m, TP=tp_m, RR=round(rr, 2), win_pct=round(wr, 1),
                         n=len(sigs), total_usd=round(total, 0), exp_usd=round(exp, 2)))
        print(f"{sl_m:>4}{tp_m:>5}{('1:'+str(round(rr,2))):>8}{wr:>7.1f}%{win/max(loss,1):>12.2f}{total:>+11.0f}{exp:>+12.2f}")
    return pd.DataFrame(rows)


def main():
    sigs = collect()
    all_df = sweep(sigs, "ALL 15 assets")
    pr = [s for s in sigs if s[7] in PRUNED]
    pr_df = sweep(pr, "PRUNED set")
    with pd.ExcelWriter(ROOT/"logs"/"exit_sweep.xlsx", engine="openpyxl") as xl:
        all_df.to_excel(xl, sheet_name="All 15 assets", index=False)
        pr_df.to_excel(xl, sheet_name="Pruned set", index=False)
    print("\nWorkbook -> logs/exit_sweep.xlsx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
