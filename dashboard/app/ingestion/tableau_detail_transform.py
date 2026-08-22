"""Clean and prune a Tableau "Mission Finding Summary" Detail export before it
is written to the COMPASS_CCSM ``TABLEAU_DETAIL`` tab.

Pure functions only — no Streamlit, no gspread, no file IO — so the rules below
are unit-testable and can run identically from the Embudo upload path, a cloud
job, or a one-off backfill script.

Three jobs, each of which came out of checking a real 92,529-row export against
the app's own ``app/analytics/finding_funnel.py``:

1. **Drop the person's name.** The export carries ``Full Name`` and
   ``Person Id`` for every one of ~89,850 real investigators and converts,
   alongside the dates they were taught, attended church and were confirmed.
   The source PDFs are stamped "Confidential - For Church Use Only", and the
   sheet this lands in is readable by every account ``auth.py`` admits — which
   today is all ~97 companionship mailboxes, not just mission leadership. No
   page aggregates by name (``build_area_rankings`` groups by teaching area;
   every chart groups by date, zone or source), so dropping the identity
   columns costs the app nothing. Decision made by the mission's tech
   missionary, 2026-08-22.

   Consequence worth knowing: the Finding Records expander on
   ``07_Embudo_de_Búsqueda.py`` builds its table from whichever of its columns
   resolve, so with no name column present it simply renders without one.

2. **Drop Tableau's artifact rows.** The export interleaves subtotal/padding
   rows carrying a ``Person Id`` but no name, no event date and no zone. They
   are invisible in Tableau and meaningless here, but
   ``compute_funnel_stage_counts`` counts ``len(df)`` for its "Found" stage and
   ``build_area_rankings`` groups them into an ``Unknown`` area — which, left
   in, ranks first in the mission. Live: 2,679 such rows of 92,529.

3. **Prune to the columns the app reads.** ``save_dataframe`` writes the whole
   frame in a single ``ws.update`` call; the raw export is 24 columns over
   92,529 rows = 2,220,696 cells, which is inside the 10M-cell sheet cap but
   far past what one API call will carry. Keeping only what
   ``finding_funnel.py`` and the Embudo page actually resolve cuts that by
   roughly 40%.
"""

from __future__ import annotations

import pandas as pd

# ── The columns the app actually reads ────────────────────────────────────────
# Every entry here is resolved somewhere in app/analytics/finding_funnel.py or
# pages/07_Embudo_de_Búsqueda.py. Names are post-normalisation (see
# normalize_headers) and are matched by resolve_col()'s substring rule, so
# `latest_zone_name` satisfies a lookup for `latest_zone`.
GROUPING_COLUMNS = (
    "event_date_selected",
    "latest_zone_name",
    "latest_district_name",
    "latest_teaching_area_name",
    "finding_source",
    "finding_category_(copy)",
)

#: Milestone dates. The first seven drive the funnel stages and the per-area
#: rankings; `first_lesson_date` is read directly by the Embudo page.
MILESTONE_COLUMNS = (
    "first_referral_event_date",
    "first_contact_attempt_event_date",
    "first_successful_contact_attempt_event_date",
    "first_new_person_being_taught_date",
    "first_lesson_date",
    "first_sacrament_date",
    "first_baptism_goal_date_set",
    "confirmation_date",
)

KEEP_COLUMNS = GROUPING_COLUMNS + MILESTONE_COLUMNS

#: Identity columns, dropped on purpose — see the module docstring.
IDENTITY_COLUMNS = ("full_name", "person_id")

#: Columns present in the export that no page reads. Listed explicitly rather
#: than "everything not in KEEP_COLUMNS" so that a genuinely new column in a
#: future export shows up in `dropped_unknown` instead of vanishing quietly.
KNOWN_UNUSED_COLUMNS = (
    "sort",
    "first_finding_event_date_(truncated)",
    "first_finding_event_date",
    "second_lesson_date",
    "latest_sacrament_date",
    "sacrament_attendance_event_count",
    "latest_baptism_goal_date_set",
)

#: Tableau emits a concatenated "…_and_5_more_(combined)" column for whatever
#: fields the sheet groups on. Its name is a mashup of several real column
#: names, which is why resolve_col() explicitly skips it — and why it must be
#: recognised here rather than reported as a new field on every single export.
_COMBINED_SUFFIX = "(combined)"


def _is_known_unused(col: str) -> bool:
    return col in KNOWN_UNUSED_COLUMNS or col.endswith(_COMBINED_SUFFIX)

#: A row must have all of these to be a real person. Tableau's artifact rows
#: carry a Person Id and nothing else.
_REQUIRED = ("event_date_selected", "latest_zone_name")


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the header rule the Embudo uploader already uses, so a file loaded
    here and a file loaded through the page normalise identically.

    Returns a new frame; the input is not modified.
    """
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def _blank(series: pd.Series) -> pd.Series:
    """True where a cell is NaN, empty, or the string 'nan'.

    Excel and CSV round-trips disagree about which of those a missing cell
    becomes, so all three are treated the same.
    """
    s = series.astype(str).str.strip().str.lower()
    return series.isna() | s.eq("") | s.eq("nan")


def clean_detail(df: pd.DataFrame, *, drop_identity: bool = True) -> tuple[pd.DataFrame, dict]:
    """Return ``(clean_frame, stats)`` ready for ``TABLEAU_DETAIL``.

    ``drop_identity=False`` keeps ``full_name``/``person_id``. It exists so a
    caller can be explicit about wanting them (and so a test can prove the
    default does not); the mission's standing decision is to drop them, so no
    production caller should pass it.

    ``stats`` reports what happened, for the ingest log and the page caption:
    ``rows_in``, ``rows_out``, ``artifact_rows_dropped``, ``identity_dropped``,
    ``dropped_unknown`` (export columns nobody recognised), ``missing_expected``
    (columns the app wants that this export lacks), ``cells_in``, ``cells_out``.
    """
    df = normalize_headers(df)
    rows_in, cols_in = df.shape

    # 1. Artifact rows. Guard on the required columns that are actually present
    #    so a partial export still cleans rather than raising.
    present_required = [c for c in _REQUIRED if c in df.columns]
    if present_required:
        keep_mask = ~pd.concat([_blank(df[c]) for c in present_required], axis=1).any(axis=1)
        cleaned = df[keep_mask].copy()
    else:
        cleaned = df.copy()
    artifact_dropped = rows_in - len(cleaned)

    # 2. Prune columns, preserving KEEP_COLUMNS order so the sheet's layout is
    #    stable across refreshes.
    wanted = list(KEEP_COLUMNS)
    if not drop_identity:
        wanted += [c for c in IDENTITY_COLUMNS if c in cleaned.columns]

    keep = [c for c in wanted if c in cleaned.columns]
    missing_expected = [c for c in KEEP_COLUMNS if c not in cleaned.columns]
    recognised = set(KEEP_COLUMNS) | set(IDENTITY_COLUMNS)
    dropped_unknown = [
        c for c in cleaned.columns if c not in recognised and not _is_known_unused(c)
    ]

    out = cleaned[keep].reset_index(drop=True)

    stats = {
        "rows_in": rows_in,
        "rows_out": len(out),
        "artifact_rows_dropped": artifact_dropped,
        "identity_dropped": sorted(
            c for c in IDENTITY_COLUMNS if c in df.columns and c not in out.columns
        ),
        "dropped_unknown": dropped_unknown,
        "missing_expected": missing_expected,
        "cells_in": rows_in * cols_in,
        "cells_out": len(out) * len(out.columns),
    }
    return out, stats
