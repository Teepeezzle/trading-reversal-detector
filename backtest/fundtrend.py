"""Per-asset FUNDAMENTAL TREND direction for the Confluence Board context layer (display-only).

A FACTUAL statement about each asset's OWN fundamentals (not generic USD, not a prediction, not a
signal). BULLISH / BEARISH / NEUTRAL + strength, derived only from that asset's relevant drivers. Every
component carries available_at; any component older than its max-age is EXCLUDED and flagged (never
silently used or substituted); nothing is interpolated or back-filled. If a leg/driver has no reachable
free source, it is excluded and said so. Keeps the "FUNDAMENTAL TREND - NOT VALIDATED" label.

DATA REACHABILITY (empirically verified in this environment; see BOARD_INTEGRITY note / PR body):
  reachable keyless: Yahoo (US yields ^TNX, DXY, commodities GC=F/CL=F/SI=F), committed archives
  (US FRED macro = point-in-time, EIA oil, per-coin funding, AV sentiment), CoinGecko.
  NOT reachable keyless here: DBnomics, ECB, IMF, World Bank, BoE, RBA, stooq (bot-blocked) -> so
  non-US central-bank rates/inflation have NO free source and those legs are EXCLUDED, never proxied.

Per-currency drivers actually used (reachable only):
  USD  : Fed rate path (FedFunds), US inflation (CPI yoy), US labor (NFP), US real yield (10y - CPI)
  JPY  : US 10y yield / risk (carry: higher US yields -> JPY weaker)       [BoJ rate/infl EXCLUDED]
  AUD  : gold terms-of-trade (GC=F)                                         [RBA rate/infl EXCLUDED]
  CAD  : oil terms-of-trade (CL=F)                                          [BoC rate/infl EXCLUDED]
  NZD,EUR,GBP,CHF,NGN : no reachable free driver -> EXCLUDED
Metals: US real yield (inverse) + DXY (inverse) [+ gold/silver ratio for XAG].
Oil   : EIA crude inventory w/w (draw=bullish) + DXY (inverse) + US real yield (inverse = demand/
        financial-conditions headwind) + RBOB gasoline crack (refining margin = product demand)
        [OPEC+/refinery/geopolitics still EXCLUDED — no reachable free source].
Crypto: US rates+DXY (risk, inverse) + per-coin funding (extreme = contrarian) + AV sentiment (7d
        staleness -> EXCLUDED when stale, e.g. the XRP 825d case) [ETF flows / asset-specific EXCLUDED].
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import fundamentals as FUND   # reuse load_bundle() for committed FRED/EIA/funding/sentiment

LABEL = "FUNDAMENTAL TREND - NOT VALIDATED"

# max-age per data type (days) — older than this => EXCLUDE + flag (never used silently)
MAX_AGE = {"fred_monthly": 45, "fred_quarterly": 100, "market": 4, "funding": 1.0, "sentiment": 7}

# reachable Yahoo macro tickers (fetched once per board run and passed in)
MKT_TICKERS = {"us10y": "^TNX", "dxy": "DX-Y.NYB", "gold": "GC=F", "oil": "CL=F", "silver": "SI=F",
               "gasoline": "RB=F"}   # RBOB gasoline front-month -> crack / product-demand proxy for oil

CRYPTO = FUND.CRYPTO
FX_CCYS = {"USD", "EUR", "JPY", "GBP", "AUD", "NZD", "CAD", "CHF", "NGN"}

# Non-US central-bank policy rate + CPI archive names (harvested into fred.csv.gz by
# research/jobs/news_refresh.py). Gives each currency a real fundamental leg so FX crosses
# with no USD leg (EURNZD, GBPNZD, GBPAUD, the JPY crosses) are no longer "insufficient data".
# A name absent from the archive (unmapped FRED id) is simply excluded — never fabricated.
FOREIGN_MACRO = {
    "EUR": ("ECB_RATE", "EA_CPI"), "GBP": ("UK_RATE", "UK_CPI"), "JPY": ("JP_RATE", "JP_CPI"),
    "AUD": ("AU_RATE", "AU_CPI"), "NZD": ("NZ_RATE", "NZ_CPI"), "CHF": ("CH_RATE", "CH_CPI"),
    "CAD": ("CA_RATE", "CA_CPI"),
}

# USD index aliases -> treated AS the US-dollar (its fundamentals ARE the USD drivers).
USD_INDEX = {"DXY", "DX-Y.NYB", "USDX", "DXYUSD"}
# Equity-index aliases -> a free-data MACRO BACKDROP only (US rates/real-yield + USD risk),
# explicitly NOT earnings/valuation. Covers common CFD tickers so new ones map automatically.
EQUITY_INDEX = {"NAS100", "US100", "USTEC", "NDX", "SPX500", "US500", "SPX", "US30", "DJI", "DJIA",
                "GER40", "DE40", "UK100", "FTSE", "JP225", "NKY", "EU50", "EUSTX50", "SX5E", "STOXX50",
                "AUS200", "HK50"}


def _is_usd_index(a: str) -> bool:
    return a in USD_INDEX


def _is_equity_index(a: str) -> bool:
    # Tolerate a trailing "USD" quote suffix (US30USD -> US30, NAS100USD -> NAS100) so broker
    # ticker variants map without having to enumerate every spelling.
    return a in EQUITY_INDEX or (a.endswith("USD") and a[:-3] in EQUITY_INDEX)


# ----------------------------- small helpers -----------------------------
def _dir(delta, deadband):
    return "↑" if delta > deadband else "↓" if delta < -deadband else "→"


def series_trend(frame, lookback=60, deadband_pct=0.5):
    """Direction of a Yahoo daily series over `lookback` bars. Returns (arrow, pct_change, last_date, age_days)."""
    if frame is None or frame.empty or len(frame) < 5:
        return None
    c = frame["Close"].to_numpy(dtype=float)
    last = float(c[-1]); ref = float(c[-min(lookback, len(c))])
    pct = (last / ref - 1.0) * 100 if ref else 0.0
    last_date = pd.Timestamp(frame.index[-1])
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    age = (now - (last_date.tz_convert("UTC").tz_localize(None) if last_date.tzinfo else last_date)).total_seconds() / 86400
    return (_dir(pct, deadband_pct), round(pct, 2), str(last_date)[:10], round(age, 1))


def _fred_latest(bundle, name, asof):
    f = bundle.get("fred")
    if f is None or f.empty:
        return None
    g = f[(f["name"] == name) & (f["first_available_at"] <= asof)].sort_values("first_available_at")
    return g.iloc[-1] if not g.empty else None


def _comp(name, arrow, detail, available_at, used=True, reason="", vote=0):
    return {"name": name, "dir": arrow, "detail": detail, "available_at": str(available_at),
            "used": used, "reason": reason, "vote": vote}


# ----------------------------- US fundamentals (committed FRED, point-in-time) -----------------------------
def us_components(asof, bundle, mkt):
    """USD fundamental drivers. vote: +1 USD-bullish, -1 bearish. Each flagged used/excluded by age."""
    out = []
    now = asof
    # rate path: FedFunds last vs ~3 releases prior
    ff = bundle.get("fred")
    ff = ff[(ff["name"] == "FedFunds") & (ff["first_available_at"] <= asof)].sort_values("first_available_at") if ff is not None and not ff.empty else None
    if ff is not None and len(ff) >= 2:
        av = ff["first_available_at"].iloc[-1]; age = (now - av).days
        last = float(ff["actual"].iloc[-1]); prev = float(ff["actual"].iloc[max(0, len(ff) - 4)])
        arrow = _dir(last - prev, 1e-9)
        used = age <= MAX_AGE["fred_monthly"]
        out.append(_comp("US rate path", arrow, f"FedFunds {last:.2f}% ({'hiking' if arrow=='↑' else 'cutting' if arrow=='↓' else 'hold'})",
                         av, used, "" if used else f"stale {age}d", vote=(1 if arrow == "↑" else -1 if arrow == "↓" else 0) if used else 0))
    # inflation: CPI yoy accel/decel
    cpi = bundle.get("fred")
    cpi = cpi[(cpi["name"] == "CPI") & (cpi["first_available_at"] <= asof)].sort_values("first_available_at") if cpi is not None and not cpi.empty else None
    if cpi is not None and len(cpi) >= 14:
        idx = cpi["actual"].to_numpy(dtype=float); av = cpi["first_available_at"].iloc[-1]; age = (now - av).days
        yoy_now = idx[-1] / idx[-13] - 1; yoy_prev = idx[-2] / idx[-14] - 1
        arrow = _dir(yoy_now - yoy_prev, 1e-6); used = age <= MAX_AGE["fred_monthly"]
        out.append(_comp("US inflation", arrow, f"CPI {yoy_now*100:.1f}% yoy ({'accelerating' if arrow=='↑' else 'cooling' if arrow=='↓' else 'flat'})",
                         av, used, "" if used else f"stale {age}d", vote=(1 if arrow == "↑" else -1 if arrow == "↓" else 0) if used else 0))
    # labor: NFP last surprise (actual vs prior)
    nfp = bundle.get("fred")
    nfp = nfp[(nfp["name"] == "NFP") & (nfp["first_available_at"] <= asof)].sort_values("first_available_at") if nfp is not None and not nfp.empty else None
    if nfp is not None and len(nfp) >= 2:
        av = nfp["first_available_at"].iloc[-1]; age = (now - av).days
        d = float(nfp["actual"].iloc[-1]) - float(nfp["actual"].iloc[-2]); arrow = _dir(d, 1e-9)
        used = age <= MAX_AGE["fred_monthly"]
        out.append(_comp("US labor", arrow, f"NFP {'improving' if arrow=='↑' else 'deteriorating' if arrow=='↓' else 'flat'}",
                         av, used, "" if used else f"stale {age}d", vote=(1 if arrow == "↑" else -1 if arrow == "↓" else 0) if used else 0))
    # real yield: US 10y (^TNX, in %) minus CPI yoy; rising real yield = USD bullish
    ry = real_yield_trend(asof, bundle, mkt)
    if ry is not None:
        out.append(ry)
    return out


def real_yield_trend(asof, bundle, mkt):
    """US real yield = 10y nominal (^TNX) - CPI yoy. Direction over ~60d. Used by USD + metals."""
    t = series_trend(mkt.get("us10y"), 60, 0.0)
    cpi = bundle.get("fred")
    cpi = cpi[(cpi["name"] == "CPI") & (cpi["first_available_at"] <= asof)].sort_values("first_available_at") if cpi is not None and not cpi.empty else None
    if t is None or cpi is None or len(cpi) < 14:
        return _comp("US real yield", "→", "unavailable", "", used=False, reason="no reachable 10y/CPI")
    arrow, pct, ld, age = t
    used = age <= MAX_AGE["market"]
    yoy = cpi["actual"].to_numpy(dtype=float)[-1] / cpi["actual"].to_numpy(dtype=float)[-13] - 1
    ry = float(mkt["us10y"]["Close"].iloc[-1]) - yoy * 100
    return _comp("US real yield", arrow, f"10y {float(mkt['us10y']['Close'].iloc[-1]):.2f}% - CPI {yoy*100:.1f}% = {ry:.2f}% ({'rising' if arrow=='↑' else 'falling' if arrow=='↓' else 'flat'})",
                 ld, used, "" if used else f"stale {age}d", vote=(1 if arrow == "↑" else -1 if arrow == "↓" else 0) if used else 0)


# ----------------------------- foreign (non-US) macro: rate path + inflation -----------------------------
def _named_rows(bundle, name, asof):
    f = bundle.get("fred")
    if f is None or f.empty:
        return None
    g = f[(f["name"] == name) & (f["first_available_at"] <= asof)].sort_values("first_available_at")
    return g if not g.empty else None


def _yoy_pair(c):
    """(yoy_now, yoy_prev) via date lookback (~360d), robust to monthly OR quarterly CPI."""
    d = c["first_available_at"].reset_index(drop=True)
    v = c["actual"].astype(float).reset_index(drop=True)

    def at(target):
        sub = v[d <= target]
        return float(sub.iloc[-1]) if len(sub) else None
    if len(v) < 2:
        return None
    now_v, prev_v = float(v.iloc[-1]), float(v.iloc[-2])
    base_now = at(d.iloc[-1] - pd.Timedelta(days=360))
    base_prev = at(d.iloc[-2] - pd.Timedelta(days=360))
    if not base_now or not base_prev:
        return None
    return now_v / base_now - 1, prev_v / base_prev - 1


def foreign_components(ccy, asof, bundle):
    """Policy-rate path (hiking = currency-bullish) + CPI acceleration (hawkish = bullish).
    Reads the harvested non-US FRED series; any missing series is just excluded."""
    spec = FOREIGN_MACRO.get(ccy)
    if not spec:
        return []
    rate_name, cpi_name = spec
    out = []
    g = _named_rows(bundle, rate_name, asof)
    if g is not None and len(g) >= 2:
        av = g["first_available_at"].iloc[-1]; age = (asof - av).days
        last = float(g["actual"].iloc[-1]); prev = float(g["actual"].iloc[max(0, len(g) - 4)])
        arrow = _dir(last - prev, 1e-9); used = age <= MAX_AGE["fred_monthly"]
        out.append(_comp(f"{ccy} rate path", arrow,
                         f"policy rate {last:.2f}% ({'hiking' if arrow=='↑' else 'cutting' if arrow=='↓' else 'hold'})",
                         av, used, "" if used else f"stale {age}d",
                         vote=(1 if arrow == "↑" else -1 if arrow == "↓" else 0) if used else 0))
    c = _named_rows(bundle, cpi_name, asof)
    yy = _yoy_pair(c) if c is not None else None
    if yy is not None:
        av = c["first_available_at"].iloc[-1]; age = (asof - av).days
        yoy_now, yoy_prev = yy
        arrow = _dir(yoy_now - yoy_prev, 1e-6); used = age <= MAX_AGE["fred_quarterly"]
        out.append(_comp(f"{ccy} inflation", arrow,
                         f"CPI {yoy_now*100:.1f}% yoy ({'accelerating' if arrow=='↑' else 'cooling' if arrow=='↓' else 'flat'})",
                         av, used, "" if used else f"stale {age}d",
                         vote=(1 if arrow == "↑" else -1 if arrow == "↓" else 0) if used else 0))
    return out


# ----------------------------- per-currency direction -----------------------------
def currency_components(ccy, asof, bundle, mkt):
    """Reachable fundamental components for one currency (vote = + bullish that currency):
    the market-based leg where one exists, plus non-US policy-rate / CPI legs from the
    harvested FRED archive (foreign_components)."""
    ccy = ccy.upper()
    if ccy == "USD":
        return us_components(asof, bundle, mkt)
    comps = []
    if ccy == "JPY":
        t = series_trend(mkt.get("us10y"), 60, 0.0)
        if t:
            arrow, pct, ld, age = t; used = age <= MAX_AGE["market"]
            # higher US yields -> carry -> JPY weaker (vote -1 for JPY when yields rising)
            comps.append(_comp("JPY (US yields/risk)", "↓" if arrow == "↑" else "↑" if arrow == "↓" else "→",
                               f"US 10y {'rising' if arrow=='↑' else 'falling' if arrow=='↓' else 'flat'} ({pct:+.1f}% 60d) -> JPY {'pressured' if arrow=='↑' else 'supported' if arrow=='↓' else 'neutral'}",
                               ld, used, "" if used else f"stale {age}d", vote=(-1 if arrow == "↑" else 1 if arrow == "↓" else 0) if used else 0))
    elif ccy == "AUD":
        t = series_trend(mkt.get("gold"), 60, 1.0)
        if t:
            arrow, pct, ld, age = t; used = age <= MAX_AGE["market"]
            comps.append(_comp("AUD terms-of-trade (gold)", arrow, f"gold {pct:+.1f}% 60d", ld, used,
                               "" if used else f"stale {age}d", vote=(1 if arrow == "↑" else -1 if arrow == "↓" else 0) if used else 0))
    elif ccy == "CAD":
        t = series_trend(mkt.get("oil"), 60, 1.0)
        if t:
            arrow, pct, ld, age = t; used = age <= MAX_AGE["market"]
            comps.append(_comp("CAD terms-of-trade (oil)", arrow, f"oil {pct:+.1f}% 60d", ld, used,
                               "" if used else f"stale {age}d", vote=(1 if arrow == "↑" else -1 if arrow == "↓" else 0) if used else 0))
    comps += foreign_components(ccy, asof, bundle)
    if not comps:
        comps = [_comp(f"{ccy} rate path / inflation", "→", "central-bank data", "", False, "no reachable free source")]
    return comps


# ----------------------------- bias assembly -----------------------------
def _bias_from(components):
    used = [c for c in components if c["used"]]
    net = sum(c["vote"] for c in used)
    if len(used) < 2:
        return "NEUTRAL", "insufficient data", net, used
    conv = abs(net) / len(used)
    if net == 0:
        return "NEUTRAL", "mixed", net, used
    bias = "BULLISH" if net > 0 else "BEARISH"
    strength = "strong" if (conv >= 0.75 and len(used) >= 3) else "moderate" if conv >= 0.5 else "weak"
    return bias, strength, net, used


def _fx_trend(asset, asof, bundle, mkt):
    base, quote = asset[:3].upper(), asset[3:6].upper()
    bcomp = currency_components(base, asof, bundle, mkt)
    qcomp = currency_components(quote, asof, bundle, mkt)
    for c in bcomp: c["name"] = f"{base}: {c['name']}"
    for c in qcomp: c["name"] = f"{quote}: {c['name']}"
    bnet = sum(c["vote"] for c in bcomp if c["used"]); qnet = sum(c["vote"] for c in qcomp if c["used"])
    bused = [c for c in bcomp if c["used"]]; qused = [c for c in qcomp if c["used"]]
    pair_score = bnet - qnet                       # base strength minus quote strength
    comps = bcomp + qcomp
    used_n = len(bused) + len(qused)
    if used_n < 2:
        bias, strength = "NEUTRAL", "insufficient data"
    else:
        conv = abs(pair_score) / used_n
        bias = "NEUTRAL" if pair_score == 0 else ("BULLISH" if pair_score > 0 else "BEARISH")
        strength = ("insufficient data" if bias == "NEUTRAL" and used_n < 2
                    else "strong" if conv >= 0.75 and used_n >= 3 else "moderate" if conv >= 0.5 else "weak")
    bdir = "bullish" if bnet > 0 else "bearish" if bnet < 0 else ("neutral" if bused else "excluded")
    qdir = "bullish" if qnet > 0 else "bearish" if qnet < 0 else ("neutral" if qused else "excluded")
    logic = f"{base} {bdir} vs {quote} {qdir} -> {asset} {bias.lower()}"
    driver = "; ".join(f"{c['name']} {c['dir']}" for c in (bused + qused)[:3]) or "no reachable drivers"
    return bias, strength, comps, logic, driver


def _metal_trend(asset, asof, bundle, mkt):
    comps = []
    ry = real_yield_trend(asof, bundle, mkt)
    if ry["used"]:
        ry = dict(ry); ry["vote"] = -ry["vote"]; ry["detail"] += " (inverse for gold)"   # rising real yield -> gold bearish
    comps.append(ry)
    dxy = series_trend(mkt.get("dxy"), 60, 0.5)
    if dxy:
        arrow, pct, ld, age = dxy; used = age <= MAX_AGE["market"]
        comps.append(_comp("DXY (inverse)", "↓" if arrow == "↑" else "↑" if arrow == "↓" else "→",
                           f"DXY {pct:+.1f}% 60d -> metals {'headwind' if arrow=='↑' else 'tailwind' if arrow=='↓' else 'neutral'}",
                           ld, used, "" if used else f"stale {age}d", vote=(-1 if arrow == "↑" else 1 if arrow == "↓" else 0) if used else 0))
    if asset.upper().startswith("XAG"):
        g = mkt.get("gold"); s = mkt.get("silver")
        if g is not None and s is not None and not g.empty and not s.empty and len(g) > 60 and len(s) > 60:
            ratio_now = float(g["Close"].iloc[-1]) / float(s["Close"].iloc[-1])
            ratio_old = float(g["Close"].iloc[-60]) / float(s["Close"].iloc[-60])
            arrow = _dir(ratio_now - ratio_old, 0.0)   # ratio falling = silver outperforming = XAG bullish
            comps.append(_comp("Gold/Silver ratio", "↑" if arrow == "↓" else "↓" if arrow == "↑" else "→",
                               f"G/S {ratio_now:.1f} ({'silver outperforming' if arrow=='↓' else 'silver lagging' if arrow=='↑' else 'flat'})",
                               str(s.index[-1])[:10], True, "", vote=(1 if arrow == "↓" else -1 if arrow == "↑" else 0)))
        comps.append(_comp("Industrial demand", "→", "proxy", "", False, "no reachable free source"))
    bias, strength, net, used = _bias_from(comps)
    logic = f"real yield {'rising' if any(c['name']=='US real yield' and c['dir']=='↑' for c in used) else 'falling' if any(c['name']=='US real yield' and c['dir']=='↓' for c in used) else '—'} + DXY -> {asset} {bias.lower()}"
    driver = "; ".join(f"{c['name']} {c['dir']}" for c in used[:3]) or "no reachable drivers"
    return bias, strength, comps, logic, driver


def _crack_trend(mkt, lookback=60, deadband_pct=3.0):
    """RBOB gasoline crack (42*RB - CL, $/bbl) direction over `lookback` days. A rising crack =
    stronger refining margin / product demand -> refiners pull more crude -> bullish. This is a
    price-derived MARGIN signal (RB relative to CL), not the absolute oil price, so it is not a
    restatement of the chart's own trend. Staleness-capped. Returns (arrow, pct, last_date, age,
    used) or None if RB=F / CL=F are not both reachable (then the driver is EXCLUDED, never faked)."""
    rb = mkt.get("gasoline"); cl = mkt.get("oil")
    if rb is None or cl is None or getattr(rb, "empty", True) or getattr(cl, "empty", True):
        return None
    j = pd.concat([rb["Close"].rename("rb"), cl["Close"].rename("cl")], axis=1).dropna()
    if len(j) < 5:
        return None
    crack = 42.0 * j["rb"].astype(float) - j["cl"].astype(float)    # RB $/gal -> $/bbl; CL $/bbl
    last = float(crack.iloc[-1]); ref = float(crack.iloc[-min(lookback, len(crack))])
    pct = (last / ref - 1.0) * 100 if ref else 0.0
    last_date = pd.Timestamp(j.index[-1])
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    age = (now - (last_date.tz_convert("UTC").tz_localize(None) if last_date.tzinfo else last_date)).total_seconds() / 86400
    return (_dir(pct, deadband_pct), round(pct, 2), str(last_date)[:10], round(age, 1), age <= MAX_AGE["market"])


def _oil_trend(asset, asof, bundle, mkt):
    comps = []
    # (1) EIA weekly crude inventory surprise — a draw (surprise < 0) = bullish, a build = bearish.
    eia = bundle.get("eia")
    eia = eia[(eia["name"] == "CrudeInventories") & (eia["first_available_at"] <= asof)].sort_values("first_available_at") if eia is not None and not eia.empty else None
    if eia is not None and not eia.empty:
        r = eia.iloc[-1]; av = r["first_available_at"]; age = (asof - av).days
        surp = r.get("surprise")
        used = age <= 14 and pd.notna(surp)
        draw = (float(surp) < 0) if pd.notna(surp) else None
        arrow = "↑" if draw else "↓" if draw is False else "→"
        comps.append(_comp("EIA crude inventory", arrow,
                           f"w/w {'draw' if draw else 'build' if draw is False else 'n/a'} {('%+.0f kb'%float(surp)) if pd.notna(surp) else ''} ({'bullish' if draw else 'bearish' if draw is False else '—'})",
                           av, used, "" if used else (f"stale {age}d" if pd.notna(surp) else "no surprise"),
                           vote=(1 if draw else -1 if draw is False else 0) if used else 0))
    # (2) DXY, inverse — a stronger dollar prices crude higher for the rest of the world -> bearish.
    dxy = series_trend(mkt.get("dxy"), 60, 0.5)
    if dxy:
        arrow, pct, ld, age = dxy; used = age <= MAX_AGE["market"]
        comps.append(_comp("DXY (inverse)", "↓" if arrow == "↑" else "↑" if arrow == "↓" else "→",
                           f"DXY {pct:+.1f}% 60d", ld, used, "" if used else f"stale {age}d",
                           vote=(-1 if arrow == "↑" else 1 if arrow == "↓" else 0) if used else 0))
    # (3) US real yield, inverse — rising real yields tighten financial conditions and dampen oil
    #     demand expectations -> bearish. Reuses the shared real-yield leg, inverted (same idiom as
    #     _equity_index_trend). Carries its own available_at / used flag.
    ry = next((c for c in us_components(asof, bundle, mkt) if c["name"] == "US real yield"), None)
    if ry is not None:
        inv = dict(ry)
        inv["name"] = "US real yield (demand, inverse)"
        inv["dir"] = "↓" if ry["dir"] == "↑" else "↑" if ry["dir"] == "↓" else "→"
        inv["detail"] = ry["detail"] + (" -> tighter = oil-demand headwind" if ry["dir"] == "↑"
                                        else " -> easier = oil-demand tailwind" if ry["dir"] == "↓" else "")
        inv["vote"] = -ry.get("vote", 0)
        comps.append(inv)
    # (4) RBOB gasoline crack — refining margin / product demand. Rising crack = bullish for crude.
    crack = _crack_trend(mkt)
    if crack is not None:
        arrow, pct, ld, age, used = crack
        comps.append(_comp("Gasoline crack (demand)", arrow,
                           f"RBOB crack {pct:+.1f}% 60d ({'margins up = demand' if arrow=='↑' else 'margins down' if arrow=='↓' else 'flat'})",
                           ld, used, "" if used else f"stale {age}d",
                           vote=(1 if arrow == "↑" else -1 if arrow == "↓" else 0) if used else 0))
    else:
        comps.append(_comp("Gasoline crack (demand)", "→", "RBOB/crude margin", "", False, "no reachable free source"))
    # (5) supply policy — still no free source (the dominant oil driver, honestly excluded).
    comps.append(_comp("OPEC+ / refinery / geopolitics", "→", "supply stance", "", False, "no reachable free source"))
    bias, strength, net, used = _bias_from(comps)
    driver = "; ".join(f"{c['name']} {c['dir']}" for c in used[:3]) or "no reachable drivers"
    return bias, strength, comps, f"inventories + USD + real-yield + crack -> {asset} {bias.lower()}", driver


def _crypto_trend(asset, asof, bundle, mkt):
    comps = []
    # rates + DXY -> risk (inverse): tighter Fed / stronger USD = crypto headwind
    us = us_components(asof, bundle, mkt)
    rate = next((c for c in us if c["name"] == "US rate path" and c["used"]), None)
    if rate:
        comps.append(_comp("US rates (risk, inverse)", "↓" if rate["dir"] == "↑" else "↑" if rate["dir"] == "↓" else "→",
                           f"Fed {'hiking -> headwind' if rate['dir']=='↑' else 'cutting -> tailwind' if rate['dir']=='↓' else 'hold'}",
                           rate["available_at"], True, "", vote=(-1 if rate["dir"] == "↑" else 1 if rate["dir"] == "↓" else 0)))
    dxy = series_trend(mkt.get("dxy"), 60, 0.5)
    if dxy:
        arrow, pct, ld, age = dxy; used = age <= MAX_AGE["market"]
        comps.append(_comp("DXY (risk, inverse)", "↓" if arrow == "↑" else "↑" if arrow == "↓" else "→",
                           f"DXY {pct:+.1f}% 60d", ld, used, "" if used else f"stale {age}d",
                           vote=(-1 if arrow == "↑" else 1 if arrow == "↓" else 0) if used else 0))
    # per-coin funding (extreme = contrarian)
    fund = bundle.get("funding", {}).get(asset.upper())
    if fund is not None and not fund.empty:
        f = fund[fund["time"] <= asof]
        if not f.empty:
            r = f.sort_values("time").iloc[-1]; av = r["time"]; age = (asof - av).total_seconds() / 86400
            rate_v = float(r["funding"]); used = age <= MAX_AGE["funding"]
            # extreme positive funding = crowded longs = bearish tilt; extreme negative = bullish
            extreme = abs(rate_v) > 0.0005
            vote = (-1 if rate_v > 0 else 1) if (extreme and used) else 0
            comps.append(_comp("Funding (contrarian)", "↓" if rate_v > 0.0005 else "↑" if rate_v < -0.0005 else "→",
                               f"{rate_v:+.4f} ({'crowded longs -> bearish tilt' if rate_v>0.0005 else 'crowded shorts -> bullish tilt' if rate_v<-0.0005 else 'neutral'})",
                               av, used, "" if used else f"stale {age:.0f}d", vote=vote))
    # AV sentiment with 7-day staleness -> EXCLUDE when stale (the XRP 825d bug)
    sent = bundle.get("sent")
    if sent is not None and not sent.empty:
        s = sent.copy(); s["avail"] = s["date"] + pd.Timedelta(days=1)
        s = s[(s["instrument_class"] == "crypto") & (s["avail"] <= asof)]
        if not s.empty:
            r = s.sort_values("avail").iloc[-1]; av = r["avail"]; age = (asof - av).total_seconds() / 86400
            used = age <= MAX_AGE["sentiment"]; val = float(r["sent_wmean"])
            comps.append(_comp("News sentiment", "↑" if val > 0.05 else "↓" if val < -0.05 else "→",
                               f"{val:+.3f}", av, used, "" if used else f"stale {age:.0f}d",
                               vote=(1 if val > 0.05 else -1 if val < -0.05 else 0) if used else 0))
    comps.append(_comp("ETF flows / asset-specific", "→", "regulatory/flows", "", False, "no reachable free source"))
    bias, strength, net, used = _bias_from(comps)
    driver = "; ".join(f"{c['name']} {c['dir']}" for c in used[:3]) or "no reachable drivers"
    return bias, strength, comps, f"rates/USD + funding{' + sentiment' if any(c['name']=='News sentiment' and c['used'] for c in comps) else ''} -> {asset} {bias.lower()}", driver


def _usd_index_trend(asset, asof, bundle, mkt):
    """DXY / USD-index: its fundamentals ARE the USD drivers (vote +1 = USD-bullish = index up)."""
    comps = us_components(asof, bundle, mkt)
    bias, strength, net, used = _bias_from(comps)
    driver = "; ".join(f"{c['name']} {c['dir']}" for c in used[:3]) or "no reachable drivers"
    return bias, strength, comps, f"USD macro drivers -> {asset} {bias.lower()}", driver


def _equity_index_trend(asset, asof, bundle, mkt):
    """Equity index MACRO BACKDROP only (free data): US rates + real yield (both inverse for
    growth equities) + USD risk (inverse). Earnings/valuation have no reachable free source."""
    comps = []
    us = us_components(asof, bundle, mkt)
    rate = next((c for c in us if c["name"] == "US rate path"), None)
    if rate is not None:
        inv = dict(rate)
        inv["name"] = "US rates (equities, inverse)"
        inv["dir"] = "↓" if rate["dir"] == "↑" else "↑" if rate["dir"] == "↓" else "→"
        inv["detail"] = ("Fed hiking -> headwind" if rate["dir"] == "↑"
                         else "Fed cutting -> tailwind" if rate["dir"] == "↓" else "Fed on hold")
        inv["vote"] = -rate.get("vote", 0)
        comps.append(inv)
    ry = next((c for c in us if c["name"] == "US real yield"), None)
    if ry is not None and ry.get("used"):
        inv = dict(ry)
        inv["name"] = "US real yield (equities, inverse)"
        inv["dir"] = "↓" if ry["dir"] == "↑" else "↑" if ry["dir"] == "↓" else "→"
        inv["detail"] = ry["detail"] + " (inverse for equities)"
        inv["vote"] = -ry.get("vote", 0)
        comps.append(inv)
    dxy = series_trend(mkt.get("dxy"), 60, 0.5)
    if dxy:
        arrow, pct, ld, age = dxy
        used = age <= MAX_AGE["market"]
        comps.append(_comp("DXY (risk, inverse)", "↓" if arrow == "↑" else "↑" if arrow == "↓" else "→",
                           f"DXY {pct:+.1f}% 60d -> equities {'headwind' if arrow=='↑' else 'tailwind' if arrow=='↓' else 'neutral'}",
                           ld, used, "" if used else f"stale {age}d",
                           vote=(-1 if arrow == "↑" else 1 if arrow == "↓" else 0) if used else 0))
    comps.append(_comp("Earnings / valuation", "→", "equity-specific", "", False, "no reachable free source"))
    bias, strength, net, used = _bias_from(comps)
    driver = "; ".join(f"{c['name']} {c['dir']}" for c in used[:3]) or "no reachable drivers"
    return bias, strength, comps, f"US rates/real-yield + USD (macro backdrop, not earnings) -> {asset} {bias.lower()}", driver


# ----------------------------- public entry -----------------------------
def market_data(fetch_ohlcv) -> dict:
    """Fetch the reachable Yahoo macro series once per board run (shared across all cards)."""
    out = {}
    for key, tk in MKT_TICKERS.items():
        try:
            out[key] = fetch_ohlcv(tk, "1d", "6mo")
        except Exception:
            out[key] = None
    return out


def fundamental_trend(asset: str, asof, bundle: dict | None = None, mkt: dict | None = None) -> dict:
    """Per-asset fundamental trend object (display-only). asof tz-naive UTC."""
    if bundle is None:
        bundle = FUND.load_bundle()
    if mkt is None:
        mkt = {}
    asof = pd.Timestamp(asof)
    if asof.tzinfo is not None:
        asof = asof.tz_convert("UTC").tz_localize(None)
    a = asset.upper(); aclass = FUND.class_of(a)
    if aclass == "crypto":
        bias, strength, comps, logic, driver = _crypto_trend(a, asof, bundle, mkt)
    elif aclass == "oil":
        bias, strength, comps, logic, driver = _oil_trend(a, asof, bundle, mkt)
    elif a.startswith(("XAU", "XAG")):
        bias, strength, comps, logic, driver = _metal_trend(a, asof, bundle, mkt)
    elif _is_usd_index(a):
        bias, strength, comps, logic, driver = _usd_index_trend(a, asof, bundle, mkt)
    elif _is_equity_index(a):
        bias, strength, comps, logic, driver = _equity_index_trend(a, asof, bundle, mkt)
    elif len(a) >= 6 and a[:3] in FX_CCYS and a[3:6] in FX_CCYS:
        bias, strength, comps, logic, driver = _fx_trend(a, asof, bundle, mkt)
    else:
        comps = [_comp("fundamentals", "→", "unmapped instrument", "", False, "no mapping")]
        bias, strength, logic, driver = "NEUTRAL", "insufficient data", "unmapped", "n/a"
    used = [c for c in comps if c["used"]]
    excluded = [{"name": c["name"], "reason": c["reason"] or "stale/unavailable"} for c in comps if not c["used"]]
    return {"label": LABEL, "asof": str(asof), "asset_class": aclass, "bias": bias, "strength": strength,
            "driver": driver, "logic": logic,
            "components": [{k: c[k] for k in ("name", "dir", "detail", "available_at", "used")} for c in comps],
            "used_count": len(used), "excluded": excluded}
