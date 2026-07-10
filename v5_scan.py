"""V5 divergence multi-timeframe scan — GitHub Actions entry point.

One cron tick every 30 minutes; this router decides which timeframes are due:

* slot :00 or :30  ->  timeframes with ``scan_every_minutes: 30``  (15m)
* slot :00 only    ->  timeframes with ``scan_every_minutes: 60``  (30m..4h)

The slot is the trigger time FLOORED to the previous 30-minute boundary, so
GitHub's 5-30 minute cron delays don't shift which timeframes run. Each
timeframe then re-derives "last closed bar" from wall-clock time, so a late
run still scans the right bars.

Usage:
    python v5_scan.py                        # auto-route by clock, email on
    python v5_scan.py --timeframes all       # scan every configured TF
    python v5_scan.py --timeframes 1h,4h     # explicit list
    python v5_scan.py --assets BTCUSD --no-email --no-freshness   # local test
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
    build_divergence_email,
    dedup_signals,
    detect_divergences,
    drop_incomplete_last_bar,
    fetch_ohlcv,
    filter_fresh,
    load_state,
    parse_tf_minutes,
    resample_ohlcv,
    save_state,
)
from src.email_alerts import _send_html_email

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "v5_scanner.yaml"
STATE_PATH = ROOT / "state" / "v5_alerted.json"
EMAIL_LOG = ROOT / "logs" / "email.log"


def due_timeframes(tf_cfg: Dict[str, dict], now: datetime) -> List[str]:
    """Timeframes whose cadence divides the current 30-minute slot."""
    slot = (now.hour * 60 + now.minute) // 30 * 30   # minutes since midnight
    due = []
    for tf, spec in tf_cfg.items():
        every = int(spec.get("scan_every_minutes", 60))
        if slot % every == 0:
            due.append(tf)
    return due


def scan_timeframe(tf: str, spec: dict, assets: Dict[str, str],
                   div_cfg: dict, fetch_cache: Dict, now: pd.Timestamp
                   ) -> List[DivergenceSignal]:
    """Scan every asset on one timeframe; returns ALL aligned divergences."""
    bar_minutes = parse_tf_minutes(tf)
    source = str(spec["source_interval"])
    period = str(spec["period"])
    rule = spec.get("resample")

    found: List[DivergenceSignal] = []
    for asset, spec_or_ticker in assets.items():
        # Config values are {ticker, anchor} dicts; bare strings still work
        # (anchor defaults to utc).
        if isinstance(spec_or_ticker, dict):
            ticker = str(spec_or_ticker["ticker"])
            anchor = str(spec_or_ticker.get("anchor", "utc"))
        else:
            ticker = str(spec_or_ticker)
            anchor = "utc"
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
            print(f"  {asset:<8} {tf:<4} only {len(frame)} bars "
                  f"(<{need} needed for SMA) — skipped")
            continue
        sigs = detect_divergences(frame, asset, ticker, tf, bar_minutes, div_cfg)
        found.extend(sigs)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="V5 divergence multi-TF scanner")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--timeframes", default="auto",
                    help="'auto' (route by clock), 'all', or CSV like '1h,4h'")
    ap.add_argument("--assets", default=None,
                    help="CSV of display names to scan (default: all in config)")
    ap.add_argument("--no-email", action="store_true",
                    help="Print signals instead of emailing")
    ap.add_argument("--no-freshness", action="store_true",
                    help="Report ALL historical matches (local testing only)")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    div_cfg = cfg["divergence"]
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

    print(f"V5 divergence scan @ {now_dt:%Y-%m-%d %H:%M} UTC")
    print(f"Timeframes due: {tfs or 'none'}  |  assets: {list(assets)}")
    if not tfs:
        return 0

    fetch_cache: Dict = {}
    all_new: List[DivergenceSignal] = []
    state = load_state(STATE_PATH)

    for tf in tfs:
        spec = tf_cfg[tf]
        print(f"-- scanning {tf} "
              f"(source {spec['source_interval']}"
              f"{', resample ' + spec['resample'] if spec.get('resample') else ''})")
        sigs = scan_timeframe(tf, spec, assets, div_cfg, fetch_cache, now)
        if not args.no_freshness:
            sigs = filter_fresh(sigs, now,
                                int(spec.get("scan_every_minutes", 60)),
                                buffer_min)
        sigs, state = dedup_signals(sigs, state)
        for s in sigs:
            print(f"  ALIGNED {s.direction:<4} {s.asset:<8} {s.timeframe:<4} "
                  f"span={s.span:<3} confirmed {s.confirm_close_time} UTC")
        all_new.extend(sigs)

    save_state(STATE_PATH, state)

    if not all_new:
        print("No new trend-aligned divergences this run.")
        return 0

    print(f"{len(all_new)} new aligned divergence(s).")
    if args.no_email:
        print("--no-email set; skipping send.")
        return 0

    subject, html = build_divergence_email(all_new)
    ok = _send_html_email(
        subject, html,
        os.environ.get("EMAIL_ADDRESS", ""),
        os.environ.get("EMAIL_PASSWORD", ""),
        EMAIL_LOG,
    )
    print("Email sent." if ok else "Email FAILED — see logs/email.log")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
