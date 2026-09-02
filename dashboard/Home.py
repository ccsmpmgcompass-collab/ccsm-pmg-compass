"""PMG Compass — application entrypoint and navigation router.

Until 2026-09-02 this file WAS the Mission Assistant page, and Streamlit built
the sidebar by globbing `pages/` and sorting filenames. That gave a flat list of
fourteen entries in which a dead page and the flagship dashboard carried
identical weight, with no way to say what any of them was for
(AUDIT-IA-2026-08-22.md, "Structural diagnosis").

Now the assistant lives in `views/00_Asistente.py` and this file does one job:
declare the pages, group them, and run the selected one.

The page files moved from `pages/` to `views/` in the same change, because
Streamlit refuses to hand navigation over while a `pages/` directory exists:
its own filesystem discovery renders the flat list first, and only once some
session has executed `st.navigation` does the app start ignoring the folder
(`navigation.py`'s docstring says so outright, and it logs a warning). Keeping
the folder would have meant a flash of the old flat sidebar on every cold
start. Nothing else about `views/` is special — `st.Page` takes a path.

WHY THE GROUPS ARE VERBS
------------------------
The old order was an accident of filenames. The new one answers "what am I
trying to do right now":

    VER       — what happened          (Panel, Desgloses, Informes)
    ANALIZAR  — why it happened        (Puntajes, Embudo, Referencias)
    DIRIGIR   — decide and act on it   (Metas, Centro de Acción, Notas)
    OPERAR    — run the machine        (Traslados, Editar Envíos, Sugerencias,
                                        Mantenimiento)

Asistente sits above the groups, unlabelled, because it is not one of the four
jobs — it is a way of asking about any of them.

THREE THINGS THAT MOVED HERE FROM EVERY PAGE
--------------------------------------------
`st.navigation` runs the router and the selected page inside ONE script run, so
per-page chrome would now render twice. `st.set_page_config()`,
`inject_global_css()` and `render_sidebar()` are therefore called here, once,
and were deleted from all fourteen page files. This is also the permanent fix
for the audit's duplicate-chrome finding: the double TEST MODE banner could
only happen because two callers each injected the global CSS.

`require_auth()` stays on the pages as well as here. It is idempotent for an
authenticated session — it returns the cached session dict and renders nothing
— and leaving it in place means no page can ever be run unauthenticated, even
if a future refactor bypasses this router.

URLs DID NOT CHANGE
-------------------
`st.Page` infers `url_path` from `source_util.page_icon_and_name`, which strips
the `NN_` filename prefix and keeps the rest verbatim, accents included — and
it reads the FILENAME, not the folder, so the `views/` rename left every path
alone. `views/17_Centro_de_Acción.py` is still served at `/Centro_de_Acción`,
the path the notification bell was pointed at when B5 was fixed. Only the
default page differs: `default=True` forces `url_path == ""`, Panel at `/`.
For the same reason the `st.switch_page("views/…")` calls in the Action Center
and the `st.page_link` in Mantenimiento keep working: `switch_page` matches on
`script_path` against the pages registered here, not on a slug.
"""

import streamlit as st

from app.auth.auth import require_auth
from app.components.design_system import (
    inject_global_css,
    render_sidebar,
    reset_section_numbering,
)

st.set_page_config(
    page_title="CCSM · PMG Compass",
    page_icon="C",
    layout="wide",
)

# Auth first: an unapproved viewer must not even see the shape of the app, and
# require_auth() calls st.stop() rather than returning on failure.
user = require_auth()
inject_global_css()


def _page(path: str, title: str, *, default: bool = False):
    return st.Page(f"views/{path}", title=title, default=default)


# NOTHING HERE GOES THROUGH t().
#
# Page names are proper nouns in this app, not UI copy: they stay Spanish with
# the interface in English, which is what tests/test_nav_and_locale_rendered.py
# has asserted since long before this rebuild (test_no_english_page_name_
# survives fails on the mere presence of "Dashboard", "Goals", "Scores"… in a
# nav label). An English speaker on this mission still says "check the Panel".
#
# The four group headers follow the page names for the same reason — a sidebar
# reading "SEE › Panel · Desgloses" would be a worse mix than either language
# on its own.
#
# The Panel is `default=True`: the app opens on the numbers rather than on an
# empty chat box, so it answers the first question before anything is typed.
_nav = {
    "": [
        _page("00_Asistente.py", "Asistente"),
    ],
    "VER": [
        _page("01_Panel.py", "Panel", default=True),
        _page("04_Desgloses.py", "Desgloses"),
        _page("11_Informes.py", "Informes"),
    ],
    "ANALIZAR": [
        _page("06_Puntajes.py", "Puntajes"),
        _page("07_Embudo_de_Búsqueda.py", "Embudo de Búsqueda"),
        _page("14_Referencias.py", "Referencias"),
    ],
    "DIRIGIR": [
        _page("02_Metas.py", "Metas"),
        _page("17_Centro_de_Acción.py", "Centro de Acción"),
        _page("10_Notas.py", "Notas"),
    ],
    "OPERAR": [
        _page("12_Traslados.py", "Traslados"),
        _page("19_Editar_Envíos.py", "Editar Envíos"),
        _page("15_Sugerencias.py", "Sugerencias"),
        _page("18_Mantenimiento.py", "Mantenimiento"),
    ],
}

# expanded=True because the default collapses everything past the tenth entry
# behind a "View 4 more" link — which hid the whole OPERAR group, header and
# all. A group nobody can see is worse wayfinding than the flat list this
# replaced.
_selected = st.navigation(_nav, expanded=True)

# After st.navigation so the language switch, the signed-in user and Sign Out
# sit BELOW the page list rather than above it.
render_sidebar(user)

# Section labels number themselves ①②③ in render order; this restarts the
# count so each page begins at ① rather than continuing the previous page's.
# It belongs here, not in the pages, precisely because the router is the one
# thing that runs exactly once per full script run.
reset_section_numbering()

_selected.run()
