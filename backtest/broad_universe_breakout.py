"""Out-of-sample UNIVERSE test for the daily-breakout edge.

The validated 18-market basket was selected BECAUSE each asset was individually
profitable -> that is universe-level selection bias. This runs the EXACT same
rules on a broad, UNSCREENED set (~55 liquid markets across every asset class,
picked only for liquidity/availability, never for profitability) and reports the
pooled expectancy -- crucially split into the ORIGINAL-18 vs the NEVER-SCREENED
markets. If the never-screened markets are also net-positive, the edge is real
and general; if only the original-18 carry it, the basket was doing the work.

Rules (identical to portfolio_backtest.py): Daily, ADX(14)<20, close>Donchian-
high(20)[1], close>SMA200; SL 1.5xATR / TP 3xATR; MAX_HOLD 60; 0.05% commission
+ 2-tick slippage. Standalone per-asset expectancy (no cross-asset slot cap, so
no ordering bias) + a compounded portfolio view for CAGR/DD.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import backtest.portfolio_backtest as pb   # noqa: E402  reuse fetch/indicators/constants

SL_MULT, TP_MULT = pb.SL_MULT, pb.TP_MULT          # 1.5 / 3.0
ADX_RANGING, DONCH, MAX_HOLD = pb.ADX_RANGING, pb.DONCH, pb.MAX_HOLD
COMMISSION, SLIP_TICKS = pb.COMMISSION, pb.SLIP_TICKS
START_EQUITY, RISK_PCT = pb.START_EQUITY, pb.RISK_PCT
CLIP = 3.0   # winsorize per-trade R: a real daily gap rarely exceeds this; blocks
             # yfinance data artifacts (e.g. sub-penny DOGE) from dominating pools

ORIG18 = set(pb.BASKET.keys())

# Broad, unscreened universe (liquidity/availability only). tick ~ per class.
def tk_tick(t):
    if t.endswith("-USD"):
        return 0.01
    if t.endswith("=X"):
        return 0.001 if "JPY" in t else 0.00001
    return 0.01
BROAD_LIST = [
    # crypto
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "LTC-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "DOT-USD", "AVAX-USD", "LINK-USD", "BCH-USD", "ATOM-USD",
    # FX
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X",
    "NZDUSD=X", "EURJPY=X", "EURGBP=X", "GBPJPY=X",
    # metals
    "GC=F", "SI=F", "HG=F", "PL=F", "PA=F",
    # energy
    "CL=F", "BZ=F", "NG=F", "RB=F", "HO=F",
    # equity indices
    "ES=F", "NQ=F", "YM=F", "RTY=F",
    # rates
    "ZB=F", "ZN=F", "ZF=F", "ZT=F",
    # ags
    "ZC=F", "ZW=F", "ZS=F", "ZM=F", "ZL=F", "KC=F", "SB=F", "CC=F", "CT=F",
    "LE=F", "HE=F", "ZO=F",
]
BROAD = {t: (t, tk_tick(t)) for t in BROAD_LIST}


def standalone_trades(tk, df, tick):
    """One position at a time, exact rules, returns list of net-R per trade."""
    c = df["Close"].to_numpy(); hi = df["High"].to_numpy(); lo = df["Low"].to_numpy()
    adx = df["adx"].to_numpy(); sma = df["sma200"].to_numpy()
    dh = df["dhigh"].to_numpy(); atr = df["atr"].to_numpy()
    n = len(df); out = []
    i = 0
    while i < n:
        sig = (np.isfinite(adx[i]) and np.isfinite(sma[i]) and np.isfinite(dh[i])
               and adx[i] < ADX_RANGING and c[i] > dh[i] and c[i] > sma[i]
               and np.isfinite(atr[i]) and atr[i] > 0)
        if not sig:
            i += 1; continue
        entry = c[i] + SLIP_TICKS * tick
        risk = SL_MULT * atr[i]
        sl = entry - risk; tp = entry + TP_MULT * atr[i]
        exit_r = None
        for j in range(i + 1, min(n, i + 1 + MAX_HOLD)):
            if lo[j] <= sl:
                px = sl - SLIP_TICKS * tick; exit_r = (px - entry) / risk; i = j; break
            if hi[j] >= tp:
                exit_r = (tp - entry) / risk; i = j; break
            if j == i + MAX_HOLD:
                exit_r = (c[j] - entry) / risk; i = j; break
        if exit_r is None:                       # ran out of data while open
            exit_r = (c[-1] - entry) / risk; i = n
        cost_r = COMMISSION * 2 * entry / risk   # round-trip commission in R
        net = exit_r - cost_r
        out.append(round(max(-CLIP, min(CLIP, net)), 4))   # winsorized
        i += 1
    return out


def stats(rs):
    rs = np.asarray(rs, float)
    if len(rs) == 0:
        return dict(n=0, win=np.nan, pf=np.nan, expR=np.nan, totR=0.0)
    pos = rs[rs > 0].sum(); neg = -rs[rs < 0].sum()
    pf = pos / neg if neg > 0 else np.inf
    return dict(n=len(rs), win=round(100 * (rs > 0).mean(), 1),
                pf=round(float(pf), 2) if np.isfinite(pf) else np.inf,
                expR=round(float(rs.mean()), 3), totR=round(float(rs.sum()), 1))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    frames = {}
    for tk, (name, tick) in BROAD.items():
        raw = pb.fetch(tk)
        if raw is None:
            print(f"  ! {tk}: no data"); continue
        frames[tk] = pb.indicators(raw)
        print(f"  loaded {tk:<10} {len(raw)} bars", flush=True)

    per = []
    all_r, orig_r, new_r = [], [], []
    for tk, df in frames.items():
        rs = standalone_trades(tk, df, BROAD[tk][1])
        s = stats(rs)
        s["ticker"] = tk; s["in_orig18"] = tk in ORIG18
        per.append(s)
        all_r += rs
        (orig_r if tk in ORIG18 else new_r).extend(rs)

    per_df = pd.DataFrame(per).sort_values("expR", ascending=False)[
        ["ticker", "in_orig18", "n", "win", "pf", "expR", "totR"]]
    n_assets = len(per_df)
    n_pos = int((per_df.expR > 0).sum())
    n_new = per_df[~per_df.in_orig18]
    n_new_pos = int((n_new.expR > 0).sum())

    pooled = pd.DataFrame([
        dict(group="ALL broad universe", **stats(all_r)),
        dict(group="ORIGINAL 18 (screened)", **stats(orig_r)),
        dict(group="NEVER-SCREENED (new markets)", **stats(new_r)),
    ])

    with pd.ExcelWriter(ROOT / "logs" / "broad_universe_breakout.xlsx", engine="openpyxl") as xl:
        pooled.to_excel(xl, sheet_name="Pooled (the bias test)", index=False)
        per_df.to_excel(xl, sheet_name="Per asset", index=False)
        pd.DataFrame({"read me": [
            "Same daily-breakout rules as the validated 18-basket, run on a broad UNSCREENED",
            "universe. The decisive row is 'NEVER-SCREENED (new markets)': if its expR/PF are",
            "positive, the edge is general and the 18-basket selection was NOT doing the work.",
            "Standalone per-asset (one position at a time, no cross-asset slot cap). yfinance",
            "daily, full history per asset. Costs 0.05%/side + 2-tick slippage. Not advice.",
        ]}).to_excel(xl, sheet_name="README", index=False)

    print("\n===== POOLED (the selection-bias test) =====")
    print(pooled.to_string(index=False))
    print(f"\nAssets: {n_assets} loaded | net-positive expR: {n_pos}/{n_assets} "
          f"({100*n_pos/n_assets:.0f}%)")
    print(f"Never-screened markets: {len(n_new)} | net-positive: {n_new_pos}/{len(n_new)} "
          f"({100*n_new_pos/max(len(n_new),1):.0f}%)")
    print("\n===== PER ASSET (sorted by expR) =====")
    print(per_df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
