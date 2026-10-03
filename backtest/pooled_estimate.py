"""Track C — partial-pooling estimator for the fundamentals shadow effect.

Per-cell samples (crypto n~12, macro n~53 on the backtest) are too thin to judge a fundamental use on
their own. But a real effect that is WEAK in each cell yet CONSISTENT in direction across cells is
detectable by pooling. This runs a DerSimonian-Laird random-effects meta-analysis across cells
(asset classes) for each shadow use and reports BOTH the per-cell estimates AND the pooled estimate
with a 95% CI, between-cell heterogeneity (tau^2, I^2), and Q.

Shadow effects measured (from the forward/backtest log):
  - gate : E[R | gate KEEPS] - E[R | gate BLOCKS]   (does blocking remove worse-than-average trades?)
  - score: OLS slope of R on score_delta            (does a higher fundamental score predict higher R?)

GUARDRAIL (D-034): below pooled n=200 this prints descriptive numbers only and makes NO verdict; at
n>=200 it applies a Bonferroni correction across the uses tested and may report significance; the
augmented-vs-baseline backtest itself is not run until n>=200. Consumes forward_test/signals.csv (+
shadow.csv). Honest by construction: with no resolved signals yet it says so and stops.

Usage:  python backtest/pooled_estimate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FT = ROOT / "forward_test"
N_SIGNIF = 200                 # D-034: no verdict below this pooled resolved-n


def load() -> pd.DataFrame:
    sp, hp = FT / "signals.csv", FT / "shadow.csv"
    if not sp.exists():
        return pd.DataFrame()
    s = pd.read_csv(sp)
    s["R"] = pd.to_numeric(s.get("R"), errors="coerce")
    s = s.dropna(subset=["R"])                       # resolved only
    if hp.exists():
        h = pd.read_csv(hp)
        s = s.merge(h[["signal_id", "gate_pass", "score_delta"]], on="signal_id", how="left")
    return s


def dl_pool(y: np.ndarray, v: np.ndarray) -> dict:
    """DerSimonian-Laird random-effects pool of effects y with variances v (se^2)."""
    k = len(y)
    if k == 0:
        return dict(k=0)
    w = 1.0 / v
    yf = float(np.sum(w * y) / np.sum(w))
    Q = float(np.sum(w * (y - yf) ** 2))
    dfree = k - 1
    C = float(np.sum(w) - np.sum(w ** 2) / np.sum(w)) if np.sum(w) > 0 else 0.0
    tau2 = max(0.0, (Q - dfree) / C) if C > 0 and k > 1 else 0.0
    ws = 1.0 / (v + tau2)
    pooled = float(np.sum(ws * y) / np.sum(ws))
    se = float(np.sqrt(1.0 / np.sum(ws)))
    I2 = max(0.0, (Q - dfree) / Q) * 100 if Q > 0 and k > 1 else 0.0
    z = pooled / se if se > 0 else np.nan
    return dict(k=k, pooled=pooled, se=se, lo=pooled - 1.96 * se, hi=pooled + 1.96 * se,
                tau2=tau2, I2=I2, Q=Q, z=z)


def gate_cells(df: pd.DataFrame):
    """Per class: mean R kept minus mean R blocked (+ SE of the difference)."""
    out = []
    if "gate_pass" not in df:
        return out
    gp = df["gate_pass"].astype(str).str.lower().isin(("true", "1"))
    for cls, g in df.assign(_keep=gp).groupby("asset_class"):
        a = g[g["_keep"]]["R"].to_numpy(); b = g[~g["_keep"]]["R"].to_numpy()
        if len(a) < 2 or len(b) < 2:
            continue
        diff = float(a.mean() - b.mean())
        se = float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
        if se > 0:
            out.append((cls, diff, se, len(a), len(b)))
    return out


def score_cells(df: pd.DataFrame):
    """Per class: OLS slope of R on score_delta (+ SE)."""
    out = []
    if "score_delta" not in df:
        return out
    for cls, g in df.groupby("asset_class"):
        x = pd.to_numeric(g["score_delta"], errors="coerce").to_numpy()
        y = g["R"].to_numpy()
        m = np.isfinite(x) & np.isfinite(y)
        x, y = x[m], y[m]
        if len(x) < 5 or np.ptp(x) == 0:
            continue
        X = np.vstack([np.ones_like(x), x]).T
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        s2 = float(resid @ resid) / max(len(x) - 2, 1)
        xc = x - x.mean(); sxx = float(xc @ xc)
        se = float(np.sqrt(s2 / sxx)) if sxx > 0 else np.nan
        if np.isfinite(se) and se > 0:
            out.append((cls, float(beta[1]), se, len(x), None))
    return out


def _emit(name, cells, n_total, lines):
    lines.append(f"\n### {name}")
    if not cells:
        lines.append("_no cell had enough data to estimate an effect._"); return
    lines.append("| cell | effect | se | n+ | n- |")
    lines.append("|---|--:|--:|--:|--:|")
    for c, e, se, na, nb in cells:
        lines.append(f"| {c} | {e:+.3f} | {se:.3f} | {na} | {'' if nb is None else nb} |")
    pool = dl_pool(np.array([c[1] for c in cells]), np.array([c[2] ** 2 for c in cells]))
    if pool["k"] >= 1:
        verdict = ("BELOW n=200 — descriptive only, NO verdict (D-034)" if n_total < N_SIGNIF
                   else f"z={pool['z']:+.2f} (Bonferroni /{2} => |z|>2.24 ~ p<0.025 to flag)")
        lines.append(f"\n**Pooled (random-effects):** {pool['pooled']:+.3f} "
                     f"[95% CI {pool['lo']:+.3f}, {pool['hi']:+.3f}], "
                     f"tau^2={pool['tau2']:.3f}, I^2={pool['I2']:.0f}%, k={pool['k']} cells. {verdict}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    df = load()
    n = len(df)
    lines = ["# Pooled fundamentals-effect estimate (Track C)", "",
             f"Resolved signals in log: **{n}** (significance gate n>={N_SIGNIF}; D-034)."]
    if n == 0:
        lines.append("\n_No resolved signals yet — nothing to pool. The forward shadow test is "
                     "accumulating; this estimator runs automatically as the log fills._")
        print("\n".join(lines)); (FT / "POOLED.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 0
    if n < N_SIGNIF:
        lines.append(f"\n> **No verdict** — below the n={N_SIGNIF} significance gate. Numbers below are "
                     "descriptive, to watch direction/consistency, not to act on.")
    _emit("Gate effect — E[R|keep] − E[R|block]", gate_cells(df), n, lines)
    _emit("Score effect — slope of R on score_delta", score_cells(df), n, lines)
    out = "\n".join(lines) + "\n"
    (FT / "POOLED.md").write_text(out, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
