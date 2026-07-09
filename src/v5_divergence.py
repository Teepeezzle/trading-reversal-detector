"""V5 Swing + MACD Divergence scanner core.

Python replica of the TradingView Pine indicator
"V5 Swing + MACD Divergence v5" with the user's live settings:

* Pivot detection: LEFT 2 / RIGHT 2 bars (``ta.pivothigh``/``ta.pivotlow``
  equivalents — a pivot confirms ``right_bars`` bars after it forms, so the
  detection is non-repainting).
* Regular divergence only: bear = higher-high price + lower-high MACD line;
  bull = lower-low price + higher-low MACD line, between two CONSECUTIVE
  same-side pivots.
* Span filter: pivot-to-pivot distance must be within [span_min, span_max]
  bars (Custom 6-50 in the live config).
* Trend alignment: chart-native SMA(200) computed ON THE SCANNED TIMEFRAME
  (the "Use DAILY 200-SMA" toggle is OFF in the live config). A bull
  divergence is ALIGNED when the confirmation bar closes above the SMA; a
  bear divergence when it closes below.
* Only ALIGNED divergences are alerted (per user requirement).

Data comes from yfinance. Timeframes yfinance doesn't serve natively
(45m/2h/3h/4h) are resampled from 15m/1h bars, so bar boundaries are
UTC-midnight anchored and may differ slightly from broker/TradingView bars.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------- data


@dataclass
class DivergenceSignal:
    """One confirmed, trend-aligned divergence."""

    asset: str            # display name, e.g. "BTCUSD"
    ticker: str           # yfinance ticker, e.g. "BTC-USD"
    timeframe: str        # e.g. "45m", "4h"
    direction: str        # "BULL" or "BEAR"
    regime: str           # "UPTREND" or "DOWNTREND"
    span: int             # bars between the two pivots
    pivot1_price: float
    pivot1_time: pd.Timestamp
    pivot2_price: float
    pivot2_time: pd.Timestamp
    macd1: float
    macd2: float
    close: float          # close of the confirmation bar
    sma: float            # SMA(200) at the confirmation bar
    confirm_time: pd.Timestamp   # START of the confirmation bar (UTC)
    bar_minutes: int

    @property
    def confirm_close_time(self) -> pd.Timestamp:
        """UTC time the confirmation bar CLOSED (signal became visible)."""
        return self.confirm_time + pd.Timedelta(minutes=self.bar_minutes)

    @property
    def signal_id(self) -> str:
        """Stable identity used for cross-run dedup."""
        return (
            f"{self.ticker}|{self.timeframe}|{self.direction}"
            f"|{self.confirm_time.isoformat()}"
        )


def parse_tf_minutes(tf: str) -> int:
    """Convert a timeframe label like ``"45m"`` / ``"4h"`` to minutes."""
    tf = tf.strip().lower()
    if tf.endswith("m"):
        return int(tf[:-1])
    if tf.endswith("h"):
        return int(tf[:-1]) * 60
    if tf.endswith("d"):
        return int(tf[:-1]) * 1440
    raise ValueError(f"Unrecognised timeframe label: {tf!r}")


def fetch_ohlcv(ticker: str, interval: str, period: str,
                retries: int = 3) -> Optional[pd.DataFrame]:
    """Download OHLCV from yfinance, normalised to a UTC-naive index."""
    for attempt in range(retries):
        try:
            raw = yf.download(ticker, period=period, interval=interval,
                              progress=False, auto_adjust=False, threads=False)
        except Exception:
            raw = None
        if raw is not None and not raw.empty:
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna(
                subset=["Open", "High", "Low", "Close"])
            if df.index.tz is not None:
                df.index = df.index.tz_convert("UTC").tz_localize(None)
            if len(df) > 0:
                return df
        time.sleep(1.5 * (attempt + 1))
    return None


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample to a coarser bar (UTC-midnight anchored bins)."""
    agg = {"Open": "first", "High": "max", "Low": "min",
           "Close": "last", "Volume": "sum"}
    return df.resample(rule).agg(agg).dropna(subset=["Open", "High", "Low", "Close"])


def drop_incomplete_last_bar(df: pd.DataFrame, bar_minutes: int,
                             now: pd.Timestamp) -> pd.DataFrame:
    """Remove any bar whose close time is still in the future (in-progress)."""
    bar_end = df.index + pd.Timedelta(minutes=bar_minutes)
    return df[bar_end <= now]


# ---------------------------------------------------------------- indicators


def macd_line(close: pd.Series, fast: int, slow: int) -> np.ndarray:
    """MACD line only (the Pine script diverges on macdLine, not histogram)."""
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    return (ema_f - ema_s).to_numpy()


def find_pivots(vals: np.ndarray, left: int, right: int, kind: str) -> List[int]:
    """Indexes of confirmed swing pivots (Pine pivothigh/pivotlow equivalent).

    A bar i is a pivot if it is the extreme of window [i-left, i+right].
    It CONFIRMS at bar i + right (non-repainting).
    """
    out: List[int] = []
    n = len(vals)
    for i in range(left, n - right):
        w = vals[i - left: i + right + 1]
        v = vals[i]
        if (kind == "high" and v == w.max()) or (kind == "low" and v == w.min()):
            out.append(i)
    return out


# ---------------------------------------------------------------- detection


def detect_divergences(df: pd.DataFrame, asset: str, ticker: str,
                       timeframe: str, bar_minutes: int,
                       cfg: Dict) -> List[DivergenceSignal]:
    """Find all trend-aligned regular divergences in the frame."""
    left = int(cfg["left_bars"])
    right = int(cfg["right_bars"])
    span_min = int(cfg["span_min"])
    span_max = int(cfg["span_max"])
    sma_len = int(cfg["trend_sma"])
    aligned_only = bool(cfg.get("aligned_only", True))

    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    macd = macd_line(df["Close"], int(cfg["macd_fast"]), int(cfg["macd_slow"]))
    sma = df["Close"].rolling(sma_len).mean().to_numpy()
    idx = df.index
    n = len(df)

    signals: List[DivergenceSignal] = []

    for kind, direction in (("high", "BEAR"), ("low", "BULL")):
        vals = high if kind == "high" else low
        piv = find_pivots(vals, left, right, kind)
        for k in range(1, len(piv)):
            i1, i2 = piv[k - 1], piv[k]
            span = i2 - i1
            if not (span_min <= span <= span_max):
                continue
            p1, p2 = float(vals[i1]), float(vals[i2])
            m1, m2 = float(macd[i1]), float(macd[i2])
            if direction == "BEAR":
                is_div = p2 > p1 and m2 < m1           # HH price, LH MACD
            else:
                is_div = p2 < p1 and m2 > m1           # LL price, HL MACD
            if not is_div:
                continue
            c = i2 + right                              # confirmation bar
            if c >= n or not np.isfinite(sma[c]):
                continue
            up = close[c] > sma[c]
            aligned = (direction == "BULL" and up) or \
                      (direction == "BEAR" and not up)
            if aligned_only and not aligned:
                continue
            signals.append(DivergenceSignal(
                asset=asset, ticker=ticker, timeframe=timeframe,
                direction=direction,
                regime="UPTREND" if up else "DOWNTREND",
                span=span,
                pivot1_price=p1, pivot1_time=idx[i1],
                pivot2_price=p2, pivot2_time=idx[i2],
                macd1=m1, macd2=m2,
                close=float(close[c]), sma=float(sma[c]),
                confirm_time=idx[c], bar_minutes=bar_minutes,
            ))
    return signals


def filter_fresh(signals: List[DivergenceSignal], now: pd.Timestamp,
                 scan_every_minutes: int, buffer_minutes: int
                 ) -> List[DivergenceSignal]:
    """Keep only signals whose confirmation bar closed within the window.

    Window = one scan period + a buffer for GitHub cron delay. The dedup
    state file prevents double-emailing when two runs both fall inside it.
    """
    window = pd.Timedelta(minutes=scan_every_minutes + buffer_minutes)
    out = []
    for s in signals:
        age = now - s.confirm_close_time
        if pd.Timedelta(0) <= age <= window:
            out.append(s)
    return out


# ---------------------------------------------------------------- dedup state


def load_state(path: Path) -> Dict[str, str]:
    """Read the alerted-signal-id state file (missing file -> empty)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path: Path, state: Dict[str, str],
               keep_days: int = 3) -> None:
    """Write state, pruning entries older than ``keep_days``."""
    cutoff = datetime.now(timezone.utc).timestamp() - keep_days * 86400
    pruned = {}
    for sid, ts in state.items():
        try:
            if datetime.fromisoformat(ts).timestamp() >= cutoff:
                pruned[sid] = ts
        except Exception:
            continue
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pruned, indent=1), encoding="utf-8")


def dedup_signals(signals: List[DivergenceSignal],
                  state: Dict[str, str]
                  ) -> Tuple[List[DivergenceSignal], Dict[str, str]]:
    """Drop signals already alerted in a previous run; record the new ones."""
    fresh: List[DivergenceSignal] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for s in signals:
        if s.signal_id in state:
            continue
        state[s.signal_id] = now_iso
        fresh.append(s)
    return fresh, state


# ---------------------------------------------------------------- email


def _fmt_price(v: float, ticker: str) -> str:
    if ticker.endswith("=X"):
        return f"{v:,.5f}"
    if v < 1:
        return f"{v:,.5f}"
    return f"{v:,.2f}"


def _signal_card(s: DivergenceSignal) -> str:
    is_bull = s.direction == "BULL"
    col = "#16a34a" if is_bull else "#dc2626"
    arrow = "&#9650;" if is_bull else "&#9660;"   # ▲ / ▼
    fmt = lambda v: _fmt_price(v, s.ticker)  # noqa: E731
    return f"""
    <table cellpadding="0" cellspacing="0" border="0" role="presentation"
           style="width:100%;margin-bottom:18px;border:1px solid #e5e7eb;
                  border-radius:8px;background:#fff;
                  font-family:Arial,Helvetica,sans-serif;">
      <tr><td style="background:{col};color:#fff;padding:14px 18px;
                     border-radius:8px 8px 0 0;">
        <div style="font-size:18px;font-weight:bold;">
          {s.asset} &middot; {s.timeframe}</div>
        <div style="font-size:14px;margin-top:4px;">
          {arrow} {s.direction} divergence &middot; ALIGNED with {s.regime}</div>
      </td></tr>
      <tr><td style="padding:16px 18px;font-size:14px;color:#111827;">
        <table style="width:100%;font-size:14px;">
          <tr><td style="color:#6b7280;padding:3px 0;">Confirmed (bar close, UTC)</td>
              <td style="text-align:right;font-weight:600;">
                {s.confirm_close_time.strftime("%Y-%m-%d %H:%M")}</td></tr>
          <tr><td style="color:#6b7280;padding:3px 0;">Close at confirmation</td>
              <td style="text-align:right;font-weight:600;">{fmt(s.close)}</td></tr>
          <tr><td style="color:#6b7280;padding:3px 0;">Pivot 1 &rarr; Pivot 2</td>
              <td style="text-align:right;">{fmt(s.pivot1_price)} &rarr; {fmt(s.pivot2_price)}</td></tr>
          <tr><td style="color:#6b7280;padding:3px 0;">Span</td>
              <td style="text-align:right;">{s.span} bars</td></tr>
          <tr><td style="color:#6b7280;padding:3px 0;">SMA(200) on {s.timeframe}</td>
              <td style="text-align:right;">{fmt(s.sma)}</td></tr>
          <tr><td style="color:#6b7280;padding:3px 0;">yfinance ticker</td>
              <td style="text-align:right;color:#6b7280;">{s.ticker}</td></tr>
        </table>
      </td></tr>
    </table>"""


def build_divergence_email(signals: List[DivergenceSignal]) -> Tuple[str, str]:
    """Return (subject, html_body) for a batch of aligned divergences."""
    count = len(signals)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    tfs = ", ".join(sorted({s.timeframe for s in signals},
                           key=parse_tf_minutes))
    subject = (f"[V5 Divergence] {count} aligned signal"
               f"{'s' if count != 1 else ''} — {tfs} — {now_str} UTC")
    cards = "\n".join(_signal_card(s) for s in signals)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="background:#f3f4f6;margin:0;padding:24px;
             font-family:Arial,Helvetica,sans-serif;">
  <table cellpadding="0" cellspacing="0" border="0"
         style="max-width:680px;margin:0 auto;"><tr><td>
    <h1 style="color:#111827;font-size:22px;margin:0 0 6px;">
      V5 Swing + MACD Divergence</h1>
    <p style="color:#6b7280;font-size:14px;margin:0 0 24px;">
      {now_str} UTC &middot; {count} trend-ALIGNED divergence{'s' if count != 1 else ''}
      &middot; LEFT/RIGHT 2/2 &middot; span 6-50 &middot; chart-native 200-SMA</p>
    {cards}
    <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:20px;">
      Context signal only — divergence+trend alignment showed no standalone
      OOS edge in this project's testing. Not financial advice.</p>
  </td></tr></table></body></html>"""
    return subject, html
