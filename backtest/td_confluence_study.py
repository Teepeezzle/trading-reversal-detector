"""TD Sequential (13+ zone & parity) and MACD-even/even + TD confluence.

Faithful to the Enhanced TD Sequential v2 Pine: TD Setup = 9 consecutive closes
< close[lookback] (buy) / > close[lookback] (sell); Countdown after a setup-9 =
bars closing <= low[2] (buy) / >= high[2] (sell), EXTENDED past 13 to 20 so we
can study 13/14/15/16/... An opposite setup-9 cancels; same-side recycles.

Trades: TD is an exhaustion/mean-reversion signal -> buy countdown = LONG, sell
countdown = SHORT, entered at the CLOSE of the bar that prints the count (no
lookahead). MACD divergences reuse the Script-A logic (pivots left5/right rb,
run=consecutive HH/LL, span=bars between pivots, even/even = run%2==0 & span%2==0
& span>run). Same exit for everything: SL 1.5xATR / TP 4xATR (+2.667R/-1R), 0.05%
/side commission + 1bp slippage. 8 assets x 1h/4h/1D.

Answers: (B) does TD countdown 13-20 have an edge, and is even>odd? (C) is
MACD-even/even + TD-13+ within 5 bars superior to either alone? + lookback/vol grid.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import (          # noqa: E402
    atr_wilder, fetch_ohlcv, resample_ohlcv, drop_incomplete_last_bar,
)

ASSETS = {
    "BTCUSD": ("BTC-USD", "utc"), "ETHUSD": ("ETH-USD", "utc"),
    "XAUUSD": ("GC=F", "ny17"), "NAS100": ("NQ=F", "ny17"),
    "USDJPY": ("USDJPY=X", "ny17"), "EURUSD": ("EURUSD=X", "ny17"),
    "GBPUSD": ("GBPUSD=X", "ny17"), "AUDUSD": ("AUDUSD=X", "ny17"),
}
TFS = {"1h": ("1h", None, "730d"), "4h": ("1h", "4h", "730d"), "1D": ("1d", None, "1500d")}
SL_ATR, TP_ATR = 1.5, 4.0
R_WIN, R_LOSS = TP_ATR / SL_ATR, -1.0
COST_FRAC = 0.0005 * 2 + 0.0001 * 2
LEFT, CD_MAX, CONF_WIN = 5, 20, 5


def ema(a, n):
    k = 2.0 / (n + 1); o = np.full(len(a), np.nan); p = None
    for i, v in enumerate(a):
        if not np.isfinite(v):
            continue
        p = v if p is None else v * k + p * (1 - k); o[i] = p
    return o


def macd_line(c):
    return ema(c, 12) - ema(c, 26)


def is_pivot(arr, i, left, right, kind):
    v = arr[i]
    for k in range(1, left + 1):
        if kind == "high" and not v > arr[i - k]:
            return False
        if kind == "low" and not v < arr[i - k]:
            return False
    for k in range(1, right + 1):
        if kind == "high" and not v > arr[i + k]:
            return False
        if kind == "low" and not v < arr[i + k]:
            return False
    return True


def macd_divs(hi, lo, cl, rb):
    """Return list of dict(ci, dir, run, span, even_even)."""
    n = len(cl); macd = macd_line(cl)
    out = []
    lPH = None; lPL = None; hh = 0; ll = 0
    for i in range(LEFT, n - rb):
        if is_pivot(hi, i, LEFT, rb, "high"):
            if lPH is not None:
                higher = hi[i] > lPH[0]; hh = hh + 1 if higher else 1
                span = i - lPH[2]
                if higher and macd[i] < lPH[1]:
                    ci = i + rb
                    if ci < n:
                        ee = (hh % 2 == 0) and (span % 2 == 0) and (span > hh)
                        out.append(dict(ci=ci, dir="short", run=hh, span=span, even_even=ee))
            lPH = (hi[i], macd[i], i)
        if is_pivot(lo, i, LEFT, rb, "low"):
            if lPL is not None:
                lower = lo[i] < lPL[0]; ll = ll + 1 if lower else 1
                span = i - lPL[2]
                if lower and macd[i] > lPL[1]:
                    ci = i + rb
                    if ci < n:
                        ee = (ll % 2 == 0) and (span % 2 == 0) and (span > ll)
                        out.append(dict(ci=ci, dir="long", run=ll, span=span, even_even=ee))
            lPL = (lo[i], macd[i], i)
    return out


def td_events(hi, lo, cl, vol, lookback, vol_mult):
    """TD setup-9 + extended countdown 13..CD_MAX. Returns dict(bar, dir, kind, k)."""
    n = len(cl)
    vavg = pd.Series(vol).rolling(14).mean().to_numpy() if vol is not None else None
    has_vol = vol is not None and np.nansum(vol) > 0
    bs = ss = 0; bcd = scd = 0; bact = sact = False
    out = []
    for i in range(n):
        volok = True
        if has_vol and vol_mult > 0 and i < len(vavg):
            volok = np.isfinite(vavg[i]) and vol[i] > vavg[i] * vol_mult
        # setup
        bs = bs + 1 if (i - lookback >= 0 and cl[i] < cl[i - lookback]) else 0
        ss = ss + 1 if (i - lookback >= 0 and cl[i] > cl[i - lookback]) else 0
        if bs == 9:
            bact = True; bcd = 0; sact = False; scd = 0
            if volok:
                out.append(dict(bar=i, dir="long", kind="setup9", k=9))
        if ss == 9:
            sact = True; scd = 0; bact = False; bcd = 0
            if volok:
                out.append(dict(bar=i, dir="short", kind="setup9", k=9))
        # countdown (extended past 13)
        if bact and i >= 2 and cl[i] <= lo[i - 2]:
            bcd += 1
            if 13 <= bcd <= CD_MAX and volok:
                out.append(dict(bar=i, dir="long", kind="cd", k=bcd))
        if sact and i >= 2 and cl[i] >= hi[i - 2]:
            scd += 1
            if 13 <= scd <= CD_MAX and volok:
                out.append(dict(bar=i, dir="short", kind="cd", k=scd))
    return out


def sim(hi, lo, cl, i, direction, entry, atrv):
    n = len(cl)
    if direction == "long":
        sl, tp = entry - SL_ATR * atrv, entry + TP_ATR * atrv
    else:
        sl, tp = entry + SL_ATR * atrv, entry - TP_ATR * atrv
    for j in range(i + 1, n):
        if direction == "long":
            if lo[j] <= sl:
                return R_LOSS
            if hi[j] >= tp:
                return R_WIN
        else:
            if hi[j] >= sl:
                return R_LOSS
            if lo[j] <= tp:
                return R_WIN
    mv = (cl[-1] - entry) if direction == "long" else (entry - cl[-1])
    return mv / (SL_ATR * atrv)


def scan(lookback=4, vol_mult=0.0, rb=2):
    now = pd.Timestamp.now(tz="UTC").tz_localize(None); cache = {}
    td_rows = []; conf_rows = []
    for asset, (tk, anchor) in ASSETS.items():
        for tf, (src, rule, per) in TFS.items():
            ck = (tk, src, per)
            if ck not in cache:
                cache[ck] = fetch_ohlcv(tk, src, per)
            base = cache[ck]
            if base is None or base.empty:
                continue
            frame = resample_ohlcv(base, rule, anchor) if rule else base
            frame = drop_incomplete_last_bar(frame, {"1h": 60, "4h": 240, "1D": 1440}[tf], now)
            if len(frame) < 260:
                continue
            hi = frame["High"].to_numpy(); lo = frame["Low"].to_numpy(); cl = frame["Close"].to_numpy()
            vol = frame["Volume"].to_numpy() if "Volume" in frame else None
            atr = atr_wilder(frame, 14)
            tds = td_events(hi, lo, cl, vol, lookback, vol_mult)
            divs = macd_divs(hi, lo, cl, rb) if (vol_mult == 0.0 and lookback == 4) else []
            # index even/even divs by direction for confluence
            ee = {"long": [], "short": []}
            for dv in divs:
                if dv["even_even"]:
                    ee[dv["dir"]].append(dv["ci"])
            for ev in tds:
                i = ev["bar"]
                if not np.isfinite(atr[i]) or atr[i] <= 0:
                    continue
                R = sim(hi, lo, cl, i, ev["dir"], cl[i], atr[i])
                costR = COST_FRAC * cl[i] / (SL_ATR * atr[i])
                conf = any(0 <= i - c <= CONF_WIN or 0 <= c - i <= CONF_WIN for c in ee[ev["dir"]]) if divs else False
                td_rows.append(dict(asset=asset, tf=tf, dir=ev["dir"], kind=ev["kind"], k=ev["k"],
                                    R=round(R - costR, 4), conf=conf))
            # MACD even/even standalone trades (for Test C)
            if divs:
                for dv in divs:
                    ci = dv["ci"]
                    if not np.isfinite(atr[ci]) or atr[ci] <= 0:
                        continue
                    R = sim(hi, lo, cl, ci, dv["dir"], cl[ci], atr[ci])
                    costR = COST_FRAC * cl[ci] / (SL_ATR * atr[ci])
                    conf_rows.append(dict(asset=asset, tf=tf, dir=dv["dir"], even_even=dv["even_even"],
                                          R=round(R - costR, 4)))
    return pd.DataFrame(td_rows), pd.DataFrame(conf_rows)


def stats(rs, label):
    rs = np.asarray(rs, float)
    if len(rs) == 0:
        return dict(group=label, n=0, win=np.nan, pf=np.nan, expR=np.nan, totR=0.0)
    pos = rs[rs > 0].sum(); neg = -rs[rs < 0].sum()
    pf = pos / neg if neg > 0 else np.inf
    return dict(group=label, n=len(rs), win=round(100 * (rs > 0).mean(), 1),
                pf=round(float(pf), 2) if np.isfinite(pf) else np.inf,
                expR=round(float(rs.mean()), 3), totR=round(float(rs.sum()), 1))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    td, conf = scan(lookback=4, vol_mult=0.0, rb=2)
    print(f"TD events: {len(td)} | MACD divs: {len(conf)}", flush=True)

    cd = td[td.kind == "cd"]
    # Test B: by countdown value 13..20 + parity
    b_rows = [stats(td[td.kind == "setup9"].R, "TD setup-9 (baseline)"),
              stats(cd.R, "TD countdown >=13 (all)")]
    for k in range(13, CD_MAX + 1):
        b_rows.append(stats(cd[cd.k == k].R, f"  countdown = {k}"))
    b_rows.append(stats(cd[cd.k % 2 == 0].R, "TD 13+ EVEN counts (14/16/18/20)"))
    b_rows.append(stats(cd[cd.k % 2 == 1].R, "TD 13+ ODD counts (13/15/17/19)"))
    testB = pd.DataFrame(b_rows)

    # Test C: MACD-even/even vs TD-13+ vs confluence
    ee = conf[conf.even_even]
    c_rows = [stats(ee.R, "MACD even/even ONLY"),
              stats(cd.R, "TD 13+ ONLY"),
              stats(cd[cd.conf].R, "CONFLUENCE: TD 13+ WITH MACD even/even (<=5 bars)"),
              stats(cd[~cd.conf].R, "TD 13+ WITHOUT MACD even/even")]
    testC = pd.DataFrame(c_rows)

    # per timeframe (TD 13+)
    tf_rows = [stats(cd[cd.tf == tf].R, f"{tf} TD 13+") for tf in TFS]
    per_tf = pd.DataFrame(tf_rows)

    # grid: lookback x vol_mult on TD 13+ pooled expR
    grid = []
    for lb in (2, 3, 4, 5, 6):
        row = {"lookback": lb}
        for vm in (0.0, 1.0, 1.5, 2.0, 2.5):
            tdg, _ = scan(lookback=lb, vol_mult=vm, rb=2)
            cdg = tdg[tdg.kind == "cd"]
            s = stats(cdg.R, "g")
            row[f"vm{vm}_n"] = s["n"]; row[f"vm{vm}_expR"] = s["expR"]
        grid.append(row)
        print(f"grid lookback={lb} done", flush=True)
    grid_tbl = pd.DataFrame(grid)

    with pd.ExcelWriter(ROOT / "logs" / "td_confluence.xlsx", engine="openpyxl") as xl:
        testB.to_excel(xl, sheet_name="Test B — TD 13+ & parity", index=False)
        testC.to_excel(xl, sheet_name="Test C — confluence", index=False)
        per_tf.to_excel(xl, sheet_name="Per timeframe", index=False)
        grid_tbl.to_excel(xl, sheet_name="Grid lookback x vol", index=False)
        td.to_excel(xl, sheet_name="All TD trades", index=False)

    # chart: countdown value vs expR
    fig, ax = plt.subplots(figsize=(10, 5))
    ks = list(range(13, CD_MAX + 1))
    ex = [cd[cd.k == k].R.mean() if len(cd[cd.k == k]) else np.nan for k in ks]
    ns = [len(cd[cd.k == k]) for k in ks]
    cols = ["#16a34a" if (isinstance(v, float) and v >= 0) else "#dc2626" for v in ex]
    ax.bar([str(k) for k in ks], ex, color=cols)
    for i, (v, nn) in enumerate(zip(ex, ns)):
        if np.isfinite(v):
            ax.text(i, v + (0.02 if v >= 0 else -0.05), f"{v:+.2f}\nn={nn}", ha="center", fontsize=7)
    ax.axhline(0, color="#111", lw=.7); ax.grid(axis="y", alpha=.25)
    ax.set_title("TD countdown value vs expectancy (R) — is 13+ special? is even>odd? (2y, 8 assets, 1h/4h/1D)")
    ax.set_xlabel("countdown value"); ax.set_ylabel("Exp R/trade")
    fig.tight_layout(); fig.savefig(ROOT / "logs" / "td_countdown_expR.png", dpi=110); plt.close(fig)

    print("\n===== TEST B: TD 13+ & parity =====\n", testB.to_string(index=False))
    print("\n===== TEST C: confluence =====\n", testC.to_string(index=False))
    print("\n===== PER TIMEFRAME (TD 13+) =====\n", per_tf.to_string(index=False))
    print("\n===== GRID lookback x vol_mult (TD 13+ expR) =====\n", grid_tbl.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
