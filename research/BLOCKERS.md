# BLOCKERS — what the project needs from the user (or is waiting on)

Open blockers at top. Jobs that hit a blocker log it here and exit cleanly (never fabricate).

---

## OPEN — action needed to start Phase 1 data flow

### B-002 · Merge this bootstrap PR to `main`
GitHub **scheduled** workflows only run from the default branch. The nightly
`research-data-refresh` workflow will not fire until this `research/bootstrap` PR is
reviewed and merged to `main`. (Code/results after this still land via PRs — never direct
pushes to main.)
**Owner:** user. **Status:** OPEN.

### B-001 · Create free Twelve Data API key and add as GitHub Secret
No data can be pulled off-peak until this exists.
1. Sign up free at https://twelvedata.com → Dashboard → copy API key (free plan: 8 req/min, 800/day).
2. Repo → Settings → Secrets and variables → Actions → **New repository secret**:
   - Name: `TWELVEDATA_API_KEY`  · Value: your key.
3. (Optional, for local runs) set `TWELVEDATA_API_KEY` in your shell env.
**Owner:** user. **Status:** OPEN. Without it, `data_refresh.py` logs here and exits 0.

---

## RESOLVED
_(none yet)_
