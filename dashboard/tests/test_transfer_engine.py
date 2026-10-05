"""Unit tests for transfer_engine — CCSM's port of the pure roster-merge logic
(see dashboard/app/ingestion/transfer_engine.py for provenance). Pure functions
only; no Google Sheets access.
"""

import datetime as dt

import pytest

from app.ingestion import transfer_engine as te


# ── Fixtures ──────────────────────────────────────────────────────────────────

MISSION_ORG_HEADERS = [
    "Area_Code", "Area_Name", "Zone", "District",
    "Companion1_Name", "Companion1_Email", "Companion2_Name", "Companion2_Email",
    "Is_DL", "Is_ZL", "Is_STL", "Is_AP", "Is_MP", "Active",
]


def _org_row(name, zone="Angol", district="Alemania 2", active="TRUE",
             c1="", c2="", email="", **flags):
    row = {h: "" for h in MISSION_ORG_HEADERS}
    row.update({
        "Area_Name": name, "Zone": zone, "District": district,
        "Companion1_Name": c1, "Companion2_Name": c2,
        "Companion1_Email": email, "Active": active,
        "Is_ZL": "FALSE", "Is_STL": "FALSE", "Is_DL": "FALSE",
        "Is_AP": "FALSE", "Is_MP": "FALSE",
    })
    row.update(flags)
    return row


def _roster_import(area, zone="Angol", district="Alemania 2",
                   c1="Elder A", c2="", calling="", email=""):
    """A TRANSFER_IMPORT-shaped row (header keys: Area, Zone, ...)."""
    return {
        "Area": area, "Zone": zone, "District": district,
        "Companion1_Name": c1, "Companion2_Name": c2,
        "Companion3_Name": "", "Companion4_Name": "",
        "Calling": calling, "Area_Email": email,
    }


# ── parse_roster ────────────────────────────────────────────────────────────────

def test_parse_roster_maps_area_and_sets_active_true():
    rows = te.parse_roster([_roster_import("Alemania 2")])
    assert len(rows) == 1
    r = rows[0]
    assert r["Area_Name"] == "Alemania 2"
    assert r["Active"] == "TRUE"


def test_parse_roster_skips_blank_area():
    rows = te.parse_roster([_roster_import(""), _roster_import("Real Area")])
    assert [r["Area_Name"] for r in rows] == ["Real Area"]


@pytest.mark.parametrize("calling,flag", [
    ("ZL", "Is_ZL"),
    ("STL", "Is_STL"),
    ("DL", "Is_DL"),
    ("AP", "Is_AP"),
    ("MP", "Is_MP"),
])
def test_parse_roster_calling_sets_correct_flag(calling, flag):
    r = te.parse_roster([_roster_import("A", calling=calling)])[0]
    assert r[flag] == "TRUE"
    others = {"Is_ZL", "Is_STL", "Is_DL", "Is_AP", "Is_MP"} - {flag}
    assert all(r[o] == "FALSE" for o in others)


def test_parse_roster_no_calling_all_flags_false():
    r = te.parse_roster([_roster_import("A", calling="")])[0]
    assert all(r[f] == "FALSE" for f in ("Is_ZL", "Is_STL", "Is_DL", "Is_AP", "Is_MP"))


# ── non-teaching-row detection ──────────────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "Mission President",
    "Assistant to President 1",
    "Zone Leader 1 - Angol",
    "Sister Training Leader - Temuco",
    "District Leader - Villarrica",
])
def test_is_non_teaching_row_true(name):
    assert te.is_non_teaching_row(_org_row(name)) is True


def test_is_non_teaching_row_false_for_real_area_with_leadership_flag():
    assert te.is_non_teaching_row(_org_row("Alemania 2", Is_DL="TRUE")) is False


# ── run_guards ───────────────────────────────────────────────────────────────────

def test_run_guards_blocks_empty_roster():
    guard = te.run_guards([], [_org_row("A")])
    assert guard["ok"] is False


def test_run_guards_blocks_over_30pct_deactivation():
    org = [_org_row(f"Area{i}") for i in range(10)]
    roster = te.parse_roster([_roster_import("Area0"), _roster_import("Area1")])
    guard = te.run_guards(roster, org)
    assert guard["ok"] is False
    assert "80%" in guard["msg"]


def test_run_guards_override_skips_the_check():
    org = [_org_row(f"Area{i}") for i in range(10)]
    roster = te.parse_roster([_roster_import("Area0")])
    guard = te.run_guards(roster, org, override=True)
    assert guard["ok"] is True


def test_run_guards_ignores_non_teaching_rows_in_denominator():
    org = [_org_row("Area0"), _org_row("Mission President")]
    roster = te.parse_roster([_roster_import("Area0")])
    guard = te.run_guards(roster, org)
    assert guard["ok"] is True


# ── build_diff ───────────────────────────────────────────────────────────────────

def test_build_diff_flags_new_area():
    diff = te.build_diff(te.parse_roster([_roster_import("New Area")]), [])
    assert any("New Area" in a for a in diff["added"])


def test_build_diff_flags_deactivated_area():
    org = [_org_row("Gone Now")]
    diff = te.build_diff([], org)
    assert diff["deactivated"] == ["Gone Now"]


def test_build_diff_flags_companion_change():
    org = [_org_row("A", c1="Elder Old")]
    roster = te.parse_roster([_roster_import("A", c1="Elder New")])
    diff = te.build_diff(roster, org)
    assert len(diff["changed"]) == 1
    assert "Elder Old" in diff["changed"][0] and "Elder New" in diff["changed"][0]


def test_build_diff_flags_reactivation():
    org = [_org_row("A", active="FALSE")]
    roster = te.parse_roster([_roster_import("A", c1="Elder New")])
    diff = te.build_diff(roster, org)
    assert len(diff["reactivated"]) == 1


# ── apply_transfer ───────────────────────────────────────────────────────────────

def test_apply_transfer_updates_matched_area_preserves_email():
    org = [_org_row("A", c1="Elder Old", email="500001@missionary.org")]
    roster = te.parse_roster([_roster_import("A", c1="Elder New")])
    new_rows, summary = te.apply_transfer(roster, org, MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "A")
    assert row["Companion1_Name"] == "Elder New"
    assert row["Companion1_Email"] == "500001@missionary.org"
    assert row["Active"] == "TRUE"


def test_apply_transfer_deactivates_unmatched_active_area():
    org = [_org_row("Gone", email="500002@missionary.org")]
    new_rows, summary = te.apply_transfer([], org, MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "Gone")
    assert row["Active"] == "FALSE"
    assert row["Companion1_Name"] == ""
    assert "Gone (500002@missionary.org)" in summary["deactivated_with_email"]


def test_apply_transfer_new_area_without_a_roster_email_is_flagged():
    roster = te.parse_roster([_roster_import("Brand New")])
    new_rows, summary = te.apply_transfer(roster, [], MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "Brand New")
    assert row["Companion1_Email"] == ""
    assert "Brand New" in summary["new_emails_needed"]
    assert summary["emails_filled"] == []


# ── email fill (PLAN-2026-10-05 R1) ─────────────────────────────────────────────

def test_a_new_area_takes_its_mailbox_from_the_roster():
    """The 2026-09-07 transfer opened seven areas with blank emails, and the
    reminder agent mails only the email columns — so none of them was asked to
    report until someone typed the addresses in by hand."""
    roster = te.parse_roster([_roster_import(
        "Collipulli 1", c1="Elder A", c2="Elder B", email="500111@missionary.org")])
    new_rows, summary = te.apply_transfer(roster, [], MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "Collipulli 1")
    assert row["Companion1_Email"] == "500111@missionary.org"
    assert row["Companion2_Email"] == "500111@missionary.org"
    assert summary["emails_filled"] == ["Collipulli 1"]
    assert summary["new_emails_needed"] == []


def test_a_single_companion_gets_the_address_once():
    roster = te.parse_roster([_roster_import(
        "Collipulli 2", c1="Elder A", email="500222@missionary.org")])
    new_rows, _ = te.apply_transfer(roster, [], MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "Collipulli 2")
    assert row["Companion1_Email"] == "500222@missionary.org"
    assert row["Companion2_Email"] == ""


def test_an_existing_blank_email_is_filled_and_a_set_one_is_kept():
    org = [_org_row("Blank", c1="Elder A"),
           _org_row("Set", c1="Elder C", email="hand@missionary.org")]
    roster = te.parse_roster([
        _roster_import("Blank", c1="Elder A", email="500333@missionary.org"),
        _roster_import("Set", c1="Elder C", email="500444@missionary.org"),
    ])
    new_rows, summary = te.apply_transfer(roster, org, MISSION_ORG_HEADERS)
    rows = {r["Area_Name"]: r for r in new_rows}
    assert rows["Blank"]["Companion1_Email"] == "500333@missionary.org"
    assert rows["Set"]["Companion1_Email"] == "hand@missionary.org"
    assert summary["emails_filled"] == ["Blank"]
    assert summary["email_mismatches"] == [
        "Set: kept hand@missionary.org, roster has 500444@missionary.org"]


def test_a_matching_email_is_neither_filled_nor_flagged():
    org = [_org_row("Same", c1="Elder A", email="500555@missionary.org")]
    roster = te.parse_roster([_roster_import("Same", c1="Elder A",
                                             email="500555@MISSIONARY.org")])
    _, summary = te.apply_transfer(roster, org, MISSION_ORG_HEADERS)
    assert summary["emails_filled"] == []
    assert summary["email_mismatches"] == []


def test_the_preview_says_where_each_email_comes_from():
    org = [_org_row("Blank", c1="Elder A"),
           _org_row("Set", c1="Elder C", email="hand@missionary.org")]
    roster = te.parse_roster([
        _roster_import("Blank", c1="Elder A", email="500333@missionary.org"),
        _roster_import("Set", c1="Elder C", email="500444@missionary.org"),
        _roster_import("Opened", email="500666@missionary.org"),
        _roster_import("No Mailbox"),
    ])
    diff = te.build_diff(roster, org)
    assert "Opened (NEW — email 500666@missionary.org from the roster)" in diff["added"]
    assert any(a.startswith("No Mailbox (NEW — no email") for a in diff["added"])
    assert "Blank: 500333@missionary.org" in diff["emails"]
    assert any(e.startswith("Set: kept hand@missionary.org") for e in diff["emails"])


def test_apply_transfer_never_touches_leadership_rows():
    org = [_org_row("Mission President", c1="President Smith")]
    new_rows, _ = te.apply_transfer([], org, MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "Mission President")
    assert row["Companion1_Name"] == "President Smith"


# ── next_schedule_update ─────────────────────────────────────────────────────────

def test_next_schedule_update_flips_planned_to_actual():
    rows = [{"Transfer_Number": "5", "Start_Date": "", "Weeks": "6", "Status": "Planned"}]
    out = te.next_schedule_update(rows, dt.date(2026, 8, 5))
    assert out[0]["Status"] == "Actual"
    assert out[0]["Start_Date"] == "2026-08-05"


def test_next_schedule_update_appends_when_none_planned():
    rows = [{"Transfer_Number": "5", "Start_Date": "2026-06-01", "Weeks": "6", "Status": "Actual"}]
    out = te.next_schedule_update(rows, dt.date(2026, 8, 5))
    assert len(out) == 2
    assert out[1]["Transfer_Number"] == "6"
    assert out[1]["Status"] == "Actual"


# ── the assistants' area (PLAN-2026-10-05 R4) ─────────────────────────────────

def _ap_row(*names, active="TRUE"):
    row = _org_row("La Marina 1", zone="San Pedro", active=active, Is_AP="TRUE")
    for i, n in enumerate(names, start=1):
        row[f"Companion{i}_Name"] = n
    return row


def test_a_listed_assistant_still_in_the_ap_area_is_not_flagged():
    rows = [_ap_row("Anderson Phillips", "Presley Egbers", "Bryson Heath", "James Blood")]
    assert te.assistants_missing_from_ap_area(
        ["Anderson Phillips", "Elder Egbers", "élder PHILLIPS"], rows) == []


def test_an_assistant_moved_out_is_flagged():
    rows = [_ap_row("Anderson Phillips", "Nuevo Asistente")]
    assert te.assistants_missing_from_ap_area(
        ["Anderson Phillips", "Presley Egbers"], rows) == ["Presley Egbers"]


def test_no_ap_row_means_nothing_to_compare():
    rows = [_org_row("Alemania 2", c1="Elder A")]
    assert te.assistants_missing_from_ap_area(["Anyone"], rows) == []


def test_an_inactive_ap_row_does_not_count():
    rows = [_ap_row("Presley Egbers", active="FALSE"), _ap_row("Someone Else")]
    assert te.assistants_missing_from_ap_area(["Presley Egbers"], rows) == ["Presley Egbers"]


def test_the_roster_shape_works_too():
    roster = te.parse_roster([{
        "Area": "La Marina 1", "Zone": "San Pedro", "District": "La Marina 1",
        "Companion1_Name": "Anderson Phillips", "Companion2_Name": "Presley Egbers",
        "Companion3_Name": "Bryson Heath", "Companion4_Name": "James Blood",
        "Calling": "AP", "Area_Email": "500407562@missionary.org"}])
    assert te.assistants_missing_from_ap_area(["James Blood"], roster) == []
    assert te.assistants_missing_from_ap_area(["Hyrum Turner"], roster) == ["Hyrum Turner"]
