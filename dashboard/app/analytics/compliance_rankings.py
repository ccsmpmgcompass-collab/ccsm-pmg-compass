"""Per-area and per-zone submission compliance over an arbitrary period.

The Panel's section 7 used to end in an expander holding an all-time per-area
table. This module is the arithmetic behind what replaced it: a ranked list of
areas or zones, for a chosen period, over nightly submissions, weekly
submissions, or both.

Pure by design -- no Streamlit, no Sheets, no i18n. Everything it needs arrives
as DataFrames and dates, which is why it can be unit-tested against hand-checked
numbers instead of an AppTest fixture. Same split as zone_comparison.py,
period_delta.py and rate_metrics.py.

Three rules worth knowing before changing anything here:

1.  **An area's Overall % is the mean of its two rounded percentages**, never
    the pooled ratio of counts. An area with 18/20 days and 2/3 weeks reads 78%
    (mean of 90 and 67), not 87% (pooled 20/23). Pooling would let the nightly
    form -- which is filed seven times a week -- swamp the weekly one, so a
    missed weekly report would cost about a point instead of the third of a
    weekly grade it actually is.

2.  **A zone's % is the mean of its areas' Overall percentages**, while the
    day and week counts beside it are sums. A zone is a set of areas, and
    averaging the areas is what keeps a 13-area zone from outranking an 8-area
    one on volume -- the mission's standing rule for every zone comparison
    (see zone_comparison.py).

3.  **Possible days and weeks floor per area, not per mission.** An area that
    only started reporting at the last transfer is not credited with the days
    before it existed, and is not penalised for them either. The floor mirrors
    queries.get_alltime_compliance: SYSTEM_START_DATE normally,
    TRANSFER_START_DATE for an area whose blank Area_ID marks it as new -- but
    only when the log agrees the area really has no earlier rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

#: The period choices, in menu order. Mirrors breakdowns_engine._KPI_PERIODS --
#: a drift test holds the two lists and their bounds together, because a user
#: who reads "This Week" on two pages of one dashboard is entitled to the same
#: seven days on both.
PERIODS: tuple[str, ...] = (
    "This Week",
    "Last Week",
    "This Month So Far",
    "Last Month",
    "All Time",
)

#: What the percentage is measured over.
NIGHTLY = "nightly"
WEEKLY = "weekly"
OVERALL = "overall"
COMPLIANCE_TYPES: tuple[str, ...] = (OVERALL, NIGHTLY, WEEKLY)

#: Colour bands. Identical to the legends already printed under section 7's two
#: calendars -- the same number must not be green on one and amber on the other.
GREEN_MIN = 85
AMBER_MIN = 70


def status_of(pct: float | None) -> str:
    """"green" / "amber" / "red" / "none" for a compliance percentage."""
    if pct is None:
        return "none"
    if pct >= GREEN_MIN:
        return "green"
    if pct >= AMBER_MIN:
        return "amber"
    return "red"


def period_bounds(label: str, today: date) -> tuple[date | None, date | None]:
    """(start, end) for a period label, both ends inclusive.

    (None, None) for "All Time" -- the caller floors it at SYSTEM_START_DATE.
    The mission week runs Monday-Sunday (CCSM_Agent5A.gs rolls back to Monday
    and the weekly report covers Mon-Sun), so weeks anchor on Monday.
    """
    if label == "This Week":
        return today - timedelta(days=today.weekday()), today
    if label == "Last Week":
        this_monday = today - timedelta(days=today.weekday())
        return this_monday - timedelta(days=7), this_monday - timedelta(days=1)
    if label == "This Month So Far":
        return today.replace(day=1), today
    if label == "Last Month":
        last_day = today.replace(day=1) - timedelta(days=1)
        return last_day.replace(day=1), last_day
    return None, None


def clip_window(start: date | None, end: date | None,
                floor: date, anchor: date) -> tuple[date | None, date | None]:
    """Intersect a period with the range that can actually be graded.

    ``floor`` is the earliest date the mission (or the area) could have
    submitted; ``anchor`` is the last night whose deadline has passed. Returns
    (None, None) when the intersection is empty -- a period entirely before
    tracking began, which the page renders as "no data yet" rather than as a
    screen of zeroes.
    """
    lo = floor if start is None else max(start, floor)
    hi = anchor if end is None else min(end, anchor)
    if lo > hi:
        return None, None
    return lo, hi


def days_in(start: date | None, end: date | None) -> int:
    """Inclusive day count, 0 for an empty window."""
    if start is None or end is None or end < start:
        return 0
    return (end - start).days + 1


def sundays_in(start: date | None, end: date | None) -> list[date]:
    """Every Sunday in the window -- one per weekly report that came due.

    The weekly form covers Mon-Sun and is credited to the Sunday it closes, so
    the number of Sundays in a window is the number of weekly reports an area
    could have filed in it. A part-week with no Sunday yet (Monday to
    Wednesday, say) contains none, which is why "This Week" has no weekly
    grade until the week ends.
    """
    if start is None or end is None or end < start:
        return []
    first = start + timedelta(days=(6 - start.weekday()) % 7)
    out = []
    d = first
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


@dataclass(frozen=True)
class AreaWindow:
    """One area's compliance over one window."""
    area: str
    zone: str
    district: str
    days_submitted: int
    days_possible: int
    weeks_submitted: int
    weeks_possible: int

    @property
    def nightly_pct(self) -> int | None:
        if not self.days_possible:
            return None
        return round(self.days_submitted / self.days_possible * 100)

    @property
    def weekly_pct(self) -> int | None:
        if not self.weeks_possible:
            return None
        return round(self.weeks_submitted / self.weeks_possible * 100)

    @property
    def overall_pct(self) -> int | None:
        """Mean of the two rounded percentages -- see rule 1 in the module doc.

        When only one of the two is measurable the Overall figure IS that one,
        rather than treating the unmeasurable half as a zero. Early in a
        mission's life the window often holds nightly days but no closed
        Sunday, and averaging in a 0% there would report a failure that was
        never possible.
        """
        parts = [p for p in (self.nightly_pct, self.weekly_pct) if p is not None]
        if not parts:
            return None
        return round(sum(parts) / len(parts))

    def pct(self, compliance_type: str) -> int | None:
        if compliance_type == NIGHTLY:
            return self.nightly_pct
        if compliance_type == WEEKLY:
            return self.weekly_pct
        return self.overall_pct


def area_floor(area_row, system_start: date, transfer_start: date,
               first_log_date: date | None) -> date:
    """The earliest date this area can be graded from.

    A blank Area_ID in MISSION_ORG marks an area created or renamed at the last
    transfer, so it floors at TRANSFER_START_DATE instead of SYSTEM_START_DATE.
    The flag is a hint, not ground truth: live data has shown areas with a blank
    ID that were already submitting under the same name well before the
    transfer. When the log disagrees with the flag, the log wins -- otherwise
    days_possible can end up smaller than days_submitted and the area reports
    over 100%. Same reconciliation queries.get_alltime_compliance does.
    """
    is_new = str(area_row.get("Area_ID", "") or "").strip() == ""
    if not is_new:
        return system_start
    floor = max(system_start, transfer_start)
    if first_log_date is not None and first_log_date < floor:
        return system_start
    return floor


def build_area_windows(areas: pd.DataFrame, daily_log: pd.DataFrame,
                       weekly_subs: pd.DataFrame, *,
                       start: date | None, end: date | None,
                       system_start: date, transfer_start: date,
                       anchor: date) -> list[AreaWindow]:
    """One AreaWindow per active area, for the given period.

    ``areas`` is get_submitting_areas() (Area_Name / Zone / District / Area_ID),
    ``daily_log`` is get_daily_log() (Date / Area), ``weekly_subs`` is
    get_weekly_submission_data() (week_end_date / area).
    """
    if areas is None or areas.empty:
        return []

    log_dates: dict[str, set] = {}
    first_seen: dict[str, date] = {}
    if daily_log is not None and not daily_log.empty \
            and {"Date", "Area"} <= set(daily_log.columns):
        parsed = pd.to_datetime(daily_log["Date"], errors="coerce").dt.date
        names = daily_log["Area"].astype(str).str.strip()
        for area_name, when in zip(names, parsed):
            if when is None or pd.isna(when):
                continue
            log_dates.setdefault(area_name, set()).add(when)
            if area_name not in first_seen or when < first_seen[area_name]:
                first_seen[area_name] = when

    week_dates: dict[str, set] = {}
    if weekly_subs is not None and not weekly_subs.empty \
            and {"week_end_date", "area"} <= set(weekly_subs.columns):
        parsed = pd.to_datetime(weekly_subs["week_end_date"], errors="coerce").dt.date
        names = weekly_subs["area"].astype(str).str.strip()
        for area_name, when in zip(names, parsed):
            if when is None or pd.isna(when):
                continue
            week_dates.setdefault(area_name, set()).add(when)

    out = []
    for _, row in areas.iterrows():
        name = str(row.get("Area_Name", row.get("Area", "")) or "").strip()
        if not name:
            continue
        floor = area_floor(row, system_start, transfer_start, first_seen.get(name))
        lo, hi = clip_window(start, end, floor, anchor)
        sundays = sundays_in(lo, hi)
        mine_days = log_dates.get(name, set())
        mine_weeks = week_dates.get(name, set())
        out.append(AreaWindow(
            area=name,
            zone=str(row.get("Zone", "") or "").strip(),
            district=str(row.get("District", "") or "").strip(),
            days_submitted=(0 if lo is None else
                            sum(1 for x in mine_days if lo <= x <= hi)),
            days_possible=days_in(lo, hi),
            weeks_submitted=sum(1 for s in sundays if s in mine_weeks),
            weeks_possible=len(sundays),
        ))
    return out


@dataclass(frozen=True)
class ZoneWindow:
    """One zone's compliance -- counts summed, percentage averaged."""
    zone: str
    areas: int
    days_submitted: int
    days_possible: int
    weeks_submitted: int
    weeks_possible: int
    area_pcts: tuple

    def pct(self, compliance_type: str = OVERALL) -> int | None:
        """Mean of the member areas' percentages -- see rule 2 in the module doc.

        Areas with nothing measurable for this compliance type are dropped from
        the average rather than counted as zero, on the same reasoning as
        AreaWindow.overall_pct. ``compliance_type`` is accepted for signature
        parity with AreaWindow.pct but is not used: the percentages were already
        reduced for the chosen type by build_zone_windows.
        """
        vals = [p for p in self.area_pcts if p is not None]
        return round(sum(vals) / len(vals)) if vals else None


def build_zone_windows(rows: list[AreaWindow],
                       compliance_type: str) -> list[ZoneWindow]:
    """Roll AreaWindows up to zones for the given compliance type."""
    by_zone: dict[str, list[AreaWindow]] = {}
    for r in rows:
        by_zone.setdefault(r.zone or "", []).append(r)

    out = []
    for zone, members in by_zone.items():
        out.append(ZoneWindow(
            zone=zone,
            areas=len(members),
            days_submitted=sum(m.days_submitted for m in members),
            days_possible=sum(m.days_possible for m in members),
            weeks_submitted=sum(m.weeks_submitted for m in members),
            weeks_possible=sum(m.weeks_possible for m in members),
            area_pcts=tuple(m.pct(compliance_type) for m in members),
        ))
    return out


def rank(rows, compliance_type: str = OVERALL, *, worst_first: bool = False,
         by_name: bool = False):
    """Sort rows for display.

    Rows with no reading sort last in BOTH directions -- "not measurable" is not
    an achievement and not a failure, so it does not belong at either end of a
    leaderboard. Ties break on name so the order is stable between reruns.
    """
    def name_of(r) -> str:
        return getattr(r, "area", None) or getattr(r, "zone", "") or ""

    if by_name:
        return sorted(rows, key=name_of)

    readable = [r for r in rows if r.pct(compliance_type) is not None]
    missing = sorted([r for r in rows if r.pct(compliance_type) is None],
                     key=name_of)
    readable.sort(key=name_of)
    readable.sort(key=lambda r: r.pct(compliance_type), reverse=not worst_first)
    return readable + missing


__all__ = [
    "PERIODS", "NIGHTLY", "WEEKLY", "OVERALL", "COMPLIANCE_TYPES",
    "GREEN_MIN", "AMBER_MIN", "status_of",
    "period_bounds", "clip_window", "days_in", "sundays_in",
    "AreaWindow", "ZoneWindow", "area_floor",
    "build_area_windows", "build_zone_windows", "rank",
]
