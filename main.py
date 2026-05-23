"""CLI entry point for the Trading Reversal Detector.

Examples:
    Run a single ticker:
        python main.py --ticker GC=F

    Scan every configured ticker:
        python main.py --scan-all
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import yaml

# Force UTF-8 on stdout/stderr so the box-drawing characters and emojis in the
# signal-alert block render on Windows consoles (default cp1252 cannot encode
# them and would crash the run otherwise).
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

from src.data_fetcher import DataFetcher
from src.email_alerts import send_signal_email
from src.indicators import compute_indicators
from src.price_levels import compute_price_levels
from src.reversal_detector import ReversalSignal, detect_reversals
from src.risk_manager import (
    RiskParameters,
    SessionState,
    apply_risk_limits,
    calculate_risk,
    register_signal,
)
from src.signal_formatter import format_signal


REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"
LOG_DIR = REPO_ROOT / "logs"
SIGNAL_LOG_PATH = LOG_DIR / "signals.log"
EMAIL_LOG_PATH = LOG_DIR / "email.log"
FETCH_ERROR_LOG_PATH = LOG_DIR / "fetch_errors.log"

VALID_INTERVALS = ["15m", "30m", "1h", "4h", "1d"]
VALID_SESSIONS = ["asian", "london", "newyork", "all"]
# Minimum intraday bars required before we even attempt to detect a signal.
MIN_INTRADAY_CANDLES = 50
MIN_DAILY_CANDLES = 30


def load_config(path: Path) -> Dict:
    """Load the YAML config from disk.

    Args:
        path: Absolute path to ``config.yaml``.

    Returns:
        The parsed configuration as a nested dict.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        yaml.YAMLError: If the file cannot be parsed.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config not found at {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def configure_logging(verbose: bool) -> logging.Logger:
    """Wire up console + file logging.

    Args:
        verbose: When True, log level is DEBUG; otherwise INFO.

    Returns:
        A logger named ``"trading"`` ready for use by ``main``.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    file_h = logging.FileHandler(LOG_DIR / "run.log", encoding="utf-8")
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(fmt)
    root.addHandler(file_h)

    return logging.getLogger("trading")


def append_signal_log(signal: ReversalSignal) -> None:
    """Append a single signal to ``logs/signals.log`` (UTF-8, one line per signal).

    Args:
        signal: The signal to record.
    """
    SIGNAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    blocked_tag = "BLOCKED" if signal.blocked else "ACTIVE"
    line = (
        f"{signal.timestamp.isoformat()} | {blocked_tag} | "
        f"{signal.ticker} | {signal.direction} | "
        f"{signal.level_type} {signal.level_name} | "
        f"entry={signal.entry_price:.5f} sl={signal.stop_loss:.5f} "
        f"tp1={signal.tp1:.5f} tp2={signal.tp2:.5f} "
        f"conf={int(round(signal.confidence_score))}%"
        + (f" | {signal.blocked_reason}" if signal.blocked else "")
        + "\n"
    )
    with SIGNAL_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line)


def flatten_tickers(config: Dict) -> List[str]:
    """Return every ticker from ``config['tickers']`` as a flat list.

    Args:
        config: Loaded configuration dict.

    Returns:
        A list of ticker symbols, preserving the configured per-class order.
    """
    out: List[str] = []
    for members in config.get("tickers", {}).values():
        out.extend(members)
    return out


def scan_ticker(
    ticker: str,
    config: Dict,
    fetcher: DataFetcher,
    params: RiskParameters,
    session: SessionState,
    logger: logging.Logger,
    interval: str = "1d",
    session_filter: str = "all",
) -> List[ReversalSignal]:
    """Run the full pipeline for one ticker and return any signals.

    Daily Price Levels are *always* derived from daily data, even when the
    pattern frame is intraday — this matches how traders think about
    horizontal support / resistance.

    Args:
        ticker: Yahoo-Finance symbol to scan.
        config: Loaded configuration dict.
        fetcher: Shared :class:`DataFetcher` (so caching works across tickers).
        params: Static risk parameters.
        session: Mutable session state.
        logger: Configured logger.
        interval: Bar interval for pattern detection. ``"1d"`` reuses the
            daily frame for both levels and pattern. Anything else fetches an
            additional intraday frame.
        session_filter: Session label passed through to the detector.

    Returns:
        Zero-or-more :class:`ReversalSignal` instances with SL/TP populated.
    """
    name = config.get("ticker_names", {}).get(ticker, ticker)
    logger.info("Scanning %s (%s) @%s", ticker, name, interval)

    daily_df = fetcher.fetch_ohlcv(ticker, interval="1d")
    if daily_df is None or len(daily_df) < MIN_DAILY_CANDLES:
        logger.warning("Skipping %s: insufficient daily data for levels", ticker)
        return []

    if interval == "1d":
        pattern_df = daily_df
    else:
        pattern_df = fetcher.fetch_ohlcv(ticker, interval=interval)
        if pattern_df is None or len(pattern_df) < MIN_INTRADAY_CANDLES:
            logger.warning(
                "Skipping %s: insufficient %s data (need >= %d bars)",
                ticker,
                interval,
                MIN_INTRADAY_CANDLES,
            )
            return []

    try:
        indicators = compute_indicators(pattern_df)
        levels = compute_price_levels(ticker, daily_df)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to compute features for %s: %s", ticker, exc)
        return []

    raw_signals = detect_reversals(
        ticker=ticker,
        ticker_name=name,
        df=pattern_df,
        levels=levels,
        rsi_series=indicators.rsi_series,
        volume_ma_series=indicators.volume_ma_series,
        atr_value=indicators.atr,
        tolerance_pct=float(config.get("extreme_touch_tolerance", 0.001)),
        swing_lookback=int(config.get("swing_lookback", 5)),
        interval=interval,
        session_filter=session_filter,
    )

    finalised: List[ReversalSignal] = []
    for signal in raw_signals:
        try:
            risk = calculate_risk(signal, indicators.atr, params)
        except ValueError as exc:
            logger.warning("Skipping signal for %s: %s", ticker, exc)
            continue

        risk = apply_risk_limits(
            signal=signal,
            risk=risk,
            session=session,
            params=params,
            tickers_by_class=config.get("tickers", {}),
        )

        signal.stop_loss = risk.stop_loss
        signal.tp1 = risk.tp1
        signal.tp2 = risk.tp2
        signal.blocked = risk.blocked
        signal.blocked_reason = risk.blocked_reason

        register_signal(signal, session, config.get("tickers", {}))
        finalised.append(signal)

    return finalised


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="trading-reversal-detector",
        description="Detect reversal signals at significant price extremes.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--ticker",
        type=str,
        help="Run on a single yfinance ticker (e.g. GC=F).",
    )
    group.add_argument(
        "--scan-all",
        action="store_true",
        help="Scan every ticker in the config file.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(CONFIG_PATH),
        help=f"Path to config.yaml (default: {CONFIG_PATH}).",
    )
    parser.add_argument(
        "--interval",
        type=str,
        choices=VALID_INTERVALS,
        default="1d",
        help=(
            "Bar interval used for pattern detection. Daily / Weekly / "
            "Monthly / Yearly reference levels are always derived from daily "
            "data regardless of this flag. Default: 1d."
        ),
    )
    parser.add_argument(
        "--session",
        type=str,
        choices=VALID_SESSIONS,
        default="all",
        help=(
            "Restrict signal generation to a trading session. "
            "asian = 00-07 UTC, london = 07-12 UTC, newyork = 12-20 UTC. "
            "Default: all."
        ),
    )
    parser.add_argument(
        "--email",
        action="store_true",
        help=(
            "Send an HTML email alert via Gmail SMTP when one or more signals "
            "fire. Requires EMAIL_ADDRESS and EMAIL_PASSWORD environment "
            "variables (EMAIL_PASSWORD must be a Gmail App Password)."
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Optional list of command-line args (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success).
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logger = configure_logging(args.verbose)
    try:
        config = load_config(Path(args.config))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load config: %s", exc)
        return 2

    params = RiskParameters(
        account_balance=float(config.get("account_balance", 10000)),
        risk_per_trade_pct=float(config.get("risk_per_trade_pct", 2.0)),
        max_daily_loss_pct=float(config.get("max_daily_loss_pct", 6.0)),
        max_concurrent_positions=int(config.get("max_concurrent_positions", 8)),
        max_positions_per_class=int(config.get("max_positions_per_class", 3)),
    )
    session = SessionState()
    fetcher = DataFetcher(error_log_path=FETCH_ERROR_LOG_PATH)

    if args.scan_all:
        tickers = flatten_tickers(config)
    else:
        tickers = [args.ticker]

    interval = args.interval
    session_filter = args.session

    if interval != "1d":
        print(
            f"📊 INTRADAY SCAN | Interval: {interval} | Session: {session_filter}"
        )

    logger.info(
        "Starting scan at %s for %d ticker(s) | interval=%s session=%s",
        datetime.now(timezone.utc).isoformat(),
        len(tickers),
        interval,
        session_filter,
    )

    all_signals: List[ReversalSignal] = []
    for ticker in tickers:
        try:
            signals = scan_ticker(
                ticker=ticker,
                config=config,
                fetcher=fetcher,
                params=params,
                session=session,
                logger=logger,
                interval=interval,
                session_filter=session_filter,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Unhandled error scanning %s: %s", ticker, exc)
            continue

        for signal in signals:
            all_signals.append(signal)
            print(format_signal(signal))
            print()
            append_signal_log(signal)

    total_signals = len(all_signals)
    logger.info("Scan complete. %d signal(s) detected.", total_signals)
    if total_signals == 0:
        print("No reversal signals detected in this scan.")

    # --- Email alert -------------------------------------------------------
    if args.email:
        if total_signals == 0:
            print("No signals. No email sent.")
        else:
            try:
                email_address = os.environ.get("EMAIL_ADDRESS", "").strip()
                email_password = os.environ.get("EMAIL_PASSWORD", "").strip()
                if not email_address or not email_password:
                    logger.error(
                        "EMAIL_ADDRESS / EMAIL_PASSWORD not set — skipping email."
                    )
                    print(
                        "Email requested but EMAIL_ADDRESS / EMAIL_PASSWORD env "
                        "vars are missing — see logs/email.log."
                    )
                else:
                    sent = send_signal_email(
                        signals=all_signals,
                        email_address=email_address,
                        email_password=email_password,
                        log_path=EMAIL_LOG_PATH,
                    )
                    if sent:
                        print(
                            f"📧 Email alert sent to {email_address} "
                            f"with {total_signals} signal(s)."
                        )
                    else:
                        print(
                            "Email send FAILED — see logs/email.log for details."
                        )
            except Exception as exc:  # noqa: BLE001
                logger.error("Unhandled email error: %s", exc)
                print("Email send FAILED unexpectedly — see logs/email.log.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
