"""Key Indicator history — the series behind the drill-down.

PLAN-2026-09-18-data-pages.md §3, step B1. A tapped Key Indicator opens a
panel that shows the metric by week against the companionships' own metas
(decision 6), the same weeks of the previous cambio as ghosts (decision 5),
the metric by cambio, and the areas in scope ranked by how they did. This
module is the arithmetic behind all four views; ``ki_drilldown`` draws them.

Pure functions, no Streamlit. Every reader of the sheet is behind a keyword
argument (``weekly=``, ``daily=``, ``goals_by_cycle=``, ``cycles=``) that
defaults to the live loader, so the tests hand in synthetic frames and the
pages hand in nothing.

Three rules the rest of the app already lives by, applied here as well:

* **A week's meta is written on the PREVIOUS week's form.** The weekly form
  asks for last week's results and next week's goals on one row, so the meta
  FOR week W is on the row for W-7 (``get_ki_goals_for_week``, and the same
  offset in ``breakdowns_engine``'s Key Indicator cards).
* **No meta written is "sin meta", never a zero goal.** A blank meta counts
  as nothing set; the point carries ``None`` and the chart draws no dash.
* **Membership is the caller's roster.** ``scope_areas`` is the set of area
  names MISSION_ORG lists for the scope today; the frames are filtered on the
  area name, never on their own Zone column (``_scope_to_areas``' reasoning).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

import pandas as pd

from app.analytics.period_delta import period_delta


# ── The shapes ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WeekPoint:
    """One Mon–Sun week of a cambio, for the "Por semana" bars.

    ``actual`` is None when no area in scope filed a weekly form for the week
    — a week nobody reported is not a zero. ``meta`` is None when no area
    wrote a meta for it. ``meta_set_by`` counts the areas whose meta was
    above zero; ``reporting`` counts the areas with a row that week.
    """
    start: date
    end: date
    actual: float | None
    meta: float | None
    meta_set_by: int
    reporting: int
    is_current: bool
    is_future: bool


@dataclass(frozen=True)
class CyclePoint:
    """One cambio, for the "Por cambio" bars.

    ``actual`` sums the weeks that have data; ``meta_so_far`` sums the metas
    written for the weeks up to and including the current one (§1.1: actual
    so far against metas set so far); ``leadership`` is the transfer goal
    from Metas for the areas in scope, or None when none is saved.
    """
    number: str
    start: date
    end: date
    actual: float | None
    meta_so_far: float | None
    leadership: float | None
    weeks_covered: int
    weeks_total: int
    is_current: bool


@dataclass(frozen=True)
class AreaRow:
    """One area of the scope over a window, for the "Por área" ranking.

    An area with no row in the window is still present — ``reported`` False,
    ``actual`` 0 — so the list names who did not file rather than hiding
    them. ``change`` is ``period_delta`` against the twin window on a basis of
    one area each side, or None when the twin has no row for the area.
    ``nights_missed`` counts the nights in the window with no DAILY_LOG row,
    or None when no daily frame was given.
    """
    area: str
    actual: float
    meta: float | None
    pct: float | None
    change: dict | None
    reported: bool
    weeks_reported: int
    nights_missed: int | None


# ── Calendar helpers ─────────────────────────────────────────────────────────

def meta_key(metric: str) -> str | None:
    """The ``_meta`` column beside a ``_real`` key, by name.

    By name rather than through ``metric_catalog.goal_metric_key``: that reads
    QUESTIONS_CONFIG, and this module never touches the sheet on its own. A
    frame without the column simply yields no meta.
    """
    suffix = "_real"
    if not str(metric).endswith(suffix):
        return None
    return str(metric)[: -len(suffix)] + "_meta"


def cycle_weeks(cycle: dict) -> list[tuple[date, date]]:
    """The Mon–Sun weeks of a cycle, oldest first, as (monday, sunday).

    The first week starts on the Monday on or before the cycle's start, and a
    week is included while its Monday is inside the cycle — so a cycle that
    starts or ends mid-week (the schedule's rows are Mondays, but nothing
    forces that) still gets whole reporting weeks, which is the grain the
    weekly form has.
    """
    start, end = cycle["start"], cycle["end"]
    monday = start - timedelta(days=start.weekday())
    out: list[tuple[date, date]] = []
    while monday <= end:
        out.append((monday, monday + timedelta(days=6)))
        monday += timedelta(days=7)
    return out


def cycle_position(cycle: dict, today: date) -> tuple[int, int]:
    """``(week n, of m)`` for the caption "cambio 2026-6 · semana 2 de 6".

    Before the cycle n is 0; after it n is m.
    """
    weeks = cycle_weeks(cycle)
    m = len(weeks)
    n = sum(1 for monday, _ in weeks if monday <= today)
    return min(n, m), m


def sundays_between(start: date, end: date) -> list[date]:
    """Every week_end_date (Sunday) inside [start, end]."""
    first = start + timedelta(days=(6 - start.weekday()) % 7)
    out: list[date] = []
    d = first
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


# ── Frame helpers ────────────────────────────────────────────────────────────

def _today(today: date | None) -> date:
    if today is not None:
        return today
    from app.utils.area_helpers import mission_today
    return mission_today()


def _load_weekly(weekly: pd.DataFrame | None, scope_areas: Iterable[str]) -> pd.DataFrame:
    """The weekly form frame, cut to the scope's areas by name."""
    if weekly is None:
        from app.db.queries import get_weekly_form_data
        weekly = get_weekly_form_data()
    areas = {str(a).strip() for a in scope_areas}
    if weekly is None or weekly.empty or "area" not in weekly.columns or not areas:
        return pd.DataFrame()
    df = weekly[weekly["area"].astype(str).str.strip().isin(areas)].copy()
    if "week_end_date" in df.columns:
        df["week_end_date"] = df["week_end_date"].astype(str).str.strip().str[:10]
    return df


def _week_rows(df: pd.DataFrame, week_end: date) -> pd.DataFrame:
    if df.empty or "week_end_date" not in df.columns:
        return pd.DataFrame()
    return df[df["week_end_date"] == week_end.isoformat()]


def _sum(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).sum())


def _reporting(df: pd.DataFrame) -> int:
    if df.empty or "area" not in df.columns:
        return 0
    return int(df["area"].nunique())


def _meta_for_week(df: pd.DataFrame, metric: str, week_end: date) -> tuple[float | None, int]:
    """The metas written FOR the week ending ``week_end`` — on the rows of
    the week before — and how many areas wrote one. (None, 0) when none did."""
    col = meta_key(metric)
    rows = _week_rows(df, week_end - timedelta(days=7))
    if col is None or rows.empty or col not in rows.columns:
        return None, 0
    values = pd.to_numeric(rows[col], errors="coerce").fillna(0.0)
    total = float(values.sum())
    if total <= 0:
        return None, 0
    if "area" in rows.columns:
        set_by = int(rows.loc[values > 0, "area"].nunique())
    else:
        set_by = int((values > 0).sum())
    return total, set_by


# ── The series ───────────────────────────────────────────────────────────────

def weekly_series(scope_areas: Iterable[str], metric: str, cycle: dict, *,
                  weekly: pd.DataFrame | None = None,
                  today: date | None = None) -> list[WeekPoint]:
    """One point per week of ``cycle`` for the areas in scope."""
    df = _load_weekly(weekly, scope_areas)
    today = _today(today)
    out: list[WeekPoint] = []
    for monday, sunday in cycle_weeks(cycle):
        rows = _week_rows(df, sunday)
        reporting = _reporting(rows)
        actual = _sum(rows, metric) if reporting and metric in rows.columns else None
        meta, set_by = _meta_for_week(df, metric, sunday)
        out.append(WeekPoint(
            start=monday, end=sunday, actual=actual, meta=meta,
            meta_set_by=set_by, reporting=reporting,
            is_current=monday <= today <= sunday,
            is_future=monday > today,
        ))
    return out


def twin_weekly(scope_areas: Iterable[str], metric: str, cycle: dict,
                prev_cycle: dict | None, *,
                weekly: pd.DataFrame | None = None) -> list[float | None]:
    """The previous cambio's actuals at the same week indices as
    ``weekly_series(cycle)`` — None where the twin has no data for that
    week, and None past the twin's last week."""
    n = len(cycle_weeks(cycle))
    if prev_cycle is None:
        return [None] * n
    df = _load_weekly(weekly, scope_areas)
    prev = cycle_weeks(prev_cycle)
    out: list[float | None] = []
    for i in range(n):
        if i >= len(prev):
            out.append(None)
            continue
        rows = _week_rows(df, prev[i][1])
        has = _reporting(rows) and metric in rows.columns
        out.append(_sum(rows, metric) if has else None)
    return out


def cycle_series(scope_areas: Iterable[str], metric: str, *,
                 cycles: list[dict] | None = None,
                 weekly: pd.DataFrame | None = None,
                 goals_by_cycle: dict | None = None,
                 today: date | None = None) -> list[CyclePoint]:
    """One point per cambio that has any weekly data for the scope, oldest
    first. A cycle with no rows at all is left out — "Por cambio" starts with
    the cycles the mission has actually reported and grows one per cycle
    (§1.3), rather than opening on a row of empty bars.

    ``goals_by_cycle`` is ``{cycle start date: {metric: total}}``, the shape
    ``goals_queries.goals_by_cycle_start`` returns; loaded for the scope when
    not given.
    """
    if cycles is None:
        from app.utils.transfer_helpers import transfer_cycles
        cycles = transfer_cycles()
    areas = list(scope_areas)
    if goals_by_cycle is None:
        from app.db.goals_queries import goals_by_cycle_start
        goals_by_cycle = goals_by_cycle_start(set(areas))
    df = _load_weekly(weekly, areas)
    today = _today(today)

    out: list[CyclePoint] = []
    for cycle in cycles:
        points = weekly_series(areas, metric, cycle, weekly=df, today=today)
        covered = [p for p in points if p.reporting]
        if not covered:
            continue
        actual = sum(p.actual or 0.0 for p in covered)
        metas = [p.meta for p in points if not p.is_future and p.meta is not None]
        meta_so_far = sum(metas) if metas else None
        lead = float((goals_by_cycle.get(cycle["start"]) or {}).get(metric, 0) or 0)
        out.append(CyclePoint(
            number=str(cycle.get("number") or "").strip(),
            start=cycle["start"], end=cycle["end"],
            actual=actual, meta_so_far=meta_so_far,
            leadership=lead if lead > 0 else None,
            weeks_covered=len(covered), weeks_total=len(points),
            is_current=cycle["start"] <= today <= cycle["end"],
        ))
    return out


def _area_window(df: pd.DataFrame, area: str, metric: str,
                 start: date, end: date) -> tuple[float, float | None, int]:
    """(actual, meta or None, weeks with a row) for one area over a window."""
    if df.empty or "area" not in df.columns:
        mine = pd.DataFrame()
    else:
        mine = df[df["area"].astype(str).str.strip() == area]
    actual = 0.0
    meta_total = 0.0
    any_meta = False
    weeks = 0
    for sunday in sundays_between(start, end):
        rows = _week_rows(mine, sunday)
        if not rows.empty:
            weeks += 1
            actual += _sum(rows, metric)
        m, _set_by = _meta_for_week(mine, metric, sunday)
        if m is not None:
            any_meta = True
            meta_total += m
    return actual, (meta_total if any_meta else None), weeks


def _nights_missed(daily: pd.DataFrame, area: str, start: date, end: date) -> int:
    """Nights in [start, end] with no DAILY_LOG row for the area."""
    if daily is None or daily.empty or "Date" not in daily.columns or "Area" not in daily.columns:
        return 0
    if end < start:
        return 0
    mine = daily[daily["Area"].astype(str).str.strip() == area]
    filed = set(mine["Date"].astype(str).str.strip().str[:10])
    d, missed = start, 0
    while d <= end:
        if d.isoformat() not in filed:
            missed += 1
        d += timedelta(days=1)
    return missed


def area_rows(scope_areas: Iterable[str], metric: str,
              window: tuple[date, date],
              twin_window: tuple[date, date] | None = None, *,
              weekly: pd.DataFrame | None = None,
              daily: pd.DataFrame | None = None,
              today: date | None = None) -> list[AreaRow]:
    """Every area of the scope over ``window``, ranked: by % of meta where
    a meta exists, then by actual. ``daily`` is the DAILY_LOG frame (Date,
    Area) for the nights-missed count; the nights counted run from the
    window's start to the earlier of its end and yesterday, because tonight's
    report has not been asked for yet.
    """
    areas = sorted({str(a).strip() for a in scope_areas if str(a).strip()})
    df = _load_weekly(weekly, areas)
    today = _today(today)
    start, end = window
    out: list[AreaRow] = []
    for area in areas:
        actual, meta, weeks = _area_window(df, area, metric, start, end)
        change = None
        if twin_window is not None:
            t_actual, _t_meta, t_weeks = _area_window(df, area, metric, *twin_window)
            if t_weeks:
                change = period_delta(actual, t_actual, current_basis=1,
                                      prior_basis=1, min_basis=1)
        nights = None
        if daily is not None:
            nights = _nights_missed(daily, area, start,
                                    min(end, today - timedelta(days=1)))
        out.append(AreaRow(
            area=area, actual=actual, meta=meta,
            pct=(actual / meta * 100.0) if meta else None,
            change=change, reported=weeks > 0, weeks_reported=weeks,
            nights_missed=nights,
        ))
    out.sort(key=lambda r: (r.pct is None, -(r.pct or 0.0), -r.actual, r.area))
    return out


# ── The nightly series ───────────────────────────────────────────────────────
# PLAN-2026-09-18-data-pages.md §5, step D3: the twenty nightly rows link into
# the same drill-down the seven Key Indicators open, so the panel needs their
# history in the shape it already draws. DAILY_LOG is one row per area per
# NIGHT, so it is bucketed into the mission's Mon–Sun weeks first and then read
# exactly like the weekly form — same WeekPoint, same CyclePoint, same AreaRow,
# so ki_drilldown draws all four tabs with no second set of charts.
#
# The one real difference is the goal. A nightly metric has no companionship
# meta and no leadership transfer goal; what it has is AGENT_CONFIG's
# GOAL_<metric>, a target PER AREA PER WEEK. So a week's goal here is that
# figure times the areas that actually reported it — the same arithmetic
# _resolve_group_goal's third tier does for the cards, which is what keeps the
# row's "18% de 20.250" and the panel's bars saying one thing.


def _load_daily(daily: pd.DataFrame | None, scope_areas: Iterable[str]) -> pd.DataFrame:
    """DAILY_LOG cut to the scope's areas, with a Mon–Sun ``week_end_date``.

    Returns the weekly-form SHAPE — one row per area per week, ``area`` and
    ``week_end_date`` lowercase — so every reader below this line is the one
    the weekly series already uses.
    """
    if daily is None:
        from app.db.queries import get_daily_log
        daily = get_daily_log()
    areas = {str(a).strip() for a in scope_areas}
    if daily is None or daily.empty or not areas:
        return pd.DataFrame()
    if "week_end_date" in daily.columns and "area" in daily.columns:
        # Already bucketed: a caller reading several cycles (daily_cycle_series)
        # buckets once and hands the result down. Without this the second pass
        # found no Date column and returned nothing, which emptied "Por cambio"
        # for every nightly metric.
        return daily[daily["area"].isin(areas)]
    if "Area" not in daily.columns or "Date" not in daily.columns:
        return pd.DataFrame()
    df = daily[daily["Area"].astype(str).str.strip().isin(areas)].copy()
    if df.empty:
        return pd.DataFrame()
    parsed = pd.to_datetime(df["Date"], errors="coerce")
    df = df[parsed.notna()]
    if df.empty:
        return pd.DataFrame()
    parsed = parsed[parsed.notna()]
    # The Sunday that ends each row's week — the same convention WEEKLY_KI's
    # week_end_date and every other weekly bucket in the app uses.
    df["week_end_date"] = (
        parsed + pd.to_timedelta(6 - parsed.dt.weekday, unit="D")
    ).dt.strftime("%Y-%m-%d")
    df["area"] = df["Area"].astype(str).str.strip()
    value_cols = [c for c in df.columns
                  if c not in ("Date", "Area", "area", "week_end_date")]
    for c in value_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if not value_cols:
        return pd.DataFrame()
    return (df.groupby(["area", "week_end_date"], as_index=False)[value_cols]
              .sum(min_count=1))


def daily_series(scope_areas: Iterable[str], metric: str, cycle: dict, *,
                 daily: pd.DataFrame | None = None,
                 goal_per_area: float | None = None,
                 today: date | None = None) -> list[WeekPoint]:
    """``weekly_series`` for a NIGHTLY metric — one point per week of the
    cycle, from DAILY_LOG.

    ``reporting`` counts the areas with at least one night in the week, and
    the goal is ``goal_per_area`` times that count: a week's target belongs to
    the areas that were there for it, so a week two areas reported is not held
    to forty-five areas' goal. Without a ``goal_per_area`` the points carry no
    goal at all, exactly as a Key Indicator week nobody wrote a meta for does.
    """
    df = _load_daily(daily, scope_areas)
    today = _today(today)
    out: list[WeekPoint] = []
    for monday, sunday in cycle_weeks(cycle):
        rows = _week_rows(df, sunday)
        reporting = _reporting(rows)
        actual = _sum(rows, metric) if reporting and metric in rows.columns else None
        meta = (float(goal_per_area) * reporting
                if goal_per_area and reporting else None)
        out.append(WeekPoint(
            start=monday, end=sunday, actual=actual, meta=meta,
            meta_set_by=reporting if meta is not None else 0,
            reporting=reporting,
            is_current=monday <= today <= sunday,
            is_future=monday > today,
        ))
    return out


def daily_twin(scope_areas: Iterable[str], metric: str, cycle: dict,
               prev_cycle: dict | None, *,
               daily: pd.DataFrame | None = None) -> list[float | None]:
    """``twin_weekly`` for a nightly metric: the previous cambio's weeks at the
    same indices."""
    n = len(cycle_weeks(cycle))
    if prev_cycle is None:
        return [None] * n
    prev = daily_series(scope_areas, metric, prev_cycle, daily=daily,
                        today=prev_cycle["end"])
    return [(prev[i].actual if i < len(prev) else None) for i in range(n)]


def daily_cycle_series(scope_areas: Iterable[str], metric: str, *,
                       cycles: list[dict] | None = None,
                       daily: pd.DataFrame | None = None,
                       goal_per_area: float | None = None,
                       today: date | None = None) -> list[CyclePoint]:
    """``cycle_series`` for a nightly metric. A cycle with no nights at all is
    left out, same rule as the weekly one — "Por cambio" starts with what the
    mission has actually reported."""
    if cycles is None:
        from app.utils.transfer_helpers import transfer_cycles
        cycles = transfer_cycles()
    areas = list(scope_areas)
    df = _load_daily(daily, areas)
    today = _today(today)
    out: list[CyclePoint] = []
    for cycle in cycles:
        points = daily_series(areas, metric, cycle, daily=df,
                              goal_per_area=goal_per_area, today=today)
        covered = [p for p in points if p.reporting]
        if not covered:
            continue
        metas = [p.meta for p in points if not p.is_future and p.meta is not None]
        out.append(CyclePoint(
            number=str(cycle.get("number") or "").strip(),
            start=cycle["start"], end=cycle["end"],
            actual=sum(p.actual or 0.0 for p in covered),
            meta_so_far=sum(metas) if metas else None,
            # There is no leadership transfer goal for a nightly metric:
            # AREA_TRANSFER_GOALS is keyed on the seven Key Indicators.
            leadership=None,
            weeks_covered=len(covered), weeks_total=len(points),
            is_current=cycle["start"] <= today <= cycle["end"],
        ))
    return out


def daily_area_rows(scope_areas: Iterable[str], metric: str,
                    window: tuple[date, date],
                    twin_window: tuple[date, date] | None = None, *,
                    daily: pd.DataFrame | None = None,
                    goal_per_area: float | None = None,
                    today: date | None = None) -> list[AreaRow]:
    """``area_rows`` for a nightly metric — every area of the scope over the
    window, ranked by % of its own weekly goal where there is one.

    The window is measured in the WEEKS it covers, not in days, because that
    is the grain the goal has: an area's target is per week, so its goal over
    the window is that figure times the weeks it reported. An area that filed
    nothing is still a row, with ``reported`` False.
    """
    areas = sorted({str(a).strip() for a in scope_areas if str(a).strip()})
    if daily is None:
        from app.db.queries import get_daily_log
        daily = get_daily_log()
    # The raw frame as well as the bucketed one: the weeks come from the
    # buckets, but a missed NIGHT is only visible one row per night, and on a
    # nightly metric that count is the first thing a leader asks about.
    df = _load_daily(daily, areas)
    today = _today(today)
    start, end = window
    weeks = sundays_between(start, end)
    out: list[AreaRow] = []
    for area in areas:
        mine = (df[df["area"] == area] if not df.empty and "area" in df.columns
                else pd.DataFrame())
        actual = 0.0
        reported = 0
        for sunday in weeks:
            rows = _week_rows(mine, sunday)
            if not rows.empty:
                reported += 1
                actual += _sum(rows, metric)
        meta = (float(goal_per_area) * reported
                if goal_per_area and reported else None)
        change = None
        if twin_window is not None:
            t_actual, t_weeks = 0.0, 0
            for sunday in sundays_between(*twin_window):
                rows = _week_rows(mine, sunday)
                if not rows.empty:
                    t_weeks += 1
                    t_actual += _sum(rows, metric)
            if t_weeks:
                change = period_delta(actual, t_actual, current_basis=1,
                                      prior_basis=1, min_basis=1)
        out.append(AreaRow(
            area=area, actual=actual, meta=meta,
            pct=(actual / meta * 100.0) if meta else None,
            change=change, reported=reported > 0, weeks_reported=reported,
            nights_missed=_nights_missed(daily, area, start,
                                         min(end, today - timedelta(days=1))),
        ))
    out.sort(key=lambda r: (r.pct is None, -(r.pct or 0.0), -r.actual, r.area))
    return out


def leadership_total(scope_areas: Iterable[str], cycle: dict, metric: str, *,
                     totals: dict | None = None) -> float | None:
    """The leadership transfer goal for the scope and metric, or None."""
    if totals is None:
        from app.db.goals_queries import group_goal_totals
        totals = group_goal_totals(cycle["start"], set(scope_areas))
    value = float((totals or {}).get(metric, 0) or 0)
    return value if value > 0 else None


def leadership_weekly_mark(scope_areas: Iterable[str], cycle: dict, metric: str, *,
                           totals: dict | None = None) -> float | None:
    """The leadership transfer goal's weekly share for the mark on the weekly
    bars: the cycle total for the scope ÷ the cycle's real weeks. None when
    no goal is saved for the metric."""
    value = leadership_total(scope_areas, cycle, metric, totals=totals)
    if value is None:
        return None
    from app.analytics.transfer_year import weeks_in_cycle
    weeks = max(1.0, weeks_in_cycle(cycle["start"], cycle["end"]))
    return value / weeks
