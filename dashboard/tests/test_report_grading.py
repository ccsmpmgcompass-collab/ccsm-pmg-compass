"""How the Informes report judges a number — `app/reports/grading.py`.

The centrepiece is `test_the_twenty_nightly_metrics_are_not_a_wall_of_red`,
which runs the real figures measured off the live sheet on 2026-09-21 through
both paths. It is the acceptance criterion for §4 step R2 and the reason
decision 31 exists: under the Key Indicators' 90/60 bands seventeen of the
twenty nightly metrics are red and not one is green, every week, forever.
"""

import pytest

from app.config.theme import goal_bar_status
from app.reports import grading as G

# Every numeric nightly metric, measured per ACTIVE area per week over the
# current transfer's two complete weeks (2026-09-07 .. 2026-09-20): the actual
# and the AGENT_CONFIG weekly per-area goal. Reproduces PLAN §1.1 exactly —
# contacts_attempted 97.9 against 150 is the figure quoted there.
NIGHTLY = {
    "roleplays": (4.1, 7),
    "contacts_attempted": (97.9, 150),
    "contacts_made": (43.8, 75),
    "meaningful_conversations": (19.3, 40),
    "new_people_found": (4.9, 8),
    "friend_lessons": (12.4, 25),
    "pmf_lessons": (1.3, 4),
    "rc_lessons": (1.4, 4),
    "rc_lessons_mcp": (0.26, 4),
    "friend_texts": (99.0, 200),
    "friend_calls": (12.3, 30),
    "member_contacts": (33.7, 50),
    "lessons_member_present": (3.0, 7),
    "references_asked": (2.5, 10),
    "member_referrals_received": (0.9, 3),
    "bom_shared": (1.5, 5),
    "church_invites": (17.9, 50),
    "baptism_doctrine_lessons": (3.5, 8),
    "baptismal_invitations": (1.5, 4),
    "baptismal_calendars": (0.43, 2),
}


# ── Attainment ────────────────────────────────────────────────────────────────

def test_attainment_is_never_clamped():
    """A goal set far too low has to be able to read 196%, or decision 22's
    ceiling could never fire."""
    assert G.attainment(196, 100) == pytest.approx(196)


def test_no_goal_is_not_a_zero_percent():
    """A percentage of nothing is not a small percentage — it is no reading."""
    assert G.attainment(50, None) is None
    assert G.attainment(50, 0) is None


def test_zero_work_against_a_real_goal_is_a_real_zero():
    assert G.attainment(0, 40) == 0.0


def test_an_unmeasured_value_is_not_a_zero_either():
    assert G.attainment(None, 40) is None


# ── Pace ──────────────────────────────────────────────────────────────────────

def test_a_third_of_the_way_through_a_third_of_the_goal_is_due():
    """Two weeks into a six-week transfer. Grading the whole goal against a
    third of the work paints an area red for being exactly on schedule."""
    assert G.paced_goal(150, 2, 6) == pytest.approx(50)


def test_a_finished_period_owes_its_whole_goal():
    assert G.paced_goal(150, 6, 6) == 150
    assert G.paced_goal(150, 7, 6) == 150


def test_an_unusable_shape_falls_back_to_the_whole_goal():
    assert G.paced_goal(150, None, 6) == 150
    assert G.paced_goal(150, 2, 0) == 150


# ── The Key Indicator bands ──────────────────────────────────────────────────

@pytest.mark.parametrize("pct,expected", [
    (100, "good"), (90, "good"), (89.9, "warn"),
    (60, "warn"), (59.9, "bad"), (0, "bad"),
])
def test_the_ki_bands_are_the_ones_the_rest_of_the_app_uses(pct, expected):
    """Reused from theme, not re-implemented — three copies of "90 and 60" is
    how a page ends up grading the same number two ways."""
    assert goal_bar_status(pct) == expected
    assert G.grade_ki(pct, 100).status == expected


def test_a_ki_in_progress_is_graded_against_the_pace_not_the_whole_goal():
    """Two weeks into a transfer, 50 against a 150 goal is exactly on pace."""
    g = G.grade_ki(50, 150, pace=G.paced_goal(150, 2, 6))
    assert g.status == "good"
    assert g.pct == pytest.approx(33.3, abs=0.1)   # the caption still shows 33%


def test_a_ki_with_no_goal_is_not_graded():
    """44 of 45 areas have no 2026-5 transfer goal (decision 23). "sin meta" is
    not a grade and not a flag."""
    g = G.grade_ki(40, None)
    assert g.status is None and g.flag is None and g.pct is None


# ── The nightly path ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("now,before,expected", [
    (116, 100, "good"),      # +16%, past the band
    (115, 100, "warn"),      # +15%, on the band — steady
    (100, 100, "warn"),
    (85, 100, "warn"),       # -15%, on the band
    (84, 100, "bad"),        # -16%
])
def test_a_nightly_row_grades_on_where_it_moved(now, before, expected):
    assert G.change_status(now, before) == expected


def test_a_rise_from_nothing_is_a_direction_without_a_size():
    """"+∞%" in a council packet is a bug wearing a number."""
    assert G.change_status(3, 0) == "good"
    assert G.change(3, 0) is None


def test_staying_at_nothing_claims_no_direction():
    assert G.change_status(0, 0) is None


def test_no_comparison_period_is_not_the_same_as_one_that_recorded_zero():
    """`before=None` means there is nothing to compare against; `before=0`
    means the week before recorded nothing, and rising off it is a real move.
    Conflating them turns every absent comparison into good news."""
    assert G.change_status(40, None) is None
    assert G.change_status(40, 0) == "good"


def test_the_nightly_path_never_returns_a_ninety_sixty_verdict():
    """The regression §4 R2 asks for. A metric at 42% of goal is "bad" on the
    Key Indicator path and, holding steady, "warn" on the nightly one. If these
    ever agree, decision 31 has been undone."""
    assert G.grade_ki(42, 100).status == "bad"
    assert G.grade_nightly(42, 100, before=41).status == "warn"


def test_a_nightly_row_still_reports_its_goal_it_just_is_not_coloured_by_it():
    """Meaningful conversations, the real figures: 48% of goal, down 12% on the
    week. The 48% is printed, the 12% is what picks the colour — and a 12% fall
    is inside the flat band, so the row reads steady rather than alarmed."""
    g = G.grade_nightly(19.3, 40, before=22.0)
    assert g.pct == pytest.approx(48.25)
    assert g.change_pct == pytest.approx(-12.27, abs=0.01)
    assert g.status == "warn"


# ── Decision 22: the flag ────────────────────────────────────────────────────

def test_the_flag_fires_in_both_directions():
    """A goal set far too low flatters an area exactly as badly as one set far
    too high condemns it."""
    assert G.goal_is_unusable(10, 100) == G.GOAL_TOO_HIGH
    assert G.goal_is_unusable(300, 100) == G.GOAL_TOO_LOW


@pytest.mark.parametrize("actual,expected", [
    (24.9, G.GOAL_TOO_HIGH), (25, None), (250, None), (250.1, G.GOAL_TOO_LOW),
])
def test_the_flag_edges(actual, expected):
    assert G.goal_is_unusable(actual, 100) == expected


def test_a_missing_goal_is_not_an_unusable_one():
    """"sin meta" and "meta no utilizable" are different statements."""
    assert G.goal_is_unusable(40, None) is None


def test_the_flag_is_a_property_of_the_goal_not_of_one_bad_fortnight():
    """An area that produced nothing against a real goal is behind — that is
    the news, and auto-flagging the row would bury it. The verdict is taken
    once at mission scope and handed down."""
    assert G.grade_ki(0, 100).status == "bad"
    assert G.grade_ki(0, 100).flag is None


def test_a_flagged_key_indicator_is_flagged_rather_than_scored():
    """Decision 22 in one line: the row prints its flag instead of a colour."""
    g = G.grade_ki(5, 100, flag=G.goal_is_unusable(5, 100))
    assert g.flag == G.GOAL_TOO_HIGH
    assert g.status is None and not g.graded
    assert g.flag_label == "meta no utilizable: demasiado alta"


def test_a_flagged_goal_does_not_silence_the_movement():
    """The flag is a statement about the goal. What the work did is a different
    statement and survives it."""
    g = G.grade_ki(5, 100, before=4, flag=G.GOAL_TOO_HIGH)
    assert g.flag == G.GOAL_TOO_HIGH
    assert g.change_pct == pytest.approx(25)


# ── The acceptance criterion ─────────────────────────────────────────────────

def test_the_twenty_nightly_metrics_are_not_a_wall_of_red():
    """§4 R2's acceptance, on the real figures: 18 usable and 2 flagged, not 18
    red. The `ki_reds` line is what the page would look like if decision 31 had
    gone the other way."""
    flagged = {m for m, (a, g) in NIGHTLY.items() if G.goal_is_unusable(a, g)}
    assert flagged == {"rc_lessons_mcp", "baptismal_calendars"}
    assert len(NIGHTLY) - len(flagged) == 18

    ki_reds = [m for m, (a, g) in NIGHTLY.items()
               if G.grade_ki(a, g).status == "bad"]
    assert len(ki_reds) == 17      # the other three sit at 61%-67%: amber

    # The same twenty on their own path, each holding steady against the week
    # before: not one of them is red.
    steady = [G.grade_nightly(a, g, before=a) for a, g in NIGHTLY.values()]
    assert {s.status for s in steady} == {"warn"}


def test_every_measured_metric_sits_between_six_and_sixty_seven_percent():
    """The measurement decision 31 rests on. If a goal recalibration ever moves
    these, this test is the place that notices."""
    pcts = sorted(G.attainment(a, g) for a, g in NIGHTLY.values())
    assert pcts[0] == pytest.approx(6.5, abs=0.5)
    assert pcts[-1] == pytest.approx(67.4, abs=0.5)
    assert pcts[len(pcts) // 2] == pytest.approx(43.3, abs=1.0)
