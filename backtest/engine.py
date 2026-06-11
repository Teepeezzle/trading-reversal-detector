"""Bar-by-bar replay backtester for the deployed reversal detector.

Faithfulness rules:
    * Signal logic is imported from ``src`` — the deployed code, unmodified.
    * At every evaluation point only data with timestamps <= "now" is visible.
    * Price levels are always computed from daily data (as deployed), with a
      synthetic *partial* today-bar appended intraday — exactly what yfinance
      hands the live scanner mid-session.
    * The detector sees a trailing window matched to the deployed fetch period
      (e.g. 1h is fetched with period="30d" live, so the replay window is
      ~720 bars), not unlimited history.

Deliberate generosity (stated, so results are an upper bound):
    * The replay evaluates only **completed** bars. The deployed 4h cron
      actually evaluates partially-formed buckets (see repaint_check.py),
      which is strictly worse than what is simulated here.

Execution model:
    * Entry at the NEXT bar's open, with adverse slippage of N ticks.
    * SL/TP from the deployed risk manager (SL = level +/- 1*ATR, TP1 = 2R
      close 50%, TP2 = 4R close 50%, no stop move after TP1 — as deployed).
    * Stops fill with adverse slippage; TPs fill at the limit price.
    * Same-bar SL+TP ambiguity resolves to SL first (conservative).
    * Commission charged once per trade on entry notional (user-specified
      0.05% "per trade").
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.indicators import compute_atr, compute_rsi, compute_volume_ma  # noqa: E402
from src.price_levels import compute_price_levels  # noqa: E402
from src.reversal_detector import detect_reversals  # noqa: E402
from src.risk_manager import RiskParameters, calculate_risk  # noqa: E402

# Trailing window the detector sees, matched to the deployed fetch periods.
WINDOW_BARS: Dict[str, int] = {
    "5m": 1380,   # ~5 trading days of 5m bars (deployed period=5d)
    "15m": 480,   # ~5 trading days of 15m bars (deployed period=5d)
    "1h": 720,    # ~30 days of 1h bars (deployed period=30d)
    "4h": 360,    # ~60 days of 4h bars (deployed period=60d)
    "1d": 252,    # ~1 year of daily bars (deployed period=1y)
}

# Minimum tick size per asset, used for the slippage model.
TICK_SIZE: Dict[str, float] = {
    "BTC-USD": 0.01,
    "GC=F": 0.10,
    "SI=F": 0.005,
    "CL=F": 0.01,
    "BZ=F": 0.01,
    "DX-Y.NYB": 0.005,
    "NQ=F": 0.25,
}

ACCOUNT_BALANCE = 10_000.0
RISK_PCT = 1.0           # user-specified 1% risk per trade
COMMISSION_PCT = 0.0005  # user-specified 0.05% per trade (on entry notional)
SLIPPAGE_TICKS = 2       # user-specified
DEDUPE_BARS = 12         # suppress identical (level,dir) re-fires for N bars


@dataclass
class BacktestTrade:
    """One simulated trade produced by a replayed signal."""

    ticker: str
    timeframe: str
    direction: str
    level_type: str
    level_name: str
    level_price: float
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    atr_at_signal: float
    confidence: float
    self_touch: bool          # prev-bar extreme IS the level (vacuous touch)
    efficiency_ratio: float   # trend/range proxy at signal time
    exit_time: Optional[pd.Timestamp] = None
    outcome: str = "open"     # 'sl' | 'tp1_sl' | 'tp2' | 'open'
    pnl_usd: float = 0.0
    r_multiple: float = 0.0


@dataclass
class CellResult:
    """Aggregated metrics for one (asset, timeframe) backtest cell."""

    ticker: str
    timeframe: str
    span_days: float
    trades: List[BacktestTrade] = field(default_factory=list)

    @property
    def closed(self) -> List[BacktestTrade]:
        return [t for t in self.trades if t.outcome != "open"]

    def metrics(self) -> Dict[str, float | int | str]:
        """Compute the summary statistics for this cell."""
        closed = self.closed
        n = len(closed)
        out: Dict[str, float | int | str] = {
            "ticker": self.ticker,
            "timeframe": self.timeframe,
            "signals": len(self.trades),
            "closed_trades": n,
            "open_at_end": len(self.trades) - n,
            "signals_per_week": round(len(self.trades) / max(self.span_days / 7.0, 1e-9), 2),
        }
        if n == 0:
            out.update({"win_rate_pct": "n/a", "profit_factor": "n/a",
                        "avg_win_usd": "n/a", "avg_loss_usd": "n/a",
                        "net_pnl_usd": 0.0, "max_dd_pct": "n/a", "sharpe": "n/a"})
            return out

        pnls = np.array([t.pnl_usd for t in closed])
        wins = pnls[pnls > 0]
        losses = pnls[pnls <= 0]
        gross_win = wins.sum() if len(wins) else 0.0
        gross_loss = -losses.sum() if len(losses) else 0.0

        out["win_rate_pct"] = round(100.0 * len(wins) / n, 1)
        out["profit_factor"] = (
            round(gross_win / gross_loss, 2) if gross_loss > 0 else "inf"
        )
        out["avg_win_usd"] = round(wins.mean(), 2) if len(wins) else 0.0
        out["avg_loss_usd"] = round(losses.mean(), 2) if len(losses) else 0.0
        out["net_pnl_usd"] = round(pnls.sum(), 2)

        # Equity curve on exit timestamps; max drawdown vs running peak.
        order = np.argsort([t.exit_time.value for t in closed])
        equity = ACCOUNT_BALANCE + np.cumsum(pnls[order])
        peak = np.maximum.accumulate(np.concatenate([[ACCOUNT_BALANCE], equity]))
        dd = (np.concatenate([[ACCOUNT_BALANCE], equity]) - peak) / peak
        out["max_dd_pct"] = round(100.0 * dd.min(), 2)

        # Daily Sharpe across the full span (flat days included), annualised.
        daily = pd.Series(
            pnls[order],
            index=pd.DatetimeIndex([closed[i].exit_time for i in order]),
        ).resample("1D").sum()
        full_range = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
        daily = daily.reindex(full_range, fill_value=0.0) / ACCOUNT_BALANCE
        if len(daily) > 5 and daily.std() > 0:
            out["sharpe"] = round(float(daily.mean() / daily.std() * np.sqrt(252)), 2)
        else:
            out["sharpe"] = "n/a"
        return out


def _to_utc_naive(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise an OHLCV index to tz-naive UTC."""
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        df = df.copy()
        df.index = idx.tz_convert("UTC").tz_localize(None)
    return df


def _macro_trend(daily_closes: np.ndarray, window: int = 200, slope_lb: int = 20) -> int:
    """Daily macro-trend label from a 200-day SMA and its slope.

    Args:
        daily_closes: Array of completed daily closes (most recent last).
        window: SMA window. Defaults to 200.
        slope_lb: Bars back used to measure the SMA slope. Defaults to 20.

    Returns:
        +1 (uptrend), -1 (downtrend), or 0 (no dominant trend / insufficient
        history). Uptrend requires price above a rising SMA200; downtrend
        requires price below a falling SMA200.
    """
    n = len(daily_closes)
    if n < window + slope_lb:
        return 0
    sma_now = float(daily_closes[-window:].mean())
    sma_prev = float(daily_closes[-window - slope_lb : -slope_lb].mean())
    price = float(daily_closes[-1])
    if sma_now <= 0:
        return 0
    rising = (sma_now - sma_prev) / sma_now > 0.002
    falling = (sma_now - sma_prev) / sma_now < -0.002
    if price > sma_now and rising:
        return 1
    if price < sma_now and falling:
        return -1
    return 0


def _efficiency_ratio(close: np.ndarray, i: int, window: int = 20) -> float:
    """Kaufman efficiency ratio over the prior ``window`` bars (trend proxy).

    ~1.0 = clean trend; ~0.0 = pure chop/range.
    """
    if i < window:
        return float("nan")
    seg = close[i - window : i + 1]
    direction = abs(seg[-1] - seg[0])
    path = np.abs(np.diff(seg)).sum()
    return float(direction / path) if path > 0 else 0.0


def _build_daily_views(
    intra_df: pd.DataFrame, daily_df: pd.DataFrame
) -> Dict[pd.Timestamp, pd.DataFrame]:
    """For each calendar day in the intraday index, the daily frame visible
    at any time during that day: all completed prior days + nothing for today
    (the per-bar partial today-row is appended by the caller).
    """
    views: Dict[pd.Timestamp, pd.DataFrame] = {}
    daily_days = daily_df.index.normalize()
    for day in sorted(set(intra_df.index.normalize())):
        views[day] = daily_df[daily_days < day]
    return views


def _partial_today_bar(
    intra_df: pd.DataFrame, day_mask: np.ndarray, upto_idx: int, day: pd.Timestamp
) -> pd.DataFrame:
    """Synthesise the partial daily bar from today's intraday bars up to now."""
    rows = intra_df.iloc[: upto_idx + 1]
    today = rows[day_mask[: upto_idx + 1]]
    if today.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "Open": [today["Open"].iloc[0]],
            "High": [today["High"].max()],
            "Low": [today["Low"].min()],
            "Close": [today["Close"].iloc[-1]],
            "Volume": [today["Volume"].sum()],
        },
        index=[day],
    )


def replay(
    ticker: str,
    timeframe: str,
    intra_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    mode: str = "existing",
) -> CellResult:
    """Replay the detector across history and simulate the resulting trades.

    Args:
        ticker: yfinance symbol.
        timeframe: '5m' | '15m' | '1h' | '4h' | '1d'.
        intra_df: OHLCV at ``timeframe`` (for '1d' pass the daily frame).
        daily_df: daily OHLCV used for level computation.
        mode: 'existing' replays deployed behaviour exactly; 'fixed' applies
            the corrected level exclusion + close-back proximity gate.

    Returns:
        A populated :class:`CellResult`.
    """
    intra_df = _to_utc_naive(intra_df)
    daily_df = _to_utc_naive(daily_df)

    window = WINDOW_BARS[timeframe]
    n = len(intra_df)
    if n < 80:
        return CellResult(ticker, timeframe, span_days=0.0)

    # Causal indicators precomputed once on the full series; after warm-up
    # these match per-window recomputation to within noise.
    rsi_full = compute_rsi(intra_df["Close"])
    atr_full = compute_atr(intra_df)
    vma_full = compute_volume_ma(intra_df["Volume"])
    closes = intra_df["Close"].to_numpy()
    highs = intra_df["High"].to_numpy()
    lows = intra_df["Low"].to_numpy()
    opens = intra_df["Open"].to_numpy()

    is_intraday = timeframe != "1d"
    if is_intraday:
        daily_views = _build_daily_views(intra_df, daily_df)
        day_norm = intra_df.index.normalize()

    tick = TICK_SIZE.get(ticker, 0.01)
    slip = SLIPPAGE_TICKS * tick
    params = RiskParameters(account_balance=ACCOUNT_BALANCE, risk_per_trade_pct=RISK_PCT)

    # Existing mode calls the deployed signatures exactly (no extra kwargs).
    # Fixed mode opts into the corrected parameters added to src during the
    # fix phase. Keeping them in kwargs means the existing run is byte-for-byte
    # the deployed code path.
    level_kwargs: Dict[str, int] = {}
    detector_kwargs: Dict[str, object] = {}
    apply_macro = mode == "macro"
    if mode in ("fixed", "macro"):
        level_kwargs["exclude_last"] = 2 if timeframe == "1d" else 1
        detector_kwargs.update(
            max_closeback_atr=1.0,       # rejection close must be within 1 ATR of level
            require_true_pierce=True,    # wick must actually trade through the level
            min_efficiency_ratio=0.30,   # skip chop/range (counter-trend death zone)
            volume_required=True,        # no soft-pass on zero-volume instruments
            dedupe_levels=True,          # collapse coincident D/W/M/Y duplicates
        )

    trades: List[BacktestTrade] = []
    last_fire: Dict[Tuple[str, str, str], int] = {}
    level_cache_key: Optional[Tuple] = None
    cached_levels = None
    cached_macro = 0

    warmup = max(60, 2 * 14 + 5)
    for i in range(warmup, n - 1):  # need bar i+1 for entry
        ts = intra_df.index[i]

        # --- build the daily view visible at time ts ----------------------
        if is_intraday:
            day = day_norm[i]
            base = daily_views[day]
            if len(base) < 30:
                continue
            # The deployed compute_price_levels uses iloc[-2] for the daily
            # level and iloc[:-1] for W/M/Y, so the partial today-row never
            # changes the levels within a day -> cache per day.
            if day != level_cache_key:
                partial = _partial_today_bar(intra_df, np.asarray(day_norm == day), i, day)
                daily_view = pd.concat([base, partial]) if not partial.empty else base
                try:
                    cached_levels = compute_price_levels(ticker, daily_view, **level_kwargs)
                except Exception:
                    cached_levels = None
                # Macro trend from completed daily closes (per-day, cached).
                cached_macro = _macro_trend(base["Close"].to_numpy()) if apply_macro else 0
                level_cache_key = day
            levels = cached_levels
        else:
            try:
                levels = compute_price_levels(
                    ticker, intra_df.iloc[: i + 1], **level_kwargs
                )
            except Exception:
                levels = None
            cached_macro = _macro_trend(intra_df["Close"].to_numpy()[:i]) if apply_macro else 0
        if levels is None:
            continue

        lo = max(0, i + 1 - window)
        df_win = intra_df.iloc[lo : i + 1]
        rsi_win = rsi_full.iloc[lo : i + 1]
        vma_win = vma_full.iloc[lo : i + 1]
        atr_val = float(atr_full.iloc[i]) if np.isfinite(atr_full.iloc[i]) else 0.0
        if atr_val <= 0:
            continue

        sigs = detect_reversals(
            ticker=ticker,
            ticker_name=ticker,
            df=df_win,
            levels=levels,
            rsi_series=rsi_win,
            volume_ma_series=vma_win,
            atr_value=atr_val,
            interval=timeframe,
            session_filter="all",
            macro_trend=(cached_macro if apply_macro else None),
            **detector_kwargs,
        )

        for sig in sigs:
            key = (sig.level_type, sig.level_name, sig.direction)
            if i - last_fire.get(key, -10**9) < DEDUPE_BARS:
                continue
            last_fire[key] = i

            # --- execution: fill at next bar open with adverse slippage ---
            fill = opens[i + 1] + (slip if sig.direction == "LONG" else -slip)
            sig.entry_price = float(fill)
            try:
                risk = calculate_risk(sig, atr_val, params)
            except ValueError:
                continue  # geometry impossible at the actual fill

            prev_extreme = lows[i - 1] if sig.direction == "LONG" else highs[i - 1]
            trade = BacktestTrade(
                ticker=ticker,
                timeframe=timeframe,
                direction=sig.direction,
                level_type=sig.level_type,
                level_name=sig.level_name,
                level_price=sig.level_price,
                signal_time=ts,
                entry_time=intra_df.index[i + 1],
                entry_price=float(fill),
                stop_loss=risk.stop_loss,
                tp1=risk.tp1,
                tp2=risk.tp2,
                atr_at_signal=atr_val,
                confidence=sig.confidence_score,
                self_touch=abs(prev_extreme - sig.level_price)
                <= 1e-9 * max(1.0, abs(sig.level_price)),
                efficiency_ratio=_efficiency_ratio(closes, i),
            )
            _simulate_exit(trade, highs, lows, intra_df.index, i + 1, slip)
            trades.append(trade)

    span = (intra_df.index[-1] - intra_df.index[0]).total_seconds() / 86400.0
    result = CellResult(ticker, timeframe, span_days=span)
    result.trades = trades
    return result


def _simulate_exit(
    trade: BacktestTrade,
    highs: np.ndarray,
    lows: np.ndarray,
    index: pd.DatetimeIndex,
    start: int,
    slip: float,
) -> None:
    """Walk forward from entry and resolve the trade in place.

    Scale-out accounting at 1% account risk (=$100 of risk):
        SL outright           -> -1.0R
        TP1 then SL (no BE)   -> +0.5R
        TP1 then TP2          -> +3.0R
    Commission (0.05% of entry notional) is then subtracted once.
    """
    risk_usd = ACCOUNT_BALANCE * RISK_PCT / 100.0
    risk_dist = abs(trade.entry_price - trade.stop_loss)
    units = risk_usd / risk_dist
    commission = COMMISSION_PCT * units * trade.entry_price

    long = trade.direction == "LONG"
    tp1_hit = False
    n = len(highs)

    for j in range(start, n):
        hi, lo_ = highs[j], lows[j]
        if long:
            sl_hit = lo_ <= trade.stop_loss
            t1 = hi >= trade.tp1
            t2 = hi >= trade.tp2
        else:
            sl_hit = hi >= trade.stop_loss
            t1 = lo_ <= trade.tp1
            t2 = lo_ <= trade.tp2

        if sl_hit:  # same-bar ambiguity: stop first (conservative)
            r = 0.5 if tp1_hit else -1.0
            # stop fills with adverse slippage
            slip_r = (slip * units * (0.5 if tp1_hit else 1.0)) / risk_usd
            trade.r_multiple = r - slip_r
            trade.pnl_usd = trade.r_multiple * risk_usd - commission
            trade.outcome = "tp1_sl" if tp1_hit else "sl"
            trade.exit_time = index[j]
            return
        if not tp1_hit and t1:
            tp1_hit = True
        if tp1_hit and t2:
            trade.r_multiple = 3.0
            trade.pnl_usd = 3.0 * risk_usd - commission
            trade.outcome = "tp2"
            trade.exit_time = index[j]
            return

    trade.outcome = "open"  # unresolved at data end; excluded from stats


def trades_to_frame(results: List[CellResult]) -> pd.DataFrame:
    """Flatten all trades from a list of cells into one DataFrame."""
    rows = []
    for cell in results:
        for t in cell.trades:
            rows.append(
                {
                    "ticker": t.ticker,
                    "timeframe": t.timeframe,
                    "direction": t.direction,
                    "level_type": t.level_type,
                    "level_name": t.level_name,
                    "signal_time": t.signal_time,
                    "entry_time": t.entry_time,
                    "entry": t.entry_price,
                    "sl": t.stop_loss,
                    "tp1": t.tp1,
                    "tp2": t.tp2,
                    "outcome": t.outcome,
                    "pnl_usd": t.pnl_usd,
                    "r_multiple": t.r_multiple,
                    "confidence": t.confidence,
                    "self_touch": t.self_touch,
                    "efficiency_ratio": t.efficiency_ratio,
                    "hour_utc": t.signal_time.hour,
                }
            )
    return pd.DataFrame(rows)
