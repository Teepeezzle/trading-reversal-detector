"""V5 CONFLUENCE scanner — GitHub Actions entry point.

Aligned V5 divergence + DRS support/resistance (any TF) + 200-SMA trend, on the
robustness-checked direction-specific shortlist. Emails [V5 CONFLUENCE] with
entry/SL/TP sizing and the static-base paper ledger. Fully isolated from the
other scanners (own workflow, concurrency group, dedup + ledger state).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml

from src.v5_divergence import (
    DivergenceSignal, dedup_signals, drop_incomplete_last_bar, fetch_ohlcv,
    filter_fresh, load_state, parse_tf_minutes, resample_ohlcv, save_state,
)
from src.v5_confluence import (
    build_confluence_email, confluence_on_frame, drs_active_red,
)
from src.email_alerts import _send_html_email
from src import v5_ledger

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "v5_confluence_scanner.yaml"
STATE_PATH = ROOT / "state" / "v5_confluence_alerted.json"
LEDGER_PATH = ROOT / "state" / "v5_confluence_ledger.json"
EMAIL_LOG = ROOT / "logs" / "email.log"


def resolve_sizing(cfg: dict) -> Tuple[float, float]:
    sizing = cfg.get("sizing", {}) or {}

    def _num(k):
        raw = os.environ.get(k, "")
        if not str(raw).strip():
            return None
        try:
            return float(str(raw).strip())
        except ValueError:
            print(f"WARN: {k}={raw!r} not numeric; ignoring")
            return None

    eq = _num("BASE_EQUITY") or _num("ACCOUNT_EQUITY") or float(sizing.get("account_equity", 1000))
    rr = _num("RISK_PCT")
    if rr is None:
        rr = float(sizing.get("risk_pct", 5))
    return eq, (rr/100.0 if rr > 1 else rr)


def due_timeframes(tf_cfg: Dict[str, dict], now: datetime) -> List[str]:
    slot = (now.hour * 60 + now.minute) // 30 * 30
    return [tf for tf, s in tf_cfg.items()
            if slot % int(s.get("scan_every_minutes", 60)) == 0]


def build_frames(ticker, anchor, tf_cfg, fetch_cache, now) -> Dict[str, Tuple[pd.DataFrame, bool]]:
    """All configured TF frames for one asset (needed so DRS can use any TF)."""
    frames: Dict[str, Tuple[pd.DataFrame, bool]] = {}
    for tf, spec in tf_cfg.items():
        src = str(spec["source_interval"]); per = str(spec["period"]); rule = spec.get("resample")
        ck = (ticker, src, per)
        if ck not in fetch_cache:
            fetch_cache[ck] = fetch_ohlcv(ticker, src, per)
        base = fetch_cache[ck]
        if base is None or base.empty:
            continue
        has_vol = ("Volume" in base) and float(np.nansum(base["Volume"].to_numpy())) > 0
        frame = resample_ohlcv(base, rule, anchor) if rule else base
        frame = drop_incomplete_last_bar(frame, parse_tf_minutes(tf), now)
        if len(frame) >= 220:
            frames[tf] = (frame, has_vol)
    return frames


def main() -> int:
    ap = argparse.ArgumentParser(description="V5 CONFLUENCE scanner")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--timeframes", default="auto")
    ap.add_argument("--assets", default=None)
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-freshness", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    div_cfg = cfg["divergence"]
    tf_cfg = cfg["timeframes"]
    assets: Dict[str, dict] = cfg["assets"]
    buffer_min = int(cfg.get("freshness_buffer_minutes", 45))
    drs_cfg = cfg.get("drs", {})
    zone_days = int(drs_cfg.get("zone_max_days", 30))
    buf_atr = float(drs_cfg.get("buffer_atr", 0.5))
    sl_mult = float(div_cfg.get("sl_atr_mult", 1.5))
    tp_mult = float(div_cfg.get("tp_atr_mult", 4.0))
    equity, risk_pct = resolve_sizing(cfg)

    if args.assets:
        wanted = [a.strip() for a in args.assets.split(",")]
        assets = {a: assets[a] for a in wanted if a in assets}

    now_dt = datetime.now(timezone.utc)
    now = pd.Timestamp(now_dt).tz_localize(None)
    if args.timeframes == "auto":
        tfs = due_timeframes(tf_cfg, now_dt)
    elif args.timeframes == "all":
        tfs = list(tf_cfg)
    else:
        tfs = [t.strip() for t in args.timeframes.split(",")]

    print(f"V5 CONFLUENCE scan @ {now_dt:%Y-%m-%d %H:%M} UTC")
    print(f"Sizing: base ${equity:,.2f}  risk {risk_pct*100:.0f}%")
    print(f"Timeframes due: {tfs or 'none'}  |  assets: {list(assets)}")
    if not tfs:
        return 0

    fetch_cache: Dict = {}
    all_new: List[DivergenceSignal] = []
    state = load_state(STATE_PATH)

    for asset, spec in assets.items():
        ticker = spec["ticker"]; anchor = spec.get("anchor", "utc")
        allowed = [str(x).lower() for x in spec.get("dirs", ["buy", "sell"])]
        frames = build_frames(ticker, anchor, tf_cfg, fetch_cache, now)
        if not frames:
            print(f"  {asset:<8} no data"); continue
        red_long, tl = drs_active_red(frames, "long", now, zone_days) if "buy" in allowed else (None, None)
        red_short, ts = drs_active_red(frames, "short", now, zone_days) if "sell" in allowed else (None, None)

        found: List[DivergenceSignal] = []
        for tf in tfs:
            if tf not in frames:
                continue
            frame, _ = frames[tf]
            sigs = confluence_on_frame(frame, asset, ticker, tf,
                                       parse_tf_minutes(tf), div_cfg, allowed,
                                       red_long, red_short, sl_mult, tp_mult, buf_atr)
            if not args.no_freshness:
                sigs = filter_fresh(sigs, now,
                                    int(tf_cfg[tf].get("scan_every_minutes", 60)), buffer_min)
            found.extend(sigs)
        found, state = dedup_signals(found, state)
        for s in found:
            print(f"  {s.side:<4} {asset:<8} {s.timeframe:<4} entry={s.close:.5f} "
                  f"SL={s.stop:.5f} TP={s.target:.5f}  DRS_red={getattr(s,'drs_red',float('nan')):.5f}")
        all_new.extend(found)

    save_state(STATE_PATH, state)

    # ---- static-base ledger ----
    portfolio = None
    risk_dollars = risk_pct * equity
    try:
        led_cache: Dict = {}

        def fetch_1h(tk):
            if tk not in led_cache:
                led_cache[tk] = fetch_ohlcv(tk, "1h", "120d")
            return led_cache[tk]

        ledger = v5_ledger.load_ledger(LEDGER_PATH)
        ledger, closed = v5_ledger.reconcile(ledger, fetch_1h, now)
        for c in closed:
            print(f"  ledger close {c['asset']:<8} {c['tf']:<4} {c['outcome']:<6} "
                  f"{c['R']:+.0f}R  {c['pnl']:+.2f}")
        if all_new:
            v5_ledger.register(ledger, all_new, risk_dollars)
        v5_ledger.save_ledger(LEDGER_PATH, ledger)
        portfolio = v5_ledger.status(ledger, equity, risk_pct)
        print(f"Ledger: realized {portfolio['realized_pnl']:+.2f} "
              f"({portfolio['realized_r']:+.1f}R)  open {portfolio['open_count']}  "
              f"hit-40%={portfolio['hit_40']}")
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: ledger update failed ({exc}); emailing without P&L block")

    if not all_new:
        print("No new confluence setups this run.")
        return 0
    print(f"{len(all_new)} new confluence setup(s).")
    if args.no_email:
        print("--no-email set; skipping send.")
        return 0

    subject, html = build_confluence_email(all_new, equity=equity,
                                           risk_pct=risk_pct, portfolio=portfolio)
    ok = _send_html_email(subject, html, os.environ.get("EMAIL_ADDRESS", ""),
                          os.environ.get("EMAIL_PASSWORD", ""), EMAIL_LOG)
    print("Email sent." if ok else "Email FAILED — see logs/email.log")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
