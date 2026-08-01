"""Final verification of the CCSM bilingual dashboard.

These assert end-state properties of the whole app rather than any one task,
so a later change that quietly undoes one of them fails here.
"""

import re
from pathlib import Path

import pytest

from app.i18n.es import ES
from tools.extract_ui_strings import extract, extract_unwrapped
from tools.i18n_coverage import report, unwrapped

ROOT = Path(__file__).resolve().parent.parent


def test_translation_coverage_is_complete():
    done, total, missing = report()
    assert missing == [], f"{len(missing)} untranslated: {missing[:10]}"
    assert done == total and total > 400, (done, total)


def test_no_ui_literal_bypasses_translation():
    todo = unwrapped()
    assert todo == [], f"{len(todo)} literals never reach t(): {todo[:10]}"


def test_isolation_still_holds_after_the_retrofit():
    """The i18n work touched almost every file; re-assert the project's core
    promise rather than trusting that it survived."""
    offenders = []
    for p in ROOT.rglob("*.py"):
        if {"venv", "__pycache__", "tests"} & set(p.parts):
            continue
        text = p.read_text(encoding="utf-8-sig")
        if "COMPASS_Main" in text or "config.settings" in text:
            offenders.append(str(p.relative_to(ROOT)))
    assert offenders == [], offenders


def test_every_page_still_sets_a_ccsm_browser_title():
    """0e7af19 branded the tab because BOTH apps rendered an identical
    'PMG Compass' title and the user could not tell CCSM from Provo apart."""
    missing = []
    for p in [ROOT / "Home.py", *sorted((ROOT / "pages").glob("*.py"))]:
        if p.name == "__init__.py":
            continue
        text = p.read_text(encoding="utf-8-sig")
        if "page_title=" in text and "CCSM" not in text.split("page_title=")[1][:60]:
            missing.append(p.name)
    assert missing == [], f"pages without a CCSM-branded tab title: {missing}"


def test_spanish_never_reuses_an_english_placeholder_set():
    def fields(s):
        return set(re.findall(r"\{(\w+)\}", s))

    bad = [en for en, es in ES.items() if fields(en) != fields(es)]
    assert bad == [], f"placeholder mismatch in: {bad[:5]}"


def test_no_translation_is_left_blank():
    blank = [en for en, es in ES.items() if not es.strip()]
    assert blank == [], blank


@pytest.mark.parametrize("group", [
    ["Home.py"], ["pages/01_Panel.py"], ["pages/02_Metas.py"],
    ["pages/04_Desgloses.py"], ["pages/06_Puntajes.py"],
    ["pages/07_Embudo_de_Búsqueda.py"], ["pages/10_Notas.py"],
    ["pages/15_Sugerencias.py"], ["pages/17_Centro_de_Acción.py"],
    ["pages/18_Mantenimiento.py"],
])
def test_each_page_individually_complete(group):
    assert extract_unwrapped(group) == []
    assert [s for s in extract(group) if s not in ES] == []
