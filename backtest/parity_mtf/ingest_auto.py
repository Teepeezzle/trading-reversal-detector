"""Auto-classify saved Twelve Data tool-result files and merge into clean series.

Each file is JSON {"result": "<semicolon CSV, newest-first>"}. We classify by CONTENT
(never by call order, which is fragile) so a mis-map cannot silently corrupt a series:

  interval : median bar spacing  -> '45min' (43-47 min) or '1h' (58-62 min)
  asset    : median close magnitude + weekend activity
             close > 30000            -> BTCUSD
             close < 1500             -> QQQ
             else (ETH ~ gold range)  -> ETHUSD if it has many Saturday bars
                                          (crypto trades 24/7), else XAUUSD
                                          (metals are closed Saturdays)

Merges into data/raw/<ASSET>_<INTERVAL>.csv (dedup on timestamp, sorted ascending),
validates OHLC sanity, and prints classification + coverage + gap report.

Usage:  python ingest_auto.py <file1> [<file2> ...]
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)


def parse(path: str) -> pd.DataFrame:
    doc = json.load(open(path))
    s = doc["result"]
    if s.startswith("Error") or "exceeds maximum" in s[:40] or "upgrading" in s[:80]:
        raise ValueError(f"not data: {s[:100]}")
    lines = [ln for ln in s.splitlines() if ln.strip()]
    hdr = lines[0].split(";")
    df = pd.DataFrame([ln.split(";") for ln in lines[1:]], columns=hdr)
    df["datetime"] = pd.to_datetime(df["datetime"])
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce") if "volume" in df.columns else 0.0
    return df[["datetime", "open", "high", "low", "close", "volume"]].dropna(
        subset=["open", "high", "low", "close"]).sort_values("datetime")


def classify(df: pd.DataFrame) -> tuple[str, str]:
    step_min = df["datetime"].diff().dropna().dt.total_seconds().median() / 60.0
    if 43 <= step_min <= 47:
        interval = "45min"
    elif 58 <= step_min <= 62:
        interval = "1h"
    else:
        raise ValueError(f"unrecognised bar spacing: {step_min:.1f} min")
    med = df["close"].median()
    if med > 30000:
        asset = "BTCUSD"
    elif med < 1500:
        asset = "QQQ"
    else:
        sat = (df["datetime"].dt.weekday == 5).mean()   # fraction of Saturday bars
        asset = "ETHUSD" if sat > 0.05 else "XAUUSD"
    return asset, interval


def merge(asset: str, interval: str, new: pd.DataFrame) -> pd.DataFrame:
    out = RAW / f"{asset}_{interval}.csv"
    if out.exists():
        old = pd.read_csv(out, parse_dates=["datetime"])
        new = pd.concat([old, new], ignore_index=True)
    new = (new.drop_duplicates(subset=["datetime"]).sort_values("datetime")
              .reset_index(drop=True))
    new.to_csv(out, index=False)
    return new


def main() -> int:
    for p in sys.argv[1:]:
        try:
            df = parse(p)
            asset, interval = classify(df)
        except ValueError as e:
            print(f"SKIP {Path(p).name}: {e}")
            continue
        merged = merge(asset, interval, df)
        print(f"{Path(p).name} -> {asset} {interval}  (+{len(df)} rows, px~{df.close.median():.4g})")
    print("\n=== COVERAGE ===")
    for f in sorted(RAW.glob("*.csv")):
        d = pd.read_csv(f, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
        tf = f.stem.split("_")[1]
        step = pd.Timedelta(minutes=45 if tf == "45min" else 60)
        gaps = d.datetime.diff()
        big = gaps[gaps > step * 20]
        bad = d[(d.high < d.low) | (d.high < d.close) | (d.low > d.close)]
        print(f"{f.name:18} rows={len(d):6} {d.datetime.min()} .. {d.datetime.max()} "
              f"biggaps={len(big)} bad_ohlc={len(bad)}")
        for i, g in big.items():
            print(f"     missing ~{g} before {d.datetime[i]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
