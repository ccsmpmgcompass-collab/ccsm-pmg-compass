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
from datetime import timedelta

from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable,
                                Frame, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Spacer)

from app.config import es_display
from app.reports import focus as FC
from app.reports import forecast as F
from app.reports import packet_parts as PP
from app.reports import periods as P
from app.reports import scope as S
from app.reports.model import (CHRONIC_BELOW, EFFORT_SCORE, INDEX_WEIGHTS,
                               UNCOLOURED_KI, reporting_status)

#: How the packet is ordered and what each block of pages is for. The keys are
#: stable; the titles and audiences are what the print guide prints.
#: Namespaced, because `Scope.key` for the whole mission is also "mission" and
#: both live in the same `Pagination.starts`.
RESUMEN = "sec:resumen"
HOW_TO_READ = "sec:how_to_read"
PRINT_GUIDE = "sec:print_guide"
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

    # Page 3 ("Cómo leer") goes in the two full copies only — decision 43:
    # in every leader's stack it cost fifteen sheets a run (151 -> 166), a
    # district's four pages becoming five. A leader's own pages carry the
    # one-line version of every rule instead (R3.2), and never point at a page
    # the leader was not handed.
    mission_section = by_key.get(MISSION)
    mission_label = mission_section.page_label if mission_section else "—"
    mission_count = mission_section.page_count if mission_section else 0
    for scope, (first, last) in units:
        pages = str(first) if first == last else f"{first}–{last}"
        count = last - first + 1
        if scope.level == S.ZONE:
            copies = lead.zone_leaders.get(scope.key, 0)
            # A zone that follows the mission directly is one range, not two
            # joined by "+" that a printer would have to read twice.
            together = (mission_section is not None and mission_section.present
                        and mission_section.last_page + 1 == first)
            rows.append(HandOut(
                f"Líderes de zona · {scope.name}",
                (_joined(mission_section, replace(
                    mission_section, first_page=first, last_page=last))
                 if together else f"{mission_label} + {pages}"), copies,
                "La misión y su zona" if copies
                else "Sin líder de zona en el organigrama",
                mission_count + count))
        elif scope.level == S.DISTRICT:
            copies = lead.district_leaders.get(scope.key, 0)
            rows.append(HandOut(
                f"Líderes de distrito · {scope.name}", pages, copies,
                "Su distrito" if copies
                else "Sin líder de distrito en el organigrama",
                count))
    return rows


def _joined(*sections) -> str:
    """Consecutive sections' pages as one range — "4–13" for the mission and
    the zone that follows it — or "—" when none has been measured yet."""
    present = [s for s in sections if s is not None and s.present]
    if not present:
        return "—"
    first = min(s.first_page for s in present)
    last = max(s.last_page for s in present)
    return str(first) if first == last else f"{first}–{last}"


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
        Section(RESUMEN, "Resumen para el presidente",
                "Presidente y asistentes"),
        Section(HOW_TO_READ, "Cómo leer este paquete",
                "Quien lo lea por primera vez"),
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
        Section(PRINT_GUIDE, "Guía de impresión",
                "Quien imprime y reparte el paquete", "Referencia"),
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
    if section.key == AREAS:
        words = {2: "dos", 3: "tres", 4: "cuatro"}.get(AREAS_PER_PAGE,
                                                      str(AREAS_PER_PAGE))
        return f"{section.title}, {words} por página"
    if each <= 0.6:
        return f"{section.title}, dos por página"
    if each == int(each):
        n = int(each)
        return (f"{section.title}, una página {agree}" if n == 1
                else f"{section.title}, {es_display.integer(n)} páginas {agree}")
    return f"{section.title}, {es_display.number(each, 1)} páginas {agree}"


def front_matter(mission, sections, units, roster, *, total_pages: int,
                 pagination: "Pagination | None" = None) -> list:
    """The cover and "Cómo leer" — pages 1 and 2 (decisions 4, 40).

    The print guide used to be page 2 of the president's own copy (AUDIT
    L1); it is the last page now (`print_guide_pages`), where the person who
    prints the packet finds it and the president does not have to turn past
    it. The contents still lists it.
    """
    period = mission.period
    facts = [
        ("Preparado para", "Presidente de misión y asistentes"),
        ("Período", f"{period.label} · {period.window_label}"),
        ("Semanas completas", period.progress_label),
        ("Cumplimiento", mission.compliance_label),
    ]
    sections = describe(sections)
    return (
        PP.cover_page(
            kicker="Consejo de liderazgo misional",
            title="Paquete del Consejo",
            standfirst=f"{mission.mission_name} — dónde está la misión, dónde "
                       f"enfocar y qué viene, en este período.",
            facts=facts,
            contents=[(s.title, s.page_label) for s in sections],
            note="Generado por PMG Compass desde la hoja de datos de la misión el "
                 f"{es_display.long_date(mission.today)}. Cada cifra viene de lo "
                 f"que las compañerías informaron o de Tableau; la nota de datos "
                 f"al final dice qué falta y por qué.")
        + [PageBreak(),
           PP.SetFurniture(PP.Furniture(
               eyebrow=mission.mission_name, period=period.window_label,
               mission=mission.mission_name, key=False))]
        + ([SectionStart(RESUMEN, pagination)] if pagination else [])
        + resumen_page(mission)
        + [PageBreak(),
           PP.SetFurniture(PP.Furniture(
               eyebrow=mission.mission_name, period=period.window_label,
               mission=mission.mission_name, key=True))]
        + ([SectionStart(HOW_TO_READ, pagination)] if pagination else [])
        + how_to_read(mission, sections)
    )


def resumen_page(mission) -> list:
    """Page 2, the president's one page (4E.1, decision 57): five blocks of
    sentences from `summary.summary` — the screen's top card prints the same.
    Nothing on it is coloured, so its footer carries no key."""
    from app.reports import summary as SM
    st = PP.styles()
    flow = [PP.SectionHead("Resumen para el presidente",
                           f"{mission.period.label} · "
                           f"{mission.period.window_label}")]
    for heading, lines in SM.summary(mission):
        flow.append(Spacer(0, 6))
        flow.append(PP.SectionHead(heading, rule=False))
        for line in lines:
            flow.append(Paragraph(PP.text(line), st["body"]))
    flow.append(Spacer(0, 6))
    flow.append(Paragraph(PP.text(
        "Cada frase sale de las páginas que siguen, donde está su cifra con "
        "su método. Las proyecciones son rangos y no llevan color."),
        st["note"]))
    return flow


def print_guide_pages(mission, sections, units, roster, *, total_pages: int,
                      pagination: "Pagination | None" = None) -> list:
    """The run sheet, as the packet's last page (AUDIT L1).

    On the first pass every range is a dash and the total is zero; the guide
    still lays out at very nearly its true length, which is what lets the
    next pass be right. It is the one part of the packet built from the packet
    rather than from a `ReportModel`.
    """
    period = mission.period
    sections = describe(sections)
    rows = hand_outs(sections, units, roster)
    paper = sheets(rows)
    lead = leadership(roster)
    missing = lead.districts_without_a_leader
    closing = [
        f"Papel total: {paper} hojas a doble cara si imprime exactamente las "
        f"filas de arriba. Las copias salen del organigrama — una por "
        f"compañería de liderazgo."]
    if missing:
        names = ", ".join(sorted(k.split("/")[-1] for k in missing))
        closing.append(
            f"{len(lead.district_leaders) - len(missing)} de "
            f"{len(lead.district_leaders)} distritos tienen un líder marcado "
            f"en el organigrama. Sin líder: {names}. Esa fila pide 0 copias; "
            f"decida a mano a quién entregarla.")
    sheets_per_copy = math.ceil(total_pages / 2) if total_pages else 0
    return (
        [PP.SetFurniture(PP.Furniture(
            eyebrow="Guía de impresión", period=period.window_label,
            mission=mission.mission_name, key=False))]
        + ([SectionStart(PRINT_GUIDE, pagination)] if pagination else [])
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


# ── Page 3: how to read the packet (C9, decision 40) ─────────────────────────

def _band_sentence() -> str:
    """The three grades in words, from the thresholds `theme` grades with — so
    this page cannot drift from the colours it explains."""
    from app.config.theme import GOAL_BAR_TIERS
    good, warn = GOAL_BAR_TIERS[0][0], GOAL_BAR_TIERS[1][0]
    return (f"{good}% o más es al ritmo, {warn}-{good - 1}% atrasado y menos "
            f"de {warn}% muy atrasado — los tres colores del pie de cada "
            f"página")


def how_to_read(mission, sections) -> list:
    """The six rules a first-pass reader needs, before the first number.

    Finding C9: the packet's rules were on its last page, behind 103 pages of
    figures that follow them. Every sentence here is built from the mission's
    own model — who did not report, how many nightly rows sit under 60%, the
    two baptism figures, how far Tableau reaches — so the page says what is
    true of THIS packet rather than what is true of packets in general. The
    full data note stays at the back as the reference.
    """
    st = PP.styles()
    period = mission.period
    rules = []

    rules.append((
        "Contra qué se mide cada porcentaje, y cómo se ordenan las unidades",
        f"Cada Indicador Clave se colorea contra la meta del liderazgo, la de "
        f"traslado, sobre las mismas semanas y áreas que informaron: "
        f"{_band_sentence()}. La columna «Compromiso» es la meta que las "
        f"compañerías se pusieron; se imprime y nunca da color. Los bautismos "
        f"del formulario no llevan color: la meta de bautismos es la anual. "
        f"Las unidades se ordenan por su índice de productividad: lo que "
        f"produce cada compañería por semana contra la misión, que es 100, "
        f"con más peso en lo más cercano al bautismo (fechas 3, sacramental y "
        f"conversos recientes 2, lo demás 1). No depende de ninguna meta, y "
        f"un área que no informó cuenta como cero. «Cambio» compara con otro "
        f"período y su encabezado dice con cuál; una raya bajo «sin base este "
        f"período» quiere decir que no hay con qué comparar, no que nada "
        f"cambió."))

    silent = sorted(mission.areas_silent)
    who = f"Cumplimiento del período: {mission.compliance_label}. "
    if silent:
        who += (f"{es_display.integer(len(silent))} de "
                f"{es_display.integer(mission.scope.area_count)} áreas no "
                f"entregaron ninguna semana completa: {', '.join(silent)}. ")
    who += ("Las sumas van sin dividir, y una semana con menos formularios se "
            "lee igual que una semana con menos trabajo: por eso cada tabla "
            "semanal termina con cuántas áreas informaron. Léala antes que las "
            "cifras de encima.")
    rules.append(("Quién informó, y quién no", who))

    graded = [r for r in mission.nightly_metrics if r.grade.pct is not None]
    from app.config.theme import GOAL_BAR_TIERS
    warn = GOAL_BAR_TIERS[1][0]
    low = sum(1 for r in graded if r.grade.pct < warn)
    night = ""
    if graded:
        night = (f"{es_display.integer(low)} de "
                 f"{es_display.integer(len(graded))} medidas nocturnas de la "
                 f"misión están por debajo del {warn}% de su meta. ")
    night += ("Una meta nocturna es una cifra por área por semana, y el "
              "porcentaje se toma sobre las noches informadas: una noche sin "
              "informe va en «Quién informó», no como un cero en la barra. La "
              "barra va en un solo azul y el color va en el cambio: una medida "
              "nocturna se califica por su movimiento, no por su distancia a "
              "la meta.")
    rules.append(("Por qué el trabajo nocturno va sin color", night))

    rules.append(("Dos cifras de bautismos", _two_baptism_figures(mission)))

    rules.append(("Proyecciones, dónde enfocar y palancas", _forward_rule(
        mission)))

    note = next((s for s in sections if s.key == DATA_NOTE), None)
    where = (f"en la página {note.page_label}" if note is not None
             and note.present else "al final")
    rules.append((
        "Dónde está el resto",
        f"La nota de datos, {where}, dice de qué pestaña sale cada cifra, qué "
        f"metas no sirven para medir y qué nombres de Tableau no están en el "
        f"roster. Quien quiera discutir un número encuentra ahí de qué está "
        f"hecho."))

    flow = [PP.SectionHead("Cómo leer este paquete",
                           f"{period.label} · seis reglas"),
            Paragraph(PP.text(
                "Seis reglas, antes de la primera cifra. Cada una está escrita "
                "con las cifras de este paquete, no con las de un paquete "
                "cualquiera."), st["body"]),
            Spacer(0, 6)]
    for n, (title, body) in enumerate(rules, start=1):
        flow.append(Paragraph(PP.text(f"{n}. {title}"), st["cell_bold"]))
        flow.append(Paragraph(PP.text(body), st["body"]))
        flow.append(Spacer(0, 6))
    flow += [Spacer(0, 4),
             PP.SectionHead("Las columnas de una tabla de indicadores",
                            "de izquierda a derecha"),
             PP.table(COLUMN_GLOSSARY, (150.0, PP.CONTENT_WIDTH - 150.0),
                      headers=("Columna", "Qué es"))]
    return flow


def _forward_rule(mission) -> str:
    """Rule 5: what the forward pages are, and what they rest on."""
    fwd = mission.forward
    bits = ["Toda proyección va como rango, con su método al lado, y sin "
            "color: no es una calificación."]
    if fwd.year is not None and fwd.year.low is not None:
        bits.append(f"El año cierra entre {_range(fwd.year.low, fwd.year.high)} "
                    f"bautismos según cuatro cálculos; harían falta "
                    f"{_int(fwd.year.needed_per_month)} por mes para la meta.")
    if fwd.pipeline is not None:
        bits.append(f"Las {_int(fwd.pipeline.open_dates)} fechas bautismales "
                    f"abiertas valen entre {_range(fwd.pipeline.low, fwd.pipeline.high)} "
                    f"bautismos en seis semanas, por lo que fechas de su misma "
                    f"edad dieron antes.")
    bits.append("Debajo de la misión, los bautismos son registros de Tableau "
                "por área del organigrama: no hay cifra certificada por zona. "
                "«Dónde enfocar» reparte lo que le falta a la misión entre sus "
                "unidades, y las palancas siguen a quienes se encontraron "
                "hace tres a seis meses, cuando la iglesia, la fecha y el "
                "bautismo ya tuvieron tiempo de ocurrir.")
    return " ".join(bits)


#: The metric table's columns, named as its heads print them (finding B7: four
#: percentages on one row, and nothing at the point of use saying which is
#: which). Vocabulary, not figures — the only thing on page 3 that is not
#: generated, because it describes the table rather than this period.
COLUMN_GLOSSARY = (
    ("Real", "Lo que las compañerías informaron en el período, sumado. En "
             "el trabajo nocturno, lo que un área hace en una semana de "
             "noches informadas: su encabezado dice «área/sem»."),
    ("Meta", "En los Indicadores Clave, la meta de traslado del liderazgo "
             "para las semanas y áreas que informaron, así que real y meta "
             "cuentan lo mismo. En el trabajo nocturno, la meta de un área "
             "para una semana, en la misma escala que su real."),
    ("Compromiso", "La suma de las metas que las compañerías se pusieron en "
                   "el formulario. Se imprime; nunca da color."),
    ("La barra", "Real contra la meta, con el color de la calificación."),
    ("Contra la meta del liderazgo", "El porcentaje de la barra y su "
                                     "calificación. En el trabajo nocturno, "
                                     "contra la meta del sector, sin color."),
    ("Cambio", "Contra el período que nombra su encabezado, por área que "
               "informó. Con cifras chicas va en unidades («+4»), no en "
               "porcentaje, y el triángulo sólo aparece cuando el movimiento "
               "es más grande que lo que el azar mueve una cifra de ese "
               "tamaño. Una raya bajo «sin base este período»: no hay con "
               "qué comparar."),
    ("Áreas que informaron", "La última fila de cada tabla semanal: cuántas "
                             "áreas entregaron el formulario esa semana."),
)


def _two_baptism_figures(mission) -> str:
    """Rule 4: the certified figure and the form's, both for this period, and
    why only one of them opens a page (decisions 21, 37, 42)."""
    period = mission.period
    block = getattr(mission, "tableau", None)
    bap = block.baptisms if block is not None else None
    ki = mission.ki("ki_baptized_confirmed_real")
    parts = []
    if bap is not None:
        ytd = bap.year_to_date
        fig = bap.period
        certified = []
        if ytd is not None and ytd.present:
            certified.append(f"{es_display.integer(ytd.count)} en lo que va "
                             f"de {bap.year}")
        if fig is not None and fig.present and period.key != P.YEAR:
            certified.append(f"{es_display.integer(fig.count)} en "
                             f"{period.label}")
        if certified:
            parts.append("Tableau certifica " + " y ".join(certified) + ".")
        if fig is not None and not fig.present:
            parts.append(f"Para {period.label} todavía no hay cifra "
                         f"certificada, y no se imprime otra en su lugar.")
    if ki is not None and ki.actual is not None:
        parts.append(f"El formulario semanal de las compañerías informó "
                     f"{_count(ki.actual)} en {period.label}.")
    pilot = _pilot_zones(mission)
    parts.append(
        f"La página de bautismos usa la certificada, que cuenta todas las "
        f"zonas de la misión; la del formulario cuenta sólo {pilot} y va en "
        f"los Indicadores Clave con su propio nombre. Nunca se suman, y la "
        f"del formulario no abre ninguna página: ni «lo más fuerte» ni «lo "
        f"que hay que mover».")
    return " ".join(parts)


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


#: Decision 38: a change with no base is a dash, and the column head says why.
#: It supersedes printing the figure and disowning it in a note four lines
#: below, which is what the packet did until 2026-09-23 (finding A2).
NO_BASE_HEAD = ("Cambio", "sin base este período")


def _against_label(model) -> str:
    """The comparison window's short name for the change column's head —
    "2026-5", "Mes anterior", "2025" — with its qualifier left to the note
    under the table, where "(primeras 2 semanas)" has the room to be read."""
    comparison = model.comparison
    if comparison is None or comparison.period is None:
        return ""
    short = comparison.period.label.split(" (")[0]
    # "vs 2 semanas anteriores" is 70pt in a 63pt column and wraps the head to
    # three lines on every table that has a base — measured, four pages on the
    # "Semanas anteriores" packet. "previas" says the same and fits.
    short = short.replace(" semanas anteriores", " semanas previas")
    return short[:1].lower() + short[1:] if short[:1].isalpha() else short


def _metric_headers(*, based: bool, against: str = "", real="Real",
                    meta="Meta") -> tuple:
    """The metric table's six heads (findings A2, A4, B7).

    The verdict column says whose goal it is against (`PP.OWN_GOAL_HEAD`); the
    change column says what it is against — "CAMBIO / vs 2026-5" — or, with no
    base, why it is empty (`NO_BASE_HEAD`). ``real`` and ``meta`` take a
    ``(label, unit)`` pair where the two are not on the same footing (R1.4).
    """
    if not based:
        change = NO_BASE_HEAD
    elif against:
        change = ("Cambio", f"vs {against}")
    else:
        change = "Cambio"
    return ("Métrica", real, meta, "", PP.OWN_GOAL_HEAD, change)


def _change(row, *, comparable: bool, confident: bool = True) -> tuple:
    """`(direction, "+12%")`, or `(0, "—")` when there is no base for one.

    Two ways to have no base, and since decision 38 they print the same: there
    is no comparison window at all (``comparable`` is False), or there is one
    and it rests on one or two areas (``confident`` is False — `Coverage.thin`).
    Either way the cell is a dash and the column head reads "sin base este
    período" (`NO_BASE_HEAD`), so the reason sits where the eye is rather than
    in a note under the table.

    The live case is not hypothetical. The default comparison for this transfer
    is the first two weeks of 2026-5, which hold a single area, and every one
    of the seven Key Indicators comes out between -36% and -65%. The packet
    used to print those figures in grey and explain below that they meant
    nothing; a reader who stops at the table takes -63% at its word.
    """
    grade = row.grade
    if not (comparable and confident):
        return (0, es_display.NA)
    # Small counts print as a signed count, never a percentage, and a move
    # inside Poisson noise prints with no direction (AUDIT-2026-10-06 H5):
    # El Mirador read "+260%" on a count of five.
    if grade.change_count is not None:
        n = round(grade.change_count)
        text = f"{'+' if n > 0 else ''}{es_display.integer(n)}"
        direction = (1 if n > 0 else -1) if n and grade.change_clear else 0
        return (direction, text)
    pct = grade.change_pct
    if pct is None:
        return (0, es_display.NA)
    # The direction of the figure as PRINTED: -0,3% prints "0%", and a red
    # triangle beside "-0%" reported a fall nobody could see in the number.
    if round(pct) == 0:
        return (0, es_display.signed_percent(0))
    direction = (1 if pct > 0 else -1) if grade.change_clear else 0
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
    """The seven Key Indicators as printable rows (decisions 10, 46, 59).

    The bar and its colour are what was done, counting every area, against
    LEADERSHIP's full goal for the period — a week an area did not report
    counts as zero, so REAL and META count the same area-weeks. The
    companionships' own goal is the uncoloured COMPROMISO beside it. The
    form's baptisms show their percentage and never take a colour: the 527
    annual goal is the baptism target. The screen's card makes the identical
    statement.
    """
    lines = []
    for row in model.key_indicators:
        note = ""
        real = row.actual
        if row.lead_goal is None:
            note = "sin meta del liderazgo para estas semanas"
        else:
            if row.lead_area_weeks < row.lead_area_weeks_possible:
                # Decision 66: graded on the area-weeks that carry a goal;
                # REAL follows them so the two columns count the same thing.
                real = row.lead_actual
                note = (f"sobre {es_display.integer(row.lead_area_weeks)} de "
                        f"{es_display.integer(row.lead_area_weeks_possible)} "
                        f"semanas-área con meta")
            if row.key in UNCOLOURED_KI:
                note = "sin color: los bautismos se miden contra la meta anual"
        lines.append(PP.MetricLine(
            label=row.label, value=_count(real),
            goal=(_goal(row.lead_goal) if row.lead_goal else es_display.NA),
            own=_count(row.meta) if row.meta else es_display.NA,
            pct=row.grade.pct, status=row.grade.status,
            verdict=_verdict(row),
            change=_change(row, comparable=comparable, confident=confident),
            note=note))
    return lines


LEAD_GOAL_HEAD = PP.LEAD_GOAL_HEAD


def nightly_lines(model, goals, *, comparable: bool) -> list:
    """Every tracked nightly metric, furthest behind first (decision 17).

    ``goals`` must be the same `nightly_goals` the model was built from: it
    feeds the row's note ("meta 150/área/sem") while the attainment beside it
    comes from the model's own grade, and handing in a different dict would put
    two goals on one line.

    ``status`` is deliberately left off the bar: decision 31 puts a nightly
    row's colour on its MOVEMENT. Under the launch goals (roughly twice what
    the mission did) seventeen of twenty bars painted red every week, the wall
    of colour decision 10 exists to prevent, so the bar is the single
    magnitude blue and the colour lives in the change. Decision G-D6 of
    PLAN-2026-10-02-goals.md revisits this after a transfer of re-based goals.
    """
    lines = []
    for row in model.nightly_weakest_first:
        # The row's own goal per sector-week (G10) — the sectors' goals for
        # the nights they filed, averaged — so the note and the percentage
        # beside it rest on one figure.
        goal = (row.goal_per_area_week if row.goal_per_area_week is not None
                else goals.get(row.key))
        # REAL and META on ONE basis, per area per week — the figure the
        # percentage is taken on (AUDIT-2026-10-06 H4). It used to print the
        # period total beside a per-area-week goal, two numbers no reader can
        # compare without dividing; the total is still here, in the note.
        if row.key == EFFORT_SCORE:
            # An average on the agents' 1-3 scale, not a count: it has no
            # period total to print.
            note = "promedio, escala de 1 a 3"
        else:
            note = (f"total del período: {_count(row.actual)}"
                    if row.actual is not None else "sin noches informadas")
        if not goal:
            note = f"{note} · sin meta configurada"
        if row.grade.flag:
            note = f"{note} · {row.grade.flag_label}"
        lines.append(PP.MetricLine(
            label=row.label, value=_per_week(row.per_reporting_area_week),
            goal=_per_week(goal) if goal else es_display.NA,
            pct=row.grade.pct, status=None, magnitude=True,
            verdict=_verdict(row, graded=False),
            change=_change(row, comparable=comparable), note=note))
    return lines


def _per_week(value) -> str:
    """A per-area-week figure: whole from 10 up, one decimal below — 44,8
    lessons is 45, but 0,4 baptismal calendars is not 0."""
    if value is None:
        return es_display.NA
    return (es_display.integer(round(value)) if abs(value) >= 10
            else es_display.number(value, 1))


#: The cells of a ranked table: every member of the productivity index, in
#: weight order, each on the index's own scale (mission = 100). Until
#: 2026-10-06 the table showed three Key Indicators beside a mean of all
#: seven, so four of the figures driving the ranking were invisible
#: (AUDIT-2026-10-06 M6). The abbreviations are written out rather than
#: trimmed off the catalogue's labels: "Amigos en la Reunión Sacramental" cut
#: to nine characters is "Amigos en", which names nothing.
CHILD_COLUMNS = (
    ("ki_baptismal_date_real", "Fecha"),
    ("ki_friends_sacrament_real", "Sacr."),
    ("ki_rc_at_church_real", "CR"),
    ("ki_member_lessons_real", "Lecc."),
    ("ki_new_people_real", "Nuevas"),
    ("ki_friends_first_week_real", "1ª sem"),
)

#: An index cell is three digits; 40pt holds "250" with room for its head.
INDEX_CELL_WIDTH = 40.0


def _child_keys(model) -> tuple:
    """The index's members as `(key, short head)`, or the unit's own keys
    when a mission's catalogue does not carry them."""
    present = {r.key for r in model.key_indicators}
    chosen = [(k, short) for k, short in CHILD_COLUMNS if k in present]
    if chosen:
        return tuple(chosen)
    return tuple((r.key, PP.fit(r.label, PP.CELL_HEAD, 34))
                 for r in model.key_indicators
                 if r.key not in UNCOLOURED_KI)[:6]


def _index_spec(model) -> PP.RankedSpec:
    """The geometry every index table draws against: no grade dots, because
    the index has no goal to grade against (decision 45)."""
    return PP.RankedSpec(width=PP.CONTENT_WIDTH, cells=_child_cells(model),
                         cell_width=INDEX_CELL_WIDTH, dots=False)


def _idx(value) -> str:
    """An index or a member's ratio, as a whole number — "94", "—"."""
    return es_display.NA if value is None else es_display.integer(value)


#: Where the index bar's track ends. 200 puts the mission's 100 in the middle
#: of every bar, so a row is read left or right of one line.
INDEX_BAR_MAX = 200.0


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

def _heading(model) -> list:
    st = PP.styles()
    return [Paragraph(PP.text(model.scope.name), st["title"]),
            Paragraph(PP.text(model.subtitle), st["subtitle"])]


def _comparison_note(model) -> str:
    """What the change column is measured against, or why it has no base.

    Says WHY there is no base; the column head already says THAT there is
    none (decision 38), so this no longer has to disown a figure printed
    above it.
    """
    comparison = model.comparison
    if comparison is None or comparison.period is None:
        # `Comparison` is falsy exactly when it has no window, so test for
        # None: `if comparison` would drop the reason it carries.
        reason = (getattr(comparison, "reason", "")
                  if comparison is not None else "")
        return f"Sin comparación: {reason}" if reason else "Sin comparación."
    cov = model.comparison_coverage
    # A comma, not brackets: the label often carries its own ("2026-5
    # (primeras 2 semanas)") and two sets in a row read as a typo.
    against = (f"{comparison.period.label}, "
               f"{comparison.period.elapsed_label}")
    if cov is None or not cov.usable:
        return f"Sin base para el cambio: {against} no tiene informes."
    if cov.thin:
        return (f"Sin base para el cambio: {against} · {cov.label} — apenas "
                f"un puñado de áreas.")
    return f"Cambio contra {against} · {cov.label}."


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


#: Decision 37. The weekly form's baptism Key Indicator is the figure the
#: packet trusts least — a handful of events a transfer, so one baptism moves
#: it by a third — so it is
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
        sub = rung.role + (" · pocas cifras" if rung.index.thin
                           and rung.index.value is not None else "")
        out.append(PP.ranked_row(
            spec, rank=None, name=rung.scope.name, sub=sub,
            cells=[_idx(rung.index.ratio(key)) for key in keys],
            value=_idx(rung.index.value), bar=rung.index.value,
            bar_max=INDEX_BAR_MAX, mark=100.0))
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
    labels = {r.key: r.label for r in parent.metrics}
    rows = [(labels.get(k, k), d)
            for (k, _), d in zip(parent.index.members, parent.deltas)]
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


def ladder_block(model, *, gaps: bool = True, strip: bool = True) -> list:
    """The whole comparison section: the three scales, then the seven gaps.

    One block so every level that carries it carries the same thing — a zone
    against the mission, a district against its zone, an area against its
    district — and a reader who has read one has read them all.
    """
    st = PP.styles()
    spec = _index_spec(model)
    rows = ladder_rows(model, spec)
    if not rows:
        return []
    above = next((r.scope.name for r in model.ladder[1:] if not r.is_self), "")
    flow = [PP.SectionHead(_ladder_title(model),
                           "productividad por compañería · misión = 100")]
    flow.extend(rows)
    gaps = gap_rows(model) if gaps else []
    if gaps:
        flow.append(Spacer(0, 6))
        flow.extend(gaps)
    strip = sibling_strip(model) if strip else []
    if strip:
        flow.append(Spacer(0, 6))
        flow.extend(strip)
    flow.append(Spacer(0, 4))
    flow.append(Paragraph(PP.text(
        f"Lo que produce cada compañería por semana, contra la misión (100). "
        f"Abajo, cuántos puntos separan a esta unidad de {above} en cada "
        f"indicador del índice."
        if gaps else
        "Lo que produce cada compañería por semana, contra la misión (100), "
        "en cada escala."), st["note"]))
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
    peers = [(c.name, c.index.value) for c in model.siblings]
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
    top = max([v for _, v in peers if v is not None] + [INDEX_BAR_MAX])
    top = 50.0 * math.ceil(top / 50.0)
    ticks = [(t, "100 = misión" if t == 100 else es_display.integer(t))
             for t in range(0, int(top) + 1, 50)]
    return [PP.strip_plot(PP.CONTENT_WIDTH, peers, highlight=model.scope.name,
                          axis_max=top, value_fmt=_idx, caption=caption,
                          ticks=ticks)]


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


def children_page(model) -> list:
    """The units one level down, weakest first (decisions 14, 15, 16)."""
    st = PP.styles()
    spec = _index_spec(model)
    flow = [PP.SectionHead(
        _children_title(model),
        "menos productiva primero · misión = 100")]
    flow.extend(child_rows(model, spec))
    flow.append(Spacer(0, 6))
    flow.append(Paragraph(PP.text(
        INDEX_NOTE if model.scope.level == S.MISSION else INDEX_NOTE_SHORT),
        st["note"]))
    return flow


#: Under every index table: what the number is, in a sentence a council can
#: repeat (decision 45).
INDEX_NOTE = ("A la derecha, el índice de productividad: lo que produce cada "
              "compañería por semana contra la misión, que es 100, sin "
              "ninguna meta. Cada celda es un indicador del índice en la "
              "misma escala. Un área que no informó cuenta como cero; quién "
              "no informó está en su propia lista.")


#: Below the mission: the one line a leader holding only their own pages
#: needs, the full sentence being on the mission's page.
INDEX_NOTE_SHORT = ("A la derecha, la productividad: lo que produce cada "
                    "compañería por semana, misión = 100, sin ninguna meta.")


def _index_words(value: float) -> str:
    """"un 27% más" / "un 6% menos" / "lo mismo" — the index said out loud."""
    gap = round(value - 100)
    if gap == 0:
        return "lo mismo"
    word = "más" if gap > 0 else "menos"
    return f"un {es_display.integer(abs(gap))}% {word}"


def _names(names) -> str:
    """"A", "A y B", "A, B y C" — people named in a sentence."""
    names = [n for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " y " + names[-1]


def reporting_headline(model) -> list:
    """Decision 60's KPI row, above the tablero on the mission and zone pages:
    the rate against its 95% target (D2's colours), its trend (decision 67)
    and who owns it."""
    rep = model.reporting
    if rep is None or model.scope.level not in (S.MISSION, S.ZONE):
        return []
    values = [v * 100 if v is not None else None for _, v in rep.trend]
    labels = [label for label, v in rep.trend if v is not None]
    n = len(rep.trend)
    trend_note = (f"últimas {n} {rep.trend_unit}" if not labels
                  else f"{n} {rep.trend_unit}: {labels[0]} a {labels[-1]}")
    if model.scope.level == S.MISSION:
        owners = "los líderes de cada zona, en «Quién informó»"
    else:
        owners = _names(rep.owners) or "sin líderes de zona en el organigrama"
    counts = (f"{es_display.integer(rep.reported)} de "
              f"{es_display.integer(rep.possible)} informes")
    return [PP.reporting_line(
        PP.CONTENT_WIDTH,
        rate_pct=rep.rate * 100 if rep.rate is not None else None,
        status=rep.status, target_pct=rep.target * 100, counts=counts,
        trend=values, trend_note=trend_note, owners=owners),
        Spacer(0, 6)]


def reporting_block(model) -> list:
    """Who reported — decision 45's separate list, worst first.

    Silence is not folded into a performance figure any more; it is said here,
    with the areas named, at mission and zone level (district pages carry the
    silent areas in their own areas table). Since decision 60 each zone carries
    its owners, the zone leaders, and every dot is on D2's bands (95/85).
    """
    st = PP.styles()
    units = model.reporting_ranked
    if not units or model.scope.level not in (S.MISSION, S.ZONE):
        return []
    spec = PP.RankedSpec(width=PP.CONTENT_WIDTH, cells=("Informes",),
                         cell_width=64.0)
    flow = [PP.SectionHead(f"Quién informó · {_children_title(model).lower()}",
                           "menos informes primero")]
    flow.append(PP.ranked_row(spec, name=_children_title(model).lower(),
                              header=True))
    for i, child in enumerate(units, start=1):
        cov = child.coverage
        rate = (cov.reporting_rate or 0) * 100 if cov is not None else 0
        silent = child.areas_silent
        sub = ("sin informe en todo el período: " + ", ".join(silent)
               if silent else "todas sus áreas informaron")
        if child.owners:
            sub = f"responsables: {_names(child.owners)} · {sub}"
        out_of = (f"{es_display.integer(cov.area_weeks_reported)} de "
                  f"{es_display.integer(cov.area_weeks_expected)}"
                  if cov is not None else es_display.NA)
        flow.append(PP.ranked_row(
            spec, rank=i, name=child.name, sub=sub,
            status=reporting_status(rate / 100), cells=[out_of],
            value=_pct(rate), bar=rate, bar_max=100))
    flow.append(Spacer(0, 4))
    flow.append(Paragraph(PP.text(
        "Informes semanales entregados contra los posibles en las semanas "
        "completas del período. Un área sin informe cuenta como cero en la "
        "productividad de arriba, a propósito: esta lista dice cuánto de ese "
        "cero es silencio."), st["note"]))
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
    if child.index.value is None:
        bits.append("sin informes en el período")
    elif child.index.thin:
        bits.append("pocas cifras")
    if child.index.value is not None and child.coverage is not None:
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
        out.append(PP.ranked_row(
            spec, rank=child.rank if child.index.value is not None else None,
            name=child.name, sub=_child_sub(child, model),
            cells=[_idx(child.index.ratio(key)) for key in keys],
            value=_idx(child.index.value), bar=child.index.value,
            bar_max=INDEX_BAR_MAX, mark=100.0))
    return out


def areas_page(model) -> list:
    """Every area inside the unit, weakest first (decision 15 — no top-N).

    Filled at mission and zone level only. At district level the areas already
    ARE the children, and the same list under two headings is noise.
    """
    st = PP.styles()
    if not model.areas_ranked:
        return []
    spec = _index_spec(model)
    flow = [PP.SectionHead(
        f"Las {es_display.integer(len(model.areas_ranked))} áreas",
        "menos productiva primero · misión = 100")]
    flow.extend(ranked_unit_rows(model.areas_ranked, model, spec,
                                 header="área"))
    flow.append(Spacer(0, 6))
    flow.append(Paragraph(PP.text(
        "Cada área tiene además su propia página más adelante en el "
        "paquete, con los nombres de la compañería."), st["note"]))
    return flow


#: The nightly table's two figure heads (finding A4, then AUDIT-2026-10-06
#: H4). Until 2026-10-06 REAL was the period's total and META one area's goal
#: for one week — "3.248 contra 44,8" — two figures a reader could not compare
#: without dividing. Both are per area per week now, the basis the percentage
#: beside them is taken on, and the period's total moved to the row's note.
#: "área/sem" fits the 37pt the column has where "área/semana" is 0,4pt too
#: wide.
NIGHTLY_REAL_HEAD = ("Real", "área/sem")
NIGHTLY_META_HEAD = ("Meta", "área/sem")


def nightly_page(model, goals) -> list:
    """Every nightly metric, with its two notes ABOVE the table.

    Round 4 found Catrihuala 2's reporting line printed alone on page 73 — the
    22-row table had split and taken the page down to its last row, and the
    two notes under it went over. Phase V met the same widow and learnt the
    fix: tying a note to the table's tail costs whole pages, and a note above
    the table can never be widowed because the head is already keeping the
    first rows company. It is also the better order: how many areas reported
    is read before the sums it qualifies (finding B8).
    """
    st = PP.styles()
    flow = [
        PP.SectionHead(
            "Todo el trabajo nocturno",
            f"más lejos de su meta primero · "
            f"{es_display.integer(len(model.nightly_metrics))} medidas"),
    ]
    nightly = model.nightly_coverage
    if nightly is not None:
        flow.append(Paragraph(PP.text(
            f"Informes nocturnos del período: {nightly.label} "
            f"({_pct((nightly.rate or 0) * 100)}), "
            f"{es_display.integer(nightly.areas_reporting)} de "
            f"{es_display.integer(nightly.areas_in_scope)} áreas informaron "
            f"al menos una noche."), st["note_lead"]))
    # No "sin cambio comparable" note: the column head says "sin base este
    # período" now (decision 38), where the eye already is.
    flow += [
        Paragraph(PP.text(
            "Real y meta van por área por semana, sobre las noches "
            "informadas; el total del período va bajo cada nombre. La barra "
            "va en un solo azul y el color va en el cambio. "
            + model.nightly_source_note),
            st["note"]),
        Spacer(0, 4),
        PP.metric_table(nightly_lines(
            model, goals, comparable=_nightly_comparable(model)),
            headers=_metric_headers(based=_nightly_comparable(model),
                                    against=_against_label(model),
                                    real=NIGHTLY_REAL_HEAD,
                                    meta=NIGHTLY_META_HEAD)),
    ]
    return flow


# ── The Tableau pages (M6, M7, Z4) ───────────────────────────────

# ── M6 · the year against its goal ───────────────────────────────

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
        return f"No hay cifra certificada de bautismos para {period.label}."
    return fig.sentence(period.label)


def baptism_page(model) -> list:
    """"Bautismos: el año y lo que viene" (AUDIT §5 item 3): the period's
    CERTIFIED figure first (decisions 41, 42), then the year against the 527
    with its landing range and the two years before it, then the open
    baptismal dates. Certified figures only for the mission (decision 21);
    the form's own figure is named in the closing note and never summed.
    """
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    if model.scope.level != S.MISSION:
        return []
    block = model.tableau
    bap = block.baptisms if block is not None else None
    flow = []
    if bap is not None:
        flow += [PP.SectionHead(f"Bautismos · {model.period.label}",
                                "cifra certificada · fuente: Tableau"),
                 PP.stat_tiles(W, _period_tiles(bap, model.period)),
                 Spacer(0, 4),
                 Paragraph(PP.text(_period_sentence(bap, model.period)),
                           st["note_lead"]),
                 Spacer(0, 8)]
    year = year_block(model)
    if year:
        flow += year + [Spacer(0, 8)]
    elif bap is not None:
        flow.append(Paragraph(PP.text(
            f"Bautismos {model.today.year}: sin meses certificados todavía, "
            f"así que el año no se dibuja ni se proyecta. No es un año sin "
            f"bautismos; es un año sin captura."), st["note_lead"]))
    pipe = pipeline_block(model)
    if pipe:
        flow += pipe
    if bap is not None:
        flow += [Spacer(0, 8), Paragraph(PP.text(
            f"Sobre la cifra de bautismos. Arriba está la cifra CERTIFICADA "
            f"de Tableau, que es la que cuenta. "
            f"{_form_baptisms_sentence(model)}"), st["note_lead"])]
    return flow


def _pilot_zones(model) -> str:
    """The zones that file Compass forms, in words — "las 4 zonas del piloto".

    The mission's children ARE the pilot: the roster carries only the zones
    AGENT_CONFIG.PILOT_ZONES names, while Tableau counts every zone.
    """
    zones = len(model.children) if model.scope.level == S.MISSION else 0
    if zones == 1:
        return "la zona del piloto"
    if zones:
        return f"las {es_display.integer(zones)} zonas del piloto"
    return "las zonas del piloto"


def _form_baptisms_sentence(model) -> str:
    """Why the form's baptism figure is not the certified one: SCOPE.

    The certified figure counts every zone of the mission; the weekly form is
    filled only in the pilot zones. Two different populations — so the two
    are never compared and never summed (decisions 21, 34), and neither is
    evidence about whether companionships fill the field (the sentence that
    said so was retracted on 2026-10-02; AUDIT-2026-10-06 C3).
    """
    ki = model.ki("ki_baptized_confirmed_real")
    pilot = _pilot_zones(model)
    said = (f"El formulario semanal de las compañerías informó "
            f"{_count(ki.actual)} en {model.period.label.lower()}. "
            if ki is not None and ki.actual is not None else "")
    return (f"{said}La certificada cuenta todas las zonas de la misión y el "
            f"formulario sólo {pilot}, así que las dos cifras no se comparan, "
            f"y nunca se suman. La del formulario aparece en los Indicadores "
            f"Clave bajo su propio nombre.")



# ── What is coming (decision 48, PLAN-2026-10-06 Phase 2) ─────────────────────
#
# Every figure here is a projection, printed as a range with its method in one
# line and never coloured: a forecast is not a grade.

def _goal(value) -> str:
    """A goal on a printed row: whole from 10 up, one decimal below — a
    goal of 0,4 is not "0" beside a row reading 400%."""
    return (es_display.integer(round(value)) if abs(value) >= 10
            else es_display.number(value, 1))


def _int(value) -> str:
    return es_display.NA if value is None else es_display.integer(round(value))


def _range(low, high) -> str:
    """"1.124-1.254", or one figure when the two round to the same."""
    if low is None or high is None:
        return es_display.NA
    a, b = round(low), round(high)
    return _int(a) if a == b else f"{_int(a)}-{_int(b)}"


def year_block(model) -> list:
    """The year's baptisms against the annual goal, and where they land
    (AUDIT-2026-10-06 C4(b), decision 46). Certified at mission level;
    Tableau's records against the zone's share of 527 at zone level."""
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    fwd = model.forward
    yl = fwd.year
    if yl is None:
        return []
    mission = model.scope.level == S.MISSION
    flow = [PP.SectionHead(f"Bautismos {yl.year}: cómo cierra el año",
                           f"{yl.source} · meses cerrados")]
    tiles = [PP.Tile(label=f"Meses cerrados de {yl.year}", value=_int(yl.total),
                     note=f"{es_display.integer(yl.months)} meses")]
    if yl.low is not None:
        tiles.append(PP.Tile(label="Cierre probable",
                             value=_range(yl.low, yl.high),
                             note=(f"de una meta de {_int(yl.goal)}"
                                   if yl.goal else "sin meta")))
    if yl.needed_per_month is not None:
        best = (f"el mejor mes fue {_int(yl.best[0])} ({yl.best[1]})"
                if yl.best else "")
        tiles.append(PP.Tile(label="Hace falta por mes",
                             value=_int(yl.needed_per_month), note=best))
    prior = yl.same_months(yl.year - 1)
    if prior:
        gap = (yl.total - prior) / prior * 100
        tiles.append(PP.Tile(label=f"Contra {yl.year - 1}",
                             value=es_display.signed_percent(gap),
                             note=(f"{_int(prior)} en los mismos "
                                   f"{es_display.integer(yl.months)} meses")))
    flow += [PP.stat_tiles(W, tiles), Spacer(0, 6)]

    years = sorted(yl.monthly)
    rows = []
    run = 0
    for i, name in enumerate(F.MONTH_ABBR):
        this = yl.monthly.get(yl.year, [None] * 12)[i]
        if this is not None:
            run += this
        row = [name] + [_int(yl.monthly[y][i]) if yl.monthly[y][i] is not None
                        else "" for y in years]
        row.append(_int(run) if this is not None else "")
        row.append(_int(yl.goal * (i + 1) / 12) if yl.goal else "")
        rows.append(row)
    heads = (["mes"] + [str(y) for y in years]
             + [("acumulado", str(yl.year)), ("ritmo de", "la meta")])
    widths = [70.0] + [62.0] * len(years) + [80.0, 80.0]
    flow.append(PP.table(rows, widths, headers=heads,
                         align=["l"] + ["r"] * (len(years) + 2)))
    flow.append(Spacer(0, 4))
    anchors = " · ".join(f"{words} {_int(v)}" for words, v in yl.anchors)
    lead = ""
    b = fwd.baptisms
    if not mission and b is not None and b.share is not None:
        lead = (f"Registros de Tableau por persona, por área del organigrama: "
                f"quedan algo por debajo de la cifra certificada. La meta de "
                f"la zona es su parte de los {_int(b.annual_goal)} de la "
                f"misión, la misma que tuvo de sus bautismos en los últimos "
                f"doce meses ({es_display.percent(b.share * 100, 1)}); se "
                f"imprime y no da color. ")
    open_month = ""
    if mission and yl.open_count:
        open_month = (f"{_int(yl.open_count)} más en el mes en curso, "
                      f"todavía sin cerrar: cuentan en lo que va del año, "
                      f"no en el ritmo ni en la proyección. ")
    flow.append(Paragraph(PP.text(
        f"{lead}{open_month}Cierre probable: el mínimo y el máximo de cuatro "
        f"cálculos — {anchors}. Sin color: es una proyección."
        f"{_year_check_sentence(model)}"), st["note"]))
    return flow


#: The pipeline's columns by age and, at mission level, by zone.
PIPE_COLUMNS = (130.0, 70.0, 110.0, 80.0)
ZONE_PIPE_COLUMNS = (170.0, 110.0, 90.0, 150.0)


def pipeline_block(model) -> list:
    """The open baptismal dates and the baptisms they are likely to become in
    six weeks (AUDIT-2026-10-06 C4(c), P4)."""
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    pl = model.forward.pipeline
    if pl is None:
        return []
    flow = [PP.SectionHead("Lo que viene: las fechas bautismales abiertas",
                           "registros de Tableau · próximas 6 semanas")]
    tiles = [PP.Tile(label="Fechas abiertas", value=_int(pl.open_dates),
                     note="fijadas en el último año, sin bautismo"),
             PP.Tile(label="Bautismos esperados", value=_range(pl.low, pl.high),
                     note=f"en 6 semanas · centro {_int(pl.expected)}")]
    fresh = sum(c for label, c, _ in pl.by_bucket[:3])
    tiles.append(PP.Tile(label="Fijadas hace 60 días",
                         value=_int(fresh),
                         note="las que más probablemente se bauticen"))
    flow += [PP.stat_tiles(W, tiles), Spacer(0, 6)]
    rows = [[label, _int(c), f"{es_display.percent(p * 100, 0)}",
             es_display.number(c * p, 1)] for label, c, p in pl.by_bucket]
    flow.append(PP.table(
        rows, PIPE_COLUMNS,
        headers=(("Edad de la fecha", "días desde que se fijó"), "Abiertas",
                 ("Se bautizan", "dentro de 6 semanas"), "Esperados"),
        align=("l", "r", "r", "r")))
    zones = model.forward.zones
    if zones:
        flow.append(Spacer(0, 8))
        zrows = [[name, _int(z.open_dates), _range(z.low, z.high),
                  "piloto de Compass" if pilot else "sin formularios de Compass"]
                 for name, pilot, z in sorted(zones, key=lambda t: -t[2].expected)]
        flow.append(PP.table(
            zrows, ZONE_PIPE_COLUMNS,
            headers=("Zona", "Fechas abiertas", ("Esperados", "6 semanas"), ""),
            align=("l", "r", "r", "l")))
    flow.append(Spacer(0, 4))
    miss = (f" En los últimos {es_display.integer(pl.backtests)} cierres de "
            f"mes, el mismo cálculo falló por un "
            f"{es_display.percent((pl.miss or 0) * 100, 0)} típico."
            if pl.miss is not None else "")
    flow.append(Paragraph(PP.text(
        "Método: cada fecha abierta cuenta con la probabilidad con que las "
        "fechas de su misma edad terminaron en bautismo dentro de seis "
        "semanas, medida en los últimos 15 cierres de mes de toda la misión."
        f"{miss} El rango es el 80% de lo esperable. Sólo cuenta a quienes "
        "hoy tienen fecha; registros de Tableau por persona, algo por debajo "
        "de la cifra certificada. Sin color: es una proyección."),
        st["note"]))
    return flow


# ── The president's front section (PLAN-2026-10-06 Phase 3) ──────────────────

def _spark_of(model, key) -> tuple:
    """`(values, boundary fractions)` of a Key Indicator's twelve weeks."""
    series = model.trend_series.get(key)
    if series is None or not series.points:
        return (), ()
    weeks = [p.week for p in series.points]
    span = max(1, (weeks[-1] - weeks[0]).days)
    bounds = tuple(max(0.0, min(1.0, (day - weeks[0]).days / span))
                   for day, _ in series.boundaries)
    return tuple(p.actual for p in series.points), bounds


def tablero_lines(model, *, comparable: bool, confident: bool) -> list:
    """The seven, one line each, for the tablero (AUDIT §5 item 1)."""
    finish = {k.key: k for k in model.forward.finish}
    lines = []
    for row in model.key_indicators:
        values, bounds = _spark_of(model, row.key)
        k = finish.get(row.key)
        need = ""
        if k is not None and k.needed_per_week is not None:
            need = _int(k.needed_per_week) + (
                f" · {es_display.number(k.factor, 1)}×" if k.factor else "")
        lines.append(PP.TableroLine(
            label=row.label, real=_count(row.actual),
            own=_count(row.meta) if row.meta else es_display.NA,
            per_comp=(es_display.number(row.per_active_area_week, 1)
                      if row.per_active_area_week is not None
                      else es_display.NA),
            pct=row.grade.pct, status=row.grade.status,
            verdict=_pct(row.grade.pct),
            change=_change(row, comparable=comparable, confident=confident),
            spark=values, boundaries=bounds,
            finish=(_range(k.low, k.high) if k is not None and k.weeks_left > 0
                    else ""),
            need=need))
    return lines


def tablero_block(model) -> list:
    """The unit's opening: where it stands in two sentences, and the seven
    Key Indicators on one table — real, per companionship, against
    leadership's goal, how they moved, their twelve weeks and, at mission and
    zone level, where the transfer finishes and what it would need."""
    st = PP.styles()
    weekly_ok = _weekly_comparable(model)
    weekly_sure = _weekly_confident(model)
    forecast = bool(model.forward.finish) and model.forward.finish[0].weeks_left > 0
    against = _against_label(model)
    based = weekly_ok and weekly_sure
    change = (("Cambio", f"vs {against}") if based and against
              else "Cambio" if based else NO_BASE_HEAD)
    heads = ["Indicador", "Real", ("Por", "comp./sem"),
             ("Propia", "compromiso"), "", ("Meta", "liderazgo"), change,
             ("12", "semanas")]
    if forecast:
        heads += [("Termina", "en"), ("Falta", "por semana")]
    flow = opening(model) + reporting_headline(model)
    flow += [
        PP.SectionHead("El tablero", f"los siete · {model.compliance_label}"),
        PP.tablero_table(tablero_lines(model, comparable=weekly_ok,
                                       confident=weekly_sure),
                         headers=tuple(heads), forecast=forecast),
        Spacer(0, 4),
    ]
    note = ("Real: lo informado en el período. Por comp.: por compañería y "
            "semana, contando a quien no informó. Propia: el compromiso, la "
            "meta que las compañerías se pusieron — se imprime y no da color. "
            "Meta: el porcentaje contra la meta del liderazgo sobre los "
            "informes que la tienen — es lo único con color. 12 semanas: su "
            "forma, cada línea en su escala, con la primera y la última "
            "semana informadas debajo.")
    if model.scope.level != S.MISSION:
        note = ("Por comp.: por compañería y semana. Propia: su compromiso, "
                "sin color. Meta: contra la del liderazgo, lo único con "
                "color. 12 semanas: su forma, con la primera y la última "
                "cifra debajo."
                + (" Termina en y falta: proyección al ritmo reciente, sin "
                   "color." if forecast else ""))
    elif forecast:
        k = model.forward.finish[0]
        note += (f" Termina en: lo que va del traslado {model.forward.transfer} "
                 f"más las {es_display.integer(k.weeks_left)} semanas que "
                 f"faltan como la peor y la mejor de las últimas "
                 f"{es_display.integer(k.pace_weeks)}; falta por semana: lo "
                 f"que haría falta para la meta del traslado y cuántas veces "
                 f"el ritmo de hoy. Proyecciones, sin color.")
        note += _backtest_sentence(model)
    flow.append(Paragraph(PP.text(note), st["note"]))
    reach = _goal_reach_line(model)
    if reach:
        flow.append(Paragraph(PP.text(reach), st["note_lead"]))
    if model.comparison is not None and model.scope.level == S.MISSION:
        flow.append(Paragraph(PP.text(_comparison_note(model)), st["note"]))
    return flow


def opening(model) -> list:
    """The unit's name and the sentences a reader needs before the table:
    strongest and weakest against leadership's goal, its productivity, its
    baptisms where the mission is not the unit, and — at zone level — what is
    coming."""
    st = PP.styles()
    best, worst = _best_and_worst(model)
    flow = _heading(model)
    lines = []
    if best is not None:
        lines.append(f"Lo más fuerte: {best.label} va en {_pct(best.grade.pct)} "
                     f"de la meta del liderazgo — {_count(best.lead_actual)} "
                     f"contra {_count(round(best.lead_goal))}.")
    if worst is not None:
        lines.append(f"Lo que hay que mover: {worst.label}, en "
                     f"{_pct(worst.grade.pct)} — {_count(worst.lead_actual)} "
                     f"contra {_count(round(worst.lead_goal))}.")
    if best is None and worst is None:
        lines.append("Ningún Indicador Clave tiene con qué medirse en este "
                     "período: o no hay meta del liderazgo, o nadie informó.")
    if model.index.value is not None and model.scope.level != S.MISSION:
        lines.append(
            f"Productividad: {_idx(model.index.value)} — cada compañería "
            f"produce {_index_words(model.index.value)} que el promedio de la "
            f"misión" + (", sobre pocas cifras" if model.index.thin else "")
            + (f"; {FC.quadrant(model.index.value, model.trend)} en las "
               f"últimas seis semanas" if FC.quadrant(model.index.value,
                                                      model.trend) else "")
            + ".")
    fwd = model.forward
    if fwd.baptisms is not None:
        lines.append(fwd.baptisms.sentence)
    if model.scope.level == S.ZONE:
        bits = []
        if fwd.year is not None and fwd.year.low is not None:
            bits.append(f"cierre probable del año {_range(fwd.year.low, fwd.year.high)}"
                        + (f" contra su parte de la meta, {_int(fwd.year.goal)}"
                           if fwd.year.goal else ""))
        if fwd.pipeline is not None:
            bits.append(f"{_int(fwd.pipeline.open_dates)} fechas bautismales "
                        f"abiertas, {_range(fwd.pipeline.low, fwd.pipeline.high)} "
                        f"bautismos esperados en seis semanas")
        if bits:
            lines.append("Lo que viene: " + "; ".join(bits)
                         + " (registros de Tableau, proyección sin color).")
    if model.scope.level == S.ZONE:
        # Phase 4 at zone level, a sentence each: the zone's two pages
        # (decision 49) have no room for the mission's sections.
        for line in (_lever_sentence(model), _years_sentence(model),
                     _mix_sentence(model), _change_sentence(model)):
            if line:
                lines.append(line)
    if model.scope.level == S.DISTRICT:
        line = _pipeline_sentence(model)
        if line:
            lines.append(line)
    if model.scope.level == S.ZONE and model.children:
        silent = [a for c in model.children for a in c.areas_silent]
        lines.append(f"Quién informó: {model.compliance_label}"
                     + (f"; sin informe en todo el período: "
                        f"{', '.join(silent)}." if silent else
                        "; todas sus áreas informaron."))
    flow.append(PP.SectionHead("Dónde estamos", model.period.window_label))
    for line in lines:
        flow.append(Paragraph(PP.text(line), st["body"]))
    return flow


def _mix_sentence(model) -> str:
    """A zone's "who found them" in one line of its opening — the mission's
    page carries the full section; a zone's would cost it a third sheet."""
    block = model.tableau
    if block is None or not block.present or not block.mix or not block.found:
        return ""
    total = block.found
    before_total = sum(m.before for m in block.mix if m.before is not None)
    parts = []
    for m in block.mix:
        share = m.count / total * 100
        if share < 1:
            continue
        bit = f"{m.label.lower()} {_pct(share)}"
        if m.before is not None and before_total:
            bit += f" (antes {_pct(m.before / before_total * 100)})"
        parts.append(bit)
    out = (f"Quién las encontró: {_int(total)} personas · "
           + " · ".join(parts))
    if block.sources:
        top = block.sources[0]
        out += (f"; la mayor fuente, {top.label.lower()} "
                f"({_pct(top.count / total * 100)})")
    return out + " (Tableau)."


#: The most areas a zone's "Dónde enfocar" lists; the rest are named under it.
ZONE_FOCUS_ROWS = 5

#: The Pareto table: rank, unit, the share bar, the share, the running total,
#: where the unit is shortest, its productivity and its trend.
FOCUS_COLUMNS = (18.0, 138.0, 78.0, 40.0, 50.0, 92.0, 44.0, 60.0)

#: A Key Indicator in a cell too narrow for its full name — one line, so a
#: ranked table keeps its 17pt rows.
SHORT_KI = {"ki_new_people_real": "Nuevas personas",
            "ki_member_lessons_real": "Lecciones c/ miembros",
            "ki_friends_sacrament_real": "Sacramental",
            "ki_friends_first_week_real": "Primera semana",
            "ki_baptismal_date_real": "Fecha bautismal",
            "ki_baptized_confirmed_real": "Bautismos",
            "ki_rc_at_church_real": "Conversos recientes"}


def focus_block(model) -> list:
    """"Dónde enfocar" (AUDIT-2026-10-06 H6): which units hold the shortfall,
    and which of them are below the mission and falling."""
    st = PP.styles()
    rows = model.focus
    if not rows:
        return []
    noun = {S.MISSION: "distritos", S.ZONE: "áreas"}[model.scope.level]
    labels = {r.key: r.label for r in model.key_indicators}
    flow = [PP.SectionHead("Dónde enfocar",
                           f"lo que falta para la meta del liderazgo, por "
                           f"{noun[:-1]}")]
    table = []
    biggest = max(r.share for r in rows) or 1.0
    shown = rows
    if model.scope.level == S.ZONE:
        # Every row up to 80% of the shortfall, and the rest in one line: the
        # zone's two pages (decision 49) cannot carry thirteen areas twice,
        # and the full list is in the areas' own pages.
        cut = next((i for i, r in enumerate(rows, start=1)
                    if r.cumulative >= 80), len(rows))
        # And never more than ZONE_FOCUS_ROWS: since Phase 4 the zone's
        # second page also carries a line per district (4C.4).
        shown = rows[:min(cut, ZONE_FOCUS_ROWS)]
    for i, r in enumerate(shown, start=1):
        trail = [p for p in r.scope.trail if p != model.scope.name]
        name = r.name + (f" · {trail[0]}" if model.scope.level == S.MISSION
                         and trail else "")
        table.append([
            str(i), name,
            PP.split_bar(FOCUS_COLUMNS[2] - 8, pct=r.share / biggest * 100,
                         part=r.silent / biggest * 100),
            es_display.percent(r.share, 0), es_display.percent(r.cumulative, 0),
            _focus_cause(r, labels),
            _idx(r.index),
            FC.trend_words(r.trend, es_display.signed_percent)])
    flow.append(PP.table(
        table, FOCUS_COLUMNS,
        headers=("", noun.capitalize(),
                 ("Parte de", "lo que falta"), "", "Acumulado",
                 ("Donde más", "le falta"), ("Produc-", "tividad"),
                 ("Tendencia", "6 semanas")),
        align=("r", "l", "l", "r", "r", "l", "r", "r")))
    head = next((i for i, r in enumerate(rows, start=1) if r.cumulative >= 80),
                len(rows))
    rest = rows[len(shown):]
    falling = [r.name for r in rows
               if FC.quadrant(r.index, r.trend) == "debajo y bajando"]
    flow.append(Spacer(0, 6))
    readable = [r for r in rows if FC.trend_step(r.trend) is not None]
    if readable:
        flow.append(PP.quadrant(
            PP.CONTENT_WIDTH, 150.0 if model.scope.level == S.MISSION else 130.0,
            [(r.name, r.index,
              FC.trend_value(r.trend) if FC.trend_step(r.trend) else 0.0,
              bool(FC.trend_step(r.trend)))
             for r in readable],
            x_label="productividad, misión = 100",
            y_label="tendencia de las últimas 6 semanas",
            corner="debajo de la misión y bajando"))
    # With every unit on too few reports (an area files at most three a
    # side) the chart would be a row of hollow dots on the zero line — the
    # picture of a measurement that was not made. It says so instead.
    flow.append(Spacer(0, 4))
    sentence = (f"Los primeros {es_display.integer(head)} {noun} suman el "
                f"{es_display.percent(rows[head - 1].cumulative, 0)} de lo que "
                f"le falta a {'la misión' if model.scope.level == S.MISSION else 'la zona'} "
                f"para la meta del liderazgo en este período. ")
    if rest:
        sentence += (f"Fuera de la tabla, {es_display.integer(len(rest))} "
                     f"{noun} más con el "
                     f"{es_display.percent(100 - shown[-1].cumulative, 0)} "
                     f"restante: {', '.join(r.name for r in rest)}. ")
    if not readable:
        sentence += (f"Sin gráfico de tendencia: ninguna de sus {noun} tiene "
                     f"informes suficientes para leerla. ")
    else:
        sentence += (("Debajo de la misión y bajando: " + ", ".join(falling)
                      + ". ") if falling else
                     "Ninguno está debajo de la misión y bajando más allá de "
                     "lo que varía de una semana a otra. ")
    quiet = sum(r.silent for r in rows)
    if quiet >= 1:
        sentence += (f"El {es_display.percent(quiet, 0)} de lo que falta es "
                     f"de semanas sin informe (la parte pálida de la barra): "
                     f"ahí la conversación es sobre informar, no sobre el "
                     f"trabajo.")
    if model.scope.level == S.ZONE:
        # A zone leader is handed the mission's pages with the zone's
        # (decision 43's run sheet), where the method is spelled out once.
        sentence += "El método, como en «Dónde enfocar» de la misión."
        flow.append(Paragraph(PP.text(sentence.strip()), st["note_lead"]))
        return flow
    flow.append(Paragraph(PP.text(sentence.strip()), st["note_lead"]))
    flow.append(Paragraph(PP.text(
        "Parte de lo que falta: la meta del liderazgo de cada unidad (todas "
        "sus áreas, a prorrata del período) menos lo que informó, sumado por "
        "indicador con los pesos del índice; quien supera su meta no compensa "
        "a nadie. «Sin informe» en la columna de al lado: más de la mitad de "
        "su parte es de semanas que nadie informó. Tendencia: las últimas tres "
        "semanas contra las tres anteriores, por informe; «estable» si el "
        "cambio cabe en lo que la unidad varía de una semana a otra, «pocas "
        "cifras» con menos de 6 informes por lado — en el gráfico, un punto "
        "hueco sobre la línea del cero."), st["note"]))
    return flow


def _focus_cause(row, labels) -> str:
    """Where a unit's part of the shortfall comes from: silence, when more
    than half of it is goal for weeks nobody filed (PLAN 4A.2), else the Key
    Indicator it is shortest on."""
    if row.mostly_silent:
        return "Sin informe"
    if not row.worst:
        return es_display.NA
    return SHORT_KI.get(row.worst) or labels.get(row.worst, "")


#: The mature funnel's columns: unit, cohort, six stages, the largest leak.
#: The leak column holds its step's two rates on the same line (148pt for
#: "contacto a lecciones · 4,7% vs 6,8%", 120pt set): on a second line they
#: grew every row and sent two zones' funnels onto a third sheet.
FUNNEL_COLUMNS = (80.0, 40.0, 42.0, 42.0, 42.0, 42.0, 42.0, 42.0, 148.0)
#: The rates' heads in a 70pt column — "Conversaciones Significativas" set
#: in tracked capitals is twice that.
RATE_HEADS = {"contact_rate": "Contacto", "mc_rate": "Conversación",
              "lesson_rate": "Lecciones", "close_rate": "Invitación"}

#: The rates-by-zone columns.
RATES_COLUMNS = (130.0, 70.0, 70.0, 70.0, 70.0, 110.0)


def levers_block(model) -> list:
    """"Palancas" (AUDIT §5 item 4, M2, M3): the mature funnel by unit
    against the mission with each unit's largest leak named, and — at mission
    level — the conversion rates by zone and a result-to-driver line per
    pilot zone."""
    st = PP.styles()
    fn = model.funnel
    flow = []
    if fn is not None and fn.mission is not None:
        short = ("Intento", "Contacto", "Lecc.", "Iglesia", "Fecha",
                 "Bautismo")
        flow.append(PP.SectionHead(
            "Palancas: el embudo maduro",
            f"encontradas del {es_display.day_month(fn.start)} al "
            f"{es_display.day_month(fn.end, with_year=True)}, seguidas hasta hoy"))

        # The note ABOVE the table (Phase V's rule): under it, it was widowed
        # onto a page of its own behind a zone's two pages.
        flow.append(Paragraph(PP.text(
            "Como el embudo maduro de la misión, por distrito."
            if model.scope.level == S.ZONE else
            "Personas encontradas hace tres a seis meses y la parte que llegó "
            "a cada paso hasta hoy: con ese tiempo, la iglesia, la fecha y el "
            "bautismo ya tuvieron ocasión de ocurrir. La mayor fuga es el "
            "paso que convierte menos del 85% de lo que convierte la misión; "
            "a su lado, qué parte de los que llegaron a ese paso pasó al "
            "siguiente, aquí y en la misión. Registros de Tableau por "
            "persona."), st["note"]))
        flow.append(Spacer(0, 3))

        def share(v):
            # A decimal under 10%: the lower funnel lives at 0,3-5%, and
            # whole numbers printed "0%" in every row under a leak named
            # "fecha a bautismo" that nobody could then check.
            return es_display.percent(v, 1 if v < 10 else 0)

        def leak(r, bold):
            if not bold and r.thin:
                return "pocas personas"
            if not r.leak:
                return "" if bold else "—"
            if r.leak_step is None:
                return r.leak
            own, mission = r.leak_step
            return f"{r.leak} · {share(own)} vs {share(mission)}"

        def line(r, bold=False):
            return ([r.name, _int(r.found)]
                    + [(share(r.pct(i)) if r.found else "")
                       for i in range(len(fn.stages))]
                    + [leak(r, bold)])

        table = [line(fn.mission, True)] + [line(r) for r in fn.rows]
        flow.append(PP.table(
            table, FUNNEL_COLUMNS,
            headers=("", ("Encon-", "tradas")) + tuple(
                (s, "%") for s in short[:len(fn.stages)]) + (
                ("Mayor fuga", "vs la misión"),),
            align=("l", "r") + ("r",) * len(fn.stages) + ("l",)))
    if model.child_rates:
        flow.append(Spacer(0, 8))
        flow.append(PP.SectionHead("Tasas de conversión por zona",
                                   "la razón de los totales · en puntos contra la misión"))
        mission = {r["key"]: r for r in model.rates}
        keys = [r["key"] for r in model.rates]
        heads = [RATE_HEADS.get(r["key"], (r.get("label") or r["key"])
                                .replace("Tasa de ", ""))
                 for r in model.rates]
        table = [["la misión"] + [es_display.percent(mission[k]["value"], 1)
                                  if mission[k]["value"] is not None
                                  else es_display.NA for k in keys] + [""]]
        for zone, rates in model.child_rates:
            by = {r["key"]: r for r in rates}
            low = FC.lowest_rate(rates, model.rates)
            table.append(
                [zone.name] + [es_display.percent(by[k]["value"], 1)
                               if by.get(k) and by[k]["value"] is not None
                               else es_display.NA for k in keys]
                + [(f"{heads[keys.index(low[1])].lower()} "
                    f"{es_display.number(low[0], 1)} pts")
                   if low is not None else "ninguna fuera del azar"])
        flow.append(PP.table(
            table, RATES_COLUMNS,
            headers=tuple(["Zona"] + heads
                          + [("Más baja", "contra la misión")]),
            align=("l", "r", "r", "r", "r", "l")))
        # What each rate divides by (AUDIT-2026-10-06 H2): Lecciones is over
        # contact ATTEMPTS, which nobody guesses.
        divides = []
        for r in model.rates:
            metric = r.get("metric")
            if metric is None:
                continue
            divides.append(
                f"{RATE_HEADS.get(r['key'], r['key'])}: "
                f"{(r.get('numerator_label') or metric.numerator).lower()} "
                f"entre {(r.get('denominator_label') or metric.denominator).lower()}")
        if divides:
            flow.append(Spacer(0, 3))
            flow.append(Paragraph(PP.text(
                "Qué divide a qué — " + " · ".join(divides) + ". Una tasa "
                "es la razón de los totales de la zona, no el promedio de sus "
                "áreas. «Más baja» sólo nombra una tasa cuando la de la "
                "misión queda fuera del rango que la zona daría por azar con "
                "sus propias cifras (80%)."), st["note"]))
        drivers = _driver_lines(model)
        if drivers:
            flow.append(Spacer(0, 6))
            flow.append(PP.SectionHead("De resultado a causa",
                                       "una línea por zona", rule=False))
            for text in drivers:
                flow.append(Paragraph(PP.text(text), st["note_lead"]))
    return flow


#: The sources table's columns: source, people, share now, share before, bar.
SOURCES_COLUMNS = (200.0, 60.0, 60.0, 70.0, 130.0)


def finding_mix_block(model) -> list:
    """Who found the people of this period, and by what means — Tableau's
    category and source columns, on the mission's pages (a zone gets the
    same in one sentence of its opening, `_mix_sentence`).

    Brought back 2026-10-07: Phase 3 retired it with the window-funnel pages
    it lived on, which no decision asked for, and it is the one place the
    packet says how little of the finding comes from members. The share in
    the same number of days just before stands beside each source; shares,
    not percentage changes, so a source of 20 people cannot read "+150%".
    """
    st = PP.styles()
    block = model.tableau
    if block is None or not block.present or not (block.mix or block.sources):
        return []
    W = PP.CONTENT_WIDTH
    total = block.found or 0
    before_total = (sum(m.before for m in block.mix
                        if m.before is not None) if block.mix else 0)
    flow = [PP.SectionHead("Quién las encontró y de dónde",
                           f"{_int(total)} personas · {block.window.caption}")]
    if block.mix:
        flow += [PP.share_bar(W, [(m.label, m.count) for m in block.mix]),
                 Spacer(0, 4)]
    if block.sources and total:
        def before_share(x):
            if x.before is None or not before_total:
                return es_display.NA
            return _pct(x.before / before_total * 100)

        rows = [[x.label, _int(x.count), _pct(x.count / total * 100),
                 before_share(x),
                 PP.bar_vs_goal(110, pct=x.count / total * 100,
                                fill=PP.SERIES[0])]
                for x in block.sources]
        flow.append(PP.table(
            rows, SOURCES_COLUMNS,
            headers=(("Fuente", f"las {_int(len(block.sources))} más grandes"),
                     "Personas", ("Del total", "este período"),
                     ("Antes", "mismos días previos"), ""),
            align=("l", "r", "r", "r", "l")))
    note = ("Categoría y fuente de hallazgo de Tableau, sobre las personas "
            "encontradas en el período, no sobre el año.")
    if block.before is not None and block.before.usable:
        note += (f" «Antes» es la misma parte en {block.before.label}.")
    note += " " + block.scope_note
    flow += [Spacer(0, 3), Paragraph(PP.text(note), st["note"])]
    return flow


def _driver_lines(model) -> list:
    """M3: per pilot zone, the result it is shortest on, the conversion rate
    furthest under the mission's, and its largest leak — one line, so a
    lagging Key Indicator arrives with the activity behind it. Since 4C.4
    the line is `model.drivers`, with the nightly input behind the result."""
    return [s for s in (_driver_sentence(d) for d in model.drivers
                        if d.low_key) if s]


def trend_block(model) -> list:
    """The last twelve complete weeks, whatever the period (AUDIT H3): the
    shape of all twelve, the figures of the last six, and how many areas
    filed each week under them."""
    st = PP.styles()
    series = [model.trend_series.get(r.key) for r in model.key_indicators]
    series = [s for s in series if s is not None and s.points]
    if not series:
        return []
    weeks = [p.week for p in series[0].points]
    boundaries = []
    for day, _ in series[0].boundaries:
        after = [i for i, w in enumerate(weeks) if w >= day]
        if after and after[0] > 0:
            boundaries.append(after[0])
    rows = [(s.label, [p.actual for p in s.points],
             _count(sum(p.actual for p in s.points if p.actual is not None)))
            for s in series]
    reporting = [p.reporting for p in series[0].points]
    return [
        PP.SectionHead("Las últimas 12 semanas",
                       "la forma de doce, las cifras de seis"),
        PP.week_table(PP.CONTENT_WIDTH, weeks, rows, boundaries=boundaries,
                      columns=6, spark_width=110.0,
                      footer=("Áreas que informaron, de "
                              f"{es_display.integer(model.scope.area_count)}",
                              reporting, "")),
        Spacer(0, 4),
        Paragraph(PP.text(
            "Cada línea en su propia escala; la regla punteada es un día de "
            "traslado y una semana que nadie informó corta la línea. Total: "
            "las doce semanas."), st["note"]),
    ]


# ── Phase 4: history, change, levers, the goal's reach (PLAN-2026-10-06 §5) ──

#: The other-years table: milestone, three years, this year against last.
YEARS_COLUMNS = (220.0, 70.0, 70.0, 70.0, 90.0)


def _signed_int(value: float) -> str:
    n = round(value)
    return ("+" if n > 0 else "") + es_display.integer(n)


def _year_change(now: int, before: int) -> str:
    """This year against last: a percentage from 20 events up on both
    sides, otherwise the difference in units (H5's rule)."""
    if now >= 20 and before >= 20:
        pct = (now - before) / before * 100
        return ("igual" if abs(pct) < 0.5
                else es_display.signed_percent(pct))
    diff = now - before
    return ("+" if diff > 0 else "") + es_display.integer(diff)


def years_block(model) -> list:
    """"Las mismas semanas, otros años" (4B.1, decision 52): Tableau's own
    milestones, under their own names, over the period's days of this year
    and the two before. Never beside a form figure (decision 34)."""
    st = PP.styles()
    y = model.years
    if y is None or not y.rows:
        return []
    window = (f"{es_display.day_month(y.start)} - "
              f"{es_display.day_month(y.end)} de cada año")
    rows = [[label] + [_int(c) for c in counts]
            + [_year_change(counts[-1], counts[-2]) if len(counts) >= 2
               else es_display.NA]
            for label, counts in y.rows]
    scope = ("las 10 zonas de la misión" if model.scope.level == S.MISSION
             else "sus áreas del organigrama de hoy")
    return [
        PP.SectionHead("Las mismas semanas, otros años",
                       f"registros de Tableau · {window}"),
        PP.table(rows, YEARS_COLUMNS,
                 headers=(("Hito", "Tableau, por persona"),)
                 + tuple(str(v) for v in y.years)
                 + ((f"{y.years[-1]}", f"contra {y.years[-2]}"),),
                 align=("l", "r", "r", "r", "r")),
        Spacer(0, 3),
        Paragraph(PP.text(
            f"Hitos del registro de Tableau por persona, en {scope}, contados "
            f"en los mismos días de cada año hasta donde llega la exportación. "
            f"No son los Indicadores Clave — el formulario semanal empezó en "
            f"agosto de 2026 — y nunca se suman con ellos. Los de "
            f"{y.years[-1]} pueden subir unos días, mientras se anotan."),
            st["note"]),
    ]


#: The transfers table: unit, one column per transfer, the change, a note.
def _history_columns(n: int) -> tuple:
    return (170.0,) + (60.0,) * n + (60.0, 520.0 - 170.0 - 60.0 * (n + 1))


def changes_block(model) -> list:
    """"Qué cambió" (4B.2-4B.3, decision 53): every zone and district's
    productivity by transfer, who sits under the mission transfer after
    transfer, who entered or left the head of "Dónde enfocar", and how the
    year's landing moved."""
    st = PP.styles()
    ch = model.changes
    if ch is None:
        return []
    flow = [PP.SectionHead("Qué cambió",
                           "con los informes de hoy, también los atrasados")]
    h = ch.history
    left_out = 0
    if h is not None and h.rows and len(h.transfers) >= 2:
        rows = []
        for scope, values in h.rows:
            now, then = values[-1].value, values[-2].value
            moved = (now is not None and then is not None
                     and abs(now - then) >= HISTORY_MOVE)
            # Every zone; a district only when it moved or stays under —
            # the rest is the same story as last transfer.
            if (scope.level != S.ZONE and not moved
                    and not h.chronic(values)):
                left_out += 1
                continue
            move = (_signed_int(now - then)
                    if now is not None and then is not None else es_display.NA)
            note = []
            if h.chronic(values):
                note.append("debajo de la misión traslado tras traslado")
            if any(v.thin for v in values):
                note.append("pocas cifras")
            trail = [p for p in scope.trail if p != model.scope.name]
            name = (f"{scope.name} · zona" if scope.level == S.ZONE
                    else scope.name + (f" · {trail[0]}"
                                       if model.scope.level == S.MISSION
                                       and trail else ""))
            rows.append([name] + [_idx(v.value) for v in values]
                        + [move, " · ".join(note)])
        flow.append(PP.table(
            rows, _history_columns(len(h.transfers)),
            headers=(("Productividad", "misión = 100"),)
            + tuple(h.transfers) + ("Cambio", ""),
            align=("l",) + ("r",) * (len(h.transfers) + 1) + ("l",),
            pad=2.5))
        flow.append(Spacer(0, 3))
    lines = []
    if h is not None and h.chronic_names:
        lines.append(
            f"Debajo de {_int(CHRONIC_BELOW)} en cada traslado desde que hay "
            f"formulario: {', '.join(h.chronic_names)}. Es la lista que no "
            f"depende de una semana buena o mala.")
    if ch.entered or ch.left:
        bits = []
        if ch.entered:
            bits.append("entraron " + ", ".join(ch.entered))
        if ch.left:
            bits.append("salieron " + ", ".join(ch.left))
        lines.append(f"En «Dónde enfocar», contra {ch.against}: "
                     + "; ".join(bits) + ".")
    now_year = model.forward.year
    if ch.landing_then is not None and now_year is not None \
            and now_year.low is not None:
        lines.append(
            f"El cierre probable del año: {ch.landing_then_label} era "
            f"{_range(ch.landing_then.low, ch.landing_then.high)}; hoy es "
            f"{_range(now_year.low, now_year.high)}, de una meta de "
            f"{_int(now_year.goal)}.")
    for line in lines:
        flow.append(Paragraph(PP.text(line), st["note_lead"]))
    rest = (f" Fuera de la tabla, {_int(left_out)} distritos que se movieron "
            f"menos de {_int(HISTORY_MOVE)} puntos." if left_out else "")
    flow.append(Paragraph(PP.text(
        "Productividad de cada traslado entero contra la misión de ese "
        "traslado; el formulario semanal empezó el 9 de agosto, así que el "
        "primer traslado cuenta sólo sus semanas con formulario. Calculado "
        "con los informes de hoy, también los atrasados: puede no coincidir "
        f"con lo que imprimió el paquete de entonces.{rest}"), st["note"]))
    return flow


#: A district's index has to move this many points between transfers to be
#: listed in "Qué cambió" (every zone is listed).
HISTORY_MOVE = 20.0


#: The levers table: zone, the leak, dates, baptisms, a note.
LEVER_COLUMNS = (130.0, 120.0, 90.0, 90.0, 90.0)


def _lever_range(span) -> str:
    if span is None:
        return es_display.NA
    lo, hi = span
    if hi < 0.5:
        return "menos de 1"
    return _range(max(0.0, lo), hi)


def levers_size_block(model) -> list:
    """"Cuánto vale cada fuga" (4C.2, decision 54): if a zone's largest leak
    converted at the mission's rate, how many more dates and baptisms per
    six weeks of finding. Ranked, ranges, never coloured."""
    st = PP.styles()
    levers = model.forward.levers
    if model.scope.level != S.MISSION or not levers:
        return []
    rows = [[v.name, v.leak, _lever_range(v.dates), _lever_range(v.baptisms),
             "piloto de Compass" if v.pilot else "sin formularios"]
            for v in levers]
    return [
        PP.SectionHead("Cuánto vale cada fuga",
                       "si convirtiera como la misión · por traslado"),
        PP.table(rows, LEVER_COLUMNS,
                 headers=("Zona", ("Mayor fuga", "del embudo maduro"),
                          ("Fechas más", "por 6 semanas"),
                          ("Bautismos más", "por 6 semanas"), ""),
                 align=("l", "l", "r", "r", "l")),
        Spacer(0, 3),
        Paragraph(PP.text(
            "Si el paso de su mayor fuga convirtiera como el de la misión: "
            "cuántas personas más pasarían, llevadas por los pasos siguientes "
            "como los da la zona o como los da la misión (el rango cubre las "
            "dos y el azar de la propia zona), y repartidas en seis semanas de "
            "hallazgo. Es un tamaño, no un pronóstico: dice qué fuga vale más "
            "la pena. Registros de Tableau por persona, las 10 zonas."),
            st["note"]),
    ]


def _goal_reach_line(model) -> str:
    """4D.1 (decision 56): how far leadership's goal is from the best the
    unit has done in a transfer the form covers. Grading is unchanged."""
    reach = model.goal_reach
    if not reach:
        return ""
    labels = {r.key: r.label for r in model.key_indicators}
    over = sorted(((r, k) for k, (r, _, _) in reach.items() if r >= 1.2),
                  reverse=True)
    top = max(reach.values(), key=lambda t: t[0])
    if over:
        names = ", ".join(f"{labels.get(k, k)} ({es_display.number(r, 1)}×)"
                          for r, k in over)
        return (f"La meta del liderazgo pide más de 1,2 veces el mejor "
                f"traslado de {'la misión' if model.scope.level == S.MISSION else 'la zona'} "
                f"desde que hay formulario en: {names}. Ahí la meta, no el "
                f"trabajo, puede ser lo que está fuera de alcance.")
    return (f"Alcance de la meta: en cada indicador, la meta del liderazgo "
            f"pide a lo más {es_display.number(top[0], 1)} veces el mejor "
            f"traslado desde que hay formulario ({top[2]}) — exigente pero "
            f"ya alcanzado.")


def _backtest_sentence(model) -> str:
    """4C.1: the transfer finish's method, tried on Tableau's history."""
    checks = [(label, b) for label, b in model.forward.finish_check if b.cases]
    if not checks:
        return ""
    bits = [f"{label.lower()}: acertó {es_display.integer(b.hits)} de "
            f"{es_display.integer(len(b.cases))}, centro a un "
            f"{es_display.percent(b.miss or 0, 0)} típico"
            for label, b in checks]
    return (" Probado: el mismo método sobre las semanas de Tableau desde "
            "2024, en traslados de seis semanas cortados en el mismo punto — "
            + "; ".join(bits) + ".")


def _year_check_sentence(model) -> str:
    """4C.1: the year's landing, made at this month of earlier years."""
    yc = model.forward.year_check
    if yc is None or not yc.cases:
        return ""
    bits = [f"a fin de {when} daba {_range(lo, hi)} y el año cerró en "
            f"{_int(actual)}" for when, lo, hi, actual in yc.cases]
    return " Probado: el mismo cálculo " + "; ".join(bits) + "."


def _driver_sentence(d) -> str:
    """One `Driver` in words: result, rate, leak, the nightly input."""
    bits = []
    if d.low_key:
        bits.append(f"lo más bajo, {d.low_label}: {_idx(d.low_ratio)}")
    if d.input is not None:
        label, real, goal, pct = d.input
        bits.append(f"detrás, {label.lower()}: {_goal(real)} por área y semana"
                    + (f" contra {_goal(goal)}" if goal else ""))
    if d.rate is not None:
        label, value, mission = d.rate
        bits.append(f"{label.lower()} {es_display.percent(value, 1)} contra "
                    f"{es_display.percent(mission, 1)} de la misión")
    if d.leak:
        step = ""
        if d.leak_step:
            step = (f" {es_display.percent(d.leak_step[0], 1)} contra "
                    f"{es_display.percent(d.leak_step[1], 1)}")
        bits.append(f"fuga de {d.leak}{step}")
    return f"{d.name}: " + "; ".join(bits) + "." if bits else ""


def drivers_block(model) -> list:
    """"De resultado a causa" on a zone's pages: one line per district
    (4C.4). The mission's lines are part of its levers block."""
    st = PP.styles()
    if model.scope.level != S.ZONE or not model.drivers:
        return []
    lines = [s for s in (_driver_sentence(d) for d in model.drivers) if s]
    if not lines:
        return []
    return ([PP.SectionHead("De resultado a causa", "un distrito por línea")]
            + [Paragraph(PP.text(s), st["note"]) for s in lines])


def _pipeline_sentence(model) -> str:
    """4C.3 (decision 55): a district's open dates in one line."""
    pl = model.forward.pipeline
    if pl is None:
        return ""
    if pl.open_dates < 15:
        return (f"Lo que viene: {_int(pl.open_dates)} fechas bautismales "
                f"abiertas — pocas fechas para un pronóstico (registros de "
                f"Tableau).")
    return (f"Lo que viene: {_int(pl.open_dates)} fechas bautismales abiertas, "
            f"{_range(pl.low, pl.high)} bautismos esperados en seis semanas "
            f"(registros de Tableau, proyección sin color).")


def _years_sentence(model) -> str:
    """4B.1 at zone level, in one line of its opening."""
    y = model.years
    if y is None or len(y.years) < 2:
        return ""
    short = {"Personas encontradas": "encontradas",
             "Asistieron a la iglesia por primera vez": "primera vez en la iglesia",
             "Fecha bautismal fijada": "fechas fijadas",
             "Bautizados (fecha de confirmación)": "bautizados"}
    bits = [f"{short.get(label, label.lower())} {_int(c[-1])} ({_int(c[-2])})"
            for label, c in y.rows]
    return (f"Las mismas semanas de {y.years[-2]}, entre paréntesis "
            f"(registros de Tableau): " + " · ".join(bits) + ".")


def _change_sentence(model) -> str:
    """4B.2-4B.3 at zone level, in one line of its opening."""
    ch = model.changes
    if ch is None or ch.history is None or len(ch.history.transfers) < 2:
        return ""
    out = ""
    chronic = ch.history.chronic_names
    if chronic:
        out = (f"Debajo de {_int(CHRONIC_BELOW)} de productividad en cada "
               f"traslado desde que hay formulario: {', '.join(chronic)}.")
    if ch.entered or ch.left:
        bits = []
        if ch.entered:
            bits.append("entraron " + ", ".join(ch.entered))
        if ch.left:
            bits.append("salieron " + ", ".join(ch.left))
        out += (" " if out else "") + (f"En «Dónde enfocar», contra "
                                       f"{ch.against}: " + "; ".join(bits) + ".")
    return out


def _lever_sentence(model) -> str:
    """4C.2 at zone level: its own row of the mission's levers."""
    if not model.forward.levers:
        return ""
    v = model.forward.levers[0]
    worth = []
    if v.dates is not None:
        worth.append(f"{_lever_range(v.dates)} fechas")
    if v.baptisms is not None:
        worth.append(f"{_lever_range(v.baptisms)} bautismos")
    return (f"Su mayor fuga, {v.leak}: si convirtiera como la misión, "
            f"{' y '.join(worth)} más por traslado (registros de Tableau, "
            f"un tamaño, no un pronóstico).")


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
            # A section SHORTER than the floor needs only its own height
            # (2026-10-07): a zone's three-district table is ~110pt, and the
            # 140pt floor sent it to the next sheet and left a third of
            # Angol's first page blank.
            out.append(CondPageBreak(min(floor, _height(block) + 2)))
        out.extend(block)
    return out


def _height(block) -> float:
    """How tall a list of flowables sets at the content width — inf if any
    of them cannot say, so the floor stands."""
    total = 0.0
    for f in block:
        try:
            total += f.wrap(PP.CONTENT_WIDTH, PP.PAGE_HEIGHT)[1]
            total += f.getSpaceBefore() + f.getSpaceAfter()
        except Exception:
            return math.inf
    return total


def mission_pages(model, goals, peers=None) -> list:
    """The president's section (AUDIT-2026-10-06 §5): the tablero, where to
    focus, the zones and who reported, the baptisms and what is coming, the
    levers, the twelve-week strip, and the nightly work."""
    return run_on([
        tablero_block(model), focus_block(model),
        children_page(model) + reporting_block(model),
        baptism_page(model), levers_block(model), levers_size_block(model),
        finding_mix_block(model), trend_block(model), years_block(model),
        changes_block(model), nightly_page(model, goals),
    ])


def zone_pages(model, goals, peers=None) -> list:
    """Two pages (decision 49): the tablero with the transfer's finish and
    its twelve weeks, the productivity ladder against the mission, its
    districts, where its shortfall sits among its areas, and its levers."""
    return run_on([
        tablero_block(model), ladder_block(model, gaps=False),
        children_page(model),
        # Every area by productivity when there is no shortfall to divide —
        # a cycle nobody set goals for — so the zone's areas never vanish.
        focus_block(model) or areas_page(model), levers_block(model),
        drivers_block(model),
    ])


def district_pages(model, goals, peers=None) -> list:
    """One page (decision 49): the tablero (its twelve weeks are the spark
    column), the ladder to its zone and the mission, and its areas by
    productivity."""
    return run_on([
        tablero_block(model), ladder_block(model, gaps=False, strip=False),
        children_page(model),
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


# ── An area, which is a companionship ───────────────────────────

AREAS_PER_PAGE = 3


def _area_spark(model, row) -> object:
    """One Key Indicator's last twelve weeks, as a drawing for its own row."""
    values, bounds = _spark_of(model, row.key)
    if len([v for v in values if v is not None]) < 2:
        return None
    return PP.sparkline(AREA_COLUMNS_SPARK, 8.0, list(values),
                        boundaries=bounds)


#: The width the spark gets inside the area rows' last column.
AREA_COLUMNS_SPARK = PP.AREA_ROW_COLUMNS[5] - 6

#: The nightly inputs a companionship controls (AUDIT M5), in the words the
#: area line prints them with.
AREA_NIGHTLY = (("contacts_attempted", "intentos de contacto"),
                ("friend_lessons", "lecciones con amigos"),
                ("lessons_member_present", "con miembro presente"),
                ("baptismal_invitations", "invitaciones al bautismo"),
                ("church_invites", "invitaciones a la iglesia"))


def area_nightly_line(model) -> str:
    """The companionship's own nights, per week against its goal."""
    rows = {r.key: r for r in model.nightly_metrics}
    bits = []
    for key, words in AREA_NIGHTLY:
        r = rows.get(key)
        if r is None or r.per_reporting_area_week is None:
            continue
        goal = (f" de {_per_week(r.goal_per_area_week)}"
                if r.goal_per_area_week else "")
        bits.append(f"{words} {_per_week(r.per_reporting_area_week)}{goal}")
    cov = model.nightly_coverage
    if not bits:
        return ("Noches: ninguna informada en el período." if cov is not None
                else "")
    head = "Noches, por semana"
    if cov is not None:
        head += f" ({cov.label} informados)"
    return head + ": " + " · ".join(bits) + "."


def area_lines(model) -> list:
    """The area's seven, each carrying its own weeks."""
    lines = ki_lines(model, comparable=False)
    return [replace(line, spark=_area_spark(model, row))
            for line, row in zip(lines, model.key_indicators)]


def area_block(model) -> list:
    """One area's third of a page (P5 (a)): who they are, their seven against
    leadership's goal with their twelve weeks, their own nights against
    their goals (AUDIT M5), their productivity against their district, zone
    and mission, and what the agents chose as their strength."""
    st = PP.styles()
    W = PP.CONTENT_WIDTH
    trail = " · ".join(model.scope.trail)
    flow = [
        Paragraph(PP.text(model.scope.name), st["area_title"]),
        PP.companionship_line(model.scope.companions),
        Paragraph(PP.text(" · ".join(x for x in (trail, model.compliance_label,
                                                 area_ladder_line(model))
                                     if x)), st["note"]),
        Spacer(0, 2),
        PP.area_ki_rows(W, area_lines(model)),
        Spacer(0, 2),
    ]
    nights = area_nightly_line(model)
    if nights:
        flow.append(Paragraph(PP.text(nights), st["note"]))
    strong = ", ".join(model.strengths)
    grow = model.growth or ""
    if strong or grow:
        bits = []
        if strong:
            bits.append(f"Su fortaleza: {strong}")
        if grow:
            bits.append(f"Para crecer: {grow}")
        flow.append(Paragraph(PP.text(" · ".join(bits)), st["note"]))
    else:
        flow.append(Paragraph(PP.text(
            "Sin fortaleza ni meta de crecimiento esta semana — el análisis "
            "de los agentes va una semana atrás de los Indicadores Clave."),
            st["note"]))
    scores = model.scores
    if scores is not None and scores.measured:
        # Kept on the area, where it has a comparator (its rank in its
        # district); gone from mission and zone pages, where it had none
        # (AUDIT-2026-10-06 M1).
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
    return flow



def area_ladder_line(model) -> str:
    """The area against its district, its zone and the mission, in one line.

    The half page has no room for the ranked table a zone or a district gets,
    and a companionship's question is smaller anyway: are we ahead of or
    behind the people around us. Three signed figures answer it in the space
    a sentence takes.
    """
    own = model.index
    if own.value is None:
        return ""
    bits = [f"{r.role} {_idx(r.index.value)}" for r in model.ladder[1:]
            if not r.is_self and r.index.value is not None]
    line = (f"Productividad {_idx(own.value)} (misión = 100)"
            + (" · pocas cifras" if own.thin else ""))
    return line + (" · " + " · ".join(bits) if bits else "")


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

    def source(name, tab):
        """A name the reader knows, and the sheet tab under it in small type
        for the one who wants to check a figure (AUDIT-2026-10-06 M4: tab
        names are developer language everywhere else in the packet)."""
        return [name, Paragraph(PP.text(f"pestaña {tab}"), st["note"])]

    rows = [
        ["Indicadores Clave", source("Formulario semanal", "WEEKLY_KI"),
         "Lo que las compañerías informaron cada semana, filtrado al "
         "organigrama por el agente."],
        ["Meta de las compañerías", source("Formulario semanal",
                                           "WEEKLY_FORM_RAW"),
         "La meta de una semana se escribe en el formulario de la semana "
         "ANTERIOR, y así se lee aquí."],
        ["Meta de traslado", source("Metas del liderazgo",
                                    "AREA_TRANSFER_GOALS"),
         "La meta del liderazgo por área por ciclo, prorrateada a la parte "
         "del traslado que cubre este período."],
        ["Trabajo nocturno", source("Formulario nocturno", "DAILY_LOG"),
         "Un informe por área por noche. La meta es la de cada sector para "
         "esa semana, recalculada cada lunes, y se mide por noche "
         "informada."],
        ["Fortaleza y crecimiento", source("Análisis de los agentes",
                                           "WEEKLY_BREAKDOWNS"),
         "Elegidas por los agentes, no recalculadas aquí. Van una semana "
         "atrás de los Indicadores Clave."],
        ["Puntajes", source("Puntajes de los agentes", "SCORES"),
         "Los cuatro puntajes del agente, promediados sobre las semanas del "
         "período. Un área sin calificar no cuenta como cero."],
        ["Organigrama", source("Organigrama de la misión", "MISSION_ORG"),
         "Zona, distrito y compañería. La pertenencia se decide aquí y nunca "
         "en la columna de una fila de datos."],
        ["Personas encontradas", source("Tableau, por persona",
                                        "TABLEAU_DETAIL"),
         "Una fila por persona encontrada, con las fechas de sus hitos: quién "
         "las encontró, el embudo maduro y cuánto vale cada fuga, las fechas "
         "abiertas, los bautismos por zona, las mismas semanas de otros años y "
         "la prueba de las proyecciones. Cubre las 10 zonas; los formularios "
         "de Compass cubren 4."],
        ["Bautismos del año", source("Tableau, certificada por mes",
                                     "TABLEAU_BAPTISMS"),
         "La cifra certificada por mes. No es la que informa el formulario "
         "semanal, y las dos no se suman."],
        ["Bautismos del período", source("Tableau, certificada por período",
                                         "TABLEAU_BAPTISM_WINDOWS"),
         "La misma cifra certificada, para los días exactos de la semana, "
         "los traslados y las últimas seis semanas. La llena la "
         "sincronización nocturna."],
    ]
    flow.append(PP.table(rows, [108, 124, W - 232],
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
    if period.key == P.LAST_MONTH and period.weeks:
        # Risk 2 of PLAN-2026-10-13: the month's form weeks and its days are
        # different spans, and the certified baptisms count the days.
        first_monday = period.weeks[0] - timedelta(days=6)
        sentences.append(
            f"Las semanas no son los días del mes: los formularios cuentan las "
            f"semanas completas que terminan en {period.label} "
            f"({es_display.day_range(first_monday, period.weeks[-1])}), "
            f"y los bautismos certificados cuentan los días del mes "
            f"({period.window_label}). Por eso nunca comparten una tabla.")
    if cov is not None and cov.thin:
        sentences.append(
            "La cobertura de este período es demasiado delgada para sostener "
            "una comparación: la columna de cambio va en raya, con la razón "
            "en su encabezado.")
    silent = mission.areas_silent
    if silent:
        sentences.append(
            f"{es_display.integer(len(silent))} de "
            f"{es_display.integer(mission.scope.area_count)} áreas no "
            f"informaron ninguna semana completa del período: "
            f"{', '.join(sorted(silent))}. Cuentan en cada denominador por "
            f"área activa, y no aparecen en ninguna suma.")
    sentences.append(
        "Los Indicadores Clave se califican contra la meta de traslado del "
        "liderazgo, sobre las semanas y áreas que informaron; la meta de las "
        "compañerías se imprime como compromiso y no da color. Los bautismos "
        "del formulario no llevan color: la meta de bautismos es la anual.")
    labels = {r.key: r.label for r in mission.key_indicators}
    weights = " · ".join(f"{labels[k]} {w}" for k, w in INDEX_WEIGHTS.items()
                         if k in labels)
    sentences.append(
        "Índice de productividad: lo que produce cada compañería por semana "
        "activa, contra la misión, que es 100; un área que no informó cuenta "
        "como cero. Cada indicador pesa distinto, más cuanto más cerca del "
        f"bautismo: {weights}. Cada uno se topa en 250, para que una cifra "
        "chica no cargue con toda la unidad, y una unidad con menos de 20 "
        "eventos dice «pocas cifras».")
    nightly_flags = [r for r in mission.nightly_metrics if r.grade.flag]
    if nightly_flags:
        names = ", ".join(r.label for r in nightly_flags)
        sentences.append(
            f"Meta nocturna no utilizable: {names}. La cifra es real y la "
            f"meta no da para medirla.")
    sentences.append(
        "El trabajo nocturno se mide contra su meta por noche informada, y "
        "sus filas se califican por su movimiento, no por su distancia a la "
        "meta.")
    sentences.extend(_tableau_sentences(mission))
    for line in sentences:
        flow.append(Paragraph(PP.text(line), st["note_lead"]))
    flow.append(Spacer(0, 8))
    flow.append(Paragraph(PP.text(
        f"Generado por PMG Compass desde la hoja de datos de la misión el "
        f"{es_display.long_date(mission.today)}."), st["note"]))
    return flow


def _tableau_sentences(mission) -> list:
    """What the data note says about the Tableau figures (decisions 32, 34,
    35, 47).

    Where the export reaches, which pages count all ten zones and which only
    the roster's, the names it carries that the roster does not, and what the
    forecasts and the mature funnel rest on.
    """
    block = getattr(mission, "tableau", None)
    if block is None:
        return ["Sin exportación de Tableau: este paquete no tiene bautismos "
                "por zona, ni fechas abiertas, ni embudo maduro."]

    out = [block.export.freshness_label(mission.today) + "."]
    source = block.export.source_label()
    if source:
        out[-1] = out[-1][:-1] + f", cargada por {source}."
    out.append(
        "Toda cifra de Tableau va con su nombre y nunca se suma ni comparte "
        "una tabla con las de los formularios de Compass: los formularios "
        "cubren las 4 zonas del piloto y Tableau las 10. Las fechas abiertas "
        "y el embudo maduro de la misión cuentan las diez zonas; los de cada "
        "zona y distrito, sólo sus áreas del organigrama.")
    out.append(
        "Debajo de la misión, los bautismos son registros de Tableau por "
        "persona (la fecha de confirmación), por área del organigrama: no "
        "existe cifra certificada por zona, y los registros quedan algo por "
        "debajo de la certificada. La parte de 527 de cada zona es la parte "
        "de los bautismos de la misión que tuvo en los últimos doce meses "
        "cerrados.")
    rec = block.reconciliation
    if rec is not None and rec.note:
        out.append(rec.note)
    out.append(
        "Las áreas de Tableau se emparejan con el organigrama por nombre de "
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
        "y el año, de la captura mensual; la semana, los traslados y las "
        "últimas seis semanas, de la captura por período que la "
        "sincronización nocturna llena. Nunca los registros de Tableau por "
        "persona, que quedan por debajo de la certificada, ni el formulario "
        "semanal, que sólo cubre las zonas del piloto.")
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
            if i and i % AREAS_PER_PAGE == 0:
                flow.append(PageBreak())
            elif i:
                flow.append(Spacer(0, 6))
                flow.append(PP.HairRule(color=PP.RULE, space_before=0,
                                        space_after=6))
            if i % AREAS_PER_PAGE == 0:
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
                             total_pages=total, pagination=measured)
                + _body(models, goals, measured)
                + [PageBreak()]
                + print_guide_pages(mission, resolved, units, roster,
                                    total_pages=total, pagination=measured))
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
