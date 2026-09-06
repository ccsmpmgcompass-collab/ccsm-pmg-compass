# Deploying the CCSM Dashboard to Streamlit Community Cloud

Companion to `RUNNING.md` (which covers local dev only). The step-by-step
walkthrough with checkboxes lives at `Desktop\CCSM Streamlit Deployment Guide.html`;
this file is the version that travels with the repo.

## Settings that must be exact

| Setting | Value | Why |
|---|---|---|
| Branch | `main` | Deploy from a stable branch, not a feature branch. |
| Main file path | `dashboard/Home.py` | The app is a subdirectory of the CCSM repo. |
| Dependencies | `dashboard/requirements.txt` | Found automatically — Streamlit Cloud looks in the repo root **or** the entrypoint's own directory. Nothing to configure. |
| Python version | Highest offered in the dropdown | Local dev runs 3.14.4. `streamlit==1.40.0` declares `>=3.8`, so any offered version satisfies it; if the build fails installing wheels, drop one version and redeploy. |
| Sharing | **Only specific people can view this app** | Not cosmetic — see below. |

## Why the app must be private

`app/auth/auth.py` is two layers: Streamlit Cloud SSO establishes *who you are*,
then the code allowlist decides *whether you get in*. On a **public** app there
is no signed-in identity, so `st.experimental_user.email` returns Streamlit's
placeholder `test@example.com`, which is in no allowlist — every visitor is
denied. Private + invited viewers is what makes layer 1 produce a real email.

## Secrets

Paste `.streamlit/secrets.cloud.toml` (gitignored, generated from your local
`secrets.toml`) into **App settings → Secrets**. To regenerate it after
rotating a credential, re-run the generator described in the HTML guide.

**`STREAMLIT_DEV_EMAIL` must never appear there.** Non-blank, it bypasses both
SSO and the allowlist (`auth.py`), admitting anyone with the URL as that user.
`tests/test_sso_viewer.py` asserts the generated template doesn't contain it.

## Who can sign in

Verified against the live `COMPASS_CCSM` sheet on 2026-07-29: **98 accounts** —
97 `@missionary.org` area mailboxes from `MISSION_ORG` plus
`ccsm.pmg.compass@gmail.com`. `get_allowed_emails()` returns *every* companion
email, not only APs.

**No `churchofjesuschrist.org` address is on that list**, so mission leadership
is locked out until added to `_ALWAYS_ALLOWED` in `auth.py`. There is a marked,
commented-out slot for the Mission President.

Note that an area mailbox only works as a login if `@missionary.org` is
Google-backed. If a missionary can't complete Google sign-in, add their personal
Google address to `_ALWAYS_ALLOWED` instead — being in `MISSION_ORG` grants
allowlist membership, not the ability to authenticate.

## The `st.user` trap

Do not "modernise" `_resolve_viewer()` to `st.user`. It does not exist before
Streamlit 1.42 (the pinned 1.40.0 raises `AttributeError` for every visitor),
and from 1.42 on it deliberately stops returning a Community Cloud account
email unless you run your own OIDC provider. `tests/test_sso_viewer.py` fails
on the broken form — verified by reverting it, not assumed.

## Reboot after any deploy that changes a file outside `views/`

**A git push is not enough.** Streamlit Cloud keeps one long-lived Python
process per app. Its file watcher re-executes a **page script** when the file
changes, but a module the page *imports* stays in `sys.modules` from whenever
the process last started. A deploy that changes both — a page and a module it
imports — leaves the new page running against the old module.

That is not theoretical. Commit `cf28071` added `can_set_goals` to
`app/auth/auth.py` and, in the same commit, the `from app.auth.auth import
can_set_goals, require_auth` at the top of `views/02_Metas.py`. The page
reloaded; the auth module did not. Every visit to Metas then died with:

```
ImportError: cannot import name 'can_set_goals' from 'app.auth.auth'
```

The tell is the traceback shape: it ends **at** the import line with no frames
beneath it. A module that genuinely fails to import shows its own frames below;
a name missing from an already-cached module does not.

**Fix, and the routine from now on:** App settings → **Reboot app** after any
deploy touching `app/`, `Home.py`, or anything else outside `views/`. Changing
only a page's own body is the one case where the push alone is sufficient.

Nothing in the repository can prevent this — it is a property of how the Cloud
runner reloads. Do not paper over it with try/except around an import: that
converts a loud, accurate error into a page that silently loses a feature.

## Verify after deploying

Runtime checks only; the local suite cannot see any of these:

1. Sign in as an invited, allowlisted account → dashboard loads.
2. Sign in as an invited account that is **not** allowlisted → "not approved".
3. Red **TEST MODE** banner names `CCSM.PMG.Compass@gmail.com`.
4. Header reads Chile Concepción South Mission; browser tab starts `CCSM ·`.
5. Language switch flips the UI to Spanish.

## Remaining dependency on Provo

`gcp_service_account` in the secrets is still Provo's
(`pmg-compass-dashboard@gen-lang-client-0214221824...`). The app works with it;
swapping it for a CCSM-owned service account and removing Provo's Editor access
on `COMPASS_CCSM` is the last gate in `Desktop\CCSM Independence Handoff Guide.html`.
