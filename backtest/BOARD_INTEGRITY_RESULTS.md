# Confluence Board — data-integrity diagnosis & fix (fix/board-data-integrity-main)

_Evidence-based. Diagnosis reported before any fix. No signal logic changed. **This is the clean
main-only version** — the data-integrity fix applied directly on top of `main`, with **none** of the
fundamentals context layer (that is a separate feature, PR #69). Nothing merged without approval._

## Causation — is this the fundamentals context layer? **No.**
- The live board (GitHub Pages) runs `confluence_board_pages.yml` from **main**, and the context layer
  is **not on main** (PR #69 still open). So the live board that exhibits these symptoms has **no context
  layer at all** — it cannot be the cause.
- Data-path diff (`git diff 0046cf6^ HEAD -- backtest/dashboard_data.py`): the context commit touched
  **only** the new `_attach_context`/`_frame_for` helpers. `fetch_ohlcv`, `build_frames`, `asset_state`,
  the roster (ASSETS/WATCHLIST), the cache, and the render loop are **byte-identical** pre/post context.
- Evidence it's not our regression: identical failure mode exists in the pre-context code on main.

## Reproduction status (honest): both bugs are **intermittent**, and did not reproduce at diagnosis time
- Last **10** deployed board runs each wrote **29/29 assets**; BTCUSD present every time. My local run
  also produced 29/29. So neither bug is a persistent/deterministic defect — they surface when the data
  source degrades. The root causes below are **demonstrated** by forcing that degradation.

---

## BUG 1 — BTCUSD stale/incorrect price
**Traced source → fetch → transform → cache → render:**
- Source: yfinance `BTC-USD` (keyless). Right now it returns **$84,613.64** (last *closed* 15m bar @
  08:30 UTC). Direct **CoinGecko** right now: **$84,625** (2 min old). Δ = 0.01% → **source is correct;
  not wrong units, not a timezone bug, not sats-vs-BTC.**
- The board shows the **last CLOSED bar** (`drop_incomplete_last_bar` removes the forming bar), and picks
  the timeframe whose last bar is most recent. So the displayed price is inherently up to one bar-interval
  old (≈25 min on 15m), and **up to the 2-hour cron interval** between refreshes.
- Amplifiers (verified): (a) a **failed GitHub Pages deploy** leaves the previous snapshot live — run
  `37053916073` generated 29 assets fine but the **deploy step failed** ("No artifacts named github-pages
  were found"), so the board stayed on an older snapshot. (b) If yfinance **intraday** fetches fail
  (rate-limit), the board silently falls back to a higher timeframe whose last bar can be hours old.
- **There is no freshness indicator and no fallback source** — a stale value looks authoritative.

**Root cause (one):** the displayed crypto price is a single-source (yfinance), last-closed-bar value with
**no freshness indicator and no fresher-source fallback**, so normal refresh lag + any deploy/fetch hiccup
renders as an unflagged stale price.

## BUG 2 — only a few assets display
**Expected vs rendered** (validated universe; watch list analogous):

| Asset | Expected | Rendered (normal) | Rendered (yfinance degraded) | Source | Mechanism |
|---|:--:|:--:|:--:|---|---|
| BTCUSD/…/USDJPY (10 validated) | yes | yes (29/29 in last 10 runs) | **dropped if its fetch fails** | yfinance | silent drop |

**Demonstrated root cause:** in `dashboard_data.py:main()`, a per-asset failure is swallowed —
`asset_state` is wrapped in `try/except` that prints the error to **stdout only** (never the board) and
sets `st=None`; and `asset_state` itself `return None` when no timeframe builds ≥220 bars (fetch
empty/rate-limited), with the `elif st is None … pass` dropping it **with no message at all**. Forcing
yfinance to fail for `GC=F` and `NQ=F` → **XAUUSD and NAS100 silently vanish** from the output (proven).
So when yfinance rate-limits several tickers (common from residential IPs / under load), the board shows
"only a few assets." **This is the classic swallowed per-asset error. Errors ARE being caught and hidden.**

Checked and ruled out: filter logic (no liquidity/min-signal/date filter excludes assets — the only
filter is the UI status toggle, which the user controls); registry/config (all 29 are in the roster);
render-layer slice/pagination (none — the grid renders every asset in the payload); the context layer
(fails closed to "no context key", never drops a card — it attached to 29/29).

---

## Fixes (root cause → fix → why safe)

**BUG 2 — fail LOUDLY, never drop.** Root: silent `st=None` drop. Fix: in `main()`, when `asset_state`
returns None or raises, append a **`NODATA` placeholder card** (asset, ticker, the error reason) instead
of dropping; log loudly. Every universe asset now always renders. *Safe:* adds cards for assets that were
previously absent; does not touch any succeeding asset's signal fields.

**BUG 1 — freshness indicator + fallback cross-check.** Root: single-source, no freshness surfacing.
Fix: a post-step (`board_health.attach_health`) adds per-card `bar_age_min` + `stale` flag (class-aware
thresholds: crypto 4h, FX/metals/indices 65h to avoid weekend false positives) and, for crypto, a keyless
**CoinGecko spot** cross-check (`spot_price`/`spot_age_min`); if the yfinance bar is stale vs spot, the UI
flags it and shows the fresher spot reference. *Safe:* additive metadata computed AFTER `asset_state`;
signals/levels still come from the yfinance bars (unchanged). BTC source stays keyless with a keyless
fallback.

**Self-check before deploy.** `backtest/board_selfcheck.py` asserts every validated-universe asset is
present with a non-null price and a bar age within its class bound; emits loud `::error::`/`::warning::`
annotations and a non-zero exit on violations. Wired into the board workflow before the deploy step
(non-blocking so the now-fail-loud board still updates, but failures are surfaced in the run).

**UI.** `NODATA` → a visible "data unavailable" card with the reason; a freshness chip (age) on every
card, amber/red when stale; the crypto spot cross-check line. (This branch carries no context layer.)

## What could still go wrong
- yfinance remains the OHLCV source for signals (required for the confluence bars); a full yfinance
  outage still yields an all-`NODATA` board — but now **visibly**, with a failing self-check, not a
  silent few-asset board.
- CoinGecko is a display-only cross-check for crypto; if it is also down, the card shows the yfinance bar
  with its freshness flag (no fabrication).
- A failed GitHub Pages **deploy** is GitHub infrastructure; the freshness indicator makes a resulting
  stale snapshot visibly stale, but does not retry the deploy (left as a noted follow-up).

## Verification (Step 4)
1. **All assets render, fresh:** live generation wrote **29/29** cards; `board_selfcheck` →
   `RESULT: OK (every validated asset has a fresh price)`, 0 critical, 0 NODATA.
2. **BTCUSD vs direct source:** board yfinance close **$84,613.64** (last closed 15m bar) vs **CoinGecko
   $84,625** (2 min old) = 0.01%. The UI now shows the fresher spot when the bar is stale (verified
   in-browser: BTC card headline switched to the CoinGecko spot with "bar stale → showing spot").
3. **No signal logic changed:** `asset_state` (lines 98–205) has **zero** diff; all changes are in new
   helpers + `main()`'s loop; no signal-computation line altered. `test_board_integrity.py` and
   `test_context_identical.py` both PASS (every signal field byte-identical under the additive layers).
4. **Fail-loud proven:** forcing a fetch failure for GC=F → XAUUSD renders as a **NO DATA** card (red,
   with reason), never dropped (`test_board_integrity.py`).
5. **No context layer here:** this is the clean main-only fix; the fundamentals context feature is PR #69.
6. **UI states verified in-browser:** fresh (green ⟳), stale (red ⟳ + spot fallback), NO DATA card, and
   the "⚠ N no-data · M stale" health pill.
