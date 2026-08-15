"""Equity simulation: $1000 traded on the winners scanner, last 30 days.

Rules (per user):
  * Assets/TFs : winners basket, 15m/1h/2h/3h/4h  (same as v5_winners_review).
  * Entry      : confirmation-bar close.  Exit: SL 1.5xATR / TP 3.0xATR.
  * Sizing     : EQUAL NOTIONAL SLICE of the cap. Each open trade deploys
                 (cap / 5) of CURRENT equity as notional (no leverage).
                 -> up to 5 concurrent positions reach the cap.
  * Concurrency: multiple per asset allowed; a new signal is SKIPPED when the
                 cap is already full (5 slots used).
  * P&L        : notional * price-move fraction.
                   win  (TP): +3.0*ATR / entry
                   loss (SL): -1.5*ATR / entry
                   open     : signed (last_close - entry)/entry
  * Caps run   : 30% and 40%.  Start equity $1000.

Time-ordered event sim: positions free their slot at the exit bar's close,
so later signals can occupy the slot. Sizing uses realized equity at entry
(open positions' unrealized P&L not counted until they close) — standard,
avoids look-ahead.
"""
from __future__ import annotations

import heapq
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.v5_divergence import (          # noqa: E402
    atr_wilder, detect_divergences, drop_incomplete_last_bar, fetch_ohlcv,
    parse_tf_minutes, resample_ohlcv,
)

WINNERS = ["BTCUSD", "ETHUSD", "DOGEUSD", "XAUUSD", "NAS100"]
TFS = ["15m", "1h", "2h", "3h", "4h"]
SL_MULT, TP_MULT = 1.5, 3.0
START_EQ = 1000.0
MAX_SLOTS = 5
LOOKBACK_DAYS = 30
FETCH_PERIOD = {"15m": "60d", "1h": "180d"}


def build_signals(now):
    cfg = yaml.safe_load((ROOT / "config" / "v5_winners_scanner.yaml").read_text("utf-8"))
    div_cfg = dict(cfg["divergence"]); div_cfg["aligned_only"] = True
    tf_cfg = cfg["timeframes"]; assets_cfg = cfg["assets"]
    win_lo = now - pd.Timedelta(days=LOOKBACK_DAYS)
    atr_len = int(div_cfg.get("atr_len", 14))
    cache: dict = {}
    sigs = []
    for asset in WINNERS:
        spec = assets_cfg[asset]; ticker = spec["ticker"]; anchor = spec.get("anchor", "utc")
        for tf in TFS:
            tspec = tf_cfg[tf]; bar_min = parse_tf_minutes(tf)
            source = str(tspec["source_interval"]); period = FETCH_PERIOD[source]
            rule = tspec.get("resample")
            ck = (ticker, source, period)
            if ck not in cache:
                cache[ck] = fetch_ohlcv(ticker, source, period)
            df = cache[ck]
            if df is None or df.empty:
                continue
            frame = resample_ohlcv(df, rule, anchor) if rule else df
            frame = drop_incomplete_last_bar(frame, bar_min, now)
            if len(frame) < int(div_cfg["trend_sma"]) + 10:
                continue
            atr = atr_wilder(frame, atr_len)
            high = frame["High"].to_numpy(); low = frame["Low"].to_numpy()
            close = frame["Close"].to_numpy()
            found = detect_divergences(frame, asset, ticker, tf, bar_min, div_cfg)
            pos = {t: k for k, t in enumerate(frame.index)}
            for s in found:
                if not (win_lo <= s.confirm_close_time <= now):
                    continue
                ci = pos.get(s.confirm_time)
                if ci is None or not np.isfinite(atr[ci]) or atr[ci] <= 0:
                    continue
                a = atr[ci]; E = s.close
                risk_frac = SL_MULT * a / E
                rew_frac = TP_MULT * a / E
                # resolve outcome
                outcome, frac, xi = "OPEN", None, len(frame) - 1
                sl = E - SL_MULT * a if s.direction == "BULL" else E + SL_MULT * a
                tp = E + TP_MULT * a if s.direction == "BULL" else E - TP_MULT * a
                for j in range(ci + 1, len(frame)):
                    if s.direction == "BULL":
                        hit_sl, hit_tp = low[j] <= sl, high[j] >= tp
                    else:
                        hit_sl, hit_tp = high[j] >= sl, low[j] <= tp
                    if hit_sl:
                        outcome, frac, xi = "SL", -risk_frac, j; break
                    if hit_tp:
                        outcome, frac, xi = "TP", +rew_frac, j; break
                if outcome == "OPEN":
                    mv = ((close[-1] - E) if s.direction == "BULL" else (E - close[-1]))
                    frac = mv / E
                exit_t = (frame.index[xi] + pd.Timedelta(minutes=bar_min)
                          if outcome != "OPEN" else now + pd.Timedelta(days=999))
                sigs.append(dict(entry_t=s.confirm_close_time, exit_t=exit_t,
                                 asset=asset, tf=tf, outcome=outcome, frac=frac))
    sigs.sort(key=lambda r: r["entry_t"])
    return sigs


def simulate(sigs, cap):
    """Event-driven sim. Returns (final_eq, taken, skipped, wins, losses, opens,
    max_dd_pct, eq_curve)."""
    slice_frac = cap / MAX_SLOTS
    equity = START_EQ
    open_heap = []            # (exit_t, pnl_dollars)
    taken = skipped = wins = losses = opens = 0
    peak = equity; max_dd = 0.0
    eq_curve = [(None, equity)]

    def realize_until(t):
        nonlocal equity, peak, max_dd
        while open_heap and open_heap[0][0] <= t:
            _, pnl = heapq.heappop(open_heap)
            equity += pnl
            peak = max(peak, equity)
            max_dd = min(max_dd, (equity - peak) / peak)
            eq_curve.append((_, equity))

    for s in sigs:
        realize_until(s["entry_t"])
        if len(open_heap) >= MAX_SLOTS:
            skipped += 1
            continue
        notional = slice_frac * equity
        pnl = notional * s["frac"]
        heapq.heappush(open_heap, (s["exit_t"], pnl))
        taken += 1
        if s["outcome"] == "TP":
            wins += 1
        elif s["outcome"] == "SL":
            losses += 1
        else:
            opens += 1
    # flush remaining
    while open_heap:
        _, pnl = heapq.heappop(open_heap)
        equity += pnl
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity - peak) / peak)
        eq_curve.append((_, equity))

    return equity, taken, skipped, wins, losses, opens, max_dd * 100, eq_curve


def main():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    sigs = build_signals(now)
    print(f"Winners signals in last {LOOKBACK_DAYS}d: {len(sigs)}   "
          f"(start ${START_EQ:.0f}, {MAX_SLOTS} slots, entry=bar close, SL1.5/TP3 ATR)\n")
    print(f"{'cap':>5}{'slice':>8}{'taken':>7}{'skipped':>9}{'W':>5}{'L':>5}"
          f"{'open':>6}{'takenWR':>9}{'finalEq':>11}{'return':>9}{'maxDD':>8}")
    results = {}
    for cap in (0.30, 0.40):
        fe, tk, sk, w, l, o, dd, curve = simulate(sigs, cap)
        res = w + l
        wr = 100 * w / res if res else float("nan")
        ret = 100 * (fe / START_EQ - 1)
        results[cap] = (fe, ret, dd)
        print(f"{cap*100:>4.0f}%{cap/5*100:>7.1f}%{tk:>7}{sk:>9}{w:>5}{l:>5}"
              f"{o:>6}{wr:>8.1f}%${fe:>10,.2f}{ret:>+8.2f}%{dd:>+7.1f}%")

    print()
    for cap, (fe, ret, dd) in results.items():
        print(f"At {cap*100:.0f}% cap: $1,000 -> ${fe:,.2f}  ({ret:+.2f}%, "
              f"max drawdown {dd:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
