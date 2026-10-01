"""Confluence backtest for the validated 10, May 2026 -> today, taken as directed.

Every qualifying confluence SETUP (aligned V5 divergence + DRS-loose any-zone-30d
+ chart-native trend, in the asset's ALLOWED direction) is treated as a trade
taken exactly as the setup directs: enter at the confirming bar's close, SL
1.5xATR, TP 4.0xATR (1:2.67). We then report win/loss for each.

Window: entry_time >= 2026-05-01. Timeframes 1h/2h/3h/4h only -- yfinance serves
~60d of 15m/30m/45m, so those can't reach May (noted, not hidden). $ = static
5% of $1000 = $50 risk/trade. Outputs logs/confluence_since_may.xlsx + equity png.
"""
from __future__ import annotations
import bisect
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
    attach_trade_levels, detect_divergences, drop_incomplete_last_bar,
    fetch_ohlcv, parse_tf_minutes, resample_ohlcv,
)
from src.v5_confluence import drs_signals            # noqa: E402

CFG = yaml.safe_load((ROOT / "config" / "v5_confluence_scanner.yaml").read_text("utf-8"))
DIV = dict(CFG["divergence"]); DIV["aligned_only"] = True
ASSETS = CFG["assets"]
ZONE_DAYS = int(CFG["drs"]["zone_max_days"]); BUF = float(CFG["drs"]["buffer_atr"])
SL_ATR = float(DIV["sl_atr_mult"]); TP_ATR = float(DIV["tp_atr_mult"])
R_WIN, R_LOSS = TP_ATR / SL_ATR, -1.0
RISK_D = 0.05 * 1000.0
MERGE_ATR = 0.75
START = pd.Timestamp("2026-05-01")
# 1h base (730d) + resamples — the TFs that span May->today
TFS = {"1h": (None, 60), "2h": ("2h", 120), "3h": ("3h", 180), "4h": ("4h", 240)}


def build_frames(ticker, anchor, cache, now):
    ck = (ticker, "1h", "730d")
    if ck not in cache:
        cache[ck] = fetch_ohlcv(ticker, "1h", "730d")
    base = cache[ck]
    if base is None or base.empty:
        return {}
    has_vol = ("Volume" in base) and float(np.nansum(base["Volume"].to_numpy())) > 0
    frames = {}
    for tf, (rule, bmin) in TFS.items():
        frame = resample_ohlcv(base, rule, anchor) if rule else base
        frame = drop_incomplete_last_bar(frame, bmin, now)
        if len(frame) >= 220:
            frames[tf] = (frame, has_vol, bmin)
    return frames


def score(frame, i, direction, entry, atrv):
    high = frame["High"].to_numpy(); low = frame["Low"].to_numpy(); close = frame["Close"].to_numpy()
    idx = frame.index; n = len(close)
    if direction == "long":
        sl, tp = entry - SL_ATR * atrv, entry + TP_ATR * atrv
    else:
        sl, tp = entry + SL_ATR * atrv, entry - TP_ATR * atrv
    for j in range(i + 1, n):
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
    mv = (close[-1] - entry) if direction == "long" else (entry - close[-1])
    return "OPEN", mv / (SL_ATR * atrv), idx[-1]


def distinct(reds, atrv):
    if not reds:
        return 0
    tol = MERGE_ATR * atrv; kept = []
    for r in sorted(reds):
        if not kept or abs(r - kept[-1]) > tol:
            kept.append(r)
    return len(kept)


def run(cache, now):
    trades = []
    for asset, spec in ASSETS.items():
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        allowed = [str(x).lower() for x in spec.get("dirs", ["buy", "sell"])]
        frames = build_frames(tk, anchor, cache, now)
        if not frames:
            print(f"{asset:<8} no data"); continue
        drs = {"long": ([], []), "short": ([], [])}
        for tf, (frame, has_vol, _bm) in frames.items():
            lc, sc, atr = drs_signals(frame, has_vol)
            idx = frame.index; low = frame["Low"].to_numpy(); high = frame["High"].to_numpy()
            for i in range(len(frame)):
                if not np.isfinite(atr[i]) or atr[i] <= 0:
                    continue
                if lc[i]:
                    drs["long"][0].append(idx[i]); drs["long"][1].append(low[i] - 1.5 * atr[i])
                if sc[i]:
                    drs["short"][0].append(idx[i]); drs["short"][1].append(high[i] + 1.5 * atr[i])
        for d in ("long", "short"):
            order = np.argsort(drs[d][0])
            drs[d] = ([drs[d][0][k] for k in order], [drs[d][1][k] for k in order])

        for tf, (frame, _hv, bmin) in frames.items():
            sigs = detect_divergences(frame, asset, tk, tf, bmin, DIV)
            sigs = attach_trade_levels(sigs, frame, int(DIV["atr_len"]), SL_ATR, TP_ATR)
            pos = {t: k for k, t in enumerate(frame.index)}
            for s in sigs:
                if s.stop is None or s.atr is None:
                    continue
                direction = "long" if s.direction == "BULL" else "short"
                if ("buy" if direction == "long" else "sell") not in allowed:
                    continue
                entry_t = s.confirm_time + pd.Timedelta(minutes=bmin)
                if entry_t < START:
                    continue
                times, reds = drs[direction]
                k = bisect.bisect_right(times, s.confirm_time) - 1

                def price_ok(rv):
                    return (s.close <= rv + BUF * s.atr) if direction == "long" else (s.close >= rv - BUF * s.atr)

                qual = []; kk = k
                while kk >= 0 and (s.confirm_time - times[kk]) <= pd.Timedelta(days=ZONE_DAYS):
                    if price_ok(reds[kk]):
                        qual.append(reds[kk])
                    kk -= 1
                if not qual:
                    continue
                i = pos[s.confirm_time]
                outc, R, xt = score(frame, i, direction, s.close, s.atr)
                trades.append(dict(
                    asset=asset, tf=tf, side=("BUY" if direction == "long" else "SELL"),
                    entry_time=entry_t, exit_time=xt + pd.Timedelta(minutes=bmin),
                    entry=round(s.close, 6), stop=round(s.stop, 6), target=round(s.target, 6),
                    span_bars=int(s.span), zones=distinct(qual, s.atr),
                    outcome=outc, R=round(R, 3), pnl_usd=round(R * RISK_D, 2)))
        print(f"{asset:<8} {sum(1 for t in trades if t['asset']==asset)} setups since May", flush=True)
    return pd.DataFrame(trades).sort_values("entry_time").reset_index(drop=True) if trades else pd.DataFrame()


def agg(sub, label):
    if sub.empty:
        return dict(group=label, n=0, wins=0, losses=0, open=0, win_pct=np.nan,
                    pf=np.nan, expR=np.nan, total_R=0.0, total_usd=0.0)
    res = sub[sub.outcome != "OPEN"]; R = sub.R.to_numpy()
    pos = R[R > 0].sum(); neg = -R[R < 0].sum()
    pf = pos / neg if neg > 0 else np.inf
    return dict(group=label, n=len(sub), wins=int((sub.outcome == "TP").sum()),
                losses=int((sub.outcome == "SL").sum()), open=int((sub.outcome == "OPEN").sum()),
                win_pct=round(100 * (res.outcome == "TP").mean(), 1) if len(res) else np.nan,
                pf=round(float(pf), 2) if np.isfinite(pf) else np.inf,
                expR=round(float(R.mean()), 3), total_R=round(float(R.sum()), 1),
                total_usd=round(float(sub.pnl_usd.sum()), 2))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    d = run({}, now)
    if d.empty:
        print("no setups since May"); return 0

    overall = pd.DataFrame([agg(d, "ALL setups (May->today)"),
                            agg(d[d.side == "BUY"], "BUY setups"),
                            agg(d[d.side == "SELL"], "SELL setups")])
    by_asset = pd.DataFrame([agg(d[d.asset == a], a) for a in ASSETS
                             if not d[d.asset == a].empty]).sort_values("total_R", ascending=False)
    d["month"] = pd.to_datetime(d.entry_time).dt.strftime("%Y-%m")
    by_month = pd.DataFrame([agg(d[d.month == m], m) for m in sorted(d.month.unique())])

    dd = d.sort_values("exit_time")
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(pd.to_datetime(dd.exit_time), dd.R.cumsum(), color="#2563eb", lw=1.8, marker="o", ms=3)
    ax.axhline(0, color="#9ca3af", lw=.8)
    ax.fill_between(pd.to_datetime(dd.exit_time), dd.R.cumsum(), 0,
                    where=(dd.R.cumsum() >= 0), color="#16a34a", alpha=.12)
    ax.fill_between(pd.to_datetime(dd.exit_time), dd.R.cumsum(), 0,
                    where=(dd.R.cumsum() < 0), color="#dc2626", alpha=.12)
    o = agg(d, "all")
    ax.set_title(f"Confluence setups taken as directed — May->today (n={o['n']}, "
                 f"{o['win_pct']}% win, {o['total_R']:+.1f}R / ${o['total_usd']:+,.0f} @ $50/trade)")
    ax.set_ylabel("Cumulative R"); ax.grid(alpha=.25); fig.tight_layout()
    fig.savefig(ROOT / "logs" / "confluence_since_may_equity.png", dpi=110); plt.close(fig)

    readme = pd.DataFrame({"May->today confluence backtest — read me": [
        "Every row in 'All setups' is a confluence SETUP taken exactly as directed: entered at the",
        "confirming bar's close, in the asset's allowed direction, SL 1.5xATR / TP 4xATR (1:2.67).",
        "outcome TP=win (+2.667R), SL=loss (-1R), OPEN=still running (marked-to-market at last bar).",
        "Window: entry on/after 2026-05-01. Timeframes 1h/2h/3h/4h ONLY -- yfinance serves ~60d of",
        "15m/30m/45m, so those can't reach May and are excluded (the live scanner does use them, so",
        "it fires MORE often than this backtest shows). Direction restrictions per the deployed config",
        "(BTC/NZDJPY/AUDUSD/NAS100/GBPUSD buy; DOGE/XAU/EUR sell; USDJPY/ETH both).",
        "$ = static 5% of $1000 = $50 risk/trade (no compounding). yfinance proxies, not OANDA.",
        "Modest, selection-biased edge -- this is one 4.8-month window; judge it as forward evidence,",
        "not proof. Not financial advice.",
    ]})
    with pd.ExcelWriter(ROOT / "logs" / "confluence_since_may.xlsx", engine="openpyxl") as xl:
        overall.to_excel(xl, sheet_name="Overall", index=False)
        by_asset.to_excel(xl, sheet_name="By asset", index=False)
        by_month.to_excel(xl, sheet_name="By month", index=False)
        d.drop(columns=["month"]).to_excel(xl, sheet_name="All setups (ledger)", index=False)
        readme.to_excel(xl, sheet_name="README", index=False)

    print("\n===== OVERALL (May -> today) =====\n", overall.to_string(index=False))
    print("\n===== BY ASSET =====\n", by_asset.to_string(index=False))
    print("\n===== BY MONTH =====\n", by_month.to_string(index=False))
    print(f"\nTotal setups since May: {len(d)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
