from __future__ import annotations

import json
from datetime import date

import pandas as pd

from app.db.sheets_client import overwrite_tab, read_tab
from app.utils.logger import get_logger
from app.i18n import t

_logger = get_logger("db.goals_queries")

_TAB = "MISSION_GOALS"
_COLS = [
    "month_start", "baptisms", "confirmations", "on_date", "at_sacrament",
    "new_people_to_teach", "rc_at_church", "members_nonmember_lessons",
    "extra_goals", "set_by", "notes",
]
_INT_COLS = [
    "baptisms", "confirmations", "on_date", "at_sacrament",
    "new_people_to_teach", "rc_at_church", "members_nonmember_lessons",
]


def current_month_start() -> str:
    """First-of-the-month ISO date for the current calendar month, e.g. '2026-07-01'."""
    return date.today().replace(day=1).isoformat()


def _read_goals() -> pd.DataFrame:
    df = read_tab(_TAB, header_marker="month_start")
    if df.empty or "month_start" not in df.columns:
        return pd.DataFrame(columns=_COLS)
    return df


def _row_to_dict(row: pd.Series) -> dict:
    d = {}
    for col in _INT_COLS:
        d[col] = int(float(row.get(col, 0) or 0))
    raw_extra = row.get("extra_goals", "") or ""
    try:
        d["extra_goals"] = json.loads(raw_extra) if raw_extra else {}
    except (json.JSONDecodeError, TypeError):
        d["extra_goals"] = {}
    d["month_start"] = str(row.get("month_start", ""))
    d["set_by"] = str(row.get("set_by", "") or "")
    d["notes"] = str(row.get("notes", "") or "")
    return d


def get_current_goal(month_start: str | None = None) -> dict | None:
    """Return the goal row for the given month_start (defaults to the current calendar month)."""
    if month_start is None:
        month_start = current_month_start()
    try:
        df = _read_goals()
        if df.empty:
            return None
        match = df[df["month_start"].astype(str) == month_start]
        if match.empty:
            return None
        return _row_to_dict(match.iloc[0])
    except Exception as e:
        _logger.error(t('Failed to fetch goal: {e}', e=e))
        return None


def get_goal_history(limit: int = 12) -> list[dict]:
    """Return the last N months of goals, newest first."""
    try:
        df = _read_goals()
        if df.empty:
            return []
        df = df.sort_values("month_start", ascending=False).head(limit)
        return [_row_to_dict(row) for _, row in df.iterrows()]
    except Exception as e:
        _logger.error(t('Failed to fetch goal history: {e}', e=e))
        return []


def upsert_goal(
    month_start: str,
    baptisms: int,
    confirmations: int,
    on_date: int,
    at_sacrament: int,
    new_people_to_teach: int,
    rc_at_church: int,
    members_nonmember_lessons: int,
    extra_goals: dict,
    set_by: str,
    notes: str = "",
) -> tuple[dict | None, str | None]:
    """Insert or update a mission goal for the given month. Returns (row, None) or (None, error)."""
    clean_extra = {k: v for k, v in (extra_goals or {}).items() if v}
    new_row = {
        "month_start":               month_start,
        "baptisms":                  baptisms,
        "confirmations":             confirmations,
        "on_date":                   on_date,
        "at_sacrament":              at_sacrament,
        "new_people_to_teach":       new_people_to_teach,
        "rc_at_church":              rc_at_church,
        "members_nonmember_lessons": members_nonmember_lessons,
        "extra_goals":               json.dumps(clean_extra),
        "set_by":                    set_by,
        "notes":                     notes,
    }
    try:
        df = _read_goals()
        if not df.empty and "month_start" in df.columns:
            mask = df["month_start"].astype(str) == month_start
            if mask.any():
                for k, v in new_row.items():
                    df.loc[mask, k] = str(v) if not isinstance(v, str) else v
            else:
                str_row = {k: str(v) if not isinstance(v, str) else v for k, v in new_row.items()}
                df = pd.concat([df, pd.DataFrame([str_row])], ignore_index=True)
        else:
            df = pd.DataFrame([new_row])

        rows = [_COLS] + [
            [str(row.get(c, "") or "") for c in _COLS]
            for _, row in df.iterrows()
        ]
        overwrite_tab(_TAB, rows)

        result = dict(new_row)
        result["extra_goals"] = clean_extra
        return result, None
    except Exception as e:
        _logger.error(t('Failed to upsert goal: {e}', e=e))
        return None, str(e)


def get_mission_goals_for_display(month_start: str | None = None) -> dict:
    """
    Return {metric_key: int} merging all 7 featured columns + non-zero extra_goals.
    Returns {} if no goal row exists yet.
    """
    row = get_current_goal(month_start)
    if not row:
        return {}
    result = {col: int(row.get(col, 0) or 0) for col in _INT_COLS}
    extra = row.get("extra_goals") or {}
    result.update({k: int(v or 0) for k, v in extra.items() if v})
    return result


_AREA_TAB = "AREA_MONTHLY_GOALS"


def _area_int_cols() -> list[str]:
    """The metric columns of AREA_MONTHLY_GOALS: one per Key Indicator.

    Was a fixed ["gate", "date_metric", "new_found", "pew", "renew",
    "member_lessons"] — Utah Provo's six KIs. Since the Goals page offers
    CCSM's seven, every value a user typed was written into a column for a
    metric that does not exist and every CCSM metric was silently dropped:
    the page reported "saved" and stored nothing.

    Falls back to whatever the tab already holds if the catalogue is
    unreadable, so a transient sheet failure degrades to "can't add new
    columns" rather than to "rewrite the tab with none".
    """
    try:
        from app.config.metric_catalog import key_indicator_metrics
        keys = list(key_indicator_metrics())
        if keys:
            return keys
    except Exception:
        pass
    df = read_tab(_AREA_TAB, header_marker="month_start")
    if not df.empty:
        return [c for c in df.columns
                if c not in ("area", "month_start", "set_by", "notes")]
    return []


def _area_cols() -> list[str]:
    return ["area", "month_start"] + _area_int_cols() + ["set_by", "notes"]


def _read_area_goals() -> pd.DataFrame:
    df = read_tab(_AREA_TAB, header_marker="month_start")
    if df.empty or "month_start" not in df.columns:
        return pd.DataFrame(columns=_area_cols())
    return df


def _area_row_to_dict(row: pd.Series) -> dict:
    d = {}
    for col in _area_int_cols():
        d[col] = int(float(row.get(col, 0) or 0))
    d["area"] = str(row.get("area", ""))
    d["month_start"] = str(row.get("month_start", ""))
    d["set_by"] = str(row.get("set_by", "") or "")
    d["notes"] = str(row.get("notes", "") or "")
    return d


def get_area_monthly_goals(month_start: str | None = None) -> pd.DataFrame:
    """All areas' Monthly Goals rows for month_start (defaults to the current
    calendar month), numeric columns coerced. Used by the MLC packet rollup
    (app/analytics/mlc_rollups.py) to source the monthly-cadence baptism goal
    instead of GOALS_CONFIG's weekly figure — see build_monthly_goals()
    there for why the two cadences can't be mixed."""
    month_start = month_start or current_month_start()
    df = _read_area_goals()
    if df.empty:
        return pd.DataFrame(columns=_area_cols())
    df = df[df["month_start"].astype(str) == month_start].copy()
    for c in _area_int_cols():
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["area"] = df["area"].astype(str).str.strip()
    return df


def get_current_area_monthly_goal(area: str, month_start: str | None = None) -> dict | None:
    """Return this area's Monthly Goals row (Gate/Date/New/Pew/Renew/Mate) for
    the given month_start (defaults to the current calendar month). Separate
    tab from GOALS_CONFIG — AgentScores.gs's weekly scoring never reads this."""
    if month_start is None:
        month_start = current_month_start()
    try:
        df = _read_area_goals()
        if df.empty:
            return None
        area_norm = str(area).strip().lower()
        match = df[
            (df["month_start"].astype(str) == month_start)
            & (df["area"].astype(str).str.strip().str.lower() == area_norm)
        ]
        if match.empty:
            return None
        return _area_row_to_dict(match.iloc[0])
    except Exception as e:
        _logger.error(t('Failed to fetch area monthly goal: {e}', e=e))
        return None


def upsert_area_monthly_goal(
    area: str,
    month_start: str,
    goals: dict,
    set_by: str,
    notes: str = "",
) -> tuple[dict | None, str | None]:
    """Insert or update one area's Monthly Goals for the given month.

    `goals` is {metric_key: value} over the mission's Key Indicators. This used
    to be six fixed keyword arguments named after Provo's KIs, so a caller
    passing CCSM's metrics could not reach the function at all — and the page
    that called it passed gate=/date_metric=/… which now evaluate to 0, so
    "Save" reported success and stored nothing.

    Unknown keys are dropped rather than written: the tab's columns come from
    the catalogue, and silently widening the schema from caller input is how a
    typo becomes a permanent column.

    Returns (row, None) or (None, error).
    """
    metric_cols = _area_int_cols()
    area_cols = _area_cols()
    new_row = {
        "area":        area,
        "month_start": month_start,
        **{k: int(goals.get(k, 0) or 0) for k in metric_cols},
        "set_by":      set_by,
        "notes":       notes,
    }
    try:
        df = _read_area_goals()
        area_norm = str(area).strip().lower()
        if not df.empty and "month_start" in df.columns and "area" in df.columns:
            mask = (
                (df["month_start"].astype(str) == month_start)
                & (df["area"].astype(str).str.strip().str.lower() == area_norm)
            )
            if mask.any():
                for k, v in new_row.items():
                    df.loc[mask, k] = str(v) if not isinstance(v, str) else v
            else:
                str_row = {k: str(v) if not isinstance(v, str) else v for k, v in new_row.items()}
                df = pd.concat([df, pd.DataFrame([str_row])], ignore_index=True)
        else:
            df = pd.DataFrame([new_row])

        rows = [area_cols] + [
            [str(row.get(c, "") or "") for c in area_cols]
            for _, row in df.iterrows()
        ]
        overwrite_tab(_AREA_TAB, rows)

        return dict(new_row), None
    except Exception as e:
        _logger.error(t('Failed to upsert area monthly goal: {e}', e=e))
        return None, str(e)


def bulk_upsert_area_monthly_goals(
    month_start: str,
    goals_by_area: dict,
    set_by: str,
) -> tuple[int, str | None]:
    """Bulk counterpart to upsert_area_monthly_goal: upsert EVERY area in
    `goals_by_area` ({area: {metric_key: value}}) for the given month in ONE
    overwrite_tab call — one Sheets API write total, not one per area. Rows for
    other months (and for areas not in `goals_by_area`) are preserved as-is.

    Metric columns come from the catalogue, same as the single-area path; the
    old fixed six were Provo's KIs, so this wrote zeros for every area.

    Returns (areas_written, None) or (0, error)."""
    try:
        df = _read_area_goals()
        metric_cols = _area_int_cols()
        area_cols = _area_cols()
        for area, goals in goals_by_area.items():
            new_row = {
                "area":        area,
                "month_start": month_start,
                **{k: int(goals.get(k, 0) or 0) for k in metric_cols},
                "set_by":      set_by,
                "notes":       "",
            }
            area_norm = str(area).strip().lower()
            if not df.empty and "month_start" in df.columns and "area" in df.columns:
                mask = (
                    (df["month_start"].astype(str) == month_start)
                    & (df["area"].astype(str).str.strip().str.lower() == area_norm)
                )
                if mask.any():
                    for k, v in new_row.items():
                        df.loc[mask, k] = str(v) if not isinstance(v, str) else v
                else:
                    str_row = {k: str(v) if not isinstance(v, str) else v for k, v in new_row.items()}
                    df = pd.concat([df, pd.DataFrame([str_row])], ignore_index=True)
            else:
                df = pd.DataFrame([new_row])

        rows = [area_cols] + [
            [str(row.get(c, "") or "") for c in area_cols]
            for _, row in df.iterrows()
        ]
        overwrite_tab(_AREA_TAB, rows)
        return len(goals_by_area), None
    except Exception as e:
        _logger.error(t('Failed to bulk upsert area monthly goals: {e}', e=e))
        return 0, str(e)


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
