"""Board data-health: freshness indicators + keyless crypto spot cross-check (fix/board-data-integrity).

Additive and read-only. Computed AFTER asset_state, so it never touches the signal path. Adds, per card:
  - fetched_at   : when this snapshot was generated (UTC)
  - bar_age_min  : minutes between `now` and the card's last bar (`updated`)
  - stale        : bar_age_min beyond a class-aware bound (crypto 4h; FX/metals/indices 65h to avoid
                   weekend false positives) -> flagged in the UI, not hidden
  - for crypto:    spot_price / spot_source / spot_age_min from CoinGecko (keyless fallback), and
                   stale_vs_spot when the yfinance bar is materially staler than live spot.
BTCUSD etc. thus have a reliable second, keyless source; when the primary bar is stale the UI prefers
the fresher spot for display (bars/levels/signals still come from yfinance, unchanged).
"""
from __future__ import annotations

import json
import urllib.request

import pandas as pd

# board asset -> CoinGecko id (keyless simple-price endpoint)
CG_ID = {"BTCUSD": "bitcoin", "ETHUSD": "ethereum", "DOGEUSD": "dogecoin", "SOLUSD": "solana",
         "XRPUSD": "ripple", "AVAXUSD": "avalanche-2", "ADAUSD": "cardano", "BNBUSD": "binancecoin",
         "LTCUSD": "litecoin", "LINKUSD": "chainlink", "DOTUSD": "polkadot", "ATOMUSD": "cosmos",
         "BCHUSD": "bitcoin-cash", "ETCUSD": "ethereum-classic", "TRXUSD": "tron", "UNIUSD": "uniswap",
         "XLMUSD": "stellar"}
STALE_MIN_CRYPTO = 240        # 4h: crypto trades 24/7
STALE_MIN_OTHER = 3900        # ~65h: covers the weekend FX/futures close without false positives
SPOT_STALE_MARGIN = 30        # bar considered stale-vs-spot if >=30 min staler than live spot
CG_URL = "https://api.coingecko.com/api/v3/simple/price"


def is_crypto(asset: str) -> bool:
    return asset.upper() in CG_ID


def stale_bound(asset: str) -> int:
    return STALE_MIN_CRYPTO if is_crypto(asset) else STALE_MIN_OTHER


def crypto_spots(assets) -> dict:
    """Batch CoinGecko simple price for the given crypto assets. {asset: (price, age_min)}. Keyless.
    Returns {} on any failure (never raises); callers degrade gracefully (no fabrication)."""
    ids = {CG_ID[a]: a for a in assets if a in CG_ID}
    if not ids:
        return {}
    url = f"{CG_URL}?ids={','.join(ids)}&vs_currencies=usd&include_last_updated_at=true"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "board-health"})
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as exc:  # noqa: BLE001
        print(f"health: CoinGecko spot unavailable ({exc}); crypto cards use yfinance bar only", flush=True)
        return {}
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    out = {}
    for cid, asset in ids.items():
        d = data.get(cid) or {}
        px = d.get("usd"); lu = d.get("last_updated_at")
        if px is None:
            continue
        age = ((now - pd.to_datetime(lu, unit="s", utc=True).tz_localize(None)).total_seconds() / 60
               if lu else None)
        out[asset] = (float(px), round(age, 1) if age is not None else None)
    return out


def attach_health(out: list, now: pd.Timestamp) -> None:
    """Annotate each card with freshness + (crypto) spot cross-check. Additive; fully guarded."""
    fetched = str(now)
    spots = crypto_spots([c.get("asset") for c in out if is_crypto(c.get("asset", ""))])
    for c in out:
        try:
            c["fetched_at"] = fetched
            if c.get("status") == "NODATA" or not c.get("updated"):
                c["bar_age_min"] = None; c["stale"] = True
                continue
            age = (now - pd.Timestamp(c["updated"])).total_seconds() / 60.0
            c["bar_age_min"] = round(age, 1)
            c["stale"] = bool(age > stale_bound(c["asset"]))
            if c["asset"] in spots:
                sp, sage = spots[c["asset"]]
                c["spot_price"] = round(sp, 6); c["spot_source"] = "CoinGecko"; c["spot_age_min"] = sage
                # bar is stale relative to live spot -> UI prefers the fresher spot for display
                c["stale_vs_spot"] = bool(sage is not None and age > (sage + SPOT_STALE_MARGIN))
                if c["stale_vs_spot"]:
                    c["stale"] = True
        except Exception as exc:  # noqa: BLE001
            print(f"{c.get('asset','?'):<8} health SKIP ({exc})", flush=True)
    n_stale = sum(1 for c in out if c.get("stale"))
    print(f"health: freshness attached to {len(out)} cards ({n_stale} stale); "
          f"crypto spot cross-check on {len(spots)}", flush=True)
