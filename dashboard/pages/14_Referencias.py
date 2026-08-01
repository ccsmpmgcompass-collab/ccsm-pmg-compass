"""
14_Referencias.py
────────────────────────────────────────────────────────────────────────────────
Member referrals — asked for, and received.

Utah Provo's Referrals page read REFERRAL_DATA / REFERRAL_SUMMARY, tabs fed by
a referral-scraper pipeline CCSM does not run and does not have. That page was
cut from this app rather than ported.

CCSM asks two referral questions on its own nightly form, so this page is built
on those instead:

    references_asked           Referencias Solicitadas
    member_referrals_received  Referencias de Miembros Recibidas

Both keys are looked up in the live catalogue rather than assumed. If a mission
stops asking either question the page says so, instead of charting a column
that is not there.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.auth.auth import require_auth
from app.components.design_system import (
    inject_global_css, render_kpi_row, render_page_header, render_section_label,
    render_sidebar, render_table,
)
from app.config.flavor_loader import METRIC_LABELS, flavor
from app.config.metric_catalog import nightly_metrics
from app.config.theme import CHART_COLORS
from app.db.queries import get_config_value, get_daily_log, get_zones
from app.i18n import t
from app.i18n.formats import NA, fmt_date, fmt_int, fmt_number, fmt_percent

st.set_page_config(
    page_title="CCSM · Referencias — PMG Compass",
    page_icon="",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

render_page_header(
    t("Referrals"),
    t("{mission} — member referrals asked for and received",
      mission=get_config_value("MISSION_NAME", flavor.display_name)),
)

#: The mission's own referral questions. Named, but never assumed to exist —
#: `_present` below is what decides whether a section renders.
ASKED = "references_asked"
RECEIVED = "member_referrals_received"

_catalog = nightly_metrics()
_present = [k for k in (ASKED, RECEIVED) if k in _catalog]

if not _present:
    st.info(
        t("This mission's nightly form does not ask about referrals, so there "
          "is nothing to report here. The questions this page needs are "
          "`references_asked` and `member_referrals_received` in "
          "QUESTIONS_CONFIG.")
    )
    st.stop()

# ── Window and scope ──────────────────────────────────────────────────────────

_c1, _c2 = st.columns(2)
with _c1:
    _days = st.number_input(t("Days displayed"), min_value=7, max_value=180,
                            value=28, step=7, key="ref_days")
_ALL = t("All zones")
with _c2:
    _zone = st.selectbox(t("Zone"), [_ALL] + get_zones(), key="ref_zone")

_df = get_daily_log(int(_days))
if _zone != _ALL and not _df.empty and "Zone" in _df.columns:
    _df = _df[_df["Zone"].astype(str) == _zone]

_missing = [k for k in (ASKED, RECEIVED) if k not in _df.columns]
_df_cols = [k for k in _present if k in _df.columns]

if _df.empty or not _df_cols:
    st.info(
        t("No nightly data in this window yet. Referral figures appear once "
          "companionships submit the nightly form and the agents write "
          "DAILY_LOG.")
    )
    st.stop()

if _missing:
    st.warning(
        t("DAILY_LOG has no column for: {cols}. Those figures are left out "
          "rather than shown as zero.",
          cols=", ".join(METRIC_LABELS.get(k, k) for k in _missing))
    )


def _total(key: str) -> float | None:
    """Window total for a metric, or None when the mission does not collect it.

    None, not 0 — "we do not ask this" and "nobody received a referral" are
    different facts and must not print the same.
    """
    if key not in _df.columns:
        return None
    return float(pd.to_numeric(_df[key], errors="coerce").fillna(0).sum())


_asked = _total(ASKED)
_received = _total(RECEIVED)

# ── Headline ──────────────────────────────────────────────────────────────────

render_section_label(t("Last {days} days", days=fmt_int(_days)))

_tiles = []
if _asked is not None:
    _tiles.append({"label": METRIC_LABELS.get(ASKED, ASKED), "value": int(_asked)})
if _received is not None:
    _tiles.append({"label": METRIC_LABELS.get(RECEIVED, RECEIVED),
                   "value": int(_received)})
if _tiles:
    render_kpi_row(_tiles)

if _asked and _received is not None:
    st.caption(
        t("{rate} of referrals asked for came back as a member referral "
          "({received} from {asked} asks).",
          rate=fmt_percent(_received / _asked * 100, 1),
          received=fmt_int(_received), asked=fmt_int(_asked))
    )
elif _asked == 0 and _received is not None:
    # Guarding the ratio, not just the division: 0 asks with referrals still
    # arriving is a real and interesting state, and "—%" says that honestly
    # where a 0% would read as failure.
    st.caption(
        t("No referrals were asked for in this window, so there is no "
          "ask-to-referral rate to report ({received} referral(s) received).",
          received=fmt_int(_received))
    )

# ── Trend ─────────────────────────────────────────────────────────────────────

render_section_label(t("Daily Trend"))

if "Date" not in _df.columns:
    st.info(t("DAILY_LOG has no Date column, so there is no trend to draw."))
else:
    _daily = (_df.groupby("Date")[_df_cols].sum().reset_index()
              .sort_values("Date"))
    _fig = go.Figure()
    for _i, _key in enumerate(_df_cols):
        _fig.add_trace(go.Bar(
            x=_daily["Date"], y=_daily[_key],
            name=METRIC_LABELS.get(_key, _key),
            marker_color=CHART_COLORS[_i % len(CHART_COLORS)],
        ))
    _fig.update_layout(
        title=t("Referrals per day"),
        xaxis_title=t("Date"), yaxis_title=t("Count"),
        xaxis_type="category", barmode="group", hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        margin=dict(t=60, b=50, l=50, r=20),
    )
    st.plotly_chart(_fig, use_container_width=True)

# ── By area ───────────────────────────────────────────────────────────────────

render_section_label(t("By Area"))

if "Area" not in _df.columns:
    st.info(t("DAILY_LOG has no Area column, so it cannot be broken down by area."))
else:
    _by = _df.groupby("Area")[_df_cols].sum().reset_index()

    _rows = []
    for _, _r in _by.iterrows():
        _a = _r.get(ASKED) if ASKED in _by.columns else None
        _rv = _r.get(RECEIVED) if RECEIVED in _by.columns else None
        _rows.append({
            t("Area"): _r["Area"],
            METRIC_LABELS.get(ASKED, ASKED): fmt_int(_a) if _a is not None else NA,
            METRIC_LABELS.get(RECEIVED, RECEIVED): fmt_int(_rv) if _rv is not None else NA,
            # An area that asked nobody has no rate — not a 0% one. Ranking by
            # a fabricated 0 would push those areas to the bottom as though
            # they had tried and failed.
            t("Rate"): (fmt_percent(_rv / _a * 100, 1)
                        if _a and _rv is not None else NA),
        })

    _tbl = pd.DataFrame(_rows)
    _sort_col = (METRIC_LABELS.get(RECEIVED, RECEIVED)
                 if RECEIVED in _by.columns else METRIC_LABELS.get(ASKED, ASKED))
    if _sort_col in _tbl.columns and not _by.empty:
        _order = _by.sort_values(
            RECEIVED if RECEIVED in _by.columns else ASKED, ascending=False
        )["Area"].tolist()
        _tbl["_o"] = _tbl[t("Area")].map({a: i for i, a in enumerate(_order)})
        _tbl = _tbl.sort_values("_o").drop(columns="_o")
    render_table(_tbl)

    st.caption(
        t("Ranked by referrals received. An area that asked for none has no "
          "rate rather than a 0% one — it has not tried and failed, it has "
          "not tried.")
    )

# ── Context ───────────────────────────────────────────────────────────────────

with st.expander(t("What this page counts")):
    st.markdown(t(
        "- **{asked}** — how many times companionships asked a member for "
        "someone to teach, from the nightly form.\n"
        "- **{received}** — how many referrals members actually gave them, "
        "also from the nightly form.\n\n"
        "Both are self-reported nightly counts, so they measure the "
        "conversation, not a record in another system. There is no referral "
        "feed to reconcile against.",
        asked=METRIC_LABELS.get(ASKED, ASKED),
        received=METRIC_LABELS.get(RECEIVED, RECEIVED),
    ))
