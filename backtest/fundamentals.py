"""Fundamental CONTEXT layer for the Confluence Board (display-only; D-032/D-033 reframe).

This is NOT a signal and makes NO performance claim. It computes, strictly AS-OF a timestamp
(no look-ahead: only records with available_at <= asof are used; nothing is interpolated,
extrapolated, or back-filled — a missing record is a gap, left null), the macro backdrop and the
latest fundamental values relevant to an instrument, plus the next scheduled high-impact event
projected from release cadence. It also exposes three honest *shadow* uses — gate / score / tag —
for the parallel forward test (recorded, never acted on, until pooled n>=200; D-034).

Data (read-only, committed): research/altdata_committed/news/{fred,eia,av_sentiment}.csv.gz and
funding/<COIN>.csv.gz. Macro values are FRED first-release (output_type=4) = POINT-IN-TIME, so no
revision look-ahead. EIA stores the release-week print (lightly revised later; noted). Sentiment and
funding are point-in-time by construction.

Label carried on every context object: "Context - not validated".
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = ROOT / "research" / "altdata_committed" / "news"
FUNDING_DIR = ROOT / "research" / "altdata_committed" / "funding"
LABEL = "Context - not validated"

# board asset -> fundamental class. FX/metals/indices ride the USD macro backdrop (FRED); oil = EIA;
# crypto = funding + sentiment. (Prefix/suffix heuristics keep new instruments mapping automatically.)
CRYPTO = {"BTCUSD", "ETHUSD", "DOGEUSD", "AVAXUSD", "SOLUSD", "XRPUSD", "ADAUSD", "BNBUSD", "LTCUSD",
          "LINKUSD", "DOTUSD", "ATOMUSD", "BCHUSD", "ETCUSD", "TRXUSD", "UNIUSD", "XLMUSD"}
OIL = {"XTIUSD", "XBRUSD", "WTIUSD", "USOUSD", "UKOUSD"}


def class_of(asset: str) -> str:
    a = asset.upper()
    if a in CRYPTO or a.endswith("USD") and a[:-3] in {c[:-3] for c in CRYPTO}:
        return "crypto"
    if a in OIL:
        return "oil"
    return "forex_macro"      # FX, metals, indices, DXY -> USD macro backdrop


# high-impact macro event names we project forward (from the FRED archive's own names)
HIGH_MACRO = {"CPI", "NFP", "GDP", "PCE"}


# ----------------------------- loading -----------------------------
def _load_news(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    for c in ("published_at", "first_available_at"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, errors="coerce").dt.tz_localize(None)
    return df


def load_bundle() -> dict:
    """Load all committed fundamental archives once (read-only). Safe if any file is absent."""
    b = {"fred": _load_news(NEWS_DIR / "fred.csv.gz"),
         "eia": _load_news(NEWS_DIR / "eia.csv.gz"),
         "sent": None, "funding": {}}
    sp = NEWS_DIR / "av_sentiment.csv.gz"
    if sp.exists():
        s = pd.read_csv(sp)
        s["date"] = pd.to_datetime(s["date"], utc=True, errors="coerce").dt.tz_localize(None)
        b["sent"] = s
    if FUNDING_DIR.exists():
        for f in FUNDING_DIR.glob("*.csv.gz"):
            d = pd.read_csv(f)
            d["time"] = pd.to_datetime(d["time"], utc=True, errors="coerce").dt.tz_localize(None)
            b["funding"][f.name.replace(".csv.gz", "")] = d
    return b


def _asof(df: pd.DataFrame, tcol: str, asof: pd.Timestamp) -> pd.DataFrame:
    """Rows known at `asof` (tcol <= asof). No-lookahead. Empty if none."""
    if df is None or df.empty or tcol not in df.columns:
        return pd.DataFrame()
    return df[df[tcol] <= asof]


def _macro_names(fred: pd.DataFrame) -> dict:
    return {n: g.sort_values("first_available_at") for n, g in fred.groupby("name")} if fred is not None and not fred.empty else {}


# ----------------------------- regime + values -----------------------------
def macro_regime(bundle: dict, asof: pd.Timestamp, dxy_frame: pd.DataFrame | None = None) -> dict:
    """USD macro backdrop as-of `asof`, from FRED first-release (point-in-time). Qualitative tags only."""
    fred = _asof(bundle.get("fred"), "first_available_at", asof)
    out = {"rates_dir": "na", "inflation_dir": "na", "usd_backdrop": "na", "dxy_trend": "na",
           "available_at": None, "point_in_time": True}
    if fred.empty:
        return out
    g = _macro_names(fred)
    stamps = []
    ff = g.get("FedFunds")
    if ff is not None and len(ff) >= 2:
        last = float(ff["actual"].iloc[-1]); prev = float(ff["actual"].iloc[max(0, len(ff) - 4)])
        out["rates_dir"] = "rising" if last > prev + 1e-9 else "falling" if last < prev - 1e-9 else "holding"
        stamps.append(ff["first_available_at"].iloc[-1])
    cpi = g.get("CPI")
    if cpi is not None and len(cpi) >= 14:                     # CPIAUCSL index -> yoy direction
        idx = cpi["actual"].to_numpy(dtype=float)
        yoy_now = idx[-1] / idx[-13] - 1.0
        yoy_prev = idx[-2] / idx[-14] - 1.0
        out["inflation_dir"] = ("accelerating" if yoy_now > yoy_prev + 1e-6
                                else "cooling" if yoy_now < yoy_prev - 1e-6 else "flat")
        out["inflation_yoy_pct"] = round(yoy_now * 100, 2)
        stamps.append(cpi["first_available_at"].iloc[-1])
    # coarse USD backdrop from rates + inflation (qualitative, context only)
    r, i = out["rates_dir"], out["inflation_dir"]
    if r == "rising" or i == "accelerating":
        out["usd_backdrop"] = "hawkish-leaning"
    elif r == "falling" or i == "cooling":
        out["usd_backdrop"] = "dovish-leaning"
    elif r == "holding":
        out["usd_backdrop"] = "neutral"
    if dxy_frame is not None and len(dxy_frame) >= 50:
        c = float(dxy_frame["Close"].iloc[-1]); sma = float(dxy_frame["Close"].rolling(50).mean().iloc[-1])
        if np.isfinite(sma):
            out["dxy_trend"] = "up" if c > sma else "down"
    if stamps:
        out["available_at"] = str(max(stamps))
    return out


def vol_regime(price_frame: pd.DataFrame | None, atr_len: int = 14, win: int = 200) -> dict:
    """Volatility regime from the instrument's own ATR% vs its trailing median (high/normal/low)."""
    if price_frame is None or len(price_frame) < max(atr_len + 2, 30):
        return {"regime": "na"}
    h = price_frame["High"].to_numpy(dtype=float); lo = price_frame["Low"].to_numpy(dtype=float)
    c = price_frame["Close"].to_numpy(dtype=float)
    tr = np.maximum(h[1:] - lo[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(lo[1:] - c[:-1])))
    atr = pd.Series(tr).ewm(alpha=1 / atr_len, adjust=False).mean().to_numpy()
    atrp = atr / c[1:]
    cur = atrp[-1]; base = pd.Series(atrp).tail(win)
    med = float(base.median()); hi = float(base.quantile(0.75)); low = float(base.quantile(0.25))
    reg = "high" if cur >= hi else "low" if cur <= low else "normal"
    return {"regime": reg, "atr_pct": round(float(cur) * 100, 3), "median_atr_pct": round(med * 100, 3)}


def next_event(bundle: dict, aclass: str, asof: pd.Timestamp, horizon_days: int = 5) -> dict | None:
    """Next scheduled high-impact event, projected from the class's observed release cadence.
    Forward projection labeled 'expected' (not a record). Keyless; no-lookahead (uses only past dates)."""
    if aclass == "oil":
        ev = _asof(bundle.get("eia"), "first_available_at", asof)
        names = {"CrudeInventories"}
    elif aclass == "forex_macro":
        ev = _asof(bundle.get("fred"), "first_available_at", asof)
        names = HIGH_MACRO
    else:
        return None                                           # crypto: no scheduled macro release
    if ev is None or ev.empty:
        return None
    best = None
    for name, g in ev[ev["name"].isin(names)].groupby("name"):
        t = g["first_available_at"].sort_values()
        if len(t) < 3:
            continue
        gap = t.diff().dropna().dt.total_seconds().median() / 86400.0
        nxt = t.iloc[-1] + pd.Timedelta(days=gap)
        while nxt < asof:
            nxt = nxt + pd.Timedelta(days=gap)
        if best is None or nxt < best["expected_at"]:
            best = {"name": name, "expected_at": nxt, "cadence_days": round(gap, 1)}
    if best is None:
        return None
    best["within_horizon"] = bool(best["expected_at"] <= asof + pd.Timedelta(days=horizon_days))
    best["tier"] = "high"
    best["expected_at"] = str(best["expected_at"])
    best["basis"] = "projected-from-cadence"
    return best


def latest_values(bundle: dict, asset: str, aclass: str, asof: pd.Timestamp) -> list[dict]:
    """Latest fundamental value(s) known at `asof` for the instrument's class. No back-fill: a series
    that does not cover `asof` is reported with its real age and a stale flag, never guessed."""
    out = []

    def pack(name, row, tcol, valcol="actual"):
        av = row[tcol]
        age = (asof - av).total_seconds() / 86400.0
        return {"name": name, "value": None if pd.isna(row.get(valcol)) else round(float(row[valcol]), 4),
                "surprise": None if pd.isna(row.get("surprise")) else round(float(row["surprise"]), 4),
                "available_at": str(av), "age_days": round(age, 1), "stale": age > 45}

    if aclass in ("forex_macro",):
        fred = _asof(bundle.get("fred"), "first_available_at", asof)
        for name in ("CPI", "NFP", "FedFunds"):
            g = fred[fred["name"] == name] if not fred.empty else fred
            if g is not None and not g.empty:
                out.append(pack(name, g.sort_values("first_available_at").iloc[-1], "first_available_at"))
    elif aclass == "oil":
        eia = _asof(bundle.get("eia"), "first_available_at", asof)
        if eia is not None and not eia.empty:
            out.append(pack("CrudeInventories", eia.sort_values("first_available_at").iloc[-1], "first_available_at"))
    elif aclass == "crypto":
        fund = bundle.get("funding", {}).get(asset)
        f = _asof(fund, "time", asof)
        if f is not None and not f.empty:
            r = f.sort_values("time").iloc[-1]
            age = (asof - r["time"]).total_seconds() / 86400.0
            out.append({"name": "funding_rate", "value": round(float(r["funding"]), 6),
                        "available_at": str(r["time"]), "age_days": round(age, 2), "stale": age > 1})
        sent = bundle.get("sent")
        if sent is not None and not sent.empty:
            avail = sent.copy(); avail["avail"] = avail["date"] + pd.Timedelta(days=1)   # D+1 no-lookahead
            s = avail[(avail["instrument_class"] == "crypto") & (avail["avail"] <= asof)]
            if not s.empty:
                r = s.sort_values("avail").iloc[-1]
                age = (asof - r["avail"]).total_seconds() / 86400.0
                out.append({"name": "news_sentiment", "value": round(float(r["sent_wmean"]), 4),
                            "available_at": str(r["avail"]), "age_days": round(age, 1), "stale": age > 7})
    return out


# ----------------------------- the context object (Track A) -----------------------------
def context_vector(asset: str, asof, price_frame: pd.DataFrame | None = None,
                   dxy_frame: pd.DataFrame | None = None, bundle: dict | None = None,
                   horizon_days: int = 5) -> dict:
    """Assemble the display-only context for one signal/card. Purely derived; cannot affect signals."""
    if bundle is None:
        bundle = load_bundle()
    asof = pd.Timestamp(asof)
    if asof.tzinfo is not None:
        asof = asof.tz_convert("UTC").tz_localize(None)
    aclass = class_of(asset)
    return {
        "label": LABEL,
        "asof": str(asof),
        "asset_class": aclass,
        "macro_regime": macro_regime(bundle, asof, dxy_frame),
        "vol_regime": vol_regime(price_frame),
        "latest_values": latest_values(bundle, asset, aclass, asof),
        "next_event": next_event(bundle, aclass, asof, horizon_days),
    }


# ----------------------------- shadow uses (Track B; recorded, never acted on) -----------------------------
def shadow_variants(asset: str, direction: str, asof, bundle: dict | None = None,
                    horizon_days: int = 5) -> dict:
    """The three honest fundamental USES, as DECISIONS only (not applied). direction in {buy,sell}.
      (a) gate  : would the signal be BLOCKED? (within 30min pre a high-impact event, or a high-impact
                  event scheduled inside the holding horizon that could invalidate it)
      (b) score : a bounded confidence delta in [-1,+1] from macro-backdrop alignment + recent surprise
      (c) tag   : regime label only (no action)
    Mechanical + non-discretionary; the forward test measures whether any of these would have helped."""
    if bundle is None:
        bundle = load_bundle()
    asof = pd.Timestamp(asof)
    if asof.tzinfo is not None:
        asof = asof.tz_convert("UTC").tz_localize(None)
    aclass = class_of(asset)
    reg = macro_regime(bundle, asof)
    nxt = next_event(bundle, aclass, asof, horizon_days)

    # (a) hard gate
    block = False; reason = "clear"
    if nxt and nxt["within_horizon"]:
        block = True; reason = f"high-impact {nxt['name']} within {horizon_days}d (expected {nxt['expected_at'][:10]})"
    gate = {"pass": (not block), "reason": reason}

    # (b) score: align trade direction with USD backdrop for USD-quoted FX/metals/indices + recent surprise
    score = 0.0; parts = []
    back = reg.get("usd_backdrop")
    if aclass == "forex_macro" and back in ("hawkish-leaning", "dovish-leaning"):
        # hawkish USD => headwind for XXXUSD longs / tailwind for USDXXX longs (coarse, USD-quote heuristic)
        usd_quote = asset.upper().endswith("USD")
        usd_base = asset.upper().startswith("USD")
        strong_usd = (back == "hawkish-leaning")
        if usd_quote:
            align = -1 if strong_usd else 1
        elif usd_base:
            align = 1 if strong_usd else -1
        else:
            align = 0
        s = 0.5 * align * (1 if direction == "buy" else -1)
        score += s; parts.append(f"usd_backdrop {back}:{s:+.2f}")
    vals = latest_values(bundle, asset, aclass, asof)
    surp = next((v.get("surprise") for v in vals if v.get("surprise") is not None), None)
    if surp is not None and abs(surp) > 0:
        s = 0.25 * (1 if surp > 0 else -1) * (1 if direction == "buy" else -1)
        score += s; parts.append(f"last_surprise:{s:+.2f}")
    score = float(max(-1.0, min(1.0, score)))

    # (c) regime tag (no action)
    tag_bits = []
    if nxt and nxt["within_horizon"]:
        tag_bits.append("pre-event")
    tag_bits.append(f"rates-{reg.get('rates_dir','na')}")
    tag_bits.append(f"infl-{reg.get('inflation_dir','na')}")
    if aclass == "crypto":
        f = next((v for v in vals if v["name"] == "funding_rate"), None)
        if f and f["value"] is not None:
            tag_bits.append("funding+" if f["value"] > 0 else "funding-")

    return {"gate": gate, "score": {"delta": round(score, 3), "parts": parts},
            "tag": "|".join(tag_bits), "asof": str(asof)}
