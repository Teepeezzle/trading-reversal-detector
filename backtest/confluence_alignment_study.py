"""Confluence trend alignment: CHART-NATIVE 200-SMA vs DAILY 200-SMA.

The live scanner aligns each divergence against the 200-SMA computed on its OWN
timeframe (chart-native). Script A / the research call the DAILY 200-SMA the
"OOS-validated" reference. This tests them head-to-head on the SAME trade pool:

  1. pull ALL DRS-qualifying divergences (aligned_only OFF) on the swing TFs;
  2. tag each with cn_aligned (close vs its chart-native 200-SMA) AND
     daily_aligned (close vs the no-lookahead DAILY 200-SMA at that time);
  3. slice: CN-aligned (= what the scanner trades now) vs DAILY-aligned.

Everything else identical: DRS-loose any-zone-30d, SL1.5/TP4, entry at confirm
close. Faithful (config assets/dirs) + fair-sample (8 assets, both dirs).
Outputs logs/confluence_alignment.xlsx.
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
    attach_trade_levels, detect_divergences, drop_incomplete_last_bar,
    fetch_ohlcv, parse_tf_minutes, resample_ohlcv,
)
from src.v5_confluence import drs_signals            # noqa: E402

CFG = yaml.safe_load((ROOT / "config" / "v5_confluence_scanner.yaml").read_text("utf-8"))
DIV = dict(CFG["divergence"]); DIV["aligned_only"] = False   # get ALL divergences
TF_CFG = CFG["timeframes"]; CFG_ASSETS = CFG["assets"]
ZONE_DAYS = int(CFG["drs"]["zone_max_days"]); BUF = float(CFG["drs"]["buffer_atr"])
SL_ATR = float(DIV["sl_atr_mult"]); TP_ATR = float(DIV["tp_atr_mult"])
R_WIN, R_LOSS = TP_ATR / SL_ATR, -1.0
LOOKBACK = pd.Timedelta(days=730)
MERGE_ATR = 0.75
SMA_LEN = int(DIV["trend_sma"])

FAIR_ASSETS = {
    "BTCUSD": ("BTC-USD", "utc", ["buy", "sell"]), "ETHUSD": ("ETH-USD", "utc", ["buy", "sell"]),
    "XAUUSD": ("GC=F", "ny17", ["buy", "sell"]), "NAS100": ("NQ=F", "ny17", ["buy", "sell"]),
    "USDJPY": ("USDJPY=X", "ny17", ["buy", "sell"]), "EURUSD": ("EURUSD=X", "ny17", ["buy", "sell"]),
    "GBPUSD": ("GBPUSD=X", "ny17", ["buy", "sell"]), "AUDUSD": ("AUDUSD=X", "ny17", ["buy", "sell"]),
}


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


def daily_sma_map(ticker, cache):
    ck = (ticker, "1d", "1500d")
    if ck not in cache:
        cache[ck] = fetch_ohlcv(ticker, "1d", "1500d")
    d = cache[ck]
    if d is None or d.empty:
        return None, None
    sma = d["Close"].rolling(SMA_LEN).mean().to_numpy()
    idx = pd.to_datetime(d.index).normalize()
    return idx, sma


def daily_sma_at(idx, sma, t):
    if idx is None:
        return np.nan
    day = pd.Timestamp(t).normalize()
    pos = idx.searchsorted(day, side="left") - 1   # last COMPLETED daily bar strictly before t's day
    if pos < 0:
        return np.nan
    return sma[pos]


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
        d_idx, d_sma = daily_sma_map(tk, cache)
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
            sigs = detect_divergences(frame, asset, tk, tf, bmin, DIV)     # aligned_only OFF -> all
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
                # alignment flags
                cn = (direction == "long" and s.close > s.sma) or (direction == "short" and s.close < s.sma)
                dsma = daily_sma_at(d_idx, d_sma, s.confirm_time)
                dn = np.nan if not np.isfinite(dsma) else (
                    (s.close > dsma) if direction == "long" else (s.close < dsma))
                i = pos[s.confirm_time]
                outc, R = score(frame, i, direction, s.close, s.atr)
                trades.append(dict(asset=asset, tf=tf, side=("BUY" if direction == "long" else "SELL"),
                                   entry_time=entry_t, zones=distinct(qual, s.atr),
                                   cn_aligned=bool(cn),
                                   daily_aligned=(None if not np.isfinite(dsma) else bool(dn)),
                                   outcome=outc, R=round(R, 3)))
    return pd.DataFrame(trades)


def stats(sub, label):
    R = sub.R.to_numpy(); res = sub[sub.outcome != "OPEN"]
    if len(R) == 0:
        return dict(group=label, n=0, win=np.nan, pf=np.nan, expR=np.nan, totR=0.0)
    pos = R[R > 0].sum(); neg = -R[R < 0].sum()
    pf = pos / neg if neg > 0 else np.inf
    return dict(group=label, n=len(R),
                win=round(100 * (res.outcome == "TP").mean(), 1) if len(res) else np.nan,
                pf=round(float(pf), 2) if np.isfinite(pf) else np.inf,
                expR=round(float(R.mean()), 3), totR=round(float(R.sum()), 1))


def summary(d, title):
    dd = d[d.daily_aligned.notna()]      # only where a daily SMA existed
    rows = [
        stats(d[d.cn_aligned], f"{title}: CHART-NATIVE aligned [LIVE]"),
        stats(dd[dd.daily_aligned == True], f"{title}: DAILY aligned"),
        stats(d, f"{title}: all DRS-qualifying divergences (unfiltered)"),
        stats(d[d.cn_aligned & (d.daily_aligned == True)], f"{title}: BOTH aligned"),
        stats(d[d.cn_aligned & (d.daily_aligned == False)], f"{title}: CN-aligned but daily-counter"),
        stats(d[(~d.cn_aligned) & (d.daily_aligned == True)], f"{title}: daily-aligned but CN-counter"),
    ]
    return pd.DataFrame(rows)


def per_tf(d, title):
    rows = []
    for tf in TF_CFG:
        sub = d[d.tf == tf]
        if not len(sub):
            continue
        rows.append(stats(sub[sub.cn_aligned], f"{tf} CN"))
        rows.append(stats(sub[sub.daily_aligned == True], f"{tf} DAILY"))
    return pd.DataFrame(rows)


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

    with pd.ExcelWriter(ROOT / "logs" / "confluence_alignment.xlsx", engine="openpyxl") as xl:
        summary(faith, "FAITHFUL").to_excel(xl, sheet_name="Faithful CN vs DAILY", index=False)
        per_tf(faith, "FAITHFUL").to_excel(xl, sheet_name="Faithful per TF", index=False)
        summary(fair, "FAIR").to_excel(xl, sheet_name="Fair CN vs DAILY", index=False)
        per_tf(fair, "FAIR").to_excel(xl, sheet_name="Fair per TF", index=False)
        faith.sort_values("entry_time").to_excel(xl, sheet_name="Faithful trades", index=False)
        fair.sort_values("entry_time").to_excel(xl, sheet_name="Fair trades", index=False)

    print("\n===== FAITHFUL (config assets/dirs) — CN vs DAILY alignment =====\n",
          summary(faith, "FAITHFUL").to_string(index=False))
    print("\n===== FAITHFUL per timeframe =====\n", per_tf(faith, "FAITHFUL").to_string(index=False))
    print("\n===== FAIR-SAMPLE (8 assets, both dirs) — CN vs DAILY =====\n",
          summary(fair, "FAIR").to_string(index=False))
    print("\n===== FAIR per timeframe =====\n", per_tf(fair, "FAIR").to_string(index=False))
    print(f"\nFaithful pool: {len(faith)} | Fair pool: {len(fair)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
