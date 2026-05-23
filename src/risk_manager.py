"""Position sizing, SL/TP placement, and session-level risk guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .reversal_detector import ReversalSignal


@dataclass
class RiskParameters:
    """Static risk knobs loaded from ``config.yaml``.

    Attributes:
        account_balance: Notional account balance used for sizing.
        risk_per_trade_pct: Percent of balance risked per trade (e.g. 2.0).
        max_daily_loss_pct: Hard daily loss limit (e.g. 6.0).
        max_concurrent_positions: Cap on simultaneous active signals.
        max_positions_per_class: Cap per asset class (forex/metals/oil/crypto).
        atr_sl_multiplier: ATR multiple used to place the SL beyond the level.
        tp1_r_multiple: R-multiple used for TP1 (typically 2.0).
        tp2_r_multiple: R-multiple used for TP2 (typically 4.0).
    """

    account_balance: float
    risk_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 6.0
    max_concurrent_positions: int = 8
    max_positions_per_class: int = 3
    atr_sl_multiplier: float = 1.0
    tp1_r_multiple: float = 2.0
    tp2_r_multiple: float = 4.0


@dataclass
class SessionState:
    """Mutable per-run risk state — passed explicitly, never global.

    Attributes:
        daily_pnl: Realised P&L for the session (negative = loss).
        active_signals: Count of signals currently considered open.
        signals_per_class: Per-asset-class active-signal counters.
    """

    daily_pnl: float = 0.0
    active_signals: int = 0
    signals_per_class: Dict[str, int] = field(default_factory=dict)


@dataclass
class RiskResult:
    """Computed risk numbers for a signal.

    Attributes:
        stop_loss: SL price.
        tp1: TP1 price.
        tp2: TP2 price.
        risk_distance: Absolute price distance between entry and SL.
        position_size_units: Units that bring per-trade risk to the configured %.
        risk_amount: Dollar amount risked.
        blocked: True if a risk guardrail prevents taking the signal.
        blocked_reason: Human-readable explanation when blocked.
    """

    stop_loss: float
    tp1: float
    tp2: float
    risk_distance: float
    position_size_units: float
    risk_amount: float
    blocked: bool = False
    blocked_reason: str = ""


def _ticker_class(ticker: str, tickers_by_class: Dict[str, list]) -> str:
    """Return the asset-class name for a ticker.

    Args:
        ticker: Yahoo-Finance symbol.
        tickers_by_class: Mapping from class name (e.g. ``"forex"``) to ticker list.

    Returns:
        The matching class name, or ``"unknown"`` if not found.
    """
    for klass, members in tickers_by_class.items():
        if ticker in members:
            return klass
    return "unknown"


def calculate_risk(
    signal: ReversalSignal,
    atr: float,
    params: RiskParameters,
) -> RiskResult:
    """Compute SL/TP and position size for a single signal.

    The SL is placed one ATR multiple *beyond* the pierced level (below for
    longs, above for shorts) — not beyond the entry — so the rejection wick is
    given room.

    Args:
        signal: The freshly-detected signal (entry & level_price must be set).
        atr: Latest ATR value (must be > 0).
        params: Static risk parameters.

    Returns:
        A populated :class:`RiskResult`.

    Raises:
        ValueError: If ``atr`` is non-positive or risk distance collapses to 0.
    """
    if atr <= 0:
        raise ValueError("ATR must be positive to compute risk")

    entry = signal.entry_price
    level = signal.level_price
    multiplier = params.atr_sl_multiplier

    if signal.direction == "LONG":
        stop_loss = level - multiplier * atr
        risk_distance = entry - stop_loss
        if risk_distance <= 0:
            raise ValueError("LONG risk distance must be positive (entry above SL)")
        tp1 = entry + params.tp1_r_multiple * risk_distance
        tp2 = entry + params.tp2_r_multiple * risk_distance
    elif signal.direction == "SHORT":
        stop_loss = level + multiplier * atr
        risk_distance = stop_loss - entry
        if risk_distance <= 0:
            raise ValueError("SHORT risk distance must be positive (SL above entry)")
        tp1 = entry - params.tp1_r_multiple * risk_distance
        tp2 = entry - params.tp2_r_multiple * risk_distance
    else:
        raise ValueError(f"Unknown direction: {signal.direction}")

    risk_amount = params.account_balance * (params.risk_per_trade_pct / 100.0)
    position_size_units = risk_amount / risk_distance

    return RiskResult(
        stop_loss=float(stop_loss),
        tp1=float(tp1),
        tp2=float(tp2),
        risk_distance=float(risk_distance),
        position_size_units=float(position_size_units),
        risk_amount=float(risk_amount),
    )


def apply_risk_limits(
    signal: ReversalSignal,
    risk: RiskResult,
    session: SessionState,
    params: RiskParameters,
    tickers_by_class: Dict[str, list],
) -> RiskResult:
    """Stamp ``blocked``/``blocked_reason`` based on session guardrails.

    Limits checked, in order:

    * Daily loss limit reached.
    * Total concurrent-signal cap.
    * Per-asset-class signal cap.

    Args:
        signal: The signal being considered.
        risk: Pre-computed risk numbers.
        session: Mutable session state (read-only here — see :func:`register_signal`).
        params: Static risk parameters.
        tickers_by_class: Mapping used to classify the ticker.

    Returns:
        A new :class:`RiskResult` with ``blocked``/``blocked_reason`` set.
    """
    daily_loss_limit = params.account_balance * (params.max_daily_loss_pct / 100.0)
    if session.daily_pnl <= -daily_loss_limit:
        risk.blocked = True
        risk.blocked_reason = (
            f"Daily loss limit reached "
            f"({session.daily_pnl:,.2f} <= -{daily_loss_limit:,.2f})"
        )
        return risk

    if session.active_signals >= params.max_concurrent_positions:
        risk.blocked = True
        risk.blocked_reason = (
            f"Max concurrent signals reached "
            f"({session.active_signals}/{params.max_concurrent_positions})"
        )
        return risk

    klass = _ticker_class(signal.ticker, tickers_by_class)
    per_class = session.signals_per_class.get(klass, 0)
    if per_class >= params.max_positions_per_class:
        risk.blocked = True
        risk.blocked_reason = (
            f"Max signals for asset class '{klass}' reached "
            f"({per_class}/{params.max_positions_per_class})"
        )
        return risk

    return risk


def register_signal(
    signal: ReversalSignal,
    session: SessionState,
    tickers_by_class: Dict[str, list],
) -> None:
    """Increment the session counters after a *non-blocked* signal is accepted.

    Args:
        signal: The accepted signal.
        session: Session state to mutate in place.
        tickers_by_class: Mapping used to classify the ticker.
    """
    if signal.blocked:
        return
    session.active_signals += 1
    klass = _ticker_class(signal.ticker, tickers_by_class)
    session.signals_per_class[klass] = session.signals_per_class.get(klass, 0) + 1
