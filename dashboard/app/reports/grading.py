"""How a number is judged — and when it refuses to judge.

Three rules, and the third is the one that matters most.

**Key Indicators grade against their goal, on 90/60.** `theme.goal_bar_status`
is the one home for those two thresholds and is reused here rather than
re-implemented; the card's own fill and tick geometry stay in
`design_system.goal_bar_state`, which is a rendering question.

**Nightly metrics grade on MOVEMENT, not on the goal** (decision 31). Measured
live on 2026-09-21 over the current transfer's two complete weeks, per active
area per week, all twenty numeric nightly metrics sit between 6% and 67% of
their configured goal, median 43%. Under 90/60 that is seventeen of twenty rows
red and not one green, every single week — a wall of colour that says nothing
about the week, which is exactly what decision 10's three states exist to
prevent. The goals are stretch targets at roughly twice current performance. So
the goal is drawn as a secondary mark and the row's status comes from where it
moved.

**A goal that is not a usable yardstick is flagged, not scored** (decision 22).
Below 25% or above 250% of a normalised pace, the goal has stopped measuring
anything and the report says so instead of pretending. It fires in both
directions: a goal set far too low flatters an area exactly as badly as one set
far too high condemns it. On CCSM today it catches two of twenty — the eighteen
that remain are low against their targets but still usefully ordered by them.

**Every function here takes numbers already reduced to a common basis.** None
of them can see how many areas reported or how many weeks a period holds, so
none of them can normalise for you. Hand `attainment` a mission's raw weekly sum
against one area's weekly goal and it will answer 2.040%, which is what a Panel
tile really read on 2026-08-21. The model reduces both sides to a rate first
(decision 12); this module only judges the result.

Pure. No Streamlit, no sheet reads. See PLAN-2026-09-21-informes.md §4 step R2.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.theme import goal_bar_status

#: Decision 22's two edges, as fractions of a normalised pace. A goal the work
#: reaches a quarter of, or overshoots two and a half times, is not a yardstick.
#: Measured 2026-09-21: of the twenty nightly metrics, `rc_lessons_mcp` (6.4% of
#: its goal) and `baptismal_calendars` (21.7%) fall below the floor and nothing
#: comes near the ceiling — 18 usable, 2 flagged, which is the acceptance test
#: for this step.
GOAL_FLOOR = 0.25
GOAL_CEILING = 2.50

#: How far a nightly metric has to move before the report calls it a move.
#: Measured 2026-09-21 across 100 metric-weeks (20 metrics, the five
#: week-over-week steps in WEEKLY_KI's complete weeks), on all three candidate
#: bases — per active area, per reporting area, per reported area-day. The
#: median absolute change is 15.6%–19.6% whichever basis is used, so ±15% lands
#: near the middle of the real distribution and roughly half the rows carry a
#: direction. The band is deliberately wide: ±5% would colour 80–88% of rows,
#: which is decision 10's wall of red wearing arrows instead, and ±25% would
#: call a genuine quarter-sized drop "steady".
FLAT_BAND = 15.0

#: What is wrong with the goal, not with the work.
GOAL_TOO_HIGH = "goal_too_high"
GOAL_TOO_LOW = "goal_too_low"

#: Spanish only, screen and packet (decision 3).
FLAG_LABELS = {
    GOAL_TOO_HIGH: "meta no utilizable: demasiado alta",
    GOAL_TOO_LOW: "meta no utilizable: demasiado baja",
}


def attainment(actual, goal) -> float | None:
    """`actual` as a percentage of `goal`, or None when there is no yardstick.

    **Never clamped.** A goal set far too low has to be able to read 196%, or
    decision 22's ceiling could never fire and a flattering goal would look
    exactly like a met one.

    None — not zero — when the goal is missing or zero, and when the actual has
    not been measured at all. A percentage of nothing is not a small percentage.
    An actual of zero against a real goal IS 0%, which is a reading of nothing
    rather than the absence of a reading.
    """
    if goal in (None, 0) or actual is None:
        return None
    try:
        return float(actual) / float(goal) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def paced_goal(goal, elapsed, full):
    """The share of a period's goal that is due by now.

    Two weeks into a six-week transfer, a third of the transfer's goal is due.
    Grading the whole goal against a third of the work paints an area red for
    being exactly on schedule — the split `goal_bar_state` draws as a bar that
    fills to 33% with its tick at 33% and its colour taken from the two.

    Returns `goal` itself when the period is over or the shape is unusable, so
    a caller never has to ask whether it is looking at a finished period.
    """
    if goal is None:
        return None
    try:
        elapsed, full = float(elapsed), float(full)
    except (TypeError, ValueError):
        return goal
    if full <= 0 or elapsed >= full:
        return goal
    return float(goal) * max(0.0, elapsed) / full


def change(now, before) -> float | None:
    """The signed percentage move from `before` to `now`.

    None when `before` is zero or missing: a rise from nothing is real, but it
    is not a percentage, and "+∞%" in a council packet is a bug wearing a
    number. `change_status` handles that case as a direction without a size.
    """
    if now is None or before in (None, 0):
        return None
    try:
        before = float(before)
    except (TypeError, ValueError):
        return None
    if before == 0:
        return None
    return (float(now) - before) / before * 100


def change_status(now, before, *, band: float = FLAT_BAND) -> str | None:
    """Where a nightly metric moved, as decision 10's three states.

    Up by more than `band` is "good", down by more than `band` is "bad", and
    anything between is "warn" — steady, which on a metric this mission is
    trying to grow is neither good news nor an alarm.

    None when there is nothing to compare against, so the row draws neutral
    rather than claiming a direction it cannot know. **`before=None` and
    `before=0` are not the same thing**: the first is "there is no comparison
    period", the second is "the comparison period recorded nothing", and a rise
    from a recorded nothing is a real move. A stay at zero claims no direction
    either way — it never started.

    `now` and `before` must already rest on the same basis — see the module
    docstring. This function cannot tell a mission that worked harder from one
    where ten more areas filed a form.
    """
    if now is None or before is None:
        return None
    if before == 0:
        try:
            return "good" if float(now) > 0 else None
        except (TypeError, ValueError):
            return None
    pct = change(now, before)
    if pct is None:
        return None
    if pct > band:
        return "good"
    if pct < -band:
        return "bad"
    return "warn"


def goal_is_unusable(actual, goal) -> str | None:
    """Whether `goal` has stopped being a yardstick — decision 22.

    GOAL_TOO_HIGH below `GOAL_FLOOR` of it, GOAL_TOO_LOW above `GOAL_CEILING`,
    None in between. Both sides must already be normalised to the same pace:
    a transfer's goal against one week's work reads 17% and would be flagged
    every time.

    None when there is no goal at all. "sin meta" is a different statement from
    "meta no utilizable" — 44 of 45 areas have no 2026-5 transfer goal
    (decision 23), and none of those goals is unusable, because none of them
    exists.

    **Ask this at MISSION scope and apply the answer everywhere below it.** A
    goal is a configured number (AGENT_CONFIG's `GOAL_*`, one mission-wide
    figure per metric), so whether it is a usable yardstick is a property of
    the goal, not of one companionship's fortnight. Asked of a single area that
    did nothing this week, it would answer "the goal is broken" when the truth
    is that the area is behind — which is the news, and the flag would bury it.
    That is why `grade_ki` and `grade_nightly` take the verdict as an argument
    rather than computing it per row.
    """
    pct = attainment(actual, goal)
    if pct is None:
        return None
    if pct < GOAL_FLOOR * 100:
        return GOAL_TOO_HIGH
    if pct > GOAL_CEILING * 100:
        return GOAL_TOO_LOW
    return None


@dataclass(frozen=True)
class Grade:
    """One judged row, for either renderer.

    ``status`` is decision 10's vocabulary — "good" / "warn" / "bad" / None —
    and is what a colour is taken from. ``pct`` is attainment against the goal
    and is always shown when it exists, whether or not it was graded on.
    ``change_pct`` is the move from the comparison period. ``flag`` marks a
    goal that is not a yardstick, and ``flag_label`` is the Spanish for it.
    """

    status: str | None = None
    pct: float | None = None
    change_pct: float | None = None
    flag: str | None = None

    @property
    def flag_label(self) -> str:
        return FLAG_LABELS.get(self.flag, "")

    @property
    def graded(self) -> bool:
        return self.status is not None


def grade_ki(actual, goal, before=None, *, now=None, pace=None,
             flag=None) -> Grade:
    """A Key Indicator: graded against its goal on 90/60, unless flagged.

    `pace` is the share of the goal due by now — pass `paced_goal(...)` for an
    in-progress period, so an area two weeks into a transfer is judged against
    two weeks of the target rather than all six.

    `now` and `before` are the pair the CHANGE is measured on; `now` defaults
    to `actual`. They come apart when attainment and change rest on different
    bases — see `grade_nightly`, where they always do.

    `flag` is the mission-scope verdict from `goal_is_unusable`, passed in
    rather than recomputed per row — see that function for why. A flagged goal
    is **not scored**: `status` comes back None and the row prints its flag
    instead of a colour. Decision 22 in one line. The change against the
    comparison period is still carried, since that is a statement about the
    work rather than about the goal.
    """
    status = None if flag else goal_bar_status(
        attainment(actual, pace if pace is not None else goal))
    now = actual if now is None else now
    return Grade(status=status, pct=attainment(actual, goal),
                 change_pct=change(now, before), flag=flag)


def grade_nightly(actual, goal, before=None, *, now=None, flag=None) -> Grade:
    """A nightly metric: graded on movement, never on the goal (decision 31).

    ``actual`` is judged against ``goal``; ``now`` and ``before`` are what the
    STATUS is taken from, and ``now`` defaults to ``actual``. On a nightly row
    they are deliberately different figures. The goal is one mission-wide
    number per area per week, so attainment divides by every ACTIVE area — an
    unreported night is work nobody recorded, and counting it as work would
    flatter. The change divides by the area-days that actually filed, because
    nine more areas reporting is not nine more areas working.

    The goal still rides along in ``pct`` and can still carry a flag — the mark
    is drawn beside the row and a reader is owed the truth about it — but it
    never becomes the colour, so a flag here does not silence the status the
    way it does on a Key Indicator. This is the difference between a report
    that says "meaningful conversations fell a fifth this week" and one that
    says all twenty metrics are red, again, as it has every week since the
    goals were set at roughly twice what the mission does.
    """
    now = actual if now is None else now
    return Grade(status=change_status(now, before),
                 pct=attainment(actual, goal),
                 change_pct=change(now, before), flag=flag)
