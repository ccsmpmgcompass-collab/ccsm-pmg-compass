import re
from pathlib import Path

AUTH = Path(__file__).resolve().parent.parent / "app" / "auth" / "auth.py"


def _allowlist_block() -> str:
    text = AUTH.read_text(encoding="utf-8-sig")
    m = re.search(r"_ALWAYS_ALLOWED\s*=\s*\{(.*?)\}", text, re.S)
    assert m, "_ALWAYS_ALLOWED literal not found"
    return m.group(1)


def test_no_provo_accounts_in_allowlist():
    block = _allowlist_block().lower()
    # Check for Provo email addresses as complete quoted strings (not substrings of CCSM account)
    for bad in ('pmg.compass@gmail.com', 'jason.ellis2@churchofjesuschrist.org', 'naomi.ellis@churchofjesuschrist.org'):
        assert f'"{bad}"' not in block, f"Provo account {bad} still allowlisted"


def test_ccsm_account_present():
    assert "ccsm.pmg.compass@gmail.com" in _allowlist_block().lower()
