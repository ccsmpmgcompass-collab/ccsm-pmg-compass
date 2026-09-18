"""The Key Indicator drill-down — what a tapped card opens.

PLAN-2026-09-18-data-pages.md §3, step B2 (audit D1: nothing on the data
pages was clickable, and no "metric by week against its goal" view existed).

The panel is driven by ONE query parameter, ``?ki=<metric key>``. A card's
``href`` sets it (design_system.render_kpi_row), the pills strip above the
panel sets or clears it, and a "✕ cerrar" pill clears it. Keeping the state
in the URL rather than in session state means a link into a metric can be
pasted, and a phone's back button closes the panel.

Four views, as ``st.pills`` tabs, all drawn from ``analytics.ki_history``:

* **Por semana** — the weeks of the current cambio, blue bars against the
  companionships' own metas (amber dash, decision 6), the leadership goal's
  weekly share as a dotted violet mark, the same weeks of the previous cambio
  as ghost bars (decision 5), and a pace tick on the week in progress.
* **Por cambio** — one bar per cambio with data: achieved against "propuesto
  hasta hoy" (amber) and the leadership transfer goal (violet).
* **Por área** — the scope's areas ranked by % of their own meta, each row a
  link into Desgloses on that area.
* **Tabla** — the weekly numbers, with a CSV download.

The caller owns the scope (which areas, what to call it); this module owns
the metric. Panel passes the whole mission, Desgloses whatever is selected.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from app.analytics import ki_history as kh
from app.analytics.period_delta import SEVERE_DROP_PCT
from app.components.charts import bars_vs_goal, chart, ranked_list
from app.components.design_system import render_section_label, render_table
from app.config.metric_catalog import key_indicator_metrics, ki_short_label
from app.config.theme import STATUS
from app.db.goals_queries import group_goal_totals
from app.db.queries import get_daily_log
from app.i18n import t
from app.i18n.formats import fmt_day_month, fmt_int
from app.utils.area_helpers import mission_today
from app.utils.transfer_helpers import transfer_window

#: The query parameter that opens the panel on a metric.
KI_PARAM = "ki"

#: The pills strip's closing option. Never a metric key.
_CLOSE = "__close__"

#: The four tabs, as stable keys — the labels are translated at render time,
#: so a language switch mid-session cannot leave a Spanish value in a widget
#: whose options have become English (the Panel's zone-mode pattern).
TAB_WEEK, TAB_CYCLE, TAB_AREA, TAB_TABLE = "week", "cycle", "area", "table"
TABS = [TAB_WEEK, TAB_CYCLE, TAB_AREA, TAB_TABLE]

#: Decision 10: three grading states, no blue.
_ON_PACE_PCT, _BEHIND_PCT = 90.0, 60.0


# ── The URL ──────────────────────────────────────────────────────────────────

def _param(name: str) -> str | None:
    raw = st.query_params.get(name)
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    raw = str(raw or "").strip()
    return raw or None


def selected_ki() -> str | None:
    """The metric ``?ki=`` names, or None when absent or not a Key Indicator.

    Validated against the catalogue: a stale or mistyped key closes the panel
    rather than opening it on nothing.
    """
    raw = _param(KI_PARAM)
    return raw if raw and raw in key_indicator_metrics() else None


def ki_href(metric: str, params: dict | None = None) -> str:
    """The card link that opens the panel on ``metric`` — a query string on
    the current page. ``params`` carries the caller's scope (Desgloses'
    ``bd_zone`` / ``bd_district`` / ``bd_area``) so the full reload a link
    causes lands back on the same scope; empty values are dropped."""
    q = {KI_PARAM: metric}
    for k, v in (params or {}).items():
        if v is not None and str(v).strip():
            q[k] = str(v)
    return "?" + urlencode(q)


def _set_ki(metric: str | None) -> None:
    if metric:
        st.query_params[KI_PARAM] = metric
    elif KI_PARAM in st.query_params:
        del st.query_params[KI_PARAM]


# ── Small formatters ─────────────────────────────────────────────────────────

def _change_text(change: dict | None) -> tuple[str, str]:
    """A period_delta result as ("↑ 12%", colour) — the same rules as the
    arrows on the cards and the progression header's chip, so a red arrow
    means one thing everywhere."""
    if not change:
        return "", "#6b7280"
    direction = int(change.get("direction", 0))
    pct, show = change.get("pct"), change.get("show")
    severe = pct is not None and pct < SEVERE_DROP_PCT
    if direction > 0:
        color, arrow = STATUS["good"], "↑"
    elif direction == 0:
        color, arrow = "#6b7280", "→"
    else:
        color, arrow = (STATUS["bad"] if severe else STATUS["warn"]), "↓"
    if show == "absolute" and change.get("change") is not None:
        n = round(float(change["change"]))
        text = f"{'+' if n > 0 else ''}{fmt_int(n)}"
    elif pct is not None:
        text = f"{fmt_int(abs(pct))}%"
    else:
        return "", "#6b7280"
    return f"{arrow} {text}", color


def _grade(pct: float | None) -> str | None:
    if pct is None:
        return None
    if pct >= _ON_PACE_PCT:
        return "good"
    if pct >= _BEHIND_PCT:
        return "warn"
    return "bad"


def _cycle_name(cycle: dict | None) -> str:
    if not cycle:
        return ""
    return str(cycle.get("number") or "").strip() or fmt_day_month(cycle["start"])


def _tab_label(key: str) -> str:
    return {
        TAB_WEEK: t("By week"),
        TAB_CYCLE: t("By cambio"),
        TAB_AREA: t("By area"),
        TAB_TABLE: t("Table"),
    }.get(key, key)


# ── The panel ────────────────────────────────────────────────────────────────

@dataclass
class _Ctx:
    metric: str
    label: str
    scope_value: str
    areas: list[str]
    cycle: dict
    prev: dict | None
    totals: dict
    today: date
    key: str


def render_ki_strip(current: str | None, *, key: str) -> None:
    """The seven Key Indicators as a pills strip — the visible affordance for
    the drill-down (the card's ``href`` is the tap target on the scoreboard).
    A tap sets ``?ki=`` and reruns; the "✕ cerrar" pill, present only while
    a metric is open, clears it. Tapping the open metric again closes it.
    """
    keys = list(key_indicator_metrics())
    if not keys:
        return
    options = keys + ([_CLOSE] if current else [])

    def _label(k: str) -> str:
        return t("✕ close") if k == _CLOSE else ki_short_label(k)

    # The widget key carries the open metric so a link-driven change of
    # ``?ki=`` (a full reload with a new default) never meets a widget whose
    # stored value belongs to the previous selection.
    picked = st.pills(t("Key Indicator"), options, format_func=_label,
                      default=current, label_visibility="collapsed",
                      key=f"{key}_strip_{current or 'none'}")
    if picked != current:
        _set_ki(None if picked in (None, _CLOSE) else picked)
        st.rerun()


def render_ki_drilldown(scope_kind: str, scope_value: str, scope_areas,
                        metric: str | None = None, *,
                        default_tab: str = TAB_WEEK,
                        key: str = "ki_dd") -> bool:
    """Draw the pills strip and, when a metric is open, the panel under it.

    ``metric`` overrides ``?ki=`` (the pages pass nothing and let the URL
    decide). Returns True when a panel was drawn, False for the closed state.
    """
    current = metric or selected_ki()
    render_ki_strip(current, key=key)
    if not current:
        return False

    today = mission_today()
    cycle = transfer_window(0, today)
    label = ki_short_label(current)
    areas = sorted({str(a).strip() for a in scope_areas if str(a).strip()})
    if cycle is None:
        render_section_label(t("{metric} · {scope}", metric=label, scope=scope_value),
                             emphasis=True)
        st.info(t("No transfer schedule yet — TRANSFER_SCHEDULE is empty, so "
                  "there is no cambio to show by week."))
        return True

    totals = group_goal_totals(cycle["start"], set(areas))
    lead_total = kh.leadership_total(areas, cycle, current, totals=totals)
    right = t("{n} areas", n=fmt_int(len(areas)))
    if lead_total:
        right += " · " + t("cambio goal {goal}", goal=fmt_int(lead_total))
    render_section_label(t("{metric} · {scope}", metric=label, scope=scope_value),
                         emphasis=True, right=right)

    tab = st.pills(t("View"), TABS, format_func=_tab_label,
                   default=default_tab if default_tab in TABS else TAB_WEEK,
                   label_visibility="collapsed", key=f"{key}_tab")
    tab = tab if tab in TABS else default_tab

    ctx = _Ctx(metric=current, label=label, scope_value=scope_value,
               areas=areas, cycle=cycle, prev=transfer_window(1, today),
               totals=totals, today=today, key=key)
    if tab == TAB_CYCLE:
        _render_cycle(ctx)
    elif tab == TAB_AREA:
        _render_area(ctx)
    elif tab == TAB_TABLE:
        _render_table(ctx)
    else:
        _render_week(ctx)
    return True


# ── Por semana ───────────────────────────────────────────────────────────────

def _week_labels(points: list[kh.WeekPoint]) -> list[str]:
    return [f"{t('W{n}', n=i + 1)}<br>{fmt_day_month(p.start)}"
            for i, p in enumerate(points)]


def _render_week(ctx: _Ctx) -> None:
    points = kh.weekly_series(ctx.areas, ctx.metric, ctx.cycle, today=ctx.today)
    twin = (kh.twin_weekly(ctx.areas, ctx.metric, ctx.cycle, ctx.prev)
            if ctx.prev else None)
    if not any(p.actual is not None or p.meta is not None for p in points):
        st.info(t("No weekly reports yet for cambio {cycle}.",
                  cycle=_cycle_name(ctx.cycle)))
        return

    cur_i = next((i for i, p in enumerate(points) if p.is_current), None)
    pace_value = None
    if cur_i is not None and points[cur_i].meta:
        elapsed = (ctx.today - points[cur_i].start).days + 1
        pace_value = points[cur_i].meta * max(1, min(7, elapsed)) / 7

    fig = bars_vs_goal(
        _week_labels(points),
        [p.actual for p in points],
        [p.meta for p in points],
        twin=twin,
        pace_index=cur_i, pace_value=pace_value,
        mark=kh.leadership_weekly_mark(ctx.areas, ctx.cycle, ctx.metric,
                                       totals=ctx.totals),
        actual_label=t("Cambio {cycle}", cycle=_cycle_name(ctx.cycle)),
        twin_label=(t("Cambio {cycle}", cycle=_cycle_name(ctx.prev))
                    if ctx.prev else None),
        goal_label=t("Companionships' meta"),
        mark_label=t("Leadership goal, per week"),
    )
    chart(fig, height=300, key=f"{ctx.key}_week_chart")

    n, m = kh.cycle_position(ctx.cycle, ctx.today)
    line = t("cambio {cycle} · week {n} of {m}",
             cycle=_cycle_name(ctx.cycle), n=fmt_int(n), m=fmt_int(m))
    if ctx.prev and twin and any(v is not None for v in twin):
        line += " · " + t("ghost bars: the same weeks of cambio {prev}",
                          prev=_cycle_name(ctx.prev))
    unset = [p for p in points if not p.is_future and p.meta is None]
    if unset:
        line += " · " + t("{n} weeks with no meta written", n=fmt_int(len(unset)))
    st.caption(line)


# ── Por cambio ───────────────────────────────────────────────────────────────

def _render_cycle(ctx: _Ctx) -> None:
    points = kh.cycle_series(ctx.areas, ctx.metric, today=ctx.today)
    if not points:
        st.info(t("No weekly reports yet in any cambio."))
        return

    cur_i = next((i for i, p in enumerate(points) if p.is_current), None)
    pace_value = None
    if cur_i is not None and points[cur_i].leadership:
        c = points[cur_i]
        days = (c.end - c.start).days + 1
        elapsed = (ctx.today - c.start).days + 1
        pace_value = c.leadership * max(1, min(days, elapsed)) / days

    fig = bars_vs_goal(
        [p.number or fmt_day_month(p.start) for p in points],
        [p.actual for p in points],
        [p.meta_so_far for p in points],
        pace_index=cur_i, pace_value=pace_value,
        mark=[p.leadership for p in points],
        actual_label=t("Achieved"),
        goal_label=t("Proposed so far"),
        mark_label=t("Cambio goal"),
    )
    chart(fig, height=300, key=f"{ctx.key}_cycle_chart")

    if cur_i is not None:
        c = points[cur_i]
        parts = []
        if c.meta_so_far:
            parts.append(t("{actual} of {meta} proposed",
                           actual=fmt_int(c.actual or 0), meta=fmt_int(c.meta_so_far)))
        else:
            parts.append(t("{actual} so far, no meta written",
                           actual=fmt_int(c.actual or 0)))
        if c.leadership:
            parts.append(t("cambio goal {goal}", goal=fmt_int(c.leadership)))
        parts.append(t("{n} of {m} weeks reported",
                       n=fmt_int(c.weeks_covered), m=fmt_int(c.weeks_total)))
        st.caption(" · ".join(parts))


# ── Por área ─────────────────────────────────────────────────────────────────

def _render_area(ctx: _Ctx) -> None:
    end = min(ctx.today, ctx.cycle["end"])
    window = (ctx.cycle["start"], end)
    twin_window = None
    if ctx.prev:
        twin_window = (ctx.prev["start"],
                       min(ctx.prev["end"], ctx.prev["start"] + (end - ctx.cycle["start"])))
    daily = get_daily_log((ctx.today - ctx.cycle["start"]).days + 7)
    rows = kh.area_rows(ctx.areas, ctx.metric, window, twin_window,
                        daily=daily, today=ctx.today)
    if not rows:
        st.info(t("MISSION_ORG lists no active areas for {scope}.", scope=ctx.scope_value))
        return

    items = []
    for r in rows:
        sub = []
        if not r.reported:
            sub.append(t("no weekly report"))
        elif r.meta:
            sub.append(t("meta {meta}", meta=fmt_int(r.meta)))
        else:
            sub.append(t("no meta written"))
        if r.reported:
            sub.append(t("1 week") if r.weeks_reported == 1
                       else t("{n} weeks", n=fmt_int(r.weeks_reported)))
        if r.nights_missed:
            sub.append(t("1 night without a report") if r.nights_missed == 1
                       else t("{n} nights without a report",
                              n=fmt_int(r.nights_missed)))
        change, color = _change_text(r.change)
        items.append({
            "name": r.area,
            "sub": " · ".join(sub),
            "value": r.actual,
            "bar": r.pct if r.pct is not None else 0,
            "status": _grade(r.pct),
            "change": change,
            "change_color": color,
            "href": "/Desgloses?" + urlencode({"bd_area": r.area, KI_PARAM: ctx.metric}),
        })
    top = max([r.pct for r in rows if r.pct is not None] + [100.0])
    st.markdown(ranked_list(items, bar_max=top), unsafe_allow_html=True)
    line = t("Ranked by % of the companionships' own meta, cambio {cycle} "
             "through {day}. Tap an area to open it on Desgloses.",
             cycle=_cycle_name(ctx.cycle), day=fmt_day_month(end))
    if ctx.prev:
        line += " " + t("The arrow compares the same weeks of cambio {prev}.",
                        prev=_cycle_name(ctx.prev))
    st.caption(line)


# ── Tabla ────────────────────────────────────────────────────────────────────

def _week_frame(ctx: _Ctx) -> pd.DataFrame:
    points = kh.weekly_series(ctx.areas, ctx.metric, ctx.cycle, today=ctx.today)
    twin = (kh.twin_weekly(ctx.areas, ctx.metric, ctx.cycle, ctx.prev)
            if ctx.prev else [None] * len(points))
    return pd.DataFrame({
        t("Week"): [f"{fmt_day_month(p.start)} – {fmt_day_month(p.end)}" for p in points],
        t("Achieved"): [p.actual for p in points],
        t("Meta"): [p.meta for p in points],
        t("Areas reporting"): [p.reporting for p in points],
        t("Previous cambio"): twin,
    })


def _render_table(ctx: _Ctx) -> None:
    df = _week_frame(ctx)
    shown = df.copy()
    for col in shown.columns[1:]:
        shown[col] = shown[col].map(lambda v: "—" if v is None or pd.isna(v) else fmt_int(v))
    render_table(shown)
    st.download_button(
        t("Download CSV"),
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{ctx.metric}_{_cycle_name(ctx.cycle) or 'cambio'}.csv",
        mime="text/csv",
        key=f"{ctx.key}_csv",
    )
