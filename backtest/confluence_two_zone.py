"""Does requiring TWO same-direction DRS zones improve the live V5 CONFLUENCE?

Baseline = the live confluence (aligned V5 + DRS-loose any-zone-30d + trend,
SL1.5/TP4): a trade qualifies if AT LEAST ONE same-direction DRS red within 30d
sits at/near price. Here we count HOW MANY qualifying zones each trade had and
test a stronger rule: require a CLUSTER of >=2 (or >=3) same-direction DRS reds
near price -- the idea being that two levels agreeing is a stronger zone than one.

Two counts per trade (both reported, because raw event-count can double-count one
level re-firing on a single TF):
  raw_qual      = number of same-dir DRS red events in 30d that satisfy price_ok
  distinct_qual = those reds merged into distinct price levels (within 0.75*ATR)

For each rule we compare GATED (n_zones >= k) vs REJECTED (n_zones < k). The gate
only earns its place if GATED expR beats BASELINE while keeping a usable sample
AND the rejected bucket is the worse one (gate removes losers, not winners).
Outputs logs/confluence_two_zone.xlsx + chart.
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
RISK_D = 0.05 * 1000.0                   # static 5% of $1000 = $50/trade
LOOKBACK = pd.Timedelta(days=730)
MERGE_ATR = 0.75                         # reds within this many ATR are the "same" level


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


def distinct_levels(reds, atrv):
    """Collapse reds within MERGE_ATR*ATR of each other into distinct levels."""
    if not reds:
        return 0
    tol = MERGE_ATR * atrv
    kept = []
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
            sigs = detect_divergences(frame, asset, tk, tf, parse_tf_minutes(tf), DIV)
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

                # collect ALL qualifying reds in the 30d window (don't stop at first)
                qual = []
                kk = k
                while kk >= 0 and (s.confirm_time - times[kk]) <= pd.Timedelta(days=ZONE_DAYS):
                    if price_ok(reds[kk]):
                        qual.append(reds[kk])
                    kk -= 1
                if not qual:                      # baseline = live rule (>=1 qualifying zone)
                    continue
                entry_t = s.confirm_time + pd.Timedelta(minutes=parse_tf_minutes(tf))
                if entry_t < now - LOOKBACK:
                    continue
                i = pos[s.confirm_time]
                outcome, R = score(frame, i, direction, s.close, s.atr)
                trades.append(dict(
                    asset=asset, tf=tf, side=("BUY" if direction == "long" else "SELL"),
                    entry_time=entry_t, raw_qual=len(qual),
                    distinct_qual=distinct_levels(qual, s.atr),
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


def sweep(d, col, tag):
    rows = [agg(d, f"BASELINE (>=1, all)")]
    for k in (2, 3):
        rows.append(agg(d[d[col] >= k], f"{tag} >= {k}"))
        rows.append(agg(d[d[col] < k], f"{tag} < {k} (rejected)"))
    return pd.DataFrame(rows)


def main():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    d = run({}, now)
    if d.empty:
        print("no confluence trades"); return 0

    raw_sweep = sweep(d, "raw_qual", "raw zones")
    dist_sweep = sweep(d, "distinct_qual", "distinct levels")
    # distribution of how many zones trades actually had
    dist_counts = (d.groupby("distinct_qual")
                   .apply(lambda g: pd.Series(dict(n=len(g),
                          win_pct=round(100 * (g[g.outcome != "OPEN"].outcome == "TP").mean(), 1)
                          if (g.outcome != "OPEN").any() else np.nan,
                          expR=round(g.R.mean(), 3), total_R=round(g.R.sum(), 1))))
                   .reset_index().rename(columns={"distinct_qual": "distinct_levels"}))

    base = agg(d, "base")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axhline(base["expR"], color="#2563eb", lw=1.8, ls="--",
               label=f"baseline >=1 zone: {base['expR']:+.3f}R (n={base['n']})")
    for col, color, mark, name in (("raw_qual", "#16a34a", "o", "raw zone count"),
                                   ("distinct_qual", "#f59e0b", "s", "distinct levels")):
        xs, ys, ns = [], [], []
        for k in (2, 3):
            sub = d[d[col] >= k]
            xs.append(f">={k}"); ys.append(sub.R.mean() if len(sub) else np.nan); ns.append(len(sub))
        ax.plot(xs, ys, color=color, lw=2, marker=mark, label=name)
        for x, y, nn in zip(xs, ys, ns):
            if np.isfinite(y):
                ax.text(x, y + 0.03, f"{y:+.3f}\nn={nn}", ha="center", fontsize=8, color=color)
    ax.axhline(0, color="#9ca3af", lw=0.6)
    ax.set_title("Require N same-direction DRS zones — confluence expectancy (2y)")
    ax.set_xlabel("minimum same-direction DRS zones near price"); ax.set_ylabel("Expectancy R/trade")
    ax.grid(alpha=0.25); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(ROOT / "logs" / "confluence_two_zone.png", dpi=110); plt.close(fig)

    readme = pd.DataFrame({"Two-zone gate — read me": [
        "Baseline = live confluence (aligned V5 + DRS-loose any-zone-30d + trend; SL1.5/TP4):",
        "  qualifies on >=1 same-direction DRS red near price within 30 days.",
        "raw_qual = count of qualifying DRS red EVENTS in the window (can double-count one level",
        "  re-firing on a single TF). distinct_qual = those reds merged into distinct price levels",
        f"  (within {MERGE_ATR}*ATR) -- the honest 'independent zones agreeing' count.",
        "Gate keeps trades with n_zones >= k; REJECTED = the complement (n_zones < k).",
        "Worth adding only if GATED expR > baseline AND rejected bucket is worse, on a usable n.",
        "$ = static 5% of $1000 = $50/trade. Window last 730d by entry. yfinance proxies, not OANDA.",
    ]})
    with pd.ExcelWriter(ROOT / "logs" / "confluence_two_zone.xlsx", engine="openpyxl") as xl:
        raw_sweep.to_excel(xl, sheet_name="Raw zone-count gate", index=False)
        dist_sweep.to_excel(xl, sheet_name="Distinct-level gate", index=False)
        dist_counts.to_excel(xl, sheet_name="By distinct-level count", index=False)
        d.sort_values("entry_time").to_excel(xl, sheet_name="All trades", index=False)
        readme.to_excel(xl, sheet_name="README", index=False)

    print("\n=== RAW ZONE-COUNT GATE ===")
    print(raw_sweep.to_string(index=False))
    print("\n=== DISTINCT-LEVEL GATE ===")
    print(dist_sweep.to_string(index=False))
    print("\n=== TRADES BY DISTINCT-LEVEL COUNT ===")
    print(dist_counts.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
