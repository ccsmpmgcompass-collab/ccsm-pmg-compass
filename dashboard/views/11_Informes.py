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

from app.analytics import period_delta as _pd
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
    st.info("El organigrama de la misión (pestaña MISSION_ORG) está vacío. "
            "Sin él no hay unidades que informar.")
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
    st.warning("Esa unidad ya no está en el organigrama de la misión.")
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
        # Decision 44, the packet's rule: the bar is against LEADERSHIP's goal
        # over the area-weeks that reported, and the companionships' own goal
        # rides as the violet tick, labelled compromiso — never the colour.
        if row.lead_goal:
            card["value"] = row.lead_actual
            card["goal"] = row.lead_goal
            if row.meta_per_area_week:
                card["mark"] = row.meta_per_area_week * row.lead_area_weeks
                card["mark_label"] = "compromiso"
            if row.key in M.UNCOLOURED_KI:
                card["note"] = "sin color: manda la meta anual"
        else:
            card["note"] = "sin meta del liderazgo para estas semanas"
        # H5, the packet's rule: a small count moves in units, and a move
        # inside Poisson noise is drawn flat and grey.
        if comparable and row.grade.change_count is not None:
            n = round(row.grade.change_count)
            card["change"] = {
                "pct": None, "change": n, "show": _pd.ABSOLUTE,
                "direction": ((1 if n > 0 else -1)
                              if n and row.grade.change_clear else _pd.FLAT)}
        elif comparable and row.grade.change_pct is not None:
            pct = row.grade.change_pct
            card["change"] = {
                "pct": pct, "change": None, "show": _pd.PERCENT,
                "direction": ((1 if pct > 0 else -1)
                              if round(pct) and row.grade.change_clear
                              else _pd.FLAT)}
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
    if not _NIGHTLY_COMPARABLE:
        return NA
    arrow = {"good": "↑", "bad": "↓"}.get(row.grade.status, "→")
    if row.grade.change_count is not None:
        n = round(row.grade.change_count)
        return f"{arrow} {'+' if n > 0 else ''}{fmt_int(n)}"
    if row.grade.change_pct is None:
        return NA
    return f"{arrow} {fmt_percent(abs(row.grade.change_pct))}"


#: The index's members as ranked-list cells, in weight order (decision 45) —
#: the packet's own heads, so the two surfaces name a column the same way.
_INDEX_CELLS = [(k, short) for k, short in (
    ("ki_baptismal_date_real", "Fecha"),
    ("ki_friends_sacrament_real", "Sacr."),
    ("ki_rc_at_church_real", "CR"),
    ("ki_member_lessons_real", "Lecc."),
    ("ki_new_people_real", "Nuevas"),
    ("ki_friends_first_week_real", "1ª sem"),
) if _model.ki(k) is not None]


def _idx(value) -> str:
    return NA if value is None else fmt_int(round(value))


def _index_columns():
    return [(short, _model.ki(k).label) for k, short in _INDEX_CELLS]


def _ranked_units(units) -> str:
    """Child units or areas, least productive first (decision 45).

    One function for both tables so a zone's districts and a zone's areas read
    identically. The value is the productivity index — output per
    companionship-week against the mission's, 100 = the mission — and every
    cell is one of its members on the same scale.
    """
    return ranked_list([{
        "name": c.name,
        "rank": c.rank if c.index.value is not None else "",
        "sub": (f"{c.coverage.label} · "
                f"{fmt_percent((c.coverage.reporting_rate or 0) * 100)} de "
                f"los informes"
                + (f" · {fmt_int(len(c.areas_silent))} sin informar"
                   if c.areas_silent else "")
                + (" · pocas cifras" if c.index.thin
                   and c.index.value is not None else "")),
        "value": c.index.value,
        "bar": c.index.value,
        "cells": [_idx(c.index.ratio(k)) for k, _ in _INDEX_CELLS],
    } for c in units],
        bar_max=200,
        value_fmt=_idx,
        columns=_index_columns(),
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
        "value": r.index.value,
        "bar": r.index.value,
        "change": (None if r.delta is None
                   else f"{'+' if r.delta >= 0 else '−'}"
                        f"{fmt_number(abs(r.delta), 0)} pts"),
        "change_color": (None if r.delta is None
                         else "good" if r.delta >= 0 else "bad"),
        "cells": [_idx(r.index.ratio(k)) for k, _ in _INDEX_CELLS],
    } for r in _model.ladder],
        bar_max=200,
        value_fmt=_idx,
        columns=_index_columns(),
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
    pairs = sorted(zip([k for k, _ in parent.index.members], parent.deltas),
                   key=lambda pair: (pair[1] is None, pair[1] or 0))
    return ranked_list([{
        "name": _model.ki(key).label if _model.ki(key) else key,
        "rank": "",
        "sub": (f"{_idx(parent.index.ratio(key))} en "
                f"{parent.scope.name}"),
        "value": delta,
        "bar": None if delta is None else abs(delta),
        "status": None if delta is None else "good" if delta >= 0 else "bad",
    } for key, delta in pairs],
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
    peers = [c for c in _model.siblings if c.index.value is not None]
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
    low = min(c.index.value for c in peers)
    high = max(c.index.value for c in peers)
    if mine.index.value >= high:
        where = f"{article} más productiv{ending}"
    elif mine.index.value <= low:
        where = f"{article} menos productiv{ending}"
    else:
        where = (f"{article} númer{ending} {fmt_int(mine.rank)} contando "
                 f"desde {article} menos productiv{ending}")
    line = (f"{where} de {fmt_int(len(peers))} {noun}, que van de "
            f"{_idx(low)} a {_idx(high)} (misión = 100)")
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

    The headline is per area that reported, per week — the figure the goal
    and the percentage rest on. "/activa" beside it counts the areas that did
    not report as well, and the gap between the two is the news.
    """
    # The headline value is per area per week on the nights filed — the basis
    # the goal and the percentage use — and the period total moves to the
    # sub-line (AUDIT-2026-10-06 H4, the packet's rule).
    return ranked_list([{
        "name": r.label,
        "rank": i,
        "sub": (f"meta {fmt_number(r.goal_per_area_week, 1)}/área/sem"
                if r.goal_per_area_week
                else "sin meta configurada")
               + (" · promedio, escala de 1 a 3" if r.key == M.EFFORT_SCORE
                  else f" · total del período {fmt_int(r.actual)}"
                  if r.actual is not None else "")
               + (f" · {r.grade.flag_label}" if r.grade.flag else ""),
        "value": r.per_reporting_area_week,
        "bar": r.grade.pct,
        # No colour either when the movement it would report is not real.
        "status": r.grade.status if _NIGHTLY_COMPARABLE else None,
        "cells": [
            _pct(r.grade.pct),
            (fmt_number(r.per_active_area_week, 1)
             if r.per_active_area_week is not None else NA),
            _change_cell(r),
        ],
    } for i, r in enumerate(rows, start=1)],
        value_fmt=lambda v: (NA if v is None else
                             fmt_int(round(v)) if abs(v) >= 10
                             else fmt_number(v, 1)),
        columns=[("% meta", "% de la meta, por noche informada"),
                 ("/activa", "por área activa por semana, contando las "
                             "áreas que no informaron"),
                 ("cambio", "contra el período de comparación")],
    )


# ── 1 · Indicadores Clave ─────────────────────────────────────────────────────

render_section_label(
    "Indicadores Clave", right=_model.subtitle,
    info=("Los siete, siempre, en cada nivel. La barra y su color van contra "
          "la meta de traslado del liderazgo, sobre las mismas semanas y "
          "áreas que informaron, así que real y meta cuentan lo mismo. La "
          "marca violeta es el compromiso: la meta que las compañerías se "
          "pusieron, que se muestra y nunca da color. Los bautismos del "
          "formulario no llevan color: la meta de bautismos es la anual. "
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
        right="productividad · misión = 100",
        info=("El índice de productividad en cada escala: lo que produce cada "
              "compañería por semana contra la misión, que es 100, con más "
              "peso en lo más cercano al bautismo. No depende de ninguna meta, "
              "así que una unidad que se pone metas bajas no sube por eso. Un "
              "área que no informó cuenta como cero."),
    )
    st.markdown(_ladder_rows(), unsafe_allow_html=True)
    _gaps = _gap_rows()
    if _gaps:
        st.caption(f"Dónde está la diferencia con "
                   f"{_model.ladder[1].scope.name}, en puntos del índice")
        st.markdown(_gaps, unsafe_allow_html=True)
    _beside = _sibling_line()
    if _beside:
        st.caption(f"Y de lado: {_beside}")


# ── 1c · Lo que viene (decisión 48) ──────────────────────────────────────────
#
# Las cuatro proyecciones del paquete, del mismo `model.forward`: cómo termina
# el traslado y qué haría falta por semana, cómo cierra el año contra los 527,
# y las fechas bautismales abiertas. Siempre un rango con su método, nunca un
# color: una proyección no es una calificación.

_FWD = _model.forward


def _rng(lo, hi) -> str:
    if lo is None or hi is None:
        return NA
    a, b = round(lo), round(hi)
    return fmt_int(a) if a == b else f"{fmt_int(a)}–{fmt_int(b)}"


if _FWD.baptisms is not None:
    st.caption(_FWD.baptisms.sentence)

if _FWD.finish and _FWD.finish[0].weeks_left > 0:
    _left = _FWD.finish[0].weeks_left
    render_section_label(
        f"Cómo termina el traslado {_FWD.transfer}",
        right=f"proyección · faltan {fmt_int(_left)} semanas",
        info=(f"Lo que va del traslado más las {_left} semanas que faltan, "
              f"cada una como la peor, el promedio o la mejor de las últimas "
              f"{_FWD.finish[0].pace_weeks} semanas completas, con los "
              f"informes de hoy. Meta: la del liderazgo para el traslado "
              f"entero, todas las áreas. Sin color: es una proyección."),
    )
    st.markdown(ranked_list([{
        "name": k.label, "rank": "",
        "sub": (f"termina en {_rng(k.low, k.high)}"
                + (f" de {fmt_int(round(k.goal))}" if k.goal else "")
                + (f" · hacen falta {fmt_int(round(k.needed_per_week))} por "
                   f"semana, {fmt_number(k.factor, 1)}× su ritmo"
                   if k.needed_per_week is not None and k.factor else "")),
        "value": k.pct(k.mid) if k.goal else None,
        "bar": k.pct(k.mid) if k.goal else None,
    } for k in _FWD.finish], bar_max=100,
        value_fmt=lambda v: NA if v is None else fmt_percent(v)),
        unsafe_allow_html=True)

if _FWD.year is not None:
    _Y = _FWD.year
    render_section_label(
        f"Bautismos {_Y.year}: cómo cierra el año",
        right=f"{_Y.source} · meses cerrados",
        info=("Cierre probable: el mínimo y el máximo de cuatro cálculos — "
              + " · ".join(f"{w} {fmt_int(round(v))}" for w, v in _Y.anchors)
              + ". Sin color: es una proyección."),
    )
    _cards = [{"label": f"En lo que va de {_Y.year}", "value": _Y.total,
               "note": f"{_Y.months} meses cerrados"}]
    if _Y.low is not None:
        _cards.append({"label": "Cierre probable",
                       "value": _rng(_Y.low, _Y.high),
                       "note": (f"de una meta de {fmt_int(round(_Y.goal))}"
                                if _Y.goal else "sin meta")})
    if _Y.needed_per_month is not None:
        _cards.append({"label": "Hace falta por mes",
                       "value": round(_Y.needed_per_month),
                       "note": (f"el mejor mes fue {_Y.best[0]} ({_Y.best[1]})"
                                if _Y.best else "")})
    _prior = _Y.same_months(_Y.year - 1)
    if _prior:
        _cards.append({"label": f"Contra {_Y.year - 1}",
                       "value": f"{(_Y.total - _prior) / _prior * 100:+.0f}%",
                       "note": f"{_prior} en los mismos {_Y.months} meses"})
    render_kpi_row(_cards)

if _FWD.pipeline is not None:
    _PL = _FWD.pipeline
    render_section_label(
        "Lo que viene: las fechas bautismales abiertas",
        right="registros de Tableau · próximas 6 semanas",
        info=("Cada fecha abierta (fijada en el último año, sin bautismo) "
              "cuenta con la probabilidad con que las fechas de su misma edad "
              "terminaron en bautismo dentro de seis semanas, medida en los "
              "últimos 15 cierres de mes"
              + (f"; en los últimos {_PL.backtests} el cálculo falló por un "
                 f"{fmt_percent((_PL.miss or 0) * 100)} típico"
                 if _PL.miss is not None else "")
              + ". El rango es el 80% de lo esperable."),
    )
    render_kpi_row([
        {"label": "Fechas abiertas", "value": _PL.open_dates,
         "note": "fijadas en el último año, sin bautismo"},
        {"label": "Bautismos esperados", "value": _rng(_PL.low, _PL.high),
         "note": f"en 6 semanas · centro {fmt_int(round(_PL.expected))}"},
        {"label": "Fijadas hace 60 días",
         "value": sum(c for _, c, _p in _PL.by_bucket[:3]),
         "note": "las que más probablemente se bauticen"},
    ])
    if _FWD.zones:
        st.markdown(ranked_list([{
            "name": name, "rank": "",
            "sub": (f"{fmt_int(z.open_dates)} fechas abiertas · "
                    + ("piloto de Compass" if pilot
                       else "sin formularios de Compass")),
            "value": z.expected, "bar": z.expected,
            "change": _rng(z.low, z.high),
        } for name, pilot, z in sorted(_FWD.zones,
                                       key=lambda t: -t[2].expected)],
            value_fmt=lambda v: NA if v is None else fmt_number(v, 1)),
            unsafe_allow_html=True)


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
        _child_label, right="menos productiva primero · misión = 100",
        info=("Ordenadas por su índice de productividad: lo que produce cada "
              "compañería por semana contra la misión (100), sin ninguna meta. "
              "Cada celda es un indicador del índice en la misma escala. No "
              "se corta la lista. Una unidad sin nada medido queda al final: "
              "no es la menos productiva, es la que no sabemos."),
    )
    st.markdown(_ranked_units(_model.children), unsafe_allow_html=True)
    render_section_label(
        "Quién informó", right="menos informes primero",
        info=("Lo que antes iba escondido dentro del promedio: informes "
              "semanales entregados contra los posibles, y qué áreas no "
              "entregaron ninguno en todo el período."),
    )
    st.markdown(ranked_list([{
        "name": c.name, "rank": i,
        "sub": ("sin informe en todo el período: " + ", ".join(c.areas_silent)
                if c.areas_silent else "todas sus áreas informaron"),
        "value": (c.coverage.reporting_rate or 0) * 100,
        "status": ("good" if (c.coverage.reporting_rate or 0) >= .9 else
                   "warn" if (c.coverage.reporting_rate or 0) >= .6 else
                   "bad"),
    } for i, c in enumerate(_model.reporting_ranked, start=1)],
        bar_max=100, value_fmt=lambda v: fmt_percent(v)),
        unsafe_allow_html=True)


# ── 3a · Dónde enfocar y palancas (PLAN-2026-10-06 Phase 3) ──────────────────
#
# Lo mismo que el paquete, del mismo modelo: qué unidades cargan lo que le
# falta a la misión o a la zona, cuáles están debajo de la misión y bajando, y
# el embudo maduro con la mayor fuga de cada unidad.

from app.reports import focus as _FC

_SHORT_KI = {"ki_new_people_real": "Nuevas personas",
             "ki_member_lessons_real": "Lecciones c/ miembros",
             "ki_friends_sacrament_real": "Sacramental",
             "ki_friends_first_week_real": "Primera semana",
             "ki_baptismal_date_real": "Fecha bautismal",
             "ki_baptized_confirmed_real": "Bautismos",
             "ki_rc_at_church_real": "Conversos recientes"}

if _model.focus:
    _noun = "distritos" if _model.scope.level == "mission" else "áreas"
    render_section_label(
        "Dónde enfocar", right=f"lo que falta para la meta del liderazgo, por "
                               f"{_noun[:-1]}",
        info=("La meta del liderazgo de cada unidad (todas sus áreas, a "
              "prorrata del período) menos lo que informó, sumado por "
              "indicador con los pesos del índice; quien supera su meta no "
              "compensa a nadie. Tendencia: las últimas tres semanas contra "
              "las tres anteriores, por informe."),
    )
    st.markdown(ranked_list([{
        "name": f.name, "rank": i,
        "sub": (f"acumulado {fmt_percent(f.cumulative)} · donde más falta: "
                f"{_SHORT_KI.get(f.worst, f.worst or NA)} · productividad "
                f"{_idx(f.index)}"
                + (f" · {_FC.quadrant(f.index, f.trend)}"
                   if _FC.quadrant(f.index, f.trend) else "")),
        "value": f.share, "bar": f.share,
        "status": ("bad" if _FC.quadrant(f.index, f.trend)
                   == "debajo y bajando" else None),
    } for i, f in enumerate(_model.focus, start=1)],
        value_fmt=lambda v: NA if v is None else fmt_percent(v)),
        unsafe_allow_html=True)
    _falling = [f.name for f in _model.focus
                if _FC.quadrant(f.index, f.trend) == "debajo y bajando"]
    st.caption("Debajo de la misión y bajando: " + ", ".join(_falling) + "."
               if _falling else "Ninguno está debajo de la misión y bajando.")

if _model.funnel is not None and _model.funnel.mission is not None:
    _FN = _model.funnel
    _short = ("Intento", "Contacto", "Lecciones", "Iglesia", "Fecha",
              "Bautismo")
    render_section_label(
        "Palancas: el embudo maduro",
        right=(f"encontradas del {es_display.day_month(_FN.start)} al "
               f"{es_display.day_month(_FN.end, with_year=True)}"),
        info=("Personas encontradas hace tres a seis meses y la parte que "
              "llegó a cada paso hasta hoy: con ese tiempo la iglesia, la "
              "fecha y el bautismo ya tuvieron ocasión de ocurrir. La mayor "
              "fuga es el paso que convierte menos del 85% de lo que convierte "
              "la misión; entre paréntesis, qué parte de los que llegaron a "
              "ese paso pasó al siguiente, aquí y en la misión. Registros de "
              "Tableau por persona."),
    )
    def _share(v):
        # A decimal under 10%, as in the packet: whole numbers read "0%"
        # down the whole baptism column.
        return fmt_percent(v, 1 if v < 10 else 0)

    def _leak(r):
        if not r.leak:
            return ""
        step = (f" ({_share(r.leak_step[0])} · misión "
                f"{_share(r.leak_step[1])})" if r.leak_step else "")
        return f" · mayor fuga: {r.leak}{step}"

    st.markdown(ranked_list([{
        "name": r.name, "rank": "",
        "sub": f"{fmt_int(r.found)} encontradas" + _leak(r),
        "value": None,
        "cells": [_share(r.pct(i)) if r.found else NA
                  for i in range(len(_FN.stages))],
    } for r in (_FN.mission,) + tuple(_FN.rows)],
        columns=list(_short[:len(_FN.stages)])),
        unsafe_allow_html=True)

if _model.child_rates:
    _rate_heads = {"contact_rate": "Contacto", "mc_rate": "Conversación",
                   "lesson_rate": "Lecciones", "close_rate": "Invitación"}
    render_section_label(
        "Tasas de conversión por zona", right="la razón de los totales",
        info="Cada zona contra la misión, en la misma tasa.",
    )
    _rows = [("la misión", _model.rates)] + [(z.name, r)
                                              for z, r in _model.child_rates]
    st.markdown(ranked_list([{
        "name": name, "rank": "", "value": None,
        "cells": [fmt_number(x["value"], 1) + "%" if x["value"] is not None
                  else NA for x in rates],
    } for name, rates in _rows],
        columns=[_rate_heads.get(r["key"], r["key"]) for r in _model.rates]),
        unsafe_allow_html=True)


# ── 3b · Su fortaleza · Para crecer ──────────────────────────────────────────

if _model.strengths or _model.growth:
    render_section_label(
        "Su fortaleza · Para crecer", right=_model.period.label,
        info=("Lo eligen los agentes de Apps Script y queda escrito en su "
              "análisis semana a semana; esta página lo LEE, no lo "
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
        info=("Cada área de la unidad, de la menos productiva a la más. Sin "
              "cortes: aparecen todas, aunque en la misión sean cuarenta y "
              "cinco — por eso van detrás de un cajón y no en la página."),
    )
    with st.expander(f"Ver las {fmt_int(len(_model.areas_ranked))} áreas"):
        st.markdown(_ranked_units(_model.areas_ranked), unsafe_allow_html=True)


# ── 4 · Trabajo nocturno ──────────────────────────────────────────────────────

render_section_label(
    "Trabajo nocturno",
    right=("más lejos de su meta primero · "
           + (_model.nightly_coverage.label if _model.nightly_coverage
              else "")),
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
    st.caption("Cada cifra va por área por semana, sobre las noches "
               "informadas; el total del período va bajo cada nombre. "
               + _model.nightly_source_note)


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
              "cifras nunca se suman ni comparten una tabla. "
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
        info=("La cifra CERTIFICADA de Tableau para los días de este período, "
              "que la sincronización nocturna captura. Si no hay captura de "
              "estos días no se muestra otra cifra en su lugar. Cuenta todas "
              "las zonas de la misión; el formulario semanal sólo las del "
              "piloto, así que su cifra aparece aparte, en Indicadores Clave, "
              "bajo su propio nombre, y las dos nunca se comparan ni se "
              "suman."),
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
               else "Sin cifra certificada de bautismos para este período.")

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
        "label": r.get("label") or r["key"],
        "value": r["value"] if r["value"] is not None else 0,
        "goal": r["target"],
        "unit": "%", "decimals": 1,
        # What it divides by, named — the packet's note word for word.
        "note": (f"{fmt_int(r['numerator'])} de {fmt_int(r['denominator'])}"
                 + (f" {r['denominator_label'].lower()}"
                    if r.get("denominator_label") else "")),
        "change": r.get("change"),
        "points_unit": "pp",
    } for r in _model.rates])


# ── 6 · Puntajes ──────────────────────────────────────────────────────────────

if _model.scores and _model.scores.measured:
    render_section_label(
        "Puntajes", right=f"{fmt_int(_model.scores.areas_scored)} áreas "
                          f"calificadas",
        info=("Los cuatro puntajes que escriben los agentes, promediados "
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
