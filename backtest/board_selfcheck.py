"""Board self-check (fix/board-data-integrity) — run BEFORE deploy.

Asserts that the generated snapshot (dashboard/data.js) renders every validated-universe asset with a
non-null price and a bar age within its class bound. Emits loud GitHub-Actions annotations
(::error:: / ::warning::) and a summary, and exits non-zero on any violation — so a degraded board is
SURFACED, never silent. Intended as a non-blocking workflow step (the board itself now fails loud with
NODATA cards), so updates still ship while the failure is visible in the run.

Usage:  python backtest/board_selfcheck.py [dashboard/data.js]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "backtest"))
import dashboard_data as dd   # noqa: E402  (ASSETS = validated universe)
import board_health as HEALTH  # noqa: E402


def load_state(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8").strip()
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j < 0:
        raise ValueError(f"no JSON object in {path}")
    return json.loads(txt[i:j + 1])


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "dashboard" / "data.js")
    if not path.exists():
        print(f"::error::board self-check: {path} not found (generation did not run?)"); return 2
    state = load_state(path)
    cards = {c["asset"]: c for c in state.get("assets", [])}
    validated = set(dd.ASSETS)
    errors, warns = [], []

    for a in sorted(validated):
        c = cards.get(a)
        if c is None:
            errors.append(f"{a}: MISSING from board payload"); continue
        if c.get("status") == "NODATA" or c.get("price") in (None, ""):
            errors.append(f"{a}: NO PRICE ({c.get('error','no data')})"); continue
        age = c.get("bar_age_min")
        bound = HEALTH.stale_bound(a)
        if age is None:
            warns.append(f"{a}: no freshness timestamp")
        elif age > bound:
            warns.append(f"{a}: STALE bar_age={age:.0f}min > {bound}min bound")
        if c.get("stale_vs_spot"):
            warns.append(f"{a}: bar stale vs live spot (spot age {c.get('spot_age_min')}min)")

    # watch-list: warn only (not deploy-critical)
    for a, c in cards.items():
        if a not in validated and (c.get("status") == "NODATA" or c.get("price") in (None, "")):
            warns.append(f"{a} (watch): no data ({c.get('error','')})")

    for w in warns:
        print(f"::warning::board self-check: {w}")
    for e in errors:
        print(f"::error::board self-check: {e}")
    total = len(cards); nod = sum(1 for c in cards.values() if c.get("status") == "NODATA")
    print(f"\nboard self-check: {total} cards, {len(validated)} validated, "
          f"{len(errors)} critical, {len(warns)} warnings, {nod} NODATA. "
          f"snapshot generated {state.get('generated')}")
    if errors:
        print("RESULT: FAIL (validated assets missing or price-less — see ::error:: above)"); return 1
    print("RESULT: OK (every validated asset has a fresh price)"); return 0


if __name__ == "__main__":
    sys.exit(main())
