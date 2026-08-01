"""
19_Editar_Envíos.py
────────────────────────────────────────────────────────────────────────────────
Correct a report a companionship already submitted.

Edits DAILY_LOG (nightly) and WEEKLY_KI (weekly) — the normalised stores, NOT
the Google Forms response sheets. See app/db/submissions_queries for why: the
agents re-read a raw form row only for an Area|Date they have not already
processed, so a raw-sheet edit is never picked up.

Leadership only, and every save is written to AUDIT_LOG with the editor's
address.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.auth.auth import is_leadership, require_auth
from app.components.design_system import (
    inject_global_css, render_page_header, render_section_label, render_sidebar,
    render_table,
)
from app.config.flavor_loader import METRIC_LABELS, flavor
from app.config.metric_catalog import format_metric_label, metric_data_type
from app.db.queries import get_areas_df, get_config_value
from app.db.submissions_queries import (
    get_nightly_submission, get_weekly_submission, nightly_dates_for_area,
    nightly_metric_columns, save_nightly_submission, save_weekly_submission,
    weekly_metric_columns, weekly_weeks_for_area, clear_caches,
)
from app.i18n import t
from app.i18n.formats import fmt_date

st.set_page_config(
    page_title="CCSM · Editar Envíos — PMG Compass",
    page_icon="",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

_email = user.get("email", "")

if not is_leadership(_email):
    render_page_header(t("Edit Submissions"),
                       get_config_value("MISSION_NAME", flavor.display_name))
    st.info(t("This page is available to mission leadership only."))
    st.stop()

render_page_header(
    t("Edit Submissions"),
    t("Correct a report a companionship already submitted"),
)

st.caption(
    t("Corrections are written to DAILY_LOG and WEEKLY_KI — the tabs the "
      "dashboard and the agents both read — not to the Google Forms response "
      "sheets, which the agents do not re-read. Every change is recorded in "
      "AUDIT_LOG with your address.")
)

# ── Choose what to correct ────────────────────────────────────────────────────

_FORM_NIGHTLY = t("Nightly report")
_FORM_WEEKLY = t("Weekly report (Key Indicators)")

_form = st.radio(t("Which report"), [_FORM_NIGHTLY, _FORM_WEEKLY],
                 horizontal=True, key="es_form")
_is_nightly = _form == _FORM_NIGHTLY

_areas_df = get_areas_df()
_area_names = (
    sorted(_areas_df["Area_Name"].dropna().astype(str).unique().tolist())
    if not _areas_df.empty and "Area_Name" in _areas_df.columns else []
)

if not _area_names:
    st.warning(t("No active areas found in MISSION_ORG."))
    st.stop()

_c1, _c2 = st.columns(2)
with _c1:
    _area = st.selectbox(t("Area"), _area_names, key="es_area")

_keys = nightly_dates_for_area(_area) if _is_nightly else weekly_weeks_for_area(_area)
_columns = nightly_metric_columns() if _is_nightly else weekly_metric_columns()

# An empty catalogue means the tab has no header yet — the agents create it on
# their first successful run. Say so plainly instead of rendering an editor
# whose Save can only fail.
if not _columns:
    st.warning(
        t("{tab} has no columns yet, so there is nothing to correct. The "
          "agents create it on their first successful run — check Agent Runs "
          "on the Mantenimiento page.",
          tab="DAILY_LOG" if _is_nightly else "WEEKLY_KI")
    )
    st.stop()

_BACKFILL = t("— a date not reported (backfill) —")

with _c2:
    _options = list(_keys) + [_BACKFILL]
    _picked = st.selectbox(
        t("Date") if _is_nightly else t("Week ending"),
        _options,
        format_func=lambda v: v if v == _BACKFILL else fmt_date(v),
        key="es_key",
    )

_backfilling = _picked == _BACKFILL
_key_val = ""

if _backfilling:
    st.warning(
        t("Backfilling creates a row that was never submitted. The nightly "
          "agent skips any date already present, so once this is saved the "
          "companionship's own late submission for that date will NOT replace "
          "it. Only use this when the report will never arrive.")
    )
    _d = st.date_input(t("Date to create"), key="es_backfill_date")
    _key_val = _d.isoformat() if _d else ""
    _current = {}
else:
    _key_val = _picked or ""
    _current = (get_nightly_submission(_area, _key_val) if _is_nightly
                else get_weekly_submission(_area, _key_val)) or {}

if not _key_val:
    st.info(t("Pick a date to continue."))
    st.stop()

if not _backfilling and not _current:
    st.info(t("No report found for {area} on {date}.",
              area=_area, date=fmt_date(_key_val)))
    st.stop()

# ── The editor ────────────────────────────────────────────────────────────────

if _current:
    render_section_label(
        t("Currently recorded — {area}, {date}",
          area=_area, date=fmt_date(_key_val))
    )
    _identity = [(k, _current.get(k, "")) for k in ("Zone", "District")
                 if _current.get(k)]
    if _identity:
        st.caption(" · ".join(f"{k}: {v}" for k, v in _identity))

render_section_label(t("New values"))
st.caption(
    t("Only the fields you change are written. Everything left alone keeps "
      "the value the companionship reported.")
)


def _label(col: str) -> str:
    """The metric's own display name, falling back to the raw column for
    anything the catalogue does not define (an agent-written column that is not
    a form question)."""
    return METRIC_LABELS.get(col, format_metric_label(col))


#: Options for CCSM's CHOICE questions, verbatim from the Spanish nightly form.
#: A CHOICE answer must be picked, never typed as a number — number_input would
#: coerce "Todo" to 0, which reads as no effort at all.
_CHOICE_OPTIONS = {
    "effort": ["", "Todo", "La mayor parte", "Algo"],
}
_YESNO_OPTIONS = ["", "Sí", "No"]

_edited: dict[str, object] = {}
_COLS_PER_ROW = 3
_cols = st.columns(_COLS_PER_ROW)

for _i, _col in enumerate(_columns):
    _slot = _cols[_i % _COLS_PER_ROW]
    _now = str(_current.get(_col, "") or "")
    _dtype = metric_data_type(_col)
    _wkey = f"es_{_area}_{_key_val}_{_col}"

    with _slot:
        if _dtype == "CHOICE" or _col in _CHOICE_OPTIONS:
            _opts = _CHOICE_OPTIONS.get(_col, ["", _now] if _now else [""])
            if _now and _now not in _opts:
                _opts = _opts + [_now]
            _new = st.selectbox(_label(_col), _opts,
                                index=_opts.index(_now) if _now in _opts else 0,
                                key=_wkey)
        elif _dtype == "YESNO":
            _opts = list(_YESNO_OPTIONS)
            if _now and _now not in _opts:
                _opts = _opts + [_now]
            _new = st.selectbox(_label(_col), _opts,
                                index=_opts.index(_now) if _now in _opts else 0,
                                key=_wkey)
        else:
            try:
                _start = int(float(_now)) if _now not in ("", "nan") else 0
            except (TypeError, ValueError):
                _start = 0
            _new = st.number_input(_label(_col), min_value=0, step=1,
                                   value=_start, key=_wkey)

    # Compare as text so 40 and "40" don't register as a change — an edit that
    # rewrites every field on every save would fill AUDIT_LOG with noise and
    # make a real correction impossible to find.
    if str(_new) != _now:
        _edited[_col] = _new

if _edited:
    st.caption(
        t("{count} field(s) changed: {fields}",
          count=len(_edited),
          fields=", ".join(_label(k) for k in sorted(_edited)))
    )
else:
    st.caption(t("No changes yet."))

_save_label = t("Create this report") if _backfilling else t("Save correction")

if st.button(_save_label, type="primary", disabled=not _edited, key="es_save"):
    _fn = save_nightly_submission if _is_nightly else save_weekly_submission
    _written, _err = _fn(_area, _key_val, _edited, _email,
                         allow_create=_backfilling)
    if _err:
        st.error(_err)
    else:
        clear_caches()
        st.success(
            t("Saved {count} field(s) for {area} on {date}. The change reaches "
              "the rest of the dashboard on the agents' next run.",
              count=_written, area=_area, date=fmt_date(_key_val))
        )
        st.rerun()

# ── What is on record now ─────────────────────────────────────────────────────

_IDENTITY_COLS = ("Date", "Week_End_Date", "Area", "Zone", "District")

if _current:
    with st.expander(t("Full record as stored")):
        render_table(pd.DataFrame([
            {t("Field"): k if k in _IDENTITY_COLS else _label(k),
             t("Value"): v}
            for k, v in _current.items()
        ]))
