"""Multiple-testing correction + robustness statistics (portable, stdlib-only math).

When you test N hypotheses and keep the best, the winner's in-sample performance is inflated by
selection alone. T-303 deflates for that. Two independent gates, both must pass:

1. **Bonferroni** (family-wise error): with N hypotheses and target family-wise alpha, a single
   hypothesis is significant only if its one-sided p-value < alpha / N. Blunt but assumption-light.

2. **Deflated Sharpe Ratio** (Bailey & Lopez de Prado, 2014): the probability the strategy's true
   Sharpe exceeds the *expected maximum Sharpe produced by N trials under the null*, correcting for
   non-normal (skewed / fat-tailed) returns and the number of trials. Significant if DSR > ~0.95.

All Phi / inverse-Phi via statistics.NormalDist (no scipy). p-values use the normal approximation
to the t-distribution, which is accurate at the n>=100-trade sample sizes this project gates on.
"""
from __future__ import annotations

import math
from statistics import NormalDist

_N = NormalDist()
EULER_MASCHERONI = 0.5772156649015329


def phi(x: float) -> float:
    """Standard-normal CDF."""
    return _N.cdf(x)


def inv_phi(p: float) -> float:
    """Standard-normal inverse CDF, guarded away from the open-interval endpoints."""
    p = min(max(p, 1e-12), 1 - 1e-12)
    return _N.inv_cdf(p)


def p_value_one_sided(sharpe_per_trade: float, n: int) -> float:
    """One-sided p-value for H0: mean R <= 0 vs H1: mean R > 0.

    With a per-trade Sharpe = mean(R)/std(R), the t-statistic is sharpe * sqrt(n); for n>=100 the
    t-distribution is well approximated by the normal, so p = 1 - Phi(sharpe * sqrt(n)).
    """
    if n is None or n < 2 or sharpe_per_trade is None or not math.isfinite(sharpe_per_trade):
        return float("nan")
    t = sharpe_per_trade * math.sqrt(n)
    return 1.0 - phi(t)


def bonferroni_alpha(n_trials: int, family_alpha: float = 0.05) -> float:
    """Per-hypothesis significance threshold controlling family-wise error at `family_alpha`."""
    n_trials = max(int(n_trials), 1)
    return family_alpha / n_trials


def expected_max_sharpe(var_trials: float, n_trials: int) -> float:
    """Expected MAX of N independent trial Sharpes under the null (all true Sharpe = 0).

    SR* = sqrt(Var) * [ (1 - g) * Phi^-1(1 - 1/N) + g * Phi^-1(1 - 1/(N*e)) ],  g = Euler-Mascheroni.
    Returns 0.0 when it cannot be formed (N<2 or non-positive variance) — i.e. no deflation benchmark.
    """
    if n_trials is None or n_trials < 2 or var_trials is None or not math.isfinite(var_trials) or var_trials <= 0:
        return 0.0
    g = EULER_MASCHERONI
    a = inv_phi(1.0 - 1.0 / n_trials)
    b = inv_phi(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(var_trials) * ((1.0 - g) * a + g * b)


def deflated_sharpe(sr_hat: float, sr_star: float, n_obs: int, skew: float, kurt_pearson: float) -> float:
    """Deflated Sharpe Ratio = P(true Sharpe > SR*) given N trials and non-normal returns.

    DSR = Phi( (SR_hat - SR*) * sqrt(T - 1) / sqrt(1 - skew*SR_hat + ((kurt - 1)/4) * SR_hat^2) )
    sr_hat / sr_star are per-observation Sharpes; T = number of trades; kurt is Pearson (normal = 3).
    Returns nan if inputs are unusable or the variance term is non-positive.
    """
    if (n_obs is None or n_obs < 2 or sr_hat is None or not math.isfinite(sr_hat)
            or not math.isfinite(sr_star)):
        return float("nan")
    if skew is None or not math.isfinite(skew):
        skew = 0.0
    if kurt_pearson is None or not math.isfinite(kurt_pearson):
        kurt_pearson = 3.0
    denom_sq = 1.0 - skew * sr_hat + ((kurt_pearson - 1.0) / 4.0) * sr_hat * sr_hat
    if denom_sq <= 0:
        return float("nan")
    z = (sr_hat - sr_star) * math.sqrt(n_obs - 1) / math.sqrt(denom_sq)
    return phi(z)
