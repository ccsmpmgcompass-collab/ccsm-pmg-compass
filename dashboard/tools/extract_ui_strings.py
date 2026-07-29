"""Extract English UI strings from Streamlit calls so translation work is
driven by a generated list rather than by reading files and hoping.

Two questions have to be answered separately, and conflating them is how a
retrofit like this ends up silently green:

  1. Is every user-facing literal routed through t()?   -> extract_unwrapped()
  2. Does every routed literal have a Spanish entry?    -> extract() vs ES

Measuring only (2) against UI-call arguments would be self-defeating: wrapping
a literal in t() turns it into an argument of `t` rather than of `st.info`, so
the string disappears from that scan entirely. A file could be fully wrapped
with an empty ES dict and report 100% translated while rendering English.
"""

import ast
import sys
from pathlib import Path

UI_CALLS = {
    "markdown", "write", "caption", "header", "subheader", "title", "info",
    "warning", "error", "success", "button", "selectbox", "radio", "checkbox",
    "text_input", "text_area", "multiselect", "slider", "expander", "tabs",
    "metric", "toggle", "number_input", "date_input", "toast", "popover",
    "download_button", "link_button", "form_submit_button", "spinner",
    "file_uploader",
    "render_page_header", "render_section_label",
}
TEXT_KWARGS = {"label", "help", "placeholder", "title", "subtitle", "body"}

# Calls whose *choices* are user-visible too. Their options arrive as a list
# literal, so they are unreachable by the plain positional-arg scan below and
# were silently absent from the coverage denominator until this was added.
CHOICE_CALLS = {
    "selectbox", "radio", "multiselect", "tabs", "segmented_control",
    "select_slider", "pills",
}

TRANSLATE_FN = "t"


def _is_stylesheet(s: str) -> bool:
    """A `<style>` block reaches st.markdown as a string but is CSS, not UI
    copy. Counting it would put a 2KB stylesheet in the translator's queue and
    in the coverage denominator.

    Deliberately matched on the `<style>` prefix alone rather than on "starts
    with `<`": every one of the four blocks in this app is a pure stylesheet,
    and a looser rule would silently swallow real markup-wrapped prose such as
    "<b>Warning</b> - check this" instead of surfacing it for translation.
    """
    return s.strip().startswith("<style>")


def _call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return ""


def _literals(nodes) -> list[str]:
    out = []
    for a in nodes:
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            s = a.value.strip()
            if len(s) > 1 and not _is_stylesheet(s):
                out.append(s)
    return out


def _ui_call_args(node: ast.Call) -> list:
    """Positional args, recognised text kwargs, and one level into option
    lists. Option lists built from sheet data are left alone - that is mission
    content, already Spanish, and translating it again would corrupt the very
    values used to look data up."""
    args = list(node.args) + [
        k.value for k in node.keywords if k.arg in TEXT_KWARGS
    ]
    if _call_name(node) in CHOICE_CALLS:
        for a in list(args):
            if isinstance(a, ast.List):
                args.extend(a.elts)
    return args


def _walk(paths: list[str]):
    for p in paths:
        yield p, ast.parse(Path(p).read_text(encoding="utf-8-sig"))


def extract(paths: list[str]) -> list[str]:
    """Every translatable literal: those still passed straight to a UI call,
    plus those already routed through t(). This is the denominator ES must
    cover."""
    found: set[str] = set()
    for _, tree in _walk(paths):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name == TRANSLATE_FN:
                found.update(_literals(node.args[:1]))
            elif name in UI_CALLS:
                found.update(_literals(_ui_call_args(node)))
    return sorted(found)


def extract_unwrapped(paths: list[str]) -> list[str]:
    """Literals still handed straight to a UI call. These render English no
    matter how complete ES is, so they are tracked separately from coverage."""
    found: set[str] = set()
    for _, tree in _walk(paths):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) in UI_CALLS:
                found.update(_literals(_ui_call_args(node)))
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
