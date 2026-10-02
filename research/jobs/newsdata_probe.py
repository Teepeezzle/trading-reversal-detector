"""PHASE 9 — newsdata.io probe (read-only): confirm the key works and show what the free tier returns.

newsdata.io is a headline/article aggregator (not economic data). Free tier = /latest (past ~48h),
no historical archive, no sentiment. This probe hits /latest for a few finance-relevant queries,
prints status + article count + sample fields (title, pubDate, country, category, sentiment-if-any),
and reports whether a usable `pubDate` timestamp is present. It stores nothing. Needs NEWSDATAIO_API_KEY.
"""
from __future__ import annotations

import json
import os
import sys

import requests

BASE = "https://newsdata.io/api/1/latest"
UA = {"User-Agent": "Mozilla/5.0 (research)"}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    key = os.environ.get("NEWSDATAIO_API_KEY", "")
    if not key:
        print("NEWSDATAIO_API_KEY not set — cannot probe."); return 0
    for params in ({"category": "business", "language": "en"},
                   {"q": "federal reserve OR CPI OR OPEC OR crude oil", "language": "en"},
                   {"q": "bitcoin OR ethereum", "language": "en"}):
        try:
            r = requests.get(BASE, params={**params, "apikey": key}, headers=UA, timeout=30)
            print(f"\n== query {params} -> HTTP {r.status_code} ==")
            j = r.json()
            if r.status_code != 200:
                print(f"  error: {json.dumps(j)[:300]}"); continue
            res = j.get("results") or []
            print(f"  status={j.get('status')} totalResults={j.get('totalResults')} returned={len(res)}")
            fields = sorted(res[0].keys()) if res else []
            print(f"  article fields: {fields}")
            print(f"  has pubDate: {'pubDate' in fields} | has sentiment: {'sentiment' in fields}")
            for a in res[:3]:
                print(f"   - [{a.get('pubDate')}] ({a.get('country')}/{a.get('category')}) "
                      f"{str(a.get('title'))[:90]}  sentiment={a.get('sentiment')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  probe error: {exc}")
    print("\ndone (read-only probe).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
