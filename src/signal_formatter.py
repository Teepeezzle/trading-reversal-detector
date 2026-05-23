"""Render :class:`ReversalSignal` instances as fixed-format alert blocks."""

from __future__ import annotations

from .reversal_detector import ReversalSignal

SEPARATOR = "═══════════════════════════════════════"


def _format_price(value: float, ticker: str) -> str:
    """Format a price with sensible precision for the instrument.

    Forex pairs (the JPY-quoted ones excepted) need 5 decimals; commodities and
    crypto are 2 decimals.

    Args:
        value: Price to format.
        ticker: Yahoo-Finance symbol — drives precision selection.

    Returns:
        A string like ``"$1,922.30"`` or ``"$1.07845"``.
    """
    if ticker.endswith("=X"):
        # Most forex pairs use 5 decimals; JPY-quoted pairs use 3
        if "JPY" in ticker:
            return f"${value:,.3f}"
        return f"${value:,.5f}"
    return f"${value:,.2f}"


def _signed_pct(entry: float, target: float) -> str:
    """Return a percent-change string with explicit sign.

    Args:
        entry: Entry price.
        target: Target price (SL/TP).

    Returns:
        e.g. ``"+0.42%"`` or ``"-0.21%"``.
    """
    if entry == 0:
        return "+0.00%"
    pct = (target - entry) / entry * 100.0
    return f"{pct:+.2f}%"


def _signed_dollars(entry: float, target: float, ticker: str) -> str:
    """Return a signed price-distance string in the instrument's unit.

    Args:
        entry: Entry price.
        target: Target price (SL/TP).
        ticker: Yahoo-Finance symbol — drives precision.

    Returns:
        e.g. ``"+$8.10"`` or ``"-$4.10"``.
    """
    diff = target - entry
    sign = "+" if diff >= 0 else "-"
    abs_diff = abs(diff)
    if ticker.endswith("=X"):
        if "JPY" in ticker:
            body = f"${abs_diff:,.3f}"
        else:
            body = f"${abs_diff:,.5f}"
    else:
        body = f"${abs_diff:,.2f}"
    return f"{sign}{body}"


def format_signal(signal: ReversalSignal) -> str:
    """Render a single signal as a fixed-width alert block.

    Args:
        signal: The signal to render.

    Returns:
        A multi-line string ready for stdout / log files.
    """
    direction_arrow = "📈" if signal.direction == "LONG" else "📉"

    entry = signal.entry_price
    sl = signal.stop_loss
    tp1 = signal.tp1
    tp2 = signal.tp2

    asset_line = f"{signal.ticker_display_name} ({signal.ticker})"
    direction_line = f"{signal.direction} {direction_arrow}"
    level_line = (
        f"{signal.level_type} {signal.level_name} @ "
        f"{_format_price(signal.level_price, signal.ticker)}"
    )

    entry_str = _format_price(entry, signal.ticker)
    sl_str = (
        f"{_format_price(sl, signal.ticker)}  "
        f"({_signed_pct(entry, sl)} | {_signed_dollars(entry, sl, signal.ticker)})"
    )
    tp1_str = (
        f"{_format_price(tp1, signal.ticker)}  "
        f"({_signed_pct(entry, tp1)} | {_signed_dollars(entry, tp1, signal.ticker)})"
        f"  → Close 50%"
    )
    tp2_str = (
        f"{_format_price(tp2, signal.ticker)}  "
        f"({_signed_pct(entry, tp2)} | {_signed_dollars(entry, tp2, signal.ticker)})"
        f" → Close 50%"
    )

    confidence_str = f"{int(round(signal.confidence_score))}%"
    timestamp_str = signal.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

    reason_indent = " " * 14
    reason_wrapped = signal.reason_string.replace(
        "RSI ", f"\n{reason_indent}RSI ", 1
    )

    lines = [
        SEPARATOR,
        "🔔 REVERSAL SIGNAL DETECTED",
        SEPARATOR,
        f"Asset:        {asset_line}",
        f"Direction:    {direction_line}",
        f"Level:        {level_line}",
    ]

    # Only surface Interval/Session for intraday scans — daily scans keep the
    # original line layout from the spec.
    if signal.interval != "1d":
        lines.append(f"Interval:     {signal.interval}")
        lines.append(f"Session:      {signal.session}")

    lines.extend(
        [
            f"Entry Price:  {entry_str}",
            f"Stop Loss:    {sl_str}",
            f"Take Profit 1: {tp1_str}",
            f"Take Profit 2: {tp2_str}",
            f"Confidence:   {confidence_str}",
            f"Reason:       {reason_wrapped}",
            f"Timestamp:    {timestamp_str}",
        ]
    )

    if signal.blocked:
        lines.append(f"⚠️  BLOCKED:    {signal.blocked_reason}")

    lines.append(SEPARATOR)
    return "\n".join(lines)


def format_signals(signals: list[ReversalSignal]) -> str:
    """Render a list of signals separated by blank lines.

    Args:
        signals: Signals to render.

    Returns:
        Combined multi-line string; empty string if the list is empty.
    """
    if not signals:
        return ""
    return "\n\n".join(format_signal(s) for s in signals)
