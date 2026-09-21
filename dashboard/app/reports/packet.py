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

from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, PageBreak,
                                PageTemplate, Paragraph, Spacer)

from app.config import es_display
from app.reports import packet_parts as PP
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

    Titles carry their own counts ("Cada zona - 4 zonas") because Provo's
    contents does and it answers the second question a reader has. The counts
    come from the models actually built, never from the roster, so a packet
    built with one zone missing says three when there are three.
    """
    zones = sum(1 for m in models if m.scope.level == S.ZONE)
    districts = sum(1 for m in models if m.scope.level == S.DISTRICT)
    areas = sum(1 for m in models if m.scope.level == S.AREA)
    return [
        Section(MISSION, "La misión", "Todos en el consejo"),
        Section(ZONES, f"Cada zona — {zones} zonas",
                "Se discute zona por zona"),
        Section(DISTRICTS, f"Cada distrito — {districts}, una página cada uno",
                "Entregar a cada líder de distrito"),
        Section(AREAS, f"Cada área — {areas}, dos por página",
                "Referencia durante el consejo"),
        Section(DATA_NOTE, "Nota de datos",
                "Quien pregunte de dónde sale una cifra", "Referencia"),
    ]


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
    rows = hand_outs(sections, units, roster)
    paper = sheets(rows)
    lead = leadership(roster)
    missing = lead.districts_without_a_leader
    closing = [
        f"Papel total: {paper} hojas a doble cara si imprime exactamente las "
        f"filas de arriba. Las copias salen de MISSION_ORG — una por "
        f"companería de liderazgo."]
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
                 f"que las companerías informaron; la nota de datos al final "
                 f"dice qué falta y por qué.")
        + [PageBreak(),
           PP.SetFurniture(PP.Furniture(
               eyebrow=mission.mission_name, period=period.window_label,
               mission=mission.mission_name))]
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
        if row.has_leadership_goal and row.meta:
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
    keys = [k for k, _ in _child_keys(model)]
    out = [PP.ranked_row(spec, name="unidad", header=True)]
    for child in model.children:
        cells = [_pct(next((m.attainment_per_active_area
                            for m in child.metrics if m.key == key), None))
                 for key in keys]
        silent = (f" · {es_display.integer(len(child.areas_silent))} sin informar"
                  if child.areas_silent else "")
        out.append(PP.ranked_row(
            spec, rank=child.rank, name=child.name,
            sub=f"{child.coverage.label}{silent}" if child.coverage else "",
            status=_attainment_status(child.mean_attainment),
            cells=cells, value=_pct(child.mean_attainment),
            bar=child.mean_attainment, bar_max=100))
    return out


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
              "contra la meta que las companerías se pusieron, por área que "
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


def _best_and_worst(model):
    """The strongest and the weakest graded Key Indicator, by attainment.

    A flagged goal is not eligible for either: it is neither the mission's best
    work nor its worst, and naming it as either would be reporting the goal as
    though it were the work (decision 22).
    """
    graded = [r for r in model.key_indicators
              if r.grade.pct is not None and not r.grade.flag]
    if not graded:
        return None, None
    ordered = sorted(graded, key=lambda r: r.grade.pct)
    return ordered[-1], ordered[0]


def mission_pages(model, goals) -> list:
    """M1-M5: where we stand, the seven, the weeks, the zones, the nights.

    One `ReportModel` and nothing else. M6 (baptisms against the annual goal)
    and M7 (finding) both read TABLEAU_BAPTISMS and the Tableau export, so they
    belong to phase T with the rest of the freshness gate and decision 34's
    separation — putting them here would have meant a form-sourced page
    quietly carrying a Tableau figure.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    weekly_ok = _weekly_comparable(model)
    weekly_sure = _weekly_confident(model)
    best, worst = _best_and_worst(model)

    # M1 — where the mission stands
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
                    f"contra {_count(worst.meta)}. Es el número que mover antes "
                    f"del próximo consejo."), st["body"]))
    flagged = [r for r in model.key_indicators if r.grade.flag]
    for row in flagged:
        flow.append(Paragraph(
            PP.text(f"{row.label}: {row.grade.flag_label}. "
                    f"{_count(row.actual)} contra una meta declarada de "
                    f"{_count(row.meta)}. La cifra es real; la meta hay que "
                    f"revisarla."), st["note_lead"]))
    flow.append(Spacer(0, 8))
    flow.append(PP.stat_tiles(W, _headline_tiles(model)))
    flow.append(Spacer(0, 10))
    behind = furthest_behind(model)
    if behind:
        flow.append(PP.SectionHead(
            "Los tres más atrasados",
            "de los Indicadores Clave con una meta utilizable"))
        wanted = {r.label for r in behind}
        flow.append(PP.metric_table(
            [line for line in ki_lines(model, comparable=weekly_ok,
                                       confident=weekly_sure)
             if line.label in wanted],
            headers=("Métrica", "Real", "Meta", "", "Contra la meta",
                     "Cambio")))
    flow.append(Spacer(0, 8))
    flow.append(PP.legend(W, GRADED_NOTE))

    # M2 — every Key Indicator against its goal
    flow.append(PageBreak())
    flow.append(PP.SectionHead("Indicadores Clave",
                               f"los siete · {model.compliance_label}"))
    flow.append(PP.metric_table(ki_lines(model, comparable=weekly_ok, confident=weekly_sure)))
    flow.append(Spacer(0, 6))
    flow.append(Paragraph(PP.text(BASIS_NOTE), st["note"]))
    flow.append(Paragraph(PP.text(_comparison_note(model)), st["note"]))
    flow.append(Spacer(0, 4))
    flow.append(PP.legend(W, GRADED_NOTE))

    # M3 — the seven, week by week
    flow.append(PageBreak())
    weeks, week_rows, boundaries, reporting = _week_rows(model)
    flow.append(PP.SectionHead("Semana a semana", "solo semanas completas"))
    flow.append(PP.week_table(
        W, weeks, week_rows, boundaries=boundaries,
        footer=("Áreas que informaron, de "
                f"{es_display.integer(model.scope.area_count)}", reporting,
                "")))
    flow.append(Spacer(0, 6))
    flow.append(Paragraph(PP.text(
        "Cada línea tiene su propia escala — la forma es la noticia y las "
        "cifras son el tamaño. La regla punteada es el día de traslado. Una "
        "semana que nadie informó corta la línea en vez de atravesarla, y su "
        "columna va en raya."), st["note"]))
    flow.append(Paragraph(PP.text(
        "Estas son sumas sin dividir. La fila de abajo dice cuántas áreas "
        "informaron cada semana, porque una semana con menos formularios se "
        "lee igual que una semana con menos trabajo y no es lo mismo."),
        st["note"]))
    if len(weeks) > PP.WEEK_COLUMN_LIMIT:
        flow.append(Paragraph(PP.text(
            f"El período tiene {es_display.integer(len(weeks))} semanas "
            f"completas, más de las que caben en columnas; queda la línea."),
            st["note"]))

    # M4 — the zones, weakest first
    flow.append(PageBreak())
    flow.append(PP.SectionHead(
        _children_title(model),
        "más atrasada primero · cada celda por área activa"))
    spec = PP.RankedSpec(width=W, cells=_child_cells(model))
    for row in child_rows(model, spec):
        flow.append(row)
    flow.append(Spacer(0, 6))
    flow.append(Paragraph(PP.text(
        "El porcentaje de la derecha es el promedio de los siete Indicadores "
        "Clave de esa unidad contra sus propias metas, por área activa — un "
        "área que no informó cuenta, porque el trabajo que nadie anotó no es "
        "trabajo que no se hizo ni trabajo que sí."), st["note"]))
    flow.append(Spacer(0, 4))
    flow.append(PP.legend(W, GRADED_NOTE))

    # M5 — every tracked nightly metric
    flow.append(PageBreak())
    flow.append(PP.SectionHead(
        "Todo el trabajo nocturno",
        f"más atrasado primero · {len(model.nightly_metrics)} medidas"))
    flow.append(PP.metric_table(
        nightly_lines(model, goals, comparable=_nightly_comparable(model))))
    flow.append(Spacer(0, 6))
    flow.append(Paragraph(PP.text(
        "El relleno es la suma del período contra la meta configurada por "
        "área activa por semana. El color está en el CAMBIO, no en la barra: "
        "estas metas están puestas cerca del doble de lo que la misión hace "
        "hoy, así que pintarlas de rojo cada semana no diría nada de la "
        "semana."), st["note"]))
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

    Provo's "THE SIX FURTHEST BEHIND", at CCSM's scale. A flagged goal is not
    eligible: the row would top the table for the goal's sake rather than the
    work's, which is the reading decision 22 exists to stop.
    """
    graded = [r for r in model.key_indicators
              if r.grade.pct is not None and not r.grade.flag]
    return sorted(graded, key=lambda r: r.grade.pct)[:limit]

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
    eyebrow = (model.mission_name if level == S.MISSION
               else f"{EYEBROW[level]} · {model.scope.name}")
    return PP.Furniture(eyebrow=eyebrow, period=model.period.window_label,
                        trail=" · ".join(model.scope.trail),
                        mission=model.mission_name)


def unit_pages(model, goals) -> list:
    """One unit's pages. The mission's are built; P4-P5 add the rest."""
    flow = [PP.SetFurniture(furniture_for(model))]
    if model.scope.level == S.MISSION:
        return flow + mission_pages(model, goals)
    return flow + _heading(model)


def data_note(models) -> list:
    """The last page: where every figure came from. P6 finishes it."""
    st = PP.styles()
    return [PP.SectionHead("Nota de datos", "de dónde sale cada cifra"),
            Paragraph("Pendiente.", st["body"])]


def _body(models, goals, pagination: Pagination) -> list:
    """Every unit in packet order, with the markers the second pass reads.

    Two markers per unit: one for the section the unit opens, if it is the
    first of its level, and one for the unit itself. The run sheet needs the
    second — it names a zone leader's own pages — and the contents needs the
    first.
    """
    section_of = {S.MISSION: MISSION, S.ZONE: ZONES, S.DISTRICT: DISTRICTS,
                  S.AREA: AREAS}
    flow, opened = [], set()
    for model in models:
        key = section_of[model.scope.level]
        flow.append(PageBreak())
        if key not in opened:
            opened.add(key)
            flow.append(SectionStart(key, pagination))
        flow.append(SectionStart(model.scope.key, pagination))
        flow.extend(unit_pages(model, goals))
    flow.append(PageBreak())
    flow.append(SectionStart(DATA_NOTE, pagination))
    flow.extend(data_note(models))
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
