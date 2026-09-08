"""Backtest: TD (setup-9 AND countdown-13) at a Predictive-Range edge.

TD implemented PROPERLY (the countdown in the user's Pine is broken):
  * BUY setup   = 9 consecutive closes < close[4].
  * BUY countdown starts after setup-9, counts bars where close <= low[2],
    completing at 13 (cancelled if an opposite setup-9 forms first).
  * mirror for sells (close > close[4]; countdown close >= high[2]).

Signals tested AT a Predictive-Range edge (buy@support / sell@resistance):
  * SETUP    = setup-9 completion at the edge.
  * COUNTDOWN = countdown-13 completion at the edge (the ask; rarer/stronger).
Exit SL 1.5xATR / TP 4.0xATR (+2.667R / -1R). $ = static $50/trade.
All 15 assets x 7 TFs (15m-4h), last 730d by entry. Proxies, not OANDA.
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
from backtest.pr_confluence_backtest import predictive_range, score, agg, TF_SPEC, TF_MIN  # noqa: E402

ASSETS = yaml.safe_load((ROOT/"config"/"v5_scanner.yaml").read_text("utf-8"))["assets"]
PR_LEN, PR_MULT, EDGE_BUF = 200, 6.0, 0.25
ATR_LEN = 14
RISK_D = 50.0
LOOKBACK = pd.Timedelta(days=730)


def td_full(close, high, low):
    """Return dict of bar-index lists: setup buy/sell (==9), countdown buy/sell (==13)."""
    n = len(close)
    bs = ss = bcd = scd = 0
    b_active = s_active = False
    out = {"setup_buy": [], "setup_sell": [], "cd_buy": [], "cd_sell": []}
    for i in range(n):
        bs = bs + 1 if (i >= 4 and close[i] < close[i-4]) else 0
        ss = ss + 1 if (i >= 4 and close[i] > close[i-4]) else 0
        if bs == 9:
            out["setup_buy"].append(i); b_active = True; bcd = 0; s_active = False; scd = 0
        if ss == 9:
            out["setup_sell"].append(i); s_active = True; scd = 0; b_active = False; bcd = 0
        if b_active and i >= 2 and close[i] <= low[i-2]:
            bcd += 1
            if bcd == 13:
                out["cd_buy"].append(i); b_active = False; bcd = 0
        if s_active and i >= 2 and close[i] >= high[i-2]:
            scd += 1
            if scd == 13:
                out["cd_sell"].append(i); s_active = False; scd = 0
    return out


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
            close = frame["Close"].to_numpy(); high = frame["High"].to_numpy(); low = frame["Low"].to_numpy()
            mid, upper, lower, unit = predictive_range(frame, PR_LEN, PR_MULT)
            atr14 = atr_wilder(frame, ATR_LEN)
            sma = frame["Close"].rolling(200).mean().to_numpy()
            td = td_full(close, high, low)
            groups = [("SETUP", "long", td["setup_buy"]), ("SETUP", "short", td["setup_sell"]),
                      ("COUNTDOWN", "long", td["cd_buy"]), ("COUNTDOWN", "short", td["cd_sell"])]
            for sigtype, direction, bars in groups:
                for c in bars:
                    if c <= 210 or not np.isfinite(unit[c]) or unit[c] <= 0 or not np.isfinite(atr14[c]) or atr14[c] <= 0:
                        continue
                    at_edge = (close[c] <= lower[c] + EDGE_BUF*unit[c]) if direction == "long" else (close[c] >= upper[c] - EDGE_BUF*unit[c])
                    if not at_edge:
                        continue
                    entry_t = frame.index[c] + pd.Timedelta(minutes=TF_MIN[tf])
                    if entry_t < now - LOOKBACK:
                        continue
                    trend_ok = np.isfinite(sma[c]) and ((direction == "long" and close[c] > sma[c]) or (direction == "short" and close[c] < sma[c]))
                    outcome, R, xt = score(frame, c, direction, close[c], atr14[c])
                    trades.append(dict(sigtype=sigtype, asset=asset, tf=tf,
                                       side=("BUY" if direction == "long" else "SELL"),
                                       trend_ok=bool(trend_ok),
                                       entry_time=entry_t, exit_time=xt + pd.Timedelta(minutes=TF_MIN[tf]),
                                       entry=round(close[c], 6),
                                       pr_edge=round(lower[c] if direction == "long" else upper[c], 6),
                                       outcome=outcome, R=round(R, 3), pnl_usd=round(R*RISK_D, 2)))
        print(f"{asset:<8} setup={sum(1 for t in trades if t['asset']==asset and t['sigtype']=='SETUP')} "
              f"countdown={sum(1 for t in trades if t['asset']==asset and t['sigtype']=='COUNTDOWN')}", flush=True)
    return pd.DataFrame(trades).sort_values("exit_time").reset_index(drop=True) if trades else pd.DataFrame(), now


def equity_chart(d, sigtype):
    dd = d[d.sigtype == sigtype].sort_values("exit_time").copy()
    if dd.empty:
        return
    dd["cum_R"] = dd.R.cumsum()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(pd.to_datetime(dd.exit_time), dd.cum_R, color="#7c3aed", lw=1.8, marker="o", ms=3)
    ax.axhline(0, color="#9ca3af", lw=0.8)
    ax.fill_between(pd.to_datetime(dd.exit_time), dd.cum_R, 0, where=(dd.cum_R >= 0), color="#16a34a", alpha=0.12)
    ax.fill_between(pd.to_datetime(dd.exit_time), dd.cum_R, 0, where=(dd.cum_R < 0), color="#dc2626", alpha=0.12)
    ax.set_title(f"PR + TD {sigtype} at edge — cumulative R (2y, n={len(dd)}, final {dd.cum_R.iloc[-1]:+.1f}R)")
    ax.set_ylabel("Cumulative R"); ax.grid(alpha=0.25); fig.tight_layout()
    fig.savefig(ROOT/"logs"/f"pr_td_{sigtype.lower()}_equity.png", dpi=110); plt.close(fig)


def main():
    d, now = run()
    if d.empty:
        print("No trades."); return 0
    rows = []
    for st in ["SETUP", "COUNTDOWN"]:
        s = d[d.sigtype == st]
        rows.append(dict(signal=st + " (all)", **agg(s)))
        rows.append(dict(signal=st + " BUY", **agg(s[s.side == "BUY"])))
        rows.append(dict(signal=st + " SELL", **agg(s[s.side == "SELL"])))
        rows.append(dict(signal=st + " trend-aligned", **agg(s[s.trend_ok])))
    compare = pd.DataFrame(rows)
    for st in ["SETUP", "COUNTDOWN"]:
        equity_chart(d, st)

    def by(col):
        return pd.DataFrame([dict(**{col: v, "sigtype": st}, **agg(d[(d[col] == v) & (d.sigtype == st)]))
                             for st in ["SETUP", "COUNTDOWN"] for v in d[d.sigtype == st][col].unique()])
    by_asset = by("asset").sort_values(["sigtype", "total_R"], ascending=[True, False])
    with pd.ExcelWriter(ROOT/"logs"/"pr_td_backtest.xlsx", engine="openpyxl") as xl:
        compare.to_excel(xl, sheet_name="Setup vs Countdown", index=False)
        by_asset.to_excel(xl, sheet_name="By asset", index=False)
        d.to_excel(xl, sheet_name="All trades", index=False)
    print("\nSETUP vs COUNTDOWN:\n", compare.to_string(index=False))
    print("\nBY ASSET:\n", by_asset.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
