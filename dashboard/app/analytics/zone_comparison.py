"""Zones compared the only way that is fair: per area.

Zones in this mission run 8 to 13 areas, so a raw zone total ranks by size.
Live on 2026-08-20 the Panel showed Los Angeles Norte first on contact attempts
with 1,289 across 11 areas — 117 per area — above Angol's 1,266 across 8, which
is 158 per area and actually first. Audit finding C2.

The arithmetic lives here rather than in the page so it can be tested without a
Streamlit runtime or a mocked sheet, and so any other page that compares zones
divides by the same denominator.

Two rules this module exists to enforce:

  * The divisor is ALL of a zone's active areas, never the ones that reported.
    A zone whose areas go silent ranks lower, on purpose — the alternative
    lets four working areas out of eleven carry a zone to the top of the table
    with nothing on screen saying so.
  * A zone with no summary row at all is NaN, not 0. "Not written yet" and
    "did nothing this week" are different claims and must not render alike.
"""

import pandas as pd

#: Column name for the Effectiveness score in the returned frame. Deliberately
#: not a metric_key: Effectiveness comes from SCORES and describes a completed
#: WEEK, while every other column is a rolling 7-day nightly figure.
EFFECTIVENESS = "__effectiveness__"

#: Share of a mission's active areas that must carry a non-zero KI_Score before
#: Effectiveness is a sound thing to rank on. Its Key Indicator third is 0 for
#: any area whose week had no goals to score against, and a week's KI goals are
#: written on the PREVIOUS week's form — so early in a mission's history nearly
#: every area scores 0 there and Effectiveness silently ranks on two thirds of
#: itself. Live on 2026-08-21: 1 area of 43.
DEFAULT_KI_MIN_SHARE = 0.5


def active_areas_by_zone(areas_df: pd.DataFrame) -> dict:
    """Zone name -> count of active teaching areas, from MISSION_ORG.

    Pass get_submitting_areas() — leadership rows are already dropped there,
    and they must be, or a zone's divisor counts companionships that never
    submit a nightly form.
    """
    if areas_df is None or areas_df.empty or "Zone" not in areas_df.columns:
        return {}
    counts = areas_df["Zone"].astype(str).str.strip().value_counts()
    return {
        str(zone): int(n) for zone, n in counts.items()
        if str(zone) and str(zone).upper() not in ("ALL", "NAN")
    }


def _zone_metric_totals(zone_df: pd.DataFrame, value_col: str) -> dict:
    """Zone name -> {metric_key: total} from DASHBOARD_SUMMARY's ZONE rows."""
    if (zone_df is None or zone_df.empty
            or not {"zone", "metric_key"} <= set(zone_df.columns)):
        return {}
    out: dict = {}
    for zone, grp in zone_df.groupby(zone_df["zone"].astype(str).str.strip()):
        out[str(zone)] = {
            str(r["metric_key"]): float(r.get(value_col, 0) or 0)
            for _, r in grp.iterrows()
        }
    return out


def _zone_effectiveness_totals(scores_df: pd.DataFrame) -> dict:
    """Zone name -> summed Effectiveness_Score for one week's SCORES rows.

    Summed, not averaged: the caller divides by the active area count, so an
    area the scoring agent never wrote a row for counts as a zero exactly like
    an area that reported nothing. Averaging over present rows instead would
    quietly hand a zone with missing rows a higher score.
    """
    if (scores_df is None or scores_df.empty
            or "Zone" not in scores_df.columns
            or "Effectiveness_Score" not in scores_df.columns):
        return {}
    zones = scores_df["Zone"].astype(str).str.strip()
    totals = pd.to_numeric(
        scores_df["Effectiveness_Score"], errors="coerce"
    ).fillna(0).groupby(zones).sum()
    return {str(z): float(v) for z, v in totals.items()}


def ki_scored_area_count(scores_df: pd.DataFrame) -> int:
    """How many areas in this week's SCORES actually carry a KI_Score."""
    if (scores_df is None or scores_df.empty
            or "KI_Score" not in scores_df.columns):
        return 0
    ki = pd.to_numeric(scores_df["KI_Score"], errors="coerce").fillna(0)
    return int((ki > 0).sum())


def effectiveness_is_rankable(
    scores_df: pd.DataFrame,
    active_areas: int,
    min_share: float = DEFAULT_KI_MIN_SHARE,
) -> bool:
    """Is the Effectiveness score whole enough to lead a ranking?

    False while its KI third is missing for most of the mission — see
    DEFAULT_KI_MIN_SHARE. The caller falls back to a metric that is complete
    today and says why, rather than ranking zones on a partial composite
    without telling anyone.
    """
    if not active_areas or scores_df is None or scores_df.empty:
        return False
    return ki_scored_area_count(scores_df) >= active_areas * min_share


def zone_comparison_table(
    zone_df: pd.DataFrame,
    areas_df: pd.DataFrame,
    metric_keys: list,
    scores_df: pd.DataFrame = None,
    per_area: bool = True,
    value_col: str = "val_7d",
) -> pd.DataFrame:
    """One row per zone: ``zone``, ``areas``, one column per metric key, and
    ``EFFECTIVENESS`` when ``scores_df`` is given.

    ``per_area=True`` (the default, and the reading the page opens on) divides
    each metric by the zone's active area count. ``per_area=False`` returns the
    zone's raw total — the reading a president sometimes wants for a sense of
    absolute volume, and the one that ranks by zone size, which is why it is
    never the default and why the Areas column is shown in both modes.

    **Effectiveness ignores the switch and is always a per-area average.** It is
    a 0-100 score, not a count: summing it produces a number like 388 that means
    nothing, and would re-introduce the size bias into the one column that is
    supposed to be size-neutral.

    Values are floats, unsorted and unformatted — ranking and locale formatting
    belong to the caller. A metric the zone has no row for is NaN, not 0 (see
    the module docstring).
    """
    counts  = active_areas_by_zone(areas_df)
    totals  = _zone_metric_totals(zone_df, value_col)
    effect  = _zone_effectiveness_totals(scores_df)
    with_eff = scores_df is not None and not getattr(scores_df, "empty", True)

    rows = []
    for zone, n_areas in counts.items():
        if not n_areas:
            continue
        zone_totals = totals.get(zone)
        row = {"zone": zone, "areas": n_areas}
        for key in metric_keys:
            if zone_totals is None:
                row[key] = float("nan")
                continue
            total = float(zone_totals.get(key, 0.0))
            row[key] = total / n_areas if per_area else total
        if with_eff:
            row[EFFECTIVENESS] = (float(effect[zone]) / n_areas
                                  if zone in effect else float("nan"))
        rows.append(row)

    cols = ["zone", "areas"] + list(metric_keys) + ([EFFECTIVENESS] if with_eff else [])
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)[cols]


def mission_summary_row(
    zone_df: pd.DataFrame,
    areas_df: pd.DataFrame,
    metric_keys: list,
    scores_df: pd.DataFrame = None,
    per_area: bool = True,
    value_col: str = "val_7d",
) -> dict:
    """The whole mission as one row, in the same shape a zone row has.

    Recomputed from the raw totals rather than aggregated from
    ``zone_comparison_table``'s output, so a per-area reading is not an average
    of averages — that would weight an 8-area zone equally with a 13-area one.

    ``per_area`` follows the caller's switch for the counts. Effectiveness
    ignores it and stays a per-area average in both modes, for the same reason
    it does per zone: it is a 0-100 score, not a count.

    A zone with no summary row is left out of BOTH sides of that column's
    division, and ``areas`` reports the divisor actually used. Counting its
    areas in the denominator would charge the mission for an agent that has not
    written yet — the module's "not written" vs "did nothing" rule, applied one
    level up.
    """
    counts = active_areas_by_zone(areas_df)
    totals = _zone_metric_totals(zone_df, value_col)
    effect = _zone_effectiveness_totals(scores_df)
    with_eff = scores_df is not None and not getattr(scores_df, "empty", True)

    present = [z for z, n in counts.items() if n and z in totals]
    divisor = sum(counts[z] for z in present)

    row = {"zone": "", "areas": divisor}
    for key in metric_keys:
        if not divisor:
            row[key] = float("nan")
            continue
        total = sum(float(totals[z].get(key, 0.0)) for z in present)
        row[key] = total / divisor if per_area else total
    if with_eff:
        scored = [z for z, n in counts.items() if n and z in effect]
        eff_div = sum(counts[z] for z in scored)
        row[EFFECTIVENESS] = (
            sum(float(effect[z]) for z in scored) / eff_div
            if eff_div else float("nan")
        )
    return row


# ── The seven Key Indicators, per zone ────────────────────────────────────────
# Data-pages plan §4 step C3, decision 7: the zone comparison is the seven Key
# Indicators, not the nightly funnel. The funnel stays above, behind a toggle,
# because it answers a different question (how much finding work) from the one
# the mission is judged on (what came of it).
#
# Everything the module's two rules say about the funnel applies here unchanged:
# the divisor is every ACTIVE area, never the ones that reported, and a zone
# with nothing written is NaN rather than 0.

def _area_zone_map(areas_df: pd.DataFrame) -> dict:
    """``{area name: zone}`` from MISSION_ORG.

    Membership comes from the roster, never from the weekly frame's own zone
    column: the form's zone is whichever section a companionship filed under,
    and an area that moved between zones mid-cycle would be counted in both.
    """
    if (areas_df is None or areas_df.empty
            or not {"Area_Name", "Zone"} <= set(areas_df.columns)):
        return {}
    return {
        str(r["Area_Name"]).strip(): str(r["Zone"]).strip()
        for _, r in areas_df.iterrows()
        if str(r.get("Area_Name", "")).strip()
    }


def _week_rows(weekly_df: pd.DataFrame, week_end) -> pd.DataFrame:
    if weekly_df is None or weekly_df.empty or "week_end_date" not in weekly_df.columns:
        return pd.DataFrame()
    key = str(week_end)[:10]
    rows = weekly_df[weekly_df["week_end_date"].astype(str).str[:10] == key]
    return rows.copy() if not rows.empty else pd.DataFrame()


def zone_ki_table(
    weekly_df: pd.DataFrame,
    areas_df: pd.DataFrame,
    metric_keys: list,
    week_end,
    per_area: bool = True,
) -> pd.DataFrame:
    """One row per zone for ONE reporting week: ``zone``, ``areas``,
    ``reporting``, and one column per Key Indicator.

    ``weekly_df`` is ``queries.get_weekly_form_data()`` — tidy rows of
    week_end_date | area | zone | metrics. ``areas_df`` is
    ``get_submitting_areas()``, which is what says how many areas a zone HAS.

    ``per_area=True`` divides each indicator by the zone's active area count,
    including the areas that did not file. That is the only fair reading — these
    zones run 8 to 13 areas — and it is why ``reporting`` is returned beside it:
    a zone at 6 of 13 is not having a bad week so much as a quiet one, and the
    caller must be able to say so.

    Values are floats, unsorted and unformatted. A zone no area filed for is
    NaN, not 0.
    """
    counts = active_areas_by_zone(areas_df)
    zone_of = _area_zone_map(areas_df)
    rows_this_week = _week_rows(weekly_df, week_end)

    totals: dict = {}
    reporting: dict = {}
    if not rows_this_week.empty and "area" in rows_this_week.columns:
        rows_this_week["__zone"] = (rows_this_week["area"].astype(str).str.strip()
                                    .map(zone_of))
        known = rows_this_week[rows_this_week["__zone"].notna()]
        for zone, grp in known.groupby("__zone"):
            totals[str(zone)] = {
                key: float(pd.to_numeric(grp[key], errors="coerce").fillna(0).sum())
                for key in metric_keys if key in grp.columns
            }
            reporting[str(zone)] = int(grp["area"].nunique())

    out = []
    for zone, n_areas in counts.items():
        if not n_areas:
            continue
        zone_totals = totals.get(zone)
        row = {"zone": zone, "areas": n_areas,
               "reporting": int(reporting.get(zone, 0))}
        for key in metric_keys:
            if zone_totals is None:
                row[key] = float("nan")
                continue
            total = float(zone_totals.get(key, 0.0))
            row[key] = total / n_areas if per_area else total
        out.append(row)

    cols = ["zone", "areas", "reporting"] + list(metric_keys)
    if not out:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(out)[cols]


def zone_ki_mission_row(
    weekly_df: pd.DataFrame,
    areas_df: pd.DataFrame,
    metric_keys: list,
    week_end,
    per_area: bool = True,
) -> dict:
    """The whole mission as one row, in the shape ``zone_ki_table`` returns.

    Recomputed from the raw totals rather than averaged over the zone rows: an
    average of four zone averages weights an 8-area zone the same as a 13-area
    one, so it would not equal the mission's own per-area figure. Same rule, and
    same reason, as ``mission_summary_row``.

    Unlike the funnel's version this counts EVERY active area in the divisor,
    including a zone none of whose areas filed. The weekly form is a per-area
    submission, so an absent area is an area that did not report — there is no
    "the agent has not written this zone's row yet" case to protect against.
    """
    counts = active_areas_by_zone(areas_df)
    zone_of = _area_zone_map(areas_df)
    rows_this_week = _week_rows(weekly_df, week_end)
    divisor = sum(n for n in counts.values() if n)

    row = {"zone": "", "areas": divisor, "reporting": 0}
    mine = pd.DataFrame()
    if not rows_this_week.empty and "area" in rows_this_week.columns:
        names = rows_this_week["area"].astype(str).str.strip()
        mine = rows_this_week[names.isin(zone_of)]
        row["reporting"] = int(mine["area"].nunique()) if not mine.empty else 0

    for key in metric_keys:
        if not divisor or mine.empty or key not in mine.columns:
            row[key] = float("nan")
            continue
        total = float(pd.to_numeric(mine[key], errors="coerce").fillna(0).sum())
        row[key] = total / divisor if per_area else total
    return row
