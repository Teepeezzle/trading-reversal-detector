"""V5 CONFLUENCE detection: aligned V5 divergence + DRS support/resistance + trend.

The 3-way spec validated in backtest (better than adding TD):
  * aligned V5 divergence (BULL = uptrend-aligned buy, BEAR = downtrend-aligned
    sell) — the alignment already encodes the 200-SMA trend agreement.
  * price AT/NEAR the latest same-direction DRS red level (any timeframe,
    within 30 days): buys need entry <= red + 0.5*ATR (support);
    sells need entry >= red - 0.5*ATR (resistance).
  * exit: SL 1.5xATR / TP 4.0xATR (+2.667R / -1R).

Restricted to the robustness-checked shortlist (positive in both the 3-way and
4-way tests), with per-asset allowed directions set in the config:
  Buys : BTCUSD, NZDJPY, USDJPY, GBPUSD
  Sells: DOGEUSD, XAUUSD, EURUSD, BTCUSD

This is a rare, high-conviction setup — expect few alerts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .v5_divergence import (
    DivergenceSignal, attach_trade_levels, detect_divergences, atr_wilder,
    parse_tf_minutes, _winners_card, _portfolio_block, _money,
)


def drs_signals(frame: pd.DataFrame, has_vol: bool):
    """Daily Reversal Pro long/short signal masks + ATR(20). Faithful to Pine."""
    c, h, l = frame["Close"], frame["High"], frame["Low"]
    v = frame["Volume"] if "Volume" in frame else pd.Series(0, index=frame.index)
    fe = c.ewm(span=9, adjust=False).mean(); se = c.ewm(span=21, adjust=False).mean()
    emaBull = (fe > se) & (fe.shift() <= se.shift())
    emaBear = (fe < se) & (fe.shift() >= se.shift())
    bullDiv = l <= l.rolling(3).min()
    bearDiv = h >= h.rolling(3).max()
    volSpike = (v > v.rolling(14).mean()*1.8) if has_vol else pd.Series(True, index=frame.index)
    atr = atr_wilder(frame, 20)
    atrS = pd.Series(atr, index=frame.index)
    atrBull = c > c.shift() + atrS*0.3
    atrBear = c < c.shift() - atrS*0.3
    longc = (emaBull & bullDiv & volSpike & atrBull).to_numpy()
    shortc = (emaBear & bearDiv & volSpike & atrBear).to_numpy()
    return longc, shortc, atr


def drs_zones(frames: Dict[str, Tuple[pd.DataFrame, bool]], direction: str
              ) -> Tuple[List[pd.Timestamp], List[float]]:
    """ALL same-direction DRS red levels across all TFs, sorted by time.

    long  -> red = DRS-long stop  = low - 1.5*ATR  (support)
    short -> red = DRS-short stop = high + 1.5*ATR (resistance)
    Returns (times, reds). The DRS-LOOSE rule checks ANY of these within 30d of
    a trigger (not just the most recent), so the caller keeps the full list.
    """
    ts: List[pd.Timestamp] = []
    rs: List[float] = []
    for tf, (frame, has_vol) in frames.items():
        longc, shortc, atr = drs_signals(frame, has_vol)
        arr = longc if direction == "long" else shortc
        idx = frame.index
        low = frame["Low"].to_numpy(); high = frame["High"].to_numpy()
        for i in range(len(frame)):
            if not arr[i] or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            ts.append(idx[i])
            rs.append(low[i]-1.5*atr[i] if direction == "long" else high[i]+1.5*atr[i])
    order = np.argsort(ts)
    return [ts[k] for k in order], [rs[k] for k in order]


def confluence_on_frame(frame: pd.DataFrame, asset: str, ticker: str, tf: str,
                        bar_min: int, div_cfg: dict, allowed_dirs: List[str],
                        zones_long: Tuple[List, List], zones_short: Tuple[List, List],
                        sl_mult: float, tp_mult: float, buffer_atr: float,
                        zone_max_days: int = 30) -> List[DivergenceSignal]:
    """Aligned V5 divergences that sit at/near ANY DRS red in the last 30d.

    DRS-LOOSE: walk back through same-direction DRS zones with time <= the
    divergence-confirm time and within `zone_max_days`; the trade qualifies if
    ANY of those zones' red level satisfies the at/near-edge price condition.
    """
    import bisect
    atr_len = int(div_cfg.get("atr_len", 14))
    sigs = detect_divergences(frame, asset, ticker, tf, bar_min, div_cfg)
    sigs = attach_trade_levels(sigs, frame, atr_len, sl_mult, tp_mult)
    maxd = pd.Timedelta(days=zone_max_days)
    out: List[DivergenceSignal] = []
    for s in sigs:
        if s.stop is None or s.atr is None:
            continue
        d = "long" if s.direction == "BULL" else "short"
        want = "buy" if d == "long" else "sell"
        if want not in allowed_dirs:
            continue
        times, reds = zones_long if d == "long" else zones_short
        buf = buffer_atr * s.atr
        k = bisect.bisect_right(times, s.confirm_time) - 1
        red = None
        while k >= 0 and (s.confirm_time - times[k]) <= maxd:
            near = (s.close <= reds[k] + buf) if d == "long" else (s.close >= reds[k] - buf)
            if near:
                red = float(reds[k]); break
            k -= 1
        if red is None:
            continue
        s.drs_red = red                  # dynamic attribute for the email
        s.side = want.upper()
        out.append(s)
    return out


def build_confluence_email(signals: List[DivergenceSignal], equity=None,
                           risk_pct=None, portfolio=None) -> Tuple[str, str]:
    """(subject, html) for confluence setups — reuses the winners card + P&L block."""
    count = len(signals)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    tfs = ", ".join(sorted({s.timeframe for s in signals}, key=parse_tf_minutes))
    subject = (f"[V5 CONFLUENCE] {count} setup"
               f"{'s' if count != 1 else ''} — {tfs} — {now_str} UTC")
    if portfolio and (portfolio.get("hit_40") or portfolio.get("below_40_now")):
        subject = "⚠ " + subject
    cards = "\n".join(_winners_card(s, equity, risk_pct) for s in signals)
    portfolio_block = _portfolio_block(portfolio)
    sizing_hdr = ("" if equity is None or risk_pct is None else
                  f" &middot; base {_money(equity)} &middot; {risk_pct*100:.0f}% risk/trade")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="background:#f3f4f6;margin:0;padding:24px;font-family:Arial,Helvetica,sans-serif;">
  <table cellpadding="0" cellspacing="0" border="0" style="max-width:680px;margin:0 auto;"><tr><td>
    <h1 style="color:#111827;font-size:22px;margin:0 0 6px;">V5 CONFLUENCE — trade setups</h1>
    <p style="color:#6b7280;font-size:14px;margin:0 0 24px;">
      {now_str} UTC &middot; {count} setup{'s' if count != 1 else ''}
      &middot; aligned V5 + DRS support/resistance + 200-SMA trend
      &middot; SL 1.5&times;ATR / TP 4&times;ATR (1:2.67){sizing_hdr}</p>
    {portfolio_block}
    {cards}
    <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:20px;">
      Robustness-checked shortlist (buys: BTC/NZDJPY/USDJPY/GBPUSD; sells:
      DOGE/XAUUSD/EURUSD/BTC). Rare, high-conviction. Small backtest samples —
      forward-tracking to prove the live hit rate. Not financial advice.</p>
  </td></tr></table></body></html>"""
    return subject, html
