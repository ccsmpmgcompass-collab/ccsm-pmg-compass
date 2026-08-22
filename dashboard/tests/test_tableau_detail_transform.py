"""Unit tests for app/ingestion/tableau_detail_transform.py.

Synthetic frames only — the real export carries ~89,850 named individuals and
never belongs in a repo. The shapes here mirror what the live 2026-08-22 export
actually contained (24 columns, Tableau artifact rows interleaved, headers in
Title Case With Spaces).
"""

import pandas as pd
import pytest

from app.ingestion.tableau_detail_transform import (
    KEEP_COLUMNS,
    IDENTITY_COLUMNS,
    clean_detail,
    normalize_headers,
)


def _raw_export() -> pd.DataFrame:
    """Three real people and two Tableau artifact rows, headed the way the live
    export heads them."""
    return pd.DataFrame(
        [
            # Full Name, Person Id, Event Date, Zone, District, Area, Source, Category,
            # referral, attempt, success, taught, lesson, sacrament, bapgoal, confirm, sort
            ["Ana Rojas", 1001, "2026-06-01", "San Pedro", "La Marina 1", "Los Huertos",
             "Ward Council", "Member", "2026-05-28", "2026-05-30", "2026-06-01",
             "2026-06-05", "2026-06-05", "2026-06-14", "2026-06-20", "2026-07-05", None],
            ["Beto Díaz", 1002, "2026-06-02", "Angol", "Los Confines", "Alemania 1",
             "Contacting in Public", "Missionary", None, "2026-06-02", "2026-06-02",
             None, None, None, None, None, None],
            ["Cami Soto", 1003, "2026-07-15", "San Pedro", "La Marina 1", "Los Huertos",
             "Facebook - Mission Ad", "Media", "2026-07-10", "2026-07-12", None,
             None, None, None, None, None, None],
            # Tableau artifact rows: a Person Id and nothing else.
            [None, 9001, None, None, None, None, None, None,
             None, None, None, None, None, None, None, None, "Total"],
            [None, 9002, "", "", None, None, None, None,
             None, None, None, None, None, None, None, None, None],
        ],
        columns=[
            "Full Name", "Person Id", "Event Date Selected", "Latest Zone Name",
            "Latest District Name", "Latest Teaching Area Name", "Finding Source",
            "Finding Category (copy)", "First Referral Event Date",
            "First Contact Attempt Event Date",
            "First Successful Contact Attempt Event Date",
            "First New Person Being Taught Date", "First Lesson Date",
            "First Sacrament Date", "First Baptism Goal Date Set",
            "Confirmation Date", "Sort",
        ],
    )


# ── header normalisation ──────────────────────────────────────────────────────

def test_normalize_headers_matches_the_uploader_rule():
    out = normalize_headers(_raw_export())
    assert "event_date_selected" in out.columns
    assert "latest_zone_name" in out.columns
    assert "finding_category_(copy)" in out.columns


def test_normalize_headers_does_not_mutate_the_input():
    raw = _raw_export()
    before = list(raw.columns)
    normalize_headers(raw)
    assert list(raw.columns) == before


# ── the privacy decision ──────────────────────────────────────────────────────

def test_identity_columns_are_dropped_by_default():
    out, stats = clean_detail(_raw_export())
    for col in IDENTITY_COLUMNS:
        assert col not in out.columns
    assert stats["identity_dropped"] == ["full_name", "person_id"]


def test_no_person_name_survives_anywhere_in_the_output():
    """Stronger than a column check: no cell of the output may hold a name."""
    out, _ = clean_detail(_raw_export())
    flat = out.astype(str).values.ravel().tolist()
    for name in ("Ana Rojas", "Beto Díaz", "Cami Soto"):
        assert name not in flat


def test_identity_can_be_kept_when_a_caller_is_explicit():
    out, stats = clean_detail(_raw_export(), drop_identity=False)
    assert "full_name" in out.columns
    assert stats["identity_dropped"] == []


# ── artifact rows ─────────────────────────────────────────────────────────────

def test_artifact_rows_are_dropped():
    out, stats = clean_detail(_raw_export())
    assert stats["rows_in"] == 5
    assert stats["rows_out"] == 3
    assert stats["artifact_rows_dropped"] == 2


def test_empty_string_counts_as_blank_not_as_a_person():
    """A CSV round-trip turns a missing cell into '', an Excel one into NaN.
    Both are artifact rows, not people."""
    raw = _raw_export()
    assert raw.iloc[4]["Event Date Selected"] == ""
    out, _ = clean_detail(raw)
    assert len(out) == 3


def test_the_literal_string_nan_is_also_blank():
    raw = _raw_export()
    raw.loc[3, "Event Date Selected"] = "nan"
    raw.loc[3, "Latest Zone Name"] = "nan"
    out, _ = clean_detail(raw)
    assert len(out) == 3


def test_a_real_person_missing_only_optional_milestones_is_kept():
    """Beto has no referral, no lessons and no confirmation — still a person."""
    out, _ = clean_detail(_raw_export())
    assert (out["latest_teaching_area_name"] == "Alemania 1").sum() == 1


# ── column pruning ────────────────────────────────────────────────────────────

def test_output_holds_exactly_the_columns_the_app_reads_in_order():
    out, _ = clean_detail(_raw_export())
    assert list(out.columns) == list(KEEP_COLUMNS)


def test_known_unused_columns_are_dropped_without_being_flagged_unknown():
    out, stats = clean_detail(_raw_export())
    assert "sort" not in out.columns
    assert stats["dropped_unknown"] == []


def test_tableau_combined_mashup_column_is_not_reported_as_new():
    """Tableau emits a '…_and_5_more_(combined)' column on every export. It is
    an artifact, not a new field, and must not raise a flag each time."""
    raw = _raw_export()
    raw["Event Date Selected, Finding Type Group, Finding Category and 5 more (combined)"] = "x"
    out, stats = clean_detail(raw)
    assert stats["dropped_unknown"] == []
    assert not any("(combined)" in c for c in out.columns)


def test_a_genuinely_new_column_is_reported_not_silently_dropped():
    """A future export gaining a column must surface, so it can be triaged."""
    raw = _raw_export()
    raw["Some Brand New Tableau Field"] = "x"
    out, stats = clean_detail(raw)
    assert stats["dropped_unknown"] == ["some_brand_new_tableau_field"]
    assert "some_brand_new_tableau_field" not in out.columns


def test_missing_expected_columns_are_reported_and_do_not_raise():
    raw = _raw_export().drop(columns=["Confirmation Date"])
    out, stats = clean_detail(raw)
    assert stats["missing_expected"] == ["confirmation_date"]
    assert "confirmation_date" not in out.columns
    assert len(out) == 3


# ── cell budget ───────────────────────────────────────────────────────────────

def test_cell_count_shrinks():
    _, stats = clean_detail(_raw_export())
    assert stats["cells_out"] < stats["cells_in"]
    assert stats["cells_in"] == 5 * 17
    assert stats["cells_out"] == 3 * len(KEEP_COLUMNS)


# ── degenerate inputs ─────────────────────────────────────────────────────────

def test_empty_frame_does_not_raise():
    out, stats = clean_detail(pd.DataFrame(columns=["Full Name", "Event Date Selected"]))
    assert len(out) == 0
    assert stats["rows_out"] == 0


def test_frame_without_the_required_columns_is_passed_through_not_emptied():
    """A malformed export should surface as 'missing_expected', never as a
    silent zero-row success that overwrites a good tab with nothing."""
    raw = pd.DataFrame({"Something Else": [1, 2, 3]})
    out, stats = clean_detail(raw)
    assert stats["rows_in"] == 3
    assert stats["artifact_rows_dropped"] == 0
    assert set(stats["missing_expected"]) == set(KEEP_COLUMNS)


# ── the funnel still works on the pruned frame ────────────────────────────────

def test_pruned_frame_still_drives_the_funnel_and_rankings():
    """The whole point of the prune is that the analytics are unaffected."""
    from app.analytics.finding_funnel import (
        build_area_rankings,
        compute_funnel_stage_counts,
    )

    out, _ = clean_detail(_raw_export())

    counts = compute_funnel_stage_counts(out)
    assert counts["Found"] == 3
    assert counts["Contact Attempted"] == 3
    assert counts["Successfully Contacted"] == 2
    assert counts["Being Taught"] == 1

    ranks = build_area_rankings(out)
    assert "Unknown" not in set(ranks["Area"])
    assert set(ranks["Area"]) == {"Los Huertos", "Alemania 1"}
    huertos = ranks[ranks["Area"] == "Los Huertos"].iloc[0]
    assert huertos["Found"] == 2
    assert huertos["Baptized"] == 1


@pytest.mark.parametrize("col", KEEP_COLUMNS)
def test_every_kept_column_is_one_the_app_can_resolve(col):
    """Guards against KEEP_COLUMNS drifting away from what finding_funnel.py
    actually looks for."""
    from app.analytics.finding_funnel import resolve_col

    out, _ = clean_detail(_raw_export())
    assert resolve_col(out, col) is not None
