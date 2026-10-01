"""PHASE 3 — single-factor tester (the unit the sweep will call).

Tests ONE indicator rule on ONE instrument/timeframe/horizon, no-lookahead and net-of-cost,
and reports stats on the TRAIN and VALIDATION splits plus two benchmarks (buy-&-hold and a
random-entry control with the same stop/target). The HOLDOUT (last 20%) is NEVER touched here.

A rule "passes" (candidate) only if, on the VALIDATION split: n>=100, net expectancy>0,
profit factor>1, AND it beats the random-entry control. Judged on validation, not train.

Usage:
  python research/jobs/single_factor.py --lake <dir> --aclass crypto --symbol BTC/USD \
      --tf 1h --rule rsi_rev --horizon swing --sl 1.5 --tp 3.0 --p "n=14,os=30" [--record]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import indicators as ind          # noqa: E402
import backtest as bt             # noqa: E402
import costs as cost_model        # noqa: E402

MIN_TRADES = 100


def parse_params(s: str) -> dict:
    out = {}
    for kv in (s or "").split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            try:
                out[k.strip()] = int(v) if v.strip().lstrip("-").isdigit() else float(v)
            except ValueError:
                out[k.strip()] = v.strip()
    return out


# ---- rule builders: return (entries: bool Series, direction) ----
def rsi_rev(df, p):                       # mean-reversion long: RSI crosses back up through OS
    n = int(p.get("n", 14)); os = float(p.get("os", 30))
    r = ind.rsi(df["close"], n)
    return (r.shift(1) < os) & (r >= os), "long"


def donch_brk(df, p):                     # breakout long: close above prior N-bar high
    n = int(p.get("n", 20))
    up, _, _ = ind.donchian(df, n)
    return df["close"] > up.shift(1), "long"


def ema_cross(df, p):                     # trend long: fast EMA crosses above slow
    f = int(p.get("f", 20)); s = int(p.get("s", 50))
    x = ind.ema_cross(df["close"], f, s)
    return (x.shift(1) <= 0) & (x > 0), "long"


def zscore_rev(df, p):                    # mean-reversion long: z crosses back up from below -zt
    n = int(p.get("n", 20)); zt = float(p.get("z", 2.0))
    z = ind.zscore(df["close"], n)
    return (z.shift(1) < -zt) & (z >= -zt), "long"


RULES = {"rsi_rev": rsi_rev, "donch_brk": donch_brk, "ema_cross": ema_cross, "zscore_rev": zscore_rev}

import yaml  # noqa: E402
CFG = yaml.safe_load((ROOT / "config.yaml").read_text("utf-8"))


def get_symbols(aclass: str) -> list[str]:
    """All symbols for an asset class, from the TD universe + the yfinance list (e.g. metals =
    XAU/USD from TD + XAG/USD from yfinance). Pooling these is how a hypothesis reaches >=100 trades."""
    syms = list(CFG.get("universe", {}).get(aclass, {}).get("symbols", []))
    syms += [y["symbol"] for y in CFG.get("yfinance", []) if y.get("asset_class") == aclass]
    return syms


def load(lake: Path, aclass: str, symbol: str, tf: str) -> pd.DataFrame:
    path = lake / aclass / f"{symbol.replace('/', '')}_{tf}.csv.gz"
    df = pd.read_csv(path, compression="gzip", parse_dates=["time"]).sort_values("time").reset_index(drop=True)
    return df


def run_one(df, rule_fn, params, horizon, sl, tp, c):
    """Simulate one instrument, split on its own timeline, return tagged trades (+ direction)."""
    entries, direction = rule_fn(df, params)
    atr = ind.atr(df, 14)
    trades = bt.simulate(df, entries.fillna(False), direction, atr, sl, tp, horizon, c["rt"], c["swap_daily"])
    if not trades.empty:
        trades["split"] = bt.tag_split(trades, bt.split_masks(df))
    return trades, direction, atr


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default=str(ROOT / "data"))
    ap.add_argument("--aclass", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--rule", required=True, choices=list(RULES))
    ap.add_argument("--horizon", default="swing", choices=["intraday", "swing"])
    ap.add_argument("--sl", type=float, default=1.5)
    ap.add_argument("--tp", type=float, default=3.0)
    ap.add_argument("--p", default="")
    ap.add_argument("--cost_mult", type=float, default=1.0)
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args()

    params = parse_params(a.p)
    c = cost_model.get(a.aclass, a.cost_mult)
    rule_fn = RULES[a.rule]
    symbols = get_symbols(a.aclass) if a.symbol.upper() == "ALL" else [a.symbol]

    all_trades = []; rnd_exps = []; rnd_w = []; bh_list = []
    for sym in symbols:
        try:
            df = load(Path(a.lake), a.aclass, sym, a.tf)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {sym}: {exc}"); continue
        trades_i, direction, atr = run_one(df, rule_fn, params, a.horizon, a.sl, a.tp, c)
        if not trades_i.empty:
            trades_i["symbol"] = sym; all_trades.append(trades_i)
        vn = int((trades_i.split == "val").sum()) if not trades_i.empty else 0
        r = bt.random_control(df, vn or 100, direction, atr, a.sl, a.tp, a.horizon, c["rt"], c["swap_daily"])
        if np.isfinite(r["expR"]):
            rnd_exps.append(r["expR"]); rnd_w.append(max(vn, 1))
        bh_list.append(bt.buy_hold_pct(df))

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame({"split": []})
    tr = trades[trades.split == "train"] if len(trades) else trades
    va = trades[trades.split == "val"] if len(trades) else trades
    st, sv = bt.stats(tr), bt.stats(va)
    rnd = {"expR": round(float(np.average(rnd_exps, weights=rnd_w)), 4) if rnd_exps else np.nan, "win": np.nan}
    bh = round(float(np.mean(bh_list)), 1) if bh_list else np.nan
    scope = f"{a.symbol}" if len(symbols) == 1 else f"{a.aclass}-ALL({len(symbols)})"

    passed = (sv["n"] >= MIN_TRADES and np.isfinite(sv["expR"]) and sv["expR"] > 0
              and sv["pf"] > 1 and (not np.isfinite(rnd["expR"]) or sv["expR"] > rnd["expR"]))
    tag = "PASS" if passed else ("THIN" if sv["n"] < MIN_TRADES else "FAIL")

    print(f"\n{scope} {a.tf} {a.horizon} · {a.rule}({a.p}) SL{a.sl}/TP{a.tp} costx{a.cost_mult}")
    print(f"  TRAIN n={st['n']:<4} win={st['win']}% expR={st['expR']} pf={st['pf']} dd={st['maxdd_R']}R")
    print(f"  VAL   n={sv['n']:<4} win={sv['win']}% expR={sv['expR']} pf={sv['pf']} "
          f"sharpe={sv['sharpe']} dd={sv['maxdd_R']}R")
    print(f"  bench random expR={rnd['expR']} (win {rnd['win']}%) · buy-hold {bh}%")
    print(f"  => {tag}  (judged on validation; holdout untouched)")

    if a.record:
        row = dict(id=f"{a.rule}-{a.symbol.replace('/','')}-{a.tf}-{a.horizon}",
                   date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), phase=3,
                   hypothesis=f"{a.rule}({a.p})", asset_class=a.aclass, symbols=a.symbol,
                   timeframe=a.tf, horizon=a.horizon, params=a.p,
                   entry_rule=a.rule, exit_rule=f"SL{a.sl}/TP{a.tp}/{a.horizon}",
                   cost_model=f"x{a.cost_mult}", sample_train=st["n"], sample_val=sv["n"],
                   winrate_train=st["win"], winrate_val=sv["win"],
                   expectancy_R_train=st["expR"], expectancy_R_val=sv["expR"],
                   profit_factor_val=sv["pf"], max_dd_R=sv["maxdd_R"], sharpe_val=sv["sharpe"],
                   benchmark_bh_R=bh, benchmark_random_R=rnd["expR"], survived=tag)
        reg = ROOT / "HYPOTHESIS_REGISTRY.csv"
        hdr = pd.read_csv(reg, nrows=0).columns.tolist()
        pd.DataFrame([{k: row.get(k, "") for k in hdr}]).to_csv(reg, mode="a", header=False, index=False)
        print(f"  recorded -> HYPOTHESIS_REGISTRY.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
