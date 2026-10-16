"""Page 1 — "La historia de este mes" (PLAN-2026-10-13 step 3.3, C1).

The packet used to open on a cover and a contents list. A monthly council
needs its conclusions first: the three findings that matter most this month,
each headed by its conclusion (an action title), each with one supporting
number, and two or three questions for the council to decide.

**Every finding is sized against the gap it addresses**, so they can be
ranked against each other:

  * a finding sized in **baptisms to 31 December** (the gap itself, the
    biggest leak, the old dates) is that many baptisms as a share of what is
    still missing for 527;
  * a finding that is not about baptisms (reporting, a zone's productivity,
    the last council's focus) is its share of what is missing for
    leadership's goal this period.

Both are "the part of a gap this would move", 0-100. The gap to 527 is the
whole of its own gap, so it leads whenever the year falls short of the goal;
527 is fixed (decision 64) and nothing here proposes moving it.

Pure: a mission `ReportModel` in, `Finding`s out. Nothing here grades.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import es_display as ES
from app.reports import scope as S
from app.reports.summary import council_line

#: How many findings page 1 prints.
TOP = 3
#: A zone's productivity has to move this many points between transfers to
#: be a finding.
ZONE_MOVE = 10.0

#: Units a finding's ``weight`` is a share of.
BAPTISMS = "bautismos hasta el 31 de dic, contra lo que falta para 527"
LEAD_GOAL = "parte de lo que falta para la meta del liderazgo"


@dataclass(frozen=True)
class Finding:
    """One candidate for page 1.

    ``title`` is the conclusion, as a heading. ``support`` is the one number
    behind it. ``question`` is what it asks the council to decide. ``weight``
    is the part of its gap it moves (0-100), in ``unit``.
    """

    key: str
    title: str
    support: str
    question: str
    weight: float
    unit: str


def _int(v) -> str:
    return ES.NA if v is None else ES.integer(round(v))


def _range(lo, hi) -> str:
    if lo is None or hi is None:
        return ES.NA
    a, b = round(lo), round(hi)
    return _int(a) if a == b else f"{_int(a)}-{_int(b)}"


def _gap_mid(m) -> float | None:
    gap = m.forward.gap
    if gap is None or gap.high <= 0:
        return None
    return (gap.low + gap.high) / 2


def _of_gap(m, lo: float, hi: float) -> float:
    """Baptisms ``lo``-``hi`` as a share of what is missing for 527."""
    mid = _gap_mid(m)
    return min(100.0, (lo + hi) / 2 / mid * 100) if mid else 0.0


def _per_100(pct: float) -> str:
    """4,7 → "5 de cada 100"; under 0,5 → "menos de 1 de cada 100"."""
    n = round(pct)
    return "menos de 1 de cada 100" if n < 1 else f"{_int(n)} de cada 100"


#: A leak's step as a sentence about the zone: who it is, then the zone's
#: rate and the mission's (`_per_100`).
_STEP_WORDS = {
    "fecha a bautismo": "{z} bautiza {n} fechas; la misión, {m}",
    "iglesia a fecha": ("{z} fija fecha a {n} de quienes asisten a la "
                        "Iglesia; la misión, a {m}"),
    "lecciones a iglesia": ("{z} lleva a la Iglesia a {n} de quienes "
                            "reciben lecciones; la misión, a {m}"),
    "contacto a lecciones": ("{z} enseña a {n} de quienes contacta; la "
                             "misión, a {m}"),
    "intento a contacto": ("{z} logra contactar a {n} de quienes intenta; "
                           "la misión, a {m}"),
    "encontradas a intento": ("{z} intenta contactar a {n} de quienes "
                              "encuentra; la misión, a {m}"),
}


def _step_title(zone: str, leak: str, step) -> str:
    zone_pct, mission_pct = step
    words = _STEP_WORDS.get(leak)
    if words is None:
        a, b = leak.split(" a ", 1)
        return (f"{zone}: de {a} a {b} pasa el {ES.percent(zone_pct, 1)}; la "
                f"misión, el {ES.percent(mission_pct, 1)}")
    n, m = _per_100(zone_pct), _per_100(mission_pct)
    if leak == "fecha a bautismo":
        # "bautiza 5 de cada 100 fechas; la misión, 15" reads as one count.
        n, m = n, m.replace(" de cada 100", "")
    return words.format(z=zone, n=n, m=m)


# ── The candidates ────────────────────────────────────────────────────────────

def gap_finding(m) -> Finding | None:
    """The year against 527: always the whole of its own gap."""
    gap, year = m.forward.gap, m.forward.year
    if gap is None or year is None or year.low is None or gap.high <= 0:
        return None
    from app.reports.packet import gap_line
    return Finding(
        key="gap",
        title=(f"El año cierra en {_range(year.low, year.high)} bautismos: "
               f"faltan {_range(gap.low, gap.high)} para {_int(gap.goal)}"),
        support=gap_line(gap),
        question=(f"¿Cuál de las palancas medidas toma la misión este mes "
                  f"para acercarse a {_int(gap.goal)}, y quién la lleva?"),
        weight=100.0, unit=BAPTISMS)


def reporting_finding(m) -> Finding | None:
    """Silence's part of the shortfall against leadership's goal."""
    rep = m.reporting
    quiet = sum(r.silent for r in m.focus)
    if rep is None or rep.rate is None or quiet < 1 or rep.rate >= rep.target:
        return None
    return Finding(
        key="reporting",
        title=(f"El {ES.percent(quiet, 0)} de lo que falta para la meta del "
               f"liderazgo es de semanas sin informe"),
        support=(f"Informes: {ES.percent(rep.rate * 100, 0)} de los posibles "
                 f"({_int(rep.reported)} de {_int(rep.possible)}); la meta es "
                 f"{ES.percent(rep.target * 100, 0)}."),
        question=(f"¿Qué hará cada zona para llegar al "
                  f"{ES.percent(rep.target * 100, 0)} de informes, y quién lo "
                  f"sigue cada semana?"),
        weight=min(100.0, quiet), unit=LEAD_GOAL)


def lever_finding(m) -> Finding | None:
    """The zone whose largest leak is worth the most, carried to 31 Dec."""
    from app.reports.forecast import transfers_left
    levers = [v for v in m.forward.levers if v.baptisms]
    funnel = m.funnel
    if not levers or funnel is None:
        return None
    v = max(levers, key=lambda x: x.size)
    row = next((r for r in funnel.rows if r.name == v.name), None)
    if row is None or not row.leak_step:
        return None
    year = m.forward.year
    transfers = (transfers_left(year.year, m.today) if year is not None
                 else 0.0)
    lo, hi = (v.baptisms[0] * transfers, v.baptisms[1] * transfers)
    if transfers:
        support = (f"Si ese paso convirtiera como el de la misión: "
                   f"{_range(lo, hi)} bautismos más hasta el 31 de dic.")
    else:
        support = (f"Si ese paso convirtiera como el de la misión: "
                   f"{_range(*v.baptisms)} bautismos más por traslado.")
    a, b = v.leak.split(" a ", 1)
    return Finding(
        key="lever", title=_step_title(v.name, v.leak, row.leak_step),
        support=support,
        question=f"¿Qué pasa en {v.name} entre {a} y {b}, y qué se hace este mes?",
        weight=_of_gap(m, lo, hi) if transfers else 0.0, unit=BAPTISMS)


def dates_finding(m) -> Finding | None:
    """What a date is worth (step 3.1), sized by bet (b): the old dates
    converting like the young ones."""
    q = m.forward.dates
    if q is None or len(q.cohorts) != 2 or not q.cohorts[0].dates:
        return None
    before, now = q.cohorts
    from app.reports.packet import _months_words
    span = _months_words(now.start, now.end)
    title = (f"De cada 100 fechas fijadas entre {span}, "
             f"{_int(now.share(now.baptized) * 100)} terminaron en bautismo "
             f"en seis semanas; en {before.start.year}, "
             f"{_int(before.share(before.baptized) * 100)}")
    support = (f"Hoy hay {_int(q.now.open)} fechas abiertas, "
               f"{_int(q.now.old)} de más de 90 días.")
    gap = m.forward.gap
    bet = (next((b for b in gap.bets if "fechas" in b.label.lower()), None)
           if gap is not None else None)
    weight = 0.0
    if bet is not None:
        support = (support[:-1] + f"; si las de 91 a 180 días convirtieran "
                   f"como las de 31 a 60, {_range(bet.low, bet.high)} "
                   f"bautismos más.")
        weight = _of_gap(m, bet.low, bet.high)
    return Finding(
        key="dates", title=title, support=support,
        question=("¿Qué fechas de más de 90 días se revisan o se liberan este "
                  "mes, y quién lo hace en cada distrito?"),
        weight=weight, unit=BAPTISMS)


def _zone_share(m, zone: str) -> float:
    return sum(r.share for r in m.focus if r.scope.zone == zone)


def zone_move_finding(m) -> Finding | None:
    """The zone whose productivity moved most between the last two
    transfers, weighted by its part of the shortfall now."""
    ch = m.changes
    h = ch.history if ch is not None else None
    if h is None or len(h.transfers) < 2:
        return None
    moves = []
    for scope, values in h.rows:
        if scope.level != S.ZONE:
            continue
        a, b = values[-2].value, values[-1].value
        if a is not None and b is not None and abs(b - a) >= ZONE_MOVE:
            moves.append((abs(b - a), scope.name, a, b))
    if not moves:
        return None
    _, name, a, b = max(moves)
    t1, t2 = h.transfers[-2], h.transfers[-1]
    share = _zone_share(m, name)
    return Finding(
        key="zone_move",
        title=(f"{name} {'subió' if b > a else 'bajó'} de {_int(a)} a "
               f"{_int(b)} de productividad entre {t1} y {t2}"),
        support=(f"Lleva el {ES.percent(share, 0)} de lo que le falta a la "
                 f"misión para la meta del liderazgo (misión = 100)."),
        question=f"¿Qué cambió en {name} entre {t1} y {t2}?",
        weight=share, unit=LEAD_GOAL)


def council_finding(m) -> Finding | None:
    """The last council's first focus unit, now (step 3.2)."""
    ch = m.changes
    c = ch.council if ch is not None else None
    if c is None or not c.focus or c.focus[0].share_now is None:
        return None
    f = c.focus[0]
    then, now = f.share_then, f.share_now
    if now <= then - 2:
        moved = (f"bajó del {ES.percent(then, 0)} al {ES.percent(now, 0)} de "
                 f"lo que falta")
    elif now >= then + 2:
        moved = (f"subió del {ES.percent(then, 0)} al {ES.percent(now, 0)} de "
                 f"lo que falta")
    else:
        moved = f"sigue con el {ES.percent(now, 0)} de lo que falta"
    return Finding(
        key="council",
        title=f"Desde el último consejo, {f.name} {moved}",
        support=council_line(m),
        question=(f"¿Qué se hizo en {f.name} desde el último consejo, y qué "
                  f"falta?"),
        weight=now, unit=LEAD_GOAL)


CANDIDATES = (gap_finding, reporting_finding, dates_finding, lever_finding,
              zone_move_finding, council_finding)


def candidates(m) -> list:
    """Every finding the mission's model can support, largest first."""
    if m is None or m.scope.level != S.MISSION:
        return []
    out = [f for f in (c(m) for c in CANDIDATES) if f is not None]
    return sorted(out, key=lambda f: -f.weight)


def story(m, n: int = TOP) -> tuple:
    """The ``n`` findings page 1 prints."""
    return tuple(candidates(m)[:n])
