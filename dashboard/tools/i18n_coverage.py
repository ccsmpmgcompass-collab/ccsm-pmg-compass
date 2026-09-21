"""Report translation coverage so remaining work is a known number."""

from pathlib import Path

from app.i18n.es import ES
from tools.extract_ui_strings import extract, extract_unwrapped


#: A file carrying this marker writes its own Spanish and is not measured for
#: translation coverage. Opt-in and per-file on purpose: the guard's whole job
#: is to catch English leaking into a Spanish UI, and a blanket exclusion by
#: directory would take a dozen bilingual pages with it.
#:
#: `views/11_Informes.py` is the first and only one (PLAN-2026-09-21-informes.md,
#: decision 3 — Zackary's answer to Q3). Its audience is two Spanish-speaking
#: readers, its strings are the mission's own vocabulary, and routing forty
#: literals through `t()` would add forty English keys nobody will ever read.
#: The page says so in its own docstring.
SPANISH_ONLY_MARKER = "i18n: spanish-only"


def _targets() -> list[str]:
    """Every .py file that can render UI text.

    Excludes venv/__pycache__/tools/tests (never UI) and app/ingestion (backend
    automation — Playwright scrapers and sheet-write scripts with no Streamlit
    runtime and no t() calls of their own; their logger.info/.error/.warning
    calls collide with UI_CALLS by attribute name alone, which is a false
    positive here, not untranslated copy). Also excludes any file that declares
    SPANISH_ONLY_MARKER.
    """
    root = Path(__file__).resolve().parent.parent
    out = []
    for p in root.rglob("*.py"):
        if ({"venv", "__pycache__", "tools", "tests", "ingestion"}
                & set(p.parts)):
            continue
        if SPANISH_ONLY_MARKER in p.read_text(encoding="utf-8-sig"):
            continue
        out.append(str(p))
    return out


def spanish_only_files() -> list[str]:
    """The files that opted out, so a test can assert the list is deliberate."""
    root = Path(__file__).resolve().parent.parent
    return sorted(
        str(p.relative_to(root)).replace("\\", "/")
        for p in root.rglob("*.py")
        if not ({"venv", "__pycache__", "tools", "tests"} & set(p.parts))
        and SPANISH_ONLY_MARKER in p.read_text(encoding="utf-8-sig")
    )


def report() -> tuple[int, int, list[str]]:
    found = extract(_targets())
    missing = [s for s in found if s not in ES or not ES[s].strip()]
    return len(found) - len(missing), len(found), missing


def unwrapped() -> list[str]:
    """Literals still passed straight to a widget. Reported alongside coverage
    because a string can be 100% translated in ES and still render English if
    nothing routes it through t()."""
    return extract_unwrapped(_targets())


if __name__ == "__main__":
    done, total, missing = report()
    pct = (100 * done / total) if total else 100.0
    todo = unwrapped()
    print(f"Translated {done}/{total} ({pct:.1f}%)")
    print(f"Not yet routed through t(): {len(todo)}")
    for s in missing[:40]:
        print("  MISSING:", s)
