"""HTML email-alert delivery via Gmail SMTP.

Reads credentials from environment variables (never from disk / config) so the
secrets only exist in memory during the SMTP exchange:

* ``EMAIL_ADDRESS`` – the Gmail account (also used as the To: address).
* ``EMAIL_PASSWORD`` – a Gmail App Password (NOT the regular account password).

Errors are appended to ``logs/email.log`` so SMTP failures don't crash the
scan but are still recoverable.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

from .reversal_detector import ReversalSignal

SMTP_HOST: str = "smtp.gmail.com"
SMTP_PORT: int = 587
SMTP_TIMEOUT_SECONDS: int = 30

logger = logging.getLogger(__name__)


def _format_price(value: float, ticker: str) -> str:
    """Format a price string with instrument-appropriate precision.

    Args:
        value: Numeric price.
        ticker: yfinance ticker symbol (drives precision).

    Returns:
        ``"$1,922.30"`` for commodities/crypto, ``"$0.71296"`` for forex,
        ``"$148.327"`` for JPY pairs.
    """
    if ticker.endswith("=X"):
        if "JPY" in ticker:
            return f"${value:,.3f}"
        return f"${value:,.5f}"
    return f"${value:,.2f}"


def _signed_pct(entry: float, target: float) -> str:
    """Return a signed percentage string e.g. ``"+0.42%"`` / ``"-0.21%"``.

    Args:
        entry: Entry price.
        target: SL or TP price.

    Returns:
        Signed percentage with 2 decimal places.
    """
    if entry == 0:
        return "+0.00%"
    pct = (target - entry) / entry * 100.0
    return f"{pct:+.2f}%"


def _signal_card_html(signal: ReversalSignal) -> str:
    """Render a single signal as an HTML card.

    Args:
        signal: The signal to render.

    Returns:
        An inline-styled ``<table>`` block (email-client compatible).
    """
    direction_color = "#16a34a" if signal.direction == "LONG" else "#dc2626"
    direction_arrow = "📈" if signal.direction == "LONG" else "📉"

    entry = signal.entry_price
    sl = signal.stop_loss
    tp1 = signal.tp1
    tp2 = signal.tp2
    ticker = signal.ticker

    blocked_badge = ""
    if signal.blocked:
        blocked_badge = (
            '<div style="background:#fef3c7;color:#92400e;padding:8px 12px;'
            'border-radius:4px;margin-top:8px;font-size:13px;">'
            f"⚠️ BLOCKED: {signal.blocked_reason}</div>"
        )

    # Intraday-only rows. Daily signals keep their original card layout.
    intraday_rows = ""
    if signal.interval != "1d":
        intraday_rows = f"""
            <tr>
              <td style="padding:4px 0;color:#6b7280;">Interval</td>
              <td style="padding:4px 0;text-align:right;font-weight:600;">
                {signal.interval}
              </td>
            </tr>
            <tr>
              <td style="padding:4px 0;color:#6b7280;">Session</td>
              <td style="padding:4px 0;text-align:right;font-weight:600;">
                {signal.session}
              </td>
            </tr>
        """

    return f"""
    <table cellpadding="0" cellspacing="0" border="0" role="presentation"
           style="width:100%;margin-bottom:20px;border:1px solid #e5e7eb;
                  border-radius:8px;background:#ffffff;
                  font-family:Arial,Helvetica,sans-serif;">
      <tr>
        <td style="background:{direction_color};color:#ffffff;padding:14px 18px;
                   border-radius:8px 8px 0 0;">
          <div style="font-size:18px;font-weight:bold;">
            {signal.ticker_display_name} ({signal.ticker})
          </div>
          <div style="font-size:14px;margin-top:4px;opacity:0.95;">
            {direction_arrow} {signal.direction}
            &nbsp;·&nbsp; {signal.level_type} {signal.level_name}
          </div>
        </td>
      </tr>
      <tr>
        <td style="padding:18px;">
          <table cellpadding="0" cellspacing="0" border="0" role="presentation"
                 style="width:100%;font-size:14px;color:#111827;">
            <tr>
              <td style="padding:4px 0;color:#6b7280;">Level</td>
              <td style="padding:4px 0;text-align:right;font-weight:600;">
                {_format_price(signal.level_price, ticker)}
              </td>
            </tr>
            {intraday_rows}
            <tr>
              <td style="padding:4px 0;color:#6b7280;">Entry</td>
              <td style="padding:4px 0;text-align:right;font-weight:600;">
                {_format_price(entry, ticker)}
              </td>
            </tr>
            <tr>
              <td style="padding:4px 0;color:#6b7280;">Stop Loss</td>
              <td style="padding:4px 0;text-align:right;color:#dc2626;">
                {_format_price(sl, ticker)}
                <span style="color:#9ca3af;">({_signed_pct(entry, sl)})</span>
              </td>
            </tr>
            <tr>
              <td style="padding:4px 0;color:#6b7280;">Take Profit 1</td>
              <td style="padding:4px 0;text-align:right;color:#16a34a;">
                {_format_price(tp1, ticker)}
                <span style="color:#9ca3af;">({_signed_pct(entry, tp1)})</span>
                <span style="color:#6b7280;font-size:12px;">&nbsp;→ Close 50%</span>
              </td>
            </tr>
            <tr>
              <td style="padding:4px 0;color:#6b7280;">Take Profit 2</td>
              <td style="padding:4px 0;text-align:right;color:#16a34a;">
                {_format_price(tp2, ticker)}
                <span style="color:#9ca3af;">({_signed_pct(entry, tp2)})</span>
                <span style="color:#6b7280;font-size:12px;">&nbsp;→ Close 50%</span>
              </td>
            </tr>
            <tr>
              <td style="padding:4px 0;color:#6b7280;">Confidence</td>
              <td style="padding:4px 0;text-align:right;font-weight:600;">
                {int(round(signal.confidence_score))}%
              </td>
            </tr>
          </table>
          <div style="margin-top:14px;padding:12px;background:#f9fafb;
                      border-radius:4px;color:#374151;font-size:13px;line-height:1.5;">
            <strong>Reason:</strong> {signal.reason_string}
          </div>
          {blocked_badge}
        </td>
      </tr>
    </table>
    """


def build_email_html(signals: List[ReversalSignal]) -> str:
    """Build the complete HTML body containing every signal card.

    Args:
        signals: Signals to render (must be non-empty).

    Returns:
        A full HTML document as a string.
    """
    count = len(signals)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cards = "\n".join(_signal_card_html(s) for s in signals)
    plural = "s" if count != 1 else ""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Trading Reversal Signals</title>
</head>
<body style="background:#f3f4f6;margin:0;padding:24px;
             font-family:Arial,Helvetica,sans-serif;">
  <table cellpadding="0" cellspacing="0" border="0" role="presentation"
         style="max-width:680px;margin:0 auto;">
    <tr>
      <td>
        <h1 style="color:#111827;font-size:22px;margin:0 0 6px;">
          🔔 Reversal Signals
        </h1>
        <p style="color:#6b7280;font-size:14px;margin:0 0 24px;">
          {today_str} UTC · {count} signal{plural} found
        </p>
        {cards}
        <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:24px;">
          Generated by trading-reversal-detector. Not financial advice.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _log_email_error(log_path: Path, message: str) -> None:
    """Append a timestamped error line to ``logs/email.log``.

    Args:
        log_path: Absolute path to the email-log file.
        message: Free-text error message.
    """
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(
                f"{datetime.now(timezone.utc).isoformat()} | ERROR | {message}\n"
            )
    except Exception:  # noqa: BLE001
        # Last-resort: if the log itself can't be written, drop silently.
        pass


def send_signal_email(
    signals: List[ReversalSignal],
    email_address: str,
    email_password: str,
    log_path: Path,
) -> bool:
    """Send the HTML alert email via Gmail SMTP.

    Args:
        signals: Detected signals (caller already gated for non-empty).
        email_address: Gmail sender / recipient (the same account).
        email_password: Gmail App Password (16-character one).
        log_path: Where to append SMTP error lines.

    Returns:
        True on success, False on any handled failure.
    """
    if not signals:
        return False
    if not email_address or not email_password:
        _log_email_error(
            log_path,
            "EMAIL_ADDRESS / EMAIL_PASSWORD env vars not set — skipping send.",
        )
        return False

    count = len(signals)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    plural = "s" if count != 1 else ""

    # If every signal in the batch shares a non-daily interval, use the
    # intraday subject; otherwise keep the original daily subject.
    intervals = {s.interval for s in signals}
    if len(intervals) == 1 and "1d" not in intervals:
        only_interval = next(iter(intervals))
        subject = (
            f"📊 Intraday Signals ({only_interval}) — {today_str} "
            f"({count} signal{plural} found)"
        )
    else:
        subject = (
            f"🔔 Trading Reversal Signals — {today_str} "
            f"({count} signal{plural} found)"
        )
    html_body = build_email_html(signals)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_address
    msg["To"] = email_address
    msg.attach(MIMEText(html_body, "html", _charset="utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(email_address, email_password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        _log_email_error(
            log_path,
            f"SMTPAuthenticationError ({exc.smtp_code}): "
            f"check EMAIL_PASSWORD is a Gmail App Password — {exc.smtp_error!r}",
        )
        logger.error("SMTP auth failed: %s", exc)
        return False
    except smtplib.SMTPException as exc:
        _log_email_error(log_path, f"SMTPException: {exc}")
        logger.error("SMTP error: %s", exc)
        return False
    except (OSError, ssl.SSLError) as exc:
        _log_email_error(log_path, f"Network/TLS error: {exc}")
        logger.error("Network error sending email: %s", exc)
        return False
    except Exception as exc:  # noqa: BLE001
        _log_email_error(log_path, f"Unexpected error: {exc}")
        logger.error("Unexpected error sending email: %s", exc)
        return False

    logger.info(
        "Email alert sent to %s with %d signal(s)", email_address, count
    )
    return True
