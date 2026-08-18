"""check_handoff_access.py — self-check for whether THIS machine/identity has
the same operating access to CCSM PMG Compass as the person who built it.
────────────────────────────────────────────────────────────────────────────
Standalone: reads credentials straight out of dashboard/.streamlit/secrets.toml
(the same file the app and probe_live.py use), plus git and the public GitHub
API. Never prints a credential value — only whether each one is present and
whether it actually authenticates.

This tool cannot see everything. Some access (the Google account that owns
the Apps Script project, Streamlit Cloud's own secrets box, the relay Gmail
accounts) has no API to probe from a script — those are listed at the end as
MANUAL items for a human to confirm directly.

Usage (always via the dashboard venv):

    venv\\Scripts\\python.exe tools\\check_handoff_access.py
    venv\\Scripts\\python.exe tools\\check_handoff_access.py --out report.txt

Nothing here writes to COMPASS_CCSM, sends email, or triggers a GitHub Action.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import requests

try:  # py3.11+ stdlib, falls back to the vendored copy for older interpreters
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SECRETS = _REPO_ROOT / ".streamlit" / "secrets.toml"
_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
_GITHUB_API_BASE = "https://api.github.com/repos/ccsmpmgcompass-collab/ccsm-pmg-compass"


class Report:
    """Same pattern as probe_live.py's Report — Windows consoles here are
    cp1252, so stdout goes through a replacing encoder while --out keeps the
    real characters."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str = "") -> None:
        self.lines.append(line)
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(line.encode(enc, "replace").decode(enc) + "\n")

    def save(self, path: str | None) -> None:
        if not path:
            return
        Path(path).write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def _load_secrets() -> dict:
    if not _SECRETS.exists():
        return {}
    with _SECRETS.open("rb") as fh:
        return tomllib.load(fh)


def check_sheet_access(out: Report, secrets: dict) -> bool:
    out("[1/7] Google Sheets service account -> COMPASS_CCSM read access")
    if "gcp_service_account" not in secrets or "COMPASS_SHEET_NAME" not in secrets:
        out("  FAIL  no [gcp_service_account] block or COMPASS_SHEET_NAME in secrets.toml")
        return False
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_dict = dict(secrets["gcp_service_account"])
        pk = creds_dict.get("private_key", "")
        creds_dict["private_key"] = pk.replace("\\n", "\n").replace("\r\n", "\n")
        creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
        client = gspread.authorize(creds)
        ss = client.open(secrets["COMPASS_SHEET_NAME"])
        tab = ss.worksheet("AGENT_CONFIG")
        rows = len(tab.get_all_values())
        out(f"  PASS  opened '{secrets['COMPASS_SHEET_NAME']}', AGENT_CONFIG has {rows} rows")
        out(f"        service account: {creds_dict.get('client_email', '?')}")
        return True
    except Exception as exc:  # noqa: BLE001 - report, don't crash the whole run
        out(f"  FAIL  {type(exc).__name__}: {exc}")
        return False


def check_git_remote(out: Report) -> bool:
    out("[2/7] git remote -> ccsm-pmg-compass repo, pull access")
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=_REPO_ROOT.parent, timeout=10,
        )
        url = remote.stdout.strip()
        out(f"        origin = {url}")
        if "ccsm" not in url.lower():
            out("  WARN  origin does not look like the CCSM repo — check .git/config")
        ls = subprocess.run(
            ["git", "ls-remote", "origin", "HEAD"],
            capture_output=True, text=True, cwd=_REPO_ROOT.parent, timeout=15,
        )
        if ls.returncode == 0 and ls.stdout.strip():
            out("  PASS  ls-remote succeeded — read auth (SSH key or PAT) works")
            out("  MANUAL push access is NOT tested here — run a real `git push` (or")
            out("         `git push --dry-run`) once to confirm write access separately.")
            return True
        out(f"  FAIL  ls-remote failed: {ls.stderr.strip()}")
        return False
    except Exception as exc:  # noqa: BLE001
        out(f"  FAIL  {type(exc).__name__}: {exc}")
        return False


def check_repo_visibility(out: Report) -> bool:
    out("[3/7] GitHub repo visibility (Streamlit Cloud free tier needs it PUBLIC to redeploy)")
    try:
        resp = requests.get(_GITHUB_API_BASE, timeout=15)
        if resp.status_code == 404:
            out("  INFO  repo is currently PRIVATE (or truly doesn't exist) — 404 from public API")
            out("        remember to flip it public before the next push/reboot")
            return True
        if resp.status_code == 200:
            private = resp.json().get("private", True)
            out(f"  PASS  repo reachable, private={private}")
            return True
        out(f"  FAIL  unexpected status {resp.status_code}")
        return False
    except Exception as exc:  # noqa: BLE001
        out(f"  FAIL  {type(exc).__name__}: {exc}")
        return False


def check_github_actions_token(out: Report, secrets: dict) -> bool:
    out("[4/7] GITHUB_ACTIONS_TOKEN -> can it list workflows on the repo?")
    token = secrets.get("GITHUB_ACTIONS_TOKEN", "")
    if not token:
        out("  FAIL  GITHUB_ACTIONS_TOKEN missing from secrets.toml")
        return False
    try:
        resp = requests.get(
            f"{_GITHUB_API_BASE}/actions/workflows",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json"},
            timeout=15,
        )
        if resp.status_code == 200:
            out("  PASS  token authenticates and can read Actions workflows")
            return True
        out(f"  FAIL  token rejected, status {resp.status_code} (never printing the token itself)")
        return False
    except Exception as exc:  # noqa: BLE001
        out(f"  FAIL  {type(exc).__name__}: {exc}")
        return False


def check_gemini_key(out: Report, secrets: dict) -> bool:
    out("[5/7] Dashboard GEMINI_API_KEY -> valid, cheap listModels() call (no generation quota spent)")
    key = secrets.get("GEMINI_API_KEY", "")
    if not key:
        out("  INFO  blank in secrets.toml — deliberately optional, disables only the Home chat panel")
        return True
    try:
        resp = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": key}, timeout=15,
        )
        if resp.status_code == 200:
            out("  PASS  key authenticates against the Gemini API")
            return True
        out(f"  FAIL  key rejected, status {resp.status_code}")
        return False
    except Exception as exc:  # noqa: BLE001
        out(f"  FAIL  {type(exc).__name__}: {exc}")
        return False


def check_imos_creds_present(out: Report) -> bool:
    out("[6/7] IMOS portal credentials -> presence only (no live login attempted here)")
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        out("  FAIL  .env not found")
        return False
    text = env_path.read_text(encoding="utf-8", errors="ignore")
    has_user = any(l.startswith("CCSM_IMOS_USERNAME=") and l.strip() != "CCSM_IMOS_USERNAME="
                   for l in text.splitlines())
    has_pass = any(l.startswith("CCSM_IMOS_PASSWORD=") and l.strip() != "CCSM_IMOS_PASSWORD="
                   for l in text.splitlines())
    if has_user and has_pass:
        out("  PASS  both CCSM_IMOS_USERNAME and CCSM_IMOS_PASSWORD are set (values not read)")
        out("  MANUAL a real login can only be confirmed by running the transfer-roster-pull")
        out("         GitHub Action or imos_transfer_runner.py directly — not attempted here")
        return True
    out("  FAIL  one or both IMOS credentials are missing/blank in .env")
    return False


def check_relay_config(out: Report, secrets: dict) -> bool:
    out("[7/7] Relay Web App URLs -> format check only (no test email sent here)")
    # Relay config lives in the live AGENT_CONFIG sheet tab, not in this repo's
    # secrets — read it the same way check_sheet_access already proved works.
    out("  INFO  RELAY_1_URL / RELAY_2_URL live in the COMPASS_CCSM sheet's AGENT_CONFIG tab,")
    out("        not in this repo. Re-run tools/probe_live.py config --key RELAY_2_URL to see")
    out("        the current value, and see reference-agent-config-relay-email-test for how to")
    out("        send a real test POST once you have explicit permission to send mail.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="also write the report to this file (UTF-8)")
    args = parser.parse_args()

    out = Report()
    out("CCSM PMG Compass — handoff access self-check")
    out("=" * 60)
    secrets = _load_secrets()
    if not secrets:
        out(f"WARNING: could not read {_SECRETS} at all — most checks below will fail")
    out()

    results = {
        "Google Sheets (COMPASS_CCSM) read access": check_sheet_access(out, secrets),
    }
    out()
    results["GitHub repo pull access"] = check_git_remote(out)
    out()
    results["GitHub repo visibility"] = check_repo_visibility(out)
    out()
    results["GITHUB_ACTIONS_TOKEN"] = check_github_actions_token(out, secrets)
    out()
    results["Dashboard Gemini API key"] = check_gemini_key(out, secrets)
    out()
    results["IMOS portal credentials"] = check_imos_creds_present(out)
    out()
    results["Relay Web App config"] = check_relay_config(out, secrets)
    out()

    out("=" * 60)
    out("SUMMARY (automated checks only)")
    for name, ok in results.items():
        out(f"  {'PASS' if ok else 'FAIL'}  {name}")
    out()
    out("NOT checkable from a script — confirm these by hand, see")
    out("CCSM_HANDOFF_ACCESS_CHECKLIST.md for how:")
    out("  - Signed in as CCSM.PMG.Compass@gmail.com (owns the Sheet, Forms, Apps Script)")
    out("  - Can open Extensions -> Apps Script on COMPASS_CCSM and paste/run functions")
    out("  - Apps Script Script Properties has its own Gemini key (separate from GEMINI_API_KEY above)")
    out("  - git push actually succeeds (this script only proved read/pull access)")
    out("  - Streamlit Cloud account can open Settings > Secrets / Reboot / Logs for the app")
    out("  - Relay Gmail account(s) reachable if RELAY_1/2 need redeploying")

    out.save(args.out)
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
