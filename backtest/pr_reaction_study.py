"""How does price REACT at the Predictive-Range edges? Test every interpretation.

For each asset x TF (all 15, 7 TFs, 2y), build the Predictive Range (unit =
6*ATR(200), stepping midline; edges = mid +/- unit) and classify FRESH edge
events, then score each as a trade (entry=event close, SL 1.5xATR / TP 4xATR):

  lower_touch_LONG   : low tags support -> BOUNCE up      (mean-reversion)
  upper_touch_SHORT  : high tags resistance -> BOUNCE down (mean-reversion)
  break_up_LONG      : close breaks above resistance -> CONTINUE up (momentum)
  break_down_SHORT   : close breaks below support -> CONTINUE down (momentum)
  lower_touch_SHORT  : support gives way (opposite of bounce)
  upper_touch_LONG   : resistance gives way (opposite of bounce)

Also a trend-aligned view (200-SMA). Whichever reaction is reliably positive is
the real edge; the rest are the red-team null. Outputs xlsx + charts.
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
from src.v5_divergence import atr_wilder, drop_incomplete_last_bar, fetch_ohlcv, resample_ohlcv  # noqa: E402
from backtest.pr_confluence_backtest import predictive_range, TF_SPEC, TF_MIN  # noqa: E402

ASSETS = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))["assets"]
PR_LEN, PR_MULT = 200, 6.0
SL_ATR, TP_ATR = 1.5, 4.0
R_WIN, R_LOSS = TP_ATR/SL_ATR, -1.0
RISK_D = 50.0
LOOKBACK = pd.Timedelta(days=730)


def score(hi, lo, cl, i, d, entry, a):
    n = len(cl)
    sl = entry-SL_ATR*a if d == "long" else entry+SL_ATR*a
    tp = entry+TP_ATR*a if d == "long" else entry-TP_ATR*a
    for j in range(i+1, n):
        if d == "long":
            if lo[j] <= sl:
                return "SL", R_LOSS
            if hi[j] >= tp:
                return "TP", R_WIN
        else:
            if hi[j] >= sl:
                return "SL", R_LOSS
            if lo[j] <= tp:
                return "TP", R_WIN
    mv = (cl[-1]-entry) if d == "long" else (entry-cl[-1])
    return "OPEN", mv/(SL_ATR*a)


def run():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache = {}; rows = []
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
            hi = frame["High"].to_numpy(); lo = frame["Low"].to_numpy(); cl = frame["Close"].to_numpy()
            idx = frame.index
            mid, up, lw, unit = predictive_range(frame, PR_LEN, PR_MULT)
            atr = atr_wilder(frame, 14)
            for i in range(211, len(frame)-1):
                if not np.isfinite(unit[i]) or unit[i] <= 0 or not np.isfinite(atr[i]) or atr[i] <= 0:
                    continue
                # fresh events
                low_touch = lo[i] <= lw[i] and lo[i-1] > lw[i-1]
                up_touch = hi[i] >= up[i] and hi[i-1] < up[i-1]
                brk_up = cl[i] > up[i] and cl[i-1] <= up[i-1]
                brk_dn = cl[i] < lw[i] and cl[i-1] >= lw[i-1]
                events = []
                if low_touch:
                    events += [("lower_touch_LONG", "long"), ("lower_touch_SHORT", "short")]
                if up_touch:
                    events += [("upper_touch_SHORT", "short"), ("upper_touch_LONG", "long")]
                if brk_up:
                    events += [("break_up_LONG", "long")]
                if brk_dn:
                    events += [("break_down_SHORT", "short")]
                if not events:
                    continue
                entry_t = idx[i] + pd.Timedelta(minutes=TF_MIN[tf])
                if entry_t < now - LOOKBACK:
                    continue
                trend_up = cl[i] > (frame["Close"].rolling(200).mean().to_numpy()[i])
                for sig, d in events:
                    aligned = (d == "long" and trend_up) or (d == "short" and not trend_up)
                    outc, R = score(hi, lo, cl, i, d, cl[i], atr[i])
                    rows.append(dict(signal=sig, asset=asset, tf=tf, dir=d,
                                     aligned=bool(aligned), outcome=outc, R=round(R, 3)))
        print(f"{asset:<8} events={sum(1 for r in rows if r['asset']==asset)}", flush=True)
    return pd.DataFrame(rows)


def agg(sub):
    res = sub[sub.outcome != "OPEN"]
    return dict(n=len(sub), win_pct=round(100*(res.outcome == "TP").mean(), 1) if len(res) else np.nan,
                total_R=round(sub.R.sum(), 1), expR=round(sub.R.mean(), 3))


def main():
    d = run()
    if d.empty:
        print("no events"); return 0
    order = ["lower_touch_LONG", "upper_touch_SHORT", "break_up_LONG", "break_down_SHORT",
             "lower_touch_SHORT", "upper_touch_LONG"]
    by_sig = pd.DataFrame([dict(signal=s, **agg(d[d.signal == s])) for s in order if not d[d.signal == s].empty])
    by_sig_aligned = pd.DataFrame([dict(signal=s+" (trend-aligned)", **agg(d[(d.signal == s) & d.aligned]))
                                   for s in order if not d[(d.signal == s) & d.aligned].empty])
    # best signal per asset (by expR among the 4 primary interpretations)
    prim = d[d.signal.isin(["lower_touch_LONG", "upper_touch_SHORT", "break_up_LONG", "break_down_SHORT"])]
    ba = []
    for a in d.asset.unique():
        for s in order[:4]:
            sub = prim[(prim.asset == a) & (prim.signal == s)]
            if len(sub) >= 8:
                ba.append(dict(asset=a, signal=s, **agg(sub)))
    by_asset = pd.DataFrame(ba).sort_values("expR", ascending=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    cols = ["#16a34a" if v >= 0 else "#dc2626" for v in by_sig.expR]
    ax.bar(by_sig.signal, by_sig.expR, color=cols); ax.axhline(0, color="#111827", lw=0.8)
    for i, (v, n) in enumerate(zip(by_sig.expR, by_sig.n)):
        ax.text(i, v + (0.005 if v >= 0 else -0.012), f"{v:+.3f}\nn={n}", ha="center", fontsize=7)
    ax.set_title("Predictive-Range edge reactions — expectancy (R) by signal (2y, all 15)")
    ax.set_ylabel("Expectancy R/trade"); ax.tick_params(axis="x", rotation=25, labelsize=8)
    ax.grid(axis="y", alpha=0.25); fig.tight_layout()
    fig.savefig(ROOT/"logs"/"pr_reaction_by_signal.png", dpi=110); plt.close(fig)

    with pd.ExcelWriter(ROOT/"logs"/"pr_reaction_study.xlsx", engine="openpyxl") as xl:
        by_sig.to_excel(xl, sheet_name="By signal", index=False)
        by_sig_aligned.to_excel(xl, sheet_name="By signal trend-aligned", index=False)
        by_asset.to_excel(xl, sheet_name="Best per asset", index=False)
    print("\n=== EDGE REACTIONS (all 15, 2y) ===\n", by_sig.to_string(index=False))
    print("\n=== TREND-ALIGNED ===\n", by_sig_aligned.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
