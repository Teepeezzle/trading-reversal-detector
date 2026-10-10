"""Research backtest for two user hypotheses on V5 Swing+MACD divergences.

DATA: Twelve Data intraday, 24 months (Oct-2024 .. Oct-2026), cached under
      data/raw/<ASSET>_<45min|1h>.csv. 2h/3h/4h are resampled from 1h.
ASSETS: BTCUSD, ETHUSD, XAUUSD (gold spot), QQQ (NAS100 proxy, RTH-only).
TIMEFRAMES: 45m, 1h, 2h, 3h, 4h.
ENGINE: identical to the live scanner — LEFT/RIGHT 2/2 pivots, MACD 12/26/9,
        chart-native SMA(200), span 6-50, regular divergence only. Entry at the
        CLOSE of the confirming bar (pivot bar + RIGHT), no lookahead.
EXIT (baseline): ATR(14) stop 1.5x / target 4.0x  (1:2.67, the live model).
COSTS: 0.05%/side commission + 1bp/side slippage, converted to R via the stop.

HYPOTHESIS 1 (entry filter):  a divergence "qualifies" when
      run in {2,4}  AND  span even  AND  span > run  AND  span <= 20
   (run = consecutive higher-highs for BEAR / lower-lows for BULL).
   We compare qualifying vs non-qualifying expectancy, with parity breakdowns.

HYPOTHESIS 2 (multi-timeframe exit):  for each entry, instead of the fixed
   target, exit at the FIRST opposite-direction divergence that confirms on
   ANY in-scope timeframe (same asset) strictly after entry — or the stop,
   whichever comes first. Compared head-to-head against the fixed-target exit
   on the SAME entry set.

Outputs: logs/parity_mtf_results.xlsx, logs/parity_mtf_*.png, and a printed
summary. Honest sample sizes and caveats included.
"""
from __future__ import annotations
import sys
from bisect import bisect_right
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from src.v5_divergence import find_pivots, macd_line, atr_wilder, resample_ohlcv  # noqa: E402

DATA = Path(__file__).resolve().parent / "data" / "raw"
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

ASSETS = ["BTCUSD", "ETHUSD", "XAUUSD", "QQQ"]
TF_ORDER = ["45min", "1h", "2h", "3h", "4h"]
TF_MIN = {"45min": 45, "1h": 60, "2h": 120, "3h": 180, "4h": 240}

LEFT, RIGHT = 2, 2
MACD_FAST, MACD_SLOW = 12, 26
SMA_LEN = 200
SPAN_MIN, SPAN_MAX = 6, 50
ATR_LEN = 14
SL_ATR, TP_ATR = 1.5, 4.0
R_WIN, R_LOSS = TP_ATR / SL_ATR, -1.0
COST_FRAC = 0.0005 * 2 + 0.0001 * 2


# ----------------------------------------------------------------- data
def load_tf(asset: str, tf: str) -> pd.DataFrame | None:
    if tf in ("45min", "1h"):
        f = DATA / f"{asset}_{tf}.csv"
        if not f.exists():
            return None
        df = pd.read_csv(f, parse_dates=["datetime"]).set_index("datetime")
    else:
        base = DATA / f"{asset}_1h.csv"
        if not base.exists():
            return None
        h = pd.read_csv(base, parse_dates=["datetime"]).set_index("datetime")
        h.columns = [c.capitalize() for c in h.columns]
        rule = {"2h": "2h", "3h": "3h", "4h": "4h"}[tf]
        df = resample_ohlcv(h, rule, anchor="utc")
        df.columns = [c.lower() for c in df.columns]
        df = df.reset_index().rename(columns={"index": "datetime"}).set_index("datetime")
    df.columns = [c.capitalize() for c in df.columns]
    return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()


# ----------------------------------------------------------------- detection
def detect(df: pd.DataFrame, asset: str, tf: str) -> list[dict]:
    """All regular divergences with run-length, confirmation and ATR."""
    n = len(df)
    if n < SMA_LEN + 5:
        return []
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    macd = macd_line(df["Close"], MACD_FAST, MACD_SLOW)
    sma = df["Close"].rolling(SMA_LEN).mean().to_numpy()
    atr = atr_wilder(df, ATR_LEN)
    idx = df.index
    bar = TF_MIN[tf]
    out = []
    for kind, direction in (("high", "BEAR"), ("low", "BULL")):
        vals = high if kind == "high" else low
        piv = find_pivots(vals, LEFT, RIGHT, kind)
        run = 0
        last = None
        for i in piv:
            if last is None:
                run = 1
                last = i
                continue
            if kind == "high":
                extend = vals[i] > vals[last]
                is_div = extend and macd[i] < macd[last]
            else:
                extend = vals[i] < vals[last]
                is_div = extend and macd[i] > macd[last]
            run = run + 1 if extend else 1
            span = i - last
            if is_div and SPAN_MIN <= span <= SPAN_MAX:
                c = i + RIGHT
                if c < n and np.isfinite(sma[c]) and np.isfinite(atr[c]) and atr[c] > 0:
                    up = close[c] > sma[c]
                    aligned = (direction == "BULL" and up) or (direction == "BEAR" and not up)
                    out.append(dict(
                        asset=asset, tf=tf, direction=direction, run=run, span=span,
                        aligned=aligned, c=c,
                        confirm_time=idx[c],
                        close_time=idx[c] + pd.Timedelta(minutes=bar),
                        entry=float(close[c]), atr=float(atr[c])))
            last = i
    return out


# ----------------------------------------------------------------- exits
def sim_fixed(high, low, close, c, direction, entry, atr):
    n = len(close)
    if direction == "BULL":
        sl, tp = entry - SL_ATR * atr, entry + TP_ATR * atr
    else:
        sl, tp = entry + SL_ATR * atr, entry - TP_ATR * atr
    for j in range(c + 1, n):
        if direction == "BULL":
            if low[j] <= sl:
                return "SL", R_LOSS, j
            if high[j] >= tp:
                return "TP", R_WIN, j
        else:
            if high[j] >= sl:
                return "SL", R_LOSS, j
            if low[j] <= tp:
                return "TP", R_WIN, j
    mv = (close[-1] - entry) if direction == "BULL" else (entry - close[-1])
    return "OPEN", mv / (SL_ATR * atr), n - 1


def sim_mtf(high, low, close, ctimes_ns, c, direction, entry, atr, exit_ns, use_stop):
    """Exit at the first bar whose close_time >= exit_ns (the first opposite
    in-scope divergence). If use_stop, a 1.5xATR stop can exit earlier. R is
    measured in stop-units. No fixed take-profit (the counter-signal is the exit)."""
    n = len(close)
    sl = entry - SL_ATR * atr if direction == "BULL" else entry + SL_ATR * atr
    for j in range(c + 1, n):
        if use_stop:
            if direction == "BULL" and low[j] <= sl:
                return "SL", R_LOSS, j
            if direction == "BEAR" and high[j] >= sl:
                return "SL", R_LOSS, j
        if exit_ns is not None and ctimes_ns[j] >= exit_ns:
            r = (close[j] - entry) if direction == "BULL" else (entry - close[j])
            return "MTF", r / (SL_ATR * atr), j
    mv = (close[-1] - entry) if direction == "BULL" else (entry - close[-1])
    return "OPEN", mv / (SL_ATR * atr), n - 1


# ----------------------------------------------------------------- metrics
HORIZON = 20  # control: dumb fixed-duration hold (~ MTF median), no stop


def sim_horizon(high, low, close, c, direction, entry, atr, H):
    n = len(close)
    j = c + H
    if j >= n:
        j = n - 1
        oc = "OPEN"
    else:
        oc = "HZ"
    r = (close[j] - entry) if direction == "BULL" else (entry - close[j])
    return oc, r / (SL_ATR * atr), j


def metrics(df: pd.DataFrame) -> dict:
    """Closed-trades-only stats (OPEN = never exited before data end, reported
    separately so unrealised marks never flatter the result)."""
    if df.empty:
        return dict(n=0, nopen=0, win=np.nan, pf=np.nan, avgR=np.nan, totR=0.0,
                    maxDD=np.nan, sharpe=np.nan, medbars=np.nan)
    nopen = int((df.outcome == "OPEN").sum())
    cl = df[df.outcome != "OPEN"]
    if cl.empty:
        return dict(n=0, nopen=nopen, win=np.nan, pf=np.nan, avgR=np.nan, totR=0.0,
                    maxDD=np.nan, sharpe=np.nan, medbars=np.nan)
    R = cl.R.to_numpy()
    wins = int((R > 0).sum())
    pos, neg = R[R > 0].sum(), -R[R < 0].sum()
    pf = pos / neg if neg > 0 else np.inf
    d = cl.sort_values("exit_time")
    cum = d.R.cumsum().to_numpy()
    dd = float((cum - np.maximum.accumulate(cum)).min()) if len(cum) else 0.0
    sh = float(R.mean() / R.std(ddof=1)) if len(R) > 1 and R.std(ddof=1) > 0 else np.nan
    return dict(n=len(cl), nopen=nopen,
                win=round(100 * wins / len(cl), 1),
                pf=round(float(pf), 2) if np.isfinite(pf) else np.inf,
                avgR=round(float(R.mean()), 3), totR=round(float(R.sum()), 1),
                maxDD=round(dd, 1), sharpe=round(sh, 3) if np.isfinite(sh) else np.nan,
                medbars=int(cl.bars.median()))


def row(label, df):
    return dict(group=label, **metrics(df))


# ----------------------------------------------------------------- main
def main() -> int:
    def ns(x):
        return np.asarray(pd.DatetimeIndex(x).as_unit("ns").asi8)

    # 1) load every (asset, tf); 2) detect; collect all signals + per-series arrays
    series = {}      # (asset,tf) -> dict(arrays)
    allsig = []
    for a in ASSETS:
        for tf in TF_ORDER:
            df = load_tf(a, tf)
            if df is None or len(df) < SMA_LEN + 5:
                print(f"skip {a} {tf} (insufficient)")
                continue
            ct = ns(df.index + pd.Timedelta(minutes=TF_MIN[tf]))
            series[(a, tf)] = dict(
                high=df["High"].to_numpy(), low=df["Low"].to_numpy(),
                close=df["Close"].to_numpy(), idx=df.index,
                ctimes_ns=ct)
            sigs = detect(df, a, tf)
            allsig.extend(sigs)
    sig = pd.DataFrame(allsig)
    print(f"\nTotal divergences detected: {len(sig)}")
    print(sig.groupby(["asset", "tf"]).size().unstack(fill_value=0).reindex(columns=TF_ORDER))

    # per-asset master list of opposite-signal close-times (for MTF exit)
    master = {}  # asset -> dict(direction -> sorted np array of close_time ns)
    for a in ASSETS:
        sa = sig[sig.asset == a]
        master[a] = {}
        for dirn in ("BULL", "BEAR"):
            master[a][dirn] = np.sort(ns(sa[sa.direction == dirn]["close_time"]))

    # 2) run exits for every signal (fixed + MTF), tag H1
    rows = []
    for s in allsig:
        a, tf = s["asset"], s["tf"]
        S = series[(a, tf)]
        c = s["c"]
        outF, RF, jF = sim_fixed(S["high"], S["low"], S["close"], c,
                                 s["direction"], s["entry"], s["atr"])
        costR = COST_FRAC * s["entry"] / (SL_ATR * s["atr"])
        # opposite-direction signal time on ANY tf, strictly after this entry closes
        opp = "BULL" if s["direction"] == "BEAR" else "BEAR"
        arr = master[a][opp]
        entry_ns = int(pd.Timestamp(s["close_time"]).as_unit("ns").value)
        k = bisect_right(arr, entry_ns)
        exit_ns = int(arr[k]) if k < len(arr) else None
        outM, RM, jM = sim_mtf(S["high"], S["low"], S["close"], S["ctimes_ns"], c,
                               s["direction"], s["entry"], s["atr"], exit_ns, use_stop=True)
        outP, RP, jP = sim_mtf(S["high"], S["low"], S["close"], S["ctimes_ns"], c,
                               s["direction"], s["entry"], s["atr"], exit_ns, use_stop=False)
        outH, RH, jH = sim_horizon(S["high"], S["low"], S["close"], c,
                                   s["direction"], s["entry"], s["atr"], HORIZON)
        q_h1 = (s["run"] in (2, 4)) and (s["span"] % 2 == 0) and (s["span"] > s["run"]) and (s["span"] <= 20)
        rows.append(dict(
            asset=a, tf=tf, direction=s["direction"], run=s["run"], span=s["span"],
            aligned=s["aligned"], h1=q_h1,
            run_even=s["run"] % 2 == 0, span_even=s["span"] % 2 == 0,
            entry_time=s["close_time"],
            # fixed-target exit
            outcome=outF, R=round(RF - costR, 4), bars=jF - c,
            exit_time=S["idx"][jF],
            # mtf exit WITH 1.5xATR stop
            m_outcome=outM, m_R=round(RM - costR, 4), m_bars=jM - c,
            m_exit_time=S["idx"][jM],
            # mtf exit PURE (counter-signal is the only exit, no stop)
            p_outcome=outP, p_R=round(RP - costR, 4), p_bars=jP - c,
            p_exit_time=S["idx"][jP],
            # CONTROL: dumb fixed-horizon hold (no stop), same no-stop basis as pure
            hz_outcome=outH, hz_R=round(RH - costR, 4), hz_bars=jH - c,
            hz_exit_time=S["idx"][jH]))
    t = pd.DataFrame(rows)

    # ---------- H1 tables (fixed-target exit) ----------
    def block(sub):
        return [
            row("ALL divergences", sub),
            row("H1 qualifying", sub[sub.h1]),
            row("non-H1 (rest)", sub[~sub.h1]),
            row("  run in {2,4}", sub[sub.run.isin([2, 4])]),
            row("  span even", sub[sub.span_even]),
            row("  span>run", sub[sub.span > sub.run]),
            row("  run even (any)", sub[sub.run_even]),
            row("  run odd (any)", sub[~sub.run_even]),
        ]
    h1_all = pd.DataFrame(block(t))
    h1_aligned = pd.DataFrame(block(t[t.aligned]))

    # H1 per timeframe and per asset (aligned universe = live scanner)
    per_tf = pd.DataFrame(
        [row(f"{tf} H1", t[(t.tf == tf) & t.h1 & t.aligned]) for tf in TF_ORDER] +
        [row(f"{tf} rest", t[(t.tf == tf) & ~t.h1 & t.aligned]) for tf in TF_ORDER])
    per_asset = pd.DataFrame(
        [row(f"{a} H1", t[(t.asset == a) & t.h1 & t.aligned]) for a in ASSETS] +
        [row(f"{a} rest", t[(t.asset == a) & ~t.h1 & t.aligned]) for a in ASSETS])

    # parity grid run x span parity (all divergences)
    par = []
    for rv in (True, False):
        for sv in (True, False):
            par.append(dict(run=("even" if rv else "odd"), span=("even" if sv else "odd"),
                            **metrics(t[(t.run_even == rv) & (t.span_even == sv)])))
    parity = pd.DataFrame(par)
    # run value x span-parity (where the user's {2,4} lives)
    rungrid = pd.DataFrame([dict(run=rn, **metrics(t[t.run == rn])) for rn in range(2, 11)])

    # ---------- H2 tables (MTF exit vs fixed), same entry sets ----------
    def h2cmp(sub, label):
        def m(pfx):
            cols = {f"{pfx}R": "R", f"{pfx}outcome": "outcome", f"{pfx}bars": "bars", f"{pfx}exit_time": "exit_time"}
            return metrics(sub[list(cols)].rename(columns=cols))
        fx = metrics(sub[["R", "outcome", "bars", "exit_time"]])
        return [dict(group=f"{label} — FIXED 1:2.67", **fx),
                dict(group=f"{label} — MTF pure (counter-signal only)", **m("p_")),
                dict(group=f"{label} — MTF + 1.5ATR stop", **m("m_")),
                dict(group=f"{label} — CONTROL hold {HORIZON} bars (no stop)", **m("hz_"))]
    h2 = pd.DataFrame(
        h2cmp(t[t.aligned], "aligned ALL") +
        h2cmp(t[t.aligned & t.h1], "aligned H1") +
        h2cmp(t, "every divergence") +
        h2cmp(t[t.h1], "H1 (all)"))

    # robustness: MTF-pure (counter-signal) on aligned universe, per asset & per TF
    def pm(sub):
        cols = {"p_R": "R", "p_outcome": "outcome", "p_bars": "bars", "p_exit_time": "exit_time"}
        return metrics(sub[list(cols)].rename(columns=cols))
    alx = t[t.aligned]
    h2_break = pd.DataFrame(
        [dict(group=f"ASSET {a}", **pm(alx[alx.asset == a])) for a in ASSETS] +
        [dict(group=f"TF {tf}", **pm(alx[alx.tf == tf])) for tf in TF_ORDER])

    # ---------- write workbook ----------
    xlsx = LOGS / "parity_mtf_results.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xl:
        h1_all.to_excel(xl, sheet_name="H1 all-divs", index=False)
        h1_aligned.to_excel(xl, sheet_name="H1 aligned", index=False)
        per_tf.to_excel(xl, sheet_name="H1 per timeframe", index=False)
        per_asset.to_excel(xl, sheet_name="H1 per asset", index=False)
        parity.to_excel(xl, sheet_name="Parity grid", index=False)
        rungrid.to_excel(xl, sheet_name="Run value grid", index=False)
        h2.to_excel(xl, sheet_name="H2 MTF vs fixed", index=False)
        h2_break.to_excel(xl, sheet_name="H2 MTFpure breakdown", index=False)
        t.drop(columns=["run_even", "span_even"]).to_excel(xl, sheet_name="All trades", index=False)

    # ---------- equity charts ----------
    def eq(ax, s, lab):
        s = s.sort_values("exit_time")
        if len(s):
            ax.plot(pd.to_datetime(s.exit_time), s.R.cumsum(),
                    label=f"{lab} (n={len(s)}, {s.R.sum():+.1f}R)", lw=1.5)
    fig, ax = plt.subplots(1, 2, figsize=(15, 5))
    al = t[t.aligned]
    alc = al[al.outcome != "OPEN"]
    eq(ax[0], alc[["R", "exit_time"]], "all aligned (fixed)")
    eq(ax[0], alc[alc.h1][["R", "exit_time"]], "H1 aligned (fixed)")
    eq(ax[0], alc[~alc.h1][["R", "exit_time"]], "non-H1 aligned (fixed)")
    ax[0].set_title("H1 entry filter — fixed 1:2.67 exit (closed only)"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3); ax[0].axhline(0, color="#888", lw=.7)
    alp = al[al.p_outcome != "OPEN"][["p_R", "p_exit_time"]].rename(columns={"p_R": "R", "p_exit_time": "exit_time"})
    eq(ax[1], alc[["R", "exit_time"]], "aligned — FIXED exit")
    eq(ax[1], alp, "aligned — MTF pure (counter-signal)")
    ax[1].set_title("H2 exit rule — fixed vs MTF counter-signal (aligned, closed)"); ax[1].legend(fontsize=8); ax[1].grid(alpha=.3); ax[1].axhline(0, color="#888", lw=.7)
    fig.tight_layout(); fig.savefig(LOGS / "parity_mtf_equity.png", dpi=110); plt.close(fig)

    # ---------- print summary ----------
    pd.set_option("display.width", 170); pd.set_option("display.max_columns", 20)
    print("\n================ H1  (ALIGNED universe = live scanner) ================")
    print(h1_aligned.to_string(index=False))
    print("\n---------------- H1  (ALL divergences, aligned+counter) ----------------")
    print(h1_all.to_string(index=False))
    print("\n---------------- H1 per timeframe (aligned) ----------------")
    print(per_tf.to_string(index=False))
    print("\n---------------- H1 per asset (aligned) ----------------")
    print(per_asset.to_string(index=False))
    print("\n---------------- Parity grid (all divergences) ----------------")
    print(parity.to_string(index=False))
    print("\n---------------- Run-value grid (all divergences) ----------------")
    print(rungrid.to_string(index=False))
    print("\n================ H2  MTF-exit vs FIXED-target (same entries) ================")
    print(h2.to_string(index=False))
    print("\n---------------- H2 MTF-pure robustness (aligned, per asset / per TF) ----------------")
    print(h2_break.to_string(index=False))
    print(f"\nWorkbook -> {xlsx}")
    print(f"Window: {t.entry_time.min()} .. {t.entry_time.max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
