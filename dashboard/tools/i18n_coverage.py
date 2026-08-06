"""Report translation coverage so remaining work is a known number."""

from pathlib import Path

from app.i18n.es import ES
from tools.extract_ui_strings import extract, extract_unwrapped


def _targets() -> list[str]:
    """Every .py file that can render UI text. Excludes venv/__pycache__/
    tools/tests (never UI) and app/ingestion (backend automation — Playwright
    scrapers and sheet-write scripts with no Streamlit runtime and no t()
    calls of their own; their logger.info/.error/.warning calls collide with
    UI_CALLS by attribute name alone, which is a false positive here, not
    untranslated copy)."""
    root = Path(__file__).resolve().parent.parent
    return [str(p) for p in root.rglob("*.py")
            if "venv" not in p.parts and "__pycache__" not in p.parts
            and "tools" not in p.parts and "tests" not in p.parts
            and "ingestion" not in p.parts]


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
