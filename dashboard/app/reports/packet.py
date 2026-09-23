"""The council packet: 63 report models in, one PDF out.

`model.build_all()` returns every scope's `ReportModel` in packet order — the
mission, four zones, thirteen districts, forty-five areas — from a single sheet
read. This module renders them, and does no arithmetic that the model has not
already done.

**Page numbers resolve in a second pass.** The cover lists the packet's
contents with their page ranges and the print guide's run sheet says which
pages go to which leader, and neither can be written until the document has
been laid out — a section that spills one row onto a fourth page moves every
range after it. So the document is built twice: the first pass records where
each section began (`SectionStart`, which asks the canvas for its own page
number), and the second is built with those ranges filled in. Hardcoding the
ranges is not an option either, because decision 32 lets the Tableau section be
*absent* from a packet, so the page count is genuinely not fixed (§5 risk 2).

**The copy counts come from MISSION_ORG**, as Provo's run sheet does: one copy
per leadership companionship, counted off `Is_ZL` and `Is_DL`. Where the roster
cannot answer, the guide says so rather than guessing — measured 2026-09-21,
twelve of the thirteen districts carry a district leader and San Pedro's
La Marina 1 carries none, which is the assistants' own area.

See PLAN-2026-09-21-informes.md §3.2 and §4 steps P2–P6.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field, replace

from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable,
                                Frame, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Spacer)

from app.config import es_display
from app.reports import packet_parts as PP
from app.reports import periods as P
from app.reports import scope as S

#: How the packet is ordered and what each block of pages is for. The keys are
#: stable; the titles and audiences are what the print guide prints.
#: Namespaced, because `Scope.key` for the whole mission is also "mission" and
#: both live in the same `Pagination.starts`.
MISSION = "sec:mission"
ZONES = "sec:zones"
DISTRICTS = "sec:districts"
AREAS = "sec:areas"
DATA_NOTE = "sec:data_note"


@dataclass(frozen=True)
class Section:
    """One block of pages, and who it is for.

    ``first_page`` and ``last_page`` are None on the first pass and filled on
    the second. A section that turned out to hold no pages at all — decision
    32's absent Tableau block is the live example — is dropped from the
    contents rather than printed with a dash, because a contents line pointing
    at nothing is worse than a shorter contents.
    """

    key: str
    title: str
    audience: str
    print_it: str = "Imprimir"
    #: How many UNITS the section covers, so `describe` can say how many pages
    #: each of them took once a pass has measured it, and what one of them is
    #: called — "cada una" for a zona or an área, "cada uno" for a distrito.
    units: int = 1
    unit_noun: str = ""
    feminine: bool = False
    first_page: int | None = None
    last_page: int | None = None

    @property
    def present(self) -> bool:
        return self.first_page is not None and self.last_page is not None

    @property
    def page_label(self) -> str:
        if not self.present:
            return "—"
        if self.first_page == self.last_page:
            return str(self.first_page)
        return f"{self.first_page}–{self.last_page}"

    @property
    def page_count(self) -> int:
        return (self.last_page - self.first_page + 1) if self.present else 0


@dataclass(frozen=True)
class HandOut:
    """One row of the run sheet: who gets paper, which pages, how many copies.

    ``pages`` is already a printed range. ``copies`` of zero is a real row —
    "nobody, and here is why" — which is how Provo's sheet handles the leaders
    who get their own PDF instead, and how this one handles a district with no
    leader on the roster.
    """

    who: str
    pages: str
    copies: int
    note: str = ""
    page_count: int = 0


def _ranges(starts, ordered_keys, end_page: int) -> dict:
    """`{key: (first, last)}` for a run of contiguous blocks.

    A block's LAST page is the page before the next block begins. Exact,
    because the packet is laid out in this order and nothing is interleaved —
    and it needs no second marker, which is the kind of thing that goes stale
    when a section learns to split.
    """
    known = [(k, starts[k]) for k in ordered_keys if k in starts]
    out = {}
    for i, (key, first) in enumerate(known):
        nxt = known[i + 1][1] if i + 1 < len(known) else end_page + 1
        out[key] = (first, max(first, nxt - 1))
    return out


@dataclass
class Pagination:
    """Where every section and every unit started, and how long it all ran.

    Filled by a build pass. `resolve` hands back the sections with their ranges
    written in; `unit_ranges` does the same for the zones and districts the run
    sheet has to name one at a time.
    """

    starts: dict = field(default_factory=dict)
    total: int = 0

    @property
    def measured(self) -> bool:
        return bool(self.starts) and self.total > 0

    def resolve(self, sections) -> list:
        spans = _ranges(self.starts, [s.key for s in sections], self.total)
        return [replace(s, first_page=spans[s.key][0], last_page=spans[s.key][1])
                for s in sections if s.key in spans]

    def unit_ranges(self, unit_keys) -> dict:
        return _ranges(self.starts, list(unit_keys), self.total)

    def page_of(self, key: str) -> int | None:
        return self.starts.get(key)

    def same_as(self, other: "Pagination") -> bool:
        """Whether a pass landed where the pass before it said it would.

        The second pass prints the ranges the first measured, and printing them
        can change how long the guide is — which moves everything after it. So
        the build repeats until a pass confirms the numbers it was given.
        """
        return self.total == other.total and self.starts == other.starts


class SectionStart(Flowable):
    """A zero-height marker that records the page its section opened on.

    It asks the canvas rather than the document because a flowable has no
    handle on the doc template, and `getPageNumber()` is the number the footer
    will print — which is the whole point, since the contents has to name the
    number a reader sees.
    """

    def __init__(self, key: str, pagination: Pagination):
        super().__init__()
        self.key = key
        self.pagination = pagination
        self.width = 0
        self.height = 0

    def wrap(self, availWidth, availHeight):
        return (0, 0)

    def draw(self):
        self.pagination.starts.setdefault(self.key,
                                          self.canv.getPageNumber())


# ── Who gets paper ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Leadership:
    """The leadership companionships MISSION_ORG knows about.

    Counted off the roster's own flags, never assumed from the number of zones
    and districts: the two disagree today, and the run sheet says so instead of
    printing thirteen copies for twelve leaders.
    """

    zone_leaders: dict = field(default_factory=dict)
    district_leaders: dict = field(default_factory=dict)
    assistants: int = 0

    @property
    def districts_without_a_leader(self) -> list:
        return [k for k, v in self.district_leaders.items() if not v]


def leadership(roster) -> Leadership:
    """Read `Is_ZL` / `Is_DL` / `Is_AP` off MISSION_ORG.

    Keyed by `Scope.key`, so a district shares its identifier with the section
    that prints it — district names are not guaranteed unique across zones.
    """
    def flag(df, col):
        if col not in df.columns:
            return df.assign(_f=False)
        return df.assign(_f=df[col].astype(str).str.strip().str.upper() == "TRUE")

    zones, districts = {}, {}
    zl = flag(roster, "Is_ZL")
    dl = flag(roster, "Is_DL")
    for z in S.zone_scopes(roster):
        zones[z.key] = int(zl[(zl["Zone"].astype(str).str.strip() == z.name)
                              & zl["_f"]].shape[0])
    for d in S.district_scopes(roster):
        rows = dl[(dl["Zone"].astype(str).str.strip() == (d.zone or ""))
                  & (dl["District"].astype(str).str.strip() == d.name) & dl["_f"]]
        districts[d.key] = int(rows.shape[0])
    ap = flag(roster, "Is_AP")
    return Leadership(zone_leaders=zones, district_leaders=districts,
                      assistants=int(ap[ap["_f"]].shape[0]))


def hand_outs(sections, units, roster) -> list:
    """The run sheet: one row per person at the table.

    The president and the assistants get the whole packet. Every zone leader
    gets the mission pages and their own zone's, and every district leader
    their own district's page — named one row at a time, with the unit's own
    name on it, rather than as a single "give them their zone packet", because
    decision 2 means there is no separate zone PDF to give them in v1.

    ``units`` is `(scope, (first, last))` in packet order, already resolved.
    """
    by_key = {s.key: s for s in sections}
    total = max((s.last_page for s in sections if s.present), default=0)
    whole = f"1–{total}" if total else "—"
    lead = leadership(roster)

    rows = [HandOut("Presidente de misión", whole, 1, "El paquete completo",
                    total),
            HandOut("Asistentes", whole, max(1, lead.assistants),
                    "El paquete completo", total)]

    mission_section = by_key.get(MISSION)
    mission_label = mission_section.page_label if mission_section else "—"
    mission_count = mission_section.page_count if mission_section else 0
    for scope, (first, last) in units:
        pages = str(first) if first == last else f"{first}–{last}"
        count = last - first + 1
        if scope.level == S.ZONE:
            copies = lead.zone_leaders.get(scope.key, 0)
            rows.append(HandOut(
                f"Líderes de zona · {scope.name}",
                f"{mission_label} + {pages}", copies,
                "La misión y su zona" if copies
                else "Sin líder de zona en MISSION_ORG",
                mission_count + count))
        elif scope.level == S.DISTRICT:
            copies = lead.district_leaders.get(scope.key, 0)
            rows.append(HandOut(
                f"Líderes de distrito · {scope.name}", pages, copies,
                "Su distrito" if copies
                else "Sin líder de distrito en MISSION_ORG",
                count))
    return rows


def sheets(rows) -> int:
    """Sheets of paper for a run sheet, printed double-sided."""
    return sum(math.ceil(r.page_count / 2) * r.copies for r in rows)


# ── The document ──────────────────────────────────────────────────────────────

def _document(buffer) -> BaseDocTemplate:
    """One frame, one template, and the furniture drawn at page end.

    `onPageEnd` rather than `onPage` — see `packet_parts.SetFurniture`. The
    cover simply never sets any, so it prints clean.
    """
    doc = BaseDocTemplate(buffer, pagesize=PP.PAGE_SIZE,
                          leftMargin=PP.MARGIN_X, rightMargin=PP.MARGIN_X,
                          topMargin=PP.MARGIN_TOP, bottomMargin=PP.MARGIN_BOTTOM,
                          title="Paquete del Consejo · PMG Compass",
                          author="PMG Compass")
    frame = Frame(PP.MARGIN_X, PP.MARGIN_BOTTOM, PP.CONTENT_WIDTH,
                  PP.CONTENT_HEIGHT, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0, id="body")
    doc.addPageTemplates([PageTemplate(id="pmg", frames=[frame],
                                       onPageEnd=PP.draw_furniture)])
    return doc


def _render(flowables) -> tuple:
    """`(pdf bytes, page count)`. The count comes from the document itself —
    the number its own footer last printed — rather than from re-parsing what
    was just written."""
    buf = io.BytesIO()
    doc = _document(buf)
    doc.build(list(flowables))
    return buf.getvalue(), doc.page


# ── The front matter ──────────────────────────────────────────────────────────

def sections_for(models) -> list:
    """The contents, in packet order, described for the print guide.

    Titles carry their own counts ("Cada zona — 4 zonas") because Provo's
    contents does and it answers the second question a reader has. The counts
    come from the models actually built, never from the roster, so a packet
    built with one zone missing says three when there are three.

    How many PAGES each unit takes is not known here and is filled in by
    `describe`, once a pass has measured it.
    """
    counts = {level: sum(1 for m in models if m.scope.level == level)
              for level in (S.ZONE, S.DISTRICT, S.AREA)}
    return [
        Section(MISSION, "La misión", "Todos en el consejo", units=1),
        Section(ZONES, f"Cada zona — {counts[S.ZONE]} zonas",
                "Se discute zona por zona", units=counts[S.ZONE],
                unit_noun="zona", feminine=True),
        Section(DISTRICTS, f"Cada distrito — {counts[S.DISTRICT]}",
                "Entregar a cada líder de distrito", units=counts[S.DISTRICT],
                unit_noun="distrito"),
        Section(AREAS, f"Cada área — {counts[S.AREA]}",
                "Referencia durante el consejo", units=counts[S.AREA],
                unit_noun="área", feminine=True),
        Section(DATA_NOTE, "Nota de datos",
                "Quien pregunte de dónde sale una cifra", "Referencia"),
    ]


def describe(sections) -> list:
    """The contents' titles, once the page count for each section is known.

    §3.2 planned "13 districts, one page each"; the districts print five, since
    decision 10 gives every unit all seven Key Indicators and decision 17 gives
    it all twenty-two nightly metrics. The decisions outrank the estimate — and
    the contents should describe the document that was built rather than the
    one that was sketched, so the count is measured here rather than written
    into the title.
    """
    out = []
    for section in sections:
        out.append(replace(section, title=_titled(section)))
    return out


def _titled(section) -> str:
    """A section's title with its real page count, in agreeing Spanish.

    "0,5 páginas cada una" is arithmetically right and reads like a mistake;
    two areas to a page is the sentence a person would say. Below one page per
    unit that is the only shape the number takes, so it is the only special
    case worth writing.
    """
    if section.units <= 1 or not section.page_count:
        return section.title
    each = section.page_count / section.units
    agree = "cada una" if section.feminine else "cada uno"
    if each <= 0.6:
        return f"{section.title}, dos por página"
    if each == int(each):
        n = int(each)
        return (f"{section.title}, una página {agree}" if n == 1
                else f"{section.title}, {es_display.integer(n)} páginas {agree}")
    return f"{section.title}, {es_display.number(each, 1)} páginas {agree}"


def front_matter(mission, sections, units, roster, *, total_pages: int) -> list:
    """The cover and the print guide — pages 1 and 2 (decision 4).

    On the first pass every range is a dash and the total is zero; the guide
    still lays out at very nearly its true length, which is what lets the next
    pass be right. It is the one part of the packet built from the packet
    rather than from a `ReportModel`.
    """
    period = mission.period
    facts = [
        ("Preparado para", "Presidente de misión y asistentes"),
        ("Período", f"{period.label} · {period.window_label}"),
        ("Semanas completas", period.progress_label),
        ("Cumplimiento", mission.compliance_label),
    ]
    sections = describe(sections)
    rows = hand_outs(sections, units, roster)
    paper = sheets(rows)
    lead = leadership(roster)
    missing = lead.districts_without_a_leader
    closing = [
        f"Papel total: {paper} hojas a doble cara si imprime exactamente las "
        f"filas de arriba. Las copias salen de MISSION_ORG — una por "
        f"compañería de liderazgo."]
    if missing:
        names = ", ".join(sorted(k.split("/")[-1] for k in missing))
        closing.append(
            f"{len(lead.district_leaders) - len(missing)} de "
            f"{len(lead.district_leaders)} distritos tienen un líder marcado "
            f"en MISSION_ORG. Sin líder: {names}. Esa fila pide 0 copias; "
            f"decida a mano a quién entregarla.")
    sheets_per_copy = math.ceil(total_pages / 2) if total_pages else 0
    return (
        PP.cover_page(
            kicker="Consejo de liderazgo misional",
            title="Paquete del Consejo",
            standfirst=f"{mission.mission_name} — el rendimiento de cada "
                       f"zona, distrito y área en este período.",
            facts=facts,
            contents=[(s.title, s.page_label) for s in sections],
            note="Generado por PMG Compass desde COMPASS_CCSM el "
                 f"{es_display.long_date(mission.today)}. Cada cifra viene de lo "
                 f"que las compañerías informaron; la nota de datos al final "
                 f"dice qué falta y por qué.")
        + [PageBreak(),
           PP.SetFurniture(PP.Furniture(
               eyebrow=mission.mission_name, period=period.window_label,
               mission=mission.mission_name, key=False))]
        + PP.print_guide(
            heading_note=f"Paquete del consejo · {total_pages or 0} páginas",
            intro=(
                f"Imprima las páginas 1-{total_pages} a doble cara, vertical, "
                f"en «Tamaño real» — no «Ajustar a la página»: el diseño "
                f"está hecho para los márgenes de Carta y escalarlo corta los "
                f"pies de página. Son {sheets_per_copy} hojas por copia "
                f"completa."),
            sections=[[s.title, s.page_label, s.audience, s.print_it]
                      for s in sections],
            handouts=[[r.who, r.pages, str(r.copies), r.note] for r in rows],
            closing=closing)
    )


# ── Reading a metric onto paper ───────────────────────────────────────────────

def _pct(value, places: int = 0) -> str:
    return es_display.percent(value, places) if value is not None else es_display.NA


def _count(value) -> str:
    """A count, printed whole unless it genuinely has a decimal to show.

    The nightly table holds nineteen counts and one 1-3 effort score, and
    "142,0 contactos" is a number pretending to a precision it does not have.
    """
    if value is None:
        return es_display.NA
    return (es_display.integer(value) if float(value) == int(value)
            else es_display.number(value, 1))


def _change(row, *, comparable: bool, confident: bool = True) -> tuple | None:
    """`(direction, "+12%")`, or None when there is nothing to say at all.

    Two gates, because there are two different kinds of nothing. ``comparable``
    is "there is no comparison window"; the column prints blank. ``confident``
    is "there is one, and it rests on one or two areas" — `Coverage.thin`. Then
    the number is still printed, because decision 6 says a partial comparison
    is shown rather than hidden, but the DIRECTION is dropped: a direction of 0
    draws no triangle and prints grey.

    The live case is not hypothetical. The default comparison for this transfer
    is the first two weeks of 2026-5, which hold a single area, and every one
    of the seven Key Indicators comes out between -36% and -65%. Seven red
    triangles down a council page would report that single area's fortnight as
    the mission collapsing.
    """
    pct = row.grade.change_pct
    if pct is None or not comparable:
        return None
    if not confident:
        return (0, es_display.signed_percent(pct))
    direction = 1 if pct > 0 else (-1 if pct < 0 else 0)
    return (direction, es_display.signed_percent(pct))


def _verdict(row, *, graded: bool = True) -> str:
    """The words beside the bar: the grade and its percentage, or the flag.

    A flagged goal prints the flag INSTEAD of a grade on a Key Indicator
    (decision 22 — it is not scored) and BESIDE the percentage on a nightly
    row, where the colour comes from the movement and the goal never becomes a
    verdict anyway (decision 31).
    """
    if row.grade.flag and graded:
        return row.grade.flag_label
    pct = _pct(row.grade.pct)
    if not graded:
        return f"{pct} de la meta" if row.grade.pct is not None else "sin meta"
    word = PP.STATUS_WORD.get(row.grade.status or "")
    if not word:
        return f"{pct} de la meta" if row.grade.pct is not None else "sin meta"
    return f"{word} · {pct}"


def ki_lines(model, *, comparable: bool, confident: bool = True) -> list:
    """The seven Key Indicators as printable rows (decision 10).

    The bar fills against the companionships' own summed meta and the violet
    mark is leadership's transfer goal on that same scale (decision 11) — the
    identical statement the KPI card makes on the screen, so the two surfaces
    cannot disagree about what a bar means.
    """
    lines = []
    for row in model.key_indicators:
        mark = None
        note = ""
        if row.has_leadership_goal:
            # The figure as well as the mark. The mark is a position on a bar
            # scaled to the companionships' own meta, and leadership's goal is
            # routinely larger than that — pinned to the track's end, four
            # different goals would all read as "exactly at the line".
            note = f"meta de traslado {_count(row.leadership_goal)}"
            if row.meta:
                mark = row.leadership_goal / row.meta * 100
        elif row.leadership_goal_areas or row.meta:
            note = (f"sin meta de traslado · "
                    f"{es_display.integer(row.leadership_goal_areas)} de "
                    f"{es_display.integer(model.scope.area_count)} áreas")
        lines.append(PP.MetricLine(
            label=row.label, value=_count(row.actual),
            goal=_count(row.meta) if row.meta else es_display.NA,
            pct=row.grade.pct, mark_pct=mark, status=row.grade.status,
            verdict=_verdict(row),
            change=_change(row, comparable=comparable, confident=confident),
            note=note))
    return lines


def nightly_lines(model, goals, *, comparable: bool) -> list:
    """Every tracked nightly metric, furthest behind first (decision 17).

    ``goals`` must be the same `nightly_goals` the model was built from: it
    feeds the row's note ("meta 150/área/sem") while the attainment beside it
    comes from the model's own grade, and handing in a different dict would put
    two goals on one line.

    ``status`` is deliberately left off the bar: decision 31 puts a nightly
    row's colour on its MOVEMENT, and the bar here is its distance from a goal
    set at roughly twice what the mission does. Seventeen of twenty bars
    painted red every week is the wall of colour decision 10 exists to prevent,
    so the bar is the single magnitude blue and the colour lives in the change.
    """
    lines = []
    for row in model.nightly_weakest_first:
        goal = goals.get(row.key)
        note = (f"meta {es_display.number(goal, 0)}/área/sem" if goal
                else "sin meta configurada")
        if row.grade.flag:
            note = f"{note} · {row.grade.flag_label}"
        lines.append(PP.MetricLine(
            label=row.label, value=_count(row.actual),
            goal=_count(goal) if goal else es_display.NA,
            pct=row.grade.pct, status=None, magnitude=True,
            verdict=_verdict(row, graded=False),
            change=_change(row, comparable=comparable), note=note))
    return lines


#: Which three Key Indicators get a column of their own in a ranked table, and
#: what they are called there. Three, not seven: seven columns at 50pt each
#: would leave 70pt for a unit's name. The abbreviations are written out rather
#: than trimmed off the catalogue's labels, because "Amigos en la Reunión
#: Sacramental" cut to nine characters is "Amigos en", which names nothing.
CHILD_COLUMNS = (
    ("ki_new_people_real", "Nuevas"),
    ("ki_friends_sacrament_real", "Sacr."),
    ("ki_baptized_confirmed_real", "Baut."),
)


def _child_keys(model) -> tuple:
    """The three above, or the unit's own first three if a key is not in use."""
    present = {r.key for r in model.key_indicators}
    chosen = [(k, short) for k, short in CHILD_COLUMNS if k in present]
    if len(chosen) == len(CHILD_COLUMNS):
        return tuple(chosen)
    return tuple((r.key, PP.fit(r.label, PP.CELL_HEAD, 44))
                 for r in model.key_indicators[:3])


def child_rows(model, spec: PP.RankedSpec) -> list:
    """The units one level down, weakest first (decisions 14, 15, 16).

    Every cell is attainment per ACTIVE area — the same basis as the headline
    beside it, so a row's cells average to its own figure. A zone where seven
    of eleven areas went quiet reads as the zone, not as the four that filed.
    """
    return ranked_unit_rows(model.children, model, spec)


def _attainment_status(pct) -> str | None:
    """A child unit's dot, on the same 90/60 bands the Key Indicators use.

    `theme.goal_bar_status` rather than a second set of thresholds — the whole
    point of decision 10 is that a green means one thing everywhere.
    """
    from app.config.theme import goal_bar_status
    return goal_bar_status(pct)


# ── The mission's pages ───────────────────────────────────────────────────────

#: The sentence under every graded table. Provo's, in intent: it says what the
#: percentage is AND what it is not, because "74%" beside another unit's "89%"
#: reads as a league table whether or not one was meant.
GRADED_NOTE = ("Cada porcentaje es esta unidad contra su propia meta — al ritmo "
               "es 90% o más, atrasado 60-89%, muy atrasado por debajo. Nada "
               "aquí compara un área, distrito o zona con otra.")

BASIS_NOTE = ("Real es la suma del período. El relleno de la barra es esa suma "
              "contra la meta que las compañerías se pusieron, por área que "
              "informó; la marca violeta es la meta de traslado del liderazgo.")


def _heading(model) -> list:
    st = PP.styles()
    return [Paragraph(PP.text(model.scope.name), st["title"]),
            Paragraph(PP.text(model.subtitle), st["subtitle"])]


def _comparison_note(model) -> str:
    """What the change column is measured against, or why there is no change."""
    comparison = model.comparison
    if comparison is None or comparison.period is None:
        reason = getattr(comparison, "reason", "") if comparison else ""
        return f"Sin comparación: {reason}" if reason else "Sin comparación."
    cov = model.comparison_coverage
    out = f"Cambio contra {comparison.period.label} ({comparison.period.elapsed_label})"
    if cov is not None:
        out += f" · {cov.label}"
        if cov.thin:
            out += (" — apenas un puñado de áreas. La cifra se muestra pero "
                    "sin dirección: no hay con qué sostener una flecha")
    return out + "."


def _weekly_comparable(model) -> bool:
    cov = model.comparison_coverage
    return cov is not None and cov.usable


def _weekly_confident(model) -> bool:
    """Whether the weekly comparison rests on more than a handful of areas.

    `Coverage.thin` is a 25% floor on possible area-weeks, measured: CCSM's
    real weeks run 58-80% and the windows this catches sit at 1.1% and 0.4%.
    """
    cov = model.comparison_coverage
    return cov is not None and cov.usable and not cov.thin


def _nightly_comparable(model) -> bool:
    """DAILY_LOG begins 2026-08-09, so the default comparison for this transfer
    holds almost no nights; a movement measured across it is one area's evening
    standing for the mission."""
    cov = model.comparison_nightly_coverage
    return cov is not None and cov.usable and not cov.thin


def _headline_tiles(model) -> list:
    """The band at the foot of M1: the outcomes, largest first.

    Baptisms lead because that is the number the council opens with, and the
    three that follow are the Key Indicators furthest along the teaching path.
    Each carries its own verdict, so the band is not four numbers without a
    scale.
    """
    wanted = ("ki_baptized_confirmed_real", "ki_new_people_real",
              "ki_friends_sacrament_real", "ki_baptismal_date_real")
    tiles = []
    for key in wanted:
        row = model.ki(key)
        if row is None:
            continue
        tiles.append(PP.Tile(label=row.label, value=_count(row.actual),
                             note=_verdict(row), status=row.grade.status))
    if not tiles:
        tiles = [PP.Tile(label=r.label, value=_count(r.actual),
                         note=_verdict(r), status=r.grade.status)
                 for r in model.key_indicators[:4]]
    return tiles


#: Decision 37. The weekly form's baptism Key Indicator is the figure the
#: packet trusts least — companionships leave the field blank, and on
#: 2026-09-23 it read 5 for a transfer Tableau certified far more of — so it is
#: never the sentence a unit's first page opens with, in either direction. It
#: keeps its tile, its row and its page (M6), where it sits beside the
#: certified figure under its own name.
NOT_FOR_VERDICTS = frozenset({"ki_baptized_confirmed_real"})


def _verdict_candidates(model) -> list:
    """The Key Indicators a sentence may name as strongest or most behind.

    A flagged goal is not eligible (decision 22): it is neither the unit's best
    work nor its worst, and naming it as either would be reporting the goal as
    though it were the work. Nor is the form's baptism figure (decision 37).
    """
    return [r for r in model.key_indicators
            if r.grade.pct is not None and not r.grade.flag
            and r.key not in NOT_FOR_VERDICTS]


def _best_and_worst(model):
    """The strongest and the weakest graded Key Indicator, by attainment —
    of the ones `_verdict_candidates` allows."""
    graded = _verdict_candidates(model)
    if not graded:
        return None, None
    ordered = sorted(graded, key=lambda r: r.grade.pct)
    return ordered[-1], ordered[0]


# ── Blocks every level shares ─────────────────────────────────

def rate_lines(model) -> list:
    """The four conversion rates as printable rows (decision 13).

    Empty below zone level, because the model leaves them empty there: a close
    rate over one companionship's three lessons is a ratio of two small
    integers wearing a percentage sign.

    The bar fills against the rate's own target rather than against 100, so
    "44,7% de contacto" reads as 89% of a 50% target and not as half of
    nothing. That is the same statement the screen's card makes.
    """
    lines = []
    for rate in model.rates:
        value, target = rate.get("value"), rate.get("target")
        pct = rate.get("pct_of_target")
        lines.append(PP.MetricLine(
            label=rate.get("label") or rate.get("key", ""),
            value=es_display.percent(value, 1),
            goal=es_display.percent(target, 0) if target else es_display.NA,
            pct=pct, status=_attainment_status(pct), magnitude=pct is None,
            verdict=(f"{PP.STATUS_WORD[_attainment_status(pct)]} · "
                     f"{_pct(pct)} de la meta") if pct is not None else "sin meta",
            note=(f"{es_display.integer(rate.get('numerator'))} de "
                  f"{es_display.integer(rate.get('denominator'))}")))
    return lines


def score_tiles(model) -> list:
    """The four scores as a tile band (decision 18).

    Ungraded on purpose: these are the scoring agent's own composites on a
    0-100 scale that is not a percentage of a goal, and colouring them with the
    90/60 bands would claim they are. The rank line beneath says where the unit
    sits, which is the comparison that means something.
    """
    scores = model.scores
    if scores is None or not scores.measured:
        return []
    pairs = (("Esfuerzo", scores.effort), ("Habilidad", scores.skill),
             ("Indicadores Clave", scores.ki),
             ("Efectividad", scores.effectiveness))
    return [PP.Tile(label=label, value=es_display.number(value, 1),
                    note="de 100")
            for label, value in pairs if value is not None]


def ladder_rows(model, spec: PP.RankedSpec) -> list:
    """This unit against the unit above it and against the mission.

    Zackary, 2026-09-23: every zone reads against the mission's averages and
    every district against its own zone's. It is also the reason a unit page
    exists at all — a district leader has no way to know whether 73% is good
    until they can see the zone at 78 and the mission at 76.

    The arithmetic is `ReportModel.ladder`, computed in the model for both
    renderers (decision 30). Drawn as three rows of the same shape as every
    other ranked table in the packet, which prints legibly at 7,5pt and
    photocopies.
    """
    keys = [k for k, _ in _child_keys(model)]
    if len(model.ladder) < 2:
        return []
    out = [PP.ranked_row(spec, name="unidad", header=True)]
    for rung in model.ladder:
        by_key = {r.key: r.attainment_per_active_area for r in rung.metrics}
        out.append(PP.ranked_row(
            spec, rank=None, name=rung.scope.name, sub=rung.role,
            status=_attainment_status(rung.mean_attainment),
            cells=[_pct(by_key.get(key)) for key in keys],
            value=_pct(rung.mean_attainment), bar=rung.mean_attainment,
            bar_max=100))
    return out


def gap_rows(model, *, limit: int | None = None,
             label_width: float = 168.0) -> list:
    """The per-indicator gap to the unit one rung up, as diverging bars.

    The ranked table above says where the three scales sit; this says which of
    the seven is carrying the difference, which is the thing a council can act
    on. Against the PARENT rather than the mission: a district is run by its
    zone, and "you are eleven points under your own zone" is a conversation
    two people in the room can have.
    """
    parent = next((r for r in model.ladder[1:] if not r.is_self), None)
    if parent is None or not any(v is not None for v in parent.deltas):
        return []
    rows = [(r.label, d) for r, d in zip(parent.metrics, parent.deltas)]
    if limit is not None:
        # Widest gap first, and an ungraded indicator is not a gap of zero —
        # it goes to the end and falls off the short list rather than
        # displacing a real one.
        rows = sorted(rows, key=lambda row: (row[1] is None,
                                             row[1] if row[1] is not None
                                             else 0))[:limit]
    # The rung's ROLE, not its name: the ranked table directly above already
    # says which zone this is, and "contra Chile Concepción South Mission"
    # does not fit a 168pt column at any size worth reading.
    return [PP.gap_bars(PP.CONTENT_WIDTH, rows, label_width=label_width,
                        note=f"contra {parent.role}")]


def ladder_block(model) -> list:
    """The whole comparison section: the three scales, then the seven gaps.

    One block so every level that carries it carries the same thing — a zone
    against the mission, a district against its zone, an area against its
    district — and a reader who has read one has read them all.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    spec = PP.RankedSpec(width=W, cells=_child_cells(model))
    rows = ladder_rows(model, spec)
    if not rows:
        return []
    above = next((r.scope.name for r in model.ladder[1:] if not r.is_self), "")
    flow = [Spacer(0, 10),
            PP.SectionHead(_ladder_title(model),
                           "cada celda por área activa")]
    flow.extend(rows)
    gaps = gap_rows(model)
    if gaps:
        flow.append(Spacer(0, 6))
        flow.extend(gaps)
    strip = sibling_strip(model)
    if strip:
        flow.append(Spacer(0, 6))
        flow.extend(strip)
    flow.append(Spacer(0, 4))
    flow.append(Paragraph(PP.text(
        f"Un porcentaje no dice nada por sí solo. Arriba está la misma medida "
        f"en cada escala a la que se puede leer; abajo, cuánto separa a esta "
        f"unidad de {above} en cada Indicador Clave, en puntos porcentuales."
        if gaps else
        "Un porcentaje no dice nada por sí solo. Estas filas son la misma "
        "medida en cada escala a la que se puede leer, para que el número de "
        "arriba tenga contra qué leerse."), st["note"]))
    return flow


def sibling_strip(model) -> list:
    """Where the unit sits among the units beside it, as one axis of dots.

    The other half of "is 73% good". The ladder answers it upward — against
    the zone, against the mission; this answers it sideways, and a leader can
    do more about sideways: the unit two dots along is run by somebody in the
    same room.

    A district at 34% among districts running 31 to 38 has a mission problem.
    The same 34% among districts running 16 to 63 has a district problem. No
    table of percentages shows the difference and this does it in 44 points.
    """
    peers = [(c.name, c.mean_attainment) for c in model.siblings]
    if len([1 for _, v in peers if v is not None]) < 2:
        return []
    # And no strip at all when THIS unit has no reading: its dot would be the
    # one missing from the line, and a distribution with an unmarked
    # highlight is a picture of everybody except the reader.
    if not any(name == model.scope.name and value is not None
               for name, value in peers):
        return []
    noun = _level_plural(model.scope.level)
    silent = sum(1 for _, v in peers if v is None)
    # Named off the LADDER, which is the unit one rung up by construction. Read
    # off `trail[0]` it named an area's zone where its district belongs:
    # "3 áreas de Los Angeles Norte" under a companionship of Huepil & Tucapel.
    above = next((r.scope.name for r in model.ladder[1:] if not r.is_self),
                 "la misión")
    caption = f"{es_display.integer(len(peers))} {noun} de {above}"
    if silent:
        caption += (f" · {es_display.integer(silent)} sin lectura, "
                    f"sin punto en la línea")
    return [PP.strip_plot(PP.CONTENT_WIDTH, peers, highlight=model.scope.name,
                          value_fmt=lambda v: _pct(v), caption=caption)]


def _level_plural(level: str) -> str:
    return {S.ZONE: "zonas", S.DISTRICT: "distritos",
            S.AREA: "áreas"}.get(level, "unidades")


def _ladder_title(model) -> str:
    """What the comparison section is called, named for the rungs it holds."""
    names = [r.role for r in model.ladder[1:] if not r.is_self]
    if not names:
        return "Contra las demás escalas"
    # "su distrito y su zona y la misión" — a comma before the last "y", the
    # way a sentence is written rather than the way a list is joined.
    head = ", ".join(names[:-1])
    return "Contra " + (f"{head} y {names[-1]}" if head else names[-1])


def at_a_glance(model, *, weekly_ok: bool, weekly_sure: bool) -> list:
    """The unit's first page: what is strongest, what to move, the headlines.

    Identical at every level, because the question is. Provo opens a zone page
    and a district page the same way it opens the mission's, and a leader who
    has read one has read them all.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    best, worst = _best_and_worst(model)
    flow = _heading(model)
    flow.append(PP.SectionHead("Dónde estamos", model.period.window_label))
    if best is not None:
        flow.append(Paragraph(
            PP.text(f"Lo más fuerte: {best.label} va en {_pct(best.grade.pct)} "
                    f"de la meta — {_count(best.actual)} contra "
                    f"{_count(best.meta)}."), st["body"]))
    if worst is not None:
        flow.append(Paragraph(
            PP.text(f"Lo que hay que mover: {worst.label} es lo más atrasado, "
                    f"en {_pct(worst.grade.pct)} — {_count(worst.actual)} "
                    f"contra {_count(worst.meta)}."), st["body"]))
    if best is None and worst is None:
        flow.append(Paragraph(PP.text(
            "Ningún Indicador Clave tiene con qué medirse en este período: "
            "o no hay meta, o nadie informó."), st["body"]))
    for row in [r for r in model.key_indicators if r.grade.flag]:
        flow.append(Paragraph(
            PP.text(f"{row.label}: {row.grade.flag_label}. "
                    f"{_count(row.actual)} contra una meta declarada de "
                    f"{_count(row.meta)}. La cifra es real; la meta hay que "
                    f"revisarla."), st["note_lead"]))
    flow.append(Spacer(0, 8))
    flow.append(PP.stat_tiles(W, _headline_tiles(model)))
    # A zone reads against the mission, an area against its district — the
    # same section the district page has carried since P4, now at every level
    # that has something above it (Zackary, 2026-09-23). The mission's ladder
    # is empty and the block is simply absent.
    flow.extend(ladder_block(model))
    behind = furthest_behind(model)
    if behind:
        # A sentence, not the three-row table this used to be. The full seven
        # are now a few centimetres below on the same page (Phase V), so the
        # table was the same rows printed twice for 85pt — and the ORDER was
        # the only thing it added, which a sentence carries.
        flow.append(Paragraph(PP.text(
            "Los más atrasados, en orden: "
            + " · ".join(f"{r.label} {_pct(r.grade.pct)}" for r in behind)
            + ". De los Indicadores Clave con una meta utilizable; los "
            "bautismos tienen su propia página, con la cifra certificada."),
            st["note_lead"]))
    flow.append(Spacer(0, 4))
    flow.append(Paragraph(PP.text(GRADED_NOTE), st["note"]))
    return flow


def key_indicator_page(model, *, weekly_ok: bool, weekly_sure: bool) -> list:
    st = PP.styles()
    return [
        PP.SectionHead("Indicadores Clave",
                       f"los siete · {model.compliance_label}"),
        PP.metric_table(ki_lines(model, comparable=weekly_ok,
                                 confident=weekly_sure)),
        Spacer(0, 6),
        Paragraph(PP.text(BASIS_NOTE), st["note"]),
        Paragraph(PP.text(_comparison_note(model)), st["note"]),
    ]


def week_page(model) -> list:
    st = PP.styles()
    weeks, rows, boundaries, reporting = _week_rows(model)
    if not rows:
        return [PP.SectionHead("Semana a semana", "solo semanas completas"),
                Paragraph(PP.text(
                    "Sin semanas completas informadas en este período."),
                    st["body"])]
    flow = [
        PP.SectionHead("Semana a semana", "solo semanas completas"),
        PP.week_table(PP.CONTENT_WIDTH, weeks, rows, boundaries=boundaries,
                      footer=("Áreas que informaron, de "
                              f"{es_display.integer(model.scope.area_count)}",
                              reporting, "")),
        Spacer(0, 6),
        Paragraph(PP.text(
            "Cada línea tiene su propia escala — la forma es la noticia y las "
            "cifras son el tamaño. La regla punteada es el día de traslado. "
            "Una semana que nadie informó corta la línea en vez de "
            "atravesarla, y su columna va en raya."), st["note"]),
        Paragraph(PP.text(
            "Estas son sumas sin dividir. La fila de abajo dice cuántas áreas "
            "informaron cada semana, porque una semana con menos formularios "
            "se lee igual que una semana con menos trabajo y no es lo mismo."),
            st["note"]),
    ]
    if len(weeks) > PP.WEEK_COLUMN_LIMIT:
        flow.append(Paragraph(PP.text(
            f"El período tiene {es_display.integer(len(weeks))} semanas "
            f"completas, más de las que caben en columnas; queda la línea."),
            st["note"]))
    return flow


def children_page(model) -> list:
    """The units one level down, weakest first (decisions 14, 15, 16)."""
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    spec = PP.RankedSpec(width=W, cells=_child_cells(model))
    flow = [PP.SectionHead(
        _children_title(model),
        "más atrasada primero · cada celda por área activa")]
    flow.extend(child_rows(model, spec))
    flow.append(Spacer(0, 6))
    flow.append(Paragraph(PP.text(
        "El porcentaje de la derecha es el promedio de los siete Indicadores "
        "Clave de esa unidad contra sus propias metas, por área activa — un "
        "área que no informó cuenta, porque el trabajo que nadie anotó no es "
        "trabajo que no se hizo ni trabajo que sí."), st["note"]))
    return flow


def _child_sub(child, model) -> str:
    """The line under a unit's name in a ranked table.

    Its place in the mission MINUS whatever the running head already says: on
    a zone's own page an area is "El Mirador", not "Angol · El Mirador", and
    the zone's name is at the top of the page either way.

    A unit with no reading at all says so here. Left with only a grey dot and
    a row of dashes it reads as a unit doing badly, when the truth is that
    nobody filed a form.
    """
    trail = [part for part in child.scope.trail if part != model.scope.name]
    bits = [" · ".join(trail)] if trail else []
    if child.mean_attainment is None:
        bits.append("sin informes en el período")
    elif child.coverage is not None:
        bits.append(child.coverage.label)
        if child.areas_silent:
            bits.append(f"{es_display.integer(len(child.areas_silent))} "
                        f"sin informar")
    return " · ".join(b for b in bits if b)


def ranked_unit_rows(units, model, spec: PP.RankedSpec, *,
                     header: str = "unidad") -> list:
    """A ranked table of units — children or areas, the same row either way.

    A unit with nothing to measure keeps its place at the end of the list and
    loses its rank NUMBER: an area that filed no form is not the ninth best
    area, it is an area nobody can rank, and printing "9" beside it invites
    exactly the reading the grey dot is trying to prevent.
    """
    keys = [k for k, _ in _child_keys(model)]
    out = [PP.ranked_row(spec, name=header, header=True)]
    for child in units:
        cells = [_pct(next((m.attainment_per_active_area
                            for m in child.metrics if m.key == key), None))
                 for key in keys]
        out.append(PP.ranked_row(
            spec, rank=child.rank if child.mean_attainment is not None else None,
            name=child.name, sub=_child_sub(child, model),
            status=_attainment_status(child.mean_attainment), cells=cells,
            value=_pct(child.mean_attainment), bar=child.mean_attainment,
            bar_max=100))
    return out


def areas_page(model) -> list:
    """Every area inside the unit, weakest first (decision 15 — no top-N).

    Filled at mission and zone level only. At district level the areas already
    ARE the children, and the same list under two headings is noise.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    if not model.areas_ranked:
        return []
    spec = PP.RankedSpec(width=W, cells=_child_cells(model))
    flow = [PP.SectionHead(
        f"Las {es_display.integer(len(model.areas_ranked))} áreas",
        "más atrasada primero · cada celda por área activa")]
    flow.extend(ranked_unit_rows(model.areas_ranked, model, spec,
                                 header="área"))
    flow.append(Spacer(0, 6))
    flow.append(Paragraph(PP.text(
        "Cada área tiene además su propia página más adelante en el "
        "paquete, con los nombres de la compañería."), st["note"]))
    return flow


def nightly_page(model, goals) -> list:
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    flow = [
        PP.SectionHead(
            "Todo el trabajo nocturno",
            f"más atrasado primero · "
            f"{es_display.integer(len(model.nightly_metrics))} medidas"),
        PP.metric_table(nightly_lines(
            model, goals, comparable=_nightly_comparable(model))),
        Spacer(0, 6),
        Paragraph(PP.text(
            "El relleno es la suma del período contra la meta configurada por "
            "área activa por semana. El color está en el CAMBIO, no en la "
            "barra: estas metas están puestas cerca del doble de lo que la "
            "misión hace hoy, así que pintarlas de rojo cada semana no diría "
            "nada de la semana."), st["note"]),
    ]
    nightly = model.nightly_coverage
    if nightly is not None:
        flow.append(Paragraph(PP.text(
            f"Informes nocturnos del período: {nightly.label} "
            f"({_pct((nightly.rate or 0) * 100)}), "
            f"{es_display.integer(nightly.areas_reporting)} de "
            f"{es_display.integer(nightly.areas_in_scope)} áreas informaron "
            f"al menos una noche."), st["note"]))
    if not _nightly_comparable(model):
        flow.append(Paragraph(PP.text(
            "Sin cambio comparable: el período de comparación casi no tiene "
            "noches registradas, y un porcentaje calculado sobre eso sería la "
            "tarde de un área hablando por toda la unidad."), st["note"]))
    return flow


def rates_and_scores(model) -> list:
    """The four conversion rates and the four scores, where each belongs.

    Rates at mission and zone (decision 13); scores wherever the agent wrote
    any (decision 18), with the area's rank in its district when it has one.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    flow = []
    if model.rates:
        flow.append(PP.SectionHead("Tasas de conversión",
                                   "la razón de los totales de la unidad"))
        flow.append(PP.metric_table(
            rate_lines(model),
            headers=("Tasa", "Real", "Meta", "", "Contra la meta", "")))
        flow.append(Spacer(0, 4))
        flow.append(Paragraph(PP.text(
            "La razón de los totales de la unidad, no el promedio de las "
            "razones de sus áreas: promediar cuarenta áreas deja que un "
            "puñado con pocos contactos y buena suerte levante el número. Un "
            "denominador en cero no es cero por ciento — es que no hubo "
            "lecciones que medir."), st["note"]))
    tiles = score_tiles(model)
    if tiles:
        flow.append(Spacer(0, 10))
        scores = model.scores
        flow.append(PP.SectionHead(
            "Puntajes",
            f"{es_display.integer(scores.areas_scored)} áreas calificadas en "
            f"{es_display.integer(scores.weeks)} semanas"))
        flow.append(PP.stat_tiles(W, tiles))
        note = ("Los cuatro puntajes que escribe el agente, promediados sobre "
                "las semanas del período. Un área que todavía no calificó no "
                "cuenta como cero: no calificada y calificada en cero son "
                "cosas distintas. Van sin color — son una escala de 0 a 100, "
                "no un porcentaje de una meta.")
        if scores.rank:
            note = (f"{model.scope.name} va {es_display.integer(scores.rank)} "
                    f"de {es_display.integer(scores.of)} en su distrito, por "
                    f"efectividad. ") + note
        flow.append(Spacer(0, 4))
        flow.append(Paragraph(PP.text(note), st["note"]))
    return flow


# ── The Tableau pages (M6, M7, Z4) ───────────────────────────────

#: Every Tableau block opens with this, and it is not optional (decision 32).
#: A reader who does not know how far the export reaches cannot weigh a single
#: figure under it.
def _freshness(model) -> str:
    block = model.tableau
    return block.export.freshness_label(model.today)


def _finding_absent(model, title: str) -> list:
    """The refusal, printed where the section would have been.

    Decision 32: a packet with no finding section is better than one quietly
    showing August. The reason is printed rather than the section silently
    disappearing, because a reader who notices the gap should not have to
    guess whether it is a bug.
    """
    st = PP.styles()
    block = model.tableau
    return [
        PP.SectionHead(title, "sin datos"),
        Paragraph(PP.text(f"Sin sección de hallazgo: {block.reason}."),
                  st["body"]),
        Spacer(0, 4),
        Paragraph(PP.text(_freshness(model)), st["note"]),
        Paragraph(PP.text(
            "Las cifras de Tableau no se estiman ni se rellenan con el "
            "período anterior. Cuando la exportación no alcanza, la sección "
            "no se imprime y esta página dice por qué."), st["note"]),
    ]


def _stage_change(stage) -> tuple | None:
    """`(direction, text)` for a funnel stage, or None.

    Only a mature stage carries one. `Stage.change` already refuses for an
    immature one; this is the formatting.
    """
    pct = stage.change
    if pct is None:
        return None
    direction = 0 if abs(pct) < 1 else (1 if pct > 0 else -1)
    return (direction, es_display.signed_percent(pct))


def funnel_block(model) -> list:
    """The cohort funnel, its channel mix and its top sources.

    The three answer one question in three grains: how far the people found in
    this window have travelled, who found them, and by what means.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    block = model.tableau
    stages = block.stages
    flow = [
        PP.stage_bars(W, [(s.label, s.count) for s in stages],
                      mature=[s.mature for s in stages],
                      changes=[_stage_change(s) for s in stages]),
        Spacer(0, 6),
        Paragraph(PP.text(
            "Cada barra son las personas encontradas en esta ventana que han "
            "llegado al menos hasta ahí: una cohorte seguida hacia adelante, "
            "no lo que ocurrió en la ventana. El porcentaje entre barras es "
            "cuántas del paso anterior siguieron."), st["note"]),
    ]
    # One note, not two. The pair said "el embudo sigue a las personas
    # encontradas en esta ventana" twice, and these seven lines print on all
    # 18 finding sections — they have to travel with every page, because a
    # zone leader is handed their own pages and nothing else, so the saving
    # has to come out of the words rather than out of the page.
    if block.maturity_note:
        flow.append(Paragraph(PP.text(block.maturity_note), st["note"]))

    if any(_stage_change(s) for s in stages):
        flow.append(Paragraph(PP.text(
            f"La columna de la derecha compara con los mismos "
            f"{es_display.integer(block.window.days)} días justo antes "
            f"({block.before.label}), para que las dos ventanas midan lo "
            f"mismo."), st["note"]))
    return flow


def mix_block(model) -> list:
    """Who found these people, and by what means."""
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    block = model.tableau
    flow = []
    if block.mix:
        flow += [
            KeepTogether([
                PP.SectionHead("Quién las encontró", "categoría de hallazgo"),
                PP.share_bar(W, [(m.label, m.count) for m in block.mix])]),
            Spacer(0, 4),
            Paragraph(PP.text(
                "Las cuatro categorías de Tableau. Un obrero, un miembro, un "
                "anuncio o un centro de visitantes: la mezcla dice de dónde "
                "viene el trabajo, no si fue bueno."), st["note"]),
        ]
    if block.sources:
        total = block.found or 1
        rows = [[s.label, es_display.integer(s.count),
                 es_display.percent(s.count / total * 100),
                 PP.bar_vs_goal(90, pct=s.count / total * 100,
                                fill=PP.SERIES[0])]
                for s in block.sources]
        flow += [
            Spacer(0, 10),
            KeepTogether([
                PP.SectionHead(
                    "De dónde salieron",
                    f"las {es_display.integer(len(block.sources))} fuentes "
                    f"más grandes"),
                PP.table(rows, (210.0, 60.0, 60.0, 110.0),
                         headers=("fuente", "personas", "del total", ""),
                         align=("l", "r", "r", "l"))]),
            Spacer(0, 4),
            Paragraph(PP.text(
                "El porcentaje es sobre las personas encontradas en esta "
                "ventana, no sobre el año. Una fuente que no aparece no "
                "produjo a nadie en estos días."), st["note"]),
        ]
    return flow


def finding_units_block(model) -> list:
    """The unit ranking under a finding section — zones at mission level, the
    unit's own children below it.

    Ranked by CONTACT RATE rather than by people found, weakest first. Found
    is a size: a big zone finds more people and that is not a verdict on it.
    What a council can act on is the share of those people the missionaries
    got to talk to, which is the same reasoning `zone_comparison` applies to
    every other cross-unit table in this app.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    block = model.tableau
    if not block.units:
        return []
    # 44pt (the default) clipped both headers to "ENCON..." / "ENSEÑ...".
    spec = PP.RankedSpec(width=W, cells=("encontradas", "enseñándose"),
                         cell_width=64.0)
    title = ("Las zonas de la misión" if block.whole_mission
             else f"Sus {block.unit_noun}")
    sub = "menor tasa de contacto primero"
    # The head, the column header and the first rows travel together: without
    # it a district's page ended with "SUS ÁREAS" and an empty column header
    # at the foot and every row on the next sheet. Three rows rather than all
    # of them, so a ten-zone table can still break where it has to.
    # The notes sit ABOVE the rows rather than under them. Measured after the
    # density pass: a closing paragraph left alone at the top of a sheet made
    # eight pages of 116 that were 98% blank, and tying it to the last two
    # rows with `KeepTogether` cost five whole pages — 60pt that jumps takes
    # a page with it. Above the table it explains the bar before the reader
    # meets it and can never be widowed, because the head is already keeping
    # the first rows company.
    notes = [Paragraph(PP.text(
        "La barra es la proporción de las personas encontradas que los "
        "misioneros lograron contactar. Encontradas es un tamaño — una zona "
        "grande encuentra más — así que el orden va por la tasa, no por el "
        "total."), st["note"])]
    if block.whole_mission:
        notes.append(Paragraph(PP.text(
            "Las seis zonas sin formularios de Compass no aparecen en "
            "ninguna otra página de este paquete. Aquí sí, porque Tableau las "
            "cubre y el consejo dirige a toda la misión."), st["note"]))
    opening, flow = ([PP.SectionHead(title, sub)] + notes
                     + [Spacer(0, 2),
                        PP.ranked_row(spec,
                                      name=block.unit_noun.rstrip("s") or "unidad",
                                      header=True)]), []
    for i, unit in enumerate(block.units, start=1):
        marks = []
        if block.whole_mission:
            marks.append("zona piloto de Compass" if unit.roster
                         else "sin formularios de Compass")
        if not unit.found:
            marks.append("nadie encontrado en la ventana")
        flow.append(PP.ranked_row(
            spec, rank=(i if unit.found else None), name=unit.name,
            sub=" · ".join(marks),
            cells=(es_display.integer(unit.found),
                   es_display.integer(unit.teaching)),
            value=(_pct(unit.contact_rate) if unit.contact_rate is not None
                   else es_display.NA),
            bar=unit.contact_rate, bar_max=100))
    return [KeepTogether(opening + flow[:3])] + flow[3:]


def finding_page(model) -> list:
    """M7 · Z4 · the district's finding pages (decisions 20, 24, 32, 34).

    Runs to whatever length the content needs (decision 25); the pagination is
    generated, so nothing downstream cares how many pages it turns out to be.
    """
    st = PP.styles()
    block = model.tableau
    if block is None:
        return []
    title = "Hallazgo"
    if not block.present:
        return _finding_absent(model, title)

    flow = [
        PP.SectionHead(title, block.window.caption),
        Paragraph(PP.text(_freshness(model)), st["note"]),
        Paragraph(PP.text(block.scope_note), st["note"]),
        Spacer(0, 8),
    ]
    flow.extend(funnel_block(model))
    # The three blocks run on rather than each starting a sheet. Forcing a
    # break between them printed three pages of finding behind every one of
    # the 18 units and took the packet from 108 to 163 — for a district, three
    # pages about fifty people. Same reasoning as P4 (h): platypus breaks
    # where it has to and a zone of three districts does not need two thirds
    # of a sheet left blank to prove it.
    for part in (mix_block(model), finding_units_block(model)):
        if part:
            flow.append(Spacer(0, 12))
            flow.extend(part)
    return flow


# ── M6 · the year against its goal ───────────────────────────────

#: A year behind its pace by less than this many baptisms is amber, not red.
#: Roughly one month's work on CCSM's own run rate (36-47 a month), which is
#: the distance a mission can still make up inside a year. Painting a year at
#: 61% of its goal in September entirely red says "lost" about a year that is
#: 32 baptisms behind.
PACE_WARN_BAPTISMS = 40.0


def _pace_status(gap: float | None) -> str | None:
    if gap is None:
        return None
    if gap >= 0:
        return "good"
    return "warn" if gap > -PACE_WARN_BAPTISMS else "bad"


def _baptism_tiles(bap) -> list:
    tiles = [PP.Tile(label="Bautismos certificados",
                     value=(es_display.integer(bap.total)
                            if bap.total is not None else es_display.NA),
                     note=(f"{es_display.integer(bap.months)} meses cerrados"
                           if bap.months else "sin meses cerrados"))]
    if bap.goal:
        tiles.append(PP.Tile(label="Meta anual",
                             value=es_display.integer(bap.goal),
                             note=(f"{_pct(bap.attainment)} alcanzado"
                                   if bap.attainment is not None else "")))
    gap = bap.gap
    if gap is not None:
        tiles.append(PP.Tile(
            label="Contra el ritmo de la meta",
            value=es_display.number(gap, 0) if gap < 0
            else f"+{es_display.number(gap, 0)}",
            note="a esta altura del año",
            status=_pace_status(gap)))
    landing = bap.landing
    if landing:
        tiles.append(PP.Tile(
            label="Si el año sigue así",
            value=es_display.integer(round(landing["value"])),
            note=(f"proyección sobre {es_display.integer(landing['months'])} "
                  f"meses")))
    return tiles


def _period_tiles(bap, period) -> list:
    """The band that leads M6: the selected period's own certified figure
    (decisions 41, 42), and beside it what it is part of.

    For "Año" the figure IS the year to date, so the two tiles beside it split
    it into the months that have closed and the one that has not. For every
    other period the tile beside it is the year to date — the context the
    period's figure sits in, not a second headline.
    """
    fig = bap.period
    tiles = [PP.Tile(
        label=P.WITHIN_LABELS.get(period.key, period.label),
        value=(es_display.integer(fig.count) if fig is not None and fig.present
               else es_display.NA),
        note=(fig.window.label if fig is not None and fig.present
              else "sin cifra certificada"))]
    if fig is not None and fig.present and fig.open_count is not None:
        month = es_display.MONTHS[int(fig.open_month[5:7]) - 1]
        if fig.closed is not None:
            last = es_display.MONTHS[fig.closed_months - 1]
            tiles.append(PP.Tile(label="De meses cerrados",
                                 value=es_display.integer(fig.closed),
                                 note=f"enero a {last}"
                                 if fig.closed_months > 1 else "enero"))
        tiles.append(PP.Tile(label="Del mes en curso",
                             value=es_display.integer(fig.open_count),
                             note=f"{month}, todavía sin cerrar"))
    elif period.key != P.YEAR:
        ytd = bap.year_to_date
        if ytd is not None and ytd.present:
            tiles.append(PP.Tile(
                label=f"En lo que va de {bap.year}",
                value=es_display.integer(ytd.count),
                note=f"hasta el {es_display.day_month(ytd.window.end)}"))
    return tiles


def _period_sentence(bap, period) -> str:
    """What the headline figure covers — `PeriodBaptisms.sentence`, shared with
    the screen so the two cannot word it differently."""
    fig = bap.period
    if fig is None:
        return (f"No hay cifra certificada de bautismos para {period.label} "
                f"(decisión 42).")
    return fig.sentence(period.label)


def baptism_page(model) -> list:
    """M6 — the period's baptisms, then the year against its one annual goal.

    The period leads (decisions 41, 42): switch the period and the headline
    changes with it, and it is the CERTIFIED figure for exactly those days or
    no figure. The year below is context and is unchanged: its pace, its
    projection and its month table stay on closed months, because a month half
    counted drawn as a point makes the year look like it is collapsing.

    Certified figures only (decision 21). The weekly form's own baptism Key
    Indicator is on M2 and does not agree with this; both are named here
    rather than reconciled into a number that is neither.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    block = model.tableau
    bap = block.baptisms if block is not None else None
    if bap is None:
        return []

    flow = [PP.SectionHead(f"Bautismos · {model.period.label}",
                           "cifra certificada · fuente: Tableau"),
            PP.stat_tiles(W, _period_tiles(bap, model.period)),
            Spacer(0, 4),
            Paragraph(PP.text(_period_sentence(bap, model.period)),
                      st["note_lead"]),
            PP.SectionHead(f"El año {bap.year} contra su meta",
                           "meses cerrados · fuente: Tableau"),
            PP.stat_tiles(W, _baptism_tiles(bap)), Spacer(0, 10)]

    if bap.goal and bap.attainment is not None:
        pace = bap.pace
        mark = None
        if pace and bap.months:
            mark = pace[bap.months - 1] / float(bap.goal) * 100
        flow += [
            PP.bar_vs_goal(W, pct=bap.attainment, height=11.0,
                           status=_pace_status(bap.gap), mark_pct=mark),
            Spacer(0, 5),
            Paragraph(PP.text(
                f"{bap.certified_label} de una meta de "
                f"{es_display.integer(bap.goal)}. La marca violeta es dónde "
                f"debería ir el año a esta altura, a un doceavo de la meta "
                f"por mes."), st["note"]),
        ]
    if bap.total is None:
        flow.append(Paragraph(PP.text(
            f"{bap.certified_label}: TABLEAU_BAPTISMS no tiene ningún mes "
            f"cerrado de {bap.year}, así que el año no se dibuja contra su "
            f"meta. No es un año sin bautismos; es un año sin captura."),
            st["note"]))
    if bap.provisional_label:
        flow.append(Paragraph(PP.text(
            f"{bap.provisional_label}. Está en lo que va del año, arriba, pero "
            f"no en esta barra ni en el ritmo: un mes a medio contar dibujado "
            f"como punto hace que el año parezca desplomarse cada vez que se "
            f"genera el paquete."),
            st["note"]))

    months = [(es_display.MONTHS_ABBR[i], bap.certified.get(
        f"{bap.year:04d}-{i + 1:02d}")) for i in range(12)]
    shown = [(name, value) for name, value in months if value is not None]
    if shown:
        biggest = max(value for _, value in shown) or 1
        rows = [[name, es_display.integer(value),
                 PP.bar_vs_goal(120, pct=value / biggest * 100,
                                fill=PP.SERIES[0])]
                for name, value in shown]
        flow += [
            Spacer(0, 12),
            PP.SectionHead("Mes a mes", "sólo meses cerrados"),
            PP.table(rows, (120.0, 60.0, 140.0),
                     headers=("mes", "bautismos", ""),
                     align=("l", "r", "l")),
        ]

    # The note is unconditional. It is the packet's statement about WHICH of
    # two disagreeing figures it used, and that is worth saying even in a
    # period where the form happened to report nothing.
    ki = model.ki("ki_baptized_confirmed_real")
    said = (f"El formulario semanal de las compañerías informó "
            f"{_count(ki.actual)} en {model.period.label.lower()}, y las dos "
            f"no coinciden: los misioneros no siempre anotan el campo."
            if ki is not None else
            "El formulario semanal de las compañerías pregunta lo mismo y no "
            "coincide: los misioneros no siempre anotan el campo.")
    flow += [
        Spacer(0, 10),
        Paragraph(PP.text(
            f"Sobre la cifra de bautismos (decisión 21). Arriba está la cifra "
            f"CERTIFICADA de Tableau, que es la que cuenta. {said} Donde "
            f"exista la certificada se usa esa; la del formulario aparece en "
            f"sus Indicadores Clave bajo su propio nombre, y nunca se "
            f"suman."), st["note_lead"]),
    ]
    return flow


# ── The pages of one unit ────────────────────────────────────

#: How much room a section needs before it is allowed to start.
#:
#: A section head with nothing under it is worse than the blank space it was
#: trying to use: the reader turns the page looking for the table it promised.
#: 140pt is the head, its rule, a table header and about four rows — measured
#: against `metric_table` at 3,5pt padding, whose rows run 17-21pt.
SECTION_FLOOR = 140.0


def run_on(blocks, *, gap: float = 10.0, floor: float | None = None) -> list:
    """Sections one after another down the page, breaking only when they must.

    Phase V's whole density change, in one function. Every unit's page used to
    be built as `PageBreak()` between every section, which is why the packet
    measured **36,6% blank at the foot of the average page** over 134 pages —
    a Key Indicator table is seven rows and took a sheet, a week-by-week strip
    is seven more and took another.

    Zackary, 2026-09-23: "I don't want to have much or any white space at
    all." So sections run on, and a `CondPageBreak` keeps one from starting
    where it cannot get four rows in. A table longer than the room left still
    splits — `packet_parts.table` repeats its header row, so the half on the
    second page is not a stack of unlabelled figures.

    This is decision 25 read the way he meant it: take the pages the content
    needs, and not one more.
    """
    floor = SECTION_FLOOR if floor is None else floor
    out = []
    for block in blocks:
        if not block:
            continue
        if out:
            out.append(Spacer(0, gap))
            out.append(CondPageBreak(floor))
        out.extend(block)
    return out


def mission_pages(model, goals, peers=None) -> list:
    """M1-M7: where we stand, the seven, the weeks, the zones, the nights, the
    year's baptisms, the finding.

    M6 and M7 sit where §3.2 numbered them — after the nightly work and before
    the scores — rather than being promoted for being outcomes. The baptism
    figure is already the first tile on M1, so M6 is the year's ARC, which is
    context and reads better once the council knows what the fortnight held.
    """
    weekly_ok = _weekly_comparable(model)
    weekly_sure = _weekly_confident(model)
    # Outcomes, then activity, then process — §3.2's order within every unit,
    # and the reason the scores come last rather than first: they are a
    # judgement about how the work was done, and a council reads them after it
    # knows what the work was.
    return run_on([
        at_a_glance(model, weekly_ok=weekly_ok, weekly_sure=weekly_sure),
        key_indicator_page(model, weekly_ok=weekly_ok, weekly_sure=weekly_sure),
        week_page(model), children_page(model),
        nightly_page(model, goals), baptism_page(model),
        finding_page(model), rates_and_scores(model),
    ])


def zone_pages(model, goals, peers=None) -> list:
    """Z1-Z3 plus the week-by-week: at a glance, the seven, its districts and
    every one of its areas, the nights.

    The same order as the mission's, because the reader is the same reader one
    rung down and Provo's zone page opens exactly like its mission page.

    The area roster is the page a zone leader actually uses — Provo's "EVERY
    AREA IN KINGS PEAK — ALL 8" — and it is every area, not a top five
    (decision 15). It runs on from the district table rather than starting its
    own page: a zone of three districts left two thirds of a sheet blank, and
    platypus breaks the list wherever it has to.

    Z4 is the finding section, roster-scoped: a zone's pages count the zone's
    own areas, never the export's idea of which zone an area is in.
    """
    weekly_ok = _weekly_comparable(model)
    weekly_sure = _weekly_confident(model)
    # §3.2's order, unchanged. The district's tail had to be rearranged to
    # save a sheet; measured, the same move here saved nothing and put two of
    # the four zones at 51% blank instead of 41.
    return run_on([
        at_a_glance(model, weekly_ok=weekly_ok, weekly_sure=weekly_sure),
        key_indicator_page(model, weekly_ok=weekly_ok, weekly_sure=weekly_sure),
        week_page(model), children_page(model), areas_page(model),
        nightly_page(model, goals), finding_page(model),
        rates_and_scores(model),
    ])


def district_pages(model, goals, peers=None) -> list:
    """The same shape as the zone's, one rung down.

    The comparison is the whole reason this page exists. A district leader has
    no way to know whether 73% is good until they can see the zone at 78 and
    the mission at 76 — the audit's own words, and the thing nothing in
    Compass did before. Since Phase V it is `at_a_glance`'s own ladder block,
    so it is the same section a zone reads against the mission.

    It has no "todas las áreas" section: at district level the areas ARE the
    children, and the same list under two headings is noise.
    """
    weekly_ok = _weekly_comparable(model)
    weekly_sure = _weekly_confident(model)
    # The scores ride with the children rather than closing the unit. §3.2
    # put them last so a council reads a judgement about HOW the work was done
    # after it knows what the work was — which held while every section had a
    # page of its own. Now they are all one document four sheets long, and
    # measured on the live packet the four score tiles alone were taking a
    # fifth sheet that was 84% blank in all thirteen districts.
    # The nightly table closes the district, and the finding section comes
    # before it — §3.2's own order (outcomes, finding, nightly work), and the
    # only block long enough to SPLIT across the last page boundary rather
    # than jumping it. Measured: the finding section closing the unit put
    # seven of thirteen districts on a fifth sheet that was 84% blank.
    return run_on([
        at_a_glance(model, weekly_ok=weekly_ok, weekly_sure=weekly_sure),
        children_page(model), rates_and_scores(model),
        key_indicator_page(model, weekly_ok=weekly_ok, weekly_sure=weekly_sure),
        week_page(model),
        finding_page(model), nightly_page(model, goals),
    ])


def _children_title(model) -> str:
    return {S.MISSION: "Zonas", S.ZONE: "Distritos",
            S.DISTRICT: "Áreas"}.get(model.scope.level, "Unidades")


def _child_cells(model) -> tuple:
    return tuple(short for _, short in _child_keys(model))


def _week_rows(model):
    """`(weeks, rows, boundary indices)` for the week-by-week table.

    A week nobody reported arrives as None and the line breaks there rather
    than joining across it; the column prints an em dash for the same reason.
    The boundaries are the INDICES of the weeks that open a transfer, so the
    rule lands between two columns instead of through one.
    """
    weeks, rows, boundaries, reporting = [], [], [], []
    for row in model.key_indicators:
        series = model.series.get(row.key)
        if series is None or not series.points:
            continue
        if not weeks:
            weeks = [p.week for p in series.points]
            reporting = [p.reporting for p in series.points]
            for day, _ in series.boundaries:
                after = [i for i, w in enumerate(weeks) if w >= day]
                if after and after[0] > 0:
                    boundaries.append(after[0])
        rows.append((row.label, [p.actual for p in series.points],
                     _count(row.actual)))
    return weeks, rows, boundaries, reporting


def furthest_behind(model, limit: int = 3) -> list:
    """The Key Indicators furthest from their own goal, weakest first.

    Provo's "THE SIX FURTHEST BEHIND", at CCSM's scale. The same candidates as
    the two sentences above it on the page (`_verdict_candidates`): a list of
    the most behind is the same claim as "lo que hay que mover", three times,
    and decision 37's reason applies to it word for word.
    """
    graded = _verdict_candidates(model)
    return sorted(graded, key=lambda r: r.grade.pct)[:limit]

# ── An area, which is a companionship ───────────────────────────

#: How tall one area's block is allowed to be, so two fit on a page with a
#: rule between them. Measured against the frame rather than guessed: 688pt of
#: content, less 12pt for the divider, halved.
AREA_BLOCK_HEIGHT = (PP.CONTENT_HEIGHT - 12) / 2


def _area_spark(model, row) -> object:
    """One Key Indicator's complete weeks, as a drawing for its own row."""
    series = model.series.get(row.key)
    if series is None or len(series.points) < 2:
        return None
    first = series.points[0].week
    span = max(1, (series.points[-1].week - first).days)
    boundaries = [max(0.0, min(1.0, (day - first).days / span))
                  for day, _ in series.boundaries]
    return PP.sparkline(AREA_COLUMNS_SPARK, 9.0,
                        [p.actual for p in series.points],
                        boundaries=boundaries)


#: The width the spark gets inside the area table's last column.
AREA_COLUMNS_SPARK = PP.AREA_COLUMNS[5] - 10


def area_lines(model) -> list:
    """The area's seven, each carrying its own weeks."""
    lines = ki_lines(model, comparable=False)
    return [replace(line, spark=_area_spark(model, row))
            for line, row in zip(lines, model.key_indicators)]


def area_block(model) -> list:
    """One area's half page: who they are, their seven, what they are good at.

    §3.2's list, in the order a companionship reads it. Their names first
    (decision 27 — this is the one thing the old page never had), then the
    seven against the goal they set themselves, then the two lines the agents
    already chose for them, then their scores and where they sit in their
    district.

    "Su fortaleza / Para crecer" is READ, never recomputed: WEEKLY_BREAKDOWNS
    stores `strength1_metric`, `strength2_metric` and `growth_metric` per area
    per week, picked by the Apps Script agents, and a second opinion printed
    beside the agents' own would be two answers to one question.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    trail = " · ".join(model.scope.trail)
    flow = [
        Paragraph(PP.text(model.scope.name), st["area_title"]),
        PP.companionship_line(model.scope.companions),
        Paragraph(PP.text(" · ".join(x for x in (trail, model.compliance_label)
                                     if x)), st["note"]),
        Spacer(0, 4),
        PP.area_metric_table(area_lines(model)),
    ]
    strong = ", ".join(model.strengths)
    grow = model.growth or ""
    if strong or grow:
        bits = []
        if strong:
            bits.append(f"Su fortaleza: {strong}")
        if grow:
            bits.append(f"Para crecer: {grow}")
        flow.append(Spacer(0, 3))
        flow.append(Paragraph(PP.text(" · ".join(bits)), st["note_lead"]))
    else:
        flow.append(Spacer(0, 3))
        flow.append(Paragraph(PP.text(
            "Sin fortaleza ni meta de crecimiento esta semana — "
            "WEEKLY_BREAKDOWNS va una semana atrás de los Indicadores Clave."),
            st["note"]))
    scores = model.scores
    if scores is not None and scores.measured:
        parts = [f"{name} {es_display.number(value, 1)}"
                 for name, value in (("Esfuerzo", scores.effort),
                                     ("Habilidad", scores.skill),
                                     ("Indicadores Clave", scores.ki),
                                     ("Efectividad", scores.effectiveness))
                 if value is not None]
        line = "Puntajes: " + " · ".join(parts)
        if scores.rank:
            line += (f" — {es_display.integer(scores.rank)}º de "
                     f"{es_display.integer(scores.of)} en su distrito, por "
                     f"efectividad")
        flow.append(Paragraph(PP.text(line), st["note"]))
    ladder = area_ladder_line(model)
    if ladder:
        flow.append(Paragraph(PP.text(ladder), st["note_lead"]))
    # The half page had 68pt of air under it, measured. This is what goes
    # there: where the companionship sits among the other areas of their own
    # district, which is the comparison they can actually see happening.
    flow.extend(sibling_strip(model))
    return flow


def area_ladder_line(model) -> str:
    """The area against its district, its zone and the mission, in one line.

    The half page has no room for the ranked table a zone or a district gets,
    and a companionship's question is smaller anyway: are we ahead of or
    behind the people around us. Three signed figures answer it in the space
    a sentence takes.
    """
    bits = [f"{r.role} {_signed(r.delta)}" for r in model.ladder[1:]
            if not r.is_self and r.delta is not None]
    return ("Contra " + " · ".join(bits)) if bits else ""


def _signed(points: float) -> str:
    """A gap in percentage points, with the sign a reader needs to see."""
    sign = "+" if points >= 0 else "-"
    return f"{sign}{es_display.number(abs(points), 0)} pts"


# ── The body ──────────────────────────────────────────────

#: What the running head calls a unit, per level.
EYEBROW = {S.ZONE: "Zona", S.DISTRICT: "Distrito", S.AREA: "Área"}


def furniture_for(model) -> PP.Furniture:
    """The running head and footer for one unit's stretch of pages.

    The mission's eyebrow is its own name; everything below it is named by its
    level, so a page torn out of the middle says what kind of thing it is about
    before it says which one.
    """
    level = model.scope.level
    if level == S.AREA:
        # Two areas share a page and the pairs run alphabetically across the
        # whole mission, so they need not share a district — the first draft
        # headed a page "Distrito · La Marina 1" above an area from San Pedro
        # 1. The head names the SECTION instead, which is true of both, and
        # each block states its own district under its own name.
        return PP.Furniture(eyebrow="Áreas",
                            period=model.period.window_label,
                            mission=model.mission_name)
    eyebrow = (model.mission_name if level == S.MISSION
               else f"{EYEBROW[level]} · {model.scope.name}")
    return PP.Furniture(eyebrow=eyebrow, period=model.period.window_label,
                        trail=" · ".join(model.scope.trail),
                        mission=model.mission_name)


#: One builder per level. The mission's and the zone's are the same shape in a
#: different order; the district's is denser, because §3.2 budgets it a page
#: and its content fits one.
PAGES = {S.MISSION: lambda m, g, p: mission_pages(m, g, p),
         S.ZONE: lambda m, g, p: zone_pages(m, g, p),
         S.DISTRICT: lambda m, g, p: district_pages(m, g, p)}


def unit_pages(model, goals, peers=None) -> list:
    """One unit's pages, whichever level it is. P5 adds the area's."""
    flow = [PP.SetFurniture(furniture_for(model))]
    build = PAGES.get(model.scope.level)
    if build is None:
        return flow + _heading(model)
    return flow + build(model, goals, peers or {})


def data_note(models, goals=None) -> list:
    """The last page: where every figure came from, and what is missing.

    Provo's "About the baptism figure" note, generalised. The rule it follows
    is that a reader who wants to argue with a number should be able to find
    out what it is made of without asking anybody — which is also the only
    thing that makes the rest of the packet safe to hand out.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    mission = next((m for m in models if m.scope.level == S.MISSION), None)
    flow = [PP.SectionHead("Nota de datos", "de dónde sale cada cifra")]
    if mission is None:
        return flow
    period = mission.period
    cov = mission.coverage
    rows = [
        ["Indicadores Clave", "WEEKLY_KI",
         "Lo que las compañerías informaron cada semana, filtrado al "
         "organigrama por el agente."],
        ["Meta de las compañerías", "Formulario semanal",
         "La meta de una semana se escribe en el formulario de la semana "
         "ANTERIOR, y así se lee aquí."],
        ["Meta de traslado", "AREA_TRANSFER_GOALS",
         "La meta del liderazgo por área por ciclo, prorrateada a la parte "
         "del traslado que cubre este período."],
        ["Trabajo nocturno", "DAILY_LOG",
         "Un informe por área por noche. La meta por métrica sale de "
         "AGENT_CONFIG y es una sola cifra para toda la misión."],
        ["Fortaleza y crecimiento", "WEEKLY_BREAKDOWNS",
         "Elegidas por los agentes, no recalculadas aquí. Esa pestaña va una "
         "semana atrás de WEEKLY_KI."],
        ["Puntajes", "SCORES",
         "Los cuatro puntajes del agente, promediados sobre las semanas del "
         "período. Un área sin calificar no cuenta como cero."],
        ["Organigrama", "MISSION_ORG",
         "Zona, distrito y compañería. La pertenencia se decide aquí y nunca "
         "en la columna de una fila de datos."],
        ["Hallazgo", "TABLEAU_DETAIL",
         "Una fila por persona encontrada, con las fechas de sus hitos. "
         "Cubre las 10 zonas; los formularios de Compass cubren 4."],
        ["Bautismos del año", "TABLEAU_BAPTISMS",
         "La cifra certificada por mes. No es la que informa el formulario "
         "semanal, y las dos no se suman."],
    ]
    flow.append(PP.table(rows, [128, 118, W - 246],
                         headers=["Cifra", "Fuente", "Qué es"]))
    flow.append(Spacer(0, 10))
    flow.append(PP.SectionHead("Lo que este paquete no dice", rule=False))
    sentences = [
        f"Período: {period.label}, {period.window_label}. "
        f"{period.progress_label}. Sólo se cuentan semanas completas; la "
        f"semana en curso no aparece en ninguna cifra.",
        f"Cumplimiento: {mission.compliance_label}. Cada porcentaje de este "
        f"paquete se apoya en eso, y una unidad que informó la mitad tiene "
        f"cifras que valen la mitad.",
    ]
    if cov is not None and cov.thin:
        sentences.append(
            "La cobertura de este período es demasiado delgada para sostener "
            "una comparación: las cifras se muestran, las flechas no.")
    silent = mission.areas_silent
    if silent:
        sentences.append(
            f"{es_display.integer(len(silent))} de "
            f"{es_display.integer(mission.scope.area_count)} áreas no "
            f"informaron ninguna semana completa del período: "
            f"{', '.join(sorted(silent))}. Cuentan en cada denominador por "
            f"área activa, y no aparecen en ninguna suma.")
    flagged = [r for r in mission.key_indicators if r.grade.flag]
    if flagged:
        names = ", ".join(r.label for r in flagged)
        sentences.append(
            f"Meta no utilizable: {names}. La cifra es real y la meta no da "
            f"para medirla, así que la fila se muestra sin calificar en vez "
            f"de pintarse de rojo. Hay que revisar la meta, no el trabajo.")
    nightly_flags = [r for r in mission.nightly_metrics if r.grade.flag]
    if nightly_flags:
        names = ", ".join(r.label for r in nightly_flags)
        sentences.append(
            f"Lo mismo en el trabajo nocturno: {names}.")
    sentences.append(
        "Las metas nocturnas de AGENT_CONFIG están puestas cerca del doble de "
        "lo que la misión hace hoy. Por eso esas filas se califican por su "
        "movimiento y no por su distancia a la meta.")
    sentences.extend(_tableau_sentences(mission))
    for line in sentences:
        flow.append(Paragraph(PP.text(line), st["note_lead"]))
    flow.append(Spacer(0, 8))
    flow.append(Paragraph(PP.text(
        f"Generado por PMG Compass desde COMPASS_CCSM el "
        f"{es_display.long_date(mission.today)}."), st["note"]))
    return flow


def _tableau_sentences(mission) -> list:
    """What the data note says about the finding figures (decisions 32, 34, 35).

    Four things, and the packet is not safe to hand out without any of them:
    where the export reaches, that its pages count a different set of zones
    from every other page, which names it carries that the roster does not,
    and — when there is no section at all — why.
    """
    block = getattr(mission, "tableau", None)
    if block is None:
        return ["Sin sección de hallazgo: este paquete se generó sin acceso "
                "a la exportación de Tableau."]

    out = [block.export.freshness_label(mission.today) + "."]
    source = block.export.source_label()
    if source:
        out[-1] = out[-1][:-1] + f", cargada por {source}."

    if not block.present:
        out.append(f"Sin sección de hallazgo en este paquete: {block.reason}. "
                   f"Las cifras de Tableau no se estiman ni se rellenan con "
                   f"el período anterior.")
        return out + _baptism_sentences(mission, block.baptisms)

    window = block.window
    out.append(
        f"Las páginas de hallazgo se apoyan en {window.label}"
        + (f", que son {window.shortfall_label}: la exportación termina antes "
           f"de que termine el período, y esas páginas no cubren los últimos "
           f"días." if window.clipped else ", el período completo.")
    )
    out.append(
        "Toda cifra de hallazgo viene de Tableau y toda cifra de Indicadores "
        "Clave y de trabajo nocturno viene de los formularios de Compass. "
        "Nunca se suman ni comparten una tabla: los formularios cubren las 4 "
        "zonas del piloto y Tableau cubre las 10, y la página de hallazgo de "
        "la misión es la única del paquete que cuenta las diez.")
    rec = block.reconciliation
    if rec is not None and rec.note:
        out.append(rec.note)
    out.append(
        "Las áreas de Tableau se emparejan con MISSION_ORG por nombre de "
        "área. La zona y el distrito de cada cifra son los del roster, no los "
        "de Tableau, que registra dónde estaba un área cuando se escribió la "
        "fila.")
    return out + _baptism_sentences(mission, block.baptisms)


def _baptism_sentences(mission, baptisms) -> list:
    """Where the baptism figures come from (decisions 21, 41, 42).

    Said whether or not the finding section printed: the baptism page does not
    rest on the Detail export, so a refused finding section is no reason to
    leave its source unexplained.
    """
    if baptisms is None:
        return []
    out = []
    fig = baptisms.period
    label = mission.period.label
    if fig is not None and fig.present:
        days = fig.window
        out.append(
            f"Bautismos de {label}: {es_display.integer(fig.count)} "
            f"certificados por Tableau, del {days.label}"
            + (f" ({days.shortfall_label})" if days.clipped else "") + ".")
    elif fig is not None:
        out.append(f"Bautismos de {label}: sin cifra certificada — "
                   f"{fig.reason}.")
    out.append(
        "Cada período lee la captura certificada de sus propios días: el mes "
        "y el año, de TABLEAU_BAPTISMS; la semana, los traslados y las "
        "últimas seis semanas, de TABLEAU_BAPTISM_WINDOWS, que la "
        "sincronización nocturna llena. Nunca los registros de Tableau por "
        "persona, que quedan por debajo de la certificada, ni el formulario "
        "semanal (decisión 42).")
    if baptisms.provisional_label:
        out.append(f"Bautismos del año: {baptisms.certified_label}. "
                   f"{baptisms.provisional_label[0].upper()}"
                   f"{baptisms.provisional_label[1:]}, así que entra en lo que "
                   f"va del año pero no en el ritmo ni en la proyección.")
    return out


def _body(models, goals, pagination: Pagination) -> list:
    """Every unit in packet order, with the markers the second pass reads.

    Two markers per unit: one for the section the unit opens, if it is the
    first of its level, and one for the unit itself. The run sheet needs the
    second — it names a zone leader's own pages — and the contents needs the
    first.

    The areas are handed to `area_pages` as a block rather than one at a time,
    because two of them share a page (§3.2) and the page break belongs between
    the pairs rather than before every unit.
    """
    section_of = {S.MISSION: MISSION, S.ZONE: ZONES, S.DISTRICT: DISTRICTS,
                  S.AREA: AREAS}
    # Every model by scope key, so a district page can look up its zone and the
    # mission without a second query (R6's note: `build_all` already returns
    # all 63, and a peer-series field only one page would read does not belong
    # on the model).
    peers = {m.scope.key: m for m in models}
    areas = [m for m in models if m.scope.level == S.AREA]
    flow, opened = [], set()
    for model in models:
        if model.scope.level == S.AREA:
            continue
        key = section_of[model.scope.level]
        flow.append(PageBreak())
        if key not in opened:
            opened.add(key)
            flow.append(SectionStart(key, pagination))
        flow.append(SectionStart(model.scope.key, pagination))
        flow.extend(unit_pages(model, goals, peers))
    if areas:
        flow.append(PageBreak())
        flow.append(SectionStart(AREAS, pagination))
        for i, model in enumerate(areas):
            if i and i % 2 == 0:
                flow.append(PageBreak())
            elif i:
                flow.append(Spacer(0, 6))
                flow.append(PP.HairRule(color=PP.RULE, space_before=0,
                                        space_after=6))
            if i % 2 == 0:
                flow.append(PP.SetFurniture(furniture_for(model)))
            flow.append(SectionStart(model.scope.key, pagination))
            flow.append(KeepTogether(area_block(model)))
    flow.append(PageBreak())
    # Its own furniture, or it inherits the last area spread's and the page
    # explaining every source in the packet is headed "Áreas".
    mission = next((m for m in models if m.scope.level == S.MISSION), None)
    if mission is not None:
        # No key: the data note grades nothing, and the three states in its
        # footer would be a key to a page with no colour on it.
        flow.append(PP.SetFurniture(PP.Furniture(
            eyebrow="Nota de datos",
            period=mission.period.window_label,
            mission=mission.mission_name, key=False)))
    flow.append(SectionStart(DATA_NOTE, pagination))
    flow.extend(data_note(models, goals))
    return flow


# ── The build ────────────────────────────────────────────

#: How many times the document is laid out before its page numbers are taken as
#: settled. Two is the usual answer and three is the ceiling: printing the
#: ranges the first pass measured can lengthen the guide by a row and move
#: everything after it, and that correction can itself move a row. Past three
#: the document is oscillating, and the last pass is used rather than looping.
MAX_PASSES = 3


def build_packet(models, roster, goals=None) -> bytes:
    """Every model, one PDF — the whole of decision 1.

    Laid out repeatedly until a pass confirms the page numbers it was handed.
    """
    goals = dict(goals or {})
    sections = sections_for(models)
    unit_keys = [m.scope.key for m in models]
    mission = next((m for m in models if m.scope.level == S.MISSION), None)
    if mission is None:
        raise ValueError("el paquete necesita el modelo de la misión")

    given, pdf = Pagination(), b""
    for _ in range(MAX_PASSES):
        measured = Pagination()
        resolved = given.resolve(sections) if given.measured else sections
        spans = given.unit_ranges(unit_keys) if given.measured else {}
        units = [(m.scope, spans[m.scope.key]) for m in models
                 if m.scope.key in spans
                 and m.scope.level in (S.ZONE, S.DISTRICT)]
        total = max((s.last_page for s in resolved if s.present), default=0)
        flow = (front_matter(mission, resolved, units, roster,
                             total_pages=total)
                + _body(models, goals, measured))
        pdf, measured.total = _render(flow)
        if measured.same_as(given):
            break
        given = measured
    return pdf


def build(period_key: str = None, against: str = None, *, data=None) -> bytes:
    """A period in, a packet out — the whole of `build_packet(period)`.

    The one call the screen's button makes. It reads the sheet once, builds the
    63 models and lays the document out; measured live on CCSM it is about 35
    seconds for the models and 20 for the PDF, which is why the button stores
    the bytes rather than a `download_button` regenerating them on every rerun.

    ``data`` is injected by the screen, which already has a cached
    `ReportData` — so a packet built from the page costs the render alone.
    """
    from app.reports import model as M
    from app.reports import periods as P

    data = data or M.load_data()
    models = M.build_all(period_key or P.DEFAULT_PERIOD,
                         against or P.COMPARE_PRIOR, data=data)
    if not models:
        raise ValueError("no hay período que informar")
    return build_packet(models, data.roster, data.nightly_goals)


def filename(model) -> str:
    """What the browser saves it as. ISO, because a filename is a key."""
    return (f"paquete-consejo-{model.period.key}-"
            f"{model.today.isoformat()}.pdf")
