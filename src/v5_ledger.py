"""Lightweight paper-trading ledger for the winners scanner.

Implements the STATIC, non-compounding model:
  * Risk per trade is a constant dollar amount = risk_pct * BASE equity.
  * Every emitted signal is registered as an OPEN position.
  * On each run we reconcile open positions against subsequent 1h price bars:
    first touch of SL -> -1R, first touch of TP -> +2R (SL-first on same bar,
    matching the backtest). Positions open past `max_age_days` are marked to
    market and closed so the ledger can't grow unbounded.
  * Realized P&L accumulates in dollars on top of the static base (no
    compounding — position size never re-derives from the growing equity).
  * A 40%-loss warning fires when cumulative realized P&L ever reaches
    -40% of the base (equity <= 0.6 * base).

State is a JSON file persisted via the Actions cache alongside the dedup
state. All functions are defensive: a data hiccup during reconcile must never
crash the scan, so callers wrap this in try/except and fall back to the
last-saved ledger.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd


def load_ledger(path: Path) -> Dict:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d.setdefault("realized_pnl", 0.0)
    d.setdefault("realized_r", 0.0)
    d.setdefault("wins", 0)
    d.setdefault("losses", 0)
    d.setdefault("closed", 0)
    d.setdefault("min_realized_pnl", 0.0)   # most-negative cumulative P&L seen
    d.setdefault("open", [])
    return d


def save_ledger(path: Path, ledger: Dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(ledger, indent=1), encoding="utf-8")


def register(ledger: Dict, signals: List, risk_dollars: float) -> Dict:
    """Add newly-emitted signals as open positions (idempotent by signal_id)."""
    known = {p["id"] for p in ledger["open"]}
    for s in signals:
        pid = s.signal_id
        if pid in known:
            continue
        ledger["open"].append(dict(
            id=pid, ticker=s.ticker, asset=s.asset, tf=s.timeframe,
            dir=s.direction, entry=float(s.close),
            sl=float(s.stop), tp=float(s.target),
            risk_dollars=float(risk_dollars),
            entry_time=s.confirm_time.isoformat()))
        known.add(pid)
    return ledger


def reconcile(ledger: Dict, fetch_1h: Callable[[str], Optional[pd.DataFrame]],
              now: pd.Timestamp, max_age_days: int = 30
              ) -> Tuple[Dict, List[Dict]]:
    """Close open positions whose SL/TP was touched on 1h bars after entry.

    Returns (ledger, newly_closed). Uses 1h bars as a uniform, always-available
    resolution for touch detection regardless of the signal's own timeframe.
    """
    still_open: List[Dict] = []
    newly_closed: List[Dict] = []
    cache: Dict[str, Optional[pd.DataFrame]] = {}

    for p in ledger["open"]:
        tk = p["ticker"]
        if tk not in cache:
            try:
                cache[tk] = fetch_1h(tk)
            except Exception:
                cache[tk] = None
        df = cache[tk]
        outcome = None                      # (kind, R)

        if df is not None and not df.empty:
            entry_t = pd.Timestamp(p["entry_time"])
            fut = df[df.index >= entry_t]
            sl, tp, direction = p["sl"], p["tp"], p["dir"]
            highs = fut["High"].to_numpy()
            lows = fut["Low"].to_numpy()
            for hi, lo in zip(highs, lows):
                if direction == "BULL":
                    hit_sl, hit_tp = lo <= sl, hi >= tp
                else:
                    hit_sl, hit_tp = hi >= sl, lo <= tp
                if hit_sl:
                    outcome = ("SL", -1.0); break
                if hit_tp:
                    outcome = ("TP", 2.0); break

            if outcome is None:
                age = now - entry_t
                if age > pd.Timedelta(days=max_age_days):
                    last = float(df["Close"].iloc[-1])
                    stop_dist = abs(p["entry"] - p["sl"])
                    mv = (last - p["entry"]) if direction == "BULL" else (p["entry"] - last)
                    outcome = ("EXPIRE", (mv / stop_dist) if stop_dist > 0 else 0.0)

        if outcome is None:
            still_open.append(p)
        else:
            kind, r = outcome
            pnl = r * p["risk_dollars"]
            ledger["realized_pnl"] += pnl
            ledger["realized_r"] += r
            ledger["closed"] += 1
            if r > 0:
                ledger["wins"] += 1
            elif r < 0:
                ledger["losses"] += 1
            ledger["min_realized_pnl"] = min(ledger["min_realized_pnl"],
                                             ledger["realized_pnl"])
            newly_closed.append(dict(asset=p["asset"], tf=p["tf"], dir=p["dir"],
                                     outcome=kind, R=r, pnl=pnl))

    ledger["open"] = still_open
    return ledger, newly_closed


def status(ledger: Dict, base: float, risk_pct: float) -> Dict:
    realized = ledger["realized_pnl"]
    open_risk = sum(p["risk_dollars"] for p in ledger["open"])
    return dict(
        base=base, risk_pct=risk_pct,
        realized_pnl=realized, realized_r=ledger["realized_r"],
        equity=base + realized,
        open_count=len(ledger["open"]), open_risk=open_risk,
        net_pct=(100 * realized / base) if base > 0 else 0.0,
        wins=ledger["wins"], losses=ledger["losses"], closed=ledger["closed"],
        min_realized_pnl=ledger["min_realized_pnl"],
        hit_40=(ledger["min_realized_pnl"] <= -0.40 * base) if base > 0 else False,
        below_40_now=(realized <= -0.40 * base) if base > 0 else False,
    )
