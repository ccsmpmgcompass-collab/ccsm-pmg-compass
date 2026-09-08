"""A brand-new area borrows its zone's typical figure instead of the floor of 1.

The 2026-09-07 transfer opened seven areas. Every Key Indicator recommended
exactly 1 for each of them — the floor in `get_recommended_transfer_goals`,
which exists so a badge never reads 0 — while Alemania 2 was recommended 60 new
people and Vilcun 82. Bulk-applying that would have set each new area a six-week
goal of finding one person, after which its goal bars would have read as
triumphant all cycle.

Zackary, 2026-09-08: "when an area doesn't have history fall back to the zone's
median is a good idea."

The floor is still right for an established area that genuinely scores zero on a
metric; it is wrong for an area that has never reported at all. These tests pin
the difference.
"""

import pandas as pd
import pytest

import app.db.queries as q
from app.config import metric_catalog as mc

QUESTIONS = pd.DataFrame([
    {"Metric_Key": "ki_new_people_real", "Metric_Display_Name": "Nuevas Personas (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "ki_baptized_confirmed_real",
     "Metric_Display_Name": "Bautizados y Confirmados (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
])

#: Two zones that perform very differently — the whole reason zone beats
#: mission. Angol averages 10/week, Arauco 2/week; the mission median is 6.
WEEKLY = pd.DataFrame(
    [{"area": a, "zone": z, "week_end_date": d,
      "ki_new_people_real": v, "ki_baptized_confirmed_real": 0}
     for a, z, v in [("Alemania 1", "Angol", 10), ("Alemania 2", "Angol", 10),
                     ("Lebu 1", "Arauco", 2), ("Lebu 2", "Arauco", 2)]
     for d in ("2026-08-09", "2026-08-16", "2026-08-23")]
)

ORG = pd.DataFrame([
    {"Area_Name": "Alemania 1", "Zone": "Angol"},
    {"Area_Name": "Alemania 2", "Zone": "Angol"},
    {"Area_Name": "Lebu 1", "Zone": "Arauco"},
    {"Area_Name": "Lebu 2", "Zone": "Arauco"},
    {"Area_Name": "Collipulli 1", "Zone": "Angol"},     # new, no history
    {"Area_Name": "Cañete 9", "Zone": "Arauco"},        # new, no history
    {"Area_Name": "Huérfana", "Zone": "Sin Datos"},     # new, zone has none either
])


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(
        "app.db.sheets_client._read_tab_cached",
        lambda tab, header_marker=None: (
            QUESTIONS.copy() if tab == "QUESTIONS_CONFIG" else pd.DataFrame()))
    monkeypatch.setattr(q, "get_weekly_ki", lambda: pd.DataFrame())
    monkeypatch.setattr(q, "get_weekly_form_data", lambda: WEEKLY.copy())
    monkeypatch.setattr(q, "get_areas_df", lambda: ORG.copy())
    monkeypatch.setattr(q, "get_question_metrics", lambda: [
        (r["Metric_Key"], r["Metric_Display_Name"], r["Form_Type"])
        for _, r in QUESTIONS.iterrows()])
    monkeypatch.setattr(q, "get_rec_stretch_pct", lambda: 10)
    mc.clear_cache()
    q.get_recommended_transfer_goals.clear()
    yield
    q.get_recommended_transfer_goals.clear()
    mc.clear_cache()


NP = "ki_new_people_real"


def _rec(area, weeks=6.0):
    return q.get_recommended_transfer_goals(area, weeks)


def test_a_new_area_is_not_recommended_one(live):
    """The bug this fixes: seven new areas all recommended 1 for everything."""
    assert _rec("Collipulli 1")[NP] > 1


def test_a_new_area_takes_its_own_zones_median(live):
    """Angol averages 10 a week, so six weeks is 60 — not the mission's 36."""
    assert _rec("Collipulli 1")[NP] == 60


def test_zone_beats_mission(live):
    """The same mission, the other zone: 2 a week over six weeks is 12.

    If this returned the same number as Collipulli 1, the fallback would be
    mission-wide and the zones' real differences would be papered over."""
    assert _rec("Cañete 9")[NP] == 12
    assert _rec("Cañete 9")[NP] != _rec("Collipulli 1")[NP]


def test_a_zone_with_no_history_falls_back_to_the_mission(live):
    """Median of the four areas' weekly means (10, 10, 2, 2) is 6; x6 = 36."""
    assert _rec("Huérfana")[NP] == 36


def test_an_area_with_its_own_history_is_untouched(live):
    """10 a week, stretched 10%, over six weeks: ceil(10 x 1.1 x 6) = 66.

    The borrowed baseline must never override a real average — including here,
    where the area's own figure is HIGHER than its zone's median."""
    assert _rec("Alemania 1")[NP] == 66


def test_a_borrowed_figure_carries_no_stretch(live):
    """60 is 10 x 6, not ceil(10 x 1.1 x 6) = 66.

    `_stretch_means` nudges by 10% because it asks an area to beat its OWN
    average. Nudging a borrowed number asks a brand-new area to beat the typical
    area in its zone, in its first cycle, which is a different thing to ask."""
    assert _rec("Collipulli 1")[NP] == 60


def test_the_floor_still_applies_where_peers_have_nothing_either(live):
    """Every area reports 0 baptisms, so the peer median is 0 — and a goal of 0
    is the one thing the floor exists to prevent."""
    assert _rec("Collipulli 1")["ki_baptized_confirmed_real"] == 1
    assert _rec("Alemania 1")["ki_baptized_confirmed_real"] == 1


def test_the_basis_is_reported_so_the_page_can_say_so(live):
    """A borrowed number that looks measured is worse than no number."""
    assert q.transfer_rec_basis("Collipulli 1", 6.0)[NP] == "zone"
    assert q.transfer_rec_basis("Huérfana", 6.0)[NP] == "mission"
    assert q.transfer_rec_basis("Alemania 1", 6.0)[NP] == "own"
