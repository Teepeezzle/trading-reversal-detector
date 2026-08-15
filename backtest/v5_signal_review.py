"""Forward-test the last 30 days of emailed [V5 Divergence] signals.

Reconstructs the exact aligned divergences the scanner emailed (same code +
config), then scores each as a trade under SCALPR ATR exits:

  entry  = close of the confirmation bar (when the email fired)
  BULL   -> BUY  : SL = entry - 1.5*ATR, TP = entry + 3.0*ATR
  BEAR   -> SELL : SL = entry + 1.5*ATR, TP = entry - 3.0*ATR
  risk   = 1.5*ATR (= 1R).  TP is 2R away.

Walk price forward from the bar AFTER entry:
  TP hit first  -> +2.0 R
  SL hit first  -> -1.0 R
  both same bar -> assume SL first (conservative) -> -1.0 R
  neither yet   -> OPEN, marked to latest close in R

Outputs overall expectancy, per-timeframe and per-asset breakdowns.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.v5_divergence import (          # noqa: E402
    detect_divergences, drop_incomplete_last_bar, fetch_ohlcv,
    parse_tf_minutes, resample_ohlcv,
)

SL_MULT = 1.5
TP_MULT = 3.0
R_WIN = TP_MULT / SL_MULT      # +2.0 R
R_LOSS = -1.0
LOOKBACK_DAYS = 30


def atr_wilder(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift()
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()


def score_signal(frame, ci, direction, entry, atr_val):
    """Return (outcome, R, exit_time). outcome in {TP,SL,OPEN}."""
    high = frame["High"].to_numpy()
    low = frame["Low"].to_numpy()
    close = frame["Close"].to_numpy()
    n = len(frame)
    risk = SL_MULT * atr_val
    if direction == "BULL":
        sl, tp = entry - risk, entry + TP_MULT * atr_val
    else:
        sl, tp = entry + risk, entry - TP_MULT * atr_val

    for j in range(ci + 1, n):
        hi, lo = high[j], low[j]
        if direction == "BULL":
            hit_sl = lo <= sl
            hit_tp = hi >= tp
        else:
            hit_sl = hi >= sl
            hit_tp = lo <= tp
        if hit_sl and hit_tp:
            return "SL", R_LOSS, frame.index[j]        # conservative
        if hit_sl:
            return "SL", R_LOSS, frame.index[j]
        if hit_tp:
            return "TP", R_WIN, frame.index[j]

    # unresolved — mark to last close
    last = close[-1]
    move = (last - entry) if direction == "BULL" else (entry - last)
    return "OPEN", move / risk, frame.index[-1]


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "v5_scanner.yaml").read_text("utf-8"))
    div_cfg = dict(cfg["divergence"])
    div_cfg["aligned_only"] = True
    tf_cfg = cfg["timeframes"]
    assets = cfg["assets"]

    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    win_lo = now - pd.Timedelta(days=LOOKBACK_DAYS)
    print(f"V5 emailed-signal review  |  window {win_lo:%Y-%m-%d} -> {now:%Y-%m-%d} UTC")
    print(f"Model: BUY/SELL on divergence dir, SL {SL_MULT}xATR / TP {TP_MULT}xATR "
          f"(+{R_WIN:.0f}R win / {R_LOSS:.0f}R loss)\n")

    fetch_cache: dict = {}
    rows = []

    for asset, spec in assets.items():
        ticker = spec["ticker"] if isinstance(spec, dict) else spec
        anchor = spec.get("anchor", "utc") if isinstance(spec, dict) else "utc"
        for tf, tspec in tf_cfg.items():
            bar_min = parse_tf_minutes(tf)
            source = str(tspec["source_interval"])
            period = str(tspec["period"])
            rule = tspec.get("resample")
            ck = (ticker, source, period)
            if ck not in fetch_cache:
                fetch_cache[ck] = fetch_ohlcv(ticker, source, period)
            df = fetch_cache[ck]
            if df is None or df.empty:
                continue
            frame = resample_ohlcv(df, rule, anchor) if rule else df
            frame = drop_incomplete_last_bar(frame, bar_min, now)
            if len(frame) < int(div_cfg["trend_sma"]) + 10:
                continue
            atr = atr_wilder(frame, int(div_cfg.get("atr_len", 14)))
            sigs = detect_divergences(frame, asset, ticker, tf, bar_min, div_cfg)
            pos = {t: k for k, t in enumerate(frame.index)}
            for s in sigs:
                if not (win_lo <= s.confirm_close_time <= now):
                    continue
                ci = pos.get(s.confirm_time)
                if ci is None or not np.isfinite(atr[ci]) or atr[ci] <= 0:
                    continue
                outcome, r, xtime = score_signal(
                    frame, ci, s.direction, s.close, atr[ci])
                rows.append(dict(
                    asset=asset, tf=tf, dir=s.direction,
                    side="BUY" if s.direction == "BULL" else "SELL",
                    confirm=s.confirm_close_time, outcome=outcome,
                    R=r, span=s.span))

    if not rows:
        print("No emailed signals in the last 30 days.")
        return 0

    d = pd.DataFrame(rows).sort_values("confirm").reset_index(drop=True)
    resolved = d[d.outcome != "OPEN"]
    openp = d[d.outcome == "OPEN"]

    def block(title, sub):
        if sub.empty:
            return
        n = len(sub)
        wins = (sub.outcome == "TP").sum()
        losses = (sub.outcome == "SL").sum()
        opn = (sub.outcome == "OPEN").sum()
        rsum = sub.R.sum()
        res = sub[sub.outcome != "OPEN"]
        wr = 100 * (res.outcome == "TP").mean() if len(res) else float("nan")
        exp = res.R.mean() if len(res) else float("nan")
        print(f"{title:<22} n={n:<4} TP={wins:<3} SL={losses:<3} open={opn:<3} "
              f"resolved_WR={wr:5.1f}%  totalR={rsum:+6.1f}  exp/trade={exp:+.3f}R")

    print("=" * 92)
    block("ALL SIGNALS", d)
    print("-" * 92)
    print("By timeframe:")
    for tf in [t for t in tf_cfg]:
        block("  " + tf, d[d.tf == tf])
    print("-" * 92)
    print("By asset:")
    for a in assets:
        sub = d[d.asset == a]
        if not sub.empty:
            block("  " + a, sub)
    print("-" * 92)
    print("By direction:")
    block("  BUY (bull div)", d[d.dir == "BULL"])
    block("  SELL (bear div)", d[d.dir == "BEAR"])
    print("=" * 92)

    # resolved-only expectancy (the honest number)
    if len(resolved):
        wr = 100 * (resolved.outcome == "TP").mean()
        print(f"\nRESOLVED trades only: n={len(resolved)}  win%={wr:.1f}  "
              f"totalR={resolved.R.sum():+.1f}  expectancy={resolved.R.mean():+.3f}R/trade")
    print(f"OPEN (unresolved) trades: n={len(openp)}  "
          f"mark-to-market R={openp.R.sum():+.1f}")

    # full per-signal listing (most recent first)
    print("\nPer-signal detail (most recent first):")
    print(f"{'confirm(UTC)':<17}{'asset':<8}{'tf':<5}{'side':<5}"
          f"{'span':<5}{'outcome':<8}{'R':>7}")
    for _, r in d.sort_values("confirm", ascending=False).iterrows():
        print(f"{r.confirm:%Y-%m-%d %H:%M} {r.asset:<8}{r.tf:<5}{r.side:<5}"
              f"{r.span:<5}{r.outcome:<8}{r.R:>+7.2f}")

    d.to_csv(ROOT / "logs" / "v5_signal_review.csv", index=False)
    print(f"\nSaved full table -> logs/v5_signal_review.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
