"""The annex: the districts' and the areas' pages (PLAN-2026-10-13 step
4.1, D3).

The council packet is what the council reads together — the story, the
resumen, the mission, the zones and their reference pages. The annex is
what is handed out: each district leader takes their own page, and the
areas follow as the council's reference. Two PDFs, built from the same 63
models, so a figure on a district page and the same figure in the packet
cannot disagree.

The area builders live here rather than in `packet.py` (the plan's risk 5:
`packet.py` should not grow past its 3,600 lines). `packet` re-exports them
for the callers that already name them there.
"""

from __future__ import annotations

from dataclasses import replace

from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Spacer

from app.config import es_display
from app.reports import packet as PK
from app.reports import packet_parts as PP
from app.reports import scope as S


# ── An area, which is a companionship ───────────────────────────

AREAS_PER_PAGE = 3


def _area_spark(model, row) -> object:
    """One Key Indicator's last twelve weeks, as a drawing for its own row."""
    values, bounds = PK._spark_of(model, row.key)
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
        goal = (f" de {PK._per_week(r.goal_per_area_week)}"
                if r.goal_per_area_week else "")
        bits.append(f"{words} {PK._per_week(r.per_reporting_area_week)}{goal}")
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
    lines = PK.ki_lines(model, comparable=False)
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
    bits = [f"{r.role} {PK._idx(r.index.value)}" for r in model.ladder[1:]
            if not r.is_self and r.index.value is not None]
    line = (f"Productividad {PK._idx(own.value)} (misión = 100)"
            + (" · pocas cifras" if own.thin else ""))
    return line + (" · " + " · ".join(bits) if bits else "")


# ── The annex as a document (step 4.1, D3) ────────────────────────────────────

class AnnexLayout:
    """Where the annex put each district, and how long it ran — what the
    council packet's run sheet prints. ``units`` is `(scope, (first, last))`
    for every district, in annex page numbers."""

    def __init__(self, total: int = 0, units=()):
        self.total = total
        self.units = tuple(units)


def annex_front(mission, sections, units, roster) -> list:
    """The annex's page 1: its header band, which page each district leader
    takes and how many copies, and its contents. No running head, like the
    council packet's page 1."""
    st = PP.styles()
    period = mission.period
    rows = [r for r in PK.hand_outs(sections, units, roster)
            if r.who.startswith("Líderes de distrito")]
    lead = PK.leadership(roster)
    missing = lead.districts_without_a_leader
    flow = [
        PP.TrackedLabel("Consejo de liderazgo misional", style=PP.SECTION,
                        color=PP.ACCENT, pad_bottom=6.0),
        Paragraph(PP.text(f"Anexo del Consejo · {period.label}"),
                  st["title"]),
        Paragraph(PP.text(
            f"{mission.mission_name} · {period.window_label} · los "
            f"distritos y las áreas"), st["subtitle"]),
        PP.HairRule(color=PP.INK, thickness=1.2, space_before=0,
                    space_after=2),
        Paragraph(PP.text(
            "El paquete del consejo es lo que el consejo lee junto; este "
            "anexo es lo que se reparte. Cada líder de distrito recibe la "
            "página de su distrito, y las áreas quedan como referencia. Las "
            "cifras son las mismas del paquete, del mismo día."),
            st["body"]),
        PP.SectionHead("Qué entregar", "una copia por compañería de liderazgo"),
        PP.table([[r.who.replace("Líderes de distrito · ", ""), r.pages,
                   str(r.copies), r.note] for r in rows],
                 [196, 70, 54, 200],
                 headers=["Distrito", "Páginas", "Copias", "Notas"],
                 align=["l", "r", "r", "l"]),
    ]
    if missing:
        names = ", ".join(sorted(k.split("/")[-1] for k in missing))
        flow.append(Spacer(0, 4))
        flow.append(Paragraph(PP.text(
            f"Sin líder de distrito en el organigrama: {names}. Esa fila pide "
            f"0 copias; decida a mano a quién entregarla."), st["note"]))
    described = PK.describe(sections)
    flow += [PP.SectionHead("En este anexo", "páginas"),
             PP.table([[Paragraph(PP.text(s.title), st["cell"]),
                        Paragraph(PP.text(s.page_label), st["cell_right"])]
                       for s in described if s.key != PK.ANNEX_FRONT],
                      [PP.CONTENT_WIDTH - 90, 90], align=["l", "r"], pad=2.0),
             Spacer(0, 6),
             Paragraph(PP.text(
                 "Imprima a doble cara, vertical, en «Tamaño real». Generado "
                 "por PMG Compass desde la hoja de datos de la misión el "
                 f"{es_display.long_date(mission.today)}."), st["note"])]
    return flow


def _annex_body(models, goals, pagination) -> list:
    """The districts, a page each, then the areas, three to a page — with
    the markers the second pass reads."""
    peers = {m.scope.key: m for m in models}
    flow = []
    opened = False
    for model in models:
        if model.scope.level != S.DISTRICT:
            continue
        flow.append(PageBreak())
        if not opened:
            opened = True
            flow.append(PK.SectionStart(PK.DISTRICTS, pagination))
        flow.append(PK.SectionStart(model.scope.key, pagination))
        flow.extend(PK.unit_pages(model, goals, peers))
    areas = [m for m in models if m.scope.level == S.AREA]
    if areas:
        flow.append(PageBreak())
        flow.append(PK.SectionStart(PK.AREAS, pagination))
        for i, model in enumerate(areas):
            if i and i % AREAS_PER_PAGE == 0:
                flow.append(PageBreak())
            elif i:
                flow.append(Spacer(0, 6))
                flow.append(PP.HairRule(color=PP.RULE, space_before=0,
                                        space_after=6))
            if i % AREAS_PER_PAGE == 0:
                flow.append(PP.SetFurniture(PK.furniture_for(model)))
            flow.append(PK.SectionStart(model.scope.key, pagination))
            flow.append(KeepTogether(area_block(model)))
    return flow


def build_annex_packet(models, roster, goals=None) -> tuple:
    """`(pdf bytes, AnnexLayout)`: the districts and the areas, laid out
    until a pass confirms the page numbers its first page prints."""
    goals = dict(goals or {})
    mission = next((m for m in models if m.scope.level == S.MISSION), None)
    if mission is None:
        raise ValueError("el anexo necesita el modelo de la misión")
    sections = PK.sections_for(models, part=PK.ANNEX)
    keys = [m.scope.key for m in models if m.scope.level == S.DISTRICT]
    given, pdf = PK.Pagination(), b""
    units = []
    for _ in range(PK.MAX_PASSES):
        measured = PK.Pagination()
        resolved = given.resolve(sections) if given.measured else sections
        spans = given.unit_ranges(keys + [PK.AREAS]) if given.measured else {}
        units = [(m.scope, spans[m.scope.key]) for m in models
                 if m.scope.key in spans and m.scope.level == S.DISTRICT]
        flow = ([PK.SectionStart(PK.ANNEX_FRONT, measured)]
                + annex_front(mission, resolved, units, roster)
                + _annex_body(models, goals, measured))
        pdf, measured.total = PK._render(flow)
        if measured.same_as(given):
            break
        given = measured
    spans = given.unit_ranges(keys + [PK.AREAS])
    units = [(m.scope, spans[m.scope.key]) for m in models
             if m.scope.key in spans and m.scope.level == S.DISTRICT]
    return pdf, AnnexLayout(total=given.total, units=units)
