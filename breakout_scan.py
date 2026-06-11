"""Entry point for the VALIDATED daily long-breakout strategy.

This is the production-ready outcome of the strategy investigation: the only
setup that passed out-of-sample validation, walk-forward stability, and a
26-year / 6-asset portfolio test (PF 1.62, max drawdown -10.2%). It scans a
basket of liquid assets on the DAILY timeframe for breakout entries, sizes each
at a fixed % of equity, logs them, and (optionally) emails an alert.

Examples:
    python breakout_scan.py                 # scan the configured basket
    python breakout_scan.py --email         # ...and email any signals
    python breakout_scan.py --ticker BTC-USD

Honest scope: this edge is DAILY-only. It does not survive intraday (1h loses,
4h is marginal/unvalidated). Run it once per day after the daily close.
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

for _stream in (sys.stdout, sys.stderr):
    _rc = getattr(_stream, "reconfigure", None)
    if callable(_rc):
        try:
            _rc(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

from src.breakout_detector import BreakoutSignal, detect_breakout
from src.data_fetcher import DataFetcher
from src.email_alerts import send_breakout_email
from src.signal_formatter import format_breakout_signal

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"
LOG_DIR = REPO_ROOT / "logs"
SIGNAL_LOG_PATH = LOG_DIR / "breakout_signals.log"
EMAIL_LOG_PATH = LOG_DIR / "email.log"
FETCH_ERROR_LOG_PATH = LOG_DIR / "fetch_errors.log"
MIN_DAILY_BARS = 220


def load_config(path: Path) -> Dict:
    """Load and return the YAML config.

    Args:
        path: Path to ``config.yaml``.

    Returns:
        Parsed configuration dict.

    Raises:
        FileNotFoundError: If the config is missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config not found at {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def configure_logging() -> logging.Logger:
    """Set up console + file logging and return the ``breakout`` logger."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)
    fh = logging.FileHandler(LOG_DIR / "breakout_run.log", encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    return logging.getLogger("breakout")


def position_size(balance: float, risk_pct: float, risk_per_unit: float) -> tuple[float, float]:
    """Compute position size in units and the dollar amount risked.

    Args:
        balance: Account balance.
        risk_pct: Percent of balance to risk on the trade.
        risk_per_unit: Price distance from entry to stop.

    Returns:
        ``(units, risk_amount)``.
    """
    risk_amount = balance * (risk_pct / 100.0)
    units = risk_amount / risk_per_unit if risk_per_unit > 0 else 0.0
    return units, risk_amount


def append_signal_log(signal: BreakoutSignal, units: float) -> None:
    """Append a one-line record of a breakout signal to the log file."""
    SIGNAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"{signal.timestamp.isoformat()} | {signal.ticker} | LONG | "
        f"entry={signal.entry_price:.4f} sl={signal.stop_loss:.4f} "
        f"tp={signal.take_profit:.4f} adx={signal.adx:.1f} "
        f"units={units:.4f}\n"
    )
    with SIGNAL_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line)


def main(argv: List[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Optional CLI args (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(
        prog="breakout-scan",
        description="Scan for validated daily long-breakout signals.",
    )
    parser.add_argument("--ticker", type=str, help="Scan a single ticker instead of the basket.")
    parser.add_argument("--email", action="store_true", help="Email alert when signals are found.")
    parser.add_argument("--config", type=str, default=str(CONFIG_PATH))
    args = parser.parse_args(argv)

    logger = configure_logging()
    try:
        cfg = load_config(Path(args.config))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load config: %s", exc)
        return 2

    bcfg = cfg.get("breakout", {})
    balance = float(bcfg.get("account_balance", 10000))
    risk_pct = float(bcfg.get("risk_per_trade_pct", 1.0))
    names = bcfg.get("basket_names", {})
    basket = [args.ticker] if args.ticker else list(bcfg.get("basket", []))
    if not basket:
        logger.error("No tickers to scan (empty basket).")
        return 2

    fetcher = DataFetcher(error_log_path=FETCH_ERROR_LOG_PATH)
    logger.info(
        "Daily breakout scan at %s for %d ticker(s)",
        datetime.now(timezone.utc).isoformat(), len(basket),
    )

    signals: List[BreakoutSignal] = []
    for ticker in basket:
        name = names.get(ticker, ticker)
        df = fetcher.fetch_ohlcv(ticker, interval="1d")
        if df is None or len(df) < MIN_DAILY_BARS:
            logger.warning("Skipping %s: insufficient daily data", ticker)
            continue
        try:
            sig = detect_breakout(ticker, name, df)
        except Exception as exc:  # noqa: BLE001
            logger.error("Detection failed for %s: %s", ticker, exc)
            continue
        if sig is not None:
            signals.append(sig)
            logger.info("BREAKOUT: %s entry=%.4f", ticker, sig.entry_price)

    for sig in signals:
        units, risk_amount = position_size(balance, risk_pct, sig.risk_per_unit)
        print(format_breakout_signal(sig, units, risk_amount))
        print()
        append_signal_log(sig, units)

    logger.info("Scan complete. %d breakout signal(s).", len(signals))
    if not signals:
        print("No breakout signals today.")

    if args.email:
        if not signals:
            print("No signals. No email sent.")
        else:
            addr = os.environ.get("EMAIL_ADDRESS", "").strip()
            pwd = os.environ.get("EMAIL_PASSWORD", "").strip()
            if not addr or not pwd:
                print("Email requested but EMAIL_ADDRESS / EMAIL_PASSWORD not set — see logs/email.log.")
            elif send_breakout_email(signals, addr, pwd, EMAIL_LOG_PATH):
                print(f"📧 Breakout email sent to {addr} ({len(signals)} signal(s)).")
            else:
                print("Email send FAILED — see logs/email.log.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
