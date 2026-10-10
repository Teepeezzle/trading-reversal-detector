"""Forward / out-of-sample tracker for the V5 PARITY (H1) scanner.

The backtest said H1 is NOT a robust edge; the honest next step is to record
the scanner's LIVE signals from deployment onward and score them forward, with
no look-ahead, so a real out-of-sample expectancy accumulates. This logs every
H1-qualifying aligned divergence (run in {2,4}, even span, span>run, span<=20)
that confirms on/after FORWARD_START, attaches the live SL 1.5xATR / TP 4.0xATR
levels (the project's model), later resolves first-touch outcomes within a
30-day horizon, and reports running stats. NO verdict is made here — milestone
gates govern (n=50 read / 100 significance / 200 walk-forward).

Subcommands:  record | resolve | report | all   (the workflow runs 'all').

Data: same yfinance layer and config as parity_scan.py. No look-ahead — a
signal's levels use only its confirmation bar; outcomes use only bars AFTER it.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import (            # noqa: E402
    atr_wilder, detect_divergences, drop_incomplete_last_bar, fetch_ohlcv,
    parse_tf_minutes, resample_ohlcv,
)
from parity_scan import qualifies_h1        # noqa: E402

CONFIG = ROOT / "config" / "parity_scanner.yaml"
SIGNALS = HERE / "parity_signals.csv"
STATUS = HERE / "PARITY_STATUS.md"

# Out-of-sample boundary: only log signals that CONFIRM on/after this instant
# (the scanner's deploy date). Nothing before it is ever logged — guarantees OOS.
FORWARD_START = pd.Timestamp("2026-10-10 00:00:00")
HORIZON_DAYS = 30
SL_ATR, TP_ATR = 1.5, 4.0
R_WIN, R_LOSS = TP_ATR / SL_ATR, -1.0
GATES = {50: "preliminary read (NO verdict)", 100: "first significance test",
         200: "walk-forward validation"}

COLS = ["signal_id", "logged_at", "instrument", "asset_class", "direction", "tf",
        "confirm_time", "entry", "stop", "target", "run", "span", "regime",
        "horizon_days", "outcome", "exit_time", "exit_price", "R", "resolved_at"]


def _class_of(asset: str) -> str:
    if asset in ("BTCUSD", "ETHUSD", "DOGEUSD"):
        return "crypto"
    if asset in ("XAUUSD", "XAGUSD", "XBRUSD"):
        return "commodity"
    if asset in ("NAS100", "DXY"):
        return "index"
    return "fx"


def _cfg():
    c = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return c["divergence"], c.get("parity", {}), c["timeframes"], c["assets"]


def _frame(ticker: str, tf: str, spec: dict, anchor: str, now: pd.Timestamp):
    df = fetch_ohlcv(ticker, str(spec["source_interval"]), str(spec["period"]))
    if df is None or df.empty:
        return None
    rule = spec.get("resample")
    frame = resample_ohlcv(df, rule, anchor) if rule else df
    return drop_incomplete_last_bar(frame, parse_tf_minutes(tf), now)


def _read():
    if SIGNALS.exists():
        return pd.read_csv(SIGNALS)
    return pd.DataFrame(columns=COLS)


def _ensure_file():
    """Guarantee the log CSV exists (header-only when empty) so downstream
    git/persistence steps always have a file to add, even on a 0-signal run."""
    if not SIGNALS.exists():
        pd.DataFrame(columns=COLS).to_csv(SIGNALS, index=False)


# ----------------------------- record -----------------------------
def record() -> int:
    div_cfg, parity_cfg, tf_cfg, assets = _cfg()
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    existing = set(_read()["signal_id"].astype(str)) if SIGNALS.exists() else set()
    cache, rows = {}, []
    for asset, aspec in assets.items():
        ticker = aspec["ticker"] if isinstance(aspec, dict) else aspec
        anchor = aspec.get("anchor", "utc") if isinstance(aspec, dict) else "utc"
        for tf, spec in tf_cfg.items():
            ck = (ticker, str(spec["source_interval"]), str(spec["period"]))
            if ck not in cache:
                cache[ck] = _frame(ticker, tf, spec, anchor, now)
            frame = cache[ck] if spec.get("resample") is None else _frame(ticker, tf, spec, anchor, now)
            if frame is None or len(frame) < int(div_cfg["trend_sma"]) + 10:
                continue
            atr = atr_wilder(frame, 14)
            pos = {t: i for i, t in enumerate(frame.index)}
            sigs = [s for s in detect_divergences(frame, asset, ticker, tf, parse_tf_minutes(tf), div_cfg)
                    if qualifies_h1(s, parity_cfg)]
            for s in sigs:
                if s.confirm_close_time < FORWARD_START or s.signal_id in existing:
                    continue
                i = pos.get(s.confirm_time)
                if i is None or not np.isfinite(atr[i]) or atr[i] <= 0:
                    continue
                a = float(atr[i])
                if s.direction == "BULL":
                    stop, tgt = s.close - SL_ATR * a, s.close + TP_ATR * a
                else:
                    stop, tgt = s.close + SL_ATR * a, s.close - TP_ATR * a
                rows.append(dict(
                    signal_id=s.signal_id, logged_at=str(now), instrument=asset,
                    asset_class=_class_of(asset), direction=s.direction, tf=tf,
                    confirm_time=str(s.confirm_close_time), entry=round(s.close, 6),
                    stop=round(stop, 6), target=round(tgt, 6), run=s.run, span=s.span,
                    regime=s.regime, horizon_days=HORIZON_DAYS, outcome="open",
                    exit_time="", exit_price="", R="", resolved_at=""))
                existing.add(s.signal_id)
    if rows:
        df = pd.DataFrame(rows)[COLS]
        df.to_csv(SIGNALS, mode="a", header=not SIGNALS.exists(), index=False)
    print(f"record: {len(rows)} new H1 signal(s) logged (OOS from {FORWARD_START.date()}).")
    return len(rows)


# ----------------------------- resolve -----------------------------
def _first_touch(bars, entry, stop, target, direction):
    if bars.empty:
        return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    h, lo, c, t = bars.High.to_numpy(), bars.Low.to_numpy(), bars.Close.to_numpy(), bars.index
    for i in range(len(bars)):
        if direction == "BULL":
            if lo[i] <= stop: return str(t[i]), float(stop), R_LOSS, "loss"
            if h[i] >= target: return str(t[i]), float(target), R_WIN, "win"
        else:
            if h[i] >= stop: return str(t[i]), float(stop), R_LOSS, "loss"
            if lo[i] <= target: return str(t[i]), float(target), R_WIN, "win"
    last = float(c[-1])
    r = (last - entry) / risk * (1 if direction == "BULL" else -1)
    return str(t[-1]), last, round(float(r), 3), "expired"


def resolve() -> int:
    sig = _read()
    if sig.empty:
        print("resolve: nothing logged yet."); return 0
    div_cfg, _, tf_cfg, assets = _cfg()
    for col in ("outcome", "exit_time", "exit_price", "R", "resolved_at"):
        sig[col] = sig[col].astype("object")
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cache, n = {}, 0
    for i, row in sig.iterrows():
        if str(row.get("outcome", "")) not in ("", "nan", "open"):
            continue
        ct = pd.to_datetime(row["confirm_time"], errors="coerce")
        if pd.isna(ct):
            continue
        aspec = assets.get(row["instrument"])
        if aspec is None:
            continue
        ticker = aspec["ticker"] if isinstance(aspec, dict) else aspec
        anchor = aspec.get("anchor", "utc") if isinstance(aspec, dict) else "utc"
        tf = row["tf"]; spec = tf_cfg[tf]
        ck = (ticker, tf)
        if ck not in cache:
            cache[ck] = _frame(ticker, tf, spec, anchor, now)
        frame = cache[ck]
        if frame is None or frame.empty:
            continue
        horizon = pd.Timedelta(days=int(row["horizon_days"]))
        win = frame[(frame.index > ct) & (frame.index <= ct + horizon)]
        matured = (now - ct) >= horizon
        res = _first_touch(win, float(row["entry"]), float(row["stop"]), float(row["target"]), row["direction"])
        if res is None:
            continue
        et, ep, r, oc = res
        if oc == "expired" and not matured:
            continue                       # neither level hit yet and horizon not elapsed -> stay open
        sig.at[i, "outcome"] = oc; sig.at[i, "exit_time"] = et
        sig.at[i, "exit_price"] = ep; sig.at[i, "R"] = r; sig.at[i, "resolved_at"] = str(now)
        n += 1
    sig.to_csv(SIGNALS, index=False)
    openn = int((sig["outcome"].astype(str) == "open").sum())
    print(f"resolve: {n} newly resolved; {openn} still open.")
    return n


# ----------------------------- report -----------------------------
def _stats(df):
    r = pd.to_numeric(df["R"], errors="coerce").dropna()
    if r.empty:
        return dict(n=0, expR=float("nan"), win=float("nan"), pf=float("nan"))
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    pf = (pos / neg) if neg > 0 else float("inf")
    return dict(n=int(len(r)), expR=round(float(r.mean()), 3),
                win=round(float((r > 0).mean() * 100), 1),
                pf=round(float(pf), 2) if np.isfinite(pf) else float("inf"))


def report() -> None:
    sig = _read()
    res = sig[pd.to_numeric(sig["R"], errors="coerce").notna()] if not sig.empty else sig
    n_total, n_res = len(sig), len(res)
    ov = _stats(res)
    nxt = next((g for g in sorted(GATES) if n_res < g), None)
    L = [
        "# V5 PARITY (H1) — forward / out-of-sample tracker",
        "",
        f"_Updated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. OOS from "
        f"{FORWARD_START.date()}. No verdict here — gates govern (n=50/100/200)._",
        "",
        "> The backtest found H1 is **not** a robust standalone edge. This log exists to "
        "confirm or refute that forward, on signals the scanner actually emitted.",
        "",
        f"- Signals logged: **{n_total}** · resolved: **{n_res}** · open: **{n_total - n_res}**",
        f"- Running expectancy: **{ov['expR']}R** · win **{ov['win']}%** · PF **{ov['pf']}** · n={ov['n']}",
        (f"- Next milestone: **n={nxt} — {GATES[nxt]}**" if nxt else
         "- All milestones reached (n>=200): walk-forward may run."),
        "",
        "| milestone | threshold | reached? |", "|---|--:|:--:|",
    ]
    for g, what in GATES.items():
        L.append(f"| {what} | {g} | {'yes' if n_res >= g else '—'} |")
    if n_res:
        L += ["", "### Resolved by asset", "", "| asset | n | expR | win% | PF |", "|---|--:|--:|--:|--:|"]
        for a, g in res.groupby("instrument"):
            s = _stats(g); L.append(f"| {a} | {s['n']} | {s['expR']} | {s['win']} | {s['pf']} |")
        L += ["", "### Resolved by timeframe", "", "| tf | n | expR | win% | PF |", "|---|--:|--:|--:|--:|"]
        for tf, g in res.groupby("tf"):
            s = _stats(g); L.append(f"| {tf} | {s['n']} | {s['expR']} | {s['win']} | {s['pf']} |")
    else:
        L += ["", "_No resolved signals yet — accumulating. H1 fires selectively, so a 50-signal "
              "read is a multi-week horizon; that wait is the point of forward testing._"]
    STATUS.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"report: {n_total} logged / {n_res} resolved -> {STATUS.name}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["record", "resolve", "report", "all"], default="all", nargs="?")
    a = ap.parse_args()
    _ensure_file()
    if a.cmd in ("record", "all"):
        record()
    if a.cmd in ("resolve", "all"):
        resolve()
    if a.cmd in ("report", "all"):
        report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
