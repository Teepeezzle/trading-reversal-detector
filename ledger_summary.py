"""Weekly ledger-summary email for the paper-tracked scanners.

Reads the Winners and Confluence paper ledgers (restored from their Actions
caches), reconciles each for freshness, and emails one combined snapshot:
realized net P&L ($ / R), win rate, closed W/L, open trades, and the 40%-loss
flag. Read-only — it does NOT save any cache/state.

The main [V5 Divergence] scanner has no ledger (context-only alerts), so it is
not included.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from src.v5_divergence import fetch_ohlcv, _money
from src import v5_ledger
from src.email_alerts import _send_html_email

ROOT = Path(__file__).resolve().parent
EMAIL_LOG = ROOT / "logs" / "email.log"
LEDGERS = {
    "V5 WINNERS": ROOT / "state" / "v5_winners_ledger.json",
    "V5 CONFLUENCE": ROOT / "state" / "v5_confluence_ledger.json",
}


def resolve_sizing() -> Tuple[float, float]:
    def _num(k):
        raw = os.environ.get(k, "")
        if not str(raw).strip():
            return None
        try:
            return float(str(raw).strip())
        except ValueError:
            return None
    eq = _num("BASE_EQUITY") or _num("ACCOUNT_EQUITY") or 1000.0
    rr = _num("RISK_PCT")
    rr = 5.0 if rr is None else rr
    return eq, (rr / 100.0 if rr > 1 else rr)


def _row(name: str, st) -> str:
    if st is None:
        return (f'<tr><td style="padding:8px 10px;font-weight:600;">{name}</td>'
                f'<td colspan="6" style="padding:8px 10px;color:#9ca3af;">no ledger yet — '
                f'no signals tracked so far</td></tr>')
    res = st["wins"] + st["losses"]
    wr = f'{100*st["wins"]/res:.0f}%' if res else "—"
    pnl = st["realized_pnl"]
    col = "#16a34a" if pnl >= 0 else "#dc2626"
    warn = " ⚠" if (st.get("hit_40") or st.get("below_40_now")) else ""
    return f"""<tr>
      <td style="padding:8px 10px;font-weight:600;">{name}{warn}</td>
      <td style="padding:8px 10px;text-align:right;color:{col};font-weight:700;">
        {'+' if pnl>=0 else ''}{_money(pnl)}</td>
      <td style="padding:8px 10px;text-align:right;">{st['realized_r']:+.1f}R</td>
      <td style="padding:8px 10px;text-align:right;">{wr}</td>
      <td style="padding:8px 10px;text-align:right;">{st['wins']}W / {st['losses']}L</td>
      <td style="padding:8px 10px;text-align:right;">{st['open_count']}</td>
      <td style="padding:8px 10px;text-align:right;">{_money(st['equity'])}</td>
    </tr>"""


def build_summary(reports, base, risk_pct) -> Tuple[str, str]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_pnl = sum(st["realized_pnl"] for _, st in reports if st)
    total_r = sum(st["realized_r"] for _, st in reports if st)
    tcol = "#16a34a" if total_pnl >= 0 else "#dc2626"
    rows = "\n".join(_row(n, st) for n, st in reports)
    subject = (f"[SCANNER LEDGERS] weekly summary — {now} — "
               f"net {'+' if total_pnl>=0 else ''}{_money(total_pnl)} ({total_r:+.1f}R)")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="background:#f3f4f6;margin:0;padding:24px;font-family:Arial,Helvetica,sans-serif;">
  <table cellpadding="0" cellspacing="0" border="0" style="max-width:720px;margin:0 auto;"><tr><td>
    <h1 style="color:#111827;font-size:22px;margin:0 0 6px;">Scanner ledgers — weekly summary</h1>
    <p style="color:#6b7280;font-size:14px;margin:0 0 6px;">
      {now} UTC &middot; base {_money(base)} &middot; {risk_pct*100:.0f}% risk/trade &middot;
      forward paper-track (not live orders)</p>
    <p style="color:{tcol};font-size:18px;font-weight:700;margin:0 0 18px;">
      Combined realized: {'+' if total_pnl>=0 else ''}{_money(total_pnl)} ({total_r:+.1f}R)</p>
    <table cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;
           font-size:13px;color:#111827;border:1px solid #e5e7eb;background:#fff;">
      <tr style="background:#0d1424;color:#94a3b8;">
        <td style="padding:8px 10px;">Scanner</td>
        <td style="padding:8px 10px;text-align:right;">Realized P&amp;L</td>
        <td style="padding:8px 10px;text-align:right;">R</td>
        <td style="padding:8px 10px;text-align:right;">Win%</td>
        <td style="padding:8px 10px;text-align:right;">Closed</td>
        <td style="padding:8px 10px;text-align:right;">Open</td>
        <td style="padding:8px 10px;text-align:right;">Equity</td>
      </tr>
      {rows}
    </table>
    <p style="color:#9ca3af;font-size:12px;margin-top:18px;">
      Realized = closed paper trades only (SL/TP reconciled on 1h bars). The main
      [V5 Divergence] scanner is context-only and has no ledger. Not financial advice.</p>
  </td></tr></table></body></html>"""
    return subject, html


def main() -> int:
    base, risk_pct = resolve_sizing()
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache: Dict = {}

    def fetch_1h(tk):
        if tk not in cache:
            cache[tk] = fetch_ohlcv(tk, "1h", "120d")
        return cache[tk]

    reports = []
    for name, path in LEDGERS.items():
        if not path.exists():
            reports.append((name, None)); continue
        led = v5_ledger.load_ledger(path)
        try:
            led, _ = v5_ledger.reconcile(led, fetch_1h, now)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN reconcile {name}: {exc}")
        st = v5_ledger.status(led, base, risk_pct)
        reports.append((name, st))
        print(f"{name}: realized {st['realized_pnl']:+.2f} ({st['realized_r']:+.1f}R) "
              f"W{st['wins']}/L{st['losses']} open {st['open_count']}")

    subject, html = build_summary(reports, base, risk_pct)
    if "--no-email" in sys.argv:
        print("SUBJECT:", subject); print("--no-email set; skipping send."); return 0
    ok = _send_html_email(subject, html, os.environ.get("EMAIL_ADDRESS", ""),
                          os.environ.get("EMAIL_PASSWORD", ""), EMAIL_LOG)
    print("Summary sent." if ok else "Summary FAILED — see logs/email.log")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
