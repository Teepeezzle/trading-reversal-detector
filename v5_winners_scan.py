"""V5 WINNERS scanner — GitHub Actions entry point.

A second, independent scanner for the 5 positive-expectancy assets on 5
timeframes. Identical detection to v5_scan.py, but:

  * reads config/v5_winners_scanner.yaml (5 assets, 5 TFs),
  * attaches SCALPR entry/stop/target to each signal,
  * emails with the unique subject "[V5 WINNERS] ...",
  * keeps its OWN dedup state file (state/v5_winners_alerted.json) so it never
    interferes with the main scanner's dedup.

Runs on its own workflow / cache namespace, so the two scanners never block
each other. Same clock-based timeframe router as the main scanner.

Usage mirrors v5_scan.py:
    python v5_winners_scan.py                     # auto-route, email on
    python v5_winners_scan.py --timeframes all
    python v5_winners_scan.py --assets BTCUSD --no-email --no-freshness
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
    attach_trade_levels,
    build_winners_email,
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
DEFAULT_CONFIG = ROOT / "config" / "v5_winners_scanner.yaml"
STATE_PATH = ROOT / "state" / "v5_winners_alerted.json"
EMAIL_LOG = ROOT / "logs" / "email.log"


def due_timeframes(tf_cfg: Dict[str, dict], now: datetime) -> List[str]:
    """Timeframes whose cadence divides the current 30-minute slot."""
    slot = (now.hour * 60 + now.minute) // 30 * 30
    return [tf for tf, spec in tf_cfg.items()
            if slot % int(spec.get("scan_every_minutes", 60)) == 0]


def scan_timeframe(tf: str, spec: dict, assets: Dict[str, dict],
                   div_cfg: dict, fetch_cache: Dict, now: pd.Timestamp
                   ) -> List[DivergenceSignal]:
    """Scan every winners asset on one timeframe; attach trade levels."""
    bar_minutes = parse_tf_minutes(tf)
    source = str(spec["source_interval"])
    period = str(spec["period"])
    rule = spec.get("resample")
    atr_len = int(div_cfg.get("atr_len", 14))
    sl_mult = float(div_cfg.get("sl_atr_mult", 1.5))
    tp_mult = float(div_cfg.get("tp_atr_mult", 3.0))

    found: List[DivergenceSignal] = []
    for asset, spec_or_ticker in assets.items():
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
                  f"(<{need} needed) — skipped")
            continue
        sigs = detect_divergences(frame, asset, ticker, tf, bar_minutes, div_cfg)
        sigs = attach_trade_levels(sigs, frame, atr_len, sl_mult, tp_mult)
        # drop any signal without a valid trade level (ATR gap)
        sigs = [s for s in sigs if s.stop is not None and s.target is not None]
        found.extend(sigs)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="V5 WINNERS scanner")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--timeframes", default="auto",
                    help="'auto', 'all', or CSV like '15m,4h'")
    ap.add_argument("--assets", default=None)
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-freshness", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    div_cfg = cfg["divergence"]
    tf_cfg = cfg["timeframes"]
    assets: Dict[str, dict] = cfg["assets"]
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

    print(f"V5 WINNERS scan @ {now_dt:%Y-%m-%d %H:%M} UTC")
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
        sigs = scan_timeframe(tf, spec, assets, div_cfg, fetch_cache, now)
        if not args.no_freshness:
            sigs = filter_fresh(sigs, now,
                                int(spec.get("scan_every_minutes", 60)),
                                buffer_min)
        sigs, state = dedup_signals(sigs, state)
        for s in sigs:
            print(f"  {('BUY' if s.direction=='BULL' else 'SELL'):<4} "
                  f"{s.asset:<8} {s.timeframe:<4} entry={s.close:.5f} "
                  f"SL={s.stop:.5f} TP={s.target:.5f} @ {s.confirm_close_time} UTC")
        all_new.extend(sigs)

    save_state(STATE_PATH, state)

    if not all_new:
        print("No new winners signals this run.")
        return 0

    print(f"{len(all_new)} new winners signal(s).")
    if args.no_email:
        print("--no-email set; skipping send.")
        return 0

    subject, html = build_winners_email(all_new)
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
