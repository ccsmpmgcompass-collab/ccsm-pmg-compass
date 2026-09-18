"""The Key Indicator drill-down panel — app/components/ki_drilldown.py.

PLAN-2026-09-18-data-pages.md §3, step B2/B3. Rendered against a stub `st`
that records every call: the panel's state lives in ``?ki=`` and the tests
drive it the way a card link, a pills tap and the "✕ cerrar" pill would.
Synthetic data throughout, the same cycle and frame as test_ki_history.
"""

from datetime import date

import pandas as pd
import pytest

from app.components import charts, design_system, ki_drilldown as dd
from app.components.ki_drilldown import (
    KI_PARAM, TABS, TAB_AREA, TAB_CYCLE, TAB_TABLE, TAB_WEEK,
    ki_href, render_ki_drilldown, selected_ki,
)

TODAY = date(2026, 9, 18)
CUR = {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
       "weeks": 6, "status": "Actual", "source": "schedule"}
PREV = {"number": "2026-5", "start": date(2026, 7, 27), "end": date(2026, 9, 6),
        "weeks": 6, "status": "Actual", "source": "schedule"}
METRIC = "ki_new_people_real"
KIS = {
    "ki_new_people_real": "Nuevas Personas Encontradas (Real)",
    "ki_member_lessons_real": "Lecciones con Miembros (Real)",
    "ki_friends_sacrament_real": "Amigos en la Reunión Sacramental (Real)",
    "ki_friends_first_week_real": "Amigos en la Iglesia (Primera Semana) (Real)",
    "ki_baptismal_date_real": "Amigos con Fecha Bautismal (Real)",
    "ki_baptized_confirmed_real": "Bautizados y Confirmados (Real)",
    "ki_rc_at_church_real": "Conversos Recientes en la Iglesia (Real)",
}


class _Rerun(Exception):
    pass


class _StubSt:
    """Just enough of streamlit for the panel: records every call, answers
    pills from a per-key script, and raises on rerun so a test can assert
    what the rerun was asked to carry."""

    def __init__(self, query=None, answers=None):
        self.query_params = dict(query or {})
        self.session_state = {}
        self.calls: list[tuple] = []
        self._answers = dict(answers or {})

    def _rec(self, name):
        def _f(*a, **kw):
            self.calls.append((name, a, kw))
        return _f

    def __getattr__(self, name):
        # markdown, caption, info, plotly_chart, download_button, warning…
        return self._rec(name)

    def pills(self, label, options, **kw):
        self.calls.append(("pills", (label, list(options)), kw))
        key = kw.get("key", "")
        return self._answers[key] if key in self._answers else kw.get("default")

    def rerun(self, **kw):
        self.calls.append(("rerun", (), kw))
        raise _Rerun()

    def named(self, name):
        return [c for c in self.calls if c[0] == name]


def _frame() -> pd.DataFrame:
    rows = [
        ("2026-08-09", "A", 2, 4), ("2026-08-09", "B", 1, 3),
        ("2026-08-16", "A", 3, 5), ("2026-08-16", "B", 2, 2),
        ("2026-08-30", "A", 1, 6), ("2026-08-30", "B", 3, 3),
        ("2026-09-06", "A", 5, 7), ("2026-09-06", "B", 2, 4),
        ("2026-09-13", "A", 6, 8), ("2026-09-13", "B", 4, 0),
    ]
    return pd.DataFrame([
        {"week_end_date": w, "area": a, "zone": "Angol",
         "ki_new_people_real": real, "ki_new_people_meta": meta}
        for w, a, real, meta in rows
    ])


@pytest.fixture
def stubbed(monkeypatch):
    """Wire the panel to synthetic data and a recording `st`; returns a
    factory taking the query params and pills answers."""
    import app.db.queries as queries
    import app.db.goals_queries as gq
    import app.utils.transfer_helpers as th

    monkeypatch.setattr(dd, "key_indicator_metrics", lambda: dict(KIS))
    monkeypatch.setattr(dd, "mission_today", lambda: TODAY)
    monkeypatch.setattr(dd, "transfer_window",
                        lambda offset=0, today=None: {0: CUR, 1: PREV}.get(offset))
    monkeypatch.setattr(dd, "group_goal_totals", lambda start, areas=None: {METRIC: 60.0})
    monkeypatch.setattr(dd, "get_daily_log", lambda days=365: pd.DataFrame(
        [{"Date": "2026-09-14", "Area": "A"}]))
    monkeypatch.setattr(queries, "get_weekly_form_data", _frame)
    monkeypatch.setattr(th, "transfer_cycles", lambda rows=None: [PREV, CUR])
    monkeypatch.setattr(gq, "goals_by_cycle_start",
                        lambda areas=None: {CUR["start"]: {METRIC: 60.0}})

    def _make(query=None, answers=None):
        st = _StubSt(query, answers)
        monkeypatch.setattr(dd, "st", st)
        monkeypatch.setattr(charts, "st", st)
        monkeypatch.setattr(design_system, "st", st)
        return st
    return _make


def _render(st, **kw):
    return render_ki_drilldown("Mission", "CCSM", {"A", "B"}, **kw)


# ── The closed state ─────────────────────────────────────────────────────────

def test_closed_when_no_query_param(stubbed):
    st = stubbed()
    assert _render(st) is False
    strips = st.named("pills")
    assert len(strips) == 1                       # the strip, no tabs
    _label, options = strips[0][1]
    assert options == list(KIS)                   # seven, no close pill
    assert strips[0][2]["default"] is None
    assert st.named("plotly_chart") == []
    assert st.named("markdown") == []


def test_a_key_that_is_not_a_key_indicator_closes_the_panel(stubbed):
    st = stubbed({KI_PARAM: "contacts_made"})
    assert selected_ki() is None
    assert _render(st) is False


# ── The query param opens it ─────────────────────────────────────────────────

def test_query_param_selects_the_metric_and_draws_the_four_tabs(stubbed):
    st = stubbed({KI_PARAM: METRIC})
    assert selected_ki() == METRIC
    assert _render(st) is True
    strip, tabs = st.named("pills")
    assert strip[2]["default"] == METRIC
    assert strip[1][1][-1] == dd._CLOSE                 # the close pill appears
    assert tabs[1][1] == TABS
    assert tabs[2]["default"] == TAB_WEEK
    header = st.named("markdown")[0][1][0]
    assert "Nuevas personas" in header
    assert "2 áreas" in header and "meta del cambio 60" in header
    assert len(st.named("plotly_chart")) == 1           # Por semana
    caption = st.named("caption")[-1][1][0]
    assert "semana 2 de 6" in caption and "2026-5" in caption


def test_default_tab_is_honoured(stubbed):
    st = stubbed({KI_PARAM: METRIC})
    _render(st, default_tab=TAB_AREA)
    assert st.named("pills")[1][2]["default"] == TAB_AREA


# ── Taps on the strip ────────────────────────────────────────────────────────

def test_tapping_a_pill_sets_the_param_and_reruns(stubbed):
    st = stubbed(answers={"ki_dd_strip_none": "ki_baptized_confirmed_real"})
    with pytest.raises(_Rerun):
        _render(st)
    assert st.query_params[KI_PARAM] == "ki_baptized_confirmed_real"


def test_the_close_pill_clears_the_param(stubbed):
    st = stubbed({KI_PARAM: METRIC}, answers={f"ki_dd_strip_{METRIC}": dd._CLOSE})
    with pytest.raises(_Rerun):
        _render(st)
    assert KI_PARAM not in st.query_params


def test_tapping_the_open_metric_again_closes_it(stubbed):
    st = stubbed({KI_PARAM: METRIC}, answers={f"ki_dd_strip_{METRIC}": None})
    with pytest.raises(_Rerun):
        _render(st)
    assert KI_PARAM not in st.query_params


# ── The other tabs ───────────────────────────────────────────────────────────

def test_por_cambio_draws_a_chart_and_names_the_goal(stubbed):
    st = stubbed({KI_PARAM: METRIC}, answers={"ki_dd_tab": TAB_CYCLE})
    _render(st)
    assert len(st.named("plotly_chart")) == 1
    caption = st.named("caption")[-1][1][0]
    assert "10 de 19 propuesto" in caption
    assert "meta del cambio 60" in caption
    assert "1 de 6 semanas" in caption


def test_por_area_ranks_the_areas_and_links_into_desgloses(stubbed):
    st = stubbed({KI_PARAM: METRIC}, answers={"ki_dd_tab": TAB_AREA})
    _render(st)
    html = next(c[1][0] for c in st.named("markdown") if "pmg-ranked" in c[1][0])
    assert html.index(">B<") < html.index(">A<")         # B: 100%, A: 86%
    assert f'href="/Desgloses?bd_area=A&amp;{KI_PARAM}={METRIC}"' in html
    # Nights due: Mon 7 Sep – Thu 17 Sep, eleven; A filed one, B none.
    assert "10 noches sin informe" in html
    assert "11 noches sin informe" in html
    assert st.named("plotly_chart") == []


def test_tabla_renders_a_table_and_a_download(stubbed):
    st = stubbed({KI_PARAM: METRIC}, answers={"ki_dd_tab": TAB_TABLE})
    _render(st)
    table = next(c[1][0] for c in st.named("markdown") if "pmg-tbl" in c[1][0])
    assert "Logrado" in table and "Cambio anterior" in table
    downloads = st.named("download_button")
    assert len(downloads) == 1
    assert downloads[0][2]["file_name"] == f"{METRIC}_2026-6.csv"
    assert b"Semana,Logrado,Meta" in downloads[0][1][1]


# ── The link a card carries ──────────────────────────────────────────────────

def test_ki_href_carries_the_scope_and_drops_blanks():
    assert ki_href(METRIC) == f"?{KI_PARAM}={METRIC}"
    href = ki_href(METRIC, {"bd_zone": "Angol", "bd_district": "", "bd_area": None})
    assert href == f"?{KI_PARAM}={METRIC}&bd_zone=Angol"
