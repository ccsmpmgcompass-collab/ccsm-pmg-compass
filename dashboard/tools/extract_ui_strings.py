"""Extract English UI strings from Streamlit calls so translation work is
driven by a generated list rather than by reading files and hoping."""

import ast
import sys
from pathlib import Path

UI_CALLS = {
    "markdown", "write", "caption", "header", "subheader", "title", "info",
    "warning", "error", "success", "button", "selectbox", "radio", "checkbox",
    "text_input", "text_area", "multiselect", "slider", "expander", "tabs",
    "metric", "toggle", "number_input", "date_input", "toast", "popover",
    "download_button", "link_button", "form_submit_button",
    "render_page_header", "render_section_label",
}
TEXT_KWARGS = {"label", "help", "placeholder", "title", "subtitle", "body"}


def _call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return ""


def extract(paths: list[str]) -> list[str]:
    found: set[str] = set()
    for p in paths:
        tree = ast.parse(Path(p).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node) not in UI_CALLS:
                continue
            args = list(node.args) + [
                k.value for k in node.keywords if k.arg in TEXT_KWARGS
            ]
            for a in args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    s = a.value.strip()
                    if len(s) > 1:
                        found.add(s)
    return sorted(found)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    targets = [str(p) for p in root.rglob("*.py")
               if "venv" not in p.parts and "__pycache__" not in p.parts
               and "tools" not in p.parts and "tests" not in p.parts]
    from app.i18n.es import ES
    for s in extract(targets):
        if s not in ES:
            print(f"    {s!r}: {s!r},")


if __name__ == "__main__":
    sys.exit(main())
