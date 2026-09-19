"""Unit tests for app/ingestion/tableau_summary_parser.py.

The fixture below is the real text layout pypdf extracts from a Mission Finding
Summary PDF, trimmed to the two regions the parser reads, with July 2024's
actual figures. No PDF binaries live in the repo.

July 2024, verified against the live file:
    found 1,963 · referred 347 · taught 842 · multi 522 · church 126 ·
    bap-date 49 · baptized 22
"""

import pytest

from app.ingestion.tableau_summary_parser import (
    MonthlySummary,
    SummaryParseError,
    baptisms_rows,
    parse_summary_text,
)

# Tabs and newlines exactly as pypdf emits them, so _flatten() is under test too.
JULY_2024 = """Conﬁdenal\t-\tFor\tChurch\tUse\tOnly
Mission\tFinding\tSummary
Start\tDate
7/1/2024
End\tDate
7/31/2024
Finding\tCategory
Todo
Grand\tTotal 22
 Total\tPeople\tBaptized 842
 New\tPeople\tBeing\tTaught 1,963
 Total\tPeople\tFound 347
 Total\tPeople\tReferred
Finding\tCategories\tBreakout
All\tFinding\tCategories
Total\tPeople\tFound 1,963
All\tOutcomesNew\tPeople\tBeing\tTaught
Multiple\tLessons
Church\tAttendance
Baptism\tGoal\tDate\tSet
Baptized\tand\tConfirmed
22
49
126
522
 842
(2.6%)
(6%)
"""


def test_parses_the_real_july_2024_layout():
    s = parse_summary_text(JULY_2024)
    assert s == MonthlySummary(
        month="2024-07",
        start_date="2024-07-01",
        end_date="2024-07-31",
        people_found=1963,
        people_referred=347,
        people_being_taught=842,
        multiple_lessons=522,
        church_attendance=126,
        baptism_goal_date_set=49,
        baptized=22,
    )


def test_the_grand_total_block_is_read_offset_by_one():
    """The number printed after 'Grand Total' is Baptized, not a grand total."""
    s = parse_summary_text(JULY_2024)
    assert s.baptized == 22          # the value sitting after 'Grand Total'
    assert s.people_found == 1963    # two labels further down


def test_the_funnel_is_read_in_reverse():
    """Labels run taught->baptized; the numbers arrive baptized->taught."""
    s = parse_summary_text(JULY_2024)
    assert (s.people_being_taught, s.multiple_lessons, s.church_attendance,
            s.baptism_goal_date_set, s.baptized) == (842, 522, 126, 49, 22)


def test_month_comes_from_inside_the_file_not_a_filename():
    """Real exports are named 'Spetember 2024', 'Febuary 2025', 'Abril 2026'."""
    assert parse_summary_text(JULY_2024).month == "2024-07"


def test_single_digit_month_is_zero_padded():
    assert parse_summary_text(JULY_2024).month == "2024-07"
    assert parse_summary_text(
        JULY_2024.replace("7/1/2024", "12/1/2024").replace("7/31/2024", "12/31/2024")
    ).month == "2024-12"


def test_thousands_separators_are_handled():
    assert parse_summary_text(JULY_2024).people_found == 1963


# ── the cross-check is the whole safety story ─────────────────────────────────

def test_disagreement_between_the_two_regions_raises():
    """If the funnel and the totals block disagree, the export changed shape and
    a silent wrong number is the worst outcome."""
    broken = JULY_2024.replace(" 842\n(2.6%)", " 999\n(2.6%)")
    with pytest.raises(SummaryParseError, match="cross-check failed"):
        parse_summary_text(broken)


def test_a_mangled_baptized_value_is_caught_too():
    broken = JULY_2024.replace("Grand\tTotal 22", "Grand\tTotal 23")
    with pytest.raises(SummaryParseError, match="cross-check failed"):
        parse_summary_text(broken)


def test_reversing_the_funnel_the_wrong_way_would_be_caught():
    """Guards the guard: if quirk 1 were ever 'simplified' away, the fixture's
    own numbers no longer line up and the cross-check fires."""
    forward = JULY_2024.replace("22\n49\n126\n522\n 842", "842\n522\n126\n49\n 22")
    with pytest.raises(SummaryParseError):
        parse_summary_text(forward)


# ── missing regions ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("cut,msg", [
    ("Start\tDate", "window"),
    ("Grand\tTotal 22", "Grand Total"),
    ("All\tOutcomes", "funnel"),
])
def test_missing_region_raises_a_named_error(cut, msg):
    with pytest.raises(SummaryParseError, match=msg):
        parse_summary_text(JULY_2024.replace(cut, "REMOVED"))


def test_empty_text_raises():
    with pytest.raises(SummaryParseError):
        parse_summary_text("")


# ── TABLEAU_BAPTISMS shaping ──────────────────────────────────────────────────

def test_baptisms_rows_matches_the_tab_contract():
    """get_baptisms_actual() selects zone == 'MISSION' and month 'YYYY-MM'."""
    jul = parse_summary_text(JULY_2024)
    dec = parse_summary_text(
        JULY_2024.replace("7/1/2024", "12/1/2024").replace("7/31/2024", "12/31/2024")
    )
    rows = baptisms_rows([dec, jul])
    assert rows == [
        ["MISSION", "2024-07", 22, "2024-07-01", "2024-07-31"],
        ["MISSION", "2024-12", 22, "2024-12-01", "2024-12-31"],
    ]


def test_baptisms_rows_sorts_chronologically():
    jul = parse_summary_text(JULY_2024)
    jan = parse_summary_text(
        JULY_2024.replace("7/1/2024", "1/1/2024").replace("7/31/2024", "1/31/2024")
    )
    assert [r[1] for r in baptisms_rows([jul, jan])] == ["2024-01", "2024-07"]


def test_baptisms_rows_is_empty_for_no_input():
    assert baptisms_rows([]) == []


def test_duplicate_downloads_of_the_same_month_collapse_to_one_row():
    """A real download folder holds 'August 2024.pdf' AND 'August 2024 (1).pdf'."""
    jul = parse_summary_text(JULY_2024)
    assert baptisms_rows([jul, jul, jul]) == [
        ["MISSION", "2024-07", 22, "2024-07-01", "2024-07-31"]]


def test_two_exports_of_one_month_that_disagree_raise():
    """Re-downloads should be identical. If they aren't, the export changed and
    quietly picking one would hide it."""
    jul = parse_summary_text(JULY_2024)
    other = parse_summary_text(
        JULY_2024.replace("Grand\tTotal 22", "Grand\tTotal 25").replace("22\n49", "25\n49")
    )
    with pytest.raises(SummaryParseError, match="disagree"):
        baptisms_rows([jul, other])


# ── the window a capture was run for  (2026-09-19) ────────────────────────────
#
# Until this date baptisms_rows() emitted three columns and discarded
# start_date/end_date, which is what made TABLEAU_BAPTISMS monthly-only: a
# month-to-date export was stored as though it described the finished month.

def _july_through(day: int, baptized: int) -> str:
    """July 2024 re-cut as a capture ending mid-month. Both the Grand Total
    block and the funnel's own value have to move together or the parser's
    cross-check refuses the text — which is the point of that cross-check."""
    return (JULY_2024
            .replace("7/31/2024", f"7/{day}/2024")
            .replace("Grand\tTotal 22", f"Grand\tTotal {baptized}")
            .replace("22\n49", f"{baptized}\n49"))


def test_a_month_to_date_export_carries_its_real_window():
    s = parse_summary_text(_july_through(19, 14))
    assert (s.month, s.start_date, s.end_date) == ("2024-07", "2024-07-01", "2024-07-19")
    assert s.baptized == 14


def test_a_wider_capture_of_the_same_month_wins_whatever_the_order():
    """Sep 1-19 and Sep 1-20 SHOULD disagree. Treating that as a contradiction
    aborted the job; the longer window is simply the newer reading."""
    partial = parse_summary_text(_july_through(19, 14))
    full = parse_summary_text(JULY_2024)
    for pair in ([partial, full], [full, partial]):
        assert baptisms_rows(pair) == [
            ["MISSION", "2024-07", 22, "2024-07-01", "2024-07-31"]]


def test_a_narrower_capture_does_not_overwrite_a_wider_one():
    partial = parse_summary_text(_july_through(5, 3))
    wider = parse_summary_text(_july_through(19, 14))
    assert baptisms_rows([wider, partial])[0][2] == 14


def test_two_windows_that_overlap_without_nesting_still_raise():
    """Jul 1-19 against Jul 5-31 is not one month captured twice; it is two
    different questions, and neither answer is the month's."""
    a = parse_summary_text(_july_through(19, 14))
    b = parse_summary_text(
        _july_through(31, 20).replace("7/1/2024", "7/5/2024"))
    with pytest.raises(SummaryParseError, match="neither covers the other"):
        baptisms_rows([a, b])


def test_an_identical_window_that_disagrees_is_still_an_error():
    """The guard was fixed, not removed: two files describing exactly the same
    days and disagreeing about them still means the export changed."""
    a = parse_summary_text(_july_through(19, 14))
    b = parse_summary_text(_july_through(19, 17))
    with pytest.raises(SummaryParseError, match="disagree"):
        baptisms_rows([a, b])
