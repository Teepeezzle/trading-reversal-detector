"""Backtest: aligned V5 divergence AT a Predictive-Range edge (the study tool).

Setup (mirrors pine/predictive_range_v5_study.pine):
  * Continuous Predictive Range: unit = mult * ATR(prLen); a midline that only
    STEPS by one unit when price pushes >1 unit away, else holds. Edges =
    mid +/- unit (upper resistance / lower support).
  * Trigger: an ALIGNED V5 divergence (BULL in uptrend / BEAR in downtrend)
    whose confirmation close lands AT the matching edge:
      BUY  = bull div with close <= lower + 0.25*unit   (at support)
      SELL = bear div with close >= upper - 0.25*unit   (at resistance)
  * Exit: SL 1.5xATR / TP 4.0xATR (+2.667R / -1R).  $ = static $50/trade.

Across all 15 assets x 7 TFs (15m-4h), last 730 days by entry. 15m/30m/45m
have only ~60d yfinance history; 1h-4h span the full 2y. Proxies, not OANDA.
Outputs logs/pr_confluence_* (xlsx + charts).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import (          # noqa: E402
    atr_wilder, attach_trade_levels, detect_divergences, drop_incomplete_last_bar,
    fetch_ohlcv, parse_tf_minutes, resample_ohlcv,
)

ASSETS = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))["assets"]
DIV = dict(yaml.safe_load((ROOT/"config"/"v5_winners_scanner.yaml").read_text("utf-8"))["divergence"])
DIV["aligned_only"] = True
SL_ATR, TP_ATR = 1.5, 4.0
R_WIN, R_LOSS = TP_ATR/SL_ATR, -1.0
PR_LEN, PR_MULT, EDGE_BUF = 200, 6.0, 0.25
RISK_D = 50.0
LOOKBACK = pd.Timedelta(days=730)
TF_SPEC = {"15m": ("15m", None, "60d"), "30m": ("30m", None, "60d"),
           "45m": ("15m", "45min", "60d"), "1h": ("1h", None, "730d"),
           "2h": ("1h", "2h", "730d"), "3h": ("1h", "3h", "730d"), "4h": ("1h", "4h", "730d")}
TF_MIN = {"15m": 15, "30m": 30, "45m": 45, "1h": 60, "2h": 120, "3h": 180, "4h": 240}


def predictive_range(frame, pr_len, mult):
    atr = atr_wilder(frame, pr_len)
    close = frame["Close"].to_numpy(); n = len(close)
    unit = mult * atr
    mid = np.full(n, np.nan)
    for i in range(n):
        if i == 0:
            mid[i] = close[i]; continue
        u = unit[i]; m = mid[i-1]
        if not np.isfinite(u) or not np.isfinite(m):
            mid[i] = close[i] if not np.isfinite(m) else m
            continue
        if close[i] - m > u:
            mid[i] = m + u
        elif m - close[i] > u:
            mid[i] = m - u
        else:
            mid[i] = m
    return mid, mid + unit, mid - unit, unit


def score(frame, i, direction, entry, atrv):
    high = frame["High"].to_numpy(); low = frame["Low"].to_numpy(); close = frame["Close"].to_numpy()
    idx = frame.index; n = len(close)
    if direction == "long":
        sl, tp = entry-SL_ATR*atrv, entry+TP_ATR*atrv
    else:
        sl, tp = entry+SL_ATR*atrv, entry-TP_ATR*atrv
    for j in range(i+1, n):
        if direction == "long":
            if low[j] <= sl:
                return "SL", R_LOSS, idx[j]
            if high[j] >= tp:
                return "TP", R_WIN, idx[j]
        else:
            if high[j] >= sl:
                return "SL", R_LOSS, idx[j]
            if low[j] <= tp:
                return "TP", R_WIN, idx[j]
    mv = (close[-1]-entry) if direction == "long" else (entry-close[-1])
    return "OPEN", mv/(SL_ATR*atrv), idx[-1]


def run():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}; trades = []
    for asset, spec in ASSETS.items():
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        for tf, (src, rule, per) in TF_SPEC.items():
            ck = (tk, src, per)
            if ck not in cache:
                cache[ck] = fetch_ohlcv(tk, src, per)
            base = cache[ck]
            if base is None or base.empty:
                continue
            frame = resample_ohlcv(base, rule, anchor) if rule else base
            frame = drop_incomplete_last_bar(frame, TF_MIN[tf], now)
            if len(frame) < 260:
                continue
            mid, upper, lower, unit = predictive_range(frame, PR_LEN, PR_MULT)
            atr14 = atr_wilder(frame, int(DIV["atr_len"]))
            sigs = detect_divergences(frame, asset, tk, tf, TF_MIN[tf], DIV)
            sigs = attach_trade_levels(sigs, frame, int(DIV["atr_len"]), SL_ATR, TP_ATR)
            pos = {t: k for k, t in enumerate(frame.index)}
            for s in sigs:
                if s.stop is None:
                    continue
                c = pos[s.confirm_time]
                if c <= 210 or not np.isfinite(unit[c]) or unit[c] <= 0:
                    continue
                direction = "long" if s.direction == "BULL" else "short"
                if direction == "long":
                    at_edge = s.close <= lower[c] + EDGE_BUF*unit[c]
                else:
                    at_edge = s.close >= upper[c] - EDGE_BUF*unit[c]
                if not at_edge:
                    continue
                entry_t = s.confirm_time + pd.Timedelta(minutes=TF_MIN[tf])
                if entry_t < now - LOOKBACK:
                    continue
                outcome, R, xt = score(frame, c, direction, s.close, s.atr)
                trades.append(dict(asset=asset, tf=tf,
                                   side=("BUY" if direction == "long" else "SELL"),
                                   entry_time=entry_t, exit_time=xt + pd.Timedelta(minutes=TF_MIN[tf]),
                                   entry=round(s.close, 6), stop=round(s.stop, 6),
                                   target=round(s.target, 6), pr_edge=round(lower[c] if direction == "long" else upper[c], 6),
                                   outcome=outcome, R=round(R, 3), pnl_usd=round(R*RISK_D, 2)))
        print(f"{asset:<8} trades={sum(1 for t in trades if t['asset']==asset)}", flush=True)
    return pd.DataFrame(trades).sort_values("exit_time").reset_index(drop=True) if trades else pd.DataFrame(), now


def agg(sub):
    res = sub[sub.outcome != "OPEN"]
    return dict(n=len(sub), wins=int((sub.outcome == "TP").sum()), losses=int((sub.outcome == "SL").sum()),
                open=int((sub.outcome == "OPEN").sum()),
                win_pct=round(100*(res.outcome == "TP").mean(), 1) if len(res) else np.nan,
                total_R=round(sub.R.sum(), 1), total_usd=round(sub.pnl_usd.sum(), 2),
                expR=round(sub.R.mean(), 3))


def charts(d, by_asset, by_month):
    dd = d.copy(); dd["cum_R"] = dd.R.cumsum(); dd["cum_usd"] = dd.pnl_usd.cumsum()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(pd.to_datetime(dd.exit_time), dd.cum_R, color="#2563eb", lw=1.8)
    ax.axhline(0, color="#9ca3af", lw=0.8)
    ax.fill_between(pd.to_datetime(dd.exit_time), dd.cum_R, 0, where=(dd.cum_R >= 0), color="#16a34a", alpha=0.12)
    ax.fill_between(pd.to_datetime(dd.exit_time), dd.cum_R, 0, where=(dd.cum_R < 0), color="#dc2626", alpha=0.12)
    ax.set_title(f"PR + V5 confluence — cumulative R (2y, n={len(dd)}, final {dd.cum_R.iloc[-1]:+.1f}R / ${dd.cum_usd.iloc[-1]:+,.0f})")
    ax.set_ylabel("Cumulative R"); ax.grid(alpha=0.25); fig.tight_layout()
    fig.savefig(ROOT/"logs"/"pr_confluence_equity.png", dpi=110); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 5))
    cols = ["#16a34a" if v >= 0 else "#dc2626" for v in by_asset.total_R]
    ax.bar(by_asset.asset, by_asset.total_R, color=cols); ax.axhline(0, color="#111827", lw=0.8)
    for i, (v, n) in enumerate(zip(by_asset.total_R, by_asset.n)):
        ax.text(i, v + (0.4 if v >= 0 else -0.9), f"{v:+.0f}R\nn={n}", ha="center", fontsize=7)
    ax.set_title("PR + V5 confluence — total R by asset (2y)"); ax.set_ylabel("Total R")
    ax.tick_params(axis="x", rotation=45, labelsize=8); ax.grid(axis="y", alpha=0.25); fig.tight_layout()
    fig.savefig(ROOT/"logs"/"pr_confluence_by_asset.png", dpi=110); plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 5))
    cols = ["#16a34a" if v >= 0 else "#dc2626" for v in by_month.total_R]
    ax.bar(by_month.month, by_month.total_R, color=cols); ax.axhline(0, color="#111827", lw=0.8)
    ax.set_title("PR + V5 confluence — total R by month (2y)"); ax.set_ylabel("Total R")
    ax.tick_params(axis="x", rotation=90, labelsize=7); ax.grid(axis="y", alpha=0.25); fig.tight_layout()
    fig.savefig(ROOT/"logs"/"pr_confluence_by_month.png", dpi=110); plt.close(fig)


def main():
    d, now = run()
    if d.empty:
        print("No trades."); return 0
    d["month"] = pd.to_datetime(d.entry_time).dt.to_period("M").astype(str)
    by_asset = pd.DataFrame([dict(asset=a, **agg(d[d.asset == a])) for a in d.asset.unique()]).sort_values("total_R", ascending=False)
    by_side = pd.DataFrame([dict(side=s, **agg(d[d.side == s])) for s in ["BUY", "SELL"]])
    by_tf = pd.DataFrame([dict(tf=t, **agg(d[d.tf == t])) for t in d.tf.unique()])
    by_month = pd.DataFrame([dict(month=m, **agg(d[d.month == m])) for m in sorted(d.month.unique())])
    charts(d, by_asset, by_month)
    res = d[d.outcome != "OPEN"]
    overall = dict(n=len(d), win_pct=round(100*(res.outcome == "TP").mean(), 1),
                   total_R=round(d.R.sum(), 1), total_usd=round(d.pnl_usd.sum(), 2), expR=round(d.R.mean(), 3))
    readme = pd.DataFrame({"PR + V5 confluence 2y backtest — read me": [
        "Aligned V5 divergence AT a Predictive-Range edge (bull@support / bear@resistance).",
        f"PR: unit={PR_MULT}xATR({PR_LEN}); edge buffer {EDGE_BUF}xunit. Exit SL 1.5xATR/TP 4xATR (+2.667R/-1R).",
        "$ = static $50/trade (5% of $1000). Window last 730d by entry. All 15 assets x 7 TFs (15m-4h).",
        "15m/30m/45m ~60d history only; 1h-4h full 2y. yfinance proxies, not OANDA. outcome TP=win/SL=loss/OPEN=MTM.",
    ]})
    with pd.ExcelWriter(ROOT/"logs"/"pr_confluence_backtest.xlsx", engine="openpyxl") as xl:
        pd.DataFrame([overall]).to_excel(xl, sheet_name="Overall", index=False)
        by_asset.to_excel(xl, sheet_name="By asset", index=False)
        by_side.to_excel(xl, sheet_name="By direction", index=False)
        by_tf.to_excel(xl, sheet_name="By timeframe", index=False)
        by_month.to_excel(xl, sheet_name="By month", index=False)
        d.drop(columns=["month"]).to_excel(xl, sheet_name="All trades", index=False)
        readme.to_excel(xl, sheet_name="README", index=False)
    print("\nOVERALL:", overall)
    print("\nBY ASSET:\n", by_asset.to_string(index=False))
    print("\nBY DIRECTION:\n", by_side.to_string(index=False))
    print("\nBY TIMEFRAME:\n", by_tf.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
