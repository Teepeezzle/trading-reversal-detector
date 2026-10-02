"""PHASE 10 / N-8 — resumable Alpha Vantage sentiment harvester.

Backfills a DAILY per-class sentiment series from AV NEWS_SENTIMENT into the committed archive
research/altdata_committed/news/av_sentiment.csv.gz. Free tier = 25 req/day, so it processes a bounded
batch of (class, month) windows per run (oldest gaps first; current month always refreshed) and stops
on a rate-limit note — a daily workflow finishes the backfill over a few days, then keeps it current.
Needs ALPHAVANTAGE_API_KEY; exits clean + logs a blocker if absent (never fabricates).

Usage:  python research/jobs/avsentiment_refresh.py [--start 2023-01-01] [--max 20]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import avsentiment as AV   # noqa: E402

BLOCKERS = ROOT / "BLOCKERS.md"
ARCHIVE = ROOT / "altdata_committed" / "news" / "av_sentiment.csv.gz"


def load_archive() -> pd.DataFrame:
    if not ARCHIVE.exists():
        return pd.DataFrame(columns=["date", "instrument_class", "sent_wmean", "n_articles"])
    df = pd.read_csv(ARCHIVE)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def have_window(arch: pd.DataFrame, aclass: str, ym: str) -> bool:
    if arch.empty:
        return False
    m = (arch["instrument_class"] == aclass) & (arch["date"].dt.strftime("%Y%m") == ym)
    return bool(m.any())


def upsert(arch: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if new.empty:
        return arch
    combined = pd.concat([arch, new], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    return combined.drop_duplicates(subset=["date", "instrument_class"], keep="last").sort_values(
        ["instrument_class", "date"]).reset_index(drop=True)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--max", type=int, default=20, help="max API windows this run (free tier ~25/day)")
    a = ap.parse_args()

    key = os.environ.get("ALPHAVANTAGE_API_KEY", "")
    if not key:
        with BLOCKERS.open("a", encoding="utf-8") as f:
            f.write("\n## N-8 AV sentiment\n- ALPHAVANTAGE_API_KEY not set — skipped.\n")
        print("ALPHAVANTAGE_API_KEY not set — logged blocker, exiting clean."); return 0

    arch = load_archive()
    wins = AV.months(a.start)
    cur_ym = wins[-1][0] if wins else None
    # build the work list: every (class, month); skip complete months already present; always refresh current
    work = [(topic, cls, ym, tf, tt)
            for topic, cls in AV.TOPIC_CLASS.items()
            for (ym, tf, tt) in wins
            if (ym == cur_ym) or not have_window(arch, cls, ym)]
    work.sort(key=lambda x: x[2])   # oldest-first
    print(f"AV sentiment harvest: {len(work)} windows pending (archive rows: {len(arch)}); batch max {a.max}")

    done = 0
    for topic, cls, ym, tf, tt in work:
        if done >= a.max:
            print(f"hit --max {a.max}; stopping (resumable — daily cron continues)"); break
        feed, limited = AV.fetch_window(key, topic, tf, tt)
        if limited:
            print("AV daily limit reached; stopping (resumable)."); break
        agg = AV.aggregate_daily(feed, cls)
        arch = upsert(arch, agg)
        done += 1
        print(f"  {cls:<12} {ym}: {len(feed)} articles -> {len(agg)} days", flush=True)
        import time as _t; _t.sleep(AV.RATE_SLEEP)

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    arch.to_csv(ARCHIVE, index=False, compression="gzip")
    span = f"{arch['date'].min()} .. {arch['date'].max()}" if not arch.empty else "-"
    print(f"done. processed {done} windows; archive rows={len(arch)} [{span}] by class: "
          f"{arch.groupby('instrument_class').size().to_dict() if not arch.empty else {}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
