"""Portfolio backtest of the VALIDATED daily long-breakout edge.

Runs the OOS-validated config as ONE account across a basket of liquid assets,
so you see how it behaves the way you'd actually trade it — combined equity
curve, real trade frequency, drawdown, and each asset's contribution.

Validated config (do NOT re-optimize):
  * timeframe : Daily
  * regime    : ADX(14) < 20  (low-ADX consolidation)
  * entry     : LONG when close > Donchian-high(20)[1]  (breakout up)
  * macro     : only long when close > SMA200 (the OOS improvement)
  * risk      : SL = 1.5*ATR, TP = 3.0*ATR (1:2), one trade per asset at a time
  * sizing    : 1% of CURRENT equity risked per trade (compounding)
  * portfolio : max 4 concurrent open positions across the basket
  * costs     : 0.05% commission + 2-tick slippage per trade
Chronological event simulation so equity, position cap and compounding interact
realistically across assets.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "backtest" / "results"

# Basket: crypto, metals, energy, an index, plus FX major (liquid, daily)
BASKET = {
    "BTC-USD": ("Bitcoin", 0.01),
    "ETH-USD": ("Ethereum", 0.01),
    "GC=F": ("Gold", 0.10),
    "SI=F": ("Silver", 0.005),
    "CL=F": ("WTI Oil", 0.01),
    "NQ=F": ("Nasdaq100", 0.25),
}

START_EQUITY = 10_000.0
RISK_PCT = 1.0
SL_MULT, TP_MULT = 1.5, 3.0
ADX_RANGING = 20.0
DONCH = 20
MAX_CONCURRENT = 4
COMMISSION = 0.0005
SLIP_TICKS = 2
MAX_HOLD = 60


def fetch(ticker: str) -> Optional[pd.DataFrame]:
    for period in ("max", "15y", "10y"):
        for _ in range(3):
            try:
                raw = yf.download(ticker, period=period, interval="1d",
                                  progress=False, auto_adjust=False, threads=False)
            except Exception:
                raw = None
            if raw is not None and not raw.empty:
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna(
                    subset=["Open", "High", "Low", "Close"])
                if len(df) >= 400:
                    return df
            time.sleep(1.5)
    return None


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    up = df["High"].diff(); dn = -df["Low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, 14)
    pdi = 100 * wilder(pd.Series(pdm, index=df.index), 14) / atr
    mdi = 100 * wilder(pd.Series(mdm, index=df.index), 14) / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    out = df.copy()
    out["atr"] = atr
    out["adx"] = wilder(dx.fillna(0), 14)
    out["sma200"] = df["Close"].rolling(200).mean()
    out["dhigh"] = df["High"].rolling(DONCH).max().shift(1)
    return out


@dataclass
class Position:
    ticker: str
    name: str
    entry_date: pd.Timestamp
    entry: float
    sl: float
    tp: float
    risk_amt: float       # $ risked
    risk_dist: float      # price distance to SL
    tick: float
    bars_held: int = 0


@dataclass
class Trade:
    ticker: str
    name: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    pnl: float
    r: float
    outcome: str


def precompute_signals(frames: Dict[str, pd.DataFrame]):
    """Return {ticker: set of dates where a long-breakout signal fires}."""
    sigs = {}
    for tk, df in frames.items():
        c = df["Close"].to_numpy(); adxv = df["adx"].to_numpy()
        sma = df["sma200"].to_numpy(); dh = df["dhigh"].to_numpy()
        ok = (~np.isnan(adxv)) & (~np.isnan(sma)) & (~np.isnan(dh)) & \
             (adxv < ADX_RANGING) & (c > dh) & (c > sma)
        sigs[tk] = set(df.index[ok])
    return sigs


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames: Dict[str, pd.DataFrame] = {}
    for tk, (name, tick) in BASKET.items():
        raw = fetch(tk)
        if raw is None:
            print(f"  ! {name}: no data, skipped")
            continue
        frames[tk] = indicators(raw)
        print(f"  loaded {name}: {len(raw)} bars {raw.index[0].date()}->{raw.index[-1].date()}")
    if not frames:
        print("No data.")
        return

    signal_dates = precompute_signals(frames)
    all_dates = sorted(set().union(*[set(df.index) for df in frames.values()]))

    equity = START_EQUITY
    open_pos: Dict[str, Position] = {}
    trades: List[Trade] = []
    curve = []

    for d in all_dates:
        # 1) manage open positions (check exits using the day's H/L)
        for tk in list(open_pos.keys()):
            pos = open_pos[tk]
            df = frames[tk]
            if d not in df.index:
                continue
            row = df.loc[d]
            hi, lo, cl = float(row["High"]), float(row["Low"]), float(row["Close"])
            pos.bars_held += 1
            exit_price = outcome = None
            if lo <= pos.sl:
                exit_price, outcome = pos.sl - SLIP_TICKS * pos.tick, "SL"
            elif hi >= pos.tp:
                exit_price, outcome = pos.tp, "TP"
            elif pos.bars_held >= MAX_HOLD:
                exit_price, outcome = cl, "TIME"
            if exit_price is not None:
                r = (exit_price - pos.entry) / pos.risk_dist
                pnl = r * pos.risk_amt - COMMISSION * 2 * pos.entry * (pos.risk_amt / pos.risk_dist) / pos.entry
                pnl = r * pos.risk_amt - COMMISSION * 2 * (pos.risk_amt / pos.risk_dist) * pos.entry
                equity += pnl
                trades.append(Trade(tk, pos.name, pos.entry_date, d, pnl, r, outcome))
                del open_pos[tk]

        # 2) new entries (after exits free up slots)
        for tk, df in frames.items():
            if tk in open_pos or d not in signal_dates[tk]:
                continue
            if len(open_pos) >= MAX_CONCURRENT:
                break
            row = df.loc[d]
            name, tick = BASKET[tk]
            atr = float(row["atr"]); entry = float(row["Close"]) + SLIP_TICKS * tick
            if not np.isfinite(atr) or atr <= 0:
                continue
            risk_dist = SL_MULT * atr
            risk_amt = equity * RISK_PCT / 100.0
            open_pos[tk] = Position(tk, name, d, entry, entry - risk_dist,
                                    entry + TP_MULT * atr, risk_amt, risk_dist, tick)

        curve.append((d, equity + sum(
            ((float(frames[t].loc[d]["Close"]) - p.entry) / p.risk_dist) * p.risk_amt
            for t, p in open_pos.items() if d in frames[t].index)))

    # ---- results ----
    cdf = pd.DataFrame(curve, columns=["date", "equity"]).set_index("date")
    cdf.to_csv(OUT / "portfolio_equity.csv")
    pnl = np.array([t.pnl for t in trades])
    rs = np.array([t.r for t in trades])
    years = (all_dates[-1] - all_dates[0]).days / 365.25
    wins = pnl[pnl > 0]; losses = pnl[pnl <= 0]
    eq = cdf["equity"].to_numpy()
    peak = np.maximum.accumulate(eq)
    maxdd = float(((eq - peak) / peak).min() * 100)
    rets = cdf["equity"].pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else float("nan")
    cagr = (eq[-1] / START_EQUITY) ** (1 / years) - 1 if years > 0 else float("nan")

    print("\n================ PORTFOLIO RESULT (validated daily breakout) ================")
    print(f"  Period           : {all_dates[0].date()} -> {all_dates[-1].date()}  ({years:.1f} yrs)")
    print(f"  Assets in basket : {len(frames)}")
    print(f"  Start / End eq   : ${START_EQUITY:,.0f}  ->  ${eq[-1]:,.0f}")
    print(f"  Total return     : {(eq[-1]/START_EQUITY-1)*100:,.1f}%")
    print(f"  CAGR             : {cagr*100:,.1f}%")
    print(f"  Max drawdown     : {maxdd:,.1f}%")
    print(f"  Sharpe (daily)   : {sharpe:.2f}")
    print(f"  Trades           : {len(trades)}  ({len(trades)/years:.1f}/yr)")
    print(f"  Win rate         : {100*len(wins)/len(trades):.0f}%")
    print(f"  Avg R / trade    : {rs.mean():+.3f}")
    print(f"  Profit factor    : {wins.sum()/-losses.sum():.2f}")
    print(f"  Avg win / loss $ : +${wins.mean():,.0f} / ${losses.mean():,.0f}")

    print("\n  Per-asset contribution:")
    by = {}
    for t in trades:
        by.setdefault(t.name, []).append(t)
    print(f"  {'asset':<12}{'trades':>7}{'win%':>7}{'net$':>10}{'avgR':>8}")
    for name, ts in sorted(by.items(), key=lambda kv: -sum(t.pnl for t in kv[1])):
        p = np.array([t.pnl for t in ts]); r = np.array([t.r for t in ts])
        print(f"  {name:<12}{len(ts):>7}{100*np.mean(p>0):>6.0f}%{p.sum():>10,.0f}{r.mean():>8.2f}")

    # yearly equity snapshots
    print("\n  Equity by year-end:")
    yr = cdf["equity"].resample("1YE").last()
    for ts, v in yr.items():
        print(f"    {ts.year}: ${v:,.0f}")
    print(f"\nSaved equity curve -> {OUT / 'portfolio_equity.csv'}")


if __name__ == "__main__":
    main()
