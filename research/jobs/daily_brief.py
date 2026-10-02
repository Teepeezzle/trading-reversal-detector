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
import requests

FXMACRO_CAL = "https://api.fxmacrodata.com/v1/calendar/usd"   # free, no key — official forward schedule

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import newsfactor as NF   # noqa: E402  (load_news + class->news mapping)
import news as NW         # noqa: E402
import newsfeed as NFEED  # noqa: E402  (N-7 forward headline archive, optional)

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


def fxmacro_forward_calendar(asof: pd.Timestamp, horizon_days: int = 10) -> pd.DataFrame:
    """OFFICIAL forward US macro release schedule with exact datetimes (FXMacroData free, no key).
    Returns high-importance events within the horizon. Empty on any failure (graceful fallback)."""
    try:
        r = requests.get(FXMACRO_CAL, timeout=20, headers={"User-Agent": "Mozilla/5.0 (research)"})
        data = (r.json() or {}).get("data") or []
    except Exception:
        return pd.DataFrame()
    rows = []
    for a in data:
        ts = a.get("announcement_datetime")
        if not ts:
            continue
        t = pd.to_datetime(ts, unit="s", utc=True).tz_localize(None)
        if t < asof or t > asof + pd.Timedelta(days=horizon_days):
            continue
        imp = str(a.get("event_importance", "")).lower()
        if imp not in ("high", "medium"):                     # skip tier-3 noise
            continue
        high = imp == "high" or bool(a.get("top_tier_for_currency"))
        rows.append(dict(name=str(a.get("release") or a.get("name")), instrument_class="forex_macro",
                         next_expected=t, cadence_days=np.nan, source="official", high=high))
    df = pd.DataFrame(rows)
    return df.sort_values("next_expected").reset_index(drop=True) if not df.empty else df


def combined_calendar(news: pd.DataFrame, asof: pd.Timestamp, horizon_days: int = 10) -> pd.DataFrame:
    """Official FXMacroData forward schedule for macro (exact times) + cadence-projected for the rest
    (e.g. EIA oil). Official rows win on name overlap."""
    cadence = forward_calendar(news, asof, horizon_days)
    if not cadence.empty:
        cadence["source"] = "projected"
        cadence["high"] = cadence["name"].isin(HIGH_IMPACT)
    official = fxmacro_forward_calendar(asof, horizon_days)
    if official.empty:
        return cadence
    cols = ["name", "instrument_class", "next_expected", "source", "high"]
    keep = cadence[cadence["instrument_class"] != "forex_macro"] if not cadence.empty else cadence
    out = pd.concat([official[cols], keep[cols]], ignore_index=True) if not keep.empty else official[cols]
    return out.sort_values("next_expected").reset_index(drop=True)


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
    cal = combined_calendar(news, asof, 14)
    official_n = int((cal["source"] == "official").sum()) if not cal.empty else 0
    lines = [f"## Briefing {asof.date()}",
             "**No trades today.** No validated candidate exists yet (Phases 3–9 found 0 MTC-significant "
             "edges); an empty list is the honest output. The event-risk calendar below is live.", "",
             f"### Event-risk calendar (next 14 days — {official_n} official FXMacroData times, rest projected)"]
    if cal.empty:
        lines.append("_No high-impact events (news table empty / source offline)._")
    else:
        lines.append("| event | class | next (UTC) | source |")
        lines.append("|---|---|---|---|")
        for _, e in cal.iterrows():
            off = (e.get("source") == "official")
            flag = " ⚠high" if bool(e.get("high")) else ""
            when = e["next_expected"].strftime("%Y-%m-%d %H:%M") + ("" if off else " ~")
            lines.append(f"| {e['name']}{flag} | {e['instrument_class']} | {when} | {e.get('source','projected')} |")
    # N-7: recent headline flow from the forward archive (if any collected yet)
    try:
        hl = NFEED.load_archive()
        if not hl.empty:
            recent = hl[hl["published_at"] >= asof - pd.Timedelta(hours=48)]
            if not recent.empty:
                by = recent.groupby("instrument_class").size().to_dict()
                lines += ["", f"### Headline flow (newsdata.io, last 48h): {len(recent)} items — "
                          + ", ".join(f"{k}:{v}" for k, v in sorted(by.items()))]
                for _, h in recent.sort_values("published_at", ascending=False).head(3).iterrows():
                    lines.append(f"- [{h['published_at'].strftime('%m-%d %H:%M')}] ({h['instrument_class']}) {str(h['title'])[:100]}")
    except Exception:
        pass

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
