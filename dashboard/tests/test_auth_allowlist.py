import sys
from pathlib import Path

# Add dashboard directory to path so app.* imports work from parent directory
dashboard_dir = Path(__file__).resolve().parent.parent
if str(dashboard_dir) not in sys.path:
    sys.path.insert(0, str(dashboard_dir))

from app.auth.auth import _ALWAYS_ALLOWED

PROVO_ACCOUNTS = {
    "jason.ellis2@churchofjesuschrist.org",
    "naomi.ellis@churchofjesuschrist.org",
    "pmg.compass@gmail.com",
}


def test_no_provo_accounts_in_allowlist():
    """Assert against the real set, not its source text. A source-text check
    is fooled by quote style, spacing and line wrapping - and would have been
    fooled here, since "pmg.compass@gmail.com" is a substring of the CCSM
    account "ccsm.pmg.compass@gmail.com"."""
    normalized = {e.strip().lower() for e in _ALWAYS_ALLOWED}
    leaked = normalized & PROVO_ACCOUNTS
    assert leaked == set(), f"Provo accounts in CCSM allowlist: {leaked}"


def test_ccsm_account_present():
    normalized = {e.strip().lower() for e in _ALWAYS_ALLOWED}
    assert "ccsm.pmg.compass@gmail.com" in normalized
