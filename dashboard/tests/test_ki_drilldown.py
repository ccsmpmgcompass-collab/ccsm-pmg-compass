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
#: A nightly metric, which the panel has opened on since plan step D3 —
#: the twenty rows on Desgloses link here the same way the cards do.
NIGHT = "contacts_made"
NIGHTLY = {"contacts_made": "Contactos",
           "friend_lessons": "Lecciones con Amigos"}
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


#: The nights area A files: three in cambio 2026-5, three in week 1 of 2026-6
#: and two in the week in progress.
_A_NIGHTS = ("2026-08-31", "2026-09-01", "2026-09-02",
             "2026-09-07", "2026-09-08", "2026-09-09",
             "2026-09-14", "2026-09-15")
#: Area B files one night a week, so the rankings and the missed-night counts
#: have two areas to tell apart.
_B_NIGHTS = ("2026-08-31", "2026-09-07", "2026-09-14")


def _nights() -> pd.DataFrame:
    """DAILY_LOG for the two areas: a cycle, a twin cycle and real gaps."""
    return pd.DataFrame(
        [{"Date": d, "Area": "A", NIGHT: 10, "friend_lessons": 5}
         for d in _A_NIGHTS]
        + [{"Date": d, "Area": "B", NIGHT: 6, "friend_lessons": 3}
           for d in _B_NIGHTS])


@pytest.fixture
def stubbed(monkeypatch):
    """Wire the panel to synthetic data and a recording `st`; returns a
    factory taking the query params and pills answers."""
    import app.db.queries as queries
    import app.db.goals_queries as gq
    import app.utils.transfer_helpers as th

    monkeypatch.setattr(dd, "key_indicator_metrics", lambda: dict(KIS))
    monkeypatch.setattr(dd, "nightly_metrics", lambda: dict(NIGHTLY))
    monkeypatch.setattr(dd, "get_area_weekly_goals", lambda: {NIGHT: 30.0})
    monkeypatch.setattr(dd, "mission_today", lambda: TODAY)
    monkeypatch.setattr(dd, "transfer_window",
                        lambda offset=0, today=None: {0: CUR, 1: PREV}.get(offset))
    monkeypatch.setattr(dd, "group_goal_totals", lambda start, areas=None: {METRIC: 60.0})
    monkeypatch.setattr(dd, "get_daily_log", lambda days=365: _nights())
    monkeypatch.setattr(queries, "get_daily_log", lambda days=365: _nights())
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


def test_a_key_in_no_catalogue_closes_the_panel(stubbed):
    """A stale or mistyped ?ki= opens nothing. "contacts_made" used to be this
    test's example and is now a legitimate target — the panel opens on the
    nightly metrics too since plan step D3 — so the example is a key that
    exists on neither form."""
    st = stubbed({KI_PARAM: "not_a_metric_at_all"})
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
    # Nights due: Mon 7 Sep – Thu 17 Sep, eleven of them. A filed five and B
    # filed two (the _nights fixture), so the two rows carry different counts
    # — the point being that this number comes from DAILY_LOG and not from the
    # weekly form the bars above it are drawn from.
    assert "6 noches sin informe" in html
    assert "9 noches sin informe" in html
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


# ── Opened on a nightly metric (plan step D3) ────────────────────────────────
# The twenty nightly rows on Desgloses link into this same panel. What differs
# is underneath: DAILY_LOG bucketed into Mon–Sun weeks instead of the weekly
# form, and AGENT_CONFIG's per-area weekly goal instead of a meta.

def test_a_nightly_metric_opens_the_panel(stubbed):
    st = stubbed({KI_PARAM: NIGHT})
    assert selected_ki() == NIGHT
    assert _render(st) is True
    strip, tabs = st.named("pills")
    assert NIGHT in strip[1][1], "the open metric must be an option on the strip"
    assert tabs[1][1] == TABS


def test_the_strip_still_leads_with_the_seven(stubbed):
    """A nightly metric joins the END of the strip. The seven are the
    mission's Key Indicators and they do not move aside for a row someone
    tapped."""
    st = stubbed({KI_PARAM: NIGHT})
    _render(st)
    options = st.named("pills")[0][1][1]
    assert options[:len(KIS)] == list(KIS)
    assert options[len(KIS)] == NIGHT


def test_the_nightly_weeks_come_from_the_daily_log(stubbed):
    """Two areas filing 10 and 6 a night for three nights of the cycle's first
    week is 48, not a weekly-form reading of nothing."""
    st = stubbed({KI_PARAM: NIGHT}, {"ki_dd_tab": TAB_WEEK})
    _render(st)
    fig = st.named("plotly_chart")[0][1][0]
    # Two bar traces — the ghosts first so the current cambio sits in front of
    # them — plus a pace marker, so the cambio on screen is the last BAR.
    actual = list([tr for tr in fig.data if tr.type == "bar"][-1].y)
    assert actual[0] == 36          # A's three nights at 10, B's one at 6


def test_the_nightly_goal_is_the_per_area_figure_times_who_reported(stubbed):
    """AGENT_CONFIG's GOAL_contacts_made is 30 per area per week, and two areas
    reported — so the week's goal is 60, not 30 and not forty-five areas'
    worth. The same arithmetic the row on Desgloses shows as "% de"."""
    st = stubbed({KI_PARAM: NIGHT}, {"ki_dd_tab": TAB_WEEK})
    _render(st)
    fig = st.named("plotly_chart")[0][1][0]
    goals = [s.y0 for s in fig.layout.shapes if s.type == "line"]
    assert 60.0 in goals


def test_a_nightly_metric_asks_for_no_transfer_goal(stubbed, monkeypatch):
    """AREA_TRANSFER_GOALS is keyed on the seven Key Indicators. Reading it for
    a nightly metric would be a sheet call that can only ever return nothing."""
    called = []
    monkeypatch.setattr(dd, "group_goal_totals",
                        lambda start, areas=None: called.append(start) or {})
    st = stubbed({KI_PARAM: NIGHT})
    _render(st)
    assert called == []


def test_the_nightly_panel_names_the_form_it_reads(stubbed):
    st = stubbed({KI_PARAM: NIGHT})
    _render(st)
    heading = [c for c in st.named("markdown") if "areas" in str(c[1])]
    assert any("nightly report" in str(c[1]) or "informe nocturno" in str(c[1])
               for c in st.calls if c[0] == "markdown")


def test_the_nightly_area_ranking_stops_at_the_last_complete_week(stubbed):
    """An area's nightly goal is per WEEK. Comparing the week in progress
    against a whole week's goal reads as a shortfall the area has not had the
    chance to avoid, so the window ends on the last Sunday — and the caption
    says so rather than naming today."""
    st = stubbed({KI_PARAM: NIGHT}, answers={"ki_dd_tab": TAB_AREA})
    _render(st)
    caption = " ".join(str(c[1]) for c in st.named("caption"))
    assert "13 de sep" in caption          # the Sunday, not Friday the 18th
    html = next(c[1][0] for c in st.named("markdown") if "pmg-ranked" in c[1][0])
    # A: three nights at 10 in that week against a 30 goal; B: one at 6.
    assert html.index(">A<") < html.index(">B<")
    assert "1 semana" in html
