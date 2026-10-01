"""Realistic, conservative per-asset-class cost model (net-of-cost is mandatory).

All performance is NET of: spread + commission + slippage (bundled into `rt`, a round-trip
fraction of entry price) and overnight financing/swap (`swap_daily`, per night held — applied
to swing trades only). These are deliberately conservative retail estimates, NOT zero.

Sensitivity: the backtest re-runs winners at 2x these costs (a real edge must survive).
"""
from __future__ import annotations

# rt = round-trip cost as a FRACTION of entry price (spread + commission + slippage).
# swap_daily = financing cost per overnight as a fraction of notional (applied per night, swing).
COSTS = {
    "forex_majors":  {"rt": 0.00015, "swap_daily": 0.00005},   # ~1.5bp rt, ~0.5bp/night
    "forex_crosses": {"rt": 0.00030, "swap_daily": 0.00010},
    "metals":        {"rt": 0.00030, "swap_daily": 0.00010},
    "oil":           {"rt": 0.00050, "swap_daily": 0.00015},
    "crypto":        {"rt": 0.00120, "swap_daily": 0.00030},    # ~12bp rt, funding-like
}
DEFAULT = {"rt": 0.00050, "swap_daily": 0.00015}


def get(asset_class: str, cost_mult: float = 1.0) -> dict:
    base = COSTS.get(asset_class, DEFAULT)
    return {"rt": base["rt"] * cost_mult, "swap_daily": base["swap_daily"] * cost_mult}
