"""V5 PARITY scanner — GitHub Actions entry point (hourly).

Emails trend-ALIGNED V5 Swing+MACD divergences that also satisfy the user's
"H1" structural filter:

    run in {2,4}  AND  span even  AND  span > run  AND  span <= 20

where run = consecutive higher-highs (BEAR) / lower-lows (BULL). Same engine
and yfinance data layer as v5_scan.py, across every asset in
config/parity_scanner.yaml, timeframes 45m/1h/2h/3h/4h.

HONESTY: this filter did NOT show a robust standalone edge in backtest (see
backtest/parity_mtf/REPORT.md). It is deployed at the user's explicit request
as a monitoring scanner, and every alert email says so. A bearish alert is
also the counter-signal/exit cue for a long (and vice-versa) — the "H2"
multi-timeframe exit idea — so opposite-direction alerts double as exits.

Usage:
    python parity_scan.py                       # auto-route by clock, email on
    python parity_scan.py --timeframes all --no-email --no-freshness   # local
    python parity_scan.py --assets BTCUSD,XAUUSD --no-email
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd
import yaml

from src.v5_divergence import (
    DivergenceSignal,
    dedup_signals,
    detect_divergences,
    drop_incomplete_last_bar,
    fetch_ohlcv,
    filter_fresh,
    load_state,
    parse_tf_minutes,
    resample_ohlcv,
    save_state,
    _signal_card,
)
from src.email_alerts import _send_html_email

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "parity_scanner.yaml"
STATE_PATH = ROOT / "state" / "parity_alerted.json"
EMAIL_LOG = ROOT / "logs" / "email.log"


def qualifies_h1(sig: DivergenceSignal, p: dict) -> bool:
    """The user's H1 structural filter on an already-aligned divergence."""
    run_in = set(int(x) for x in p.get("run_in", [2, 4]))
    if sig.run not in run_in:
        return False
    if p.get("require_span_even", True) and sig.span % 2 != 0:
        return False
    if p.get("require_span_gt_run", True) and not (sig.span > sig.run):
        return False
    if sig.span > int(p.get("span_max", 20)):
        return False
    return True


def due_timeframes(tf_cfg: Dict[str, dict], now: datetime) -> List[str]:
    slot = (now.hour * 60 + now.minute) // 30 * 30
    return [tf for tf, spec in tf_cfg.items()
            if slot % int(spec.get("scan_every_minutes", 60)) == 0]


def scan_timeframe(tf: str, spec: dict, assets: Dict[str, str], div_cfg: dict,
                   parity_cfg: dict, fetch_cache: Dict, now: pd.Timestamp
                   ) -> List[DivergenceSignal]:
    bar_minutes = parse_tf_minutes(tf)
    source = str(spec["source_interval"])
    period = str(spec["period"])
    rule = spec.get("resample")
    found: List[DivergenceSignal] = []
    for asset, spec_or_ticker in assets.items():
        if isinstance(spec_or_ticker, dict):
            ticker = str(spec_or_ticker["ticker"])
            anchor = str(spec_or_ticker.get("anchor", "utc"))
        else:
            ticker, anchor = str(spec_or_ticker), "utc"
        cache_key = (ticker, source, period)
        if cache_key not in fetch_cache:
            fetch_cache[cache_key] = fetch_ohlcv(ticker, source, period)
        df = fetch_cache[cache_key]
        if df is None or df.empty:
            print(f"  {asset:<8} {tf:<4} no data from yfinance — skipped")
            continue
        frame = resample_ohlcv(df, rule, anchor) if rule else df
        frame = drop_incomplete_last_bar(frame, bar_minutes, now)
        need = int(div_cfg["trend_sma"]) + 10
        if len(frame) < need:
            print(f"  {asset:<8} {tf:<4} only {len(frame)} bars (<{need}) — skipped")
            continue
        sigs = detect_divergences(frame, asset, ticker, tf, bar_minutes, div_cfg)
        kept = [s for s in sigs if qualifies_h1(s, parity_cfg)]
        found.extend(kept)
    return found


def build_parity_email(signals: List[DivergenceSignal]):
    count = len(signals)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    tfs = ", ".join(sorted({s.timeframe for s in signals}, key=parse_tf_minutes))
    subject = (f"[V5 PARITY] {count} H1 signal{'s' if count != 1 else ''} — {tfs} — {now_str} UTC")
    cards = "\n".join(_signal_card(s) for s in signals)
    # surface run/span on each card (the H1 structure) via a small header strip
    rows = "\n".join(
        f'<tr><td style="padding:2px 0;color:#374151;">{s.asset} {s.timeframe} '
        f'{s.direction} — run={s.run}, span={s.span}</td></tr>' for s in signals)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="background:#f3f4f6;margin:0;padding:24px;font-family:Arial,Helvetica,sans-serif;">
  <table cellpadding="0" cellspacing="0" border="0" style="max-width:680px;margin:0 auto;"><tr><td>
    <h1 style="color:#111827;font-size:22px;margin:0 0 6px;">V5 PARITY — H1 divergence alerts</h1>
    <p style="color:#6b7280;font-size:14px;margin:0 0 16px;">
      {now_str} UTC &middot; {count} aligned divergence{'s' if count != 1 else ''} with
      run&isin;{{2,4}}, even span, span&gt;run, span&le;20 &middot; LEFT/RIGHT 2/2 &middot; chart-native 200-SMA</p>
    <table style="width:100%;font-size:13px;margin-bottom:14px;">{rows}</table>
    {cards}
    <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:20px;line-height:1.5;">
      ⚠ Monitoring scanner, NOT a validated edge. This H1 parity filter did not show a
      robust standalone edge in backtest (24mo, BTC/ETH/gold/QQQ, 45m-4h; see
      backtest/parity_mtf/REPORT.md) — its aggregate improvement was largely a
      junk-filter/regime effect. An opposite-direction alert doubles as the
      counter-signal exit for an open position. Not financial advice.</p>
  </td></tr></table></body></html>"""
    return subject, html


def main() -> int:
    ap = argparse.ArgumentParser(description="V5 PARITY (H1) divergence scanner")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--timeframes", default="auto")
    ap.add_argument("--assets", default=None)
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-freshness", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    div_cfg = cfg["divergence"]
    parity_cfg = cfg.get("parity", {})
    tf_cfg = cfg["timeframes"]
    assets: Dict[str, str] = cfg["assets"]
    buffer_min = int(cfg.get("freshness_buffer_minutes", 45))

    if args.assets:
        wanted = [a.strip() for a in args.assets.split(",")]
        missing = [a for a in wanted if a not in assets]
        if missing:
            print(f"Unknown asset(s) {missing}; available: {list(assets)}")
            return 2
        assets = {a: assets[a] for a in wanted}

    now_dt = datetime.now(timezone.utc)
    now = pd.Timestamp(now_dt).tz_localize(None)

    if args.timeframes == "auto":
        tfs = due_timeframes(tf_cfg, now_dt)
    elif args.timeframes == "all":
        tfs = list(tf_cfg)
    else:
        tfs = [t.strip() for t in args.timeframes.split(",")]
        unknown = [t for t in tfs if t not in tf_cfg]
        if unknown:
            print(f"Unknown timeframe(s) {unknown}; configured: {list(tf_cfg)}")
            return 2

    print(f"V5 PARITY scan @ {now_dt:%Y-%m-%d %H:%M} UTC")
    print(f"Timeframes due: {tfs or 'none'}  |  assets: {list(assets)}")
    if not tfs:
        return 0

    fetch_cache: Dict = {}
    all_new: List[DivergenceSignal] = []
    state = load_state(STATE_PATH)

    for tf in tfs:
        spec = tf_cfg[tf]
        print(f"-- scanning {tf} (source {spec['source_interval']}"
              f"{', resample ' + spec['resample'] if spec.get('resample') else ''})")
        sigs = scan_timeframe(tf, spec, assets, div_cfg, parity_cfg, fetch_cache, now)
        if not args.no_freshness:
            sigs = filter_fresh(sigs, now, int(spec.get("scan_every_minutes", 60)), buffer_min)
        sigs, state = dedup_signals(sigs, state)
        for s in sigs:
            print(f"  H1 {s.direction:<4} {s.asset:<8} {s.timeframe:<4} "
                  f"run={s.run} span={s.span} confirmed {s.confirm_close_time} UTC")
        all_new.extend(sigs)

    save_state(STATE_PATH, state)

    if not all_new:
        print("No new H1-qualifying aligned divergences this run.")
        return 0

    print(f"{len(all_new)} new H1 divergence(s).")
    if args.no_email:
        print("--no-email set; skipping send.")
        return 0

    subject, html = build_parity_email(all_new)
    ok = _send_html_email(subject, html,
                          os.environ.get("EMAIL_ADDRESS", ""),
                          os.environ.get("EMAIL_PASSWORD", ""),
                          EMAIL_LOG)
    print("Email sent." if ok else "Email FAILED — see logs/email.log")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
