"""
11_Informes.py
────────────────────────────────────────────────────────────────────────────────
El informe de consejo — una unidad, un período, los mismos números que imprime
el paquete.

Esta página no calcula nada. `app/reports/model.build_report()` arma el
`ReportModel` y aquí sólo se dibuja; `app/reports/packet.py` dibuja el mismo
modelo en PDF. Es lo único que impide que la hoja impresa y la pantalla digan
cosas distintas de la misma semana (PLAN-2026-09-21-informes.md, decisión 30).

Lo que reemplazó: un selector de semana suelto, tres tablas, dos botones CSV y
una lectura de `get_daily_log(365)` que traía un año entero para mostrar siete
días (hallazgo F9 de la auditoría). Nada de eso sobrevive.

Español solamente, sin `t()` (decisión 3): el público son dos lectores que leen
en español, las cadenas son el vocabulario propio de la misión, y pasar cuarenta
literales por `t()` agregaría cuarenta claves en inglés que nadie va a leer. Los
componentes compartidos traen su propia traducción. El marcador de abajo es lo
que exime a este archivo del control de cobertura de traducción — ver
`tools/i18n_coverage.SPANISH_ONLY_MARKER`.

i18n: spanish-only
"""

from __future__ import annotations

import streamlit as st

from app.auth.auth import require_auth
from app.components.charts import (ranked_list, share_bar, spark_multiples,
                                   stage_bars)
from app.components.design_system import (
    render_companionship_card, render_kpi_row, render_page_header,
    render_section_label, render_section_tabs,
)
from app.components.ki_drilldown import ki_href, render_ki_drilldown
from app.components.scope_selector import ANY, render_scope_selectors
from app.config import es_display
from app.i18n.formats import NA, fmt_int, fmt_number, fmt_percent
from app.reports import model as M
from app.reports import periods as P
from app.reports import scope as S

# Page chrome (set_page_config / inject_global_css / render_sidebar) is owned by
# Home.py's st.navigation router since 2026-09-02 — the router and this page
# share one script run, so calling them here would render twice.
user = require_auth()


# ── Data, once ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Leyendo la misión…")
def _load():
    """Every frame the report reads, once per five minutes.

    `ReportData` memoises the goal lookups inside itself, so the cache also
    keeps those. The packet builds 63 scopes off one of these; the screen
    builds one.
    """
    return M.load_data()


_data = _load()

render_page_header("Informes", f"{_data.mission_name} — informe de consejo")

if _data.roster is None or _data.roster.empty:
    st.info("MISSION_ORG está vacío. Sin el organigrama no hay unidades que "
            "informar.")
    st.stop()


# ── The control bar (§3.1) ────────────────────────────────────────────────────

_zone, _district, _area, _level = render_scope_selectors(_data.roster,
                                                         prefix="rep")
_scope = S.resolve(
    _data.roster, _level,
    zone=None if _zone == ANY else _zone,
    district=None if _district == ANY else _district,
    area=None if _area == ANY else _area,
    mission_name=_data.mission_name,
)
if _scope is None:
    st.warning("Esa unidad ya no está en MISSION_ORG.")
    st.stop()

# Periods the schedule can actually supply — a label is simply absent rather
# than resolving to an empty page (`periods.available`).
_period_keys = P.available(_data.today, _data.cycles)
if not _period_keys:
    st.info("No hay ningún período que informar todavía.")
    st.stop()

# The transfer leads, because the transfer is the unit the mission plans and is
# judged in (decisión 5). `render_section_tabs` would otherwise open on the
# first option in the list, which is the display order, not the default.
st.session_state.setdefault("rep_period_section", P.DEFAULT_PERIOD)
_period_key = render_section_tabs(
    {k: P.PERIOD_LABELS[k] for k in _period_keys},
    key="rep_period_section", per_row=3,
)
_period = P.resolve(_period_key, _data.today, _data.cycles)

# "Comparar contra" only appears when there is a choice to make: on most
# periods the period's own twin and the weeks before it are the same window,
# and two pills that do the same thing are worse than one.
_compare_keys = P.available_comparisons(_period, _data.today, _data.cycles)
_against = P.COMPARE_PRIOR
if len(_compare_keys) > 1:
    st.caption("Comparar contra")
    _against = render_section_tabs(
        {k: P.COMPARE_LABELS[k] for k in _compare_keys},
        key="rep_compare_section", per_row=2,
    )
_comparison = P.comparison_for(_period, _data.today, _data.cycles,
                               against=_against)

_model = M.build_report(_scope, _period, _comparison, _data)


# ── Generar paquete (P6) ──────────────────────────────────────────────────────
#
# Two controls, not one. `st.download_button` needs the bytes in hand before it
# is drawn, and building them takes about a minute on the live sheet — 63
# models and 108 pages — so a download button alone would rebuild the whole
# packet on every rerun of the page, including the reruns a pill click causes.
# The first button builds and parks the result; the second hands it over.
#
# The packet is the whole mission, always (decisión 1), whatever unit the
# selectors point at: it contains that unit's pages either way, and a packet
# whose contents changed with a dropdown would be a different document under
# the same name.

#: Where the built packet waits between the two clicks, keyed by the period it
#: was built for — so changing the período pill offers a fresh build rather
#: than yesterday's bytes under today's label.
_PACKET_KEY = "rep_packet"


def _render_packet_control() -> None:
    from app.reports import packet as PK

    left, right = st.columns([1, 2])
    built = st.session_state.get(_PACKET_KEY)
    with left:
        if st.button("Generar paquete", type="primary",
                     use_container_width=True):
            with st.spinner("Armando el paquete — 63 unidades…"):
                try:
                    st.session_state[_PACKET_KEY] = {
                        "period": _period.key,
                        "bytes": PK.build(_period.key, _against, data=_data),
                        "name": PK.filename(_model),
                    }
                except Exception as exc:          # noqa: BLE001 - shown, not hidden
                    st.session_state.pop(_PACKET_KEY, None)
                    st.error(f"No se pudo armar el paquete: {exc}")
            built = st.session_state.get(_PACKET_KEY)
    with right:
        if built and built.get("period") == _period.key:
            size = len(built["bytes"]) / 1024
            st.download_button(
                f"Descargar · {built['name']} ({fmt_int(size)} KB)",
                data=built["bytes"], file_name=built["name"],
                mime="application/pdf", use_container_width=True)
        else:
            st.caption("Todo el consejo en un PDF: la misión, las 4 zonas, los "
                       "13 distritos y las 45 áreas, con su guía de impresión.")


_render_packet_control()

#: What a drill-down link has to carry to come back to this unit.
_SCOPE_PARAMS = {
    "rep_zone": _scope.zone or "",
    "rep_district": _scope.district or "",
    "rep_area": _scope.name if _scope.level == S.AREA else "",
}

st.caption(f"{_model.scope.name} · {_model.subtitle}")

# ── The companionship, when the unit IS one (decisión 27) ────────────────────
#
# One companionship per area, so the area view is the companionship view and
# has their names on it. Per-missionary history is explicitly out of scope.
if _scope.level == S.AREA:
    _row = _data.roster[
        _data.roster["Area_Name"].astype(str).str.strip() == _scope.name]
    if not _row.empty:
        render_companionship_card(_row.iloc[0], zone=_scope.zone or "",
                                  district=_scope.district or "")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct(value) -> str:
    return NA if value is None else fmt_percent(value)


def _comparison_note() -> str:
    """Why a comparison is absent, or how thin it is — decision 6.

    A partial comparison is SHOWN, with its coverage stated; only a window
    with nothing in it becomes "sin comparación". The two readings are
    different and the caption has to be able to say which one it is.
    """
    if not _model.comparison:
        return _model.comparison.reason or "Sin comparación."
    cov = _model.comparison_coverage
    if cov is None or not cov.usable:
        return (f"Sin comparación: {_comparison.period.label} no tiene "
                f"informes.")
    text = f"Comparado con {_comparison.period.label} · {cov.label}"
    if cov.reporting_rate is not None:
        text += f" · {fmt_percent(cov.reporting_rate * 100)} de los informes"
    if cov.thin:
        text += " — apenas un puñado de áreas: sin base para el cambio"
    return text


def _ki_cards() -> list[dict]:
    """The seven, as goal-bar cards.

    The bar fills against the companionships' own meta and the leadership
    transfer goal rides as a second violet tick (decisión 11) — identical to
    Panel and Desgloses, one vocabulary app-wide.
    """
    # Decision 38: a thin comparison is no base at all. The card says so
    # instead of drawing a coloured arrow off one area's fortnight — the
    # packet's rule, so the page and the paper cannot disagree about it.
    comparable = (_model.comparison_coverage is not None
                  and _model.comparison_coverage.usable
                  and not _model.comparison_coverage.thin)
    cards = []
    for row in _model.key_indicators:
        card = {
            "label": row.label,
            "value": row.actual if row.actual is not None else 0,
            # The link carries this page's scope so the full reload it causes
            # lands back on the same unit (`scope_selector.SCOPE_PARAMS`).
            "href": ki_href(row.key, _SCOPE_PARAMS),
        }
        if row.meta:
            card["goal"] = row.meta
        if row.has_leadership_goal:
            card["mark"] = row.leadership_goal
            card["mark_label"] = "meta de liderazgo"
        elif row.leadership_goal_areas or row.meta:
            card["note"] = (f"sin meta de traslado · "
                            f"{fmt_int(row.leadership_goal_areas)} de "
                            f"{fmt_int(_model.scope.area_count)} áreas")
        if row.grade.flag:
            card["note"] = row.grade.flag_label
        if row.grade.change_pct is not None and comparable:
            card["delta"] = row.grade.change_pct
        else:
            card["change_note"] = "sin base este período"
            card["change_note_title"] = _comparison_note()
        cards.append(card)
    return cards


#: Whether the comparison window holds enough nights for a nightly change to
#: mean anything. DAILY_LOG begins 2026-08-09, so the default comparison for
#: this transfer — 2026-5's first two weeks — holds almost none, and a movement
#: measured across it is one area's evening standing for the mission.
_NIGHTLY_COMPARABLE = (_model.comparison_nightly_coverage is not None
                       and _model.comparison_nightly_coverage.usable
                       and not _model.comparison_nightly_coverage.thin)


def _change_cell(row) -> str:
    """A metric's movement as a short arrow string, or why there is none."""
    if row.grade.change_pct is None or not _NIGHTLY_COMPARABLE:
        return NA
    arrow = {"good": "↑", "bad": "↓"}.get(row.grade.status, "→")
    return f"{arrow} {fmt_percent(abs(row.grade.change_pct))}"


def _ranked_units(units) -> str:
    """Child units or areas as ranked rows, weakest first.

    One function for both tables so a zone's districts and a zone's areas read
    identically. Every cell is attainment per ACTIVE area — the same basis as
    the headline beside it, so a row's cells average to its own value.
    """
    return ranked_list([{
        "name": c.name,
        "rank": c.rank,
        "sub": (f"{c.coverage.label} · "
                f"{fmt_percent((c.coverage.reporting_rate or 0) * 100)} de "
                f"los informes"
                + (f" · {fmt_int(len(c.areas_silent))} sin informar"
                   if c.areas_silent else "")),
        "value": c.mean_attainment,
        "bar": c.mean_attainment,
        "cells": [_pct(next((m.attainment_per_active_area
                             for m in c.metrics if m.key == r.key), None))
                  for r in _model.key_indicators],
    } for c in units],
        value_fmt=lambda v: NA if v is None else fmt_percent(v),
        columns=[(r.label[:14], r.label) for r in _model.key_indicators],
    )


def _ladder_rows() -> str:
    """The unit against every scale above it — Zackary, 2026-09-23.

    A zone reads against the mission's averages, a district against its own
    zone's, an area against its district's. The arithmetic is
    `ReportModel.ladder`: the model works it out once so this page and the
    printed packet cannot disagree about the sign of a gap (decisión 30).
    """
    return ranked_list([{
        "name": r.scope.name,
        "rank": "",
        "sub": r.role,
        "value": r.mean_attainment,
        "bar": r.mean_attainment,
        "change": (None if r.delta is None
                   else f"{'+' if r.delta >= 0 else '−'}"
                        f"{fmt_number(abs(r.delta), 0)} pts"),
        "change_color": (None if r.delta is None
                         else "good" if r.delta >= 0 else "bad"),
        "cells": [_pct(next((m.attainment_per_active_area
                             for m in r.metrics if m.key == k.key), None))
                  for k in _model.key_indicators],
    } for r in _model.ladder],
        bar_max=100,
        value_fmt=lambda v: NA if v is None else fmt_percent(v),
        columns=[(r.label[:14], r.label) for r in _model.key_indicators],
    )


def _gap_rows() -> str:
    """Which of the seven is carrying the difference with the unit above.

    The table above says where the scales sit; this says where the gap comes
    from, which is the part a council can act on. Against the PARENT rather
    than the mission: a district is run by its zone, and "eleven points under
    your own zone" is a conversation two people in the room can have.
    """
    parent = next((r for r in _model.ladder[1:] if not r.is_self), None)
    if parent is None or not any(d is not None for d in parent.deltas):
        return ""
    pairs = sorted(zip(parent.metrics, parent.deltas),
                   key=lambda pair: (pair[1] is None, pair[1] or 0))
    return ranked_list([{
        "name": row.label,
        "rank": "",
        "sub": (f"{_pct(row.attainment_per_active_area)} en "
                f"{parent.scope.name}"),
        "value": delta,
        "bar": None if delta is None else abs(delta),
        "status": None if delta is None else "good" if delta >= 0 else "bad",
    } for row, delta in pairs],
        value_fmt=lambda v: (NA if v is None else
                             f"{'+' if v >= 0 else '−'}"
                             f"{fmt_number(abs(v), 0)} pts"),
    )


def _sibling_line() -> str:
    """Where the unit sits among the units beside it, in one sentence.

    The packet draws this as a strip of dots; on screen the ranked table of
    every sibling is one click away in the parent's own view, so the sentence
    carries what the strip is for — the position and the SPREAD. A unit at 34%
    among peers running 31 to 38 has a mission problem; the same 34% among
    peers running 16 to 63 has a problem of its own.
    """
    peers = [c for c in _model.siblings if c.mean_attainment is not None]
    if len(peers) < 2:
        return ""
    mine = next((c for c in peers if c.name == _model.scope.name), None)
    if mine is None:
        return ""
    # No bare ordinal. "1º" means the WEAKEST everywhere else in this app —
    # every ranked table in Compass is most-behind-first — so a line reading
    # "1º de 3" beside a unit at the top of its peers would be read backwards
    # by anybody who had just come from one of those tables.
    noun, article = {"zone": ("zonas", "la"), "district": ("distritos", "el"),
                     "area": ("áreas", "la")}.get(_model.scope.level,
                                                  ("unidades", "la"))
    ending = "a" if article == "la" else "o"
    low = min(c.mean_attainment for c in peers)
    high = max(c.mean_attainment for c in peers)
    if mine.mean_attainment >= high:
        where = f"{article} más fuerte"
    elif mine.mean_attainment <= low:
        where = f"{article} más atrasad{ending}"
    else:
        where = (f"{article} númer{ending} {fmt_int(mine.rank)} contando "
                 f"desde {article} más atrasad{ending}")
    line = (f"{where} de {fmt_int(len(peers))} {noun}, que van de "
            f"{fmt_percent(low)} a {fmt_percent(high)}")
    silent = len(_model.siblings) - len(peers)
    if silent:
        line += f" · {fmt_int(silent)} sin lectura"
    return line


def _nightly_rows(rows) -> str:
    """Every tracked nightly metric as ranked rows, furthest behind first.

    A ranked list rather than a table: nine columns at 375px is 892px of
    sideways scrubbing, which is the measurement that put `ranked_list`'s
    wrapping cell strip into the design system in the first place (auditoría
    P5). The strip takes the row's right half on a laptop and its own second
    line on a phone.

    The two per-area rates both appear because they answer different
    questions, and the difference between them is the news: "por área activa"
    counts the areas that did not report, "por área que informó" does not.
    """
    return ranked_list([{
        "name": r.label,
        "rank": i,
        "sub": (f"meta {fmt_number(_data.nightly_goals.get(r.key), 0)}/área/sem"
                if _data.nightly_goals.get(r.key)
                else "sin meta configurada")
               + (f" · {r.grade.flag_label}" if r.grade.flag else ""),
        "value": r.actual,
        "bar": r.grade.pct,
        # No colour either when the movement it would report is not real.
        "status": r.grade.status if _NIGHTLY_COMPARABLE else None,
        "cells": [
            _pct(r.grade.pct),
            (fmt_number(r.per_active_area_week, 1)
             if r.per_active_area_week is not None else NA),
            (fmt_number(r.per_reporting_area_week, 1)
             if r.per_reporting_area_week is not None else NA),
            _change_cell(r),
        ],
    } for i, r in enumerate(rows, start=1)],
        # Counts print whole; only the 1-3 effort score has a decimal to show.
        value_fmt=lambda v: (NA if v is None else
                             fmt_int(v) if float(v) == int(v)
                             else fmt_number(v, 1)),
        columns=[("% meta", "% de la meta configurada"),
                 ("/activa", "por área activa por semana"),
                 ("/informó", "por área que informó por semana"),
                 ("cambio", "contra el período de comparación")],
    )


# ── 1 · Indicadores Clave ─────────────────────────────────────────────────────

render_section_label(
    "Indicadores Clave", right=_model.subtitle,
    info=("Los siete, siempre, en cada nivel. La barra se llena contra la meta "
          "que las compañías se pusieron en el formulario de la semana "
          "anterior; la marca violeta es la meta del traslado que fija el "
          "liderazgo. El porcentaje reduce ambos lados a un promedio por área "
          "que informó antes de dividir — 39 áreas fijaron las metas de la "
          "semana que terminó el 20 de septiembre y 27 entregaron resultados, "
          "así que sumar y dividir daría un número sin sentido. "
          + _comparison_note()),
)

if not _model.coverage.usable:
    st.info(f"Ninguna área de {_model.scope.name} entregó el formulario "
            f"semanal en este período.")
else:
    render_kpi_row(_ki_cards())
    st.caption(_comparison_note())

# The same drill-down Panel and Desgloses open (decisión 28), on this page's
# own scope. It owns the metric; this page owns which areas.
render_ki_drilldown("scope", _model.scope.name, _model.scope.areas,
                    key="rep_ki")


# ── 1b · Contra la escala de arriba ──────────────────────────────────────────
#
# Zackary, 2026-09-23: cada zona contra el promedio de la misión y cada
# distrito contra el promedio de su zona. El modelo arma la escalera
# (`ReportModel.ladder`) y aquí sólo se dibuja.

if _model.ladder:
    _above = [r.role for r in _model.ladder[1:] if not r.is_self]
    _head = ", ".join(_above[:-1])
    render_section_label(
        "Contra " + (f"{_head} y {_above[-1]}" if _head else _above[-1]),
        right="cada celda por área activa",
        info=("Un porcentaje no dice nada por sí solo: un 73% es bueno si la "
              "zona va en 60 y malo si va en 85. Estas filas son la misma "
              "medida en cada escala a la que se puede leer — por ÁREA "
              "ACTIVA, la única base en la que dos unidades de distinto "
              "tamaño se pueden comparar. Una unidad que no informó no tiene "
              "lectura y no tiene diferencia: restarle su propio silencio "
              "sería hablar del formulario, no del trabajo."),
    )
    st.markdown(_ladder_rows(), unsafe_allow_html=True)
    _gaps = _gap_rows()
    if _gaps:
        st.caption(f"Dónde está la diferencia con "
                   f"{_model.ladder[1].scope.name}, en puntos porcentuales")
        st.markdown(_gaps, unsafe_allow_html=True)
    _beside = _sibling_line()
    if _beside:
        st.caption(f"Y de lado: {_beside}")


# ── 2 · Semana a semana ───────────────────────────────────────────────────────

render_section_label(
    "Semana a semana", right=_model.period.label,
    info=("Cada indicador por semana completa. Una semana que nadie informó "
          "no aparece como cero: no es un cero, es una semana sin datos. Las "
          "líneas punteadas marcan el inicio de un traslado."),
)

_series = [s for s in _model.series.values() if s.reported_points]
if not _series:
    st.info("Todavía no hay semanas completas con datos en este período.")
else:
    st.markdown(
        spark_multiples(
            {s.label: [p.actual for p in s.points] for s in _series},
            caption=lambda name: next(
                (f"{len(s.reported_points)} de {len(s.points)} "
                 f"{'semana' if len(s.points) == 1 else 'semanas'}"
                 for s in _series if s.label == name), ""),
        ),
        unsafe_allow_html=True,
    )
    # B8: how many areas filed each week, under the lines it qualifies. The
    # packet prints it as the week table's last row; here it is the first
    # thing under the sparks, because a week where nine fewer companionships
    # sent a form draws the same dip as a week of less work.
    _filed = [(p.week, p.reporting) for p in _series[0].points]
    _counts = [n for _, n in _filed if n is not None]
    if _counts:
        _of = fmt_int(_model.scope.area_count)
        if len(_filed) <= 6:
            _weeks = " · ".join(
                f"{es_display.day_month(w)}: {fmt_int(n) if n is not None else NA}"
                for w, n in _filed)
            st.markdown(f"**Áreas que informaron, de {_of}** — {_weeks}")
        else:
            st.markdown(f"**Áreas que informaron, de {_of}** — entre "
                        f"{fmt_int(min(_counts))} y {fmt_int(max(_counts))} "
                        f"por semana")
    for _mark, _number in _series[0].boundaries:
        st.caption(f"Inicio del traslado {_number}: {_mark}")


# ── 3 · Las unidades, de la más débil a la más fuerte ────────────────────────

_child_label = {"mission": "Zonas", "zone": "Distritos",
                "district": "Áreas"}.get(_model.scope.level)

if _model.children and _child_label:
    render_section_label(
        _child_label, right="de la más débil a la más fuerte",
        info=("Ordenadas por el promedio de sus siete indicadores contra las "
              "metas de sus compañías, medido POR ÁREA ACTIVA — una unidad "
              "donde la mitad de las áreas no informó baja en la tabla, a "
              "propósito. No se corta la lista: aparecen todas. Una unidad sin "
              "nada medido queda al final, no al principio: no es la más "
              "débil, es la que no sabemos."),
    )
    st.markdown(_ranked_units(_model.children), unsafe_allow_html=True)


# ── 3b · Su fortaleza · Para crecer ──────────────────────────────────────────

if _model.strengths or _model.growth:
    render_section_label(
        "Su fortaleza · Para crecer", right=_model.period.label,
        info=("Lo eligen los agentes de Apps Script y queda escrito en "
              "WEEKLY_BREAKDOWNS semana a semana; esta página lo LEE, no lo "
              "vuelve a calcular. Si se recalculara aquí, la compañía leería "
              "una cosa en su correo y otra en esta pantalla."),
    )
    render_kpi_row(
        [{"label": "Su fortaleza", "value": _s} for _s in _model.strengths]
        + ([{"label": "Para crecer", "value": _model.growth}]
           if _model.growth else [])
    )


# ── 3c · Todas las áreas ─────────────────────────────────────────────────────

if _model.areas_ranked:
    render_section_label(
        "Todas las áreas", right=f"{fmt_int(len(_model.areas_ranked))} áreas",
        info=("Cada área de la unidad, de la más débil a la más fuerte. Sin "
              "cortes: aparecen todas, aunque en la misión sean cuarenta y "
              "cinco — por eso van detrás de un cajón y no en la página."),
    )
    with st.expander(f"Ver las {fmt_int(len(_model.areas_ranked))} áreas"):
        st.markdown(_ranked_units(_model.areas_ranked), unsafe_allow_html=True)


# ── 4 · Trabajo nocturno ──────────────────────────────────────────────────────

render_section_label(
    "Trabajo nocturno", right=(_model.nightly_coverage.label if
                               _model.nightly_coverage else ""),
    info=("Todas las métricas del formulario nocturno, no una lista corta. El "
          "estado sale del MOVIMIENTO contra el período de comparación, no de "
          "la meta: medidas contra sus metas, las veinte métricas van del 6% "
          "al 67%, y graduarlas con la banda 90/60 pintaría diecisiete filas "
          "rojas todas las semanas. La meta sigue impresa, y si deja de servir "
          "de vara se marca en lugar de calificarse."),
)

if not _model.nightly_metrics:
    st.info("No hay actividad nocturna en este período.")
else:
    st.markdown(_nightly_rows(_model.nightly_weakest_first),
                unsafe_allow_html=True)
    if not _NIGHTLY_COMPARABLE:
        _ncov = _model.comparison_nightly_coverage
        if not _model.comparison:
            _why = _model.comparison.reason or "no hay período que comparar."
        elif _ncov and _ncov.usable:
            _why = f"{_comparison.period.label} sólo tiene {_ncov.label}."
        else:
            _why = f"{_comparison.period.label} no tiene noches informadas."
        st.caption("Sin cambio nocturno: " + _why
                   + " El formulario nocturno empezó el 9 de agosto de 2026.")
    if _model.nightly_coverage and _model.nightly_coverage.rate is not None:
        st.caption(
            f"{_model.nightly_coverage.label} "
            f"({fmt_percent(_model.nightly_coverage.rate * 100)}) · "
            f"{fmt_int(_model.nightly_coverage.areas_reporting)} de "
            f"{fmt_int(_model.nightly_coverage.areas_in_scope)} áreas "
            f"informaron al menos una noche."
        )


# ── 4b · Hallazgo (decisiones 20, 24, 32, 34) ────────────────────────────────
#
# La misma sección que imprime el paquete, del mismo `model.tableau`. La
# diferencia entre pantalla y papel es sólo el dibujo: aquí `charts.stage_bars`
# con su barra gemela, allá `packet_parts.stage_bars` con su columna de cambio.

_BLOCK = _model.tableau


def _finding_units() -> str:
    """Las unidades de la sección de hallazgo, peor tasa de contacto primero.

    Por tasa y no por personas encontradas: encontradas es un tamaño — una
    zona grande encuentra más — y lo accionable es qué proporción de esa gente
    los misioneros alcanzaron a contactar.
    """
    return ranked_list([{
        "name": u.name,
        "rank": i if u.found else None,
        "sub": " · ".join(x for x in (
            ("zona piloto de Compass" if u.roster else
             "sin formularios de Compass") if _BLOCK.whole_mission else "",
            "" if u.found else "nadie encontrado en la ventana") if x),
        "value": u.contact_rate,
        "bar": u.contact_rate,
        "cells": [fmt_int(u.found), fmt_int(u.teaching),
                  _pct(u.teaching_rate)],
    } for i, u in enumerate(_BLOCK.units, start=1)],
        value_fmt=lambda v: NA if v is None else fmt_percent(v),
        columns=[("encontradas", "personas encontradas en la ventana"),
                 ("enseñándose", "de ellas, cuántas reciben lecciones"),
                 ("% enseñ.", "enseñándose sobre encontradas")],
    )


if _BLOCK is not None:
    render_section_label(
        "Hallazgo",
        right=(_BLOCK.window.caption if _BLOCK.present else "sin datos"),
        info=("Viene de Tableau, no de los formularios de Compass, y las dos "
              "cifras nunca se suman ni comparten una tabla (decisión 34). "
              "La ventana es la del período recortada a lo que alcanza la "
              "exportación guardada: si no alcanza, la sección no se dibuja y "
              "dice por qué."),
    )
    st.caption(_BLOCK.export.freshness_label(_model.today))

    if not _BLOCK.present:
        st.info(f"Sin sección de hallazgo: {_BLOCK.reason}. Las cifras de "
                f"Tableau no se estiman ni se rellenan con el período "
                f"anterior.")
    else:
        st.caption(_BLOCK.scope_note)
        _stages = _BLOCK.stages
        st.markdown(stage_bars(
            [(x.label, x.count) for x in _stages],
            highlight_worst=True,
            mature=[x.mature for x in _stages],
            twin=[x.before for x in _stages],
            twin_label=(_BLOCK.before.label if _BLOCK.before
                        and _BLOCK.before.usable else None),
        ), unsafe_allow_html=True)
        st.caption(
            "Cada barra son las personas encontradas en esta ventana que han "
            "llegado al menos hasta ahí: una cohorte seguida hacia adelante, "
            "no lo que ocurrió en la ventana."
            + (f" La barra tenue es la misma cantidad de días justo antes "
               f"({_BLOCK.before.label})."
               if _BLOCK.before and _BLOCK.before.usable else ""))
        if _BLOCK.maturity_note:
            st.caption(_BLOCK.maturity_note)

        if _BLOCK.mix:
            st.markdown(share_bar([(m.label, m.count) for m in _BLOCK.mix]),
                        unsafe_allow_html=True)
            st.caption("Quién las encontró — las cuatro categorías de "
                       "Tableau.")

        if _BLOCK.sources:
            _found = _BLOCK.found or 1
            st.markdown(ranked_list([{
                "name": x.label,
                "rank": i,
                "value": x.count,
                "bar": x.count / _found * 100,
                "cells": [_pct(x.count / _found * 100)],
            } for i, x in enumerate(_BLOCK.sources, start=1)],
                columns=[("del total", "sobre las personas encontradas en "
                                       "esta ventana")],
            ), unsafe_allow_html=True)
            st.caption(f"De dónde salieron — las "
                       f"{fmt_int(len(_BLOCK.sources))} fuentes más grandes.")

        if _BLOCK.units:
            st.markdown(_finding_units(), unsafe_allow_html=True)
            st.caption(
                "La barra es la proporción de las personas encontradas que "
                "los misioneros lograron contactar, peor primero."
                + (" Las seis zonas sin formularios de Compass no aparecen en "
                   "ninguna otra parte de esta página."
                   if _BLOCK.whole_mission else ""))


# ── 4c · Bautismos del período, y el año (M6, decisiones 21, 41, 42) ─────────

if _BLOCK is not None and _BLOCK.baptisms is not None:
    _BAP = _BLOCK.baptisms
    _FIG = _BAP.period
    _HAS = _FIG is not None and _FIG.present
    render_section_label(
        f"Bautismos · {_model.period.label}",
        right="cifra certificada · fuente: Tableau",
        info=("La cifra CERTIFICADA de Tableau para los días de este período. "
              "El mes y el año salen de TABLEAU_BAPTISMS; la semana, los "
              "traslados y las últimas seis semanas, de "
              "TABLEAU_BAPTISM_WINDOWS, que la sincronización nocturna llena. "
              "Si no hay captura de estos días no se muestra otra cifra en su "
              "lugar (decisión 42). El formulario semanal pregunta lo mismo y "
              "no coincide, así que aparece aparte, en Indicadores Clave, bajo "
              "su propio nombre."),
    )
    # A refused period shows a dash, never 0: "no certified figure" and "no
    # baptisms" are different facts.
    _cards = [{"label": P.WITHIN_LABELS.get(_model.period.key,
                                            _model.period.label),
               "value": _FIG.count if _HAS else NA,
               "note": (_FIG.window.label if _HAS
                        else "sin cifra certificada")}]
    if _HAS and _FIG.open_count is not None:
        if _FIG.closed is not None:
            _cards.append({"label": "De meses cerrados",
                           "value": _FIG.closed,
                           "note": f"{fmt_int(_FIG.closed_months)} meses"})
        _cards.append({"label": "Del mes en curso", "value": _FIG.open_count,
                       "note": "todavía sin cerrar"})
    elif (_model.period.key != P.YEAR and _BAP.year_to_date is not None
          and _BAP.year_to_date.present):
        _cards.append({"label": f"En lo que va de {_BAP.year}",
                       "value": _BAP.year_to_date.count,
                       "note": _BAP.year_to_date.window.label})
    render_kpi_row(_cards)
    st.caption(_FIG.sentence(_model.period.label) if _FIG is not None
               else "Sin cifra certificada de bautismos (decisión 42).")

    render_section_label(
        f"El año {_BAP.year} contra su meta",
        right="meses cerrados · fuente: Tableau",
        info=("El ritmo y la proyección se miden sobre los meses cerrados. Un "
              "mes a medio contar sumado al ritmo hace que el año parezca "
              "desplomarse cada vez que se abre la página; por eso el mes en "
              "curso está en la cifra de arriba y no aquí."),
    )
    render_kpi_row([
        {"label": f"Bautismos certificados {_BAP.year}",
         "value": _BAP.total if _BAP.total is not None else NA,
         "goal": _BAP.goal,
         "note": (f"{fmt_int(_BAP.months)} meses cerrados"
                  if _BAP.months else "sin meses cerrados")},
        {"label": "Contra el ritmo de la meta",
         "value": round(_BAP.gap, 1) if _BAP.gap is not None else NA,
         "decimals": 1,
         "note": "a esta altura del año"},
        {"label": "Si el año sigue así",
         "value": (round(_BAP.landing["value"])
                   if _BAP.landing else NA),
         "goal": _BAP.goal,
         "note": (f"proyección sobre {fmt_int(_BAP.landing['months'])} meses"
                  if _BAP.landing else "sin proyección")},
    ])
    if _BAP.provisional_label:
        st.caption(f"{_BAP.provisional_label}. Está en la cifra de arriba, "
                   f"no en el ritmo ni en la proyección.")


# ── 5 · Tasas de conversión ───────────────────────────────────────────────────

if _model.rates:
    render_section_label(
        "Tasas de conversión", right=_model.period.label,
        info=("La razón de los totales de la unidad, no el promedio de las "
              "razones de sus áreas: promediar cuarenta áreas deja que un "
              "puñado con pocos contactos y buena suerte levante el número. "
              "Un denominador en cero no es cero por ciento — es que no hubo "
              "lecciones que medir."),
    )
    render_kpi_row([{
        "label": _data.labels.get(r["key"], r["key"]),
        "value": r["value"] if r["value"] is not None else 0,
        "goal": r["target"],
        "unit": "%", "decimals": 1,
        "note": f"{fmt_int(r['numerator'])} de {fmt_int(r['denominator'])}",
        "change": r.get("change"),
        "points_unit": "pp",
    } for r in _model.rates])


# ── 6 · Puntajes ──────────────────────────────────────────────────────────────

if _model.scores and _model.scores.measured:
    render_section_label(
        "Puntajes", right=f"{fmt_int(_model.scores.areas_scored)} áreas "
                          f"calificadas",
        info=("Los cuatro puntajes que escribe CCSM_AgentScores, promediados "
              "sobre las semanas del período. Un área que el agente todavía no "
              "calificó no cuenta como cero: no calificada y calificada en "
              "cero son cosas distintas."),
    )
    _cards = [
        {"label": "Esfuerzo", "value": _model.scores.effort},
        {"label": "Habilidad", "value": _model.scores.skill},
        {"label": "Indicadores Clave", "value": _model.scores.ki},
        {"label": "Efectividad", "value": _model.scores.effectiveness},
    ]
    render_kpi_row([{**c, "value": round(c["value"], 1), "decimals": 1}
                    for c in _cards if c["value"] is not None])
    if _model.scores.rank:
        st.caption(f"{_model.scope.name} va {fmt_int(_model.scores.rank)} de "
                   f"{fmt_int(_model.scores.of)} en su distrito, por "
                   f"efectividad.")


# ── 7 · Quién informó ─────────────────────────────────────────────────────────

render_section_label(
    "Cumplimiento", right=_model.compliance_label,
    info=("Califica todo lo de arriba. Sobre más de una semana se informa la "
          "tasa por área-semana y no cuántas áreas entregaron alguna vez: 39 "
          "de 45 áreas tocaron este traslado, pero sólo 27 entregaron la "
          "segunda semana, y «39 de 45» esconde eso."),
)

render_kpi_row([
    {"label": "Informes semanales",
     "value": _model.coverage.area_weeks_reported,
     "goal": _model.coverage.area_weeks_expected,
     "note": _model.coverage.label},
    {"label": "Noches informadas",
     "value": (_model.nightly_coverage.days_reported
               if _model.nightly_coverage else 0),
     "goal": (_model.nightly_coverage.days_possible
              if _model.nightly_coverage else None),
     "note": (_model.nightly_coverage.label if _model.nightly_coverage else "")},
    {"label": "Áreas sin informe semanal",
     "value": len(_model.areas_silent),
     "note": f"de {fmt_int(_model.scope.area_count)}"},
])

if _model.areas_silent:
    # Named, at every level, the mission included (decisión 16). This packet
    # has two readers.
    st.caption("Sin formulario semanal en este período: "
               + " · ".join(_model.areas_silent))
