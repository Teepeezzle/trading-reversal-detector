"""Track B — forward shadow test for fundamentals on the Confluence Board.

We CANNOT validate "fundamentals improve signals" on the backtest sample (65 signals; D-033). So we
accumulate a real forward sample instead. This logs every fresh confluence SETUP from now on, together
with (1) the full point-in-time fundamental context vector at signal time (every value with its
available_at) and (2) the three honest shadow USES recorded in parallel but NEVER acted on:
  (a) hard gate, (b) score adjustment, (c) regime tag.
Later it resolves each signal's outcome (SL 1.5xATR / TP 4xATR, +2.667R / -1R, 30-day cap) and reports
running sample size + stats. No verdict is produced here; the milestone gates (SHADOW_TEST.md / D-034)
govern when a verdict may be attempted: n=100 read, n=200 significance, n=400 walk-forward.

Subcommands:
  record    append fresh SETUP signals (+ context + shadow variants); never re-acts on past rows
  resolve   fill outcomes for matured signals (first-touch SL/TP within the horizon)
  report    write forward_test/STATUS.md (sample size + running stats + milestone status)
  all       record -> resolve -> report  (what the weekly workflow runs)

Read-only market/fundamental data. No look-ahead: a signal's context uses only records with
available_at <= signal time; outcomes use only bars AFTER entry.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))
import dashboard_data as dd          # noqa: E402  (reuse the LIVE signal machinery; not modified)
import fundamentals as FUND          # noqa: E402
from src.v5_divergence import fetch_ohlcv   # noqa: E402

SIGNALS = HERE / "signals.csv"
SHADOW = HERE / "shadow.csv"
STATUS = HERE / "STATUS.md"
HORIZON_DAYS = 30                    # resolution cap (DRS zone horizon); exit at cap if neither level hit
R_WIN, R_LOSS = dd.TP_ATR / dd.SL_ATR, -1.0

SIG_COLS = ["signal_id", "logged_at", "instrument", "asset_class", "direction", "tf",
            "confirm_time", "entry", "stop", "target", "horizon_days",
            "macro_rates", "macro_infl", "macro_infl_yoy", "usd_backdrop", "dxy_trend", "vol_regime",
            "macro_available_at", "next_event", "next_event_at", "next_event_within",
            "context_json", "outcome", "exit_time", "exit_price", "R", "resolved_at"]
SHA_COLS = ["signal_id", "recorded_at", "instrument", "direction",
            "gate_pass", "gate_reason", "score_delta", "score_parts", "tag"]


def _read(path, cols):
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=cols)


def _append(path, cols, rows):
    if not rows:
        return
    df = pd.DataFrame(rows)[cols]
    hdr = not path.exists()
    df.to_csv(path, mode="a", header=hdr, index=False)


# ----------------------------- record -----------------------------
def record(universe: dict | None = None) -> int:
    """Append any FRESH SETUP (status==SETUP) not already logged, with context + shadow variants."""
    if universe is None:
        universe = dd.ASSETS
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    bundle = FUND.load_bundle()
    existing = set(_read(SIGNALS, SIG_COLS)["signal_id"].astype(str)) if SIGNALS.exists() else set()
    cache = {}
    new_sig, new_sha = [], []
    for asset, spec in universe.items():
        tk = spec["ticker"]; anchor = spec.get("anchor", "utc")
        allowed = [str(x).lower() for x in spec.get("dirs", ["buy", "sell"])]
        try:
            st = dd.asset_state(asset, tk, anchor, allowed, False, cache, now)
        except Exception as exc:  # noqa: BLE001
            print(f"{asset:<8} skip ({exc})"); continue
        if not st or st.get("status") != "SETUP" or not st.get("setup"):
            continue
        s = st["setup"]; side = s["side"].lower()
        confirm = st.get("updated")                    # board doesn't expose setup's own ts; use snapshot bar
        sid = f"{asset}|{s['tf']}|{confirm}"
        if sid in existing:
            continue
        aclass = FUND.class_of(asset)
        ctx = FUND.context_vector(asset, confirm, price_frame=dd._frame_for(cache, tk), bundle=bundle)
        sh = FUND.shadow_variants(asset, side, confirm, bundle=bundle)
        m = ctx["macro_regime"]; ne = ctx.get("next_event") or {}
        new_sig.append({
            "signal_id": sid, "logged_at": str(now), "instrument": asset, "asset_class": aclass,
            "direction": side, "tf": s["tf"], "confirm_time": confirm,
            "entry": s["entry"], "stop": s["stop"], "target": s["target"], "horizon_days": HORIZON_DAYS,
            "macro_rates": m.get("rates_dir"), "macro_infl": m.get("inflation_dir"),
            "macro_infl_yoy": m.get("inflation_yoy_pct"), "usd_backdrop": m.get("usd_backdrop"),
            "dxy_trend": m.get("dxy_trend"), "vol_regime": ctx["vol_regime"].get("regime"),
            "macro_available_at": m.get("available_at"), "next_event": ne.get("name"),
            "next_event_at": ne.get("expected_at"), "next_event_within": ne.get("within_horizon"),
            "context_json": json.dumps(ctx, separators=(",", ":"), default=str),
            "outcome": "", "exit_time": "", "exit_price": "", "R": "", "resolved_at": ""})
        new_sha.append({
            "signal_id": sid, "recorded_at": str(now), "instrument": asset, "direction": side,
            "gate_pass": sh["gate"]["pass"], "gate_reason": sh["gate"]["reason"],
            "score_delta": sh["score"]["delta"], "score_parts": ";".join(sh["score"]["parts"]),
            "tag": sh["tag"]})
        print(f"LOG {sid}  {side.upper()} entry={s['entry']} gate={'pass' if sh['gate']['pass'] else 'BLOCK'} "
              f"score={sh['score']['delta']:+.2f} tag={sh['tag']}")
    _append(SIGNALS, SIG_COLS, new_sig)
    _append(SHADOW, SHA_COLS, new_sha)
    print(f"record: {len(new_sig)} new signal(s) logged (universe {len(universe)} assets).")
    return len(new_sig)


# ----------------------------- resolve -----------------------------
def _first_touch(bars, entry, stop, target, side):
    """First-touch SL/TP after entry; return (exit_time, exit_price, R, outcome). Cap at last bar."""
    risk = abs(entry - stop)
    if risk <= 0 or bars.empty:
        return None
    h = bars["High"].to_numpy(); lo = bars["Low"].to_numpy(); c = bars["Close"].to_numpy()
    t = bars.index
    for i in range(len(bars)):
        if side == "buy":
            if lo[i] <= stop: return str(t[i]), float(stop), R_LOSS, "loss"
            if h[i] >= target: return str(t[i]), float(target), R_WIN, "win"
        else:
            if h[i] >= stop: return str(t[i]), float(stop), R_LOSS, "loss"
            if lo[i] <= target: return str(t[i]), float(target), R_WIN, "win"
    last = float(c[-1]); r = (last - entry) / risk * (1 if side == "buy" else -1)
    return str(t[-1]), last, round(float(r), 3), "expired"


def resolve(universe: dict | None = None) -> int:
    if universe is None:
        universe = dd.ASSETS
    sig = _read(SIGNALS, SIG_COLS)
    if sig.empty:
        print("resolve: no signals logged yet."); return 0
    for c in ("outcome", "exit_time", "exit_price", "R", "resolved_at"):   # allow string/mixed writes
        sig[c] = sig[c].astype("object")
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    tick = {a: s["ticker"] for a, s in universe.items()}
    n = 0
    for i, row in sig.iterrows():
        if str(row.get("outcome", "")) not in ("", "nan", "open"):
            continue
        ct = pd.to_datetime(row["confirm_time"], errors="coerce")
        if pd.isna(ct):
            continue
        tk = tick.get(row["instrument"])
        if not tk:
            continue
        try:
            bars = fetch_ohlcv(tk, "1h", "730d")
        except Exception:
            bars = None
        if bars is None or bars.empty:
            sig.at[i, "outcome"] = "open"; continue
        win = bars[(bars.index > ct) & (bars.index <= ct + pd.Timedelta(days=int(row["horizon_days"])))]
        matured = (now - ct) >= pd.Timedelta(days=int(row["horizon_days"]))
        res = _first_touch(win, float(row["entry"]), float(row["stop"]), float(row["target"]), row["direction"])
        if res is None:
            sig.at[i, "outcome"] = "open"; continue
        et, ep, r, oc = res
        if oc == "expired" and not matured:
            sig.at[i, "outcome"] = "open"; continue        # not enough time elapsed; leave open
        sig.at[i, "outcome"] = oc; sig.at[i, "exit_time"] = et; sig.at[i, "exit_price"] = ep
        sig.at[i, "R"] = r; sig.at[i, "resolved_at"] = str(now); n += 1
    sig.to_csv(SIGNALS, index=False)
    print(f"resolve: {n} signal(s) newly resolved; {int((sig['outcome']=='open').sum())} still open.")
    return n


# ----------------------------- report -----------------------------
def _stats(df):
    r = pd.to_numeric(df["R"], errors="coerce").dropna()
    if r.empty:
        return dict(n=0, expR=np.nan, win=np.nan)
    return dict(n=int(len(r)), expR=round(float(r.mean()), 3),
                win=round(float((r > 0).mean() * 100), 1))


def report() -> None:
    sig = _read(SIGNALS, SIG_COLS)
    resolved = sig[pd.to_numeric(sig["R"], errors="coerce").notna()] if not sig.empty else sig
    n_total = len(sig); n_res = len(resolved)
    ov = _stats(resolved) if n_res else dict(n=0, expR=np.nan, win=np.nan)
    gates = {100: "preliminary read (NO verdict)", 200: "first significance test (MTC)",
             400: "walk-forward validation"}
    nxt = next((g for g in sorted(gates) if n_res < g), None)
    lines = [
        "# Forward shadow test — STATUS",
        "",
        f"_Updated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. No verdict is made here; milestone "
        "gates govern (see SHADOW_TEST.md / D-034)._",
        "",
        f"- Signals logged: **{n_total}** · resolved: **{n_res}** · open: **{n_total - n_res}**",
        f"- Running (resolved) expectancy: **{ov['expR']}R** · win **{ov['win']}%** · n={ov['n']}  "
        "(baseline confluence; shadow variants compared at the gates, not here)",
        f"- Next milestone: **n={nxt} — {gates[nxt]}**" if nxt else
        "- All milestones reached (n>=400): walk-forward may run.",
        "",
        "| milestone | threshold | reached? | unlocks |",
        "|---|--:|:--:|---|",
    ]
    for g, what in gates.items():
        lines.append(f"| {what} | {g} | {'✅' if n_res >= g else '—'} | "
                     f"{'read only' if g==100 else 'significance + MTC' if g==200 else 'walk-forward'} |")
    if n_res:
        lines += ["", "### Resolved by asset class", "", "| class | n | expR | win% |", "|---|--:|--:|--:|"]
        for cls, g in resolved.groupby("asset_class"):
            s = _stats(g); lines.append(f"| {cls} | {s['n']} | {s['expR']} | {s['win']} |")
    else:
        lines += ["", "_No resolved signals yet — the log is accumulating. This is expected; the "
                  "confluence fires ~30x/yr across the validated universe, so a 200-signal sample is a "
                  "multi-quarter horizon, which is exactly why we forward-test instead of over-reading "
                  "the 65-signal backtest._"]
    STATUS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {n_total} logged / {n_res} resolved -> {STATUS.name}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["record", "resolve", "report", "all"], default="all", nargs="?")
    a = ap.parse_args()
    if a.cmd in ("record", "all"):
        record()
    if a.cmd in ("resolve", "all"):
        resolve()
    if a.cmd in ("report", "all"):
        report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
