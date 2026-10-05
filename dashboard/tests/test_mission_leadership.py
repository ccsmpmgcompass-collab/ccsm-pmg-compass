"""MISSION_LEADERSHIP, and who the app treats as leadership.

PLAN-2026-10-05-roster-access.md D1, D2, D9. MISSION_ORG cannot name the
President or the assistants (its one Is_AP row is a mailbox four missionaries
share; no row is flagged Is_MP), so they reached the app only through addresses
typed into auth.py. The tab replaces that list. And the leadership pages —
Traslados' Apply, Editar Envíos, Mantenimiento's settings — stop opening for
zone, district and sister training leaders' shared area mailboxes.
"""

import pandas as pd
import pytest

from app.auth import auth
from app.db import queries as q

_ORG = pd.DataFrame([
    # The AP area: four missionaries, one mailbox.
    {"Area_Name": "La Marina 1", "Zone": "San Pedro", "District": "La Marina 1",
     "Companion1_Name": "Anderson Phillips", "Companion1_Email": "500407562@missionary.org",
     "Companion2_Name": "Presley Egbers", "Companion2_Email": "500407562@missionary.org",
     "Is_DL": "FALSE", "Is_ZL": "FALSE", "Is_STL": "FALSE", "Is_AP": "TRUE",
     "Is_MP": "FALSE", "Active": "TRUE"},
    # A zone leader's area.
    {"Area_Name": "Alemania 1", "Zone": "Angol", "District": "Puren",
     "Companion1_Name": "Said Adasme", "Companion1_Email": "500388234@missionary.org",
     "Companion2_Name": "Gustavo Caetano", "Companion2_Email": "500388234@missionary.org",
     "Is_DL": "FALSE", "Is_ZL": "TRUE", "Is_STL": "FALSE", "Is_AP": "FALSE",
     "Is_MP": "FALSE", "Active": "TRUE"},
    # An ordinary area.
    {"Area_Name": "Alemania 2", "Zone": "Angol", "District": "Los Confines",
     "Companion1_Name": "Benny Jimenez", "Companion1_Email": "500495012@missionary.org",
     "Companion2_Name": "", "Companion2_Email": "",
     "Is_DL": "FALSE", "Is_ZL": "FALSE", "Is_STL": "FALSE", "Is_AP": "FALSE",
     "Is_MP": "FALSE", "Active": "TRUE"},
])

_LEADERS = pd.DataFrame([
    {"Name": "Presidente Gutierrez", "Email": " GutierrezSauceDom@ChurchOfJesusChrist.org ",
     "Role": "President", "Active": "TRUE", "Notes": ""},
    {"Name": "Anderson Phillips", "Email": "anderson.phillips@missionary.org",
     "Role": "assistant", "Active": "TRUE", "Notes": ""},
    {"Name": "Hyrum Turner", "Email": "hyrum.turner@missionary.org",
     "Role": "assistant", "Active": "FALSE", "Notes": "went home 2026-09"},
    {"Name": "Typo", "Email": "not-an-address", "Role": "assistant",
     "Active": "TRUE", "Notes": ""},
    {"Name": "Wrong role", "Email": "zl@missionary.org", "Role": "zone leader",
     "Active": "TRUE", "Notes": ""},
])

_TABS: dict = {}


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    _TABS.clear()
    _TABS.update({"MISSION_ORG": _ORG, q.LEADERSHIP_TAB: _LEADERS})

    def fake(tab_name, header_marker=None):
        return _TABS.get(tab_name, pd.DataFrame()).copy()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    yield


# ── the tab ───────────────────────────────────────────────────────────────────

def test_only_valid_active_rows_count():
    roles = q.get_leadership_roles()
    assert roles == {
        "gutierrezsaucedom@churchofjesuschrist.org": "president",
        "anderson.phillips@missionary.org": "assistant",
    }


def test_an_inactive_row_is_kept_for_the_editor():
    every = q.get_mission_leadership(active_only=False)
    assert "hyrum.turner@missionary.org" in set(every["Email"])


def test_no_tab_means_no_leaders_from_it():
    del _TABS[q.LEADERSHIP_TAB]
    assert q.get_leadership_roles() == {}
    # ...and MISSION_ORG's flags still answer — but an AP area's mailbox is a
    # LEADER (it leads its district), never an assistant (D11).
    assert q.get_user_role("500407562@missionary.org") == "leader"


# ── roles ─────────────────────────────────────────────────────────────────────

def test_the_tab_names_the_president():
    assert q.get_user_role("gutierrezsaucedom@churchofjesuschrist.org") == "president"


def test_mission_org_still_names_area_mailboxes():
    assert q.get_user_role("500388234@missionary.org") == "leader"
    assert q.get_user_role("500495012@missionary.org") == "missionary"
    assert q.get_user_role("stranger@gmail.com") == "unknown"


# ── who opens the leadership pages (D2, D9) ───────────────────────────────────

@pytest.mark.parametrize("email,expected", [
    ("gutierrezsaucedom@churchofjesuschrist.org", True),   # tab: president
    ("anderson.phillips@missionary.org", True),            # tab: assistant
    ("500407562@missionary.org", False),                   # AP area's shared mailbox (D11)
    ("zackary.butterfield@missionary.org", True),          # owner
    ("ccsm.pmg.compass@gmail.com", True),                  # system
    ("500388234@missionary.org", False),                   # a zone leader's mailbox
    ("500495012@missionary.org", False),                   # an ordinary area
    ("hyrum.turner@missionary.org", False),                # inactive row
    ("grayden16gmc@gmail.com", False),                     # signs in, is not leadership
])
def test_is_leadership(email, expected):
    assert auth.is_leadership(email) is expected


def test_a_zone_leader_still_signs_in():
    """D2 narrows the leadership PAGES, not sign-in (2026-08-22 decision)."""
    assert "500388234@missionary.org" in auth.allowed_emails()
    assert "500407562@missionary.org" in auth.allowed_emails()


def test_the_task_roster_is_the_tab_not_the_ap_mailbox():
    """Centro de Acción hands tasks to these people. It was MISSION_ORG's AP
    row — the shared mailbox, which can no longer open the page (D11)."""
    from app.db.action_center_queries import get_leadership_roster
    assert [r["email"] for r in get_leadership_roster()] == [
        "anderson.phillips@missionary.org",
        "gutierrezsaucedom@churchofjesuschrist.org"]


def test_the_tab_lets_leaders_sign_in_with_their_own_address():
    allowed = auth.allowed_emails()
    assert "anderson.phillips@missionary.org" in allowed
    assert "gutierrezsaucedom@churchofjesuschrist.org" in allowed
    assert "hyrum.turner@missionary.org" not in allowed


def test_leaders_are_no_longer_hardcoded():
    """A leader typed into auth.py outlives his assignment — Hyrum Turner had to
    be removed by hand. They live in the tab now."""
    for email in ("anderson.phillips@missionary.org", "presley.egbers@missionary.org",
                  "gutierrezsaucedom@churchofjesuschrist.org"):
        assert email not in auth._ALWAYS_ALLOWED


@pytest.mark.parametrize("user,expected", [
    ({"email": "gutierrezsaucedom@churchofjesuschrist.org", "role": "president"}, True),
    ({"email": "anderson.phillips@missionary.org", "role": "assistant"}, True),
    ({"email": "zackary.butterfield@missionary.org", "role": "unknown"}, True),
    ({"email": "500388234@missionary.org", "role": "leader"}, False),
    ({"email": "500407562@missionary.org", "role": "leader"}, False),
    ({"email": "grayden16gmc@gmail.com", "role": "unknown"}, False),
])
def test_who_sets_goals(user, expected):
    assert auth.can_set_goals(user) is expected


# ── saving ────────────────────────────────────────────────────────────────────

def test_validation_names_each_problem():
    problems = q.validate_leadership_rows([
        {"Name": "A", "Email": "a@missionary.org", "Role": "assistant"},
        {"Name": "B", "Email": "b at missionary", "Role": "assistant"},
        {"Name": "C", "Email": "c@missionary.org", "Role": "zone leader"},
        {"Name": "D", "Email": "A@missionary.org", "Role": "assistant"},
        {"Name": "", "Email": "", "Role": ""},     # an empty editor line
    ])
    assert len(problems) == 3
    assert any(p.startswith("B:") for p in problems)
    assert any(p.startswith("C:") for p in problems)
    assert any(p.startswith("D:") and "twice" in p for p in problems)


def test_save_writes_the_header_and_normalised_rows(monkeypatch):
    written = {}
    monkeypatch.setattr("app.db.sheets_client.overwrite_tab",
                        lambda tab, rows, **kw: written.update({tab: rows}))
    q.save_mission_leadership([
        {"Name": "Presley Egbers", "Email": " Presley.Egbers@missionary.org",
         "Role": "Assistant", "Active": True, "Notes": ""},
        {"Name": "", "Email": "", "Role": "", "Active": True},
        {"Name": "Old AP", "Email": "old@missionary.org", "Role": "assistant",
         "Active": False, "Notes": "released"},
    ])
    assert written[q.LEADERSHIP_TAB] == [
        ["Name", "Email", "Role", "Active", "Notes"],
        ["Presley Egbers", "presley.egbers@missionary.org", "assistant", "TRUE", ""],
        ["Old AP", "old@missionary.org", "assistant", "FALSE", "released"],
    ]


def test_save_refuses_a_bad_row(monkeypatch):
    monkeypatch.setattr("app.db.sheets_client.overwrite_tab",
                        lambda tab, rows, **kw: pytest.fail("must not write"))
    with pytest.raises(ValueError):
        q.save_mission_leadership([{"Name": "X", "Email": "nope", "Role": "assistant"}])
