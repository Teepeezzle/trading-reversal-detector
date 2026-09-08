"""Detailed per-trade results for the BEST confluence: V5 + DRS-loose.

Every aligned V5 divergence that sits in a DRS-loose zone (any same-dir DRS red
in the last 30d satisfying buy entry<=red+0.5ATR / sell entry>=red-0.5ATR),
across ALL 15 assets, BOTH directions, last 730d. Exit SL 1.5xATR / TP 4xATR
(+2.667R / -1R). $ = static $50/trade.

Full per-trade detail (entry/exit time+price, SL, TP, DRS level, bars held,
outcome, R, $) plus breakdowns by asset, asset x direction, asset x timeframe,
and month, so the prune/direction decision can be made on the numbers.
"""
from __future__ import annotations
import bisect, sys
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import (atr_wilder, attach_trade_levels, detect_divergences,  # noqa: E402
                               drop_incomplete_last_bar, fetch_ohlcv, resample_ohlcv)
from src.v5_confluence import drs_signals   # noqa: E402
from backtest.pr_confluence_backtest import TF_SPEC, TF_MIN  # noqa: E402

ASSETS = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))["assets"]
DIV = dict(yaml.safe_load((ROOT/"config"/"v5_winners_scanner.yaml").read_text("utf-8"))["divergence"])
DIV["aligned_only"] = True
SL_ATR, TP_ATR = 1.5, 4.0
R_WIN, R_LOSS = TP_ATR/SL_ATR, -1.0
ZONE_DAYS, BUF, RISK_D = 30, 0.5, 50.0
LOOKBACK = pd.Timedelta(days=730)


def in_zone(times, reds, T, entry, atr, direction):
    k = bisect.bisect_right(times, T) - 1
    while k >= 0 and (T - times[k]) <= pd.Timedelta(days=ZONE_DAYS):
        red = reds[k]
        if direction == "long" and entry <= red + BUF*atr:
            return red
        if direction == "short" and entry >= red - BUF*atr:
            return red
        k -= 1
    return None


def score_detail(frame, i, direction, entry, atrv):
    high = frame["High"].to_numpy(); low = frame["Low"].to_numpy(); close = frame["Close"].to_numpy()
    n = len(close)
    if direction == "long":
        sl, tp = entry-SL_ATR*atrv, entry+TP_ATR*atrv
    else:
        sl, tp = entry+SL_ATR*atrv, entry-TP_ATR*atrv
    for j in range(i+1, n):
        if direction == "long":
            if low[j] <= sl:
                return "SL", R_LOSS, j, sl
            if high[j] >= tp:
                return "TP", R_WIN, j, tp
        else:
            if high[j] >= sl:
                return "SL", R_LOSS, j, sl
            if low[j] <= tp:
                return "TP", R_WIN, j, tp
    mv = (close[-1]-entry) if direction == "long" else (entry-close[-1])
    return "OPEN", mv/(SL_ATR*atrv), n-1, close[-1]


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
            o = np.argsort(drs[d][0])
            drs[d] = ([drs[d][0][k] for k in o], [drs[d][1][k] for k in o])

        for tf, (frame, _) in frames.items():
            sigs = detect_divergences(frame, asset, tk, tf, TF_MIN[tf], DIV)
            sigs = attach_trade_levels(sigs, frame, int(DIV["atr_len"]), SL_ATR, TP_ATR)
            pos = {t: k for k, t in enumerate(frame.index)}
            for s in sigs:
                if s.stop is None or not s.atr:
                    continue
                d = "long" if s.direction == "BULL" else "short"
                red = in_zone(drs[d][0], drs[d][1], s.confirm_time, s.close, s.atr, d)
                if red is None:
                    continue
                c = pos[s.confirm_time]
                if c <= 210:
                    continue
                entry_t = s.confirm_time + pd.Timedelta(minutes=TF_MIN[tf])
                if entry_t < now - LOOKBACK:
                    continue
                outcome, R, xi, xpx = score_detail(frame, c, d, s.close, s.atr)
                rows.append(dict(
                    asset=asset, tf=tf, side=("BUY" if d == "long" else "SELL"),
                    entry_time_utc=entry_t,
                    exit_time_utc=frame.index[xi] + pd.Timedelta(minutes=TF_MIN[tf]),
                    bars_held=xi - c, entry=round(s.close, 6), stop=round(s.stop, 6),
                    target=round(s.target, 6), drs_red=round(red, 6),
                    exit_price=round(xpx, 6), atr=round(s.atr, 6), span=s.span,
                    outcome=outcome, R=round(R, 3), pnl_usd=round(R*RISK_D, 2)))
        print(f"{asset:<8} trades={sum(1 for r in rows if r['asset']==asset)}", flush=True)
    return pd.DataFrame(rows).sort_values("entry_time_utc").reset_index(drop=True), now


def agg(sub):
    res = sub[sub.outcome != "OPEN"]
    return dict(n=len(sub), wins=int((sub.outcome == "TP").sum()), losses=int((sub.outcome == "SL").sum()),
                open=int((sub.outcome == "OPEN").sum()),
                win_pct=round(100*(res.outcome == "TP").mean(), 1) if len(res) else np.nan,
                total_R=round(sub.R.sum(), 1), total_usd=round(sub.pnl_usd.sum(), 2),
                expR=round(sub.R.mean(), 3), avg_bars=int(round(sub.bars_held.mean())) if len(sub) else 0)


def main():
    d, now = run()
    if d.empty:
        print("No trades."); return 0
    d["month"] = pd.to_datetime(d.entry_time_utc).dt.to_period("M").astype(str)
    by_asset = pd.DataFrame([dict(asset=a, **agg(d[d.asset == a])) for a in d.asset.unique()]).sort_values("total_R", ascending=False)
    ad = []
    for a in d.asset.unique():
        for sd in ["BUY", "SELL"]:
            sub = d[(d.asset == a) & (d.side == sd)]
            if not sub.empty:
                ad.append(dict(asset=a, side=sd, **agg(sub)))
    by_asset_dir = pd.DataFrame(ad).sort_values(["asset", "side"])
    at = []
    for a in d.asset.unique():
        for tf in d.tf.unique():
            sub = d[(d.asset == a) & (d.tf == tf)]
            if not sub.empty:
                at.append(dict(asset=a, tf=tf, **agg(sub)))
    by_asset_tf = pd.DataFrame(at)
    by_month = pd.DataFrame([dict(month=m, **agg(d[d.month == m])) for m in sorted(d.month.unique())])

    # cumulative equity chart (all 15)
    dd = d.sort_values("exit_time_utc").copy(); dd["cum_R"] = dd.R.cumsum()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(pd.to_datetime(dd.exit_time_utc), dd.cum_R, color="#2563eb", lw=1.6)
    ax.axhline(0, color="#9ca3af", lw=0.8)
    ax.set_title(f"V5+DRS-loose (all 15) — cumulative R (2y, n={len(dd)}, {dd.cum_R.iloc[-1]:+.1f}R)")
    ax.set_ylabel("Cumulative R"); ax.grid(alpha=0.25); fig.tight_layout()
    fig.savefig(ROOT/"logs"/"drs_v5_detail_equity.png", dpi=110); plt.close(fig)

    with pd.ExcelWriter(ROOT/"logs"/"drs_v5_detail.xlsx", engine="openpyxl") as xl:
        by_asset.to_excel(xl, sheet_name="By asset", index=False)
        by_asset_dir.to_excel(xl, sheet_name="By asset x direction", index=False)
        by_asset_tf.to_excel(xl, sheet_name="By asset x timeframe", index=False)
        by_month.to_excel(xl, sheet_name="By month", index=False)
        d.drop(columns=["month"]).to_excel(xl, sheet_name="All trades", index=False)
    print("\nBY ASSET:\n", by_asset.to_string(index=False))
    print("\nBY ASSET x DIRECTION (positive only):\n",
          by_asset_dir[by_asset_dir.total_R > 0].sort_values("total_R", ascending=False).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
