"""The one chart language (data-pages plan A2, 2026-09-18).

Every helper in app/components/charts.py returns a figure or an HTML string
without a Streamlit runtime; only chart() touches st, and that is checked by
monkeypatching st.plotly_chart. The point of pinning these is that the three
data pages stop carrying their own layouts: whatever is asserted here is what
every chart on them looks like.
"""

import re

import plotly.graph_objects as go
import pytest

from app.components import charts
from app.components.charts import (
    apply_layout, bars_vs_goal, chart, ranked_list, small_multiples, stage_bars,
)
from app.config.theme import SERIES_COLORS, STATUS


# ── chart() / apply_layout ───────────────────────────────────────────────────

def test_chart_is_the_only_plotly_call_and_hides_the_modebar(monkeypatch):
    calls = []
    monkeypatch.setattr(charts.st, "plotly_chart",
                        lambda fig, **kw: calls.append((fig, kw)))
    fig = go.Figure(go.Bar(x=["a"], y=[1]))
    chart(fig, height=240, key="k1")
    assert len(calls) == 1
    _, kw = calls[0]
    assert kw["use_container_width"] is True
    assert kw["theme"] is None
    assert kw["config"]["displayModeBar"] is False
    assert kw["config"]["responsive"] is True
    assert kw["key"] == "k1"


def test_layout_strips_the_in_chart_title():
    fig = go.Figure(go.Bar(x=["a"], y=[1]))
    fig.update_layout(title="Nightly Activity")
    apply_layout(fig)
    assert not fig.layout.title.text


def test_layout_sets_one_margin_and_the_template():
    fig = go.Figure(go.Bar(x=["a"], y=[1]))
    fig.update_layout(margin=dict(l=140, r=55, t=60, b=150))
    apply_layout(fig)
    m = fig.layout.margin
    assert (m.l, m.r, m.t, m.b) == (44, 16, 8, 36)
    assert fig.layout.template is not None
    assert fig.layout.font.size == 12


def test_layout_never_goes_below_the_minimum_height():
    fig = go.Figure(go.Bar(x=["a"], y=[1]))
    apply_layout(fig, height=100)
    assert fig.layout.height == charts.MIN_HEIGHT
    fig2 = go.Figure(go.Bar(x=["a"], y=[1]))
    fig2.update_layout(height=430)
    apply_layout(fig2)
    assert fig2.layout.height == 430


def test_one_series_gets_no_legend_and_two_get_one_below_the_plot():
    one = go.Figure(go.Bar(x=["a"], y=[1], name="x"))
    apply_layout(one)
    assert one.layout.showlegend is False
    two = go.Figure([go.Bar(x=["a"], y=[1], name="x"),
                     go.Bar(x=["a"], y=[2], name="y")])
    apply_layout(two)
    assert two.layout.showlegend is True
    assert two.layout.legend.orientation == "h"
    assert two.layout.legend.y < 0
    assert two.layout.margin.b > one.layout.margin.b


def test_a_pie_keeps_its_legend_even_as_one_trace():
    pie = go.Figure(go.Pie(labels=["a", "b"], values=[1, 2]))
    apply_layout(pie)
    assert pie.layout.showlegend is True


def test_axes_automargin_so_long_labels_are_not_clipped():
    """Audit E2: two horizontal bar charts with margin l=10 showed two
    letters of every zone name."""
    fig = go.Figure(go.Bar(x=[1], y=["Concepción Centro"], orientation="h"))
    apply_layout(fig)
    assert fig.layout.yaxis.automargin is True
    assert fig.layout.xaxis.automargin is True


def test_caller_axis_settings_survive():
    fig = go.Figure(go.Bar(x=["a"], y=[1]))
    fig.update_layout(yaxis=dict(range=[0, 100], ticksuffix="%"),
                      xaxis=dict(type="category"))
    apply_layout(fig)
    assert list(fig.layout.yaxis.range) == [0, 100]
    assert fig.layout.yaxis.ticksuffix == "%"
    assert fig.layout.xaxis.type == "category"


# ── bars_vs_goal ─────────────────────────────────────────────────────────────

def _traces(fig, kind):
    return [tr for tr in fig.data if tr.type == kind]


def test_bars_are_blue_and_labelled():
    fig = bars_vs_goal(["S1", "S2", "S3"], [10, 12, 8], 15)
    bar = _traces(fig, "bar")[0]
    assert bar.marker.color == SERIES_COLORS[0]
    assert list(bar.text) == ["10", "12", "8"]
    assert bar.textposition == "outside"


def test_a_scalar_goal_is_one_dashed_line_at_that_height():
    fig = bars_vs_goal(["S1", "S2"], [10, 12], 15)
    lines = [s for s in fig.layout.shapes if s.type == "line"]
    assert len(lines) == 1
    assert lines[0].y0 == 15 and lines[0].y1 == 15
    assert lines[0].line.dash == "dash"
    assert lines[0].line.color == STATUS["warn"]


def test_a_per_bucket_goal_is_a_dash_over_each_bar():
    fig = bars_vs_goal(["S1", "S2", "S3"], [10, 12, 8], [15, None, 9])
    lines = [s for s in fig.layout.shapes if s.type == "line"]
    assert len(lines) == 2                    # the None bucket draws nothing
    assert {(round(s.x0 + s.x1) / 2, s.y0) for s in lines} == {(0, 15), (2, 9)}


def test_the_goal_has_a_legend_entry_without_points():
    fig = bars_vs_goal(["S1"], [10], 15, goal_label="Meta")
    legend = [tr for tr in fig.data if tr.type == "scatter" and tr.name == "Meta"]
    assert legend and list(legend[0].x) == [None]


def test_twin_ghost_bars_are_outline_only_and_drawn_first():
    fig = bars_vs_goal(["S1", "S2"], [10, 12], 15, twin=[8, None],
                       twin_label="Cambio 2026-5")
    bars = _traces(fig, "bar")
    assert bars[0].name == "Cambio 2026-5"
    assert bars[0].marker.color == "rgba(0,0,0,0)"
    assert bars[0].marker.line.color == charts.GHOST
    assert bars[0].width > bars[1].width
    assert list(bars[0].y) == [8, 0]
    assert fig.layout.barmode == "overlay"


def test_no_twin_means_no_ghost_trace():
    fig = bars_vs_goal(["S1"], [10], 15)
    assert len(_traces(fig, "bar")) == 1


def test_the_pace_tick_sits_on_the_in_progress_bucket():
    fig = bars_vs_goal(["S1", "S2", "S3"], [10, 12, 4], 15,
                       pace_index=2, pace_value=6)
    tick = [tr for tr in fig.data if tr.type == "scatter"
            and tr.marker.symbol == "line-ew"][0]
    assert list(tick.x) == ["S3"] and list(tick.y) == [6]
    bar = _traces(fig, "bar")[0]
    assert list(bar.marker.opacity) == [1.0, 1.0, 0.55]


def test_the_y_axis_leaves_room_for_the_tallest_of_bar_goal_or_ghost():
    fig = bars_vs_goal(["S1"], [10], 30, twin=[40])
    assert fig.layout.yaxis.range[1] >= 40 * 1.2


# ── small_multiples ──────────────────────────────────────────────────────────

def test_small_multiples_one_panel_per_series_one_hue():
    fig = small_multiples({
        "Nuevas personas": (["w1", "w2", "w3"], [1, 2, 3]),
        "Lecciones":       (["w1", "w2", "w3"], [10, 20, 15]),
        "Amigos":          (["w1", "w2", "w3"], [5, 5, 6]),
    }, cols=2)
    lines = _traces(fig, "scatter")
    assert len(lines) == 3
    assert {tr.line.color for tr in lines} == {SERIES_COLORS[0]}
    assert all(tr.showlegend is False for tr in lines)
    # three panels over two columns: two rows, so two distinct y-axes at least
    assert fig.layout.yaxis2 is not None and fig.layout.yaxis3 is not None


def test_small_multiples_prints_the_last_value():
    fig = small_multiples({"A": (["w1", "w2"], [1, 7])})
    texts = [a.text for a in fig.layout.annotations]
    assert "7" in texts
    assert "A" in texts   # the panel title


def test_small_multiples_skips_a_trailing_none_when_printing():
    fig = small_multiples({"A": (["w1", "w2", "w3"], [1, 7, None])})
    texts = [a.text for a in fig.layout.annotations]
    assert "7" in texts and "None" not in texts


# ── stage_bars ───────────────────────────────────────────────────────────────

def test_stage_bars_write_the_step_conversion_between_rows():
    html = stage_bars([("Encontrados", 200), ("Enseñados", 50), ("Bautizados", 5)])
    convs = re.findall(r'pmg-stage-conv[^>]*>.*?<span>([^<]*)</span>', html)
    assert convs == ["25%", "10%"]
    assert html.count('class="pmg-stage"') == 3


def test_stage_bars_scale_to_the_first_stage():
    html = stage_bars([("A", 200), ("B", 50)])
    widths = re.findall(r"width:([0-9.]+)%", html)
    assert widths == ["100.0", "25.0"]


def test_stage_bars_handle_a_zero_previous_stage():
    html = stage_bars([("A", 0), ("B", 3)])
    assert "—" in html


def test_stage_bars_escape_labels_and_return_empty_for_nothing():
    assert "<script>" not in stage_bars([("<script>x</script>", 1)])
    assert stage_bars([]) == ""


# ── ranked_list ──────────────────────────────────────────────────────────────

def test_ranked_list_row_order_and_parts():
    html = ranked_list([
        {"name": "Zona A", "sub": "16/20 días", "value": 80, "status": "green",
         "change": "↑ 3"},
        {"name": "Zona B", "value": 55, "status": "amber"},
    ], value_fmt=lambda v: f"{int(v)}%", bar_max=100)
    rows = re.findall(r'class="pmg-rank-row"', html)
    assert len(rows) == 2
    assert html.index("Zona A") < html.index("Zona B")
    assert "16/20 días" in html and "↑ 3" in html
    assert "80%" in html and "55%" in html
    assert "width:80.0%" in html and "width:55.0%" in html
    assert STATUS["good"] in html and STATUS["warn"] in html


def test_ranked_list_escapes_names():
    html = ranked_list([{"name": "<img src=x onerror=alert(1)>", "value": 1}])
    assert "<img" not in html


def test_ranked_list_rows_can_be_links():
    html = ranked_list([{"name": "Zona A", "value": 1, "href": "?zone=A"},
                        {"name": "Zona B", "value": 2}],
                       href=lambda r: "?zone=" + r["name"][-1])
    assert re.search(r'<a class="pmg-rank-row" href="\?zone=A"', html)
    assert re.search(r'<a class="pmg-rank-row" href="\?zone=B"', html)


def test_ranked_list_keeps_a_true_rank_when_given_one():
    html = ranked_list([{"rank": 41, "name": "Zona Z", "value": 3}])
    assert ">41<" in html


def test_ranked_list_without_a_value_prints_a_dash_and_no_bar():
    html = ranked_list([{"name": "Zona A", "value": None}])
    assert "—" in html and "width:0.0%" in html


def test_ranked_list_is_empty_for_no_rows():
    assert ranked_list([]) == ""


# ── spark_multiples ──────────────────────────────────────────────────────────

def test_spark_multiples_draws_a_panel_per_metric_with_its_last_value():
    from app.components.charts import spark_multiples

    html = spark_multiples({"Intentos de Contacto": [10, 40, 90],
                            "Contactos": [5, 5, 5]})
    assert html.count("pmg-spark-cell") == 2
    assert html.count("<svg") == 2, "a panel is missing its sparkline"
    assert ">90<" in html and ">5<" in html


def test_spark_multiples_is_a_grid_that_wraps():
    """The reason this exists rather than small_multiples: a Plotly subplot
    grid's column count is fixed when the figure is built, and four columns at
    375px gives each panel about 80px. This is a CSS grid, so it reflows, and
    the phone breakpoint lives in the stylesheet with the KPI grid's."""
    import re

    from app.components import design_system as ds
    from app.components.charts import spark_multiples

    html = spark_multiples({"A": [1, 2], "B": [2, 1]})
    assert "display:grid" in html and "auto-fit" in html
    assert re.search(r"@media \(max-width: ?640px\)[^}]*\{[^}]*\.pmg-sparks",
                     ds._CSS, re.S)


def test_spark_multiples_survives_a_metric_with_no_readings():
    from app.components.charts import spark_multiples

    html = spark_multiples({"Sin datos": [], "Con datos": [1, 2, 3]})
    assert "—" in html, "a metric with no readings must not print a number"
    assert html.count("pmg-spark-cell") == 2


def test_spark_multiples_escapes_its_labels():
    from app.components.charts import spark_multiples

    html = spark_multiples({"<img src=x onerror=alert(1)>": [1, 2]})
    assert "<img" not in html
