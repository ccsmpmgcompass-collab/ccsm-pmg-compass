"""app/components/charts.py — the one chart language for the data pages.

Data-pages redesign, step A2 (PLAN-2026-09-18-data-pages.md §2). Before this
module the Panel, Desgloses and Embudo drew fifteen Plotly figures through
fifteen hand-written layouts: three palettes, five margin conventions, titles
inside some charts and section labels above others, legends above, below and
absent, and two y-axes whose labels were clipped to two letters (audit E2).

Everything here has ONE look:

* ``chart(fig)`` is the only place the three pages call ``st.plotly_chart``.
  It applies the layout below and nothing else — the section label is the
  chart's title, so no figure carries one of its own.
* ``bars_vs_goal`` is the drill-down's bar chart (Phase B, mockup 3.2).
* ``small_multiples`` replaces the eight-week spaghetti (audit P4).
* ``stage_bars`` replaces both Plotly funnels (audit D5, E4) with HTML.
* ``ranked_list`` is the Panel's compliance-rankings row, generalised.

Colour: ``SERIES_COLORS[0]`` (blue) is the one magnitude hue — "this metric,
this period" on every chart. The twin/ghost is translucent white. Status
(good / warn / bad) is ``theme.STATUS``. Nothing else is coloured.
"""
from __future__ import annotations

import html as _html
import math
from typing import Callable, Iterable, Sequence

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from plotly.subplots import make_subplots

from app.components.design_system import _register_plotly_template
from app.config.theme import SERIES_COLORS, STATUS
from app.i18n import t
from app.i18n.formats import fmt_int

#: The single magnitude hue.
MAGNITUDE = SERIES_COLORS[0]
#: The twin period's ghost bars: outline only, translucent white.
GHOST = "rgba(255,255,255,0.35)"
#: The goal line. Amber, dashed — a reference, not a grade.
GOAL_LINE = STATUS["warn"]
#: The pace tick: white, like the KPI card's.
PACE_TICK = "rgba(244,244,248,0.9)"
#: Text on the dark surface.
INK = "#f4f4f8"
MUTED = "#9ca3af"

MIN_HEIGHT = 220
_FONT = dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif",
             size=12, color=MUTED)
_MARGIN = dict(l=44, r=16, t=8, b=36)
#: Extra bottom margin when a legend sits under the plot.
_LEGEND_ROOM = 28


def _legend_wanted(fig: go.Figure) -> bool:
    """A legend only when there is something to tell apart: two or more named
    traces that would show in it, or a pie/funnel whose categories ARE the
    legend."""
    n = 0
    for tr in fig.data:
        if tr.type in ("pie", "funnelarea"):
            return True
        if getattr(tr, "showlegend", None) is False:
            continue
        if getattr(tr, "visible", None) is False:
            continue
        n += 1
    return n >= 2


def apply_layout(fig: go.Figure, *, height: int | None = None) -> go.Figure:
    """The shared layout, applied over whatever the figure already carries.

    Axis specifics the caller set (ranges, tick formats, category order) are
    kept; the surface, font, margins, title and legend placement are not the
    caller's to decide. Both axes get ``automargin`` so a long tick label
    widens the margin instead of being clipped — audit E2 was two horizontal
    bar charts whose zone names showed two letters each.
    """
    # The template is registered by inject_stylesheet() on every page run;
    # outside one (a test, a script) it is registered here instead.
    if "pmg_dark" not in pio.templates:
        _register_plotly_template()
    h = height if height is not None else (fig.layout.height or 300)
    h = max(MIN_HEIGHT, int(h))
    legend = _legend_wanted(fig)
    margin = dict(_MARGIN)
    if legend:
        margin["b"] = margin["b"] + _LEGEND_ROOM
    fig.update_layout(
        template="pmg_dark",
        title_text="",
        font=_FONT,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=margin,
        height=h,
        showlegend=legend,
        hoverlabel=dict(bgcolor="#0e0e15", font=dict(color=INK, size=12)),
    )
    if legend:
        fig.update_layout(legend=dict(
            orientation="h", yanchor="top", y=-0.16, xanchor="left", x=0,
            font=dict(size=11), bgcolor="rgba(0,0,0,0)",
        ))
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    return fig


def chart(fig: go.Figure, *, height: int | None = None,
          key: str | None = None) -> None:
    """Draw a figure. The ONLY ``st.plotly_chart`` call site on the data pages."""
    apply_layout(fig, height=height)
    kwargs = {"key": key} if key else {}
    st.plotly_chart(
        fig, use_container_width=True, theme=None,
        config={"displayModeBar": False, "responsive": True}, **kwargs,
    )


# ── bars vs goal ─────────────────────────────────────────────────────────────

def _as_list(v, n: int) -> list:
    """A per-bucket list from a scalar or a sequence; None where absent."""
    if v is None:
        return [None] * n
    if isinstance(v, (int, float)):
        return [float(v)] * n
    out = list(v)
    out += [None] * (n - len(out))
    return [None if x is None else float(x) for x in out[:n]]


def bars_vs_goal(labels: Sequence[str], actual: Sequence[float | None],
                 goal, *, twin: Sequence[float | None] | None = None,
                 pace_index: int | None = None,
                 pace_value: float | None = None,
                 actual_label: str | None = None,
                 twin_label: str | None = None,
                 goal_label: str | None = None,
                 value_fmt: Callable = fmt_int) -> go.Figure:
    """Blue bars against a dashed amber goal, with the previous period's
    values as outline-only ghost bars and a white tick on the in-progress
    bucket (mockup 3.2).

    ``goal`` is a number (one line across every bucket) or a per-bucket
    sequence (a dash over each bar — the weekly metas differ week to week,
    decision 6). A ``None`` bucket draws no goal there. ``twin`` is aligned
    with ``labels``; ``None`` skips that bucket. ``pace_index`` names the
    in-progress bucket, drawn lighter, and ``pace_value`` is where its bar
    should be by today.
    """
    labels = [str(x) for x in labels]
    n = len(labels)
    act = _as_list(actual, n)
    goals = _as_list(goal, n)
    ghosts = _as_list(twin, n) if twin is not None else None

    fig = go.Figure()
    if ghosts is not None and any(v is not None for v in ghosts):
        fig.add_trace(go.Bar(
            x=labels, y=[0 if v is None else v for v in ghosts],
            name=twin_label or t("Previous cambio"),
            width=0.82,
            marker=dict(color="rgba(0,0,0,0)", line=dict(color=GHOST, width=1.5)),
            hovertemplate="%{x}<br>%{y:.0f}<extra>"
                          + _html.escape(twin_label or t("Previous cambio")) + "</extra>",
        ))
    opacity = [0.55 if i == pace_index else 1.0 for i in range(n)]
    fig.add_trace(go.Bar(
        x=labels, y=[0 if v is None else v for v in act],
        name=actual_label or t("This cambio"),
        width=0.5 if ghosts is not None else 0.7,
        marker=dict(color=MAGNITUDE, opacity=opacity),
        text=["" if v is None else value_fmt(v) for v in act],
        textposition="outside", cliponaxis=False,
        textfont=dict(color=INK, size=12),
        hovertemplate="%{x}<br>%{y:.0f}<extra>"
                      + _html.escape(actual_label or t("This cambio")) + "</extra>",
    ))

    # The goal. One number: a line across the chart. Per bucket: a dash over
    # each bar, at that bucket's own goal. Both dashed amber, and one legend
    # entry (a trace with no points) names them.
    goal_name = goal_label or t("Goal")
    if isinstance(goal, (int, float)) and goal > 0:
        fig.add_hline(y=float(goal), line=dict(color=GOAL_LINE, width=2, dash="dash"))
    else:
        for i, g in enumerate(goals):
            if g is None or g <= 0:
                continue
            fig.add_shape(type="line", xref="x", yref="y",
                          x0=i - 0.42, x1=i + 0.42, y0=g, y1=g,
                          line=dict(color=GOAL_LINE, width=2, dash="dash"))
    if any(g is not None and g > 0 for g in goals):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="lines", name=goal_name,
            line=dict(color=GOAL_LINE, width=2, dash="dash"),
            hoverinfo="skip",
        ))

    if pace_index is not None and pace_value is not None and 0 <= pace_index < n:
        fig.add_trace(go.Scatter(
            x=[labels[pace_index]], y=[float(pace_value)], mode="markers",
            marker=dict(symbol="line-ew", size=24, line=dict(width=2.5, color=PACE_TICK)),
            name=t("Expected by today"), showlegend=False,
            hovertemplate=_html.escape(t("Expected by today")) + ": %{y:.0f}<extra></extra>",
            cliponaxis=False,
        ))

    top = max([v for v in act if v is not None] +
              [g for g in goals if g is not None] +
              ([v for v in ghosts if v is not None] if ghosts else []) +
              ([float(pace_value)] if pace_value is not None else []) + [0])
    fig.update_layout(
        barmode="overlay",
        xaxis=dict(type="category"),
        yaxis=dict(range=[0, max(top * 1.22, 1)], rangemode="tozero"),
        hovermode="x unified",
    )
    return fig


# ── small multiples ──────────────────────────────────────────────────────────

def small_multiples(series: dict[str, tuple[Sequence, Sequence]], cols: int = 4,
                    *, value_fmt: Callable = fmt_int,
                    row_height: int = 150) -> go.Figure:
    """One mini line per metric, one hue, its own y-axis, the last value
    printed. Replaces a chart that drew every metric on one axis, where the
    biggest series flattened the rest into the baseline (audit P4)."""
    names = list(series.keys())
    n = len(names)
    cols = max(1, min(cols, n)) if n else 1
    rows = max(1, math.ceil(n / cols))
    fig = make_subplots(
        rows=rows, cols=cols, subplot_titles=names,
        vertical_spacing=min(0.35, 0.18 * 4 / max(rows, 1)) if rows > 1 else 0,
        horizontal_spacing=0.06,
    )
    for k, name in enumerate(names):
        x, y = series[name]
        x = list(x)
        y = [None if v is None else float(v) for v in y]
        r, c = divmod(k, cols)
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines+markers", name=name, showlegend=False,
            line=dict(color=MAGNITUDE, width=2), marker=dict(size=4),
            hovertemplate="%{x}<br>%{y:.0f}<extra>" + _html.escape(str(name)) + "</extra>",
        ), row=r + 1, col=c + 1)
        last = next((i for i in range(len(y) - 1, -1, -1) if y[i] is not None), None)
        if last is not None:
            fig.add_annotation(
                x=x[last], y=y[last], text=value_fmt(y[last]),
                showarrow=False, xanchor="left", xshift=6, yshift=2,
                font=dict(size=12, color=INK),
                row=r + 1, col=c + 1,
            )
        fig.update_yaxes(rangemode="tozero", nticks=3, tickfont=dict(size=10),
                         row=r + 1, col=c + 1)
        fig.update_xaxes(type="category", nticks=3, tickfont=dict(size=10),
                         row=r + 1, col=c + 1)
    for ann in fig.layout.annotations:
        if ann.text in names:
            ann.font = dict(size=12, color=MUTED)
            ann.xanchor = "left"
            ann.x = ann.x - (0.5 / cols) * 0.98
    fig.update_layout(height=rows * row_height + 40, showlegend=False)
    return fig


# ── stage bars ───────────────────────────────────────────────────────────────

def stage_bars(stages: Iterable[tuple[str, float]], *,
               value_fmt: Callable = fmt_int) -> str:
    """Horizontal single-hue bars, one per stage, with the step conversion
    written between rows (mockup 3.3). Pure HTML — a funnel chart's shrinking
    trapezoids encode nothing a bar and a percentage do not, and its labels
    clip. The first stage sets the bar's full width."""
    rows = [(str(lbl), (0.0 if v is None else float(v))) for lbl, v in stages]
    if not rows:
        return ""
    full = max([v for _, v in rows] + [0]) or 1.0
    out = ['<div class="pmg-stages" style="margin:4px 0 12px 0;">']
    prev = None
    for lbl, v in rows:
        if prev is not None:
            conv = f"{fmt_int(round(v / prev * 100))}%" if prev > 0 else "—"
            out.append(
                f'<div class="pmg-stage-conv" style="display:flex;align-items:center;'
                f'gap:6px;padding:2px 0 2px 0;margin-left:34%;font-size:0.7rem;'
                f'color:{MUTED};">'
                f'<span style="opacity:.7;">↓</span><span>{conv}</span></div>'
            )
        width = max(0.0, min(100.0, v / full * 100))
        out.append(
            f'<div class="pmg-stage" style="display:grid;'
            f'grid-template-columns:minmax(0,34%) minmax(0,1fr) auto;'
            f'align-items:center;gap:10px;">'
            f'<span style="font-size:0.8rem;color:{INK};overflow:hidden;'
            f'text-overflow:ellipsis;white-space:nowrap;" title="{_html.escape(lbl)}">'
            f'{_html.escape(lbl)}</span>'
            f'<span style="display:block;height:14px;border-radius:3px;'
            f'background:rgba(255,255,255,0.06);overflow:hidden;">'
            f'<span style="display:block;height:100%;width:{width:.1f}%;'
            f'background:{MAGNITUDE};border-radius:3px;"></span></span>'
            f'<span style="font-size:0.85rem;font-weight:700;color:{INK};'
            f'font-variant-numeric:tabular-nums;min-width:3rem;text-align:right;">'
            f'{_html.escape(str(value_fmt(v)))}</span>'
            f'</div>'
        )
        prev = v
    out.append("</div>")
    return "".join(out)


# ── ranked list ──────────────────────────────────────────────────────────────

#: Row tints by status. The three statuses are theme.STATUS; "none" is a row
#: with nothing to grade (no data). Old vocabularies (green/amber/red, from
#: compliance_rankings.status_of) are accepted.
_STATUS_ALIAS = {"green": "good", "amber": "warn", "red": "bad",
                 "good": "good", "warn": "warn", "bad": "bad"}
_ROW_TINT = {
    "good": ("rgba(62,207,111,0.10)", STATUS["good"]),
    "warn": ("rgba(242,177,52,0.10)", STATUS["warn"]),
    "bad":  ("rgba(240,100,90,0.10)", STATUS["bad"]),
    "none": ("rgba(255,255,255,0.03)", "#4b5563"),
}


def ranked_list(rows: Sequence[dict], *, value_fmt: Callable = fmt_int,
                bar_max: float | None = None,
                href: Callable[[dict], str | None] | None = None) -> str:
    """rank · dot · name · sub-line · inline bar · change · value, one row per
    entry, as HTML. Extracted from the Panel's compliance rankings so every
    ranked comparison on the data pages is the same row.

    Each row dict: ``name`` (required); ``rank`` (else its position); ``sub``
    (a muted line under the name); ``value`` (the number at the right, or
    None for "—"); ``bar`` (the inline bar's magnitude, default ``value``);
    ``status`` ("good"/"warn"/"bad"/None, or green/amber/red); ``change`` (a
    short string, already formatted, e.g. "↑ 12%"); ``change_color``;
    ``href`` (the row becomes a link). ``href`` the argument is a function of
    the row for callers that derive it; a row's own ``href`` wins.
    ``bar_max`` fills the bar; default the largest bar in the list.
    """
    rows = list(rows)
    if not rows:
        return ""
    bars = []
    for r in rows:
        b = r.get("bar", r.get("value"))
        try:
            bars.append(None if b is None else float(b))
        except (TypeError, ValueError):
            bars.append(None)
    full = bar_max if bar_max else (max([b for b in bars if b is not None] + [0]) or 1.0)

    out = ['<div class="pmg-ranked">']
    for i, (r, b) in enumerate(zip(rows, bars), start=1):
        status = _STATUS_ALIAS.get(str(r.get("status") or "").lower(), "none")
        bg, dot = _ROW_TINT[status]
        rank = r.get("rank", i)
        value = r.get("value")
        shown = "—" if value is None else str(value_fmt(value))
        width = 0.0 if b is None else max(0.0, min(100.0, b / full * 100))
        sub = r.get("sub") or ""
        change = r.get("change") or ""
        change_color = r.get("change_color") or MUTED
        link = r.get("href") or (href(r) if href else None)
        tag, attrs = ("a", f' href="{_html.escape(str(link))}" target="_self"') if link else ("div", "")
        out.append(
            f'<{tag} class="pmg-rank-row"{attrs} style="display:grid;'
            f'grid-template-columns:1.6rem 0.6rem minmax(0,1fr) minmax(48px,26%) auto auto;'
            f'align-items:center;gap:0.7rem;background:{bg};border-radius:8px;'
            f'padding:0.55rem 0.9rem;margin-bottom:0.35rem;color:inherit;'
            f'text-decoration:none;{"cursor:pointer;" if link else ""}">'
            f'<span style="text-align:right;color:#6b7280;font-size:0.8rem;">{_html.escape(str(rank))}</span>'
            f'<span style="width:0.6rem;height:0.6rem;border-radius:50%;background:{dot};"></span>'
            f'<span style="min-width:0;">'
            f'<span style="display:block;color:{INK};font-weight:600;font-size:0.92rem;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{_html.escape(str(r.get("name", "")))}</span>'
            + (f'<span style="display:block;color:{MUTED};font-size:0.75rem;">{_html.escape(str(sub))}</span>' if sub else "")
            + f'</span>'
            f'<span style="display:block;height:6px;border-radius:3px;background:rgba(255,255,255,0.06);overflow:hidden;">'
            f'<span style="display:block;height:100%;width:{width:.1f}%;background:{dot};border-radius:3px;"></span></span>'
            f'<span style="font-size:0.78rem;color:{change_color};min-width:2.6rem;text-align:right;">{_html.escape(str(change))}</span>'
            f'<span style="color:{INK};font-weight:700;font-size:0.95rem;text-align:right;'
            f'min-width:3.2rem;font-variant-numeric:tabular-nums;">{_html.escape(shown)}</span>'
            f'</{tag}>'
        )
    out.append("</div>")
    return "".join(out)
