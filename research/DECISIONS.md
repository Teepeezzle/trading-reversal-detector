# DECISIONS — every judgment call, with the why

Append-only. Newest at top. Each entry: date · decision · why · reversible?

---

### 2026-10-05 · D-036 · CONCLUDE the free-data short-horizon search — final negative report
User decision after the Phase-10 (AV sentiment) final verdict. The program has tested **2,479
hypotheses** across every structurally-distinct approach (Phases 3–10: single factors, combos×gates,
power boosts, new families, cross-sectional, deep HistData, crypto funding, news gates, sentiment) and
**0 survived the full gauntlet** (net cost, no-lookahead, ≥100 trades, 60/20/20, beat benchmarks, 2×
cost, parameter sensitivity, Bonferroni, Deflated Sharpe). 231 base-gate PASSes, 0 candidates. The
strongest base-gate results of the whole program were the Phase-10 crypto sentiment cells (Sharpe
≈0.34/0.29, n≈200+) — still deflated below significance by the trial correction. Per the honesty clause,
**a documented negative result is the correct, valuable outcome** — no robust short-horizon edge exists
in this $0/free-data universe under this gauntlet. **Deliverable:** `research/FINAL_REPORT.md`. **Holdout
NEVER touched** — reserved for one clean confirmation if a credible candidate ever arises (paid data,
longer horizon, or Phase-11 `fund_direction`). Infrastructure (registry, gauntlet, sealed holdout) is
kept — reusable if budget/horizon changes. Off-peak pipeline should wind down (no remaining work).
_Reversible: yes — the search can reopen with new data/horizon; nothing is deleted._

### 2026-10-04 · D-035 · RESUME main program — carry forward 4 learnings from the Confluence Board digression
The board digression (D-032..D-034) surfaced four lessons now folded into the main research program as
standing rules:
1. **Thin-sample discipline.** Fundamental augmentation could not be validated at n≈12–47 per cell — the
   same small-sample regime that gave this project two false positives (two-zone DRS, PR gate). **Rule:**
   no fundamental/overlay factor gets a verdict from thin per-cell samples; require pooled estimation
   across instruments (DerSimonian-Laird or equivalent) AND a minimum n (≥100 per cell, or pooled ≥200)
   before judging. Applies to the Phase-10 sentiment factor and any future fundamental factor.
2. **Staleness rule (per-type max-age; exclude, never carry).** The board displayed `news_sentiment` 825
   days stale. The research pipeline had the SAME latent bug: `sentfactor.enrich` did a backward
   `merge_asof` with no age cap, so bars past the archive would get the last (arbitrarily stale)
   sentiment. **Fixed now:** `sentfactor.enrich` caps at `max_age_days=7` (merge_asof `tolerance`) →
   stale = NaN = no trade; `news.latest_asof` gains an optional `max_age_days` (default None preserves
   completed phases; use ~45d for monthly macro going forward). No value is ever used beyond its max-age.
3. **Per-asset fundamental direction is a reusable component, logged not assumed.** The board's per-asset
   fundamental-trend logic (`backtest/fundtrend.py`) is registered in HYPOTHESIS_REGISTRY.csv as a
   **Phase-11 pending** hypothesis (`fund_direction`) — to be judged by the full gauntlet (net cost,
   no-lookahead, ≥100 trades / pooled, MTC, 2× cost, benchmarks) like any factor, never assumed to work.
4. **Fail loud, never silent.** The board dropped assets silently on fetch failure. **Rule:** the
   research pipeline flags/logs every data gap. `sentfactor` now prints `SKIP <class>/<sym>` on a failed
   load (a missing symbol is a visible gap, not clean data); data-refresh already logs to BLOCKERS. The
   rule applies pipeline-wide.
_Reversible: yes (rules are tunable); the staleness cap is a strict no-lookahead/no-stale improvement._

### 2026-10-03 · D-034 · Fundamentals v1 — reframe to context + forward shadow test + broaden base (milestone gates)
User-directed follow-up to D-033. We cannot prove "fundamentals improve signals" on the thin sample, so
we separate *using them correctly now* from *proving value over time*. Three tracks, branch
`feature/fundamentals-v1` (PR-only; nothing merges to main / touches the live board without approval):
**(A) context layer** — fundamentals shown on the board as DISPLAY-ONLY context (macro regime, latest
point-in-time values, next projected event), labelled "Context - not validated", toggleable; zero change
to the signal path (proven byte-identical, `backtest/test_context_identical.py`). Displaying the backdrop
is a factual claim, not a statistical one — defensible regardless of sample size. **(B) forward shadow
test** — log every fresh SETUP with its point-in-time context + three shadow uses (gate/score/tag)
recorded but never acted on; resolve outcomes; weekly Actions job. **(C) broaden the base** — a separate
direction-unrestricted eval universe (`config/fundamentals_eval_universe.yaml`, +12 instruments incl.
WTI/Brent so EIA is finally usable; live scanner config untouched) + a DerSimonian-Laird partial-pooling
estimator (`backtest/pooled_estimate.py`) that detects a weak-but-consistent effect across cells without
more data. **MILESTONE GATES (held to):** resolved n=100 = preliminary read (NO verdict); n=200 = first
significance test WITH multiple-testing correction; n=400 = walk-forward. **Hard rule: do NOT run the
augmented-vs-baseline backtest until pooled n>=200.** No performance claim is made until then; context is
explicitly not validated. Transferable to the main program: the forward-log + pooling + point-in-time
context pattern is how any thin-sample overlay (incl. the N-8 sentiment factor) should be judged.
_Reversible: yes — all isolated on the feature branch; context is toggleable and additive._

### 2026-10-03 · D-033 · Confluence Board fundamentals study — NOT VIABLE (stopped at viability gate)
Outcome of the D-032 digression (full report: `research/fundamentals/RESULTS.md`). The question "do
fundamentals improve the Confluence Board's signals?" **cannot be answered honestly on current data.**
The Confluence Board is a live *snapshot* (no persisted signal log), so signals are reconstructed by
the frozen confluence logic over yfinance history (trailing ~730d; 15–45m only ~60d). Measured over
that window across the whole 10-asset validated universe: **65 signals** (FX 47, crypto 12, metals 6,
index 0) — vs a pre-set gate of **≥200 total / ≥100 per class**. Of the fundamentals, only FRED macro
(→FX/metals/index, ~53 signals) and crypto funding (→crypto, 12) overlap at all; **AV daily sentiment
has ZERO overlap** (ends 2024-02, signal window starts 2024-10) and **EIA has no oil asset** in the
universe. So the flow was stopped at Step 1 — no pre-registration, no backtest, no ablation, no registry
rows (nothing was tested). **Vintage check PASSED (good case):** macro is first-release / point-in-time
(`output_type=4`), so there is no revision look-ahead to flag. **Transferable findings for the main
program:** (1) the binding constraint for ANY overlay/filter study on the confluence is *signal count*,
not data coverage — the setup fires ~30×/yr across 10 assets, so overlays will always be n≈10–50 per
cell = the regime that gave two false positives here (PR gate n=22, two-zone DRS n≈10 that inverted a
week later); do not run gate/score studies on it without far more signals. (2) AV sentiment becomes
usable for crypto/macro overlays only once its backfill reaches ≥2024-10 (N-8 self-advancing, ~days
away) — but that fixes *overlap*, not the thin-sample problem. (3) point-in-time macro (FRED
output_type=4) is reusable infrastructure for any future vintage-safe news study. **Recommendation:
DO NOT INCORPORATE / revisit only if signal breadth materially increases.** _Reversible: n/a (evaluation
only; live board untouched; branch holds the report)._

### 2026-10-03 · D-032 · PAUSE the main research program for a scoped Confluence Board fundamentals study
User-directed digression. The main multi-week signal-research program is **paused (not abandoned)** to
answer a bounded question about a *different* live system — the **Confluence Board** (the divergence/
confluence scanner that auto-refreshes to GitHub Pages): *does incorporating fundamental data improve
its signals?* Strictly an **evaluation + recommendation**, no deployment; nothing on the live board
changes without explicit approval (Step 6 gate). **Hard rules for the digression:** work only on branch
`research/fundamentals-augmentation`; never push to main; do not modify the live Pages output, its
workflows, or its data pipeline; add the fundamental layer as a parallel/opt-in path (do not rewrite
existing signal logic); **never interpolate/extrapolate/back-fill** a fundamental value (a missing
record is a gap, not a guess); all data access read-only; time-boxed — if the Step-1 data audit fails
the viability gate (<200 signals in the overlap window, or <100 per asset class) or reveals look-ahead
(revised-to-date not point-in-time fundamentals), **stop early and say so** rather than forcing a
deliverable. Off-peak Actions left running: the N-8 AV-sentiment harvester continues self-advancing on
main (D-031) — that is the research program's own job, explicitly left untouched. Outcome will be logged
here (transferable to the main program). _Reversible: yes — digression is isolated on its own branch;
RESUME HERE for the main project is pinned at the top of PROJECT_STATE.md._

### 2026-10-03 · D-031 · Auto-advance the AV sentiment backfill (scoped exception to D-002)
User directive: "merge tomorrow's archive PR and keep advancing the backfill." The resumable harvester
only progresses if each day's archive lands on `main` (the next run reads the committed archive from
main, under the free 25-calls/day cap), so the backfill stalls without a daily merge. To keep it
advancing without babysitting, `research-avsentiment-refresh` now **auto-squash-merges its own
data-archive PR** (`research/av-sentiment`) at the end of each run (`gh pr merge --squash`, guarded to
no-op when the harvest changed nothing). **Scoped exception to D-002** (which bars direct-to-main / auto
merges): limited to the bot's own auto-generated data file on a fixed path
(`altdata_committed/news/av_sentiment.csv.gz`), **never code** — all code still lands via human-merged
PRs. Audit trail preserved (each advance is a squash-merge referencing the PR, span in the body). Low
risk: the harvester is validated + idempotent, and the definitive sweep runs `--refresh` so any bad
day's data is recomputed, not frozen. _Reversible: yes — delete the auto-merge step; manual merge
resumes._ The SWEEP stays a deliberate act (not automated): run `research-sent-sweep` →
`research-robustness phase=10` once the span reaches ~present (~5 days of backfill).

### 2026-10-02 · D-030 · N-8 — Alpha Vantage NEWS_SENTIMENT as the first $0 backtestable sentiment source
User added `ALPHAVANTAGE_API_KEY` (free tier) + `POLYGON_API_KEY` as secrets and directed "build N-8".
AV `NEWS_SENTIMENT` is the first FREE source we found that is historical + UTC-timestamped + pre-scored
(`overall_sentiment_score` ∈ [-1,1] per article, with `topics` + per-asset `ticker_sentiment` incl
`FOREX:`/`CRYPTO:`) — i.e. the programmatic-SENTIMENT use D-021 reserves, finally available at $0.
**Architecture** (reconciles the user's "harvest historical from MCP, real-time from the API" with the
$0 rule): AV ships the *same* data over a keyed REST endpoint that runs inside Actions, so we harvest via
REST (not the MCP, which can't run in CI, cf. D-001/D-009) — efficient + resumable. Free tier = 25
req/day, so `jobs/avsentiment_refresh.py` does a bounded batch of (class, month) windows per run (oldest
gaps first, current month always refreshed, stop on rate-limit note) and the daily `research-avsentiment-
refresh` workflow backfills over ~days then stays current, committing a DAILY relevance-weighted per-class
series → `altdata_committed/news/av_sentiment.csv.gz`. Topic→class: economy_macro→forex_macro (drives FX
+ metals via USD), energy_transportation→oil, blockchain→crypto. **Factor** (`src/sentfactor.py`): strict
NO-LOOKAHEAD join (day-D sentiment usable only from D+1), families `sent_rev` (fade z-extremes) + `sent_mom`
(follow z-momentum), one side per hypothesis, pooled + net-of-cost through the SAME SL/TP engine;
`jobs/sent_sweep.py` emits phase-10 registry rows + SENT_STUDY.md, judged by the shared gauntlet
(`robustness.py --phase 10`: 2× cost + sensitivity + Bonferroni + Deflated Sharpe). News stays CONTEXT/
FILTER (D-021): sentiment is an edge only if it clears MTC. The sweep can only run meaningfully after the
archive accrues (~1y). POLYGON_API_KEY noted for a later macro feature (inflation-expectations / deep
prices); not used by N-8. _Reversible: yes (drop the factor + archive; key unused elsewhere)._

### 2026-10-02 · D-021 · STANDING RULE — fundamental/news layer as context & filter (never standalone)
User-directed standing rule (full spec: research/NEWS_LAYER.md). Add a fundamental/news layer that is
CONTEXT AND FILTER only — never a standalone entry signal. Mandatory: UTC `published_at` +
`first_available_at` on every item (no look-ahead; undated item = discard); a forward event calendar
(no new intraday entry <30min before a high-impact release; no holding a fresh position through one
without a logged reason); three uses only (GATE / REGIME-TAG / programmatic timestamped SENTIMENT);
NO discretionary news trading; every news factor logged in HYPOTHESIS_REGISTRY.csv and judged by the
same gauntlet (own MTC family; "improves expectancy after cost?" vs "just fewer trades?" both valid);
API-sourced for off-peak (MCP-only = interactive-only, excluded, cf. D-009); prefer structured
timestamped official feeds (FRED/EIA/economic-calendar), log source+pull-time, exclude undated; and a
DAILY_SIGNALS briefing line per signal (news tag + invalidating scheduled event). Applies across all
future phases alongside the technical work. _Reversible: no (standing directive) — mechanics tunable._

### 2026-10-02 · D-028 · Consensus forecasts confirmed paid across 4 providers; FXMacroData free actuals/calendar is a timestamp upgrade
Evaluated the user's 5-source plan (FRED, EIA, FXMacroData, CalcFi, FMP). Tested FXMacroData live
(no key): its free USD endpoints serve the release CALENDAR (with precise `announcement_datetime` +
`point_in_time_safe`/vintage flags — better timestamping than our FRED fetcher) and ACTUAL values
(`/v1/announcements/usd/{indicator}`, official BLS/BEA), but **forecast values are plan-gated**
("Forecast values require a plan; 14-day trial"). So consensus/forecast is now confirmed PAID at
**4/4** providers (CoinGlass, Finnhub, FMP 402, FXMacroData) — it is a licensed product, not a
findable-free item. CalcFi = actuals-only CSV mirror (redundant with FRED). FMP economic calendar =
402 on free (tested). **Conclusions:** (1) the actual-vs-PRIOR surprise proxy stays the $0 reality
(D-026 stands); (2) OPTIONAL free upgrade — switch N-1 timing to FXMacroData's free calendar/
announcements for sharper `announcement_datetime` + vintage (no key); (3) a one-time consensus harvest
is possible via FXMacroData's 14-day trial IF it's card-free and serves history — commit once, like the
Bybit funding — a user decision. True ongoing consensus = budget (D-003). _Reversible: yes._

### 2026-10-02 · D-029 · FXMacroData free = ~90d-capped data + plan-gated forecasts; its free FORWARD calendar now powers N-6
Follow-up to D-028 after deeper live testing. FXMacroData free `/announcements` is capped to a ~90-day
trailing window (start_date/end_date are ignored on free; earliest_available ≈ 2 months back), and
`/predictions` (forecast values) are plan-gated. So "do both": **#1 (historical actuals via FXMacroData)
and #2 (consensus harvest) are NOT viable at $0** — free can't backfill multi-year, a 14-day trial
wouldn't either, and forecasts need a paid plan. FRED stays the free historical macro source; consensus
remains a budget item (D-003, D-026). **BUT the free `/v1/calendar/usd` forward schedule IS fully usable
(no key): 100+ official upcoming US releases with exact `announcement_datetime` + `event_importance`/
`market_tier`/`top_tier_for_currency` out to 2027.** Wired into N-6 (`daily_brief.fxmacro_forward_calendar`
/ `combined_calendar`): the event-risk calendar now shows OFFICIAL exact release times for macro (⚠high
on tier-1), with graceful fallback to cadence-projection (and EIA-oil) if offline. This sharpens the
§3 30-min pre-release gate. newsdata/FMP/Finnhub/FXMacroData = 5 providers; consensus paid at all.
_Reversible: yes._

### 2026-10-02 · D-027 · newsdata.io = live headline feed only (not economic data); forward-collector role
Tested live (NEWSDATAIO_API_KEY, read-only probe). newsdata.io is a HEADLINE/ARTICLE aggregator, not
an economic-data source: it returns title/description/content/pubDate/country/category/keywords, with
NO macro-release values (FRED), inventory values (EIA), or consensus forecasts (calendar). So it does
NOT replace or fill the three economic sources, and does NOT enable the historical consensus-surprise
study (D-026 stands). Free-tier limits confirmed live: `/latest` only (~48h, no archive — archive is
~$199/mo), and **sentiment is paid** (field returns "ONLY AVAILABLE IN PROFESSIONAL AND CORPORATE
PLANS"). It IS timestamped (pubDate) and keyword-filterable. **Fit:** a FORWARD live headline/event
feed for the daily briefing (N-6) and Phase-6 forward paper; if collected on a schedule it builds our
own timestamped archive over time, enabling a self-computed programmatic keyword/event-flow factor
later (§4, our own measure — never their paid sentiment, never discretionary reading). Cannot backtest
historically at $0. Probe kept (`jobs/newsdata_probe.py` + workflow). _Reversible: yes._

### 2026-10-02 · D-026 · Consensus-surprise calendar is paywalled at $0 everywhere → use the actual-vs-prior proxy
N-3 aimed for a TRUE consensus surprise (actual − forecast). All three free candidates gate it:
CoinGlass funding = 401 "Upgrade plan"; Finnhub `/calendar/economic` = premium ("You don't have
access"); FMP `/stable/economic-calendar` = **402 "Restricted Endpoint … upgrade your plan"**. So
consensus/forecast data is a paywalled product at the free tier across providers — confirmed, not
assumed. **Decision:** keep the free **actual-vs-PRIOR** surprise proxy (FRED beat/miss vs the previous
print; EIA week-over-week build/draw), which N-5 already studied and which drove the surprise-SIGN
tilt (D-025). The FMP/FINNHUB keys are unused for this (both gated) — the user may delete them. A true
consensus surprise would need a paid calendar (Trading Economics / FMP paid / etc.) — a budget decision
(D-003), not a $0 item. The `fetch_fmp` code stays (exits-clean, logs a blocker) so it lights up if a
paid FMP plan is ever added. News layer otherwise COMPLETE: schema+no-lookahead join (N-4), FRED (N-1)
+ EIA (N-2) live, gate/regime-tag study (N-5), daily briefing (N-6). News = context/filter, confirmed
useful as a regime tag, not a standalone edge. Holdout untouched. _Reversible: yes (paid data reopens N-3)._

### 2026-10-02 · D-025 · Phase 9 N-5 verdict: news gates mostly cut trades; surprise-sign is the real effect, but 0 clear MTC
Ran the news-gate study (D-021 §6) on the deep FX/metals 1h/4h lake + FX/metals/oil macro news (FRED
235 events + EIA 195). 380 base-vs-gated cells → **11 improve expectancy, 131 just-cut-trades, 48 hurt,
175 thin; 0 clear the N=196 MTC bar** (Bonferroni p<2.6e-4, DSR>0.95). So a news filter overwhelmingly
removes trades without raising expectancy. The genuine improvers cluster in the **surprise-SIGN regime
split** (surp_pos/surp_neg) and the **quiet** regime — economically coherent (e.g. oil roc_mom base
+0.047R → +0.205R after a positive crude-inventory surprise; FX roc_mom flips -0.051R → +0.075R with
the surprise sign) — but none are significant after correction. Consistent with the whole program:
coherent tilts, no MTC-significant standalone edge. Takeaways: (1) news is confirmed useful as a
REGIME TAG / context, not a standalone signal (as D-021 intends); (2) the surprise-sign effect is the
most promising lead and would sharpen with a true consensus surprise (actual-vs-forecast) from an
economic calendar — motivates N-3. Holdout untouched. _Reversible: yes._

### 2026-10-02 · D-024 · Phase 8 Step B verdict: crypto funding families also yield 0 candidates
Ran the alt-data sweep on the full 17-coin / 2y committed-funding lake: 60 hypotheses (fund_rev,
fund_mom, basis_rev × params × TF × horizon) → 2 base-gate PASS → T-303 `--phase 8` (N=26, Bonferroni
p<1.9e-3, SR*=0.21) → **0 candidates**. The best, `fund_rev` short on crypto 4h-intraday (fade crowded
longs), is genuinely coherent — val Sharpe 0.134, +0.107R, survives 2× cost (+0.06R, PF 1.22), 100%
parameter-robust, decisively beats random — but fails the 26-trial MTC (p=0.035 vs 0.0019; DSR 0.15).
basis_rev was empty (basis deferred, NaN). So funding/positioning signals behave like everything else:
a real-looking tilt that doesn't survive honest multiple-testing correction. **Program tally across
Phases 3–8 (price / regime-gated / cross-sectional / deep-data / funding): ~1,740 hypotheses, 0
deployable edges.** Next per the standing rule (D-021): build the news/fundamental layer (FRED/EIA keys
are in). A perp-price source would let basis_rev run later. Holdout still untouched. _Reversible: yes._

### 2026-10-02 · D-023 · CoinGlass free tier is paid-gated → commit Bybit funding instead (resolves B-004)
D-022's CoinGlass plan failed live: the historical funding-rate endpoint returns `401 "Upgrade plan"`
on the free tier (free docs list the interval but the endpoint itself needs a paid plan). So no $0
funding API is reliably US-reachable (Bybit/Binance geo-block US Actions; OKX uncertain; CoinGlass
paid). **Resolution:** funding is tiny (8h × 2y × 17 coins = 208 KB), so fetch it once from a non-US
box via Bybit and COMMIT it to the repo at `research/altdata_committed/funding/{SYM}.csv.gz` (17/18
coins; MATIC not a Bybit perp). `cryptoalt_refresh.py` now joins committed funding to the TD crypto
bars from the lake — no network, no key, no geo-block in CI. Overrides D-006 for this one small,
static dataset (funding history doesn't change retroactively, so committing is safe). The
COINGLASS_API_KEY secret is now unused (the user may delete it). Validated end-to-end locally: funding
families produce real base-gate PASSes (e.g. fund_rev 4h-intraday-short Sharpe 0.20, +0.11R at 2× cost);
basis deferred (NaN). _Reversible: yes._

### 2026-10-02 · D-022 · Crypto funding via CoinGlass free API (resolves B-004 geo-block)
Bybit/Binance geo-block US GitHub Actions (B-004), so crypto funding for Phase 8 comes from CoinGlass
— a US-accessible data VENDOR (not an exchange), free "Hobbyist" tier, historical funding-rate OHLC at
`open-api-v4.coinglass.com/api/futures/funding-rate/history`, auth header `CG-API-KEY`. Free-tier
constraint: interval >= 4h (fine — funding is 8-hourly). Price/bars for the backtest come from the
existing crypto OHLCV lake (Twelve Data, which works in US CI); perp/spot BASIS deferred (needs a
perp-price endpoint) so Phase 8 ships with the funding families (fund_rev, fund_mom) first. Needs a
`COINGLASS_API_KEY` repo secret (user action, like TWELVEDATA_API_KEY). _Reversible: yes._

### 2026-10-02 · D-020 · Phase 7 Step A verdict: DEEP data refutes the "under-powered" hypothesis
Built a free deep lake (HistData 1-min → 15m/1h/4h/1D, ~21 months, FX majors/crosses + XAU/XAG) and
re-ran the phase-3 + phase-5 single-factor grids on it (480 configs, phase 7 / id `|deep`). Depth
jumped 5–8× (15m ~5000→~43000 bars/instrument; pooled 1h rules fire 475–535 trades). Result: 480 →
19 base-gate PASS → T-303 `--phase 7` (N=230, Bonferroni p<2.2e-4, SR*=0.30) → **0 candidates**. The
telling detail: the high-n rules regressed to **Sharpe ≈0.01 (p≈0.42)** — more data tightened the
estimate around **zero**, it did not expose a hidden edge. The earlier promising Sharpes (e.g. oil
rsi_rev 0.24 on ~120 trades) were **small-sample inflation**. This rules OUT "the edges were real but
under-sampled": with real statistical power, single-factor technical rules on FX/metals have no net-of-
cost edge. Strengthens D-017/D-019. (Fetcher got monthly data for current+prior year ≈21mo; older
years need HistData's yearly-zip endpoint — minor future enhancement, didn't change the verdict.)
Oil not on HistData → unchanged. Holdout untouched. Next: Step B (crypto alt-data) per "Both, A first".
_Reversible: yes._

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
