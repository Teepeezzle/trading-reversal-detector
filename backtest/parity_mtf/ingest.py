"""Ingest a saved Twelve Data MCP tool-result file into a clean per-series CSV.

The MCP result JSON is {"result": "<semicolon-CSV>"} where the CSV is newest-first
and may or may not carry a volume column. We parse it, tag it with (symbol, interval),
append to backtest/parity_mtf/data/raw/<SYM>_<TF>.csv, de-duplicate on timestamp,
sort ascending, validate OHLC sanity, and print a summary for manual identity checks.

Usage:  python ingest.py <tool_result_path> <symbol> <interval>
        symbol e.g. BTC/USD  ->  stored as BTCUSD
        interval e.g. 45min / 1h
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)


def sym_key(symbol: str) -> str:
    return symbol.replace("/", "").replace(":", "").upper()


def parse_result(path: str) -> pd.DataFrame:
    doc = json.load(open(path))
    s = doc["result"]
    if s.startswith("Error") or "exceeds maximum" in s[:40]:
        raise SystemExit(f"tool-result file holds an error, not data: {s[:120]}")
    lines = [ln for ln in s.splitlines() if ln.strip()]
    header = lines[0].split(";")
    rows = [ln.split(";") for ln in lines[1:]]
    df = pd.DataFrame(rows, columns=header)
    df["datetime"] = pd.to_datetime(df["datetime"])
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume"] = 0.0
    return df[["datetime", "open", "high", "low", "close", "volume"]]


def main() -> int:
    tr_path, symbol, interval = sys.argv[1], sys.argv[2], sys.argv[3]
    new = parse_result(tr_path)
    out = RAW / f"{sym_key(symbol)}_{interval}.csv"
    if out.exists():
        old = pd.read_csv(out, parse_dates=["datetime"])
        allrows = pd.concat([old, new], ignore_index=True)
    else:
        allrows = new
    allrows = (allrows.dropna(subset=["open", "high", "low", "close"])
                      .drop_duplicates(subset=["datetime"])
                      .sort_values("datetime")
                      .reset_index(drop=True))
    # OHLC sanity
    bad = allrows[(allrows.high < allrows.low) |
                  (allrows.high < allrows.open) | (allrows.high < allrows.close) |
                  (allrows.low > allrows.open) | (allrows.low > allrows.close)]
    allrows.to_csv(out, index=False)
    px = allrows["close"]
    print(f"[{symbol} {interval}] -> {out.name}")
    print(f"  rows={len(allrows)}  span={allrows.datetime.min()} .. {allrows.datetime.max()}")
    print(f"  close: min={px.min():.4g} median={px.median():.4g} max={px.max():.4g}  bad_ohlc_rows={len(bad)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
