"""Test the user's hypothesis on the V5 Swing+MACD divergence VISUALIZER:

  "Divergences are more profitable when run (HH/LL) is EVEN, span is EVEN,
   and span > run."   i.e.  (run%2==0) and (span%2==0) and (span>run)

Faithful reconstruction of the Pine logic (leftBars=5, rightBars=rb; a bear div
= price higher-high + MACD lower-high; run = consecutive HH/LL pivot count;
span = bars between the two pivots). NO lookahead: entry is the CLOSE of the bar
that CONFIRMS the pivot (pivot bar + rightBars). Daily-200-SMA trend alignment
is built from COMPLETED prior-day values only (no lookahead_on).

Exit: ATR(14) stops, SL 1.5x / TP 4x (conservative SL-first on ambiguous bars).
Costs: 0.05% commission/side + ~1 tick slippage, converted to R via the stop.

Outputs logs/divergence_parity.xlsx (+ equity chart). Metrics per group:
trades, win%, profit factor, avg R, max drawdown (R), per-trade Sharpe.
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
    atr_wilder, fetch_ohlcv, resample_ohlcv, drop_incomplete_last_bar, parse_tf_minutes,
)

ASSETS = {
    "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD", "XAUUSD": "GC=F", "NAS100": "NQ=F",
    "USDJPY": "USDJPY=X", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "AUDUSD": "AUDUSD=X",
}
ANCHOR = {"BTCUSD": "utc", "ETHUSD": "utc"}   # rest default ny17
# tf -> (source_interval, resample_rule, period)
TFS = {
    "1h": ("1h", None, "730d"),
    "4h": ("1h", "4h", "730d"),
    "1D": ("1d", None, "1500d"),
}
LEFT = 5
RBARS = [1, 2, 3]
FAST, SLOW, SIG = 12, 26, 9
SL_ATR, TP_ATR = 1.5, 4.0
R_WIN, R_LOSS = TP_ATR / SL_ATR, -1.0
COST_FRAC = 0.0005 * 2 + 0.0001 * 2      # 0.05%/side commission + ~1bp slippage/side
SEC_PER_YEAR = 365.25 * 24 * 3600


def ema(a, n):
    k = 2.0 / (n + 1)
    o = np.full(len(a), np.nan)
    p = None
    for i, v in enumerate(a):
        if not np.isfinite(v):
            continue
        p = v if p is None else v * k + p * (1 - k)
        o[i] = p
    return o


def macd_line(c):
    return ema(c, FAST) - ema(c, SLOW)


def pivots(arr, left, right, kind):
    """Strict Pine-style pivots. Returns list of (center_index) that are pivots."""
    n = len(arr)
    out = []
    for i in range(left, n - right):
        v = arr[i]
        ok = True
        for k in range(1, left + 1):
            if kind == "high" and not (v > arr[i - k]):
                ok = False; break
            if kind == "low" and not (v < arr[i - k]):
                ok = False; break
        if not ok:
            continue
        for k in range(1, right + 1):
            if kind == "high" and not (v > arr[i + k]):
                ok = False; break
            if kind == "low" and not (v < arr[i + k]):
                ok = False; break
        if ok:
            out.append(i)
    return out


def build_daily_trend(ticker):
    """Prior-completed-day close & 200-SMA, indexed by date (no lookahead)."""
    d = fetch_ohlcv(ticker, "1d", "1500d")
    if d is None or d.empty:
        return None
    c = d["Close"]
    sma = c.rolling(200).mean()
    df = pd.DataFrame({"c": c.shift(1), "sma": sma.shift(1)})   # prior completed day
    df.index = pd.to_datetime(df.index).normalize()
    return df


def trend_at(daily, ts):
    if daily is None:
        return None
    day = pd.Timestamp(ts).normalize()
    pos = daily.index.searchsorted(day, side="right") - 1
    if pos < 0:
        return None
    row = daily.iloc[pos]
    if not np.isfinite(row["c"]) or not np.isfinite(row["sma"]):
        return None
    return 1 if row["c"] > row["sma"] else -1   # +1 uptrend, -1 downtrend


def sim(hi, lo, cl, i, direction, entry, atrv):
    n = len(cl)
    if direction == "long":
        sl, tp = entry - SL_ATR * atrv, entry + TP_ATR * atrv
    else:
        sl, tp = entry + SL_ATR * atrv, entry - TP_ATR * atrv
    for j in range(i + 1, n):
        if direction == "long":
            if lo[j] <= sl:
                return "SL", R_LOSS, j
            if hi[j] >= tp:
                return "TP", R_WIN, j
        else:
            if hi[j] >= sl:
                return "SL", R_LOSS, j
            if lo[j] <= tp:
                return "TP", R_WIN, j
    mv = (cl[-1] - entry) if direction == "long" else (entry - cl[-1])
    return "OPEN", mv / (SL_ATR * atrv), n - 1


def scan(asset, ticker, tf, spec, rb, daily, cache):
    src, rule, per = spec
    ck = (ticker, src, per)
    if ck not in cache:
        cache[ck] = fetch_ohlcv(ticker, src, per)
    base = cache[ck]
    if base is None or base.empty:
        return []
    frame = resample_ohlcv(base, rule, ANCHOR.get(asset, "ny17")) if rule else base
    frame = drop_incomplete_last_bar(frame, parse_tf_minutes(tf) if tf != "1D" else 1440,
                                     pd.Timestamp.now(tz="UTC").tz_localize(None))
    if len(frame) < 260:
        return []
    hi = frame["High"].to_numpy(); lo = frame["Low"].to_numpy(); cl = frame["Close"].to_numpy()
    idx = frame.index
    macd = macd_line(cl)
    atr = atr_wilder(frame, 14)
    ph = set(pivots(hi, LEFT, rb, "high"))
    pl = set(pivots(lo, LEFT, rb, "low"))
    trades = []
    lastPH = None; hhRun = 0
    lastPL = None; llRun = 0
    n = len(frame)
    for i in range(n):
        # bearish (price higher-high, macd lower-high)
        if i in ph:
            price = hi[i]; m = macd[i]
            if lastPH is not None:
                higher = price > lastPH[0]
                hhRun = hhRun + 1 if higher else 1
                span = i - lastPH[2]
                if higher and m < lastPH[1]:
                    ci = i + rb                      # confirm bar
                    if ci < n and np.isfinite(atr[ci]) and atr[ci] > 0:
                        tr = trend_at(daily, idx[ci])
                        aligned = (tr == -1)
                        outc, R, xj = sim(hi, lo, cl, ci, "short", cl[ci], atr[ci])
                        costR = COST_FRAC * cl[ci] / (SL_ATR * atr[ci])
                        trades.append(dict(asset=asset, tf=tf, rb=rb, dir="short",
                            run=hhRun, span=span, aligned=aligned,
                            entry_time=idx[ci], exit_time=idx[xj], outcome=outc,
                            R=round(R - costR, 4)))
            else:
                hhRun = 1
            lastPH = (price, m, i)
        # bullish (price lower-low, macd higher-low)
        if i in pl:
            price = lo[i]; m = macd[i]
            if lastPL is not None:
                lower = price < lastPL[0]
                llRun = llRun + 1 if lower else 1
                span = i - lastPL[2]
                if lower and m > lastPL[1]:
                    ci = i + rb
                    if ci < n and np.isfinite(atr[ci]) and atr[ci] > 0:
                        tr = trend_at(daily, idx[ci])
                        aligned = (tr == 1)
                        outc, R, xj = sim(hi, lo, cl, ci, "long", cl[ci], atr[ci])
                        costR = COST_FRAC * cl[ci] / (SL_ATR * atr[ci])
                        trades.append(dict(asset=asset, tf=tf, rb=rb, dir="long",
                            run=llRun, span=span, aligned=aligned,
                            entry_time=idx[ci], exit_time=idx[xj], outcome=outc,
                            R=round(R - costR, 4)))
            else:
                llRun = 1
            lastPL = (price, m, i)
    return trades


def metrics(df):
    if df.empty:
        return dict(n=0, win=np.nan, pf=np.nan, avgR=np.nan, maxDD=np.nan, sharpe=np.nan, totR=0.0)
    closed = df[df.outcome != "OPEN"]
    wins = (closed.outcome == "TP").sum()
    R = df.R.to_numpy()
    pos = R[R > 0].sum(); neg = -R[R < 0].sum()
    pf = pos / neg if neg > 0 else np.inf
    d = df.sort_values("exit_time")
    cum = d.R.cumsum().to_numpy()
    peak = np.maximum.accumulate(cum)
    maxdd = float((cum - peak).min()) if len(cum) else 0.0
    sharpe = float(R.mean() / R.std(ddof=1)) if len(R) > 1 and R.std(ddof=1) > 0 else np.nan
    return dict(n=len(df), win=round(100 * wins / len(closed), 1) if len(closed) else np.nan,
                pf=round(float(pf), 2) if np.isfinite(pf) else np.inf,
                avgR=round(float(R.mean()), 3), maxDD=round(maxdd, 1),
                sharpe=round(sharpe, 3) if np.isfinite(sharpe) else np.nan,
                totR=round(float(R.sum()), 1))


def row(label, df):
    return dict(group=label, **metrics(df))


def main():
    cache = {}
    daily_cache = {}
    all_trades = []
    for asset, ticker in ASSETS.items():
        if ticker not in daily_cache:
            daily_cache[ticker] = build_daily_trend(ticker)
        daily = daily_cache[ticker]
        for tf, spec in TFS.items():
            for rb in RBARS:
                t = scan(asset, ticker, tf, spec, rb, daily, cache)
                all_trades.extend(t)
            print(f"{asset:<7} {tf:<3} done ({sum(1 for x in all_trades if x['asset']==asset and x['tf']==tf)} trades over rb)", flush=True)
    d = pd.DataFrame(all_trades)
    if d.empty:
        print("no trades"); return 0
    d["run_even"] = d.run % 2 == 0
    d["span_even"] = d.span % 2 == 0
    d["hypo"] = d.run_even & d.span_even & (d.span > d.run)

    # ---- primary hypothesis test (rb=2, the script default) ----
    base_rb = d[d.rb == 2]
    H = base_rb[base_rb.hypo]
    NOTH = base_rb[~base_rb.hypo]
    hypo_tbl = pd.DataFrame([
        row("ALL divergences (rb=2)", base_rb),
        row("HYPOTHESIS even/even/span>run", H),
        row("Everything else (baseline)", NOTH),
        row("  run EVEN only", base_rb[base_rb.run_even]),
        row("  run ODD only", base_rb[~base_rb.run_even]),
        row("  span EVEN only", base_rb[base_rb.span_even]),
        row("  span ODD only", base_rb[~base_rb.span_even]),
        row("  span>run only", base_rb[base_rb.span > base_rb.run]),
        row("HYPO + trend-aligned", H[H.aligned]),
        row("HYPO + counter-trend", H[~H.aligned]),
    ])

    # ---- hypothesis per timeframe (robustness) ----
    per_tf = []
    for tf in TFS:
        sub = base_rb[base_rb.tf == tf]
        per_tf.append(row(f"{tf}  HYPO", sub[sub.hypo]))
        per_tf.append(row(f"{tf}  rest", sub[~sub.hypo]))
    per_tf_tbl = pd.DataFrame(per_tf)

    # ---- hypothesis per asset ----
    per_asset = []
    for a in ASSETS:
        sub = base_rb[base_rb.asset == a]
        per_asset.append(dict(asset=a, **{f"hypo_{k}": v for k, v in metrics(sub[sub.hypo]).items() if k in ("n", "avgR", "pf", "win")},
                              **{f"rest_{k}": v for k, v in metrics(sub[~sub.hypo]).items() if k in ("n", "avgR", "pf", "win")}))
    per_asset_tbl = pd.DataFrame(per_asset)

    # ---- grid: run (2..10) x span-bucket ----
    buckets = [("3-9", 3, 9), ("10-19", 10, 19), ("20-29", 20, 29), ("30-50", 30, 50)]
    grid = []
    for rn in range(2, 11):
        r = {"run": rn}
        sub_r = base_rb[base_rb.run == rn]
        for name, lo_, hi_ in buckets:
            sub = sub_r[(sub_r.span >= lo_) & (sub_r.span <= hi_)]
            m = metrics(sub)
            r[f"{name}_n"] = m["n"]; r[f"{name}_avgR"] = m["avgR"]
        grid.append(r)
    grid_tbl = pd.DataFrame(grid)

    # ---- parity grid: run parity x span parity ----
    parity = []
    for re_ in (True, False):
        for se_ in (True, False):
            sub = base_rb[(base_rb.run_even == re_) & (base_rb.span_even == se_)]
            parity.append(dict(run=("even" if re_ else "odd"), span=("even" if se_ else "odd"), **metrics(sub)))
    parity_tbl = pd.DataFrame(parity)

    # ---- rightBars comparison (hypo) ----
    rbtbl = []
    for rb in RBARS:
        sub = d[d.rb == rb]
        rbtbl.append(row(f"rb={rb} HYPO", sub[sub.hypo]))
        rbtbl.append(row(f"rb={rb} rest", sub[~sub.hypo]))
    rb_tbl = pd.DataFrame(rbtbl)

    # ---- aligned vs unaligned (all rb=2) ----
    al_tbl = pd.DataFrame([
        row("aligned (all)", base_rb[base_rb.aligned]),
        row("counter-trend (all)", base_rb[~base_rb.aligned]),
    ])

    # ---- equity chart: hypo vs baseline (rb=2) ----
    fig, ax = plt.subplots(figsize=(11, 5))
    for sub, lab, col in ((H, "HYPOTHESIS even/even", "#16a34a"), (NOTH, "baseline (rest)", "#dc2626"),
                          (base_rb, "all divergences", "#2563eb")):
        s = sub.sort_values("exit_time")
        if len(s):
            ax.plot(pd.to_datetime(s.exit_time), s.R.cumsum(), label=f"{lab} (n={len(s)}, {s.R.sum():+.1f}R)", lw=1.6)
    ax.axhline(0, color="#9ca3af", lw=.8); ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("Even-run/even-span hypothesis vs baseline — cumulative R (rb=2, 8 assets, 1h/4h/1D)")
    ax.set_ylabel("Cumulative R"); fig.tight_layout()
    fig.savefig(ROOT / "logs" / "divergence_parity_equity.png", dpi=110); plt.close(fig)

    with pd.ExcelWriter(ROOT / "logs" / "divergence_parity.xlsx", engine="openpyxl") as xl:
        hypo_tbl.to_excel(xl, sheet_name="Hypothesis test", index=False)
        parity_tbl.to_excel(xl, sheet_name="Parity grid", index=False)
        per_tf_tbl.to_excel(xl, sheet_name="Per timeframe", index=False)
        per_asset_tbl.to_excel(xl, sheet_name="Per asset", index=False)
        grid_tbl.to_excel(xl, sheet_name="Run x Span grid", index=False)
        rb_tbl.to_excel(xl, sheet_name="rightBars", index=False)
        al_tbl.to_excel(xl, sheet_name="Alignment", index=False)
        d.drop(columns=["run_even", "span_even"]).to_excel(xl, sheet_name="All trades", index=False)

    pd.set_option("display.width", 160); pd.set_option("display.max_columns", 20)
    print("\n===== HYPOTHESIS TEST (rb=2) =====\n", hypo_tbl.to_string(index=False))
    print("\n===== PARITY GRID =====\n", parity_tbl.to_string(index=False))
    print("\n===== PER TIMEFRAME =====\n", per_tf_tbl.to_string(index=False))
    print("\n===== RUN x SPAN grid (avg R) =====\n", grid_tbl.to_string(index=False))
    print("\n===== rightBars =====\n", rb_tbl.to_string(index=False))
    print("\n===== ALIGNED vs COUNTER =====\n", al_tbl.to_string(index=False))
    print(f"\nTotal divergence trades (all rb/tf/asset): {len(d)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
