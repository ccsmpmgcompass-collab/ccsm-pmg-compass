# CCSM PMG Compass — Handoff Access Checklist

Purpose: when a new missionary takes over CCSM PMG Compass, confirm their
Claude session has the same operating access this project currently runs on
— so if something breaks (a quota error, a broken trigger, a bad deploy),
they can actually fix it instead of being locked out.

This is Phase 8 of the CCSM go-live program (see memory: CCSM READINESS).

## The prompt — paste this to the incoming missionary's Claude Code session

Have them open this repo in Claude Code (or whatever agent they're using),
then paste the block below as their first message:

```
This repo is CCSM PMG Compass — a Streamlit dashboard + Google Apps Script
automation system for a real mission. I'm taking over as the tech missionary
running it. Before I touch anything, check whether you (this Claude session,
on this machine, under my accounts) have the same operating access the
previous person had.

1. Read CCSM_HANDOFF_ACCESS_CHECKLIST.md in this repo root — it lists every
   system this project depends on and why.
2. Run: cd dashboard && venv\Scripts\python.exe tools\check_handoff_access.py
   (create the venv first per dashboard/RUNNING.md if it doesn't exist yet)
3. For every check that FAILS, tell me plainly what's missing and which
   account/credential needs to be set up — don't just say "access denied."
4. For every item under "NOT checkable from a script" in that doc, ask me
   directly whether I can currently do it (sign into the Google account,
   open the Apps Script editor, open Streamlit Cloud settings, etc.) — don't
   assume either way.
5. Give me a short PASS/FAIL/UNKNOWN summary at the end, plus a prioritized
   list of what to fix first if anything failed.

Do not send any real email, push to origin, change any live Google Sheet
cell, or flip the GitHub repo's visibility while doing this — read-only
checks only. Ask me before anything that writes or sends.
```

## What "access" means here, system by system

| # | System | Who/what it is | Where the credential lives | Script-checkable? |
|---|--------|-----------------|------------------------------|--------------------|
| 1 | Google account `CCSM.PMG.Compass@gmail.com` | Owns the `COMPASS_CCSM` Sheet, the Nightly/Weekly/Suggestions Google Forms, and the bound Apps Script project (all 30 `CCSM_*.gs` agents) | Google sign-in only — no key file | No — sign-in only, human confirms |
| 2 | GCP service account | Programmatic read/write to `COMPASS_CCSM` via `gspread`, used by the Streamlit app, `tools/probe_live.py`, and this checklist's own script | `dashboard/.streamlit/secrets.toml` (`[gcp_service_account]`), mirrored in `dashboard/.env` (`GOOGLE_SHEETS_CREDENTIALS_JSON`) and in the GitHub repo's own Actions secrets | Yes — check 1/7 |
| 3 | GitHub org/repo `ccsmpmgcompass-collab/ccsm-pmg-compass` | Where all code lives; Streamlit Cloud auto-deploys from `main` on every push | SSH key (this machine uses host alias `github.com-ccsm`, separate from any Provo key) or a PAT typed into Git Credential Manager | Pull: yes (check 2/7). Push: no — run a real `git push` once |
| 4 | GitHub repo visibility | Streamlit Cloud's free tier can only *clone* a **public** repo — every reboot/redeploy re-clones, not just first connect | GitHub repo Settings → Danger Zone | Yes — check 3/7 (read-only; flipping it is a manual, deliberate step) |
| 5 | `GITHUB_ACTIONS_TOKEN` | Fine-grained PAT the Streamlit app uses (`app/integrations/github_actions.py`) to fire the `transfer-roster-pull` workflow via the GitHub API | `dashboard/.streamlit/secrets.toml` | Yes — check 4/7 (never prints the token, only whether it authenticates) |
| 6 | Streamlit Community Cloud account | Owns the deployed app (`ccsm-pmg-compass-….streamlit.app`) — Settings > Secrets, Reboot, Logs, and the Share/invite list (a **separate** allowlist from the code-level one in `auth.py`) | Cloud account sign-in only | No — human confirms by logging in and checking Manage app |
| 7 | Dashboard `GEMINI_API_KEY` | Powers the Home page chatbot only | `dashboard/.streamlit/secrets.toml` | Yes — check 5/7 (cheap `listModels` call, doesn't burn generation quota) |
| 8 | Apps Script's own Gemini key | Powers `CCSM_Agent1C.gs`'s leadership coaching narratives — **a different key, different quota bucket** than #7 | Apps Script project → Project Settings → Script Properties (inside the Apps Script editor itself) | No — only visible from inside the Apps Script editor (needs #1) |
| 9 | IMOS portal credentials | Missionary-org intranet login the Playwright transfer-roster scraper signs into | `dashboard/.env` (`CCSM_IMOS_USERNAME`/`CCSM_IMOS_PASSWORD`), duplicated in the GitHub repo's Actions secrets | Presence only — check 6/7. A real login isn't attempted automatically (2FA/lockout risk) |
| 10 | Relay Gmail Web Apps (`RELAY_1_URL`/`RELAY_2_URL`) | Separate Apps Script Web App deployments (each under its own Google account) that route outbound mission mail around Gmail's 100/day quota | Values live in the **live `COMPASS_CCSM` sheet**, `AGENT_CONFIG` tab — not in this repo at all | Format only — check 7/7 points you at `tools/probe_live.py config` |

## Not checkable from a script — confirm these by hand

- Signed in as `CCSM.PMG.Compass@gmail.com` (or has been added as an editor)
  and can actually open **Extensions → Apps Script** on `COMPASS_CCSM`.
- Can paste a `.gs` file's full contents into that editor and run a function
  from the dropdown (e.g. `smokeTestPipeline`) — editing this repo's `.gs`
  files does **nothing live** on its own; see `CCSM_DEPLOYMENT.md`.
- Apps Script → Project Settings → Script Properties has its own Gemini key
  set (item #8 above) — check by opening it, don't assume it matches #7.
- `git push` actually succeeds, not just `git ls-remote` (the script only
  proves read access — SSH/PAT auth can be pull-only).
- Can log into Streamlit Community Cloud and see this app under "Your apps",
  open Settings → Secrets (values match `dashboard/.streamlit/secrets.cloud.toml`),
  and use Reboot / Manage app / Logs.
- Can reach whichever Gmail account(s) own the relay Web App deployments, in
  case a relay needs to be redeployed (see `reference-agent-config-relay-email-test`
  memory for the payload shape a working relay expects).

## Running the automated half

```
cd dashboard
venv\Scripts\python.exe tools\check_handoff_access.py
```

Add `--out report.txt` to also save the output. Exit code is non-zero if any
automated check failed. Nothing it does writes to the sheet, sends email,
pushes code, or changes repo visibility — it is read-only by design, same
rule as `tools/probe_live.py`.

## If a check fails

- **Sheet read fails** → the service account key in `secrets.toml`/`.env` is
  stale, wrong project, or was never shared onto `COMPASS_CCSM`. Regenerate
  from the GCP project in item #2's row, or re-share the sheet with the
  existing `client_email`.
- **git pull fails** → no SSH key/PAT configured for this account against
  `ccsmpmgcompass-collab`. Set one up the same way the original deploy did
  (see `project-ccsm-streamlit-dashboard` memory: a fine-grained PAT scoped
  to just this repo, typed directly into Git Credential Manager, never into
  a chat).
- **`GITHUB_ACTIONS_TOKEN` fails** → it's expired/revoked or scoped to an
  account that no longer has access. Issue a new fine-grained PAT (Contents:
  read, Actions: read/write on this repo) under whichever GitHub identity
  will hold long-term ownership, and paste it into both `secrets.toml` and
  the Streamlit Cloud secrets box.
- **Repo is private** → expected in steady state per the accepted tradeoff,
  but must be flipped public immediately before the next push or reboot, or
  Streamlit Cloud will fail with "Failed to download the sources for
  repository."
