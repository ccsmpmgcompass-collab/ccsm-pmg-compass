"""Isolation guards. These are the executable form of the project's core
promise: the CCSM dashboard shares no code path with the Provo app."""
import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # dashboard/

CUT_PAGES = ["11_Reports.py", "12_Transfer_Flow.py", "14_Referrals.py"]


def _py_files():
    return [p for p in ROOT.rglob("*.py")
            if "__pycache__" not in p.parts and "venv" not in p.parts
            and "tests" not in p.parts]


def _module_to_path(mod: str):
    p = ROOT / (mod.replace(".", os.sep) + ".py")
    if p.exists():
        return p
    p2 = ROOT / mod.replace(".", os.sep) / "__init__.py"
    return p2 if p2.exists() else None


def test_no_import_escapes_dashboard():
    """Every `app.*` import must resolve to a file inside dashboard/."""
    unresolved = []
    for f in _py_files():
        tree = ast.parse(f.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.ImportFrom) and node.module \
                    and node.module.startswith("app"):
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                mods += [a.name for a in node.names if a.name.startswith("app")]
            for m in mods:
                if _module_to_path(m) is None:
                    unresolved.append(f"{f.relative_to(ROOT)} -> {m}")
    assert unresolved == [], f"imports escape dashboard/: {unresolved}"


def test_no_supabase_or_settings_reachable():
    """settings.py is the only Supabase entry point; it must stay unreachable."""
    offenders = [str(f.relative_to(ROOT)) for f in _py_files()
                 if "config.settings" in f.read_text(encoding="utf-8-sig")]
    assert offenders == [], f"settings.py became reachable: {offenders}"


def test_no_provo_sheet_reference():
    """The Provo sheet name must never appear in executable code.

    Provo *email* addresses are checked separately in test_auth_allowlist.py -
    auth.py is copied verbatim in this task and is Task 3's job to fix, so
    folding that assertion in here would make this task un-greenable.
    """
    hits = [f"{f.relative_to(ROOT)}" for f in _py_files()
            if "COMPASS_Main" in f.read_text(encoding="utf-8-sig")]
    assert hits == [], f"COMPASS_Main referenced in: {hits}"


def test_cut_pages_absent():
    for name in CUT_PAGES:
        assert not (ROOT / "pages" / name).exists(), f"{name} should be cut"


def test_miracles_removed():
    assert not (ROOT / "pages" / "15_Suggestions_&_Miracles.py").exists()
    p = ROOT / "pages" / "15_Sugerencias.py"
    assert p.exists(), "page should be renamed to 15_Sugerencias.py"
    assert "miracle_pdf" not in p.read_text(encoding="utf-8-sig")
    assert not (ROOT / "app" / "export").exists()


def test_no_references_to_missing_pages():
    """Every st.switch_page/st.page_link target must resolve to a real file.
    A rename or a cut page leaves callers pointing at nothing, which raises
    StreamlitAPIException at runtime for the user who clicks it.

    Parses the calls with ast rather than string-matching, so it only flags
    real switch_page/page_link invocations (not the word appearing in a
    comment or docstring) and isn't fooled by whitespace/line-wrapping.
    """
    bad = []
    for f in _py_files():
        tree = ast.parse(f.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if name not in ("switch_page", "page_link"):
                continue
            if not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                target = arg.value
                if target.endswith(".py") and not (ROOT / target).exists():
                    bad.append(f"{f.relative_to(ROOT)} -> {target}")
    assert bad == [], f"references to nonexistent pages: {bad}"
