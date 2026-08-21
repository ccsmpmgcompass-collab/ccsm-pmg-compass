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


def zone_per_area_table(
    zone_df: pd.DataFrame,
    areas_df: pd.DataFrame,
    metric_keys: list,
    scores_df: pd.DataFrame = None,
    value_col: str = "val_7d",
) -> pd.DataFrame:
    """One row per zone, every metric divided by the zone's active area count.

    Columns: ``zone``, ``areas``, one per entry in ``metric_keys``, and
    ``EFFECTIVENESS`` when ``scores_df`` is given. Values are floats, unsorted
    and unformatted — ranking and locale formatting belong to the caller.

    A metric the zone has no row for is NaN, not 0 (see the module docstring).
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
            row[key] = (float(zone_totals.get(key, 0.0)) / n_areas
                        if zone_totals is not None else float("nan"))
        if with_eff:
            row[EFFECTIVENESS] = (float(effect[zone]) / n_areas
                                  if zone in effect else float("nan"))
        rows.append(row)

    cols = ["zone", "areas"] + list(metric_keys) + ([EFFECTIVENESS] if with_eff else [])
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)[cols]
