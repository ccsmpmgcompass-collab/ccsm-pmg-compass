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
* ``share_bar`` is one 100% stacked bar: a mix, where a donut was.
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

from app.analytics.period_delta import SEVERE_DROP_PCT
from app.components.design_system import _register_plotly_template
from app.components.design_system import sparkline_svg as _spark
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
#: The leadership mark — the same violet as the KPI card's second tick
#: (design_system._MARK_COLOR): neither a grade nor the pace, on both.
MARK_LINE = "#9085e9"
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
                 mark=None, mark_label: str | None = None,
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

    ``mark`` is the leadership goal (decision 6): a dotted violet line, one
    number or per bucket exactly like ``goal``, so the companionships' amber
    meta and leadership's mark are two different marks on every chart, as
    they are two ticks on the card. ``mark_label`` names it in the legend.
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

    # The leadership mark, drawn the same two ways as the goal.
    marks = _as_list(mark, n) if mark is not None else [None] * n
    if isinstance(mark, (int, float)) and mark > 0:
        fig.add_hline(y=float(mark), line=dict(color=MARK_LINE, width=2, dash="dot"))
    else:
        for i, g in enumerate(marks):
            if g is None or g <= 0:
                continue
            fig.add_shape(type="line", xref="x", yref="y",
                          x0=i - 0.42, x1=i + 0.42, y0=g, y1=g,
                          line=dict(color=MARK_LINE, width=2, dash="dot"))
    if any(g is not None and g > 0 for g in marks):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="lines",
            name=mark_label or t("Leadership goal"),
            line=dict(color=MARK_LINE, width=2, dash="dot"),
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
              [g for g in marks if g is not None] +
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
    biggest series flattened the rest into the baseline (audit P4).

    **Desktop widths only.** ``cols`` is baked into the figure, and a Plotly
    subplot grid cannot reflow: at 375px a four-column grid gives each panel
    about 80px, where the titles overlap and the value annotations land in the
    next panel over. For a grid that has to survive a phone, use
    ``spark_multiples`` below."""
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


# ── spark multiples ──────────────────────────────────────────────────────────

def spark_multiples(series: dict[str, Sequence], *, value_fmt: Callable = fmt_int,
                    caption: Callable[[str], str] | None = None) -> str:
    """One small panel per metric — name, latest value, sparkline — as a CSS
    grid that WRAPS. The small-multiples idiom for a page that has to read at
    375px as well as 1400px.

    ``small_multiples`` above is a Plotly subplot grid, and its column count is
    fixed when the figure is built: a four-column grid asked to render at 339px
    gives every panel about 80px, where the titles overlap each other and the
    value annotations land in the neighbouring panel. Measured live on the
    Panel at 375px, 2026-09-18. Plotly cannot reflow a subplot grid
    responsively, and Streamlit cannot tell the server how wide the browser is,
    so a grid that must survive both widths is drawn in HTML instead — the same
    reasoning that made ``stage_bars`` HTML rather than a funnel chart.

    What is lost against the Plotly version: the y-axis and the week ticks.
    What a reader takes from a small multiple is the shape and where it ends,
    and those are exactly what a sparkline and the printed last value carry.
    The real chart, with its axes, is one tap away in the drill-down.

    ``series`` maps a label to its values, oldest first; ``caption`` optionally
    returns a muted line under each panel.
    """
    cells = []
    for name, values in series.items():
        nums = [v for v in (values or []) if v is not None]
        last = value_fmt(nums[-1]) if nums else "—"
        foot = (caption(name) if caption else "") or ""
        cells.append(
            f'<div class="pmg-spark-cell" style="background:rgba(255,255,255,0.03);'
            f'border:1px solid rgba(255,255,255,0.07);border-radius:10px;'
            f'padding:0.6rem 0.75rem;min-width:0;">'
            f'<div title="{_html.escape(str(name))}" style="font-size:0.7rem;'
            f'font-weight:600;color:{MUTED};line-height:1.2;overflow:hidden;'
            f'text-overflow:ellipsis;white-space:nowrap;">{_html.escape(str(name))}</div>'
            f'<div style="font-size:1.15rem;font-weight:700;color:{INK};'
            f'margin-top:2px;font-variant-numeric:tabular-nums;">{_html.escape(str(last))}</div>'
            + _spark(nums)
            + (f'<div style="font-size:0.65rem;color:{MUTED};margin-top:2px;">'
               f'{_html.escape(str(foot))}</div>' if foot else "")
            + '</div>'
        )
    if not cells:
        return ""
    return ('<div class="pmg-sparks" style="display:grid;'
            'grid-template-columns:repeat(auto-fit,minmax(max(150px,22%),1fr));'
            'gap:10px;margin-bottom:1.25rem;">' + "".join(cells) + '</div>')


# ── stage bars ───────────────────────────────────────────────────────────────

def _widest_drop(values: Sequence[float]) -> int | None:
    """Index of the step that loses the most PEOPLE, i.e. the largest absolute
    fall from one stage to the next; the returned index is the lower stage.

    Absolute, not the lowest conversion rate. On the live export the two
    disagree and only one of them is worth pointing at: found → church is
    2.545 → 167, so 2.378 people are lost there, while baptism-date → baptized
    is 68 → 3, a 4% step that costs 65. The 4% is the smaller number in every
    sense, and calling it the pipeline's problem would be wrong.
    """
    best, best_i = 0.0, None
    for i in range(1, len(values)):
        fall = values[i - 1] - values[i]
        if fall > best:
            best, best_i = fall, i
    return best_i


def stage_bars(stages: Iterable[tuple[str, float]], *,
               value_fmt: Callable = fmt_int,
               highlight_worst: bool = False,
               twin: Sequence[float | None] | None = None,
               twin_label: str | None = None) -> str:
    """Horizontal single-hue bars, one per stage, with the step conversion
    written between rows (mockup 3.3). Pure HTML — a funnel chart's shrinking
    trapezoids encode nothing a bar and a percentage do not, and its labels
    clip. The first stage sets the bar's full width.

    ``highlight_worst`` marks the step that loses the most people: its
    conversion line turns amber and says so. A funnel always narrows, so this
    is a "look here", not a grade — which is why it is amber and named rather
    than red and silent.

    ``twin`` draws the same stages from the period before, as a thin dim bar
    under each one and on the same scale, so "better or worse than last time"
    is a comparison of two lengths rather than of two screens. Its value rides
    on the row's hover, named by ``twin_label``. A stage the twin has no
    reading for simply has no second bar — the previous cambio's first weeks
    are legitimately empty on a mission four cycles old (plan step D5).
    """
    rows = [(str(lbl), (0.0 if v is None else float(v))) for lbl, v in stages]
    if not rows:
        return ""
    twins = list(twin or [])
    twins += [None] * (len(rows) - len(twins))
    # ONE scale for both series: a twin scaled to its own maximum would draw a
    # collapsed period as a healthy one.
    full = max([v for _, v in rows]
               + [t for t in twins if t is not None] + [0]) or 1.0
    worst = _widest_drop([v for _, v in rows]) if highlight_worst else None
    out = ['<div class="pmg-stages" style="margin:4px 0 12px 0;">']
    prev = None
    for i, (lbl, v) in enumerate(rows):
        if prev is not None:
            conv = f"{fmt_int(round(v / prev * 100))}%" if prev > 0 else "—"
            worst_here = (i == worst)
            note = (f'<span style="font-weight:600;">· '
                    f'{_html.escape(t("largest drop"))}</span>') if worst_here else ""
            out.append(
                f'<div class="pmg-stage-conv" style="display:flex;align-items:center;'
                f'gap:6px;padding:2px 0 2px 0;margin-left:34%;font-size:0.7rem;'
                f'color:{STATUS["warn"] if worst_here else MUTED};">'
                f'<span style="opacity:.7;">↓</span><span>{conv}</span>{note}</div>'
            )
        width = max(0.0, min(100.0, v / full * 100))
        tv = twins[i]
        hover = lbl
        twin_html = ""
        if tv is not None:
            hover = (f"{lbl} · {twin_label or t('Previous period')}: "
                     f"{value_fmt(tv)}")
            twin_html = (
                f'<span style="display:block;height:5px;margin-top:3px;'
                f'border-radius:2px;background:rgba(255,255,255,0.05);'
                f'overflow:hidden;">'
                f'<span style="display:block;height:100%;'
                f'width:{max(0.0, min(100.0, tv / full * 100)):.1f}%;'
                f'background:rgba(203,203,210,0.45);border-radius:2px;">'
                f'</span></span>')
        out.append(
            f'<div class="pmg-stage" style="display:grid;'
            f'grid-template-columns:minmax(0,34%) minmax(0,1fr) auto;'
            f'align-items:center;gap:10px;" title="{_html.escape(hover)}">'
            f'<span style="font-size:0.8rem;color:{INK};min-width:0;'
            f'overflow-wrap:anywhere;">{_html.escape(lbl)}</span>'
            f'<span style="min-width:0;">'
            f'<span style="display:block;height:14px;border-radius:3px;'
            f'background:rgba(255,255,255,0.06);overflow:hidden;">'
            f'<span style="display:block;height:100%;width:{width:.1f}%;'
            f'background:{MAGNITUDE};border-radius:3px;"></span></span>'
            f'{twin_html}</span>'
            f'<span style="font-size:0.85rem;font-weight:700;color:{INK};'
            f'font-variant-numeric:tabular-nums;min-width:3rem;text-align:right;">'
            f'{_html.escape(str(value_fmt(v)))}</span>'
            f'</div>'
        )
        prev = v
    out.append("</div>")
    return "".join(out)


# ── share bar ────────────────────────────────────────────────────────────────

def share_bar(parts: Sequence[tuple[str, float]], *,
              value_fmt: Callable = fmt_int, min_label_share: float = 7.0) -> str:
    """One 100% stacked bar and a legend beneath it — a mix, where the page
    used to draw a donut.

    A donut asks the reader to compare arcs; a single bar puts every category
    on one axis and reads at a glance. It is also the only shape of this that
    survives a phone: the donut it replaces carried its labels OUTSIDE the
    ring, which at 375px left the ring about 120px across.

    Hues are ``SERIES_COLORS`` in order — identity, not magnitude: these are
    four different things, not four sizes of one. A slice narrower than
    ``min_label_share`` percent keeps its colour and its legend row but drops
    the percentage written inside it, where it would not fit.
    """
    rows = [(str(lbl), max(0.0, float(v or 0))) for lbl, v in parts]
    total = sum(v for _, v in rows)
    if not rows or total <= 0:
        return ""
    segs, legend = [], []
    for i, (lbl, v) in enumerate(rows):
        share = v / total * 100
        hue = SERIES_COLORS[i % len(SERIES_COLORS)]
        inner = (f'{fmt_int(round(share))}%' if share >= min_label_share else "")
        segs.append(
            f'<span title="{_html.escape(lbl)}: {_html.escape(str(value_fmt(v)))} '
            f'({fmt_int(round(share))}%)" '
            f'style="flex:0 0 {share:.3f}%;display:flex;align-items:center;'
            f'justify-content:center;background:{hue};color:#08080e;'
            f'font-size:0.72rem;font-weight:700;overflow:hidden;">{inner}</span>'
        )
        legend.append(
            f'<span style="display:inline-flex;align-items:center;gap:0.4rem;'
            f'font-size:0.78rem;color:{MUTED};min-width:0;">'
            f'<span style="flex:none;width:0.6rem;height:0.6rem;border-radius:2px;'
            f'background:{hue};"></span>'
            f'<span style="color:{INK};overflow:hidden;text-overflow:ellipsis;'
            f'white-space:nowrap;">{_html.escape(lbl)}</span>'
            f'<span style="flex:none;font-variant-numeric:tabular-nums;">'
            f'{_html.escape(str(value_fmt(v)))} · {fmt_int(round(share))}%</span>'
            f'</span>'
        )
    return (
        '<div class="pmg-share">'
        '<span style="display:flex;height:30px;border-radius:6px;overflow:hidden;'
        'background:rgba(255,255,255,0.06);">' + "".join(segs) + '</span>'
        '<span style="display:flex;flex-wrap:wrap;gap:0.4rem 1.1rem;'
        'margin-top:0.55rem;">' + "".join(legend) + '</span>'
        '</div>'
    )


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


def _cells_html(cells: Sequence, tints: Sequence | None,
                columns: Sequence[str], *, header: bool = False) -> str:
    """The right-hand strip of small numbers on a row that carries columns.

    Each cell carries its own column name in a span that is hidden on a laptop,
    where the header row above already names it, and shown on a phone, where
    the halves stack and the header is gone. Without it a stacked row would be
    seven bare numbers.
    """
    cols = [(c, c) if isinstance(c, str) else (c[0], c[1]) for c in columns]
    n = len(cols)
    parts = []
    for i in range(n):
        label, full = cols[i]
        text = "" if i >= len(cells) else ("" if cells[i] is None else str(cells[i]))
        tint = None
        if tints and i < len(tints) and tints[i]:
            tint = STATUS.get(_STATUS_ALIAS.get(str(tints[i]).lower(), ""), None)
        color = MUTED if header else (tint or INK)
        weight = "600" if (tint or header) else "500"
        size = "0.68rem" if header else "0.8rem"
        key = (f'<i class="pmg-cell-k" style="font-style:normal;color:{MUTED};'
               f'font-weight:500;font-size:0.68rem;">'
               f'{_html.escape(str(label))} </i>') if not header else ""
        # Seven columns share about 600px, so a header is trimmed to fit and
        # carries its full name on hover. The same title rides on every value,
        # which is what a reader hovers first.
        title = f' title="{_html.escape(str(full))}"' if full else ""
        parts.append(
            f'<span{title} style="color:{color};font-weight:{weight};font-size:{size};'
            f'text-align:right;font-variant-numeric:tabular-nums;overflow:hidden;'
            f'text-overflow:ellipsis;white-space:nowrap;">'
            f'{key}{_html.escape(str(label)) if header else ""}{_html.escape(text)}</span>'
        )
    return (
        f'<span class="pmg-rank-cells" style="display:grid;'
        f'grid-template-columns:repeat({n},minmax(0,1fr));gap:0.5rem;'
        f'align-items:center;">' + "".join(parts) + '</span>'
    )


def change_text(change: dict | None) -> tuple[str, str]:
    """A ``period_delta`` result as ``("↑ 12%", colour)`` — the short form a
    ranked row's change column takes.

    The same rules as the arrows on the KPI cards, so a red down-arrow means
    one thing on every page. A severe drop is red, an ordinary one amber, a
    move inside the neutral band a grey "→", and a small count prints its
    absolute change rather than a percentage of almost nothing.

    Lived in ki_drilldown until the nightly rows (plan step D3) became its
    second caller; it belongs beside ``ranked_list``, which is what consumes it.
    """
    if not change:
        return "", MUTED
    direction = int(change.get("direction", 0))
    pct, show = change.get("pct"), change.get("show")
    severe = pct is not None and pct < SEVERE_DROP_PCT
    if direction > 0:
        color, arrow = STATUS["good"], "↑"
    elif direction == 0:
        color, arrow = MUTED, "→"
    else:
        color, arrow = (STATUS["bad"] if severe else STATUS["warn"]), "↓"
    if show == "absolute" and change.get("change") is not None:
        n = round(float(change["change"]))
        text = f"{'+' if n > 0 else ''}{fmt_int(n)}"
    elif pct is not None:
        text = f"{fmt_int(abs(pct))}%"
    else:
        return "", MUTED
    return f"{arrow} {text}", color


def ranked_list(rows: Sequence[dict], *, value_fmt: Callable = fmt_int,
                bar_max: float | None = None,
                href: Callable[[dict], str | None] | None = None,
                columns: Sequence[str] | None = None) -> str:
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

    ``spark`` (a list of numbers, oldest first) draws a sparkline under the
    name — the shape behind the one number at the right. ``title`` overrides
    what the name shows on hover, for a row with something more to say than its
    own name (the nightly rows' landing projection, plan step D3).

    ``columns`` turns the row into a comparison across several measures at
    once. Each entry is a label, or a ``(label, full name)`` pair where the
    label had to be trimmed to fit — seven columns share about 600px, and the
    full name then rides on hover — the Panel's four zones against the seven Key Indicators (plan step
    C3). Each row then carries ``cells``, a list of already-formatted strings
    the same length as ``columns``, and optionally ``cell_status``, a matching
    list of "good"/"bad"/None that tints the best and worst in each column.
    A header row names the columns above the list. The strip takes the row's
    right half on a laptop and its own second line on a phone, which is what a
    nine-column table could not do — the zone table was 766px wide at 375px and
    scrolled the whole page sideways (audit P5).
    """
    rows = list(rows)
    if not rows:
        return ""
    n_cells = len(columns) if columns else 0
    bars = []
    for r in rows:
        b = r.get("bar", r.get("value"))
        try:
            bars.append(None if b is None else float(b))
        except (TypeError, ValueError):
            bars.append(None)
    full = bar_max if bar_max else (max([b for b in bars if b is not None] + [0]) or 1.0)

    out = ['<div class="pmg-ranked">']
    if n_cells:
        # The header sits over the cells half only, indented past the rank, the
        # dot and the name so each label lands on its own column.
        out.append(
            f'<div class="pmg-rank-head" style="display:grid;'
            f'grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:0.7rem;'
            f'padding:0 0.9rem 0.3rem 0.9rem;">'
            f'<span></span>{_cells_html([], None, columns, header=True)}'
            f'</div>'
        )
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

        if n_cells:
            # Two halves: who and how much on the left, the columns on the
            # right. The halves stack on a phone (see .pmg-rank-row-cells in
            # the stylesheet), so seven numbers never force a sideways scroll.
            #
            # A row that carries columns usually has no separate headline
            # number: the quantity it is ranked on is already one of the
            # columns, and printing it twice on one line reads as a mistake.
            # Omit ``value`` and the bar under the name carries the ranking on
            # its own.
            has_value = "value" in r
            left_cols = ("1.6rem 0.6rem minmax(0,1fr) auto" if has_value
                         else "1.6rem 0.6rem minmax(0,1fr)")
            value_html = (
                f'<span style="color:{INK};font-weight:700;font-size:0.95rem;'
                f'text-align:right;min-width:3.2rem;font-variant-numeric:tabular-nums;">'
                f'{_html.escape(shown)}</span>' if has_value else ""
            )
            out.append(
                f'<{tag} class="pmg-rank-row pmg-rank-row-cells"{attrs} '
                f'style="display:grid;'
                f'grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);'
                f'align-items:center;gap:0.7rem;background:{bg};border-radius:8px;'
                f'padding:0.55rem 0.9rem;margin-bottom:0.35rem;color:inherit;'
                f'text-decoration:none;{"cursor:pointer;" if link else ""}">'
                f'<span style="display:grid;'
                f'grid-template-columns:{left_cols};'
                f'align-items:center;gap:0.7rem;min-width:0;">'
                f'<span style="text-align:right;color:#6b7280;font-size:0.8rem;">{_html.escape(str(rank))}</span>'
                f'<span style="width:0.6rem;height:0.6rem;border-radius:50%;background:{dot};"></span>'
                f'<span style="min-width:0;">'
                f'<span title="{_html.escape(str(r.get("name", "")))}" '
                f'style="display:block;color:{INK};font-weight:600;font-size:0.92rem;'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
                f'{_html.escape(str(r.get("name", "")))}</span>'
                + (f'<span style="display:block;color:{MUTED};font-size:0.75rem;">'
                   f'{_html.escape(str(sub))}</span>' if sub else "")
                + f'<span style="display:block;height:6px;margin-top:5px;border-radius:3px;'
                f'background:rgba(255,255,255,0.06);overflow:hidden;">'
                f'<span style="display:block;height:100%;width:{width:.1f}%;'
                f'background:{dot};border-radius:3px;"></span></span>'
                f'</span>'
                + value_html
                + f'</span>'
                + _cells_html(r.get("cells") or [], r.get("cell_status"), columns)
                + f'</{tag}>'
            )
            continue

        # The sparkline rides UNDER the name rather than in a column of its
        # own: the row is already six columns wide at 1400px, and a seventh
        # would have to be hidden on a phone — where the shape is exactly as
        # useful as it is on a laptop.
        spark_html = _spark(
            [v for v in (r.get("spark") or []) if v is not None], width=104,
            height=18) if r.get("spark") else ""
        name = str(r.get("name", ""))
        hover = str(r.get("title") or name)
        out.append(
            f'<{tag} class="pmg-rank-row"{attrs} style="display:grid;'
            f'grid-template-columns:1.6rem 0.6rem minmax(0,1fr) minmax(48px,26%) auto auto;'
            f'align-items:center;gap:0.7rem;background:{bg};border-radius:8px;'
            f'padding:0.55rem 0.9rem;margin-bottom:0.35rem;color:inherit;'
            f'text-decoration:none;{"cursor:pointer;" if link else ""}">'
            f'<span style="text-align:right;color:#6b7280;font-size:0.8rem;">{_html.escape(str(rank))}</span>'
            f'<span style="width:0.6rem;height:0.6rem;border-radius:50%;background:{dot};"></span>'
            f'<span style="min-width:0;">'
            f'<span class="pmg-rank-name" title="{_html.escape(hover)}" '
            f'style="display:block;color:{INK};font-weight:600;font-size:0.92rem;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{_html.escape(name)}</span>'
            + (f'<span style="display:block;color:{MUTED};font-size:0.75rem;">{_html.escape(str(sub))}</span>' if sub else "")
            + spark_html
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
