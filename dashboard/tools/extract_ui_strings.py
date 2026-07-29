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
import keyword
import re
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


def _placeholder_name(expr: ast.AST, used: set) -> str:
    """Derive a readable {placeholder} name from the interpolated expression.

    The name becomes part of the translator-facing key, so it has to be stable
    and meaningful: `{area}` tells a translator what will appear there,
    `{v0}` does not.
    """
    if isinstance(expr, ast.Name):
        base = expr.id
    elif isinstance(expr, ast.Attribute):
        base = expr.attr
    elif isinstance(expr, ast.Subscript) and isinstance(expr.slice, ast.Constant) \
            and isinstance(expr.slice.value, str):
        base = expr.slice.value
    elif isinstance(expr, ast.Call):
        # A call's own name is usually the worst available label: nobody
        # translating a string is helped by "{get_config_value}" or
        # "{strftime}". Prefer what the call is ABOUT.
        fn = expr.func
        first_str = next((a.value for a in expr.args
                          if isinstance(a, ast.Constant) and isinstance(a.value, str)), None)
        if _call_name(expr) == "len":
            base = "count"
        elif isinstance(fn, ast.Attribute) and isinstance(fn.value, (ast.Name, ast.Attribute)):
            # obj.method(...) -> name it after the object: _monday.strftime() -> monday
            base = fn.value.id if isinstance(fn.value, ast.Name) else fn.value.attr
        elif first_str:
            # get_config_value("MISSION_NAME", ...) -> mission_name
            base = first_str
        else:
            base = _call_name(expr) or "value"
    else:
        base = "value"
    base = re.sub(r"\W+", "_", str(base)).strip("_").lower() or "value"
    if base[0].isdigit():
        base = f"v_{base}"
    if keyword.iskeyword(base):
        # `t("...", class=x)` is a SyntaxError, and the template and the kwarg
        # must agree, so the rename has to happen here where both are derived.
        base = f"{base}_"
    name, i = base, 2
    while name in used:
        name, i = f"{base}{i}", i + 1
    used.add(name)
    return name


def fstring_template(node: ast.JoinedStr) -> tuple[str, list]:
    """Turn an f-string into a (template, [(name, expr_node), ...]) pair.

    Shared with the codemod on purpose: if the extractor derived the key one
    way and the rewriter another, the gate would demand a translation for a
    key the app never looks up - green scan, English page.

    Literal braces are re-escaped to {{ }} because ast has already decoded
    them, and str.format() would otherwise read them back as placeholders.
    """
    used: set = set()
    parts: list[str] = []
    fields: list = []
    for v in node.values:
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            parts.append(v.value.replace("{", "{{").replace("}", "}}"))
        elif isinstance(v, ast.FormattedValue):
            name = _placeholder_name(v.value, used)
            conv = f"!{chr(v.conversion)}" if v.conversion and v.conversion != -1 else ""
            spec = ""
            if v.format_spec is not None:
                spec_txt = "".join(
                    c.value for c in v.format_spec.values
                    if isinstance(c, ast.Constant) and isinstance(c.value, str)
                )
                spec = f":{spec_txt}"
            parts.append(f"{{{name}{conv}{spec}}}")
            fields.append((name, v.value))
    return "".join(parts), fields


_HTML_TAG = re.compile(r"<[A-Za-z/!]")


def is_translatable_fstring(node: ast.JoinedStr) -> bool:
    """True when an f-string carries real prose rather than markup or pure
    interpolation.

    Excludes inline HTML/CSS - this app builds a lot of its layout with
    f-string <div> blocks, and those are structure, not copy.
    """
    literal = "".join(v.value for v in node.values
                      if isinstance(v, ast.Constant) and isinstance(v.value, str))
    if _HTML_TAG.search(literal) or "!important" in literal or "data-testid" in literal:
        return False
    return bool(re.search(r"[A-Za-z]{2,}", literal))


def _translates_via_format_func(node: ast.Call) -> bool:
    """True when the widget renders its options through t().

    Options whose VALUE is load-bearing - written to COMPASS_CCSM, compared
    with ==, or used as a lookup key - must stay English, so they cannot be
    wrapped in t() directly. The correct Streamlit idiom is to keep the option
    list English and pass format_func=t, which translates the label only. Such
    options are fully handled, so they are not "unwrapped"; they still need ES
    entries, which is why extract() keeps collecting them.
    """
    for k in node.keywords:
        if k.arg != "format_func":
            continue
        if isinstance(k.value, ast.Name) and k.value.id == TRANSLATE_FN:
            return True
        for sub in ast.walk(k.value):
            if isinstance(sub, ast.Call) and _call_name(sub) == TRANSLATE_FN:
                return True
    return False


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
    matter how complete ES is, so they are tracked separately from coverage.

    Includes f-strings. An f-string is a JoinedStr rather than a Constant, so
    for a long time it was invisible here AND absent from extract()'s
    denominator - the gate could not report it missing because it never knew
    it existed. Each is reported as the template it will become, so the entry
    doubles as a preview of the ES key the conversion will need.
    """
    found: set[str] = set()
    for _, tree in _walk(paths):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node) not in UI_CALLS:
                continue
            args = _ui_call_args(node)
            if _translates_via_format_func(node):
                # Options are rendered through t(); only the widget's own
                # label/help text can still be unwrapped here.
                args = [a for a in args if not any(
                    a is e for x in node.args if isinstance(x, ast.List)
                    for e in x.elts)]
            found.update(_literals(args))
            for a in args:
                if isinstance(a, ast.JoinedStr) and is_translatable_fstring(a):
                    found.add(fstring_template(a)[0])
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
