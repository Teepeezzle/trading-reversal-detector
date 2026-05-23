# GitHub Secrets Setup

The `daily_scan.yml` workflow reads two secrets:

| Secret           | What it is                                               |
|------------------|----------------------------------------------------------|
| `EMAIL_ADDRESS`  | The Gmail account that sends — and receives — the alert. |
| `EMAIL_PASSWORD` | A Gmail **App Password** (NOT your normal password).     |

Both must be set before the first scheduled run, otherwise the scan will run
successfully but the email step will log
`EMAIL_ADDRESS / EMAIL_PASSWORD not set — skipping send.` to `logs/email.log`.

---

## 1. Generate a Gmail App Password

App Passwords are 16-character single-purpose credentials that work with
`smtplib` even when your account has 2-Step Verification enabled (which it
**must** for App Passwords to be available).

1. Open: <https://myaccount.google.com/apppasswords>
   - If that page says "App passwords aren't available for your account",
     enable 2-Step Verification first at
     <https://myaccount.google.com/signinoptions/two-step-verification>,
     then try the link again.
2. Under **App name**, type `trading-reversal-detector` and click **Create**.
3. Google will show a 16-character password like `xxxx xxxx xxxx xxxx`.
   - Copy it now — Google will not show it again.
   - You can paste it with or without spaces; both work.
4. Click **Done**.

> If you ever leak the password (e.g. paste it into chat / a commit / a
> screenshot), come back to this page and click the trash icon next to the
> entry to revoke it, then create a new one.

---

## 2. Add the secrets to GitHub Actions

1. Open your repository on GitHub.
2. Click **Settings** (top tab of the repo, not your profile).
3. In the left sidebar: **Secrets and variables → Actions**.
4. Click **New repository secret** (top right).
5. Add **EMAIL_ADDRESS**:
   - **Name:** `EMAIL_ADDRESS`
   - **Secret:** your full Gmail address, e.g. `you@gmail.com`
   - Click **Add secret**.
6. Click **New repository secret** again.
7. Add **EMAIL_PASSWORD**:
   - **Name:** `EMAIL_PASSWORD`
   - **Secret:** the 16-character App Password from step 1
   - Click **Add secret**.

Both secrets should now be listed (their values stay masked forever — even
to you).

Direct link (replace `OWNER/REPO`):
`https://github.com/OWNER/REPO/settings/secrets/actions`

---

## 3. Manually trigger the workflow

You can test the workflow at any time without waiting for the daily 17:00 UTC
cron:

1. Go to the **Actions** tab of the repo.
2. In the left sidebar, click **Daily Reversal Scan**.
3. Click the **Run workflow** dropdown (top right).
4. Leave the branch on `main` and click the green **Run workflow** button.
5. After ~5–10 seconds, refresh the page — a new run will appear at the top
   of the list.

Direct link (replace `OWNER/REPO`):
`https://github.com/OWNER/REPO/actions/workflows/daily_scan.yml`

---

## 4. Reading the logs when something fails

1. Open the **Actions** tab → click the failed run.
2. Click the **scan** job on the left.
3. Expand the step that failed (the one with the red ❌).
4. The full Python output (including any SMTP error message) is visible inline.

For deeper inspection, the workflow uploads the entire `logs/` directory as
an artifact named `scan-logs-<run-id>`:

1. On the run page, scroll to the **Artifacts** section near the bottom.
2. Click **scan-logs-{run_id}** to download a zip containing:
   - `logs/run.log` – everything the scanner logged.
   - `logs/signals.log` – append-only signal history.
   - `logs/email.log` – SMTP errors only (empty if no errors occurred).

### Common failures

| Symptom in logs                                                | Fix                                                                                                  |
|----------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| `SMTPAuthenticationError (535)`                                | App Password is wrong, expired, or you used the normal account password.                              |
| `EMAIL_ADDRESS / EMAIL_PASSWORD not set`                       | One or both secrets are missing from **Settings → Secrets and variables → Actions**.                  |
| `Network/TLS error` / `socket.timeout`                         | GitHub Actions transient network blip. Re-run the job — same workflow page → "Re-run failed jobs".    |
| `No signals. No email sent.`                                   | Not a failure — the scan ran but no four-condition setups fired today.                                |
| `ImportError` / `ModuleNotFoundError`                          | `requirements.txt` is out of date for the code; add the missing dependency and push again.            |

---

## 5. Rotating credentials

If you ever suspect the App Password is compromised:

1. Visit <https://myaccount.google.com/apppasswords> and **delete** the
   existing `trading-reversal-detector` entry.
2. Generate a fresh one (step 1 above).
3. Update the `EMAIL_PASSWORD` secret in GitHub (the **Update** button next
   to it — no need to delete and recreate).

No code changes are required — the next workflow run picks up the new value.
