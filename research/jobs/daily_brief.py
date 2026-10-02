"""PHASE 9 / N-6 — DAILY_SIGNALS briefing (standing rule D-021 §9).

Produces the daily briefing: a forward event-risk calendar (the next scheduled high-impact releases,
projected from each event's observed cadence in the news table) and, for each live signal, a one-line
news context + the scheduled event that could invalidate it before its horizon. Until a validated
candidate exists, the signal list is empty by design and the briefing is the event-risk calendar only.
Keyless: reads the committed news table (src/news.py) + DAILY_SIGNALS.md.

Exposes brief_for_signal(signal, news) for the future scanner to call per signal.
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
import newsfactor as NF   # noqa: E402  (load_news + class->news mapping)
import news as NW         # noqa: E402

DAILY = ROOT / "DAILY_SIGNALS.md"
HIGH_IMPACT = {"CPI", "PCE", "NFP", "GDP", "FedFunds", "CrudeInventories"}


def forward_calendar(news: pd.DataFrame, asof: pd.Timestamp, horizon_days: int = 10) -> pd.DataFrame:
    """Project the NEXT occurrence of each recurring event from its observed cadence (median gap
    between past releases). Returns high-impact events due within `horizon_days` of `asof`."""
    if news is None or news.empty:
        return pd.DataFrame(columns=["name", "instrument_class", "next_expected", "cadence_days"])
    rows = []
    for (name, cls), g in news.groupby(["name", "instrument_class"]):
        t = g["first_available_at"].dropna().sort_values()
        if len(t) < 2:
            continue
        gap = t.diff().dropna().dt.total_seconds().median() / 86400.0
        nxt = t.iloc[-1] + pd.Timedelta(days=gap)
        while nxt < asof:                       # roll forward to the first future occurrence
            nxt = nxt + pd.Timedelta(days=gap)
        rows.append(dict(name=name, instrument_class=cls, next_expected=nxt, cadence_days=round(gap, 1)))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    within = df[df["next_expected"] <= asof + pd.Timedelta(days=horizon_days)]
    return within.sort_values("next_expected").reset_index(drop=True)


def brief_for_signal(signal: dict, news: pd.DataFrame, asof: pd.Timestamp) -> str:
    """One-line news context + next invalidating event for a live signal (D-021 §9)."""
    aclass = signal.get("asset_class", "")
    sub = NF.news_for_class(news, aclass)
    tag = "quiet session"
    if not sub.empty:
        past = sub[sub["first_available_at"] <= asof]
        if not past.empty:
            last = past.sort_values("first_available_at").iloc[-1]
            sign = "surprise+" if (last.get("surprise") or 0) > 0 else ("surprise-" if (last.get("surprise") or 0) < 0 else "in-line")
            tag = f"last {last['name']} {sign}"
    cal = forward_calendar(news, asof)
    srcs = NF.CLASS_SRC.get(aclass, set())
    cal = cal[cal["instrument_class"].isin(srcs)] if srcs else cal.iloc[0:0]
    evrisk = "none in 10d"
    if not cal.empty:
        e = cal.iloc[0]
        evrisk = f"{e['name']} ~{e['next_expected'].date()}"
    return f"news: {tag}; next event risk: {evrisk}"


def render(news: pd.DataFrame, asof: pd.Timestamp) -> str:
    cal = forward_calendar(news, asof)
    lines = [f"## Briefing {asof.date()}",
             "**No trades today.** No validated candidate exists yet (Phases 3–9 found 0 MTC-significant "
             "edges); an empty list is the honest output. The event-risk calendar below is live.", "",
             "### Event-risk calendar (next 10 days, projected from release cadence)"]
    if cal.empty:
        lines.append("_No high-impact events projected (news table empty or too short)._")
    else:
        lines.append("| event | class | next (approx, UTC) | cadence (d) |")
        lines.append("|---|---|---|--:|")
        for _, e in cal.iterrows():
            flag = " ⚠high" if e["name"] in HIGH_IMPACT else ""
            lines.append(f"| {e['name']}{flag} | {e['instrument_class']} | {e['next_expected'].strftime('%Y-%m-%d %H:%M')} | {e['cadence_days']} |")
    lines += ["", "_Per-signal briefing (once candidates are live): `news: <tag>; next event risk: "
              "<event ~date>` — see brief_for_signal(). No new intraday entry within 30 min of a ⚠high "
              "event; no holding a fresh position through one without a logged reason (D-021 §3)._"]
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default="", help="reference date (UTC, YYYY-MM-DD); default = latest news date")
    a = ap.parse_args()
    news = NF.load_news()
    if a.asof:
        asof = pd.Timestamp(a.asof)
    else:
        asof = news["first_available_at"].max() if not news.empty else pd.Timestamp(datetime.now(timezone.utc).date())
    section = render(news, asof)

    # replace the most recent "## Briefing"/"## <date>" block under the header, else insert after intro
    txt = DAILY.read_text(encoding="utf-8")
    marker = "\n## Briefing "
    head, sep, _ = txt.partition(marker)
    if sep:                                    # drop old briefing up to the next '---'
        rest = _.split("\n---\n", 1)
        tail = ("\n---\n" + rest[1]) if len(rest) > 1 else "\n"
        txt = head + "\n" + section + "\n" + tail
    else:
        parts = txt.split("\n---\n", 1)
        txt = parts[0] + "\n\n" + section + "\n\n---\n" + (parts[1] if len(parts) > 1 else "")
    DAILY.write_text(txt, encoding="utf-8")
    print(f"briefing written for {asof.date()} ({0 if news.empty else len(forward_calendar(news, asof))} upcoming events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
