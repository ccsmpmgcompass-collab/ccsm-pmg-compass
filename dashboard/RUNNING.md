# Running the CCSM Dashboard Locally

Standalone Streamlit dashboard for the Chile Concepción South Mission (CCSM),
reading from the `COMPASS_CCSM` Google Sheet. This is a separate deployment
from Provo's PMG Compass dashboard — same codebase lineage, different sheet,
different secrets, different port.

## 1. Create the venv

From this directory (`dashboard/`):

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

`venv/` is gitignored and must be recreated on every machine you clone this
repo onto — it is never committed.

## 2. Why `streamlit==1.40.0` is pinned exactly

`requirements.txt` pins `streamlit==1.40.0`, not `>=1.40.0`. Newer Streamlit
releases (confirmed through 1.59.1) have a `st.selectbox` regression: clicking
a searchable selectbox fails to clear the existing input, so typed characters
append to the current selection instead of replacing it and searching. This
breaks every searchable dropdown in the app (area pickers, zone/district
pickers, etc.). 1.40.0 is confirmed bug-free via direct browser testing.

**Do not loosen this pin** without re-testing selectbox click-and-type
behavior in a real browser first.

## 3. Secrets

`dashboard/.streamlit/secrets.toml` is **gitignored and untracked**. It does
not exist after a fresh clone — you must create it yourself (copy from a
teammate's machine or from the mission's credential store, never commit it).

Required keys:

| Key | Purpose |
|---|---|
| `COMPASS_SHEET_NAME` | Name of the Google Sheet to read (`"COMPASS_CCSM"` for this mission). |
| `gcp_service_account` | Full service-account JSON block (type, project_id, private_key, client_email, etc.) — the credential used to read the Sheet via gspread. |

Optional keys:

| Key | Purpose |
|---|---|
| `GEMINI_API_KEY` | Enables the AI assistant features. Leave blank to disable them — the app degrades gracefully and surfaces a Gemini-related error/notice on the affected feature only, it does not crash the app. |
| `STREAMLIT_DEV_EMAIL` | Local-only auth bypass. See the warning below. |

> **`STREAMLIT_DEV_EMAIL` must be absent or blank in production.** It
> completely bypasses BOTH the Google SSO check and the allowlist whenever it
> is non-blank (`app/auth/auth.py:63-68`). It is required for local
> development. If it is set in the production `secrets.toml` on Streamlit
> Cloud, anyone who reaches the URL is admitted as that user.

## 4. Port convention

Run this app on **port 8502**, not the default 8501:

```
venv\Scripts\streamlit run Home.py --server.port 8502
```

Provo's PMG Compass dev app runs on 8501. Both dashboards need to run
side by side during development (e.g. comparing behavior, or one developer
running both missions locally at once), so CCSM is fixed to 8502 by
convention to avoid a port collision. There is no port setting in
`.streamlit/config.toml` — pass `--server.port` on the command line every
time, or set it in your own local launch script.

## 5. Running the tests

```
venv\Scripts\python.exe -m pytest tests/ -q
```

11 tests, all passing as of 2026-07-28. Always invoke the venv's own
`python.exe` explicitly — a bare `python`/`pytest` on PATH can silently hit a
different, unpinned interpreter.

## Known state (as of 2026-07-28)

CCSM launched 2026-07-27; no missionary has submitted a report yet. This is
expected, not a bug. As a result:

- `DAILY_LOG`, `WEEKLY_BREAKDOWNS`, `GOALS_CONFIG`, `NIGHTLY_FORM_RAW`,
  `WEEKLY_FORM_RAW` are all 0 rows.
- `MISSION_ORG`, `LIVE_SNAPSHOT`, `SCORES` are populated (98 rows each —
  mission structure exists).
- `DASHBOARD_SUMMARY` has 360 rows.
- Every page shows a red **TEST MODE** banner — correct, `TEST_MODE=TRUE` in
  sheet config.
- `Home.py` may surface a Gemini-related notice because `GEMINI_API_KEY` is
  deliberately left blank in this mission's secrets — expected, not a finding.

All 10 entry points were exercised against the live `COMPASS_CCSM` sheet
using `streamlit.testing.v1.AppTest` (one subprocess per page, 180s timeout
each). **All 10 rendered without raising** — 8 render as "empty" (no data yet,
by design) and 2 (`Home.py`, `pages/18_Mantenimiento.py`) render as "clean"
(real content). Full per-page results, including which Streamlit elements
each page produced, are in
`.superpowers/sdd/2026-07-28-ccsm-streamlit-dashboard/task-4-report.md`.

Two pages worth a second look next time real data flows in (not bugs, just
noted for whoever fixes things after data arrives):

- `pages/04_Desgloses.py` has a mojibake character (`�`) in its selector
  help text — cosmetic, an encoding artifact in the source string.
- `pages/06_Puntajes.py` shows "No daily activity data yet" even though
  `SCORES` itself has 98 rows — worth confirming that's intentional (scores
  gated on daily activity) once real `DAILY_LOG` rows exist.
