"""Email a failure alert when a watched GitHub Actions workflow fails.

Driven by the `workflow_health_notifier.yml` workflow (on: workflow_run). Reads
the failed run's details and the Gmail creds from the environment and sends one
short HTML email. Self-contained (stdlib only) so the notifier needs no pip
install and has as few moving parts as possible. Best-effort: never raises — a
dead notifier must not itself page anyone, so failures are logged to stderr and
the process still exits 0.

Env:
  EMAIL_ADDRESS, EMAIL_PASSWORD   Gmail account + app password (same as scanners)
  WF_NAME, WF_CONCLUSION, WF_URL, WF_BRANCH, WF_EVENT, WF_RUN_NUMBER   run context
"""
from __future__ import annotations

import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST, SMTP_PORT, TIMEOUT = "smtp.gmail.com", 587, 30


def main() -> int:
    addr = os.environ.get("EMAIL_ADDRESS", "")
    pw = os.environ.get("EMAIL_PASSWORD", "")
    name = os.environ.get("WF_NAME", "(unknown workflow)")
    concl = os.environ.get("WF_CONCLUSION", "failure")
    url = os.environ.get("WF_URL", "")
    branch = os.environ.get("WF_BRANCH", "")
    event = os.environ.get("WF_EVENT", "")
    run_no = os.environ.get("WF_RUN_NUMBER", "")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if not addr or not pw:
        print("notify: EMAIL_ADDRESS/EMAIL_PASSWORD not set — cannot send; skipping.",
              file=sys.stderr)
        return 0

    subject = f"⚠ Workflow FAILED: {name} ({concl}) — {now}"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="background:#f3f4f6;margin:0;padding:24px;font-family:Arial,Helvetica,sans-serif;">
  <table cellpadding="0" cellspacing="0" border="0" style="max-width:600px;margin:0 auto;"><tr><td>
    <h1 style="color:#b91c1c;font-size:20px;margin:0 0 6px;">&#9888; GitHub Actions failure</h1>
    <p style="color:#6b7280;font-size:14px;margin:0 0 16px;">{now}</p>
    <table style="width:100%;font-size:14px;color:#111827;border:1px solid #e5e7eb;border-radius:8px;">
      <tr><td style="padding:10px 14px;background:#fee2e2;color:#991b1b;font-weight:bold;border-radius:8px 8px 0 0;">
        {name}</td></tr>
      <tr><td style="padding:12px 14px;">
        <table style="width:100%;font-size:14px;">
          <tr><td style="color:#6b7280;padding:3px 0;">Conclusion</td><td style="text-align:right;font-weight:600;color:#b91c1c;">{concl}</td></tr>
          <tr><td style="color:#6b7280;padding:3px 0;">Run</td><td style="text-align:right;">#{run_no} &middot; {event}</td></tr>
          <tr><td style="color:#6b7280;padding:3px 0;">Branch</td><td style="text-align:right;">{branch}</td></tr>
        </table>
        <p style="margin:14px 0 0;"><a href="{url}" style="color:#2563eb;">Open the failed run &rarr;</a></p>
      </td></tr>
    </table>
    <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:18px;">
      Automated health check for watched scanners/board. Re-run the job from the run page once fixed.</p>
  </td></tr></table></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = addr
    msg["To"] = addr
    msg.attach(MIMEText(html, "html", _charset="utf-8"))
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT) as s:
            s.ehlo(); s.starttls(context=ctx); s.ehlo()
            s.login(addr, pw); s.send_message(msg)
        print(f"notify: failure email sent for '{name}' ({concl}).")
    except Exception as exc:  # noqa: BLE001
        print(f"notify: email send failed ({exc}) — not failing the notifier.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
