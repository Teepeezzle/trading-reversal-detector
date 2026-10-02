# DECISIONS — every judgment call, with the why

Append-only. Newest at top. Each entry: date · decision · why · reversible?

---

### 2026-10-02 · D-019 · Phase 6 verdict + PROGRAM conclusion: $0 idea space exhausted, 0 edges
Full cross-sectional sweep ran in CI on the widened lake: 320 configs → 25 base-gate PASS → T-303
`--phase 6` (N=132 valid tests, Bonferroni p<3.8e-4, SR*=0.36) → **0 candidates**. Best was crypto
15m momentum (Sharpe 0.078, p=0.22, DSR 0.002 — fat tails, kurtosis ~12, sink the DSR). **PROGRAM
RESULT:** across Phases 3–6, **~1,200 hypotheses** spanning every structurally-distinct approach —
per-instrument mean-reversion, breakout, momentum, trend-pullback, stochastic, MACD; regime-gated
combinations; and cross-sectional relative-strength — on free data (TD + yfinance, 15m–1D, widened
17-coin crypto + FX/metals/oil), net of cost and multiple-testing-corrected, produced **0 deployable
edges.** The honest conclusion: there is no robustly significant short-horizon technical edge
discoverable under the $0 / free-data constraints with this disciplined gauntlet. The remaining lever
is **data/budget** (D-003): deeper intraday history, a survivorship-aware universe, more instruments,
or alternative data — a decision for the user. The framework, the ~1,200-row registry, and this
null result are the deliverable. Holdout NEVER touched (still available for a genuine future
candidate). _Reversible: yes (a budget or new data source reopens the search)._

### 2026-10-02 · D-018 · Phase 6 = cross-sectional relative-strength (new engine, own MTC family)
Last structurally-new $0 idea (user-directed). New portable engine `src/xsectional.py`: each
rebalance, rank a class's instruments by trailing momentum (lookback L), hold long top-k (/ short
bottom-k, mode ls/lo) for H bars, **non-overlapping** periods so observations are ~independent.
No-lookahead (rank@t, enter t+1 open, exit t+1+H open); net of one round-trip + overnight-swap per
period; benchmarks = equal-weight buy-hold + random-pick control (same k/H). One rebalance period =
one observation, so `bt.stats`/split and the `mtc.py` gauntlet apply unchanged. `jobs/xs_sweep.py`
grids class × TF(15m/1h/4h/1D) × (L,H) × k × mode → **phase-6** rows; `robustness.py --phase 6`
re-evaluates xs rows through the engine (2× cost + L/H sensitivity + Bonferroni + DSR), its own MTC
family. Classes with <3 instruments (metals, oil on free data) auto-skip. Validated locally end-to-end
(engine + judge, incl. a forced-PASS gauntlet). Local 9-coin crypto = weak/marginal (tiny Sharpe,
fat tails). Real run = CI on the widened 17-coin lake. _Reversible: yes._

### 2026-10-02 · D-017 · Phase 5 verdict: new factor families also yield 0 candidates
Full phase-5 sweep ran in CI on the widened lake: 540 hypotheses (5 families × 6 TFs × 5 classes ×
2 horizons) → 58 base-gate PASS → T-303 `--phase 5` (N=288 valid tests, Bonferroni p<1.74e-4, SR*=0.42)
→ **0 candidates**. Best survivor-of-2×-cost was `bb_breakout` FX 4h swing (Sharpe 0.10, p=0.11) —
nowhere near the bar. **Cumulative: ~880 hypotheses across Phases 3–5, 0 deployable edges.** The
single-factor space we can express on free data (mean-reversion, breakout, momentum, pullback,
stochastic, MACD; gated and ungated; 15m–1D; pooled + widened universe) is **exhausted** and
contains no robustly significant, cost-surviving, multiple-testing-corrected short-horizon edge.
Two levers remain, both the user's call: (a) **cross-sectional ranking** (relative strength across
instruments — structurally different, per-instrument rules can't capture it; needs a cross-instrument
engine change, T-404); (b) **reconsider the $0 data constraint** (D-003) — shallow 15m (~52d), a
~17-coin / limited-FX universe, and no survivorship correction are the likely binding limiters.
Holdout STILL never touched. _Reversible: yes._

### 2026-10-02 · D-016 · Phase 5 = new factor families across 15m/1h/2h/3h/4h/1D (user-directed)
Breakout/mean-reversion exhausted → open a fresh single-factor search over families NOT yet tested:
momentum ignition (`roc_mom`), volatility breakout (`bb_breakout`, Bollinger — distinct from
Donchian), trend-pullback (`ema_pullback`), stochastic reversal (`stoch_rev`), MACD momentum
(`macd_mom`). Added to `factors.RULES`; new sweep `jobs/family_sweep.py` + `research-family-sweep`
workflow; tagged **phase 5** (its own MTC family, judged by `robustness.py --phase 5`). Timeframes =
15m/1h/2h/3h/4h/1D at the user's request — **2h and 3h are RESAMPLED from 1h** in `factors.load`
(bar-open label='left', no-lookahead); this re-includes 15m despite D-005 (user override; the ~52d
15m depth caveat still stands). Param-name collision fixed (`bb_breakout.kstd`, `stoch_rev.klen`) so
the sensitivity sweep perturbs the right param; STEP map extended. CAVEAT carried: 2h/3h are highly
correlated with 1h and six TFs multiply the trial count — both HARDEN the multiple-testing bar, so a
survivor must be strong AND hold across a broad cross-section (the test that killed the last lead).
_Reversible: yes._

### 2026-10-02 · D-015 · Widened crypto universe DESTROYS the 15m breakout edge — it was small-sample luck
Move 3 executed: crypto universe 9→17 (MATIC 404 on TD free — POL rebrand; logged, skipped), fetched
in CI, re-ran `research-power-boost` on the bigger pool. Result is decisive and NEGATIVE: the
near-miss collapsed. `donch_brk(20)` & `vol_hi` 15m — Sharpe **0.281→0.160**, 2× cost **+0.242→+0.050R**,
**DSR 0.895→0.433**; even the 1h baseline Sharpe halved (0.18→0.09). Adding 8 coins is effectively a
cross-sectional out-of-sample test, and the edge regressed hard toward zero. **Conclusion: the
regime-gated crypto breakout is NOT a robust edge — the 9-coin result was selection/small-sample
inflation.** The discipline worked exactly as designed: widening the sample exposed a mirage before
any deployment. No candidate. Across Phases 3–4.5 (≈340 hypotheses + the confirmation) **0 deployable
edges**. This retires the breakout-lead line; genuinely new directions (different factor families, or
a data/budget reconsideration for deeper intraday history) are needed, not more grinding of this lead.
_Reversible: yes._

### 2026-10-02 · D-014 · Power boost: cross-class pooling DILUTES; crypto 15m nearly clears the bar
Phase-4.5 pre-registered confirmation of the regime-gated breakout (`donch_brk(20)` & gate, swing)
under trade-adding data configs (`jobs/power_boost.py`, local lake). Findings:
- **Move 1 (pool crypto+FX+metals+oil): DEAD.** All gated breakouts go NEGATIVE when pooled across
  classes (allclass expR −0.05…−0.15R). The edge is crypto-specific; other classes' breakouts
  dilute it. Do not cross-class-pool breakouts.
- **Move 2 (crypto 15m): strong.** `donch_brk(20)` & `vol_hi` on 15m: n=133, expR +0.422R, PF 1.77,
  Sharpe 0.281, +0.242R at 2× cost, **p=0.0006 (clears Bonferroni)**, **DSR=0.895** (just under 0.95).
  15m lifted both sample and Sharpe. Best edge found so far — one gate short of a candidate.
- **Move 3 (widen crypto universe): the lever to finish.** config.yaml crypto 9→18 symbols; a CI
  data-refresh fetches them, then `research-power-boost` re-runs on the bigger pool. More crypto 15m
  trades at the same Sharpe should push DSR over 0.95.
CAVEAT carried forward: 15m history is shallow (~52d → ~10d validation window). Even if it clears
the statistical bar, that is a short, possibly single-regime sample — Phase-5 walk-forward + Phase-6
forward paper stay MANDATORY before any deployment. Thresholds not loosened. _Reversible: yes._

### 2026-10-02 · D-013 · Phase-4 = Phase-3 leads × regime gates; same gauntlet, own MTC family
Phase 3 left 0 standalone candidates, only leads. Phase 4 (T-401) crosses **every** phase-3
base-gate PASS (read from the registry — no cherry-picking) with a fixed gate catalogue
(`factors.GATES`): ADX ranging/trending (`adx_lo20/lo25/hi25`), higher-TF trend (`trend_up` =
close>SMA200), volatility regime (`vol_lo/hi` vs trailing-median ATR%), and NY session (`ny`).
Combined rule = base & gate, no-lookahead (gate read at the signal bar, trade at next open),
identified by `entry_rule = "<rule>+<gate>"` with base params left in `params` so T-303's
sensitivity sweep still perturbs them. The **phase-4 search is its own multiple-testing family**
(T-303 `--phase 4`): N and the DSR benchmark come from phase-4 valid tests only, not phase-3.
**Finding:** gating lifted robustness markedly — 13/21 base-PASS combos now survive 2× cost (vs
≈0 in Phase 3), led by **crypto `donch_brk`+`vol_hi`/`ny`/`adx_hi25`** (val Sharpe ≈0.18, DSR ≈0.66,
+0.125R at 2× cost, 100% param-robust). Still 0 cleared the full gauntlet — the gate concentrates
the edge into ~120 trades, so significance is power-limited, not direction-wrong. These are the
**Phase-5 confirmation leads**; thresholds were NOT loosened to manufacture a candidate. _Reversible: yes._

### 2026-10-02 · D-012 · T-303 promotion gate = 2× cost + sensitivity + Bonferroni + Deflated Sharpe
A base-gate PASS (≥100 val trades, positive net expectancy, beat random) is only a lead; the
winner of a ~220-hypothesis sweep is inflated by selection alone. **Decision:** a hypothesis
becomes a CANDIDATE only if it survives ALL four independent checks, judged on validation:
(1) **2× transaction cost** still n≥100, expR>0, PF>1; (2) **parameter sensitivity** — ≥60% of
±1–2 neighbors stay positive with positive median (edge is a plateau, not a spike); (3)
**Bonferroni** one-sided p < 0.05 / N where N = hypotheses actually tested; (4) **Deflated Sharpe
Ratio > 0.95** (Bailey & López de Prado — deflates for N trials via the expected-max-Sharpe
benchmark and for skew/fat tails). p-values use the normal approximation to the t-distribution,
valid at n≥100. All math is stdlib (`research/src/mtc.py`, `statistics.NormalDist`) — no scipy, so
it runs identically off-peak. Implemented in `research/jobs/robustness.py`; nothing reaches
CANDIDATES.md otherwise. _Reversible: yes (thresholds are CLI args)._

### 2026-10-01 · D-011 · Phase-3 tests POOL a rule across an asset class (sample size)
Engine validation showed single-instrument rules fire only 8–54 trades (val 8–21) — far below
the 100-trade minimum. **Decision:** every single-factor test pools a rule across ALL instruments
in its asset class (each split on its own 60/20/20 timeline, trades pooled by split tag). This
reaches ~85–432 trades. Note: crypto (9 syms) & FX-intraday still land ~85–96 val — to clear 100
reliably, pool FX majors+crosses together or add 4h. Benchmark = trade-weighted avg of per-
instrument random-entry controls. Engine (backtest.py/costs.py/single_factor.py) verified on real
lake data; no naive factor passed (expected). _Reversible: yes._

### 2026-10-01 · D-010 · Sources reconciled (T-102); gold is spot, silver/oil are futures
TD vs yfinance 1h close, inner-joined: **EUR/USD PASS** (median 0.027%, p95 0.038%), **BTC/USD
PASS** (0.058% / 0.154%) → like-for-like sources agree tightly, **mixed lake validated**. XAU/USD
"FAIL" (0.46% / 1.36%) is the **spot-vs-futures basis** (TD XAU/USD = spot; yfinance GC=F =
futures), not a data error. **Consequence to carry:** gold = spot (TD); silver/oil = futures
(yfinance). Fine for short-horizon technical signals (basis slow-moving); model roll/financing
per instrument when costs are applied. See RECONCILE.md. _Reversible: yes (could switch gold to GC=F)._

### 2026-10-01 · D-009 · Bigdata.com = interactive macro-event/news overlay only (MCP-ONLY, PAYG)
User added the Bigdata.com connector. Assessment: it's an **equities-focused** news/sentiment/
fundamentals service (packages: company-sentiment, earnings, filings, economic-calendar,
premium-news, web, …; PAYG 1000 credits). For this FX/metals/oil/crypto PRICE project its useful
surface is narrow — **economic-calendar + premium-news/web for macro-event context**. It is
**MCP-ONLY** (no portable API → excluded from off-peak Actions sweeps per architecture) and
**metered** (burning credits in bulk breaks the $0 spirit). **Decision:** use it only at the
INTERACTIVE layer — event-awareness for the daily briefing (Phase 6) and qualitative regime
labelling (Phase 4) — never as a price source and never in backtests/sweeps. _Reversible: yes._

### 2026-10-01 · D-008 · Silver + oil sourced from yfinance (not on TD free)
Twelve Data free returns 404 for XAG/USD, WTI/USD, BRENT/USD. User chose the yfinance fallback
(B-003 option A): `SI=F` (silver), `CL=F` (WTI), `BZ=F` (Brent) — free, already used in this repo,
same lake format via `research/src/yfinance_client.py` (4h resampled from 1h). These three are
**sole-source** (no TD cross-check) and inherit yfinance limits (15m ~60d). _Reversible: yes._

### 2026-10-01 · D-007 · Volume features restricted to FX/metals/oil (crypto has no free volume)
First live run confirmed Twelve Data free crypto quotes omit `volume`. **Decision:** volume
primitives (OBV, volume-spike, VWAP-by-volume) are tested on FX/metals/oil only; crypto uses
price/volatility/structure primitives. The client now tolerates missing volume (sets 0.0).
Revisit if a crypto volume source is added. _Reversible: yes._

### 2026-10-01 · D-006 · Lake persisted via Actions cache + artifact (not git) for now
The OHLCV lake is kept out of git (`research/.gitignore`) and persisted via Actions
**cache** (fast, free) + an uploaded **artifact** (downloadable, 14-day retention). Reason:
we don't yet know the lake's on-disk size, and committing large data to a public repo is
wasteful/irreversible. After the first refresh we measure size and decide whether to also
git-commit it (to a data branch) for long-term durability. _Reversible: yes._

### 2026-10-01 · D-005 · 5-minute timeframe excluded from scope (for now)
Deep 5m history is not available on free data tiers (Twelve Data free 5min is shallow;
yfinance 5m is a few days). Per the mission's "say so and request a decision" rule, we
flagged it; user chose $0 budget. **Decision:** scope = 15m / 1h / 4h / 1D. Revisit only
if the budget decision changes. _Reversible: yes (budget-gated)._

### 2026-10-01 · D-004 · Survivorship bias accepted as a documented limitation
A survivorship-free universe (delisted crypto/pairs, changed tickers) is not obtainable
on free tiers. **Decision:** universe = currently-listed liquid instruments; every
performance claim carries a "survivorship-not-corrected" caveat. Mitigation: favour
instruments with long continuous listings; note any known delistings qualitatively.
_Reversible: yes (paid data would fix)._

### 2026-10-01 · D-003 · Budget = $0, free tiers only
User choice. Enforced in code: Twelve Data capped at 8 req/min & 800 req/day via a
persisted daily counter; on exhaustion the job logs to BLOCKERS and exits cleanly.
Public-repo Actions minutes are free, so compute is not the binding cost. _Reversible: yes._

### 2026-10-01 · D-002 · Build in existing repo under `research/`, land via PR
User choice. Reuses the existing yfinance pipeline, backtest harness, and Actions/caching.
All research isolated under `research/`. Work pushes to `research/*` branches and lands as
PRs the user merges; **never a direct push to main.** Note: scheduled workflows run only
from the default branch, so workflow files must be merged to main to fire. _Reversible: yes._

### 2026-10-01 · D-001 · Twelve Data (free) as primary off-peak data layer; yfinance as cross-check
User choice. Twelve Data is portable (plain HTTPS API → works inside GitHub Actions, unlike
MCP servers) and covers FX/metals/oil/crypto + indicators. yfinance stays as a free second
source for reconciliation. MCP servers (TradingView/OANDA) remain the **interactive** layer
only and are never relied on inside Actions. _Reversible: yes._
