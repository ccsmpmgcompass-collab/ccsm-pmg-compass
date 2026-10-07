"""The president's one page — "Resumen" (PLAN-2026-10-06 4E.1, decision 57).

Five short blocks, every sentence built from the mission's own model so the
page and the screen's top card cannot disagree (decision 30):

  1. **Dónde estamos** — the seven against leadership's goal, how much of the
     shortfall is silence, and the year's baptisms against the 527;
  2. **A dónde ir** — the three units carrying most of the shortfall, each
     with the conversation it calls for, and the units below the mission
     transfer after transfer;
  3. **Lo que viene** — the transfer's finish, the pipeline, the lever worth
     most;
  4. **Qué cambió** — the year's landing then and now, the focus list's
     movers, the zones' largest index moves;
  5. **Una pregunta para cada zona** — from its result-to-cause line.

Pure: a `ReportModel` in, ``[(heading, [sentence, ...]), ...]`` out. Nothing
here grades or colours.
"""

from __future__ import annotations

from app.config import es_display as ES
from app.reports import scope as S
from app.reports.model import CHRONIC_BELOW, UNCOLOURED_KI


def _int(v) -> str:
    return ES.NA if v is None else ES.integer(round(v))


def _range(lo, hi) -> str:
    if lo is None or hi is None:
        return ES.NA
    a, b = round(lo), round(hi)
    return _int(a) if a == b else f"{_int(a)}-{_int(b)}"


def _num(v) -> str:
    return ES.integer(round(v)) if abs(v) >= 10 else ES.number(v, 1)


def where_we_are(m) -> list:
    out = []
    graded = [r for r in m.key_indicators
              if r.key not in UNCOLOURED_KI and r.grade.pct is not None
              and r.lead_goal]
    if graded:
        status = {"good": 0, "warn": 0, "bad": 0}
        for r in graded:
            if r.grade.status in status:
                status[r.grade.status] += 1
        worst = min(graded, key=lambda r: r.grade.pct)
        best = max(graded, key=lambda r: r.grade.pct)
        out.append(
            f"Contra la meta del liderazgo: {status['good']} de "
            f"{len(graded)} indicadores al ritmo, {status['warn']} atrasados, "
            f"{status['bad']} muy atrasados. Lo más fuerte, {best.label} "
            f"({ES.percent(best.grade.pct, 0)}); lo más atrasado, "
            f"{worst.label} ({ES.percent(worst.grade.pct, 0)}).")
    quiet = sum(r.silent for r in m.focus)
    if quiet >= 1:
        out.append(
            f"El {ES.percent(quiet, 0)} de lo que le falta a la misión es de "
            f"semanas sin informe; {_int(len(m.areas_silent))} áreas no "
            f"informaron en todo el período"
            + (f" ({', '.join(m.areas_silent)})" if m.areas_silent else "")
            + ".")
    y = m.forward.year
    if y is not None and y.low is not None:
        line = (f"Bautismos {y.year}: {_int(y.total)} certificados en "
                f"{ES.integer(y.months)} meses; cierre probable "
                f"{_range(y.low, y.high)} de {_int(y.goal)}")
        if y.needed_per_month is not None and y.best:
            line += (f"; hacen falta {_int(y.needed_per_month)} por mes y el "
                     f"mejor mes fue {_int(y.best[0])} ({y.best[1]})")
        out.append(line + ".")
    return out


def where_to_go(m) -> list:
    out = []
    for r in m.focus[:3]:
        trail = [p for p in r.scope.trail if p != m.scope.name]
        name = r.name + (f" ({trail[0]})" if trail else "")
        if r.mostly_silent:
            why = ("la mayor parte es de semanas sin informe: la conversación "
                   "es sobre informar")
        else:
            label = next((k.label for k in m.key_indicators
                          if k.key == r.worst), "")
            why = (f"donde más le falta, {label.lower()}; productividad "
                   f"{_int(r.index)}")
        out.append(f"{name} — {ES.percent(r.share, 0)} de lo que falta; {why}.")
    ch = m.changes
    if ch is not None and ch.history is not None and ch.history.chronic_names:
        out.append(f"Debajo de {_int(CHRONIC_BELOW)} de productividad en cada "
                   f"traslado desde que hay formulario: "
                   f"{', '.join(ch.history.chronic_names)}.")
    return out


def whats_coming(m) -> list:
    out = []
    fin = [k for k in m.forward.finish if k.goal and k.key not in UNCOLOURED_KI]
    if fin:
        reach = [k for k in fin if k.high >= k.goal]
        out.append(
            f"El traslado {m.forward.transfer}: al mejor ritmo reciente, "
            f"{_int(len(reach))} de {_int(len(fin))} indicadores llegan a la "
            f"meta del liderazgo para el traslado entero"
            + (f" ({', '.join(k.label for k in reach)})" if reach else "")
            + " — esa meta cuenta todas las áreas, también las que no "
              "informan.")
    p = m.forward.pipeline
    if p is not None:
        out.append(f"Fechas bautismales abiertas: {_int(p.open_dates)}; "
                   f"{_range(p.low, p.high)} bautismos esperados en seis "
                   f"semanas (registros de Tableau).")
    if m.forward.levers:
        v = m.forward.levers[0]
        out.append(f"La fuga que más vale: {v.name}, {v.leak} — "
                   f"{_range(*v.baptisms)} bautismos más por traslado si "
                   f"convirtiera como la misión.")
    return out


def what_changed(m) -> list:
    out = []
    ch = m.changes
    y = m.forward.year
    if ch is None:
        return out
    if ch.landing_then is not None and y is not None and y.low is not None:
        out.append(f"El cierre probable del año pasó de "
                   f"{_range(ch.landing_then.low, ch.landing_then.high)} "
                   f"({ch.landing_then_label}) a {_range(y.low, y.high)}.")
    if ch.entered or ch.left:
        bits = []
        if ch.entered:
            bits.append("entraron " + ", ".join(ch.entered))
        if ch.left:
            bits.append("salieron " + ", ".join(ch.left))
        out.append(f"En «Dónde enfocar», contra {ch.against}: "
                   + "; ".join(bits) + ".")
    h = ch.history
    if h is not None and len(h.transfers) >= 2:
        moves = []
        for scope, values in h.rows:
            if scope.level != S.ZONE:
                continue
            a, b = values[-2].value, values[-1].value
            if a is not None and b is not None:
                moves.append((b - a, scope.name, a, b))
        if moves:
            moves.sort(key=lambda t: -abs(t[0]))
            out.append("Productividad de las zonas, de "
                       f"{h.transfers[-2]} a {h.transfers[-1]}: "
                       + " · ".join(f"{n} de {_int(a)} a {_int(b)}"
                                    for _, n, a, b in moves) + ".")
    return out


def questions(m) -> list:
    out = []
    for d in m.drivers:
        if d.leak and d.leak_step:
            a, b = d.leak.split(" a ", 1)
            q = (f"¿Qué pasa entre {a} y {b}? Pasa el "
                 f"{ES.percent(d.leak_step[0], 1)}; la misión, el "
                 f"{ES.percent(d.leak_step[1], 1)}.")
        elif d.input is not None:
            label, real, goal, _ = d.input
            q = (f"¿Qué frena {d.low_label.lower()}? Sus "
                 f"{label.lower()} van en {_num(real)} por área y semana"
                 + (f" contra {_num(goal)}." if goal else "."))
        elif d.low_key:
            q = f"¿Qué frena {d.low_label.lower()}?"
        else:
            continue
        out.append(f"{d.name}: {q}")
    return out


def summary(m) -> list:
    """``[(heading, [sentence, ...]), ...]`` for the mission's model."""
    if m is None or m.scope.level != S.MISSION:
        return []
    blocks = [("Dónde estamos", where_we_are(m)),
              ("A dónde ir", where_to_go(m)),
              ("Lo que viene", whats_coming(m)),
              ("Qué cambió", what_changed(m)),
              ("Una pregunta para cada zona", questions(m))]
    return [(h, lines) for h, lines in blocks if lines]
