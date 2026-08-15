"""V5 winners-only forward test -> tabbed Excel workbook.

Scope (per user):
  Assets   : the 5 positive-expectancy 'winners' -> BTCUSD, ETHUSD, DOGEUSD,
             XAUUSD, NAS100.
  TFs      : 15m, 1h, 2h, 3h, 4h  (30m/45m dropped — they were the losers).
  Windows  : last 30 days AND last 90 days.
             15m has only ~60d of yfinance history, so its 90d column is
             capped at whatever <=60d is available (flagged in the sheet).
  Model    : enter at confirmation-bar close; BULL->BUY, BEAR->SELL;
             SL 1.5xATR, TP 3.0xATR  -> +2R win / -1R loss; open->mark-to-mkt.
  Times    : UTC only.  Each trade shows entry (confirm) AND exit timestamp.

Output: logs/v5_winners_review.xlsx  with tabs:
  - Detail 30d, Detail 90d  (one row per signal)
  - Summary  (per-asset + per-timeframe grids for both windows)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.v5_divergence import (          # noqa: E402
    detect_divergences, drop_incomplete_last_bar, fetch_ohlcv,
    parse_tf_minutes, resample_ohlcv,
)

WINNERS = ["BTCUSD", "ETHUSD", "DOGEUSD", "XAUUSD", "NAS100"]
TFS = ["15m", "1h", "2h", "3h", "4h"]
SL_MULT, TP_MULT = 1.5, 3.0
R_WIN, R_LOSS = TP_MULT / SL_MULT, -1.0
# fetch periods chosen to cover a 90d window (+ SMA200 warmup)
FETCH_PERIOD = {"15m": "60d", "1h": "180d"}


def atr_wilder(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift()
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()


def score(frame, ci, direction, entry, atr_val):
    """Return (outcome, R, exit_idx)."""
    high, low, close = (frame["High"].to_numpy(), frame["Low"].to_numpy(),
                        frame["Close"].to_numpy())
    n = len(frame)
    risk = SL_MULT * atr_val
    if direction == "BULL":
        sl, tp = entry - risk, entry + TP_MULT * atr_val
    else:
        sl, tp = entry + risk, entry - TP_MULT * atr_val
    for j in range(ci + 1, n):
        if direction == "BULL":
            hit_sl, hit_tp = low[j] <= sl, high[j] >= tp
        else:
            hit_sl, hit_tp = high[j] >= sl, low[j] <= tp
        if hit_sl:                       # SL checked first = conservative
            return "SL", R_LOSS, j
        if hit_tp:
            return "TP", R_WIN, j
    move = (close[-1] - entry) if direction == "BULL" else (entry - close[-1])
    return "OPEN", move / risk, n - 1


def collect(div_cfg, tf_cfg, assets_cfg, now, win_days, fetch_cache):
    win_lo = now - pd.Timedelta(days=win_days)
    rows = []
    for asset in WINNERS:
        spec = assets_cfg[asset]
        ticker = spec["ticker"]; anchor = spec.get("anchor", "utc")
        for tf in TFS:
            tspec = tf_cfg[tf]
            bar_min = parse_tf_minutes(tf)
            source = str(tspec["source_interval"])
            period = FETCH_PERIOD[source]
            rule = tspec.get("resample")
            ck = (ticker, source, period)
            if ck not in fetch_cache:
                fetch_cache[ck] = fetch_ohlcv(ticker, source, period)
            df = fetch_cache[ck]
            if df is None or df.empty:
                continue
            frame = resample_ohlcv(df, rule, anchor) if rule else df
            frame = drop_incomplete_last_bar(frame, bar_min, now)
            if len(frame) < int(div_cfg["trend_sma"]) + 10:
                continue
            atr = atr_wilder(frame, int(div_cfg.get("atr_len", 14)))
            sigs = detect_divergences(frame, asset, ticker, tf, bar_min, div_cfg)
            pos = {t: k for k, t in enumerate(frame.index)}
            for s in sigs:
                if not (win_lo <= s.confirm_close_time <= now):
                    continue
                ci = pos.get(s.confirm_time)
                if ci is None or not np.isfinite(atr[ci]) or atr[ci] <= 0:
                    continue
                a = atr[ci]; entry = s.close
                outcome, r, xi = score(frame, ci, s.direction, entry, a)
                risk = SL_MULT * a
                sl = entry - risk if s.direction == "BULL" else entry + risk
                tp = (entry + TP_MULT * a if s.direction == "BULL"
                      else entry - TP_MULT * a)
                exit_close_t = frame.index[xi] + pd.Timedelta(minutes=bar_min)
                rows.append(dict(
                    entry_time_utc=s.confirm_close_time,
                    asset=asset, tf=tf,
                    side="BUY" if s.direction == "BULL" else "SELL",
                    direction=s.direction, span=s.span,
                    entry_price=round(entry, 6),
                    stop_price=round(sl, 6), target_price=round(tp, 6),
                    atr=round(a, 6),
                    outcome=outcome,
                    exit_time_utc=exit_close_t if outcome != "OPEN" else pd.NaT,
                    bars_held=xi - ci,
                    R=round(r, 3),
                ))
    return pd.DataFrame(rows).sort_values("entry_time_utc").reset_index(drop=True)


def grid(d: pd.DataFrame, key: str, order) -> pd.DataFrame:
    out = []
    for k in order:
        sub = d[d[key] == k]
        if sub.empty:
            continue
        res = sub[sub.outcome != "OPEN"]
        out.append(dict(**{key: k}, n=len(sub),
                        TP=int((sub.outcome == "TP").sum()),
                        SL=int((sub.outcome == "SL").sum()),
                        open=int((sub.outcome == "OPEN").sum()),
                        resolved_WR_pct=round(100 * (res.outcome == "TP").mean(), 1)
                        if len(res) else np.nan,
                        total_R=round(sub.R.sum(), 1),
                        exp_per_trade_R=round(res.R.mean(), 3) if len(res) else np.nan))
    return pd.DataFrame(out)


def overall_row(label, d):
    res = d[d.outcome != "OPEN"]
    return dict(scope=label, n=len(d),
                TP=int((d.outcome == "TP").sum()),
                SL=int((d.outcome == "SL").sum()),
                open=int((d.outcome == "OPEN").sum()),
                resolved_WR_pct=round(100 * (res.outcome == "TP").mean(), 1)
                if len(res) else np.nan,
                total_R=round(d.R.sum(), 1),
                exp_per_trade_R=round(res.R.mean(), 3) if len(res) else np.nan)


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "v5_scanner.yaml").read_text("utf-8"))
    div_cfg = dict(cfg["divergence"]); div_cfg["aligned_only"] = True
    tf_cfg = cfg["timeframes"]; assets_cfg = cfg["assets"]
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)

    fetch_cache: dict = {}
    d30 = collect(div_cfg, tf_cfg, assets_cfg, now, 30, fetch_cache)
    d90 = collect(div_cfg, tf_cfg, assets_cfg, now, 90, fetch_cache)

    # 15m real coverage in the 90d window (history is <=60d)
    d90_15 = d90[d90.tf == "15m"]
    cov15 = (f"{(now - d90_15.entry_time_utc.min()).days}d actual"
             if not d90_15.empty else "no data")

    print(f"30d signals: {len(d30)}   90d signals: {len(d90)}   "
          f"(15m 90d coverage: {cov15})")

    out = ROOT / "logs" / "v5_winners_review.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        d30.to_excel(xl, sheet_name="Detail 30d", index=False)
        d90.to_excel(xl, sheet_name="Detail 90d", index=False)

        # ---- Summary sheet ----
        summ = []
        summ.append(pd.DataFrame([overall_row("ALL 30d", d30),
                                  overall_row("ALL 90d", d90)]))
        blocks = [("=== 30d by timeframe ===", grid(d30, "tf", TFS)),
                  ("=== 30d by asset ===", grid(d30, "asset", WINNERS)),
                  ("=== 90d by timeframe ===", grid(d90, "tf", TFS)),
                  ("=== 90d by asset ===", grid(d90, "asset", WINNERS))]
        start = 0
        overall = pd.concat(summ, ignore_index=True)
        overall.to_excel(xl, sheet_name="Summary", index=False, startrow=start)
        start = len(overall) + 3
        ws = xl.sheets["Summary"]
        for title, g in blocks:
            ws.cell(row=start, column=1, value=title)
            g.to_excel(xl, sheet_name="Summary", index=False, startrow=start)
            start += len(g) + 3
        note = ("NOTE: 15m yfinance history is ~60d, so its 90d figures cover "
                f"only {cov15}. 1h/2h/3h/4h use the full 90d. "
                "Model: enter at confirmation-bar close, SL 1.5xATR, TP 3xATR "
                "(+2R win / -1R loss), SL-first on same-bar ties. Times UTC.")
        ws.cell(row=start, column=1, value=note)

    # console summary
    for label, d in (("30d", d30), ("90d", d90)):
        r = overall_row(label, d)
        print(f"\n{label}: n={r['n']} TP={r['TP']} SL={r['SL']} open={r['open']} "
              f"WR={r['resolved_WR_pct']}%  totalR={r['total_R']:+}  "
              f"exp={r['exp_per_trade_R']:+}R")
        print(grid(d, "tf", TFS).to_string(index=False))
        print(grid(d, "asset", WINNERS).to_string(index=False))

    print(f"\nWorkbook -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
