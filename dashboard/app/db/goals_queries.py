"""Leadership's goals for a companionship, set once per TRANSFER CYCLE.

One tab, `AREA_TRANSFER_GOALS`, keyed by ``area`` + ``transfer_start``, holding
the mission's seven Key Indicators. It replaces two monthly tabs that never
existed on the live sheet — `MISSION_GOALS` and `AREA_MONTHLY_GOALS`, probed
2026-09-05 and absent, along with every function that read them. Nothing was
ever saved monthly, so nothing is stranded by the change.

Why a transfer and not a month
──────────────────────────────
The mission plans in six-week transfer cycles and reports in Monday-to-Sunday
weeks, and those two line up exactly: every `TRANSFER_SCHEDULE` start is a
Monday and every `WEEKLY_KI.Week_End_Date` is a Sunday, so a six-week cycle is
six whole weekly rows. A calendar month is neither — it cuts weeks in half, and
the monthly path this replaces needed `_weeks_in_month` and `_sundays_in_month`
estimates to paper over that. Those estimates are gone rather than ported.

Why keyed by the START DATE
───────────────────────────
`Transfer_Number` is a label with no enforced format — CCSM's live values read
"2026-4" through "2026-8" — and two functions in this app parsed it as an
integer until 2026-09-05 (see `queries.get_recent_transfer_dates`). A start date
is unambiguous, sorts correctly, and is what `transfer_window()` already
identifies a cycle by. The number rides along as a display label only, and
nothing keys on it.

Why the mission has no row of its own
─────────────────────────────────────
There was to be a second `MISSION_TRANSFER_GOALS` tab. It was dropped
(Zackary, 2026-09-05): the mission's figure for a cycle IS its areas' summed
goals — `group_goal_totals()` below — so a separate mission row would be a
second answer to one question, and reconciling the two would be permanent
busywork. One tab, one number.

APP_SETTINGS at the bottom of this file is a separate concern that happens to
share it, and is untouched by any of the above.

See PLAN-2026-09-05-backlog.md §7.2 and §7.10.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.db.sheets_client import overwrite_tab, read_tab
from app.utils.logger import get_logger
from app.i18n import t

_logger = get_logger("db.goals_queries")

_TAB = "AREA_TRANSFER_GOALS"

#: Columns that are not a metric. `transfer_number` is carried for display only.
_KEY_COLS = ["area", "transfer_start", "transfer_number"]
_TAIL_COLS = ["set_by", "notes"]


def _metric_cols() -> list[str]:
    """The tab's metric columns: one per Key Indicator, from the live catalogue.

    Read from `QUESTIONS_CONFIG` rather than written down. `AREA_MONTHLY_GOALS`
    once hardcoded Utah Provo's six — gate | date_metric | new_found | pew |
    renew | member_lessons — none of which CCSM collects, so every value a user
    typed went into a column for a metric that does not exist and every CCSM
    metric was dropped: the page reported "saved" and stored nothing. Taking the
    catalogue's own KI set is both correct and self-correcting when the form
    changes.

    Falls back to whatever the tab already holds if the catalogue is unreadable,
    so a transient sheet failure degrades to "can't add new columns" rather than
    to "rewrite the tab with none".
    """
    try:
        from app.config.metric_catalog import key_indicator_metrics
        keys = list(key_indicator_metrics())
        if keys:
            return keys
    except Exception:
        pass
    df = read_tab(_TAB, header_marker="transfer_start")
    if not df.empty:
        return [c for c in df.columns if c not in _KEY_COLS + _TAIL_COLS]
    return []


def _cols() -> list[str]:
    return _KEY_COLS + _metric_cols() + _TAIL_COLS


def _read() -> pd.DataFrame:
    df = read_tab(_TAB, header_marker="transfer_start")
    if df.empty or "transfer_start" not in df.columns:
        return pd.DataFrame(columns=_cols())
    return df


def _norm_start(transfer_start) -> str:
    """A cycle key as the tab stores it: a bare ISO date.

    Accepts a `date` or a string, and trims any time component a sheet round
    trip may have added — "2026-09-07 00:00:00" and `date(2026, 9, 7)` are the
    same cycle, and a lookup that treats them as different silently loses a
    saved goal.
    """
    if isinstance(transfer_start, date):
        return transfer_start.isoformat()
    return str(transfer_start or "").strip()[:10]


def _as_date(transfer_start) -> date | None:
    """`transfer_start` as a real date, or None if it will not parse."""
    try:
        return date.fromisoformat(_norm_start(transfer_start))
    except ValueError:
        return None


def _row_to_dict(row: pd.Series) -> dict:
    d = {col: int(float(row.get(col, 0) or 0)) for col in _metric_cols()}
    d["area"] = str(row.get("area", ""))
    d["transfer_start"] = _norm_start(row.get("transfer_start", ""))
    d["transfer_number"] = str(row.get("transfer_number", "") or "")
    d["set_by"] = str(row.get("set_by", "") or "")
    d["notes"] = str(row.get("notes", "") or "")
    return d


def _scoped(df: pd.DataFrame, areas=None) -> pd.DataFrame:
    """`df` cut to `areas` (case- and space-insensitive), or whole if None."""
    if areas is None or df.empty or "area" not in df.columns:
        return df
    wanted = {str(a).strip().lower() for a in areas}
    return df[df["area"].astype(str).str.strip().str.lower().isin(wanted)]


# ── reads ─────────────────────────────────────────────────────────────────────

def get_area_transfer_goals(transfer_start) -> pd.DataFrame:
    """Every area's goals for one cycle, metric columns coerced to numbers."""
    key = _norm_start(transfer_start)
    df = _read()
    if df.empty:
        return pd.DataFrame(columns=_cols())
    df = df[df["transfer_start"].astype(str).str.strip().str[:10] == key].copy()
    for c in _metric_cols():
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        else:
            df[c] = 0
    df["area"] = df["area"].astype(str).str.strip()
    return df


def get_area_transfer_goal(area: str, transfer_start) -> dict | None:
    """One area's goals for one cycle, or None if it has not set any."""
    key = _norm_start(transfer_start)
    try:
        df = _read()
        if df.empty:
            return None
        area_norm = str(area).strip().lower()
        match = df[
            (df["transfer_start"].astype(str).str.strip().str[:10] == key)
            & (df["area"].astype(str).str.strip().str.lower() == area_norm)
        ]
        if match.empty:
            return None
        return _row_to_dict(match.iloc[0])
    except Exception as e:
        _logger.error(t('Failed to fetch area transfer goal: {e}', e=e))
        return None


def group_goal_totals(transfer_start, areas=None) -> dict:
    """``{metric: summed goal}`` for one cycle across `areas` — the whole
    mission when `areas` is None.

    This is the mission's (or a zone's, or a district's) figure for the cycle.
    There is no separate mission row to read instead — see the module docstring.
    Areas that set no goal contribute nothing rather than a zero, which is the
    same thing arithmetically and is why every total this feeds is shown beside
    a count of how many areas are behind it.
    """
    df = _scoped(get_area_transfer_goals(transfer_start), areas)
    if df.empty:
        return {}
    return {c: float(df[c].sum()) for c in _metric_cols() if c in df.columns}


def goals_by_cycle_start(areas=None) -> dict:
    """``{cycle start date: {metric: summed goal}}`` across every saved cycle.

    Keyed by a real `date`, which is the shape `analytics.transfer_year`'s
    `year_goal_total()` takes, so the year summary hands one to the other with
    nothing in between. A row whose `transfer_start` will not parse is dropped:
    a goal that cannot be placed on a calendar cannot be pro-rated into a year.
    """
    df = _scoped(_read(), areas)
    if df.empty:
        return {}
    metrics = [c for c in _metric_cols() if c in df.columns]
    out: dict = {}
    for _, row in df.iterrows():
        start = _as_date(row.get("transfer_start", ""))
        if start is None:
            continue
        bucket = out.setdefault(start, {m: 0.0 for m in metrics})
        for m in metrics:
            try:
                bucket[m] += float(row.get(m, 0) or 0)
            except (TypeError, ValueError):
                continue
    return out


def cycles_with_goals(areas=None) -> set:
    """The cycle start dates that carry at least one non-zero goal.

    The numerator of the year summary's mandatory coverage caption ("4 de 8
    cambios tienen metas"). A cycle whose every saved value is zero does not
    count as planned — a row of zeros is what a stray save leaves behind, not a
    target anyone set.
    """
    return {start for start, metrics in goals_by_cycle_start(areas).items()
            if any(v for v in metrics.values())}


def areas_with_goals(transfer_start) -> int:
    """How many areas have a non-zero goal saved for this cycle.

    Shown beside any summed total, for the same reason `_ki_goal_note` exists on
    the Panel: a mission figure resting on six areas out of forty-three must not
    read the same as one every area signed up to.
    """
    df = get_area_transfer_goals(transfer_start)
    if df.empty:
        return 0
    metrics = [c for c in _metric_cols() if c in df.columns]
    if not metrics:
        return 0
    return int((df[metrics].sum(axis=1) > 0).sum())


# ── writes ────────────────────────────────────────────────────────────────────

def _write_rows(df: pd.DataFrame) -> None:
    cols = _cols()
    overwrite_tab(_TAB, [cols] + [
        [str(row.get(c, "") or "") for c in cols] for _, row in df.iterrows()
    ])


def _merge_row(df: pd.DataFrame, new_row: dict) -> pd.DataFrame:
    """Upsert `new_row` into `df` on (area, transfer_start)."""
    if df.empty or "transfer_start" not in df.columns or "area" not in df.columns:
        return pd.DataFrame([new_row])
    mask = (
        (df["transfer_start"].astype(str).str.strip().str[:10] == new_row["transfer_start"])
        & (df["area"].astype(str).str.strip().str.lower()
           == str(new_row["area"]).strip().lower())
    )
    if mask.any():
        for k, v in new_row.items():
            df.loc[mask, k] = v if isinstance(v, str) else str(v)
        return df
    str_row = {k: v if isinstance(v, str) else str(v) for k, v in new_row.items()}
    return pd.concat([df, pd.DataFrame([str_row])], ignore_index=True)


def _new_row(area: str, transfer_start, transfer_number: str,
             goals: dict, set_by: str, notes: str = "") -> dict:
    """One tab row. Unknown keys in `goals` are DROPPED, never written.

    The tab's columns come from the catalogue, and silently widening the schema
    from caller input is how a typo becomes a permanent column.
    """
    return {
        "area":            area,
        "transfer_start":  _norm_start(transfer_start),
        "transfer_number": str(transfer_number or ""),
        **{k: int(goals.get(k, 0) or 0) for k in _metric_cols()},
        "set_by":          set_by,
        "notes":           notes,
    }


def upsert_area_transfer_goal(
    area: str,
    transfer_start,
    goals: dict,
    set_by: str,
    transfer_number: str = "",
    notes: str = "",
) -> tuple[dict | None, str | None]:
    """Insert or update one area's goals for one cycle. Returns (row, None) or
    (None, error).

    `goals` is ``{metric_key: value}`` over the mission's Key Indicators. Its
    predecessor took six fixed keyword arguments named after Provo's KIs, so a
    caller passing CCSM's metrics could not reach the function at all — and the
    page calling it passed `gate=`/`date_metric=`/…, which evaluated to 0. "Save"
    reported success and stored nothing. `tests/test_area_transfer_goals.py`
    is the regression test for exactly that.
    """
    row = _new_row(area, transfer_start, transfer_number, goals, set_by, notes)
    try:
        _write_rows(_merge_row(_read(), row))
        return row, None
    except Exception as e:
        _logger.error(t('Failed to upsert area transfer goal: {e}', e=e))
        return None, str(e)


def bulk_upsert_area_transfer_goals(
    transfer_start,
    goals_by_area: dict,
    set_by: str,
    transfer_number: str = "",
) -> tuple[int, str | None]:
    """Upsert EVERY area in `goals_by_area` ({area: {metric_key: value}}) for one
    cycle in ONE `overwrite_tab` call — one Sheets write total, not one per area.

    Rows for other cycles, and for areas not named, are preserved as-is. With
    forty-plus areas this is the only realistic way to fill the tab; one write
    per area would trip the API quota.

    Returns (areas_written, None) or (0, error).
    """
    try:
        df = _read()
        for area, goals in goals_by_area.items():
            df = _merge_row(
                df, _new_row(area, transfer_start, transfer_number, goals, set_by))
        _write_rows(df)
        return len(goals_by_area), None
    except Exception as e:
        _logger.error(t('Failed to bulk upsert area transfer goals: {e}', e=e))
        return 0, str(e)


def delete_area_transfer_goal(area: str, transfer_start) -> str | None:
    """Remove one area's row for one cycle. None on success, an error string
    otherwise. Absent rows are not an error — the end state is what was asked
    for either way."""
    key = _norm_start(transfer_start)
    try:
        df = _read()
        if df.empty:
            return None
        keep = ~(
            (df["transfer_start"].astype(str).str.strip().str[:10] == key)
            & (df["area"].astype(str).str.strip().str.lower() == str(area).strip().lower())
        )
        _write_rows(df[keep])
        return None
    except Exception as e:
        _logger.error(t('Failed to delete area transfer goal: {e}', e=e))
        return str(e)


_SETTINGS_TAB = "APP_SETTINGS"
_SETTINGS_COLS = ["key", "value", "updated_by", "updated_at"]


def _read_settings() -> pd.DataFrame:
    df = read_tab(_SETTINGS_TAB, header_marker="key")
    if df.empty or "key" not in df.columns:
        return pd.DataFrame(columns=_SETTINGS_COLS)
    return df


def get_app_setting(key: str, default: str = "") -> str:
    """Return one APP_SETTINGS value by key, or `default` if unset. Streamlit-app
    only — a separate tab from AGENT_CONFIG, which live Apps Script agents read;
    nothing in docs/*.gs looks at APP_SETTINGS."""
    try:
        df = _read_settings()
        if df.empty:
            return default
        match = df[df["key"].astype(str).str.strip() == str(key).strip()]
        if match.empty:
            return default
        return str(match.iloc[0].get("value", default) or default)
    except Exception as e:
        _logger.error(t('Failed to read app setting {key!r}: {e}', key=key, e=e))
        return default


def set_app_setting(key: str, value: str, updated_by: str) -> str | None:
    """Insert or update one APP_SETTINGS key. Returns None on success, an error
    string on failure. Rewrites the whole (small) tab via overwrite_tab, same
    pattern as upsert_goal/upsert_area_monthly_goal."""
    from datetime import datetime as _dt

    new_row = {
        "key": str(key).strip(),
        "value": str(value),
        "updated_by": updated_by,
        "updated_at": _dt.now().isoformat(timespec="seconds"),
    }
    try:
        df = _read_settings()
        if not df.empty and "key" in df.columns:
            mask = df["key"].astype(str).str.strip() == new_row["key"]
            if mask.any():
                for k, v in new_row.items():
                    df.loc[mask, k] = v
            else:
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df = pd.DataFrame([new_row])

        rows = [_SETTINGS_COLS] + [
            [str(row.get(c, "") or "") for c in _SETTINGS_COLS]
            for _, row in df.iterrows()
        ]
        overwrite_tab(_SETTINGS_TAB, rows)
        return None
    except Exception as e:
        _logger.error(t('Failed to set app setting {key!r}: {e}', key=key, e=e))
        return str(e)
