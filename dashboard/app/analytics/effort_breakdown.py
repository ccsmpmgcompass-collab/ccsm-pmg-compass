"""Nightly effort answers, counted against every active area — not just the ones
that filed.

The Panel's effort section used to read `DASHBOARD_SUMMARY`'s EFFORT rows, which
`CCSM_Agent5A.gs` writes as one row per date holding all/most/some counts and a
`total_areas` column that is *how many areas submitted*, not how many exist. Run
live on 2026-08-22 the section reported "146 Todo, 83 La mayor parte, 13 Algo"
— 242 answers presented as the mission, when the mission had 43 areas over 7
days and therefore 301 chances to answer. The 59 area-days nobody filed were
invisible, and every share on screen was silently a share of the submitters.

So this module counts a window the other way round: **the denominator is built
from the active areas and the days, and the answers are placed into it.** What
is missing is a number, not an absence.

Three things worth knowing before changing anything here:

1.  **The source is `DAILY_LOG`, not `DASHBOARD_SUMMARY`.** `CCSM_Agent3.gs`
    appends one deduplicated row per area per date and backfills late arrivals,
    while Agent5A re-tallies the raw form and counts a re-submission twice —
    live, the two disagreed on 2 of 7 dates (2026-08-21: 26 areas vs 33). It is
    also the tab section 7's compliance calendar already counts, and one page
    may not hold two different answers to "how many areas reported that night".
    `DAILY_LOG` keeps the answer as the form's own Spanish text, so read it
    through `queries.get_daily_effort_log()` — `get_daily_log()` coerces every
    metric column to a number and turns "Todo" into 0.

2.  **Possible days floor per area.** An area created at the last transfer is
    not charged for the days before it existed. The floor is
    `compliance_rankings.area_floor`, reused rather than reimplemented, so an
    area's denominator here and its denominator in the compliance rankings can
    never drift apart.

3.  **The score is computed over the areas that answered, and only them.** A
    missing form is a compliance failure — section 7 grades it, by name — and
    scoring it as zero effort would say something the data does not: that the
    companionship worked badly, rather than that nobody knows. The reporting
    share travels beside the score for exactly this reason; the two facts are
    reported together and never merged.

Pure: no Streamlit, no sheet access, no i18n. Same split as zone_comparison.py,
period_delta.py, rate_metrics.py and compliance_rankings.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from app.analytics.compliance_rankings import area_floor

#: The three answers, strongest first. These ids are internal; the form's own
#: wording is in LEVEL_TEXT and the display labels belong to the page.
ALL = "all"
MOST = "most"
SOME = "some"
LEVELS: tuple[str, ...] = (ALL, MOST, SOME)

#: Weights behind the effort score. Identical to `ccsmEffortScore` in
#: CCSM_Helpers.gs, which is what AGENT_CONFIG's EFFORT_SCORE_TARGET is set
#: against — a different weighting here would grade the mission on one scale
#: and compare it to a target measured on another.
LEVEL_WEIGHTS: dict[str, int] = {ALL: 3, MOST: 2, SOME: 1}

#: The answers as the Spanish nightly form writes them, lowercased. Matching on
#: text is deliberate: DAILY_LOG stores the label, not a code, so this is the
#: only place the two vocabularies meet.
LEVEL_TEXT: dict[str, str] = {
    "todo": ALL,
    "la mayor parte": MOST,
    "algo": SOME,
}

#: Length of the window the Panel shows, in days. Same 7 as period_delta's.
WINDOW_DAYS = 7


def normalize_level(raw) -> str | None:
    """One of LEVELS for a raw DAILY_LOG effort cell, or None if it isn't one.

    Blank cells, "nan" and anything the form no longer offers return None and
    are counted as *not answered* rather than quietly folded into "Algo".
    """
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text or text == "nan":
        return None
    return LEVEL_TEXT.get(text)


def score_of(counts: dict) -> float | None:
    """Effort score for a tally of answers, or None when nothing was answered.

    (Todo x3 + La mayor parte x2 + Algo x1) / answers, over the answers only —
    see rule 3 in the module docstring.
    """
    answered = sum(int(counts.get(k, 0)) for k in LEVELS)
    if answered <= 0:
        return None
    weighted = sum(int(counts.get(k, 0)) * LEVEL_WEIGHTS[k] for k in LEVELS)
    return weighted / answered


#: AGENT_CONFIG's target for the effort score, and the value CcsmData.gs seeds
#: it with. Stored plainly (2.75), not as the 0-1 fraction the rate targets use
#: — rate_metrics.target_pct multiplies by 100 and this deliberately does not.
SCORE_TARGET_KEY = "EFFORT_SCORE_TARGET"
DEFAULT_SCORE_TARGET = 2.75


def score_target(config: dict, *, default: float = DEFAULT_SCORE_TARGET) -> float:
    """The configured effort-score target, on the same 1-3 scale as `score_of`.

    A missing, blank or unparseable row falls back to the agent's own default
    rather than to zero, which would paint any score at all as target met.
    """
    raw = (config or {}).get(SCORE_TARGET_KEY)
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def window_bounds(anchor: date, *, days: int = WINDOW_DAYS) -> tuple[date, date]:
    """``(start, end)`` for the ``days``-day window ending on ``anchor``.

    ``anchor`` is the last night whose deadline has passed
    (`area_helpers.compliance_anchor_date`), never today: an area that has until
    9:30 PM to file has not missed anything at 2 in the afternoon.
    """
    return anchor - timedelta(days=days - 1), anchor


@dataclass(frozen=True)
class DayEffort:
    """One date: what was answered, and how many areas could have answered."""

    day: date
    counts: dict
    possible: int

    @property
    def answered(self) -> int:
        return sum(int(self.counts.get(k, 0)) for k in LEVELS)

    @property
    def missing(self) -> int:
        return max(0, self.possible - self.answered)

    @property
    def score(self) -> float | None:
        return score_of(self.counts)

    def share(self, level: str) -> float | None:
        """This level as a percentage of the area-days that were possible."""
        if self.possible <= 0:
            return None
        return int(self.counts.get(level, 0)) / self.possible * 100.0

    @property
    def missing_share(self) -> float | None:
        if self.possible <= 0:
            return None
        return self.missing / self.possible * 100.0


@dataclass(frozen=True)
class AreaEffort:
    """One area over the whole window."""

    area: str
    zone: str
    district: str
    counts: dict
    possible: int

    @property
    def answered(self) -> int:
        return sum(int(self.counts.get(k, 0)) for k in LEVELS)

    @property
    def missing(self) -> int:
        return max(0, self.possible - self.answered)

    @property
    def score(self) -> float | None:
        return score_of(self.counts)


@dataclass
class EffortWindow:
    """A window of nightly effort answers, with the honest denominator attached."""

    start: date | None
    end: date | None
    days: list = field(default_factory=list)   # list[DayEffort], oldest first
    areas: list = field(default_factory=list)  # list[AreaEffort], by area name

    @property
    def counts(self) -> dict:
        return {k: sum(int(d.counts.get(k, 0)) for d in self.days) for k in LEVELS}

    @property
    def possible(self) -> int:
        """Area-days the mission could have answered, floors included."""
        return sum(d.possible for d in self.days)

    @property
    def answered(self) -> int:
        return sum(d.answered for d in self.days)

    @property
    def missing(self) -> int:
        return max(0, self.possible - self.answered)

    @property
    def score(self) -> float | None:
        return score_of(self.counts)

    @property
    def reporting_pct(self) -> float | None:
        """Share of possible area-days that carry an answer at all."""
        if self.possible <= 0:
            return None
        return self.answered / self.possible * 100.0

    def share(self, level: str) -> float | None:
        if self.possible <= 0:
            return None
        return int(self.counts.get(level, 0)) / self.possible * 100.0

    @property
    def missing_share(self) -> float | None:
        if self.possible <= 0:
            return None
        return self.missing / self.possible * 100.0

    @property
    def area_count(self) -> int:
        return len(self.areas)


#: Answers an area needs before its score may be ranked against the others.
#: Yumbel answered twice in the window and said "Todo" both times, which is a
#: perfect 3,00 — above every area that answered all seven nights and had one
#: ordinary day. Same instinct as period_delta.MIN_COMPARABLE_DAYS: a number is
#: not comparable just because it can be computed. Areas below the threshold
#: keep their score and sink to the bottom of the list; nothing is hidden.
MIN_RANKABLE_ANSWERS = 4


def rank_areas(areas: list, *, min_answers: int = MIN_RANKABLE_ANSWERS) -> list:
    """AreaEffort rows in display order: best effort first, thin evidence last.

    Sorted by (enough answers to rank, score, answers). An area with no answers
    at all has no score and sorts last of the last — see `score_of`, which
    refuses to call that a zero.
    """
    def key(a):
        rankable = a.answered >= min_answers
        return (1 if rankable else 0,
                a.score if a.score is not None else -1.0,
                a.answered)

    return sorted(areas, key=key, reverse=True)


def _first_log_dates(effort_log: pd.DataFrame) -> dict:
    """Earliest date each area appears in the log — the evidence `area_floor`
    weighs against MISSION_ORG's blank-Area_ID hint."""
    seen: dict = {}
    if effort_log is None or effort_log.empty:
        return seen
    if not {"Date", "Area"} <= set(effort_log.columns):
        return seen
    parsed = pd.to_datetime(effort_log["Date"], errors="coerce").dt.date
    names = effort_log["Area"].astype(str).str.strip()
    for name, when in zip(names, parsed):
        if when is None or pd.isna(when) or not name:
            continue
        if name not in seen or when < seen[name]:
            seen[name] = when
    return seen


def area_floors(areas: pd.DataFrame, effort_log: pd.DataFrame, *,
                system_start: date, transfer_start: date) -> dict:
    """``{area name: earliest date it can be graded from}`` for every active area.

    ``areas`` is `queries.get_submitting_areas()` (Area_Name / Zone / District /
    Area_ID). ``effort_log`` should be the FULL log, not the window — an area's
    first-ever row is what tells `area_floor` whether a blank Area_ID really
    means "new at this transfer".
    """
    if areas is None or areas.empty or "Area_Name" not in areas.columns:
        return {}
    first_seen = _first_log_dates(effort_log)
    floors: dict = {}
    for _, row in areas.iterrows():
        name = str(row.get("Area_Name", "") or "").strip()
        if not name:
            continue
        floors[name] = area_floor(row, system_start, transfer_start,
                                  first_seen.get(name))
    return floors


def build_window(effort_log: pd.DataFrame, areas: pd.DataFrame, *,
                 start: date | None, end: date | None,
                 system_start: date, transfer_start: date) -> EffortWindow:
    """The window's answers, per day and per area, over every active area.

    ``effort_log`` is `queries.get_daily_effort_log()` (Date / Area / Zone /
    District / effort). Rows for areas outside ``areas`` are ignored — a closed
    area's old rows must not appear in a numerator whose denominator no longer
    counts it, or a day can read over 100%.
    """
    floors = area_floors(areas, effort_log,
                         system_start=system_start, transfer_start=transfer_start)
    if not floors or start is None or end is None or end < start:
        return EffortWindow(start=start, end=end)

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    # One answer per area per date. DAILY_LOG holds no duplicates today, but
    # assignment makes that a property of this function rather than a hope.
    answers: dict = {}
    if effort_log is not None and not effort_log.empty \
            and {"Date", "Area", "effort"} <= set(effort_log.columns):
        parsed = pd.to_datetime(effort_log["Date"], errors="coerce").dt.date
        names = effort_log["Area"].astype(str).str.strip()
        for name, when, raw in zip(names, parsed, effort_log["effort"]):
            if when is None or pd.isna(when):
                continue
            if when < start or when > end or name not in floors:
                continue
            level = normalize_level(raw)
            if level is not None:
                answers[(name, when)] = level

    meta = {}
    if {"Zone", "District"} <= set(areas.columns):
        for _, row in areas.iterrows():
            meta[str(row.get("Area_Name", "") or "").strip()] = (
                str(row.get("Zone", "") or "").strip(),
                str(row.get("District", "") or "").strip(),
            )

    day_rows = []
    for day in days:
        counts = {k: 0 for k in LEVELS}
        possible = 0
        for name, floor in floors.items():
            if floor is not None and day < floor:
                continue
            possible += 1
            level = answers.get((name, day))
            if level:
                counts[level] += 1
        day_rows.append(DayEffort(day=day, counts=counts, possible=possible))

    area_rows = []
    for name in sorted(floors):
        floor = floors[name]
        counts = {k: 0 for k in LEVELS}
        possible = 0
        for day in days:
            if floor is not None and day < floor:
                continue
            possible += 1
            level = answers.get((name, day))
            if level:
                counts[level] += 1
        zone, district = meta.get(name, ("", ""))
        area_rows.append(AreaEffort(area=name, zone=zone, district=district,
                                    counts=counts, possible=possible))

    return EffortWindow(start=start, end=end, days=day_rows, areas=area_rows)


__all__ = [
    "ALL", "MOST", "SOME", "LEVELS", "LEVEL_WEIGHTS", "LEVEL_TEXT",
    "WINDOW_DAYS", "SCORE_TARGET_KEY", "DEFAULT_SCORE_TARGET",
    "normalize_level", "score_of", "score_target", "window_bounds",
    "DayEffort", "AreaEffort", "EffortWindow", "area_floors", "build_window",
    "MIN_RANKABLE_ANSWERS", "rank_areas",
]
