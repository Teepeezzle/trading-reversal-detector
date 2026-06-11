"""Entry point for the OVERNIGHT METALS drift strategy.

Run near the daily close. It prints (and optionally emails) a long-overnight
signal for each validated metal — enter at the close, exit at the next open.
Validated net-of-cost and out-of-sample on ~25y of data: Gold +0.026%/night
(Sharpe 0.64), Silver +0.060%/night (Sharpe 0.67). A small, diversifying,
short-hold edge — not intraday day-trading.

Examples:
    python overnight_scan.py
    python overnight_scan.py --email
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

from src.data_fetcher import DataFetcher
from src.email_alerts import _send_html_email
from src.overnight_metals import OvernightSignal, build_overnight_signal

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"
LOG_DIR = REPO_ROOT / "logs"
SIGNAL_LOG_PATH = LOG_DIR / "overnight_signals.log"
EMAIL_LOG_PATH = LOG_DIR / "email.log"
FETCH_ERROR_LOG_PATH = LOG_DIR / "fetch_errors.log"
SEP = "═══════════════════════════════════════"


def load_config(path: Path) -> Dict:
    """Load the YAML config."""
    if not path.exists():
        raise FileNotFoundError(f"Config not found at {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def configure_logging() -> logging.Logger:
    """Console + file logging; returns the ``overnight`` logger."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)
    fh = logging.FileHandler(LOG_DIR / "overnight_run.log", encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    return logging.getLogger("overnight")


def format_overnight(sig: OvernightSignal) -> str:
    """Render an overnight signal as a fixed-width alert block."""
    return "\n".join([
        SEP,
        "🌙 OVERNIGHT METALS SIGNAL (validated drift)",
        SEP,
        f"Market:       {sig.market_name} ({sig.ticker})",
        f"Action:       LONG at close, exit at next open",
        f"Entry (close):{sig.entry_close:,.2f}",
        f"Expected:     +{sig.expected_drift_pct:.3f}% per night (net, validated OOS)",
        f"Timestamp:    {sig.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        SEP,
    ])


def overnight_email_html(signals: List[OvernightSignal]) -> str:
    """Build a simple HTML body for the overnight signals."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = "".join(
        f"<tr><td style='padding:6px 10px;'>{s.market_name} ({s.ticker})</td>"
        f"<td style='padding:6px 10px;text-align:right;'>{s.entry_close:,.2f}</td>"
        f"<td style='padding:6px 10px;text-align:right;color:#16a34a;'>+{s.expected_drift_pct:.3f}%</td></tr>"
        for s in signals
    )
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="background:#f3f4f6;margin:0;padding:24px;font-family:Arial,Helvetica,sans-serif;">
  <table style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;border:1px solid #e5e7eb;">
    <tr><td style="padding:16px 18px;">
      <h2 style="color:#111827;margin:0 0 4px;font-size:18px;">🌙 Overnight metals — {today}</h2>
      <p style="color:#6b7280;font-size:13px;margin:0 0 12px;">Long at the close, exit at the next open.</p>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr style="color:#6b7280;"><td style="padding:6px 10px;">Market</td>
          <td style="padding:6px 10px;text-align:right;">Close</td>
          <td style="padding:6px 10px;text-align:right;">Exp/night</td></tr>
        {rows}
      </table>
      <p style="color:#9ca3af;font-size:12px;margin-top:14px;">Validated net-of-cost & out-of-sample.
        Small, diversifying short-hold edge. Use low-cost execution. Not advice.</p>
    </td></tr>
  </table></body></html>"""


def main(argv: List[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(prog="overnight-scan",
                                     description="Long-overnight metals drift signals.")
    parser.add_argument("--email", action="store_true", help="Email the signals.")
    parser.add_argument("--config", type=str, default=str(CONFIG_PATH))
    args = parser.parse_args(argv)

    logger = configure_logging()
    try:
        cfg = load_config(Path(args.config))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load config: %s", exc)
        return 2

    ocfg = cfg.get("overnight", {})
    markets = list(ocfg.get("markets", []))
    names = ocfg.get("market_names", {})
    if not markets:
        logger.error("No overnight markets configured.")
        return 2

    fetcher = DataFetcher(error_log_path=FETCH_ERROR_LOG_PATH)
    signals: List[OvernightSignal] = []
    for tk in markets:
        df = fetcher.fetch_ohlcv(tk, interval="1d")
        if df is None or len(df) < 30:
            logger.warning("Skipping %s: insufficient data", tk)
            continue
        sig = build_overnight_signal(tk, names.get(tk, tk), df)
        if sig is not None:
            signals.append(sig)

    SIGNAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    for sig in signals:
        print(format_overnight(sig))
        print()
        with SIGNAL_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(f"{sig.timestamp.isoformat()} | {sig.ticker} | LONG-overnight | "
                     f"close={sig.entry_close:.2f} exp={sig.expected_drift_pct:.3f}%\n")

    logger.info("Overnight scan complete. %d signal(s).", len(signals))
    if not signals:
        print("No overnight signals.")

    if args.email and signals:
        addr = os.environ.get("EMAIL_ADDRESS", "").strip()
        pwd = os.environ.get("EMAIL_PASSWORD", "").strip()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if addr and pwd and _send_html_email(
            f"🌙 Overnight Metals — {today}", overnight_email_html(signals),
            addr, pwd, EMAIL_LOG_PATH,
        ):
            print(f"📧 Overnight email sent to {addr}.")
        else:
            print("Email not sent — check EMAIL_ADDRESS/EMAIL_PASSWORD and logs/email.log.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
