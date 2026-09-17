"""Does a Predictive-Range gate IMPROVE the live V5 CONFLUENCE?

Baseline = the exact live confluence logic (aligned V5 + DRS-loose any-zone-30d
+ trend, exit SL 1.5xATR / TP 4xATR). For every qualifying confluence trade we
also measure WHERE its entry sat in the Predictive-Range channel:

    frac = (close - lower)/(2*unit)   for BUYs  (0 = on support, 1 = on resistance)
    frac = (upper - close)/(2*unit)   for SELLs (0 = on resistance, 1 = on support)

A "PR gate" keeps only trades whose entry is within `thresh` of the favourable
edge (buys near PR support, sells near PR resistance). We evaluate several
thresholds (quarter / third / half of the channel) and, for each, compare:

    BASELINE  : all confluence trades (what runs live now)
    GATED     : confluence trades that PASS the PR gate
    REJECTED  : confluence trades the gate throws away

The gate only earns its place if GATED expectancy beats BASELINE *and* REJECTED
is the worse bucket (i.e. the gate removes losers, not winners). Small-n cuts
are flagged, not celebrated. Outputs logs/confluence_pr_gate.xlsx + chart.
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
from backtest.pr_confluence_backtest import predictive_range  # noqa: E402

CFG = yaml.safe_load((ROOT / "config" / "v5_confluence_scanner.yaml").read_text("utf-8"))
DIV = dict(CFG["divergence"]); DIV["aligned_only"] = True
TF_CFG = CFG["timeframes"]; ASSETS = CFG["assets"]
ZONE_DAYS = int(CFG["drs"]["zone_max_days"]); BUF = float(CFG["drs"]["buffer_atr"])
SL_ATR = float(DIV["sl_atr_mult"]); TP_ATR = float(DIV["tp_atr_mult"])
R_WIN, R_LOSS = TP_ATR / SL_ATR, -1.0
RISK_D = 0.05 * 1000.0                  # static 5% of $1000 = $50/trade
LOOKBACK = pd.Timedelta(days=730)
PR_LEN, PR_MULT = 200, 6.0
THRESHOLDS = [0.25, 0.33, 0.50]         # fraction of the channel from the favourable edge


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
    n = len(close)
    if direction == "long":
        sl, tp = entry - SL_ATR * atrv, entry + TP_ATR * atrv
    else:
        sl, tp = entry + SL_ATR * atrv, entry - TP_ATR * atrv
    for j in range(i + 1, n):
        if direction == "long":
            if low[j] <= sl:
                return "SL", R_LOSS
            if high[j] >= tp:
                return "TP", R_WIN
        else:
            if high[j] >= sl:
                return "SL", R_LOSS
            if low[j] <= tp:
                return "TP", R_WIN
    mv = (close[-1] - entry) if direction == "long" else (entry - close[-1])
    return "OPEN", mv / (SL_ATR * atrv)


def run(cache, now):
    """Exact live confluence (DRS-loose any-zone), tagging each trade with its
    Predictive-Range channel fraction from the favourable edge."""
    trades = []
    for asset, spec in ASSETS.items():
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        allowed = [str(x).lower() for x in spec.get("dirs", ["buy", "sell"])]
        frames = build_frames(tk, anchor, cache, now)
        if not frames:
            continue
        # DRS red zones per direction, sorted by time (any-TF, any-zone)
        drs = {"long": ([], []), "short": ([], [])}
        pr = {}
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
            mid, up, lw, unit = predictive_range(frame, PR_LEN, PR_MULT)
            pr[tf] = (up, lw, unit)
        for d in ("long", "short"):
            order = np.argsort(drs[d][0])
            drs[d] = ([drs[d][0][k] for k in order], [drs[d][1][k] for k in order])

        for tf, (frame, _) in frames.items():
            sigs = detect_divergences(frame, asset, tk, tf, parse_tf_minutes(tf), DIV)
            sigs = attach_trade_levels(sigs, frame, int(DIV["atr_len"]), SL_ATR, TP_ATR)
            pos = {t: k for k, t in enumerate(frame.index)}
            up_a, lw_a, unit_a = pr[tf]
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

                red = None
                while k >= 0 and (s.confirm_time - times[k]) <= pd.Timedelta(days=ZONE_DAYS):
                    if price_ok(reds[k]):
                        red = reds[k]; break
                    k -= 1
                if red is None:
                    continue
                entry_t = s.confirm_time + pd.Timedelta(minutes=parse_tf_minutes(tf))
                if entry_t < now - LOOKBACK:
                    continue
                i = pos[s.confirm_time]
                # PR channel fraction from the favourable edge (needs finite bands)
                u = unit_a[i]; up_v = up_a[i]; lw_v = lw_a[i]
                if not np.isfinite(u) or u <= 0:
                    frac = np.nan
                elif direction == "long":
                    frac = (s.close - lw_v) / (2 * u)     # 0 = on support
                else:
                    frac = (up_v - s.close) / (2 * u)      # 0 = on resistance
                outcome, R = score(frame, i, direction, s.close, s.atr)
                trades.append(dict(
                    asset=asset, tf=tf, side=("BUY" if direction == "long" else "SELL"),
                    entry_time=entry_t, pr_frac=round(float(frac), 4) if np.isfinite(frac) else np.nan,
                    outcome=outcome, R=round(R, 3), pnl_usd=round(R * RISK_D, 2)))
        print(f"{asset:<8} trades={sum(1 for t in trades if t['asset']==asset)}", flush=True)
    return pd.DataFrame(trades)


def agg(sub, label):
    res = sub[sub.outcome != "OPEN"]
    return dict(bucket=label, n=len(sub),
                wins=int((sub.outcome == "TP").sum()), losses=int((sub.outcome == "SL").sum()),
                open=int((sub.outcome == "OPEN").sum()),
                win_pct=round(100 * (res.outcome == "TP").mean(), 1) if len(res) else np.nan,
                total_R=round(sub.R.sum(), 1), total_usd=round(sub.pnl_usd.sum(), 2),
                expR=round(sub.R.mean(), 3) if len(sub) else np.nan)


def main():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    d = run({}, now)
    if d.empty:
        print("no confluence trades"); return 0
    base = agg(d, "BASELINE (all confluence)")
    have_frac = d[d.pr_frac.notna()]

    # Overall gate sweep (buys & sells together, symmetric gate)
    sweep = [base]
    for th in THRESHOLDS:
        gated = have_frac[have_frac.pr_frac <= th]
        rejected = have_frac[have_frac.pr_frac > th]
        sweep.append(agg(gated, f"GATED  frac<={th:.2f}"))
        sweep.append(agg(rejected, f"reject frac>{th:.2f}"))
    sweep_df = pd.DataFrame(sweep)

    # Buys-only view (PR SUPPORT is specifically a buy concept)
    buys = d[d.side == "BUY"]; buys_f = buys[buys.pr_frac.notna()]
    buy_rows = [agg(buys, "BUY baseline")]
    for th in THRESHOLDS:
        buy_rows.append(agg(buys_f[buys_f.pr_frac <= th], f"BUY near support <= {th:.2f}"))
        buy_rows.append(agg(buys_f[buys_f.pr_frac > th], f"BUY away  > {th:.2f}"))
    buys_df = pd.DataFrame(buy_rows)

    # Sells-only view
    sells = d[d.side == "SELL"]; sells_f = sells[sells.pr_frac.notna()]
    sell_rows = [agg(sells, "SELL baseline")]
    for th in THRESHOLDS:
        sell_rows.append(agg(sells_f[sells_f.pr_frac <= th], f"SELL near resistance <= {th:.2f}"))
        sell_rows.append(agg(sells_f[sells_f.pr_frac > th], f"SELL away  > {th:.2f}"))
    sells_df = pd.DataFrame(sell_rows)

    # Chart: expectancy of BASELINE vs GATED vs REJECTED across thresholds
    fig, ax = plt.subplots(figsize=(10, 5))
    xs = [f"{th:.2f}" for th in THRESHOLDS]
    g_exp = [agg(have_frac[have_frac.pr_frac <= th], "g")["expR"] for th in THRESHOLDS]
    r_exp = [agg(have_frac[have_frac.pr_frac > th], "r")["expR"] for th in THRESHOLDS]
    g_n = [int((have_frac.pr_frac <= th).sum()) for th in THRESHOLDS]
    ax.axhline(base["expR"], color="#2563eb", lw=1.8, ls="--", label=f"baseline {base['expR']:+.3f}R (n={base['n']})")
    ax.plot(xs, g_exp, color="#16a34a", lw=2, marker="o", label="GATED (near favourable edge)")
    ax.plot(xs, r_exp, color="#dc2626", lw=2, marker="s", label="REJECTED (away from edge)")
    for x, v, nn in zip(xs, g_exp, g_n):
        ax.text(x, v + 0.03, f"{v:+.3f}\nn={nn}", ha="center", fontsize=8, color="#16a34a")
    ax.axhline(0, color="#9ca3af", lw=0.6)
    ax.set_title("PR gate on live confluence — expectancy vs gate strictness (2y)")
    ax.set_xlabel("gate threshold (fraction of channel from favourable edge; smaller = stricter)")
    ax.set_ylabel("Expectancy R/trade"); ax.grid(alpha=0.25); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(ROOT / "logs" / "confluence_pr_gate.png", dpi=110); plt.close(fig)

    readme = pd.DataFrame({"PR gate on confluence — read me": [
        "Baseline = the LIVE confluence (aligned V5 + DRS-loose any-zone-30d + trend; SL1.5/TP4).",
        "pr_frac = where the entry sat in its Predictive-Range channel, measured from the",
        "  FAVOURABLE edge: BUY 0=on PR support .. 1=on PR resistance; SELL 0=on resistance .. 1=on support.",
        "GATED frac<=t keeps only entries within fraction t of that favourable edge (buys near PR",
        "  support, sells near PR resistance). REJECTED = the complement the gate would drop.",
        "The gate is only worth adding if GATED expR > BASELINE expR AND REJECTED is the worse bucket",
        "  (gate removes losers). Watch n: a stricter gate that 'improves' expR on a tiny n is noise.",
        "$ = static 5% of $1000 = $50/trade. Window last 730d by entry. yfinance proxies, not OANDA.",
    ]})
    with pd.ExcelWriter(ROOT / "logs" / "confluence_pr_gate.xlsx", engine="openpyxl") as xl:
        sweep_df.to_excel(xl, sheet_name="Gate sweep (all)", index=False)
        buys_df.to_excel(xl, sheet_name="Buys (PR support)", index=False)
        sells_df.to_excel(xl, sheet_name="Sells (PR resistance)", index=False)
        d.sort_values("entry_time").to_excel(xl, sheet_name="All trades", index=False)
        readme.to_excel(xl, sheet_name="README", index=False)

    print("\n=== GATE SWEEP (all confluence, symmetric PR gate) ===")
    print(sweep_df.to_string(index=False))
    print("\n=== BUYS (near PR support) ===")
    print(buys_df.to_string(index=False))
    print("\n=== SELLS (near PR resistance) ===")
    print(sells_df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
