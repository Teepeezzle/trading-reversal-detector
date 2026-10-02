"""PHASE 9 / N-7 — scheduled newsdata.io headline collector.

Fetches the latest finance-relevant headlines and appends new ones (dedup) to the committed archive
research/altdata_committed/news/headlines.csv.gz. Forward-only (newsdata free = ~48h, no archive).
Needs NEWSDATAIO_API_KEY; exits clean + logs a blocker if absent (never fabricates).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import newsfeed as NF   # noqa: E402

BLOCKERS = ROOT / "BLOCKERS.md"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    key = os.environ.get("NEWSDATAIO_API_KEY", "")
    if not key:
        with BLOCKERS.open("a", encoding="utf-8") as f:
            f.write("\n## N-7 newsdata collect\n- NEWSDATAIO_API_KEY not set — skipped.\n")
        print("NEWSDATAIO_API_KEY not set — logged blocker, exiting clean."); return 0
    fetched, added, total = NF.collect(key)
    print(f"done. fetched={fetched} added={added} archive_total={total} -> {NF.ARCHIVE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
