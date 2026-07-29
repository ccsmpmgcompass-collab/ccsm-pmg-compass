"""Report translation coverage so remaining work is a known number."""

from pathlib import Path

from app.i18n.es import ES
from tools.extract_ui_strings import extract


def report() -> tuple[int, int, list[str]]:
    root = Path(__file__).resolve().parent.parent
    targets = [str(p) for p in root.rglob("*.py")
               if "venv" not in p.parts and "__pycache__" not in p.parts
               and "tools" not in p.parts and "tests" not in p.parts]
    found = extract(targets)
    missing = [s for s in found if s not in ES or not ES[s].strip()]
    return len(found) - len(missing), len(found), missing


if __name__ == "__main__":
    done, total, missing = report()
    pct = (100 * done / total) if total else 100.0
    print(f"Translated {done}/{total} ({pct:.1f}%)")
    for s in missing[:40]:
        print("  MISSING:", s)
