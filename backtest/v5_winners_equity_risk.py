"""Risk-based equity sim: $1000 on the winners scanner, last 30 days.

Model (per user's revised spec):
  * Each trade is sized so that hitting the 1.5xATR stop loses a FIXED % of
    CURRENT equity (compounding). Position notional = risk$ / stop-distance%.
      win  (TP, 3xATR) = +2 x risk$   (1:2 R:R)
      loss (SL, 1.5xATR) = -1 x risk$
      open  = (favourable move / 1.5xATR) x risk$
  * Risk-per-trade run at 5% AND 10% of equity.
  * TOTAL open risk (sum of open positions' risk$) has a 40%-of-equity ceiling
    that WARNS but does NOT block: every signal is still taken; we count how
    often the warning fires and track peak concurrent risk.
  * Entry = confirmation-bar close.  Winners basket, 15m/1h/2h/3h/4h, 30 days.

Event-driven so positions realise (and free their risk) at their exit bar.
Sizing uses realised equity at entry (open trades' unrealised P&L excluded).

NOTE ON LEVERAGE: risk-based sizing implies notional = risk$ / stop%. With a
~0.7% ATR stop and 10% risk, that's ~14x notional vs equity — i.e. it assumes
leverage is available to reach the risk target. Real brokers cap this.
"""
from __future__ import annotations

import argparse
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
RISK_CEILING = 0.40          # total-open-risk warning threshold
LOOKBACK_DAYS = 30
FETCH_PERIOD = {"15m": "60d", "1h": "180d"}


def build_signals(now, lookback_days):
    cfg = yaml.safe_load((ROOT / "config" / "v5_winners_scanner.yaml").read_text("utf-8"))
    div_cfg = dict(cfg["divergence"]); div_cfg["aligned_only"] = True
    tf_cfg = cfg["timeframes"]; assets_cfg = cfg["assets"]
    win_lo = now - pd.Timedelta(days=lookback_days)
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
            posmap = {t: k for k, t in enumerate(frame.index)}
            for s in found:
                if not (win_lo <= s.confirm_close_time <= now):
                    continue
                ci = posmap.get(s.confirm_time)
                if ci is None or not np.isfinite(atr[ci]) or atr[ci] <= 0:
                    continue
                a = atr[ci]; E = s.close; stop_dist = SL_MULT * a
                sl = E - stop_dist if s.direction == "BULL" else E + stop_dist
                tp = E + TP_MULT * a if s.direction == "BULL" else E - TP_MULT * a
                outcome, R, xi = "OPEN", None, len(frame) - 1
                for j in range(ci + 1, len(frame)):
                    if s.direction == "BULL":
                        hit_sl, hit_tp = low[j] <= sl, high[j] >= tp
                    else:
                        hit_sl, hit_tp = high[j] >= sl, low[j] <= tp
                    if hit_sl:
                        outcome, R, xi = "SL", -1.0, j; break
                    if hit_tp:
                        outcome, R, xi = "TP", +2.0, j; break
                if outcome == "OPEN":
                    mv = (close[-1] - E) if s.direction == "BULL" else (E - close[-1])
                    R = mv / stop_dist
                exit_t = (frame.index[xi] + pd.Timedelta(minutes=bar_min)
                          if outcome != "OPEN" else now + pd.Timedelta(days=999))
                sigs.append(dict(entry_t=s.confirm_close_time, exit_t=exit_t,
                                 asset=asset, tf=tf, outcome=outcome, R=R,
                                 side=("BUY" if s.direction == "BULL" else "SELL"),
                                 entry_price=round(E, 6), stop_price=round(sl, 6),
                                 target_price=round(tp, 6)))
    sigs.sort(key=lambda r: r["entry_t"])
    return sigs


def simulate(sigs, risk_pct):
    equity = START_EQ
    open_heap = []                 # (exit_t, pnl, risk_dollars)
    open_risk = 0.0
    peak = equity; max_dd = 0.0
    warns = 0; peak_risk_pct = 0.0
    wins = losses = opens = 0

    def realize_until(t):
        nonlocal equity, open_risk, peak, max_dd
        while open_heap and open_heap[0][0] <= t:
            _, pnl, rd = heapq.heappop(open_heap)
            equity += pnl
            open_risk -= rd
            peak = max(peak, equity)
            if peak > 0:
                max_dd = min(max_dd, (equity - peak) / peak)

    for s in sigs:
        realize_until(s["entry_t"])
        risk_d = risk_pct * equity
        total_after = open_risk + risk_d
        if equity > 0 and total_after / equity > RISK_CEILING:
            warns += 1
        peak_risk_pct = max(peak_risk_pct, total_after / equity if equity > 0 else 0)
        pnl = s["R"] * risk_d
        heapq.heappush(open_heap, (s["exit_t"], pnl, risk_d))
        open_risk += risk_d
        if s["outcome"] == "TP":
            wins += 1
        elif s["outcome"] == "SL":
            losses += 1
        else:
            opens += 1

    while open_heap:
        _, pnl, rd = heapq.heappop(open_heap)
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            max_dd = min(max_dd, (equity - peak) / peak)

    return dict(final=equity, ret=100 * (equity / START_EQ - 1),
                wins=wins, losses=losses, opens=opens, warns=warns,
                max_dd=max_dd * 100, peak_risk=peak_risk_pct * 100)


def main():
    ap = argparse.ArgumentParser(description="Winners risk-based equity sim")
    ap.add_argument("--days", type=int, default=30, help="lookback window in days")
    ap.add_argument("--risk", default="5,10",
                    help="CSV of risk-per-trade percents, e.g. '10' or '5,10'")
    args = ap.parse_args()
    risks = [float(x) / 100.0 for x in str(args.risk).split(",")]

    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    sigs = build_signals(now, args.days)
    res = sum(1 for s in sigs if s["outcome"] != "OPEN")
    wr = 100 * sum(1 for s in sigs if s["outcome"] == "TP") / res if res else 0

    # 15m real coverage (history is <=60d so a 90d window is capped)
    s15 = [s for s in sigs if s["tf"] == "15m"]
    cov15 = (now - min(s["entry_t"] for s in s15)).days if s15 else 0

    print(f"Winners signals last {args.days}d: {len(sigs)}  (all taken)  "
          f"resolved WR {wr:.1f}%   start ${START_EQ:.0f}")
    print(f"(15m history capped at {cov15}d; 1h-4h use the full {args.days}d)\n")
    print(f"{'risk/trade':>11}{'finalEq':>13}{'return':>11}{'maxDD':>9}"
          f"{'40%warns':>10}{'peakRisk':>10}")
    out = {}
    for rp in risks:
        r = simulate(sigs, rp)
        out[rp] = r
        print(f"{rp*100:>9.0f}% ${r['final']:>11,.2f}{r['ret']:>+10.1f}%"
              f"{r['max_dd']:>+8.1f}%{r['warns']:>10}{r['peak_risk']:>9.0f}%")
    print()
    for rp, r in out.items():
        print(f"At {rp*100:.0f}% risk/trade over {args.days}d: $1,000 -> "
              f"${r['final']:,.2f} ({r['ret']:+.1f}%)  |  max drawdown "
              f"{r['max_dd']:.1f}%  |  40% warning fired on {r['warns']} of "
              f"{len(sigs)} signals  |  peak concurrent risk {r['peak_risk']:.0f}%")
    first = out[risks[0]]
    print(f"\n(Wins {first['wins']} / Losses {first['losses']} / "
          f"Open {first['opens']} — same trades all rows, only size differs.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
