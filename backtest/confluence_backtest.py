"""Full 2-year per-trade backtest of the LIVE V5 CONFLUENCE logic.

Replicates v5_confluence_scan.py exactly (walk-forward):
  For each aligned V5 divergence (allowed direction) on the shortlist, find the
  LATEST same-direction DRS red level (any TF) with time <= trigger and within
  30 days, require price at/near it (buy <= red+0.5ATR / sell >= red-0.5ATR),
  then score SL 1.5xATR / TP 4.0xATR (+2.667R / -1R).

Window: last 730 days by ENTRY time. (15m/30m/45m only have ~60d of yfinance
history, so those TFs contribute recent trades only; 1h-4h span the full 2y.)

Outputs:
  logs/confluence_trades.csv / .xlsx  (per-trade wins & losses + breakdowns)
  logs/confluence_equity.png, _by_asset.png, _by_month.png  (charts)
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
from src.v5_divergence import (          # noqa: E402
    atr_wilder, attach_trade_levels, detect_divergences, drop_incomplete_last_bar,
    fetch_ohlcv, parse_tf_minutes, resample_ohlcv,
)
from src.v5_confluence import drs_signals   # noqa: E402

CFG = yaml.safe_load((ROOT/"config"/"v5_confluence_scanner.yaml").read_text("utf-8"))
DIV = dict(CFG["divergence"]); DIV["aligned_only"] = True
TF_CFG = CFG["timeframes"]; ASSETS = CFG["assets"]
ZONE_DAYS = int(CFG["drs"]["zone_max_days"]); BUF = float(CFG["drs"]["buffer_atr"])
SL_ATR = float(DIV["sl_atr_mult"]); TP_ATR = float(DIV["tp_atr_mult"])
R_WIN, R_LOSS = TP_ATR/SL_ATR, -1.0
RISK_D = 0.05 * 1000.0                 # static model default: 5% of $1000 = $50/trade
LOOKBACK = pd.Timedelta(days=730)


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
                return "SL", R_LOSS, idx[j], sl
            if high[j] >= tp:
                return "TP", R_WIN, idx[j], tp
        else:
            if high[j] >= sl:
                return "SL", R_LOSS, idx[j], sl
            if low[j] <= tp:
                return "TP", R_WIN, idx[j], tp
    mv = (close[-1]-entry) if direction == "long" else (entry-close[-1])
    return "OPEN", mv/(SL_ATR*atrv), idx[-1], close[-1]


def run(mode, cache, now):
    """mode='latest' = live scanner logic (only the most recent DRS band).
    mode='anyzone' = looser rule used to pick the shortlist (any DRS zone in 30d
    whose red satisfies the price condition)."""
    trades = []
    for asset, spec in ASSETS.items():
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        allowed = [str(x).lower() for x in spec.get("dirs", ["buy", "sell"])]
        frames = build_frames(tk, anchor, cache, now)
        if not frames:
            continue
        # DRS signals per direction, sorted by time
        drs = {"long": ([], []), "short": ([], [])}
        for tf, (frame, has_vol) in frames.items():
            lc, sc, atr = drs_signals(frame, has_vol)
            idx = frame.index; low = frame["Low"].to_numpy(); high = frame["High"].to_numpy()
            for i in range(len(frame)):
                if not np.isfinite(atr[i]) or atr[i] <= 0:
                    continue
                if lc[i]:
                    drs["long"][0].append(idx[i]); drs["long"][1].append(low[i]-1.5*atr[i])
                if sc[i]:
                    drs["short"][0].append(idx[i]); drs["short"][1].append(high[i]+1.5*atr[i])
        for d in ("long", "short"):
            order = np.argsort(drs[d][0])
            drs[d] = ([drs[d][0][k] for k in order], [drs[d][1][k] for k in order])

        # V5 triggers per TF
        for tf, (frame, _) in frames.items():
            sigs = detect_divergences(frame, asset, tk, tf, parse_tf_minutes(tf), DIV)
            sigs = attach_trade_levels(sigs, frame, int(DIV["atr_len"]), SL_ATR, TP_ATR)
            pos = {t: k for k, t in enumerate(frame.index)}
            for s in sigs:
                if s.stop is None or s.atr is None:
                    continue
                direction = "long" if s.direction == "BULL" else "short"
                if ("buy" if direction == "long" else "sell") not in allowed:
                    continue
                T = s.confirm_time
                times, reds = drs[direction]
                k = bisect.bisect_right(times, T) - 1

                def price_ok(rv):
                    return (s.close <= rv + BUF*s.atr) if direction == "long" else (s.close >= rv - BUF*s.atr)

                red = None
                if mode == "latest":
                    if k >= 0 and (T - times[k]) <= pd.Timedelta(days=ZONE_DAYS) and price_ok(reds[k]):
                        red = reds[k]
                else:  # anyzone
                    kk = k
                    while kk >= 0 and (T - times[kk]) <= pd.Timedelta(days=ZONE_DAYS):
                        if price_ok(reds[kk]):
                            red = reds[kk]; break
                        kk -= 1
                if red is None:
                    continue
                i = pos[s.confirm_time]
                outcome, R, xt, xpx = score(frame, i, direction, s.close, s.atr)
                entry_t = s.confirm_time + pd.Timedelta(minutes=parse_tf_minutes(tf))
                if entry_t < now - LOOKBACK:
                    continue
                trades.append(dict(
                    asset=asset, tf=tf, side=("BUY" if direction == "long" else "SELL"),
                    entry_time=entry_t, exit_time=xt + pd.Timedelta(minutes=parse_tf_minutes(tf)),
                    entry=round(s.close, 6), stop=round(s.stop, 6), target=round(s.target, 6),
                    drs_red=round(red, 6), outcome=outcome, R=round(R, 3),
                    pnl_usd=round(R*RISK_D, 2)))
        print(f"{asset:<8} trades={sum(1 for t in trades if t['asset']==asset)}", flush=True)

    if not trades:
        return pd.DataFrame()
    return pd.DataFrame(trades).sort_values("exit_time").reset_index(drop=True)


def summarize(d):
    def agg(sub):
        res = sub[sub.outcome != "OPEN"]
        return dict(n=len(sub), wins=int((sub.outcome == "TP").sum()),
                    losses=int((sub.outcome == "SL").sum()), open=int((sub.outcome == "OPEN").sum()),
                    win_pct=round(100*(res.outcome == "TP").mean(), 1) if len(res) else np.nan,
                    total_R=round(sub.R.sum(), 1), total_usd=round(sub.pnl_usd.sum(), 2),
                    expR=round(sub.R.mean(), 3))
    by_asset = pd.DataFrame([dict(asset=a, **agg(d[d.asset == a])) for a in d.asset.unique()]).sort_values("total_R", ascending=False)
    by_side = pd.DataFrame([dict(side=s, **agg(d[d.side == s])) for s in ["BUY", "SELL"]])
    by_tf = pd.DataFrame([dict(tf=t, **agg(d[d.tf == t])) for t in d.tf.unique()])
    d["month"] = pd.to_datetime(d.entry_time).dt.to_period("M").astype(str)
    by_month = pd.DataFrame([dict(month=m, **agg(d[d.month == m])) for m in sorted(d.month.unique())])
    return by_asset, by_side, by_tf, by_month


def charts(d, by_asset, by_month, suffix, label):
    dd = d.copy()
    dd["cum_R"] = dd.R.cumsum(); dd["cum_usd"] = dd.pnl_usd.cumsum()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(pd.to_datetime(dd.exit_time), dd.cum_R, color="#2563eb", lw=1.8, marker="o", ms=3)
    ax.axhline(0, color="#9ca3af", lw=0.8)
    ax.fill_between(pd.to_datetime(dd.exit_time), dd.cum_R, 0, where=(dd.cum_R >= 0), color="#16a34a", alpha=0.12)
    ax.fill_between(pd.to_datetime(dd.exit_time), dd.cum_R, 0, where=(dd.cum_R < 0), color="#dc2626", alpha=0.12)
    ax.set_title(f"V5 Confluence [{label}] — cumulative R (2y, n={len(dd)}, "
                 f"final {dd.cum_R.iloc[-1]:+.1f}R / ${dd.cum_usd.iloc[-1]:+,.0f} @ $50/trade)")
    ax.set_ylabel("Cumulative R"); ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(ROOT/"logs"/f"confluence_equity_{suffix}.png", dpi=110); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    cols = ["#16a34a" if v >= 0 else "#dc2626" for v in by_asset.total_R]
    ax.bar(by_asset.asset, by_asset.total_R, color=cols)
    ax.axhline(0, color="#111827", lw=0.8)
    for i, (v, n) in enumerate(zip(by_asset.total_R, by_asset.n)):
        ax.text(i, v + (0.4 if v >= 0 else -0.8), f"{v:+.0f}R\nn={n}", ha="center", fontsize=8)
    ax.set_title(f"V5 Confluence [{label}] — total R by asset (2y)"); ax.set_ylabel("Total R"); ax.grid(axis="y", alpha=0.25)
    fig.tight_layout(); fig.savefig(ROOT/"logs"/f"confluence_by_asset_{suffix}.png", dpi=110); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 5))
    cols = ["#16a34a" if v >= 0 else "#dc2626" for v in by_month.total_R]
    ax.bar(by_month.month, by_month.total_R, color=cols)
    ax.axhline(0, color="#111827", lw=0.8)
    ax.set_title(f"V5 Confluence [{label}] — total R by month (2y)"); ax.set_ylabel("Total R")
    ax.tick_params(axis="x", rotation=90, labelsize=7); ax.grid(axis="y", alpha=0.25)
    fig.tight_layout(); fig.savefig(ROOT/"logs"/f"confluence_by_month_{suffix}.png", dpi=110); plt.close(fig)


def overall_row(label, d):
    res = d[d.outcome != "OPEN"]
    return dict(rule=label, n=len(d),
                win_pct=round(100*(res.outcome == "TP").mean(), 1) if len(res) else np.nan,
                total_R=round(d.R.sum(), 1), total_usd=round(d.pnl_usd.sum(), 2),
                expR=round(d.R.mean(), 3))


def main():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}
    results = {}
    for mode, label, suffix in (("latest", "LIVE latest-band", "live"),
                                ("anyzone", "LOOSER any-zone-30d", "loose")):
        print(f"\n########## {label} ##########")
        d = run(mode, cache, now)
        if d.empty:
            print("  no trades"); continue
        by_asset, by_side, by_tf, by_month = summarize(d)
        charts(d, by_asset, by_month, suffix, label)
        results[label] = (d, by_asset, by_side, by_tf, by_month)
        print("  overall:", overall_row(label, d))

    comp = pd.DataFrame([overall_row(l, r[0]) for l, r in results.items()])
    readme = pd.DataFrame({"V5 Confluence 2y backtest — read me": [
        "Two DRS rules compared:",
        "  LIVE latest-band = what the scanner does now: only the SINGLE most recent same-dir DRS red",
        "    (any TF, <=30d) must satisfy the price condition. Very strict -> few trades.",
        "  LOOSER any-zone-30d = the rule used to PICK the shortlist: ANY DRS zone in the last 30d whose",
        "    red satisfies the price condition qualifies. More trades, richer sample.",
        "Both: aligned V5 + trend + at/near red; exit SL 1.5xATR / TP 4xATR (+2.667R / -1R).",
        "$ = static 5% of $1000 = $50/trade. Window: last 730d by entry.",
        "15m/30m/45m have only ~60d yfinance history (recent trades only); 1h-4h span the full 2y.",
        "Data = yfinance proxies (XAUUSD=GC=F etc.), not your OANDA feed. outcome TP=win, SL=loss, OPEN=MTM.",
        "",
        "Each rule has its own sheets (suffix -live / -loose): By asset, By direction, By timeframe,",
        "By month, All trades. Charts: confluence_equity_*, _by_asset_*, _by_month_*.",
    ]})
    with pd.ExcelWriter(ROOT/"logs"/"confluence_backtest.xlsx", engine="openpyxl") as xl:
        comp.to_excel(xl, sheet_name="Compare rules", index=False)
        for label, (d, by_asset, by_side, by_tf, by_month) in results.items():
            sfx = "live" if "LIVE" in label else "loose"
            by_asset.to_excel(xl, sheet_name=f"By asset-{sfx}", index=False)
            by_side.to_excel(xl, sheet_name=f"By direction-{sfx}", index=False)
            by_tf.to_excel(xl, sheet_name=f"By timeframe-{sfx}", index=False)
            by_month.to_excel(xl, sheet_name=f"By month-{sfx}", index=False)
            d.drop(columns=["month"], errors="ignore").to_excel(xl, sheet_name=f"All trades-{sfx}", index=False)
        readme.to_excel(xl, sheet_name="README", index=False)

    print("\n=== COMPARISON ===")
    print(comp.to_string(index=False))
    for label, (d, by_asset, *_ ) in results.items():
        print(f"\n--- {label} by asset ---")
        print(by_asset.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
