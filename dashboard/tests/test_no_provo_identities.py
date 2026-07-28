"""Guards against Provo (a different mission's) people reaching CCSM's app.

Task 3 cleaned auth.py's _ALWAYS_ALLOWED but the real allowlist is a UNION with
get_allowed_emails(), which separately hardcoded two Provo addresses - so the
security property was still broken while the auth tests were green. These tests
check the property where it actually holds, not where it was convenient to look.
"""
import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent

PROVO_IDENTITIES = [
    "jason.ellis2@churchofjesuschrist.org",
    "naomi.ellis@churchofjesuschrist.org",
    "pmg.compass@gmail.com",       # Provo's system account
    "Sister Ellis",
]


def _py_files():
    return [p for p in ROOT.rglob("*.py")
            if "__pycache__" not in p.parts and "venv" not in p.parts
            and "tests" not in p.parts]


def test_no_provo_identity_anywhere_in_source():
    """Note 'pmg.compass@gmail.com' is a substring of CCSM's own
    'ccsm.pmg.compass@gmail.com', so match on a boundary, not a bare substring."""
    hits = []
    for f in _py_files():
        text = f.read_text(encoding="utf-8-sig")
        for ident in PROVO_IDENTITIES:
            for m in re.finditer(re.escape(ident), text, re.I):
                start = m.start()
                preceding = text[start - 1] if start > 0 else " "
                if preceding.isalnum() or preceding in "._-":
                    continue          # part of a longer, different identifier
                line = text[:start].count("\n") + 1
                hits.append(f"{f.relative_to(ROOT)}:{line}: {ident}")
    assert hits == [], f"Provo identities present: {hits}"


def test_get_allowed_emails_adds_nothing_hardcoded(monkeypatch):
    """The runtime check: with an EMPTY MISSION_ORG, the allowlist must be
    empty. Anything appearing here was injected by code, not by the sheet."""
    import app.db.queries as q
    monkeypatch.setattr(q, "get_areas_df", lambda: pd.DataFrame())
    assert q.get_allowed_emails() == set()


def test_allowlist_union_has_no_provo_accounts(monkeypatch):
    """Belt and braces: the actual union auth.py computes must be Provo-free."""
    import app.db.queries as q
    from app.auth.auth import _ALWAYS_ALLOWED
    monkeypatch.setattr(q, "get_areas_df", lambda: pd.DataFrame())
    allowed = {e.lower() for e in _ALWAYS_ALLOWED} | {
        e.lower() for e in q.get_allowed_emails()}
    provo = {"jason.ellis2@churchofjesuschrist.org",
             "naomi.ellis@churchofjesuschrist.org",
             "pmg.compass@gmail.com"}
    assert allowed & provo == set(), f"Provo accounts can sign in: {allowed & provo}"
