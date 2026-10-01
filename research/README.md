# Short-Horizon Signal Research

A multi-week, checkpointed quant research project. **Read `PROJECT_STATE.md` first.**

## Three planes
1. **Storage & state (this repo):** the `research/` markdown/CSV files are persistent
   memory + task queue + result store. `/research/data` is the cached OHLCV lake.
2. **Off-peak compute (GitHub Actions):** scheduled jobs pull data and run sweeps while the
   laptop is off. **MCP servers do not exist in Actions** — off-peak code uses the portable
   HTTPS data client (`src/twelvedata_client.py`) + committed `/data` only.
3. **Interactive compute (laptop + MCP):** TradingView / OANDA MCP for live review and
   reconciliation. MCP-only indicators are marked MCP-ONLY and excluded from off-peak sweeps.
   **Bigdata.com** (news/sentiment/economic-calendar) is an interactive **macro-event overlay
   only** — MCP-ONLY + PAYG-metered, never a price source, never in backtests (D-009).

## The portability rule
Every indicator and signal rule must exist as a **plain Python function in `research/src/`** —
not only as an MCP tool call — so it runs identically off-peak and interactively. When the
laptop opens, off-peak results are **reconciled** against MCP-sourced numbers for the same
period; divergence beyond the stated tolerance → STOP and report before trusting either.

## Layout
```
research/
  PROJECT_STATE.md  DECISIONS.md  BLOCKERS.md  DATA_MANIFEST.md
  HYPOTHESIS_REGISTRY.csv  CANDIDATES.md  QUEUE.md  DAILY_SIGNALS.md
  config.yaml            # universe + timeframes + session timing
  requirements.txt       # portable deps (requests, pandas, pyyaml)
  src/
    twelvedata_client.py # rate+budget-limited HTTPS client (free tier)
    # indicators.py, backtest.py ... (Phase 2+)
  jobs/
    data_refresh.py      # idempotent /data lake builder
  data/                  # OHLCV lake (csv.gz), cached by Actions
```

## Hard rules (enforced)
- **Read-only / paper only. No live-trading keys, ever.** Actions get free-tier read-only keys only.
- **No look-ahead:** only closed bars; forming bars dropped.
- **Net of costs:** spread + commission + realistic slippage + swap for anything held overnight.
- **$0 budget:** Twelve Data free (8/min, 800/day) hard-capped; exceed → log BLOCKERS + exit.
- **Branch discipline:** `research/*` → PR → user merges. Never push to main.
- **Honesty:** "no reliable edge found" is a valid, valuable result. Never fabricate to stay green.

## Workflow set (status)
- `research-data-refresh` — nightly, session-aware. **Written** (this PR).
- `research-sweep`, `research-walkforward`, `research-validate`, `research-briefing`,
  `research-reconcile` — **planned** (built once data flows; see QUEUE.md).

See `PROJECT_STATE.md` for current phase and the exact next step.
