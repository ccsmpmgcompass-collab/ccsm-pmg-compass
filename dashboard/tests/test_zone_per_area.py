"""Zones are compared per area, never by raw total.

Audit item 3 (finding C2). The Panel's zone table ranked on DASHBOARD_SUMMARY's
raw 7-day ZONE totals, which rank by how many areas a zone has. Zones here run
8 to 13 areas, so on 2026-08-20 Los Angeles Norte displayed first on contact
attempts with 1,289 across 11 areas — 117 per area — above Angol's 1,266 across
8, which is 158 per area and actually first.

Every fixture below is synthetic and sized so the two rankings DISAGREE. A
fixture where the big zone also wins per area would pass against the old code.
"""

import pandas as pd

from app.analytics.zone_comparison import (
    EFFECTIVENESS,
    active_areas_by_zone,
    effectiveness_is_rankable,
    ki_scored_area_count,
    zone_per_area_table,
)

FUNNEL = ["contacts_attempted", "contacts_made", "friend_lessons",
          "baptismal_invitations"]


def _areas(*spec) -> pd.DataFrame:
    """spec: (zone, n_areas) pairs -> a MISSION_ORG-shaped frame."""
    rows = []
    for zone, n in spec:
        for i in range(1, n + 1):
            rows.append({"Area_Code": f"{zone[:2].upper()}{i:02d}",
                         "Area_Name": f"{zone} {i}", "Zone": zone,
                         "District": zone, "Active": "TRUE"})
    return pd.DataFrame(rows)


def _summary(*spec) -> pd.DataFrame:
    """spec: (zone, {metric_key: val_7d}) pairs -> DASHBOARD_SUMMARY ZONE rows."""
    rows = []
    for zone, metrics in spec:
        for key, val in metrics.items():
            rows.append({"record_type": "ZONE", "metric_key": key,
                         "metric_name": key, "zone": zone, "area": "",
                         "district": "", "val_7d": val, "val_14d": val,
                         "val_28d": val, "val_transfer": val})
    return pd.DataFrame(rows)


def _scores(*spec) -> pd.DataFrame:
    """spec: (zone, [(effectiveness, ki), ...]) -> one week of SCORES rows."""
    rows = []
    for zone, areas in spec:
        for i, (eff, ki) in enumerate(areas, start=1):
            rows.append({"Area_Code": f"{zone[:2].upper()}{i:02d}",
                         "Area_Name": f"{zone} {i}", "Zone": zone,
                         "Week_Ending_Date": "2026-08-16",
                         "Effort_Score": eff, "Skill_Score": eff,
                         "KI_Score": ki, "Effectiveness_Score": eff})
    return pd.DataFrame(rows)


def _ranked(table: pd.DataFrame, by: str) -> list:
    """Zone names in the order the page would print them."""
    return table.sort_values(by, ascending=False)["zone"].tolist()


# ── The core fix ──────────────────────────────────────────────────────────────

def test_a_bigger_zone_does_not_outrank_a_harder_working_smaller_one():
    """The live 2026-08-20 case, to scale: 11 areas x 117 vs 8 areas x 158."""
    table = zone_per_area_table(
        _summary(("Los Angeles Norte", {"contacts_attempted": 1289}),
                 ("Angol",             {"contacts_attempted": 1266})),
        _areas(("Los Angeles Norte", 11), ("Angol", 8)),
        FUNNEL,
    )
    assert _ranked(table, "contacts_attempted")[0] == "Angol", (
        "ranked by raw total again — the bigger zone won on volume alone")

    per_area = table.set_index("zone")["contacts_attempted"]
    assert round(per_area["Angol"], 1) == 158.2
    assert round(per_area["Los Angeles Norte"], 1) == 117.2


def test_the_divisor_is_every_active_area_not_the_ones_that_reported():
    """A zone whose areas went silent ranks lower, on purpose.

    Only the zone's total reaches DASHBOARD_SUMMARY — nothing in it says how
    many areas contributed — so dividing by "who reported" would let 4 working
    areas out of 13 carry a zone to the top with nothing on screen saying so.
    """
    table = zone_per_area_table(
        _summary(("Temuco", {"friend_lessons": 130})),
        _areas(("Temuco", 13)),
        FUNNEL,
    )
    row = table.iloc[0]
    assert row["areas"] == 13, "Areas column must print the divisor used"
    assert row["friend_lessons"] == 10.0


def test_a_zone_with_no_summary_row_is_blank_not_zero():
    """"Not written yet" and "did nothing" must not render alike.

    A zero here would accuse a zone of a week's inactivity on the strength of a
    missing row — and a zero sorts above nothing, so it would also outrank a
    genuinely idle zone.
    """
    table = zone_per_area_table(
        _summary(("Angol", {"friend_lessons": 80})),
        _areas(("Angol", 8), ("San Pedro", 11)),
        FUNNEL,
    )
    san_pedro = table[table["zone"] == "San Pedro"].iloc[0]
    assert pd.isna(san_pedro["friend_lessons"])
    assert san_pedro["areas"] == 11, "the zone is still listed, with its size"

    # NaN must not be treated as a large value by the ranking.
    assert _ranked(table, "friend_lessons")[0] == "Angol"


def test_leadership_rows_never_inflate_a_zones_divisor():
    """get_submitting_areas() drops them; active_areas_by_zone must not add any
    back through a Zone value of ALL, which is what leadership rows carry."""
    areas = pd.concat([
        _areas(("Angol", 8)),
        pd.DataFrame([{"Area_Code": "ZL01", "Area_Name": "Zone Leader - Angol",
                       "Zone": "ALL", "District": "ALL", "Active": "TRUE"}]),
    ], ignore_index=True)
    assert active_areas_by_zone(areas) == {"Angol": 8}


def test_zone_names_match_across_tabs_despite_stray_spaces():
    """MISSION_ORG and DASHBOARD_SUMMARY are written by different agents; a
    trailing space in one would silently blank a real zone's whole row."""
    summary = _summary(("Angol ", {"contacts_attempted": 800}))
    areas = _areas(("Angol", 8))
    table = zone_per_area_table(summary, areas, FUNNEL)
    assert table.iloc[0]["contacts_attempted"] == 100.0


# ── Effectiveness: a weekly score, and only when it is whole ──────────────────

def test_effectiveness_is_averaged_over_active_areas_not_scored_rows():
    """An area the scoring agent wrote no row for counts as a zero, exactly
    like an area that reported nothing to the nightly form. Averaging over
    present rows instead would reward a zone for its missing rows."""
    table = zone_per_area_table(
        _summary(("Angol", {"friend_lessons": 80})),
        _areas(("Angol", 8)),
        FUNNEL,
        _scores(("Angol", [(80.0, 50.0)] * 4)),   # 4 rows for 8 active areas
    )
    assert table.iloc[0][EFFECTIVENESS] == 40.0   # 320 / 8, not 320 / 4


def test_effectiveness_does_not_lead_while_its_ki_third_is_missing():
    """KI_Score is 0 for an area whose week had no goals to score against, and
    a week's KI goals are written on the PREVIOUS week's form. Live on
    2026-08-21 that was 1 area of 43 — Effectiveness would have ranked zones on
    two thirds of itself with nothing saying so."""
    sparse = _scores(("Angol", [(48.0, 0.0)] * 42 + [(74.0, 56.0)]))
    assert ki_scored_area_count(sparse) == 1
    assert not effectiveness_is_rankable(sparse, active_areas=43)


def test_effectiveness_leads_once_half_the_mission_carries_a_ki_score():
    healthy = _scores(("Angol", [(60.0, 55.0)] * 22 + [(60.0, 0.0)] * 21))
    assert ki_scored_area_count(healthy) == 22
    assert effectiveness_is_rankable(healthy, active_areas=43)


def test_the_threshold_is_a_share_of_active_areas_not_of_scored_rows():
    """22 scored areas is a majority of 43 and a minority of 60. The mission's
    size is the denominator — a week where the agent wrote few rows must not
    clear the bar just because most of the rows it did write have a KI score."""
    week = _scores(("Angol", [(60.0, 55.0)] * 22))
    assert effectiveness_is_rankable(week, active_areas=43)
    assert not effectiveness_is_rankable(week, active_areas=60)


def test_no_effectiveness_column_when_no_week_has_been_scored():
    """SCORES is empty before the first Monday run. The column is dropped
    rather than filled with zeros, so nothing can be sorted by it."""
    table = zone_per_area_table(
        _summary(("Angol", {"friend_lessons": 80})),
        _areas(("Angol", 8)),
        FUNNEL,
        pd.DataFrame(),
    )
    assert EFFECTIVENESS not in table.columns
    assert not effectiveness_is_rankable(pd.DataFrame(), active_areas=43)


# ── Degenerate inputs ─────────────────────────────────────────────────────────

def test_no_active_areas_yields_an_empty_table_not_a_division_by_zero():
    table = zone_per_area_table(
        _summary(("Angol", {"friend_lessons": 80})), pd.DataFrame(), FUNNEL)
    assert table.empty
    assert list(table.columns) == ["zone", "areas"] + FUNNEL


def test_a_metric_missing_from_one_zones_rows_is_zero_not_absent():
    """The zone reported, this metric just never came up — different from the
    zone having no row at all, and it must stay a comparable number."""
    table = zone_per_area_table(
        _summary(("Angol", {"friend_lessons": 80})),
        _areas(("Angol", 8)),
        FUNNEL,
    )
    assert table.iloc[0]["baptismal_invitations"] == 0.0
