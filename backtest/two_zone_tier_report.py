"""Analysis workbook for the TWO-ZONE DRS TIER (before shipping to the scanner).

Runs the live confluence (aligned V5 + DRS-loose any-zone-30d + trend, SL1.5/TP4)
on the deployed 15m-4h set, tags each trade with how many DISTINCT DRS levels
(merged within 0.75*ATR14) and raw zone EVENTS sat near price, and writes a
full analysis workbook so the tier decision can be reviewed on the evidence:

  Summary        - baseline vs tier ◆/◆◆/◆◆◆ vs gate >=2, with win%, profit
                   factor, expectancy, total R/$, max drawdown, avg win/loss.
  By asset       - tier expectancy per asset.
  By timeframe   - tier expectancy per timeframe.
  All trades     - the complete per-trade ledger (entry/stop/target, span,
                   raw & distinct zone counts, tier, outcome, R, $).
  README         - how to read it + the honest caveats (small n, one regime).

Also logs/two_zone_tier_equity.png (cumulative R: baseline vs >=2 vs rejected).
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
TF_CFG = CFG["timeframes"]; ASSETS = CFG["assets"]
ZONE_DAYS = int(CFG["drs"]["zone_max_days"]); BUF = float(CFG["drs"]["buffer_atr"])
SL_ATR = float(DIV["sl_atr_mult"]); TP_ATR = float(DIV["tp_atr_mult"])
R_WIN, R_LOSS = TP_ATR / SL_ATR, -1.0
RISK_D = 0.05 * 1000.0                    # static 5% of $1000 = $50/trade
LOOKBACK = pd.Timedelta(days=730)
MERGE_ATR = 0.75


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
            continue
        drs = {"long": ([], []), "short": ([], [])}
        for tf, (frame, has_vol) in frames.items():
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

        for tf, (frame, _) in frames.items():
            bmin = parse_tf_minutes(tf)
            sigs = detect_divergences(frame, asset, tk, tf, bmin, DIV)
            sigs = attach_trade_levels(sigs, frame, int(DIV["atr_len"]), SL_ATR, TP_ATR)
            pos = {t: k for k, t in enumerate(frame.index)}
            for s in sigs:
                if s.stop is None or s.atr is None:
                    continue
                direction = "long" if s.direction == "BULL" else "short"
                if ("buy" if direction == "long" else "sell") not in allowed:
                    continue
                times, reds = drs[direction]
                k = bisect.bisect_right(times, s.confirm_time) - 1

                def price_ok(rv):
                    return (s.close <= rv + BUF * s.atr) if direction == "long" else (s.close >= rv - BUF * s.atr)

                qual = []
                kk = k
                while kk >= 0 and (s.confirm_time - times[kk]) <= pd.Timedelta(days=ZONE_DAYS):
                    if price_ok(reds[kk]):
                        qual.append(reds[kk])
                    kk -= 1
                if not qual:
                    continue
                entry_t = s.confirm_time + pd.Timedelta(minutes=bmin)
                if entry_t < now - LOOKBACK:
                    continue
                i = pos[s.confirm_time]
                dz = distinct(qual, s.atr)
                nearest = min(qual, key=lambda r: abs(r - s.close))
                outcome, R, xt = score(frame, i, direction, s.close, s.atr)
                tier = "3+" if dz >= 3 else str(dz)
                trades.append(dict(
                    asset=asset, tf=tf, side=("BUY" if direction == "long" else "SELL"),
                    entry_time=entry_t, exit_time=xt + pd.Timedelta(minutes=bmin),
                    entry=round(s.close, 6), stop=round(s.stop, 6), target=round(s.target, 6),
                    span_bars=int(s.span), raw_zones=len(qual), distinct_zones=dz, tier=tier,
                    nearest_drs=round(float(nearest), 6), outcome=outcome, R=round(R, 3),
                    pnl_usd=round(R * RISK_D, 2)))
        print(f"{asset:<8} {sum(1 for t in trades if t['asset']==asset)} trades", flush=True)
    return pd.DataFrame(trades).sort_values("entry_time").reset_index(drop=True)


def maxdd(sub):
    if sub.empty:
        return 0.0
    cum = sub.sort_values("exit_time").R.cumsum().to_numpy()
    peak = np.maximum.accumulate(cum)
    return round(float((cum - peak).min()), 1)


def agg(sub, label):
    res = sub[sub.outcome != "OPEN"]
    R = sub.R.to_numpy()
    pos = R[R > 0].sum(); neg = -R[R < 0].sum()
    pf = (pos / neg) if neg > 0 else float("inf")
    wins = R[R > 0]; losses = R[R < 0]
    return dict(bucket=label, n=len(sub),
                wins=int((sub.outcome == "TP").sum()), losses=int((sub.outcome == "SL").sum()),
                open=int((sub.outcome == "OPEN").sum()),
                win_pct=round(100 * (res.outcome == "TP").mean(), 1) if len(res) else np.nan,
                profit_factor=round(float(pf), 2) if np.isfinite(pf) else np.inf,
                expR=round(float(R.mean()), 3) if len(sub) else np.nan,
                total_R=round(float(R.sum()), 1), total_usd=round(float(sub.pnl_usd.sum()), 2),
                max_dd_R=maxdd(sub),
                avg_win_R=round(float(wins.mean()), 2) if len(wins) else np.nan,
                avg_loss_R=round(float(losses.mean()), 2) if len(losses) else np.nan)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    d = run({}, now)
    if d.empty:
        print("no trades"); return 0

    summary = pd.DataFrame([
        agg(d, "BASELINE — all confluence (>=1 zone) [LIVE NOW]"),
        agg(d[d.distinct_zones == 1], "Tier ◆  exactly 1 distinct zone"),
        agg(d[d.distinct_zones == 2], "Tier ◆◆ exactly 2 distinct zones"),
        agg(d[d.distinct_zones >= 3], "Tier ◆◆◆ 3+ distinct zones"),
        agg(d[d.distinct_zones >= 2], "GATE >=2 distinct (◆◆ + ◆◆◆) [PROPOSED]"),
        agg(d[d.distinct_zones < 2], "REJECTED by gate (1 zone only)"),
        agg(d[d.raw_zones >= 2], "raw-count gate >=2 events"),
        agg(d[d.raw_zones < 2], "raw-count rejected (1 event)"),
    ])

    # tier x asset (expR + n)
    def pivot(field):
        rows = []
        for a in d.asset.unique():
            sub = d[d.asset == a]
            row = {"asset": a, "n": len(sub), "exp_all": round(sub.R.mean(), 3)}
            for t in ["1", "2", "3+"]:
                ss = sub[sub.tier == t]
                row[f"n_{t}"] = len(ss); row[f"expR_{t}"] = round(ss.R.mean(), 3) if len(ss) else np.nan
            rows.append(row)
        return pd.DataFrame(rows).sort_values("exp_all", ascending=False)
    by_asset = pivot("asset")

    by_tf_rows = []
    for tf in d.tf.unique():
        sub = d[d.tf == tf]
        r = {"tf": tf, "n": len(sub)}
        for t in ["1", "2", "3+"]:
            ss = sub[sub.tier == t]
            r[f"n_{t}"] = len(ss); r[f"expR_{t}"] = round(ss.R.mean(), 3) if len(ss) else np.nan
        by_tf_rows.append(r)
    by_tf = pd.DataFrame(by_tf_rows)

    # equity chart
    fig, ax = plt.subplots(figsize=(11, 5))
    for sub, lab, col in ((d, "baseline all (>=1)", "#2563eb"),
                          (d[d.distinct_zones >= 2], "gate >=2 distinct", "#16a34a"),
                          (d[d.distinct_zones < 2], "rejected (1 zone)", "#dc2626")):
        s = sub.sort_values("exit_time")
        if len(s):
            ax.plot(pd.to_datetime(s.exit_time), s.R.cumsum(),
                    label=f"{lab}  (n={len(s)}, {s.R.sum():+.1f}R, exp {s.R.mean():+.3f})", lw=1.8, color=col)
    ax.axhline(0, color="#9ca3af", lw=.8); ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("Two-zone tier — cumulative R (deployed 15m-4h confluence, 2y)")
    ax.set_ylabel("Cumulative R"); fig.tight_layout()
    fig.savefig(ROOT / "logs" / "two_zone_tier_equity.png", dpi=110); plt.close(fig)

    readme = pd.DataFrame({"Two-zone tier — read me / how to analyse": [
        "WHAT THIS IS: the live confluence (aligned V5 divergence + DRS-loose any-zone-30d + 200-SMA",
        "  trend; exit SL 1.5xATR / TP 4xATR = +2.667R win / -1R loss). Each trade is tagged with how",
        "  many DISTINCT DRS support/resistance levels sat near price (merged within 0.75xATR14) and",
        "  how many raw DRS events. TIER = distinct-zone count (1 / 2 / 3+).",
        "",
        "*** REPLICATION FAILURE -- READ THIS FIRST ***",
        "The two-zone gate DID NOT hold up out-of-sample. Same test, one week apart, fresh yfinance data:",
        "  Tier '2 zones' (n=10):   Sep-17 = +1.200R, 60% win   ->   Sep-24 = -0.267R, 20% win",
        "  Gate >=2 distinct:       Sep-17 = +0.964R            ->   Sep-24 = +0.261R (WORSE than baseline)",
        "  Rejected (1 zone):       Sep-17 = +0.298R            ->   Sep-24 = +0.598R (now the BETTER bucket)",
        "The n=10 tier buckets flipped sign on a trivial data shift. The distinct-count monotonicity",
        "  (1<2<3) is gone. The 'edge' was a small-sample artifact of one 2y window, not a real effect.",
        "",
        "CONCLUSION: DO NOT ship the two-zone gate. On current data it would EMAIL FEWER trades and drop",
        "  the BETTER (1-zone) ones. The only durable piece is the BASELINE confluence itself",
        "  (+0.59R Sep-17 / +0.45R Sep-24, PF ~1.9) -- keep the scanner exactly as it is.",
        "",
        "HOW TO READ 'Summary': compare BASELINE vs GATE>=2 vs REJECTED. If the gate were real, REJECTED",
        "  would be the worse bucket and GATE>=2 would beat BASELINE. Neither is true this week.",
        "",
        "NOTES: ~n=10 per tier bucket; single ~2y window; yfinance proxies (XAUUSD=GC=F etc.), not your",
        "  OANDA feed; in-sample. $ column = static 5% of $1000 = $50/trade. outcome TP=win, SL=loss,",
        "  OPEN=marked-to-market at last bar. Not financial advice.",
    ]})

    with pd.ExcelWriter(ROOT / "logs" / "two_zone_tier_report.xlsx", engine="openpyxl") as xl:
        summary.to_excel(xl, sheet_name="Summary", index=False)
        by_asset.to_excel(xl, sheet_name="By asset x tier", index=False)
        by_tf.to_excel(xl, sheet_name="By timeframe x tier", index=False)
        d.to_excel(xl, sheet_name="All trades", index=False)
        readme.to_excel(xl, sheet_name="README", index=False)

    pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
    print("\n===== SUMMARY =====\n", summary.to_string(index=False))
    print("\n===== BY TIMEFRAME x TIER =====\n", by_tf.to_string(index=False))
    print(f"\nWrote logs/two_zone_tier_report.xlsx  ({len(d)} trades)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
