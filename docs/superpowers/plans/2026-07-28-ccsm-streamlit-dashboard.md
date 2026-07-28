# CCSM Streamlit Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a standalone, fully bilingual (EN/ES) Streamlit dashboard for the Chile Concepción South Mission inside the CCSM repo, reading `COMPASS_CCSM`, with zero shared code or runtime with the Utah Provo app.

**Architecture:** A `dashboard/` subfolder in the CCSM repo holds a self-contained copy of the Streamlit app — `Home.py`, 9 pages, and the 16-module import closure those pages actually reach. Isolation from Provo is enforced by an executable test, not by convention. Data targeting is a single secret (`COMPASS_SHEET_NAME = "COMPASS_CCSM"`). Bilingual UI runs through a `t()` lookup keyed on the English source string, so any missing translation degrades to English.

**Tech Stack:** Python 3, Streamlit 1.40.0 (pinned — see Global Constraints), gspread, pandas, plotly, pytest, google-genai.

## Global Constraints

- **Repo:** all work happens in `C:\Users\2011794-MTS\Desktop\Worldwide PMG Compass\CCSM PMG Compass`. The Provo repo `C:\Users\2011794-MTS\Desktop\PMG-Compass` is **read-only source material** — never modify, never commit to it.
- **Streamlit pin:** `streamlit==1.40.0` exactly. Newer releases through 1.59.1 have a `st.selectbox` regression where clicking a searchable selectbox fails to clear the input. Do not loosen. (Provo's working venv has drifted to 1.57.0 — do not copy that drift.)
- **Sheet:** `COMPASS_SHEET_NAME = "COMPASS_CCSM"`, ID `1DA1UHAZSGLFn5Dc1RtI_9g2Y0qYIibpFKVPt3SmFTaI`. The string `COMPASS_Main` must never appear in `dashboard/` outside an inert docstring.
- **No Supabase.** Nothing in the closure imports `app/config/settings.py`. If a task makes it reachable again, that is a defect.
- **Local port:** run on **8502**. Provo's dev app uses 8501; both must be able to run at once.
- **Python invocation:** always `dashboard/venv/Scripts/python.exe`, never bare `python` — a bare call hits a system install missing these packages.
- **Translation scope:** UI chrome only. Sheet-sourced content (metric labels, mission name, knowledge base, notes, area names) is already Spanish and must never pass through `t()`.
- **Live-system boundary:** this plan performs **no writes** to `COMPASS_CCSM` or any live system. Every sheet interaction is read-only. If a task appears to need a write, stop and ask.
- **Non-ASCII output:** mission data contains accented characters (`Chile Concepción South Mission`). Never pipe sheet output through `grep` — it treats the stream as binary and silently drops matching lines. Redirect to a file and read it instead. This exact trap produced a false "MISSION_NAME is missing" finding during planning.

---

### Task 1: Scaffold `dashboard/` and prove isolation

Copies the app and locks isolation behind a test in the same task, because a copy without the guard is not independently reviewable — the guard *is* the deliverable.

**Files:**
- Create: `dashboard/tests/test_isolation.py`
- Create: `dashboard/Home.py`, `dashboard/pages/` (9 pages + `__init__.py`)
- Create: `dashboard/app/` (16 modules + package markers + `app/config/flavors/*.json`)
- Create: `dashboard/requirements.txt`, `dashboard/.streamlit/config.toml`
- Modify: `.gitignore` (repo root)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: the `dashboard/` tree that every later task edits. Test module `dashboard/tests/test_isolation.py` exposing `test_no_import_escapes_dashboard`, `test_no_supabase_or_settings_reachable`, `test_no_provo_sheet_reference`, `test_cut_pages_absent`.

- [ ] **Step 1: Write the failing isolation test**

Create `dashboard/tests/test_isolation.py`:

```python
"""Isolation guards. These are the executable form of the project's core
promise: the CCSM dashboard shares no code path with the Provo app."""
import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # dashboard/

CUT_PAGES = ["11_Reports.py", "12_Transfer_Flow.py", "14_Referrals.py"]


def _py_files():
    """Exclude tests/ - this module's own source contains the very strings the
    guards search for ("config.settings", "COMPASS_Main"), so scanning it would
    make the guards permanently self-matching."""
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
```

- [ ] **Step 2: Run the test to verify it fails**

```powershell
cd "C:\Users\2011794-MTS\Desktop\Worldwide PMG Compass\CCSM PMG Compass"
python -m pytest dashboard/tests/test_isolation.py -v
```

Expected: collection error / failure — `dashboard/` has no app to check yet.

- [ ] **Step 3: Copy the closure from the Provo repo**

Copy exactly these, preserving directory structure, from `C:\Users\2011794-MTS\Desktop\PMG-Compass` into `dashboard/`:

Entry point and pages (9):
```
Home.py
pages/__init__.py
pages/01_dashboard.py
pages/02_Goals.py
pages/04_Breakdowns.py
pages/06_Scores.py
pages/07_Finding_Funnel.py
pages/10_Notes.py
pages/15_Suggestions_&_Miracles.py
pages/17_Action_Center.py
pages/18_Maintenance.py
```

Do **not** copy `pages/11_Reports.py`, `pages/12_Transfer_Flow.py`, `pages/14_Referrals.py`.

The 16-module closure (computed from the pages' actual imports, not guessed):
```
app/analytics/finding_funnel.py
app/analytics/trends.py
app/auth/auth.py
app/breakdowns_engine.py
app/chat/gemini_chat.py
app/components/design_system.py
app/components/scope_selector.py
app/config/flavor_loader.py
app/config/metrics.py
app/config/theme.py
app/db/action_center_queries.py
app/db/goals_queries.py
app/db/queries.py
app/db/sheets_client.py
app/utils/area_helpers.py
app/utils/logger.py
```

Package markers (all 0 bytes except `app/chat/__init__.py` at 23 bytes — copy it, don't recreate it):
```
app/__init__.py  app/analytics/__init__.py  app/auth/__init__.py
app/chat/__init__.py  app/components/__init__.py  app/config/__init__.py
app/db/__init__.py  app/utils/__init__.py
```

Data files `flavor_loader.py` reads at `Path(__file__).parent / "flavors"`:
```
app/config/flavors/*.json   (all 13)
```

Do **not** copy `app/export/`, `app/ingestion/`, `app/integrations/`, `app/reporting/`, `app/main.py`, or `app/config/settings.py`. `app/export/miracle_pdf.py` is reachable only from the Miracles tab removed in Task 2, so it is excluded here.

Also copy `requirements.txt` and `.streamlit/config.toml`, then delete from `dashboard/requirements.txt` the lines for packages no longer reachable: `reportlab`, `pypdf`, `pdfplumber`, `google-api-python-client`, `supabase`, `playwright`, `openpyxl` (keep any not present; do not add new pins).

- [ ] **Step 4: Add gitignore entries**

Append to the repo-root `.gitignore` (which currently holds only `node_modules/`, `*.xls`, `.superpowers/`):

```
dashboard/venv/
dashboard/.streamlit/secrets.toml
dashboard/**/__pycache__/
.pytest_cache/
```

- [ ] **Step 5: Run the test to verify it passes**

```powershell
python -m pytest dashboard/tests/test_isolation.py -v
```

Expected: 4 passed. If `test_no_supabase_or_settings_reachable` fails, a copied module still imports `app.config.settings` — find it and confirm whether it belongs in the closure at all rather than copying `settings.py` to silence the test.

- [ ] **Step 6: Commit**

```powershell
git add dashboard .gitignore
git commit -m "feat(dashboard): scaffold standalone CCSM Streamlit app

Copies Home.py, 9 pages, and the 16-module import closure those pages
actually reach (computed, not guessed) out of the Provo app. Reports,
Transfer Flow and Referrals are omitted - COMPASS_CCSM lacks their tabs.

app/config/settings.py falls outside the closure, so the CCSM dashboard
needs no Supabase at all. test_isolation.py enforces that and the rest of
the isolation promise as executable checks."
```

---

### Task 2: ~~Remove the Miracles tab from page 15~~ — ABSORBED INTO TASK 1

**Skip this task.** It was folded into Task 1 during execution and is a no-op.

**Why:** Task 1's `test_no_import_escapes_dashboard` cannot pass while
`pages/15_Suggestions_&_Miracles.py` still imports `app.export.miracle_pdf`,
and this task was what removed that import. Splitting them left Task 1 with no
green state — a sequencing defect in the plan as written. The work below was
performed as part of Task 1; it is retained for reference only.

---

<details>
<summary>Original Task 2 text (executed within Task 1)</summary>

### Remove the Miracles tab from page 15

**Files:**
- Modify: `dashboard/pages/15_Suggestions_&_Miracles.py` (drop the `from app.export.miracle_pdf import ...` at line 12 and the Miracles tab body around line 276)

**Interfaces:**
- Consumes: `dashboard/` tree from Task 1.
- Produces: a Suggestions-only page. No new symbols.

- [ ] **Step 1: Write the failing test**

Append to `dashboard/tests/test_isolation.py`:

```python
def test_miracles_removed():
    p = ROOT / "pages" / "15_Suggestions_&_Miracles.py"
    text = p.read_text(encoding="utf-8-sig")
    assert "miracle_pdf" not in text, "miracle_pdf import still present"
    assert not (ROOT / "app" / "export").exists(), "app/export should not exist"
```

- [ ] **Step 2: Run to verify it fails**

```powershell
python -m pytest dashboard/tests/test_isolation.py::test_miracles_removed -v
```

Expected: FAIL — `miracle_pdf` import still present.

- [ ] **Step 3: Remove the Miracles code**

Delete the `from app.export.miracle_pdf import correct_and_translate, build_miracle_pdf` import. Find the `st.tabs([...])` call that creates the Suggestions/Miracles split and collapse it so the page renders Suggestions directly without a tab container. Delete the entire Miracles tab body, including the `build_miracle_pdf(...)` download button. Rename the page file to `dashboard/pages/15_Suggestions.py`.

Update `CUT_PAGES` handling: add a check that `15_Suggestions_&_Miracles.py` no longer exists and `15_Suggestions.py` does.

- [ ] **Step 4: Run to verify it passes**

```powershell
python -m pytest dashboard/tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add dashboard
git commit -m "feat(dashboard): drop Miracles tab, COMPASS_CCSM has no Miracles tab

Removes the last consumer of app/export/, so the whole export package
stays out of the closure. Page renamed to 15_Suggestions.py."
```

</details>

### Task 2b: Correct the sheet name in user-facing text (done within Task 1)

Found during Task 1, not anticipated by this plan. `COMPASS_Main` appears in
**14 user-facing strings** — 12 in `18_Maintenance.py`, 1 in `06_Scores.py`, and
1 in `gemini_chat.py`'s Gemini system prompt. This is a correctness bug, not
cosmetics: the Maintenance page would instruct CCSM leadership to open **Provo's
spreadsheet** as their source of truth, and the system prompt would teach the
assistant the wrong data store.

Fix: replace the sheet-name token with `COMPASS_CCSM` in UI copy, the system
prompt, and docstrings alike. Change only the token — do not reword surrounding
prose. Do not touch `_get_spreadsheet()`'s `st.secrets["COMPASS_SHEET_NAME"]`
lookup; runtime targeting was already correct.

---

### Task 3: Point auth at CCSM

**Files:**
- Modify: `dashboard/app/auth/auth.py:23-27`
- Test: `dashboard/tests/test_auth_allowlist.py`

**Interfaces:**
- Consumes: `dashboard/app/auth/auth.py` from Task 1.
- Produces: `_ALWAYS_ALLOWED: set[str]` containing only CCSM accounts. `is_leadership(email) -> bool` and `require_auth() -> dict` keep their existing signatures.

**Decided 2026-07-28 — not an open item.** The user will add the Mission President's address themselves after handoff. Seed the allowlist with `CCSM.PMG.Compass@gmail.com` (the value in CCSM's `AGENT_CONFIG`) and leave the marked comment line in place permanently. **Do not wait on this, and do not invent an address** — the marked line is the deliverable, not a placeholder to be filled in later by an implementer.

- [ ] **Step 1: Write the failing test**

Create `dashboard/tests/test_auth_allowlist.py`:

```python
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
    for bad in ("jason.ellis2", "naomi.ellis", "pmg.compass@gmail.com"):
        assert bad not in block, f"Provo account {bad} still allowlisted"


def test_ccsm_account_present():
    assert "ccsm.pmg.compass@gmail.com" in _allowlist_block().lower()
```

- [ ] **Step 2: Run to verify it fails**

```powershell
python -m pytest dashboard/tests/test_auth_allowlist.py -v
```

Expected: FAIL — `jason.ellis2 still allowlisted`.

- [ ] **Step 3: Replace the allowlist**

In `dashboard/app/auth/auth.py`, replace the `_ALWAYS_ALLOWED` literal with:

```python
_ALWAYS_ALLOWED = {
    "ccsm.pmg.compass@gmail.com",   # CCSM system account (from AGENT_CONFIG)
    # TODO(CCSM): add the Mission President's churchofjesuschrist.org address.
    # Deliberately left unset - do not guess an address for an auth allowlist.
}
```

Update the module docstring's "Approved emails" section to describe CCSM rather than Provo.

- [ ] **Step 4: Run to verify it passes**

```powershell
python -m pytest dashboard/tests/ -v
```

Expected: all pass, including `test_no_provo_references` from Task 1.

- [ ] **Step 5: Commit**

```powershell
git add dashboard
git commit -m "feat(dashboard): replace Provo auth allowlist with CCSM accounts

The MP address is intentionally absent rather than guessed - an auth
allowlist is the wrong place for an assumption."
```

---

### Task 4: Configure, install, and get it running

**Files:**
- Create: `dashboard/.streamlit/secrets.toml` (gitignored — never committed)
- Create: `dashboard/venv/`
- Create: `dashboard/RUNNING.md`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: a launchable app; `dashboard/venv/Scripts/python.exe` used by every later task.

- [ ] **Step 1: Create the virtualenv and install the pin**

```powershell
cd "C:\Users\2011794-MTS\Desktop\Worldwide PMG Compass\CCSM PMG Compass\dashboard"
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install pytest
```

- [ ] **Step 2: Verify the Streamlit pin actually took**

```powershell
venv\Scripts\python.exe -c "import streamlit; print(streamlit.__version__)"
```

Expected: exactly `1.40.0`. If it prints anything else, stop and fix — the pin exists for a real selectbox bug.

- [ ] **Step 3: Write the secrets file**

Create `dashboard/.streamlit/secrets.toml`. Copy the `[gcp_service_account]` block verbatim from `C:\Users\2011794-MTS\Desktop\PMG-Compass\.streamlit\secrets.toml` — that service account already holds Editor on `COMPASS_CCSM`.

```toml
COMPASS_SHEET_NAME  = "COMPASS_CCSM"
GEMINI_API_KEY      = ""   # CCSM's own key - ask the user
STREAMLIT_DEV_EMAIL = "ccsm.pmg.compass@gmail.com"  # LOCAL DEV ONLY

[gcp_service_account]
# ... copied verbatim ...
```

**Leave `GEMINI_API_KEY` blank.** Verified 2026-07-28: no CCSM Gemini key exists in any `.env` or `secrets.toml` on this machine — the only key present is **Provo's**, in `PMG-Compass/.streamlit/secrets.toml`. CCSM's key is expected in Apps Script → Project Settings → Script Properties, and the user is retrieving it separately.

**Never copy Provo's Gemini key into this app.** Doing so would re-couple the two missions through a shared quota and a shared billing identity — the exact thing this project exists to prevent. A blank key only disables the Home chat panel (`Home.py:234` raises a caught `st.error`); all 9 other pages work normally.

**Secrets hygiene (applies to every task):** `.gitignore` was hardened in `61eddd6` and verified to ignore `.env` and `secrets.toml` at any depth. Never print a key's value to the console, into a report file, or into a commit — report presence and length only. A key that reaches a git remote must be rotated even if the commit is later removed.

- [ ] **Step 4: Confirm it reads the right sheet before launching any UI**

```powershell
venv\Scripts\python.exe -c "import tomllib;d=tomllib.load(open('.streamlit/secrets.toml','rb'));print(d['COMPASS_SHEET_NAME'])"
```

Expected: `COMPASS_CCSM`. This is the single value that makes the app CCSM's.

- [ ] **Step 5: Launch on port 8502**

```powershell
venv\Scripts\streamlit.exe run Home.py --server.port 8502
```

Expected: server starts. Some pages will error on empty tabs — that is Task 5's input, not a failure here. Record which pages load, which are empty, and which raise.

- [ ] **Step 6: Write `dashboard/RUNNING.md`**

Document: the venv creation commands, the 1.40.0 pin rationale, the port-8502 convention, which secrets are required vs optional, and that `secrets.toml` is gitignored and must be recreated on another machine.

- [ ] **Step 7: Commit**

```powershell
git add dashboard/RUNNING.md
git commit -m "docs(dashboard): local run instructions for the CCSM app"
```

Verify `git status` shows `secrets.toml` untracked. If it is staged, stop and fix `.gitignore`.

---

### Task 5: Harden the pages against empty tabs

`DAILY_LOG`, `WEEKLY_BREAKDOWNS`, `GOALS_CONFIG`, `NIGHTLY_FORM_RAW`, and `WEEKLY_FORM_RAW` are all **0 rows** — CCSM launched 2026-07-27 and no missionary has submitted. Every fix must preserve correct behavior once data arrives; an empty-state guard must never change how real data is computed or reported.

**Files:**
- Modify: whichever of the 9 pages raised in Task 4 Step 5
- Test: `dashboard/tests/test_empty_tabs.py`

**Interfaces:**
- Consumes: the failure list recorded in Task 4 Step 5.
- Produces: pages that render an explicit empty state instead of raising. No signature changes.

- [ ] **Step 1: Write a failing test per crashing page**

Use Streamlit's `AppTest` with the sheet layer patched to return empty frames. Patch **at the module that imports the function**, not at the source module — `from x import fn` binds at import time.

Create `dashboard/tests/test_empty_tabs.py`:

```python
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

PAGES = [
    "pages/01_dashboard.py",
    "pages/02_Goals.py",
    "pages/04_Breakdowns.py",
    "pages/06_Scores.py",
    "pages/07_Finding_Funnel.py",
    "pages/10_Notes.py",
    "pages/15_Suggestions.py",
    "pages/17_Action_Center.py",
    "pages/18_Maintenance.py",
]


@pytest.mark.parametrize("page", PAGES)
def test_page_survives_empty_tabs(page, monkeypatch):
    monkeypatch.setattr("app.db.sheets_client._read_tab_cached",
                        lambda *a, **k: pd.DataFrame())
    at = AppTest.from_file(page, default_timeout=60)
    at.run()
    assert not at.exception, f"{page} raised on empty data: {at.exception}"
```

- [ ] **Step 2: Run to see which pages fail**

```powershell
venv\Scripts\python.exe -m pytest tests/test_empty_tabs.py -v
```

Expected: some subset fails. Record the exact exception per page — that list drives Step 3.

- [ ] **Step 3: Fix each failure at its root**

For each failing page, read the traceback and fix the actual cause. Typical shapes, all of which must be fixed by guarding the *entry* to the computation rather than by wrapping it in a bare `except`:

- Indexing a column on an empty frame → check `df.empty` first and render `st.info(...)`.
- `df.iloc[0]` on zero rows → guard with `if df.empty: return`.
- Division by a zero row count → guard the denominator, and return no value rather than `0` where a rate is undefined (a 0% rate and "no data" are different claims).
- `pd.to_datetime` on an empty column → guard before converting.

Never use a bare `except Exception: pass` to make the test go green. That would hide real failures once CCSM has data.

- [ ] **Step 4: Run to verify all pass**

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add dashboard
git commit -m "fix(dashboard): render empty states instead of raising on zero-row tabs

CCSM launched 2026-07-27 with no submissions yet, so DAILY_LOG,
WEEKLY_BREAKDOWNS, GOALS_CONFIG and both FORM_RAW tabs are empty. Each
guard checks the frame at the entry to the computation; none changes how
real data is calculated once submissions arrive."
```

---

### Task 6: The i18n core

**Files:**
- Create: `dashboard/app/i18n/__init__.py`
- Create: `dashboard/app/i18n/es.py`
- Test: `dashboard/tests/test_i18n.py`

**Interfaces:**
- Consumes: nothing from prior tasks (standalone module).
- Produces — every later task depends on these exact signatures:
  - `t(text: str, **kwargs) -> str` — returns the Spanish string for `text` when the active language is `"es"` and a translation exists; otherwise returns `text`. When `kwargs` are given, calls `.format(**kwargs)` on the resolved template.
  - `get_lang() -> str` — `"en"` or `"es"`, read from `st.session_state["pmg_lang"]`, defaulting to `"en"`.
  - `set_lang(lang: str) -> None` — writes `st.session_state["pmg_lang"]`; raises `ValueError` on anything other than `"en"`/`"es"`.
  - `app.i18n.es.ES: dict[str, str]` — English source string → Spanish.

  Note: coverage measurement lives entirely in Task 8's `tools/i18n_coverage.py`, which compares `ES` against strings extracted from source. `app/i18n/` deliberately exposes no coverage helper — a count of `ES` entries would measure the dict against itself and could report 100% while strings sat untranslated in the UI.

- [ ] **Step 1: Write the failing tests**

Create `dashboard/tests/test_i18n.py`:

```python
import pytest
import streamlit as st
from app.i18n import t, get_lang, set_lang
from app.i18n.es import ES


@pytest.fixture(autouse=True)
def _clear_state():
    st.session_state.clear()
    yield
    st.session_state.clear()


def test_defaults_to_english():
    assert get_lang() == "en"


def test_english_returns_source_unchanged():
    assert t("Area Scores") == "Area Scores"


def test_spanish_returns_translation():
    set_lang("es")
    ES["Area Scores"] = "Puntajes por Área"
    assert t("Area Scores") == "Puntajes por Área"


def test_missing_translation_falls_back_to_english():
    """The core safety property: a missing key must never raise or leak a
    key name - it degrades to readable English."""
    set_lang("es")
    assert t("A string nobody translated") == "A string nobody translated"


def test_interpolation_applies_after_lookup():
    set_lang("es")
    ES["Welcome back, {name}"] = "Bienvenido de nuevo, {name}"
    assert t("Welcome back, {name}", name="Elder Fox") == \
        "Bienvenido de nuevo, Elder Fox"


def test_interpolation_works_in_english_too():
    assert t("Welcome back, {name}", name="Elder Fox") == \
        "Welcome back, Elder Fox"


def test_set_lang_rejects_unknown():
    with pytest.raises(ValueError):
        set_lang("fr")
```

- [ ] **Step 2: Run to verify it fails**

```powershell
venv\Scripts\python.exe -m pytest tests/test_i18n.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.i18n'`.

- [ ] **Step 3: Implement the module**

Create `dashboard/app/i18n/es.py`:

```python
"""English source string -> Spanish (es_CL). Populated by Tasks 9-12.

Keys are the exact English strings as they appear in the UI. A key that is
absent falls back to English, so this dict is always safe to be incomplete.
"""

ES: dict[str, str] = {}
```

Create `dashboard/app/i18n/__init__.py`:

```python
"""Bilingual UI support.

The English source string is its own lookup key. That makes the retrofit
mechanical, needs no invented key namespace, and means a renamed or
untranslated string degrades to readable English instead of raising or
showing a raw identifier.

Only UI chrome goes through t(). Sheet-sourced mission content (metric
labels, mission name, knowledge base, notes, area names) is already Spanish
and must never be translated again.
"""

import streamlit as st

from app.i18n.es import ES

_LANGS = ("en", "es")
_KEY = "pmg_lang"


def get_lang() -> str:
    lang = st.session_state.get(_KEY, "en")
    return lang if lang in _LANGS else "en"


def set_lang(lang: str) -> None:
    if lang not in _LANGS:
        raise ValueError(f"unsupported language: {lang!r}")
    st.session_state[_KEY] = lang


def t(text: str, **kwargs) -> str:
    """Translate `text` for the active language, then interpolate.

    Lookup happens before formatting so Spanish word order can differ from
    English. Returns `text` unchanged when no translation exists.
    """
    resolved = ES.get(text, text) if get_lang() == "es" else text
    if kwargs:
        try:
            return resolved.format(**kwargs)
        except (KeyError, IndexError):
            # A malformed translation must not break the page.
            return text.format(**kwargs)
    return resolved
```

- [ ] **Step 4: Run to verify it passes**

```powershell
venv\Scripts\python.exe -m pytest tests/test_i18n.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```powershell
git add dashboard/app/i18n dashboard/tests/test_i18n.py
git commit -m "feat(i18n): translation core keyed on the English source string

Missing translations fall back to English rather than raising or showing a
raw key, so an incomplete ES dict is always safe to ship."
```

---

### Task 7: The language switch

**Files:**
- Modify: `dashboard/Home.py` (insert above the `render_page_header` call around line 90)
- Modify: `dashboard/app/components/design_system.py` (`render_sidebar`, line 672)
- Test: `dashboard/tests/test_language_switch.py`

**Interfaces:**
- Consumes: `set_lang`, `get_lang` from Task 6.
- Produces: `render_language_switch(key: str) -> None` in `app/components/design_system.py`, rendering a radio and calling `set_lang` on change. Callers pass a unique `key` because Home and the sidebar both render it.

- [ ] **Step 1: Write the failing test**

Create `dashboard/tests/test_language_switch.py`:

```python
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def _empty_sheets(monkeypatch):
    monkeypatch.setattr("app.db.sheets_client._read_tab_cached",
                        lambda *a, **k: pd.DataFrame())


def test_home_renders_a_language_switch():
    at = AppTest.from_file("Home.py", default_timeout=60)
    at.run()
    assert not at.exception
    labels = [r.label for r in at.radio]
    assert any("Language" in (lbl or "") or "Idioma" in (lbl or "")
               for lbl in labels), f"no language radio found: {labels}"


def test_switch_sets_session_state():
    at = AppTest.from_file("Home.py", default_timeout=60)
    at.run()
    at.radio[0].set_value("Español").run()
    assert at.session_state["pmg_lang"] == "es"


def test_language_persists_to_another_page():
    at = AppTest.from_file("pages/01_dashboard.py", default_timeout=60)
    at.session_state["pmg_lang"] = "es"
    at.run()
    assert not at.exception
    assert at.session_state["pmg_lang"] == "es"
```

- [ ] **Step 2: Run to verify it fails**

```powershell
venv\Scripts\python.exe -m pytest tests/test_language_switch.py -v
```

Expected: FAIL — no language radio found.

- [ ] **Step 3: Implement the switch**

Add to `dashboard/app/components/design_system.py`:

```python
def render_language_switch(key: str) -> None:
    """Language selector. Rendered at the top of Home and mirrored in the
    sidebar so the choice can be changed from any page."""
    from app.i18n import get_lang, set_lang

    options = {"English": "en", "Español": "es"}
    labels = list(options)
    current = get_lang()
    index = 1 if current == "es" else 0

    chosen = st.radio(
        "Language / Idioma",
        labels,
        index=index,
        horizontal=True,
        key=key,
        label_visibility="collapsed",
    )
    if options[chosen] != current:
        set_lang(options[chosen])
        st.rerun()
```

In `render_sidebar`, add `render_language_switch("ds_lang_sidebar")` inside the `with st.sidebar:` block, above the `st.divider()`.

In `dashboard/Home.py`, immediately before the `render_page_header(...)` call, add:

```python
from app.components.design_system import render_language_switch
render_language_switch("home_lang")
```

- [ ] **Step 4: Run to verify it passes**

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add dashboard
git commit -m "feat(i18n): language switch on Home, mirrored in the sidebar

Sidebar mirror means the choice survives navigation instead of stranding a
Spanish reader on an English page."
```

---

### Task 8: String extraction tooling and the coverage gate

Translating ~800 strings by hand-scanning files is how strings get missed. This task builds the tool that finds them and reports what is left.

**Files:**
- Create: `dashboard/tools/extract_ui_strings.py`
- Create: `dashboard/tools/i18n_coverage.py`
- Test: `dashboard/tests/test_extract_ui_strings.py`

**Interfaces:**
- Consumes: `app.i18n.es.ES` from Task 6.
- Produces:
  - `extract_ui_strings.extract(paths: list[str]) -> list[str]` — sorted unique English UI strings.
  - `extract_ui_strings.main()` — prints a paste-ready `ES` dict skeleton for untranslated strings.
  - `i18n_coverage.report() -> tuple[int, int, list[str]]` — `(translated, total_found, missing)`.

- [ ] **Step 1: Write the failing test**

Create `dashboard/tests/test_extract_ui_strings.py`:

```python
from pathlib import Path

from tools.extract_ui_strings import extract

FIXTURE = '''
import streamlit as st
st.markdown("Hello world")
st.button("Save changes")
st.caption(f"Week {x}")
value = "not a ui string"
st.write(some_variable)
'''


def test_extracts_only_ui_call_literals(tmp_path: Path):
    f = tmp_path / "sample.py"
    f.write_text(FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    assert "Hello world" in found
    assert "Save changes" in found
    assert "not a ui string" not in found


def test_ignores_dynamic_arguments(tmp_path: Path):
    f = tmp_path / "sample.py"
    f.write_text(FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    assert all("some_variable" not in s for s in found)
```

- [ ] **Step 2: Run to verify it fails**

```powershell
venv\Scripts\python.exe -m pytest tests/test_extract_ui_strings.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'tools'`.

- [ ] **Step 3: Implement the extractor**

Create `dashboard/tools/__init__.py` (empty) and `dashboard/tools/extract_ui_strings.py`:

```python
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
```

Create `dashboard/tools/i18n_coverage.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes, then get the real baseline**

```powershell
venv\Scripts\python.exe -m pytest tests/test_extract_ui_strings.py -v
venv\Scripts\python.exe -m tools.i18n_coverage
```

Expected: tests pass; coverage prints `Translated 0/N`. **Record N** — it is the real denominator for Tasks 9–12 and supersedes the spec's 578 floor.

- [ ] **Step 5: Commit**

```powershell
git add dashboard/tools dashboard/tests/test_extract_ui_strings.py
git commit -m "feat(i18n): UI string extractor and coverage report

Translation work is driven by a generated list and measured against a real
denominator, so gaps are a known number instead of a surprise."
```

---

### Tasks 9–12: Translate the UI

Four tasks, split so a reviewer can accept one page group while rejecting another. Each follows the identical procedure below; only the file group changes.

| Task | Pages | Approx. strings |
|---|---|---|
| 9 | `Home.py`, `pages/01_dashboard.py`, `pages/04_Breakdowns.py` | ~70 |
| 10 | `pages/07_Finding_Funnel.py`, `pages/10_Notes.py`, `pages/15_Suggestions.py`, `pages/17_Action_Center.py` | ~165 |
| 11 | `pages/06_Scores.py`, `app/components/design_system.py`, `app/components/scope_selector.py` | ~110 |
| 12 | `pages/02_Goals.py`, `pages/18_Maintenance.py` | ~250 |

**Interfaces (all four):**
- Consumes: `t()` from Task 6; `tools.i18n_coverage.report()` from Task 8.
- Produces: entries in `app.i18n.es.ES`; `t(...)` wrapping at UI call sites in the listed files. No function signatures change.

**Procedure for each of Tasks 9–12:**

- [ ] **Step 1: Generate the string list for this task's files**

```powershell
venv\Scripts\python.exe -c "from tools.extract_ui_strings import extract; [print(repr(s)) for s in extract(['<file1>','<file2>'])]"
```

- [ ] **Step 2: Write the failing coverage test for this group**

Add to `dashboard/tests/test_i18n_coverage.py` (create on Task 9):

```python
from tools.extract_ui_strings import extract
from app.i18n.es import ES

GROUPS = {
    "task9":  ["Home.py", "pages/01_dashboard.py", "pages/04_Breakdowns.py"],
}


def _missing(files):
    return [s for s in extract(files) if s not in ES or not ES[s].strip()]


def test_group_fully_translated():
    for name, files in GROUPS.items():
        assert _missing(files) == [], f"{name} untranslated: {_missing(files)[:10]}"
```

Each later task adds its own key to `GROUPS`.

- [ ] **Step 3: Run to verify it fails**

```powershell
venv\Scripts\python.exe -m pytest tests/test_i18n_coverage.py -v
```

Expected: FAIL, listing untranslated strings.

- [ ] **Step 4: Add the translations**

Add each English string to `ES` in `dashboard/app/i18n/es.py` with its Chilean-Spanish (`es_CL`) equivalent, using the formal register appropriate to mission leadership. Real examples of the expected form:

```python
ES: dict[str, str] = {
    "Language / Idioma": "Idioma / Language",
    "Sign Out": "Cerrar sesión",
    "Area Scores": "Puntajes por Área",
    "Mission Assistant": "Asistente de la Misión",
    "Welcome back, {name}": "Bienvenido de nuevo, {name}",
    "App Guide — what each page does":
        "Guía de la Aplicación — qué hace cada página",
    "No data yet": "Aún no hay datos",
    "Last updated": "Última actualización",
    "Week": "Semana",
}
```

Rules:
- Keep every `{placeholder}` intact and identically spelled; `t()` formats after lookup.
- Translate UI chrome only. Leave sheet-sourced values (area names, zone names, mission name, metric labels from `flavor_loader`, knowledge-base text) untouched.
- Preserve trailing/leading punctuation and em-dashes so layout is unchanged.

- [ ] **Step 5: Wrap the call sites**

In each file in the group, wrap user-facing literals in `t(...)`, adding `from app.i18n import t` at the top. Interpolated strings convert from f-string to `t()` kwargs so the template is looked up before formatting:

```python
# before
st.caption(f"Welcome back, {user['name']}")
# after
st.caption(t("Welcome back, {name}", name=user["name"]))
```

Do **not** wrap: dict keys, DataFrame column names, `key=` widget identifiers, CSS, HTML attribute values, or any value read from the sheet. Wrapping a column name breaks data lookup.

- [ ] **Step 6: Run to verify it passes**

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
venv\Scripts\python.exe -m tools.i18n_coverage
```

Expected: all tests pass; coverage percentage rises by this group's share.

- [ ] **Step 7: Visually verify both languages**

```powershell
venv\Scripts\streamlit.exe run Home.py --server.port 8502
```

Walk this task's pages in English, switch to Español, walk them again. Confirm no raw `{placeholder}` text, no layout breakage from longer Spanish strings, and no translated column headers.

- [ ] **Step 8: Commit**

```powershell
git add dashboard
git commit -m "feat(i18n): translate <group name> to Spanish"
```

---

### Task 13: Translate the sidebar navigation labels

**Highest-risk change in the plan — sequenced last so it can be abandoned without costing any translated string.** Streamlit derives sidebar nav labels from filenames, so `t()` cannot reach them. Fixing that needs `st.navigation`/`st.Page`, which changes page URLs.

**Files:**
- Modify: `dashboard/Home.py`
- Test: `dashboard/tests/test_navigation.py`

**Interfaces:**
- Consumes: `t()` from Task 6, `get_lang()` for the rerun trigger.
- Produces: `Home.py` defining the nav via `st.navigation`. Page modules themselves are unchanged.

- [ ] **Step 1: Confirm the API exists on the pinned version**

```powershell
venv\Scripts\python.exe -c "import streamlit as st; print(hasattr(st,'navigation'), hasattr(st,'Page'), st.__version__)"
```

Expected: `True True 1.40.0`. If either is `False`, **stop and skip Task 13 entirely** — report that nav labels stay English and everything else is done. That is an acceptable outcome, not a failure.

- [ ] **Step 2: Write the failing test**

Create `dashboard/tests/test_navigation.py`:

```python
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent / "Home.py"


def test_home_uses_st_navigation():
    text = HOME.read_text(encoding="utf-8-sig")
    assert "st.navigation" in text
    assert "st.Page" in text


def test_nav_titles_are_translated():
    text = HOME.read_text(encoding="utf-8-sig")
    assert 'title=t("Dashboard")' in text
```

- [ ] **Step 3: Run to verify it fails**

```powershell
venv\Scripts\python.exe -m pytest tests/test_navigation.py -v
```

Expected: FAIL — `st.navigation` not in Home.py.

- [ ] **Step 4: Convert to `st.navigation`**

Restructure `dashboard/Home.py` so the chat body moves into `dashboard/pages/00_Assistant.py` and `Home.py` becomes the router. Keep `url_path` values stable and English so bookmarks do not change when the language does:

```python
import streamlit as st
from app.i18n import t

st.set_page_config(page_title="PMG Compass", page_icon="C", layout="wide")

pages = [
    st.Page("pages/00_Assistant.py",     title=t("Assistant"),      url_path="assistant", default=True),
    st.Page("pages/01_dashboard.py",     title=t("Dashboard"),      url_path="dashboard"),
    st.Page("pages/02_Goals.py",         title=t("Goals"),          url_path="goals"),
    st.Page("pages/04_Breakdowns.py",    title=t("Breakdowns"),     url_path="breakdowns"),
    st.Page("pages/06_Scores.py",        title=t("Scores"),         url_path="scores"),
    st.Page("pages/07_Finding_Funnel.py",title=t("Finding Funnel"), url_path="finding-funnel"),
    st.Page("pages/10_Notes.py",         title=t("Notes"),          url_path="notes"),
    st.Page("pages/15_Suggestions.py",   title=t("Suggestions"),    url_path="suggestions"),
    st.Page("pages/17_Action_Center.py", title=t("Action Center"),  url_path="action-center"),
    st.Page("pages/18_Maintenance.py",   title=t("Maintenance"),    url_path="maintenance"),
]

st.navigation(pages).run()
```

Add the nav titles to `ES`:

```python
    "Assistant": "Asistente",
    "Dashboard": "Panel",
    "Goals": "Metas",
    "Breakdowns": "Desgloses",
    "Scores": "Puntajes",
    "Finding Funnel": "Embudo de Búsqueda",
    "Notes": "Notas",
    "Suggestions": "Sugerencias",
    "Action Center": "Centro de Acción",
    "Maintenance": "Mantenimiento",
```

Each page keeps its own `require_auth()` / `inject_global_css()` / `render_sidebar()` calls — `st.navigation` does not run them for you.

Note: `_render_action_bell` in `design_system.py:715` hardcodes the link `\Action_Center`. Update it to `/action-center` to match the new `url_path`, or the bell links nowhere.

- [ ] **Step 5: Run to verify it passes**

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all pass. Task 5's and Task 7's `AppTest.from_file` tests still target page files directly and must still pass — if they break, the page modules picked up a dependency on the router, which is a defect.

- [ ] **Step 6: Verify in the browser**

```powershell
venv\Scripts\streamlit.exe run Home.py --server.port 8502
```

Confirm all 10 nav entries appear, switch to Español and confirm the sidebar labels change, and click the Action Center bell to confirm it lands on the right page.

- [ ] **Step 7: Commit**

```powershell
git add dashboard
git commit -m "feat(i18n): translate sidebar nav labels via st.navigation

url_path values stay English so bookmarks survive a language change."
```

---

### Task 14: Final verification and the one live sheet write

**Files:**
- Create: `dashboard/tests/test_final_verification.py`
- Modify: `COMPASS_CCSM` → `AGENT_CONFIG` tab (**live production sheet — user confirmation required**)

**Interfaces:**
- Consumes: everything.
- Produces: a green suite and a verified running app.

- [ ] **Step 1: Run the whole suite**

```powershell
cd "C:\Users\2011794-MTS\Desktop\Worldwide PMG Compass\CCSM PMG Compass\dashboard"
venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all pass. Report the actual count; do not claim green without the output.

- [ ] **Step 2: Report final translation coverage**

```powershell
venv\Scripts\python.exe -m tools.i18n_coverage
```

Report the real percentage. If below 100%, list what remains rather than rounding up.

- [ ] **Step 3: Confirm the Provo repo is untouched**

```powershell
cd "C:\Users\2011794-MTS\Desktop\PMG-Compass"
git status --short
```

Expected: only the pre-existing `.gitignore` and `app/config/settings.py` modifications that were there before this work began. Anything else means the isolation promise was broken.

- [ ] **Step 4: Verify `MISSION_NAME` reads correctly (read-only — no write)**

`AGENT_CONFIG` **already has** a `MISSION_NAME` row (`Chile Concepción South Mission`, verified 2026-07-28). An earlier draft of this plan claimed it was missing; that was a `grep` artifact — the value contains `ó`, so grep treated the stream as binary and suppressed the line.

**No write to any live sheet occurs in this project.** Confirm the value reaches the UI:

```powershell
venv\Scripts\python.exe -c "import tomllib,gspread; from google.oauth2.service_account import Credentials; s=tomllib.load(open('.streamlit/secrets.toml','rb')); c=Credentials.from_service_account_info(dict(s['gcp_service_account']),scopes=['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']); ws=gspread.authorize(c).open('COMPASS_CCSM').worksheet('AGENT_CONFIG'); print([r[:2] for r in ws.get_all_values() if r and r[0]=='MISSION_NAME'])"
```

Expected: `[['MISSION_NAME', 'Chile Concepción South Mission']]`.

If any step in this plan appears to require a write to `COMPASS_CCSM`, stop and ask — it is out of scope.

- [ ] **Step 5: Confirm the mission name renders, including the accent**

Launch the app and confirm page headers read "Chile Concepción South Mission" with the accent intact (a mojibake `Concepci�n` means an encoding bug in the read path, not a sheet problem).

- [ ] **Step 6: Final browser walkthrough**

```powershell
venv\Scripts\streamlit.exe run Home.py --server.port 8502
```

Walk all 10 pages in English, then all 10 in Español. Confirm: headers show the mission name, no page raises, no raw placeholders, and the sidebar language switch works from every page. Record any page that is empty-but-fine versus broken.

- [ ] **Step 7: Commit**

```powershell
cd "C:\Users\2011794-MTS\Desktop\Worldwide PMG Compass\CCSM PMG Compass"
git add dashboard
git commit -m "test(dashboard): final verification of the CCSM bilingual dashboard"
```

---

## Remaining open items after this plan

- **CCSM Mission President's email** for `_ALWAYS_ALLOWED` (Task 3 leaves a marked TODO rather than guessing).
- **CCSM's own Gemini API key** (Task 4; blank only disables the Home chat panel).
- **Native-speaker proofread** of the Spanish. The translations are machine-written; `MISSION_LOCALE` is `es_CL`.
- **CCSM-owned GCP service account** — the dashboard currently authenticates with Provo's, which already has Editor on `COMPASS_CCSM`. Step 2 of the existing Independence Handoff Guide.
- **Cloud deployment and a CCSM GitHub remote** — the CCSM repo still has no remote at all.
- **`RELAY_2_URL`** is still blank in `AGENT_CONFIG`, unrelated to the dashboard.
