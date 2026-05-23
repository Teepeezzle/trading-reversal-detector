"""Unit tests for the Trading Reversal Detector.

All tests use synthetic OHLCV frames — no network calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Make the package importable when running ``pytest`` from the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.indicators import (  # noqa: E402
    Indicators,
    compute_atr,
    compute_indicators,
    compute_rsi,
    compute_volume_ma,
)
from src.price_levels import compute_price_levels  # noqa: E402
from src.reversal_detector import (  # noqa: E402
    ReversalSignal,
    _find_swing_highs,
    _find_swing_lows,
    detect_reversals,
)
from src.risk_manager import (  # noqa: E402
    RiskParameters,
    SessionState,
    apply_risk_limits,
    calculate_risk,
)
from src.signal_formatter import format_signal  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic OHLCV builders
# ---------------------------------------------------------------------------


def _build_df(closes, highs=None, lows=None, opens=None, volumes=None):
    """Build an OHLCV DataFrame from arrays.

    Defaults: high = close + 0.5, low = close - 0.5, open = close,
    volume = 1000.
    """
    n = len(closes)
    closes = np.asarray(closes, dtype=float)
    if highs is None:
        highs = closes + 0.5
    if lows is None:
        lows = closes - 0.5
    if opens is None:
        opens = closes.copy()
    if volumes is None:
        volumes = np.full(n, 1000.0)
    dates = pd.date_range(end="2025-01-30", periods=n, freq="D")
    return pd.DataFrame(
        {
            "Open": np.asarray(opens, dtype=float),
            "High": np.asarray(highs, dtype=float),
            "Low": np.asarray(lows, dtype=float),
            "Close": closes,
            "Volume": np.asarray(volumes, dtype=float),
        },
        index=dates,
    )


def _build_bullish_reversal_df(level: float = 95.0) -> pd.DataFrame:
    """Construct OHLCV data that should trigger a LONG signal at ``level``.

    Pattern (n=50 so the RSI(14) warm-up is well past both swing points):
        * idx 0-14:  flat-ish at ~110 (gives RSI a calm baseline of ~50).
        * idx 15-19: sharp decline 108.2 → 101.0 (RSI plummets).
        * idx 20:    Close 101.0, Low 100.0  → swing low #1, low RSI.
        * idx 21-30: strong recovery 101 → ~110 (RSI rebuilds).
        * idx 31-34: minor drift 109.5 → 108.0 (RSI flattens).
        * idx 35:    PIN BAR — Close 105.0 (small dip), Low 95.0
                     → swing low #2: Lower Low in price but RSI stays much
                     higher than idx 20 because the close barely moved.
        * idx 36-44: gentle recovery 105.2 → 106.8.
        * idx 45-47: drift down to ~97 approaching support.
        * idx 48 (previous candle): Low 94.5 — pierces level 95.
        * idx 49 (current candle):  Close 97.0 — closed back inside.
        * Volume[49] = 3000 vs ~1000 average → 3× confirmation.

    Returns:
        A 50-row OHLCV DataFrame.
    """
    n = 50
    closes = np.full(n, 110.0)
    lows = closes - 0.5
    highs = closes + 0.5
    volumes = np.full(n, 1000.0)

    # idx 0-14: flat baseline at 110 (RSI ~ 50)
    for i in range(15):
        closes[i] = 110.0 + (0.1 if i % 2 == 0 else -0.1)
        lows[i] = closes[i] - 0.5
        highs[i] = closes[i] + 0.5

    # idx 15-19: sharp decline into swing low 1
    for i in range(15, 20):
        closes[i] = 110.0 - (i - 14) * 1.8
        lows[i] = closes[i] - 0.5
        highs[i] = closes[i] + 0.5

    # idx 20: swing low #1 — close 101, low wick to 100
    closes[20] = 101.0
    lows[20] = 100.0
    highs[20] = 102.0

    # idx 21-30: strong recovery — rebuilds RSI
    for i in range(21, 31):
        closes[i] = 101.0 + (i - 20) * 0.9
        lows[i] = closes[i] - 0.5
        highs[i] = closes[i] + 0.5

    # idx 31-34: minor drift down
    for i in range(31, 35):
        closes[i] = 110.0 - (i - 30) * 0.5
        lows[i] = closes[i] - 0.5
        highs[i] = closes[i] + 0.5

    # idx 35: PIN BAR — close stays high, low wicks below idx 20's low
    closes[35] = 105.0
    lows[35] = 95.0
    highs[35] = 106.0

    # idx 36-44: gentle recovery
    for i in range(36, 45):
        closes[i] = 105.0 + (i - 35) * 0.2
        lows[i] = closes[i] - 0.5
        highs[i] = closes[i] + 0.5

    # idx 45-47: drift down toward support
    for i, value in enumerate([99.0, 98.0, 97.0], start=45):
        closes[i] = value
        lows[i] = value - 0.5
        highs[i] = value + 0.5

    # idx 48 (previous candle): pierces level
    closes[48] = 96.0
    lows[48] = 94.5
    highs[48] = 97.0

    # idx 49 (current candle): closes back inside
    closes[49] = 97.0
    lows[49] = 95.5
    highs[49] = 97.5

    # Volume confirmation on rejection candle
    volumes[49] = 3000.0

    opens = closes.copy()
    return _build_df(closes, highs=highs, lows=lows, opens=opens, volumes=volumes)


def _build_no_divergence_df(level: float = 95.0) -> pd.DataFrame:
    """OHLCV data that satisfies conditions 1-2 + 4 but *fails* divergence.

    Both swing lows are at the same Low value (96.0), so price has NOT made
    a lower low — bullish divergence requires price LL + RSI HL, and the
    first half fails. A correctly-implemented detector must NOT fire.
    """
    n = 50
    closes = np.full(n, 100.0)
    lows = closes - 0.5
    highs = closes + 0.5
    volumes = np.full(n, 1000.0)

    # idx 0-14: flat at 100
    for i in range(15):
        closes[i] = 100.0
        lows[i] = 99.5
        highs[i] = 100.5

    # idx 15-19: gentle dip
    for i in range(15, 20):
        closes[i] = 100.0 - (i - 14) * 0.5
        lows[i] = closes[i] - 0.5
        highs[i] = closes[i] + 0.5

    # idx 20: swing low #1 at 96.0
    closes[20] = 97.5
    lows[20] = 96.0
    highs[20] = 98.0

    # idx 21-34: recovery and drift back
    for i in range(21, 35):
        closes[i] = 97.5 + (i - 20) * 0.2
        lows[i] = closes[i] - 0.5
        highs[i] = closes[i] + 0.5

    # idx 35: swing low #2 at SAME 96.0 (no Lower Low → no divergence)
    closes[35] = 97.5
    lows[35] = 96.0
    highs[35] = 98.0

    # idx 36-44: gentle recovery
    for i in range(36, 45):
        closes[i] = 97.5 + (i - 35) * 0.2
        lows[i] = closes[i] - 0.5
        highs[i] = closes[i] + 0.5

    # idx 45-47: drift down toward level
    for i, value in enumerate([99.0, 98.0, 97.0], start=45):
        closes[i] = value
        lows[i] = value - 0.5
        highs[i] = value + 0.5

    # idx 48: previous candle pierces level
    closes[48] = 96.0
    lows[48] = 94.5
    highs[48] = 97.0

    # idx 49: closes back inside
    closes[49] = 97.0
    lows[49] = 95.5
    highs[49] = 97.5
    volumes[49] = 3000.0

    opens = closes.copy()
    return _build_df(closes, highs=highs, lows=lows, opens=opens, volumes=volumes)


# ---------------------------------------------------------------------------
# Indicator tests
# ---------------------------------------------------------------------------


def test_rsi_bounds():
    """RSI must stay within [0, 100] for any realistic series."""
    np.random.seed(0)
    closes = pd.Series(100 + np.cumsum(np.random.randn(200)))
    rsi = compute_rsi(closes, period=14)
    valid = rsi.dropna()
    assert len(valid) > 0
    assert (valid >= 0).all()
    assert (valid <= 100).all()


def test_rsi_all_gains_yields_100():
    """A monotonically increasing series should drive RSI to ~100."""
    closes = pd.Series(np.arange(1, 51, dtype=float))
    rsi = compute_rsi(closes, period=14)
    assert rsi.iloc[-1] == pytest.approx(100.0, abs=1e-6)


def test_atr_is_positive():
    """ATR must be non-negative across a realistic frame."""
    np.random.seed(1)
    n = 100
    closes = 100 + np.cumsum(np.random.randn(n))
    highs = closes + np.random.rand(n) * 2
    lows = closes - np.random.rand(n) * 2
    df = _build_df(closes, highs=highs, lows=lows)
    atr = compute_atr(df, period=14)
    valid = atr.dropna()
    assert len(valid) > 0
    assert (valid >= 0).all()
    assert valid.iloc[-1] > 0


def test_volume_ma_window():
    """Volume-MA needs at least ``period`` bars before producing a value."""
    vol = pd.Series(np.arange(1, 41, dtype=float))
    ma = compute_volume_ma(vol, period=20)
    assert pd.isna(ma.iloc[18])
    assert ma.iloc[19] == pytest.approx(vol.iloc[:20].mean())


def test_compute_indicators_returns_dataclass():
    """``compute_indicators`` returns a populated ``Indicators`` instance."""
    np.random.seed(2)
    closes = 100 + np.cumsum(np.random.randn(60))
    df = _build_df(closes, volumes=np.full(60, 1500.0))
    ind = compute_indicators(df)
    assert isinstance(ind, Indicators)
    assert 0 <= ind.rsi <= 100
    assert ind.atr >= 0
    assert ind.volume_ma == pytest.approx(1500.0)


# ---------------------------------------------------------------------------
# Price-levels tests
# ---------------------------------------------------------------------------


def test_price_levels_uses_history_only():
    """The current candle must not define its own period extremes."""
    closes = np.linspace(100, 120, 60)
    df = _build_df(closes)
    df.iloc[-1, df.columns.get_loc("High")] = 999.0  # outlier on current candle
    df.iloc[-1, df.columns.get_loc("Low")] = -999.0

    levels = compute_price_levels("TEST", df)
    assert levels.yearly_high < 999.0
    assert levels.yearly_low > -999.0
    # Daily reference = previous candle (idx -2), not the outlier current
    assert levels.daily_high == pytest.approx(df.iloc[-2]["High"])
    assert levels.daily_low == pytest.approx(df.iloc[-2]["Low"])


# ---------------------------------------------------------------------------
# Swing-point helper tests
# ---------------------------------------------------------------------------


def test_find_swing_lows_simple():
    """Two clear V-shapes give exactly two swing lows."""
    series = pd.Series(
        [10, 9, 8, 7, 6, 5, 6, 7, 8, 9, 10, 9, 8, 7, 6, 4, 5, 6, 7, 8, 9, 10, 11]
    )
    swings = _find_swing_lows(series, lookback=5)
    assert len(swings) == 2
    assert series.iloc[swings[0]] == 5
    assert series.iloc[swings[1]] == 4


def test_find_swing_highs_simple():
    """Two clear peaks give exactly two swing highs."""
    series = pd.Series(
        [1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1, 2, 3, 4, 5, 7, 6, 5, 4, 3, 2, 1, 0]
    )
    swings = _find_swing_highs(series, lookback=5)
    assert len(swings) == 2
    assert series.iloc[swings[0]] == 6
    assert series.iloc[swings[1]] == 7


# ---------------------------------------------------------------------------
# Detector tests
# ---------------------------------------------------------------------------


def test_long_signal_triggers_on_close_back_with_divergence():
    """A textbook bullish close-back + divergence + volume spike fires LONG."""
    df = _build_bullish_reversal_df(level=95.0)
    ind = compute_indicators(df)

    # Stand-in PriceLevels — yearly_low = 95.0 is the level under test.
    from src.price_levels import PriceLevels

    levels = PriceLevels(
        ticker="TEST",
        daily_high=df.iloc[-2]["High"],
        daily_low=df.iloc[-2]["Low"],
        weekly_high=200.0,
        weekly_low=80.0,
        monthly_high=200.0,
        monthly_low=80.0,
        yearly_high=200.0,
        yearly_low=95.0,
    )

    signals = detect_reversals(
        ticker="TEST",
        ticker_name="Synthetic",
        df=df,
        levels=levels,
        rsi_series=ind.rsi_series,
        volume_ma_series=ind.volume_ma_series,
        atr_value=ind.atr,
        tolerance_pct=0.001,
        swing_lookback=5,
    )

    longs = [s for s in signals if s.direction == "LONG"]
    assert len(longs) >= 1, "Expected at least one LONG signal at yearly low=95"
    sig = next(s for s in longs if s.level_price == pytest.approx(95.0))
    assert sig.level_type == "Yearly"
    assert sig.level_name == "Low"
    assert sig.entry_price == pytest.approx(df.iloc[-1]["Close"])
    assert 0 <= sig.confidence_score <= 100


def test_no_signal_when_divergence_missing():
    """Same touch+close-back pattern but no RSI divergence → no signal."""
    df = _build_no_divergence_df(level=95.0)
    ind = compute_indicators(df)

    from src.price_levels import PriceLevels

    levels = PriceLevels(
        ticker="TEST",
        daily_high=df.iloc[-2]["High"],
        daily_low=df.iloc[-2]["Low"],
        weekly_high=200.0,
        weekly_low=80.0,
        monthly_high=200.0,
        monthly_low=80.0,
        yearly_high=200.0,
        yearly_low=95.0,
    )

    signals = detect_reversals(
        ticker="TEST",
        ticker_name="Synthetic",
        df=df,
        levels=levels,
        rsi_series=ind.rsi_series,
        volume_ma_series=ind.volume_ma_series,
        atr_value=ind.atr,
        tolerance_pct=0.001,
        swing_lookback=5,
    )

    longs_at_level = [
        s for s in signals if s.direction == "LONG" and s.level_price == pytest.approx(95.0)
    ]
    assert longs_at_level == [], "Detector fired without RSI divergence"


# ---------------------------------------------------------------------------
# Risk-manager tests
# ---------------------------------------------------------------------------


def _make_long_signal(entry: float = 100.0, level: float = 99.5) -> ReversalSignal:
    """Build a minimal LONG signal for risk-math tests."""
    from datetime import datetime, timezone

    return ReversalSignal(
        ticker="GC=F",
        ticker_display_name="Gold",
        direction="LONG",
        level_type="Monthly",
        level_name="Low",
        level_price=level,
        entry_price=entry,
        stop_loss=0.0,
        tp1=0.0,
        tp2=0.0,
        confidence_score=70.0,
        reason_string="test",
        timestamp=datetime.now(timezone.utc),
    )


def test_risk_manager_long_sl_tp():
    """SL/TP and position-size math for a LONG signal."""
    signal = _make_long_signal(entry=100.0, level=99.5)
    params = RiskParameters(account_balance=10_000.0, risk_per_trade_pct=2.0)
    result = calculate_risk(signal, atr=1.0, params=params)

    # SL = level - 1*ATR = 99.5 - 1.0 = 98.5
    assert result.stop_loss == pytest.approx(98.5)
    # Risk distance = entry - SL = 100 - 98.5 = 1.5
    assert result.risk_distance == pytest.approx(1.5)
    # TP1 = entry + 2R = 100 + 3.0 = 103.0
    assert result.tp1 == pytest.approx(103.0)
    # TP2 = entry + 4R = 100 + 6.0 = 106.0
    assert result.tp2 == pytest.approx(106.0)
    # Position size = ($10k * 2%) / 1.5 = $200 / 1.5
    assert result.position_size_units == pytest.approx(200.0 / 1.5)
    assert result.risk_amount == pytest.approx(200.0)


def test_risk_manager_short_sl_tp():
    """SL/TP math for a SHORT signal mirrors the LONG case."""
    signal = _make_long_signal(entry=100.0, level=100.5)
    signal.direction = "SHORT"
    params = RiskParameters(account_balance=10_000.0, risk_per_trade_pct=2.0)
    result = calculate_risk(signal, atr=1.0, params=params)

    assert result.stop_loss == pytest.approx(101.5)  # level + 1*ATR
    assert result.risk_distance == pytest.approx(1.5)
    assert result.tp1 == pytest.approx(97.0)  # entry - 2R
    assert result.tp2 == pytest.approx(94.0)  # entry - 4R


def test_risk_limits_block_when_concurrent_cap_reached():
    """Once ``active_signals`` >= cap, the next signal must be blocked."""
    signal = _make_long_signal()
    params = RiskParameters(
        account_balance=10_000.0,
        max_concurrent_positions=2,
        max_positions_per_class=5,
    )
    session = SessionState(active_signals=2)
    result = calculate_risk(signal, atr=1.0, params=params)
    result = apply_risk_limits(
        signal=signal,
        risk=result,
        session=session,
        params=params,
        tickers_by_class={"metals": ["GC=F"]},
    )
    assert result.blocked is True
    assert "concurrent" in result.blocked_reason.lower()


def test_risk_limits_block_when_daily_loss_exceeded():
    """A blown daily loss budget blocks new signals."""
    signal = _make_long_signal()
    params = RiskParameters(account_balance=10_000.0, max_daily_loss_pct=6.0)
    session = SessionState(daily_pnl=-650.0)  # -6.5% > 6% cap
    result = calculate_risk(signal, atr=1.0, params=params)
    result = apply_risk_limits(
        signal=signal,
        risk=result,
        session=session,
        params=params,
        tickers_by_class={"metals": ["GC=F"]},
    )
    assert result.blocked is True
    assert "loss" in result.blocked_reason.lower()


# ---------------------------------------------------------------------------
# Formatter smoke-test (no exception, contains required markers)
# ---------------------------------------------------------------------------


def test_format_signal_smoke():
    """The formatter produces output containing every required field."""
    sig = _make_long_signal(entry=1922.30, level=1920.50)
    sig.stop_loss = 1918.20
    sig.tp1 = 1928.60
    sig.tp2 = 1935.80
    sig.confidence_score = 78
    sig.level_type = "Monthly"
    sig.level_name = "Low"

    out = format_signal(sig)
    for marker in (
        "REVERSAL SIGNAL DETECTED",
        "Gold",
        "LONG",
        "Monthly Low",
        "Stop Loss",
        "Take Profit 1",
        "Take Profit 2",
        "Confidence:",
        "Timestamp:",
    ):
        assert marker in out, f"Formatter missing marker: {marker}"
