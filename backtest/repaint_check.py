"""Demonstrate the 4h partial-bar repaint in the deployed cron path.

The live workflow runs at 07:00, 11:00, 15:00, 19:00 UTC and calls
``_fetch_4h_via_resample`` -> ``hourly.resample("4h")``. pandas anchors 4h
buckets at 00:00, so the buckets are [00-04), [04-08), [08-12), [12-16),
[16-20), [20-24). At 11:00 UTC the [08-12) bucket has only the 08,09,10,11
hours partially present — the bar is STILL FORMING. The detector treats
``df.iloc[-1]`` as "the most recent CLOSED candle" and decides close-back on it.

This script takes real 1h data and, for each cron time, compares:
    * the 4h bar the cron SEES (partial), vs
    * the same 4h bar once it has FULLY closed.
It flags every case where the close-back verdict flips — i.e. the emailed
signal repaints away.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

CRON_HOURS = [7, 11, 15, 19]
AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def main(ticker: str = "BTC-USD") -> int:
    raw = yf.download(ticker, period="60d", interval="1h",
                      progress=False, auto_adjust=False, threads=False)
    if raw is None or raw.empty:
        print("no data")
        return 1
    hourly = _flatten(raw)
    if hourly.index.tz is not None:
        hourly.index = hourly.index.tz_convert("UTC").tz_localize(None)

    # Fully-closed 4h bars (ground truth).
    closed_4h = hourly.resample("4h").agg(AGG).dropna()

    flips = 0
    examples = []
    for ts in hourly.index:
        if ts.hour not in CRON_HOURS:
            continue
        # What the cron ACTUALLY has at wall-clock ts: only 1h bars that have
        # already closed, i.e. bars whose START is strictly before ts. The bar
        # labelled ts itself is just opening and carries no data yet.
        seen = hourly.loc[hourly.index < ts].resample("4h").agg(AGG).dropna()
        if len(seen) < 2:
            continue
        partial_bar = seen.iloc[-1]            # the still-forming bucket
        bucket_start = seen.index[-1]
        if bucket_start not in closed_4h.index:
            continue
        final_bar = closed_4h.loc[bucket_start]  # same bucket, fully closed

        # Only interested when the cron's view of this bucket is genuinely
        # partial (fewer bars than the closed bucket has).
        bucket_end = bucket_start + pd.Timedelta(hours=4)
        if ts >= bucket_end:
            continue  # bucket already complete at ts -> no repaint possible

        # Toy level = prior bucket's low (a "support"). Did the close-back flip?
        prior_low = seen.iloc[-2]["Low"]
        seen_close_back = partial_bar["Close"] > prior_low
        final_close_back = final_bar["Close"] > prior_low
        # The High/Low the signal "saw" vs reality also differs:
        high_grew = final_bar["High"] > partial_bar["High"] + 1e-9
        low_grew = final_bar["Low"] < partial_bar["Low"] - 1e-9

        if seen_close_back != final_close_back or high_grew or low_grew:
            flips += 1
            if len(examples) < 6:
                examples.append(
                    {
                        "cron_time": ts,
                        "bucket": bucket_start,
                        "seen_close": round(float(partial_bar["Close"]), 2),
                        "final_close": round(float(final_bar["Close"]), 2),
                        "seen_high": round(float(partial_bar["High"]), 2),
                        "final_high": round(float(final_bar["High"]), 2),
                        "seen_low": round(float(partial_bar["Low"]), 2),
                        "final_low": round(float(final_bar["Low"]), 2),
                        "closeback_flipped": seen_close_back != final_close_back,
                    }
                )

    total_cron = sum(1 for ts in hourly.index if ts.hour in CRON_HOURS)
    print(f"\n===== 4h REPAINT CHECK ({ticker}, 60d of 1h data) =====")
    print(f"Cron evaluations examined : {total_cron}")
    print(f"Bars where what-the-cron-saw != fully-closed bar : {flips} "
          f"({100*flips/max(total_cron,1):.1f}%)")
    print("\nExample repainting bars (the signal saw the LEFT values, "
          "but the candle actually CLOSED at the RIGHT values):")
    if examples:
        print(pd.DataFrame(examples).to_string(index=False))
    else:
        print("  (none in this sample)")
    print("\nEvery row above is a bar the emailed signal was computed on while "
          "the 4h candle was still forming. By the real close, the OHLC moved — "
          "and where 'closeback_flipped' is True, the rejection the email "
          "claimed never actually happened.")
    return 0


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "BTC-USD"
    raise SystemExit(main(t))
