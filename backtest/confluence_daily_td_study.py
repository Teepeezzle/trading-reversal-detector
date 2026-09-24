"""Backtest the two proposed confluence-scanner extensions BEFORE building:
  (1) a DAILY pass  -> add 1D to the confluence frames; how many signals does it
      add and are they tradeable?
  (2) a TD-EXHAUSTION context tag -> for each confluence trade, is a same-
      direction Daily TD signal (setup-9 or countdown>=13) present within 10 days
      before entry? Does 'tagged' perform differently from 'untagged'? (The tag is
      meant as CONTEXT, not a gate -- this just checks whether it carries info.)

Confluence = aligned V5 divergence + DRS-loose any-zone-30d + trend, SL1.5/TP4.
Run faithfully (config assets/dirs) AND as a fair-sample (8 assets, both dirs)
so the Daily edge isn't judged on a handful of trades. No lookahead; entry at the
confirming bar close. Outputs logs/confluence_daily_td.xlsx.
"""
from __future__ import annotations
import bisect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import (          # noqa: E402
    atr_wilder, attach_trade_levels, detect_divergences, drop_incomplete_last_bar,
    fetch_ohlcv, parse_tf_minutes, resample_ohlcv,
)
from src.v5_confluence import drs_signals            # noqa: E402

CFG = yaml.safe_load((ROOT / "config" / "v5_confluence_scanner.yaml").read_text("utf-8"))
DIV = dict(CFG["divergence"]); DIV["aligned_only"] = True
TF_CFG = CFG["timeframes"]; CFG_ASSETS = CFG["assets"]
ZONE_DAYS = int(CFG["drs"]["zone_max_days"]); BUF = float(CFG["drs"]["buffer_atr"])
SL_ATR = float(DIV["sl_atr_mult"]); TP_ATR = float(DIV["tp_atr_mult"])
R_WIN, R_LOSS = TP_ATR / SL_ATR, -1.0
LOOKBACK = pd.Timedelta(days=730)
MERGE_ATR = 0.75
TD_LOOK, TD_CDMIN, TAG_DAYS = 4, 13, 10

# frames = the scanner's swing TFs + a new Daily pass
TFS = {tf: (str(s["source_interval"]), s.get("resample"), str(s["period"]),
            parse_tf_minutes(tf)) for tf, s in TF_CFG.items()}
TFS["1D"] = ("1d", None, "1500d", 1440)

FAIR_ASSETS = {
    "BTCUSD": ("BTC-USD", "utc", ["buy", "sell"]), "ETHUSD": ("ETH-USD", "utc", ["buy", "sell"]),
    "XAUUSD": ("GC=F", "ny17", ["buy", "sell"]), "NAS100": ("NQ=F", "ny17", ["buy", "sell"]),
    "USDJPY": ("USDJPY=X", "ny17", ["buy", "sell"]), "EURUSD": ("EURUSD=X", "ny17", ["buy", "sell"]),
    "GBPUSD": ("GBPUSD=X", "ny17", ["buy", "sell"]), "AUDUSD": ("AUDUSD=X", "ny17", ["buy", "sell"]),
}


def build_frames(ticker, anchor, cache, now):
    frames = {}
    for tf, (src, rule, per, bmin) in TFS.items():
        ck = (ticker, src, per)
        if ck not in cache:
            cache[ck] = fetch_ohlcv(ticker, src, per)
        base = cache[ck]
        if base is None or base.empty:
            continue
        has_vol = ("Volume" in base) and float(np.nansum(base["Volume"].to_numpy())) > 0
        frame = resample_ohlcv(base, rule, anchor) if rule else base
        frame = drop_incomplete_last_bar(frame, bmin, now)
        if len(frame) >= 220:
            frames[tf] = (frame, has_vol, bmin)
    return frames


def daily_td(frame):
    """Same-direction Daily TD exhaustion times (setup-9 or countdown>=13)."""
    hi = frame["High"].to_numpy(); lo = frame["Low"].to_numpy(); cl = frame["Close"].to_numpy()
    idx = frame.index; n = len(cl)
    bs = ss = bcd = scd = 0; bact = sact = False
    ev = {"long": [], "short": []}
    for i in range(n):
        bs = bs + 1 if (i - TD_LOOK >= 0 and cl[i] < cl[i - TD_LOOK]) else 0
        ss = ss + 1 if (i - TD_LOOK >= 0 and cl[i] > cl[i - TD_LOOK]) else 0
        if bs == 9:
            bact = True; bcd = 0; sact = False; scd = 0; ev["long"].append(idx[i])
        if ss == 9:
            sact = True; scd = 0; bact = False; bcd = 0; ev["short"].append(idx[i])
        if bact and i >= 2 and cl[i] <= lo[i - 2]:
            bcd += 1
            if bcd >= TD_CDMIN:
                ev["long"].append(idx[i])
        if sact and i >= 2 and cl[i] >= hi[i - 2]:
            scd += 1
            if scd >= TD_CDMIN:
                ev["short"].append(idx[i])
    ev["long"].sort(); ev["short"].sort()
    return ev


def tagged(ev_times, entry_t):
    if not ev_times:
        return False
    j = bisect.bisect_right(ev_times, entry_t) - 1
    return j >= 0 and (entry_t - ev_times[j]) <= pd.Timedelta(days=TAG_DAYS)


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


def distinct(reds, atrv):
    if not reds:
        return 0
    tol = MERGE_ATR * atrv; kept = []
    for r in sorted(reds):
        if not kept or abs(r - kept[-1]) > tol:
            kept.append(r)
    return len(kept)


def scan(assets, cache):
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    trades = []
    for asset, (tk, anchor, dirs) in assets.items():
        allowed = [str(x).lower() for x in dirs]
        frames = build_frames(tk, anchor, cache, now)
        if not frames:
            continue
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
        td_ev = daily_td(frames["1D"][0]) if "1D" in frames else {"long": [], "short": []}

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
                if entry_t < now - LOOKBACK and tf != "1D":
                    continue
                i = pos[s.confirm_time]
                outc, R = score(frame, i, direction, s.close, s.atr)
                trades.append(dict(asset=asset, tf=tf, side=("BUY" if direction == "long" else "SELL"),
                                   entry_time=entry_t, zones=distinct(qual, s.atr),
                                   td_tag=tagged(td_ev[direction], entry_t),
                                   outcome=outc, R=round(R, 3)))
    return pd.DataFrame(trades)


def stats(sub, label):
    if isinstance(sub, pd.DataFrame):
        R = sub.R.to_numpy(); res = sub[sub.outcome != "OPEN"]
        win = round(100 * (res.outcome == "TP").mean(), 1) if len(res) else np.nan
    else:
        R = np.asarray(sub, float); win = np.nan
    if len(R) == 0:
        return dict(group=label, n=0, win=np.nan, pf=np.nan, expR=np.nan, totR=0.0)
    pos = R[R > 0].sum(); neg = -R[R < 0].sum()
    pf = pos / neg if neg > 0 else np.inf
    return dict(group=label, n=len(R), win=win, pf=round(float(pf), 2) if np.isfinite(pf) else np.inf,
                expR=round(float(R.mean()), 3), totR=round(float(R.sum()), 1))


def tf_table(d, title):
    rows = []
    for tf in list(TFS):
        sub = d[d.tf == tf]
        if len(sub):
            rows.append(stats(sub, f"{title}: {tf}"))
    rows.append(stats(d[d.tf != "1D"], f"{title}: swing (non-1D)"))
    rows.append(stats(d[d.tf == "1D"], f"{title}: DAILY PASS (1D)"))
    return pd.DataFrame(rows)


def tag_table(d, title):
    return pd.DataFrame([
        stats(d, f"{title}: ALL"),
        stats(d[d.td_tag], f"{title}: TD-tagged"),
        stats(d[~d.td_tag], f"{title}: not tagged"),
        stats(d[(d.tf == "1D")], f"{title}: 1D all"),
        stats(d[(d.tf == "1D") & d.td_tag], f"{title}: 1D TD-tagged"),
    ])


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cache = {}
    faith = scan({a: (v["ticker"], v.get("anchor", "utc"),
                      [str(x).lower() for x in v.get("dirs", ["buy", "sell"])])
                  for a, v in CFG_ASSETS.items()}, cache)
    fair = scan(FAIR_ASSETS, cache)

    f_tf = tf_table(faith, "FAITHFUL")
    f_tag = tag_table(faith, "FAITHFUL")
    s_tf = tf_table(fair, "FAIR")
    s_tag = tag_table(fair, "FAIR")
    daily_by_asset = pd.DataFrame([
        stats(fair[(fair.tf == "1D") & (fair.asset == a)], a) for a in FAIR_ASSETS
    ])

    with pd.ExcelWriter(ROOT / "logs" / "confluence_daily_td.xlsx", engine="openpyxl") as xl:
        f_tf.to_excel(xl, sheet_name="Faithful by TF", index=False)
        f_tag.to_excel(xl, sheet_name="Faithful TD-tag", index=False)
        s_tf.to_excel(xl, sheet_name="Fair-sample by TF", index=False)
        s_tag.to_excel(xl, sheet_name="Fair-sample TD-tag", index=False)
        daily_by_asset.to_excel(xl, sheet_name="Daily pass per asset", index=False)
        faith.sort_values("entry_time").to_excel(xl, sheet_name="Faithful trades", index=False)
        fair.sort_values("entry_time").to_excel(xl, sheet_name="Fair trades", index=False)

    print("\n===== FAITHFUL (your scanner config) — by timeframe =====\n", f_tf.to_string(index=False))
    print("\n===== FAITHFUL — TD-exhaustion tag split =====\n", f_tag.to_string(index=False))
    print("\n===== FAIR-SAMPLE (8 assets, both dirs) — by timeframe =====\n", s_tf.to_string(index=False))
    print("\n===== FAIR-SAMPLE — TD-exhaustion tag split =====\n", s_tag.to_string(index=False))
    print("\n===== DAILY PASS per asset (fair) =====\n", daily_by_asset.to_string(index=False))
    print(f"\nFaithful trades: {len(faith)} | Fair trades: {len(fair)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
