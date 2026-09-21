"""The printed page: its furniture, its type scale, and five vector charts.

The council packet is one PDF drawn with ReportLab and nothing else
(decision 29). Everything here is a shape or a size — no numbers are computed
in this module and none of it knows what a Key Indicator is. `packet.py` reads
a `ReportModel` and asks for these pieces; this file decides what they look
like.

**Three things are settled here and inherited by every page below.**

*The paper.* Letter, portrait, because the mission prints on Letter and
decision 25's acceptance is that a page survives "Actual size" without the
footer clipping. The margins leave a band at the top for the running head and
one at the bottom for the footer, and no flowable is ever allowed into either.

*The type.* Helvetica, Helvetica-Bold and Helvetica-Oblique — three of the
base-14 fonts, which every PDF reader already has. **No font file ships with
this repo**, for the same reason decision 29 rules out a headless browser: an
embedded TTF is one more thing that can fail on Streamlit Cloud and it would
buy nothing a council packet needs.

*The colour.* `config/theme.py`, always, through its PRINT_* tokens — the same
three states and the same violet leadership mark the screen draws, re-valued
for white paper and measured there. The Phase F lesson was that a second
palette is how two greens end up meaning "good" on one page; the answer is not
to avoid print colours but to keep them in the one home the screen's come from.

**Why the arrows are drawn and not typed.** Measured 2026-09-21: ReportLab
silently font-switches a character the base-14 encoding cannot reach. A "↑" in
a Helvetica string is quietly emitted in *Symbol*, a "▲" in *ZapfDingbats*, so
a change chip would print in a different typeface from the number beside it and
nothing in the build would say so. Every direction in this packet is therefore
a vector triangle (`change_mark`), and every string goes through `text()`,
which normalises the handful of characters the app's Spanish vocabulary carries
and drops anything else outside the printable set. `tests/test_packet_parts.py`
asserts the real packet's strings pass through it unchanged, so a genuine
occurrence fails the build instead of printing in the wrong font.

Pure, like the rest of `app/reports`: no Streamlit, no sheet reads, no model
import. See PLAN-2026-09-21-informes.md §4 step P1.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from reportlab.graphics.shapes import (Circle, Drawing, Group, Line, Polygon,
                                       PolyLine, Rect, String)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (Flowable, Paragraph, Spacer, Table,
                                TableStyle)

from app.config import es_display, theme

# ── The paper ─────────────────────────────────────────────────────────────────

PAGE_SIZE = letter                       # 612 x 792 pt
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE

#: Side margins. 46pt is a hair under two thirds of an inch — wide enough that
#: a duplex printer's drift cannot eat a table's last column, narrow enough
#: that the 45-area ranking fits without shrinking its type.
MARGIN_X = 46.0

#: The top band belongs to the running head and the bottom band to the footer.
#: A flowable never enters either, which is what makes "Actual size" safe.
MARGIN_TOP = 58.0
MARGIN_BOTTOM = 46.0

CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X          # 520
CONTENT_HEIGHT = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

#: Where the furniture itself sits, measured from the page edges.
HEAD_BASELINE = PAGE_HEIGHT - 36.0
HEAD_RULE_Y = PAGE_HEIGHT - 44.0
FOOT_RULE_Y = 36.0
FOOT_BASELINE = 26.0


# ── The type ──────────────────────────────────────────────────────────────────

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"


@dataclass(frozen=True)
class Type:
    """One step of the scale: a size and the leading that goes with it."""

    size: float
    leading: float
    font: str = FONT
    #: Letter-spacing, in points. Only the uppercase steps carry any — set
    #: solid, a tracked lowercase line reads as a mistake.
    track: float = 0.0


#: Nine steps for the body, and two more the cover alone uses. Every string in
#: the packet is one of these; a size written inline is how a document ends up
#: with eleven sizes and no hierarchy.
TITLE = Type(21, 24, FONT_BOLD)
SUBTITLE = Type(8.8, 12)
SECTION = Type(8, 11, FONT_BOLD, track=0.9)        # uppercase
SECTION_NOTE = Type(6.8, 9.5)
BODY = Type(8.5, 11.5)
CELL = Type(7.5, 9.8)
CELL_HEAD = Type(6.2, 8.5, FONT_BOLD, track=0.7)   # uppercase
NOTE = Type(6.4, 8.6)
TILE_VALUE = Type(18, 20, FONT_BOLD)
TILE_LABEL = Type(6.2, 8.5, FONT_BOLD, track=0.7)  # uppercase
FURNITURE = Type(6.4, 8.5, FONT, track=0.6)

#: The cover's own two. A cover is the one page in a document that is allowed
#: a size nothing else uses — it has one job and no neighbours to sit beside.
COVER_TITLE = Type(32, 35, FONT_BOLD)
COVER_LEAD = Type(11, 15.5)


# ── The colour ────────────────────────────────────────────────────────────────

def pc(hex_color: str) -> colors.Color:
    """One of theme.py's hex strings as a ReportLab colour.

    The only way a colour enters this module. A `HexColor` written inline here
    would be a value nobody can re-theme and the start of the second palette
    the module docstring exists to prevent.
    """
    return colors.HexColor(hex_color)


INK = pc(theme.PRINT_INK)
INK_2 = pc(theme.PRINT_INK_2)
INK_3 = pc(theme.PRINT_INK_3)
RULE = pc(theme.PRINT_RULE)
RULE_SOFT = pc(theme.PRINT_RULE_SOFT)
TINT = pc(theme.PRINT_TINT)
PAPER = pc(theme.PRINT_PAPER)
MARK = pc(theme.PRINT_MARK)
ACCENT = pc(theme.PRINT_ACCENT)
NAVY = pc(theme.MISSION_NAVY)

#: The three grading states, on paper. Keyed by decision 10's vocabulary.
STATUS = {k: pc(v) for k, v in theme.PRINT_STATUS.items()}

#: Identity, not magnitude — the same eight the screen assigns in the same
#: order, so a zone keeps its colour across the two surfaces (theme.py measured
#: all eight above 3:1 on white, so they carry to paper unchanged).
SERIES = [pc(c) for c in theme.SERIES_COLORS]

#: A row, bar or dot with nothing to grade. Not a fourth state — the absence of
#: one, which is why it is grey and not a hue.
UNGRADED = INK_3


def status_color(status: str | None) -> colors.Color:
    return STATUS.get(status or "", UNGRADED)


#: The words that ride beside the colour, so a reader who cannot separate the
#: hues — or a packet photocopied in black and white, which is how half of
#: these get read — loses nothing. Decision 10's three states in Spanish.
STATUS_WORD = {"good": "al ritmo", "warn": "atrasado", "bad": "muy atrasado"}


# ── Text that is safe to print ────────────────────────────────────────────────

#: Characters the app's own vocabulary uses that the base-14 encoding cannot
#: reach, and what each becomes on paper. Left alone, ReportLab emits them in
#: Symbol or ZapfDingbats without a word of warning — measured 2026-09-21.
#: The arrows have no substitute here on purpose: a direction is a triangle
#: (`change_mark`), drawn, so there is nothing to substitute.
_SUBSTITUTIONS = {
    "→": "-",           # a range or a flow, set with a hyphen
    "−": "-",           # true minus
    "‑": "-",           # non-breaking hyphen
    # The three spaces are written as codepoints because set as themselves
    # they would be three identical-looking keys in one dict.
    chr(0x00A0): " ",     # no-break space
    chr(0x2009): " ",     # thin space
    chr(0x202F): " ",     # narrow no-break space
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
}


def text(value) -> str:
    """A string reduced to what Helvetica can print without switching fonts.

    The substitutions above first, then anything still outside the printable
    set is stripped of its accents if that makes it printable and dropped if it
    does not. Dropping is the last resort and it is silent by design at
    runtime — a companionship whose name arrives with an unexpected character
    should not break the president's download — but `test_packet_parts.py`
    runs every string of the real packet through here and fails if any of them
    changes, so a real occurrence is caught at build time rather than printed
    in ZapfDingbats.
    """
    s = "" if value is None else str(value)
    for bad, good in _SUBSTITUTIONS.items():
        s = s.replace(bad, good)
    try:
        s.encode("cp1252")
        return s
    except UnicodeEncodeError:
        pass
    out = []
    for ch in s:
        try:
            ch.encode("cp1252")
            out.append(ch)
            continue
        except UnicodeEncodeError:
            pass
        folded = "".join(c for c in unicodedata.normalize("NFKD", ch)
                         if not unicodedata.combining(c))
        try:
            folded.encode("cp1252")
            out.append(folded)
        except UnicodeEncodeError:
            continue
    return "".join(out)


def is_printable(value) -> bool:
    """Whether `text()` would leave this string alone. The test's whole job."""
    s = "" if value is None else str(value)
    return text(s) == s


def width_of(s: str, style: Type) -> float:
    """How wide a string sets, tracking included."""
    s = text(s)
    return stringWidth(s, style.font, style.size) + style.track * max(0, len(s) - 1)


def fit(s: str, style: Type, limit: float) -> str:
    """`s`, shortened with an ellipsis until it sets inside `limit`.

    Measured rather than counted: "Purén y Los Sauces" is the widest name on
    CCSM's roster at 67pt in CELL, and a character count would have trimmed
    "Los Angeles Norte" — narrower by 5pt — at the same place.
    """
    s = text(s)
    if width_of(s, style) <= limit:
        return s
    ell = "..."
    while s and width_of(s + ell, style) > limit:
        s = s[:-1]
    return (s.rstrip() + ell) if s else ""


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _string(x: float, y: float, s: str, style: Type, color: colors.Color,
            *, anchor: str = "start", upper: bool = False) -> String:
    """One untracked run of text inside a Drawing, in a named type step.

    `String` has no character spacing, so a TRACKED run inside a Drawing goes
    through `_tracked` and is set glyph by glyph instead.
    """
    s = text(s).upper() if upper else text(s)
    return String(x, y, s, fontName=style.font, fontSize=style.size,
                  fillColor=color, textAnchor=anchor)


def _tracked(group: Group, x: float, y: float, s: str, style: Type,
             color: colors.Color, *, upper: bool = False,
             anchor: str = "start") -> float:
    """A letter-spaced run, drawn glyph by glyph. Returns the width it took.

    The uppercasing happens before the measuring, so an ``anchor`` of "end"
    lands on the string that is actually set rather than on the one passed in.
    """
    s = text(s).upper() if upper else text(s)
    if anchor == "end":
        x -= width_of(s, style)
    elif anchor == "middle":
        x -= width_of(s, style) / 2
    cursor = x
    for ch in s:
        group.add(String(cursor, y, ch, fontName=style.font,
                         fontSize=style.size, fillColor=color))
        cursor += stringWidth(ch, style.font, style.size) + style.track
    return max(0.0, cursor - x - style.track)


def draw_tracked(canvas, x: float, y: float, s: str, style: Type,
                 color: colors.Color, *, anchor: str = "start",
                 upper: bool = False) -> float:
    """A letter-spaced run drawn straight onto a canvas. Returns its width.

    Tracking lives on a PDF text object, not on the canvas — `canvas.drawString`
    has no character spacing at all and `canvas.setCharSpace` does not exist.
    Right alignment is done by measuring, since a text object only sets from a
    point.

    **The character spacing is always emitted, including when it is zero.** In
    PDF, `Tc` is text state and text state survives `ET`: a tracked run leaves
    its spacing behind for whatever is drawn next. Left conditional, the section
    note inherited its label's 0.9pt and set 30pt wider than it measured, which
    put it over the right margin — right-aligned text that overflows to the
    RIGHT is the confusing half of that bug, and it took a rendered page to see.
    """
    s = text(s).upper() if upper else text(s)
    w = width_of(s, style)
    if anchor == "end":
        x -= w
    elif anchor == "middle":
        x -= w / 2
    obj = canvas.beginText(x, y)
    obj.setFont(style.font, style.size)
    obj.setFillColor(color)
    obj.setCharSpace(style.track)
    obj.textOut(s)
    canvas.drawText(obj)
    return w


def change_mark(x: float, y: float, direction: int, *, size: float = 4.4,
                color: colors.Color | None = None) -> Polygon | None:
    """The triangle that says which way a number moved — never a typed arrow.

    `direction` is 1, -1 or 0; a 0 draws nothing and the row's "sin cambio" is
    the statement. `x`,`y` is the triangle's bottom-left corner, so it sits on
    a text baseline without any nudging.
    """
    if not direction:
        return None
    half = size / 2
    if direction > 0:
        pts = [x, y, x + size, y, x + half, y + size * 0.85]
        fill = color or STATUS["good"]
    else:
        pts = [x, y + size * 0.85, x + size, y + size * 0.85, x + half, y]
        fill = color or STATUS["bad"]
    return Polygon(points=pts, fillColor=fill, strokeColor=None, strokeWidth=0)


def dot(cx: float, cy: float, status: str | None, *, r: float = 2.6) -> Circle:
    """The status dot that heads a ranked row."""
    return Circle(cx, cy, r, fillColor=status_color(status), strokeColor=None,
                  strokeWidth=0)


# ── Page furniture ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Furniture:
    """What the running head and footer say on a stretch of pages.

    ``eyebrow`` is the unit, uppercase, left of the head — "ZONA · SAN PEDRO".
    ``period`` is the window, right of it. ``trail`` is the unit's ancestors,
    printed in the footer so a loose page handed to a district leader still
    says which zone it belongs to (`Scope.trail`).
    """

    eyebrow: str = ""
    period: str = ""
    trail: str = ""
    mission: str = ""

    def draw(self, canvas, page_number: int) -> None:
        plain = Type(FURNITURE.size, FURNITURE.leading, FURNITURE.font)
        canvas.saveState()
        draw_tracked(canvas, MARGIN_X, HEAD_BASELINE, self.eyebrow, FURNITURE,
                     INK_3, upper=True)
        draw_tracked(canvas, PAGE_WIDTH - MARGIN_X, HEAD_BASELINE, self.period,
                     plain, INK_3, anchor="end")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_X, HEAD_RULE_Y, PAGE_WIDTH - MARGIN_X, HEAD_RULE_Y)

        canvas.line(MARGIN_X, FOOT_RULE_Y, PAGE_WIDTH - MARGIN_X, FOOT_RULE_Y)
        foot = " · ".join(p for p in ("PMG Compass", self.mission, self.trail) if p)
        draw_tracked(canvas, MARGIN_X, FOOT_BASELINE, foot, plain, INK_3)
        draw_tracked(canvas, PAGE_WIDTH - MARGIN_X, FOOT_BASELINE,
                     f"Página {page_number}", plain, INK_3, anchor="end")
        canvas.restoreState()


#: Where the current furniture is parked between the flowable that sets it and
#: the page callback that draws it. On the canvas rather than in a module
#: global so two packets built in one process cannot cross.
_FURNITURE_ATTR = "_pmg_furniture"


class SetFurniture(Flowable):
    """A zero-height marker: from here on, the pages say this.

    Placed at the top of a unit's first page. The furniture is drawn by
    `draw_furniture` on **onPageEnd**, not onPage — a page's flowables have all
    been drawn by then, so a marker at the top of a section reaches the head of
    the very page it opens. On onPage it would land a page late, which is the
    kind of bug that only shows up at the one place a section changes.
    """

    def __init__(self, furniture: Furniture):
        super().__init__()
        self.furniture = furniture
        self.width = 0
        self.height = 0

    def wrap(self, availWidth, availHeight):
        return (0, 0)

    def draw(self):
        setattr(self.canv, _FURNITURE_ATTR, self.furniture)


def draw_furniture(canvas, doc) -> None:
    """The `onPageEnd` callback. Draws whatever the last marker asked for."""
    furniture = getattr(canvas, _FURNITURE_ATTR, None)
    if furniture is not None:
        furniture.draw(canvas, doc.page)


# ── Flowables ─────────────────────────────────────────────────────────────────

class SectionHead(Flowable):
    """An uppercase tracked label at the left, its qualifier at the right.

    Provo's packet runs the qualifier on immediately after the label; this
    right-aligns it instead, so a long one ("weakest first · goal = weekly
    target × complete weeks") can never collide with the label or wrap into
    the rule below it. It is truncated rather than wrapped for the same reason.
    """

    def __init__(self, label: str, note: str = "", *, width: float | None = None,
                 space_before: float = 12.0, space_after: float = 5.0,
                 rule: bool = True):
        super().__init__()
        self.label = label
        self.note = note
        self.width = width if width is not None else CONTENT_WIDTH
        self.space_before = space_before
        self.space_after = space_after
        self.rule = rule
        self.height = SECTION.leading + space_before + space_after

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return (availWidth, self.height)

    def draw(self):
        c = self.canv
        y = self.space_after + 2.0
        c.saveState()
        used = draw_tracked(c, 0, y, self.label, SECTION, INK, upper=True)
        if self.note:
            room = self.width - used - 14
            if room > 24:
                draw_tracked(c, self.width, y,
                             fit(self.note, SECTION_NOTE, room), SECTION_NOTE,
                             INK_3, anchor="end")
        if self.rule:
            c.setStrokeColor(RULE)
            c.setLineWidth(0.5)
            c.line(0, y - 3.5, self.width, y - 3.5)
        c.restoreState()


class HairRule(Flowable):
    """A rule the width of the frame, in one of the two rule greys."""

    def __init__(self, *, color: colors.Color | None = None,
                 thickness: float = 0.5, space_before: float = 4.0,
                 space_after: float = 4.0, width: float | None = None):
        super().__init__()
        self.color = color or RULE
        self.thickness = thickness
        self.space_before = space_before
        self.space_after = space_after
        self.width = width if width is not None else CONTENT_WIDTH
        self.height = thickness + space_before + space_after

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return (availWidth, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(self.color)
        c.setLineWidth(self.thickness)
        c.line(0, self.space_after, self.width, self.space_after)
        c.restoreState()


def styles() -> dict[str, ParagraphStyle]:
    """The paragraph styles, one per step of the scale that needs wrapping.

    A `Paragraph` is used wherever text can run long — a note, a sentence of
    explanation, a name in a table cell. Everything of a known length is drawn
    into a `Drawing` instead, where it can be positioned to the point.
    """
    def make(name, t: Type, color, **kw):
        return ParagraphStyle(name, fontName=t.font, fontSize=t.size,
                              leading=t.leading, textColor=color, **kw)

    return {
        "title": make("title", TITLE, INK, spaceAfter=2),
        "subtitle": make("subtitle", SUBTITLE, INK_3, spaceAfter=6),
        "cover_title": make("cover_title", COVER_TITLE, INK, spaceAfter=10),
        "cover_lead": make("cover_lead", COVER_LEAD, INK_2, spaceAfter=0),
        "cell_center": make("cell_center", CELL, INK_2, alignment=1),
        "body": make("body", BODY, INK_2, spaceAfter=4),
        "cell": make("cell", CELL, INK_2),
        "cell_bold": make("cell_bold", Type(CELL.size, CELL.leading, FONT_BOLD),
                          INK),
        "cell_right": make("cell_right", CELL, INK_2, alignment=2),
        "note": make("note", NOTE, INK_3, spaceAfter=3),
        "note_lead": make("note_lead", NOTE, INK_2, spaceAfter=3),
    }


# ── 1 · A bar against its goal, with the leadership mark ──────────────────────

def bar_vs_goal(width: float, *, pct: float | None, status: str | None = None,
                mark_pct: float | None = None, height: float = 7.0,
                track_color: colors.Color | None = None,
                fill: colors.Color | None = None) -> Drawing:
    """The packet's twin of the KPI card's goal bar (decision 11).

    The fill is the work as a percentage of the companionships' own meta and
    takes the grade's colour; the violet rule is leadership's transfer goal on
    the same scale (`mark_pct`), and it is drawn taller than the track so it
    reads as a reference laid across the bar rather than as part of it.

    A ``mark_pct`` past 100 keeps its rule on the track's last point and adds
    an arrowhead just outside it, so a goal beyond the bar's own scale reads as
    beyond rather than as met.

    ``fill`` overrides the grade's colour for a bar that is a MAGNITUDE rather
    than a grade — the nightly rows, whose colour lives in their movement
    (decision 31). It draws in the one magnitude blue, not in the ungraded
    grey: the reading exists, it is simply not being judged here.

    Over 100% the fill stops at the end of the track and the figure beside it
    carries the overshoot — a bar that runs past its own track would have to
    rescale every other bar on the page to stay honest, and then nothing is
    comparable. A `pct` of None draws the empty track: no reading, not a zero.
    """
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=track_color or RULE_SOFT,
               strokeColor=None, strokeWidth=0, rx=1.5, ry=1.5))
    if pct is not None and pct > 0:
        filled = max(0.0, min(100.0, float(pct))) / 100.0 * width
        if filled > 0:
            d.add(Rect(0, 0, filled, height,
                       fillColor=fill if fill is not None else status_color(status),
                       strokeColor=None, strokeWidth=0, rx=1.5, ry=1.5))
    if mark_pct is not None:
        value = float(mark_pct)
        x = min(max(0.0, min(100.0, value)) / 100.0 * width, width - 1.2)
        d.add(Rect(x, -1.6, 1.2, height + 3.2, fillColor=MARK,
                   strokeColor=None, strokeWidth=0))
        if value > 100.0:
            # A mark past the end of the track would be clamped onto the edge,
            # where four different leadership goals all read as "exactly at the
            # line". The arrowhead says the goal is beyond it — which on CCSM
            # today is the common case, because leadership's transfer goal
            # routinely asks for more than the companionships promised.
            d.add(Polygon(points=[width + 1.5, -1.6, width + 1.5, height + 1.6,
                                  width + 5.0, height / 2],
                          fillColor=MARK, strokeColor=None, strokeWidth=0))
    return d


# ── 2 · A sparkline, with the transfer boundaries on it ───────────────────────

def sparkline(width: float, height: float, values,
              *, boundaries=(), color: colors.Color | None = None,
              last_color: colors.Color | None = None) -> Drawing:
    """A metric's complete weeks, as a line. Direction, not value.

    ``values`` may hold None for a week nothing was filed, and the line
    **breaks** there rather than joining across it. The screen's
    `sparkline_svg` drops the gaps and draws through them, which is the right
    call for a 96px card; on a printed page a straight run through a silent
    week is a claim that the week happened, and this packet's whole argument is
    that a silent week is news.

    ``boundaries`` are fractions of the width (0..1) where a transfer began
    (decision 9) — a dashed vertical rule and nothing else. The label belongs
    to whatever draws the axis, if anything does; a six-point spark has no room
    for one.
    """
    d = Drawing(width, height)
    vals = list(values or [])
    nums = [v for v in vals if v is not None]
    for frac in boundaries or ():
        x = max(0.0, min(1.0, float(frac))) * width
        d.add(Line(x, 0, x, height, strokeColor=RULE,
                   strokeWidth=0.5, strokeDashArray=[1.5, 1.5]))
    if len(nums) < 2:
        return d
    lo, hi = min(nums), max(nums)
    span = (hi - lo) or 1.0
    pad = 1.5
    n = len(vals)
    xs = [pad + (width - 2 * pad) * i / (n - 1) for i in range(n)]

    def y_of(v):
        if hi == lo:
            return height / 2
        return pad + (height - 2 * pad) * (v - lo) / span

    run, last_pt = [], None
    line_color = color or SERIES[0]
    for x, v in zip(xs, vals):
        if v is None:
            if len(run) >= 4:
                d.add(PolyLine(points=list(run), strokeColor=line_color,
                               strokeWidth=1.1, strokeLineJoin=1))
            run = []
            continue
        y = y_of(float(v))
        run.extend([x, y])
        last_pt = (x, y)
    if len(run) >= 4:
        d.add(PolyLine(points=list(run), strokeColor=line_color,
                       strokeWidth=1.1, strokeLineJoin=1))
    if last_pt:
        d.add(Circle(last_pt[0], last_pt[1], 1.7,
                     fillColor=last_color or line_color, strokeColor=None,
                     strokeWidth=0))
    return d


# ── 3 · Stage bars: where people are lost ─────────────────────────────────────

STAGE_ROW_HEIGHT = 15.0
STAGE_CONV_HEIGHT = 9.0


def _widest_drop(values) -> int | None:
    """Index of the step that loses the most PEOPLE — the same rule, and the
    same reasoning, as `components/charts._widest_drop`. The largest absolute
    fall, never the lowest conversion rate: a 4% step that costs 65 people is
    not the pipeline's problem when an 88% step costs 2,378.
    """
    best, best_i = 0.0, None
    for i in range(1, len(values)):
        fall = values[i - 1] - values[i]
        if fall > best:
            best, best_i = fall, i
    return best_i


def stage_bars(width: float, stages, *, value_fmt=None,
               highlight_worst: bool = True,
               label_share: float = 0.36) -> Drawing:
    """The teaching pipeline: one bar per stage, the step's conversion between.

    Single hue, because these are five sizes of one thing. The step that loses
    the most people is named and turns amber — a "look here", not a grade,
    which is why it is amber and says so rather than red and silent.

    A later stage larger than an earlier one leaves its conversion off, as the
    screen's does: people reach a milestone during the window whose earlier
    milestone fell before it, so a funnel can legitimately widen and a
    percentage over 100 there would be arithmetic about two different cohorts.
    """
    fmt = value_fmt or es_display.integer
    rows = [(str(lbl), 0.0 if v is None else float(v)) for lbl, v in stages]
    n = len(rows)
    height = max(1.0, n * STAGE_ROW_HEIGHT + max(0, n - 1) * STAGE_CONV_HEIGHT)
    d = Drawing(width, height)
    if not rows:
        return d
    full = max([v for _, v in rows] + [0.0]) or 1.0
    worst = _widest_drop([v for _, v in rows]) if highlight_worst else None

    label_w = width * label_share
    value_w = 42.0
    track_x = label_w + 8
    track_w = max(10.0, width - label_w - value_w - 16)

    y = height
    prev = None
    for i, (lbl, v) in enumerate(rows):
        if prev is not None:
            y -= STAGE_CONV_HEIGHT
            worst_here = (i == worst)
            conv = (f"{round(v / prev * 100)}%" if prev > 0 and v <= prev
                    else "")
            if conv:
                col = STATUS["warn"] if worst_here else INK_3
                tri = change_mark(track_x, y + 1.5, -1, size=3.6, color=col)
                if tri is not None:
                    d.add(tri)
                note = f"{conv} del anterior"
                if worst_here:
                    note += " · la mayor caída"
                d.add(_string(track_x + 6, y + 1.5, note, NOTE, col))
        y -= STAGE_ROW_HEIGHT
        bar_y = y + 3
        bar_h = 9.0
        d.add(_string(0, bar_y + 1.5, fit(lbl, CELL, label_w), CELL, INK_2))
        d.add(Rect(track_x, bar_y, track_w, bar_h, fillColor=RULE_SOFT,
                   strokeColor=None, strokeWidth=0, rx=1.5, ry=1.5))
        filled = max(0.0, min(1.0, v / full)) * track_w
        if filled > 0:
            d.add(Rect(track_x, bar_y, filled, bar_h, fillColor=SERIES[0],
                       strokeColor=None, strokeWidth=0, rx=1.5, ry=1.5))
        d.add(_string(width, bar_y + 1.5, fmt(v), CELL, INK, anchor="end"))
        prev = v
    return d


# ── 4 · One stacked bar and its legend: a mix ─────────────────────────────────

SHARE_BAR_HEIGHT = 13.0
SHARE_LEGEND_HEIGHT = 10.0


def share_bar(width: float, parts, *, value_fmt=None,
              min_label_share: float = 9.0, legend_columns: int = 3) -> Drawing:
    """A 100% stacked bar with its legend under it — never a donut.

    Hues are SERIES in order: identity, not magnitude. A segment narrower than
    ``min_label_share`` keeps its colour and its legend row and drops the
    percentage printed inside it, where it would not fit. On paper the legend
    wraps into fixed columns rather than flowing, so two packets of the same
    section always break in the same place.
    """
    fmt = value_fmt or es_display.integer
    rows = [(str(lbl), max(0.0, float(v or 0))) for lbl, v in parts]
    total = sum(v for _, v in rows)
    legend_rows = (len(rows) + legend_columns - 1) // legend_columns if rows else 0
    height = SHARE_BAR_HEIGHT + 4 + legend_rows * SHARE_LEGEND_HEIGHT
    d = Drawing(width, height)
    if not rows or total <= 0:
        return d
    bar_y = height - SHARE_BAR_HEIGHT
    x = 0.0
    for i, (lbl, v) in enumerate(rows):
        share = v / total * 100
        seg = width * share / 100
        hue = SERIES[i % len(SERIES)]
        d.add(Rect(x, bar_y, seg, SHARE_BAR_HEIGHT, fillColor=hue,
                   strokeColor=PAPER, strokeWidth=0.6))
        if share >= min_label_share:
            d.add(_string(x + seg / 2, bar_y + 4, f"{round(share)}%",
                          Type(6.4, 8.5, FONT_BOLD), PAPER, anchor="middle"))
        x += seg
    col_w = width / legend_columns
    for i, (lbl, v) in enumerate(rows):
        row, col = divmod(i, legend_columns)
        lx = col * col_w
        ly = bar_y - 4 - (row + 1) * SHARE_LEGEND_HEIGHT + 3
        d.add(Rect(lx, ly, 5, 5, fillColor=SERIES[i % len(SERIES)],
                   strokeColor=None, strokeWidth=0))
        share = v / total * 100
        tail = f"  {fmt(v)} · {round(share)}%"
        room = col_w - 10 - width_of(tail, NOTE)
        d.add(_string(lx + 8, ly, fit(lbl, NOTE, max(20.0, room)), NOTE, INK_2))
        d.add(_string(lx + 8 + width_of(fit(lbl, NOTE, max(20.0, room)), NOTE),
                      ly, tail, NOTE, INK_3))
    return d


# ── 5 · A ranked row ──────────────────────────────────────────────────────────

RANK_ROW_HEIGHT = 17.0
RANK_HEAD_HEIGHT = 12.0


@dataclass(frozen=True)
class RankedSpec:
    """The column geometry a ranked list and its header both draw against.

    One spec per table, handed to every row, so nothing can drift a point out
    of line. ``cells`` are the small measures between the name and the
    attainment — the screen's `ranked_list(columns=...)` strip, which at 375px
    wraps onto its own line and here simply has the room.
    """

    width: float
    cells: tuple[str, ...] = ()
    rank_width: float = 14.0
    dot_width: float = 10.0
    value_width: float = 64.0
    bar_width: float = 46.0
    cell_width: float = 44.0
    sub: bool = True

    @property
    def name_width(self) -> float:
        used = (self.rank_width + self.dot_width + self.value_width
                + self.bar_width + len(self.cells) * self.cell_width)
        return max(50.0, self.width - used - 8)

    @property
    def name_x(self) -> float:
        return self.rank_width + self.dot_width

    @property
    def cells_x(self) -> float:
        return self.name_x + self.name_width + 8

    @property
    def bar_x(self) -> float:
        return self.cells_x + len(self.cells) * self.cell_width

    @property
    def value_x(self) -> float:
        return self.width


def ranked_row(spec: RankedSpec, *, rank=None, name: str = "", sub: str = "",
               status: str | None = None, cells=(), value: str = "",
               bar: float | None = None, bar_max: float | None = None,
               header: bool = False, rule: bool = True) -> Drawing:
    """rank · dot · name · sub-line · measures · bar · value, as one Drawing.

    The printed twin of `components/charts.ranked_list`, row for row, so "who
    needs help" is the same shape on the screen and on the page. Names are
    truncated to the spec's column rather than wrapped: measured on the live
    roster the widest of the 45 sets at 67pt against a column of about 150, so
    nothing truncates today and the rule is there for the name that eventually
    does.

    ``header=True`` draws the column labels instead of a row.
    """
    height = RANK_HEAD_HEIGHT if header else RANK_ROW_HEIGHT
    d = Drawing(spec.width, height)
    if header:
        y = 3.0
        g = Group()
        for i, label in enumerate(spec.cells):
            # Right-aligned over the numbers beneath, not left-aligned at the
            # column's start: a header sitting a few points left of its own
            # figures reads as a header for the column before it.
            right = spec.cells_x + i * spec.cell_width + spec.cell_width - 8
            _tracked(g, right, y, fit(label.upper(), CELL_HEAD,
                                      spec.cell_width - 8),
                     CELL_HEAD, INK_3, anchor="end")
        _tracked(g, spec.name_x, y, name or "unidad", CELL_HEAD, INK_3,
                 upper=True)
        d.add(g)
        if rule:
            d.add(Line(0, 0, spec.width, 0, strokeColor=RULE, strokeWidth=0.5))
        return d

    # A row with a sub-line sets its name higher so the sub still lands INSIDE
    # the row's declared height. At 6.5 the sub's baseline came out at -0.7 and
    # printed over whatever the page put underneath — a Drawing does not clip,
    # so nothing complains and the last row of every table bleeds.
    base = 8.5 if sub else 5.0
    if rank is not None:
        d.add(_string(spec.rank_width - 5, base, str(rank), NOTE, INK_3,
                      anchor="end"))
    d.add(dot(spec.rank_width + 4, base + 2.2, status))
    d.add(_string(spec.name_x, base, fit(name, CELL, spec.name_width), CELL,
                  INK))
    if sub:
        d.add(_string(spec.name_x, base - 7.5, fit(sub, NOTE, spec.name_width),
                      NOTE, INK_3))
    for i, cell in enumerate(cells):
        d.add(_string(spec.cells_x + i * spec.cell_width + spec.cell_width - 8,
                      base, str(cell), CELL, INK_2, anchor="end"))
    if bar is not None:
        full = bar_max or bar or 1.0
        w = max(0.0, min(1.0, float(bar) / float(full or 1.0))) * (spec.bar_width - 8)
        d.add(Rect(spec.bar_x, base + 0.5, spec.bar_width - 8, 5.0,
                   fillColor=RULE_SOFT, strokeColor=None, strokeWidth=0,
                   rx=1, ry=1))
        if w > 0:
            d.add(Rect(spec.bar_x, base + 0.5, w, 5.0,
                       fillColor=status_color(status), strokeColor=None,
                       strokeWidth=0, rx=1, ry=1))
    if value:
        d.add(_string(spec.value_x, base, value, CELL, INK, anchor="end"))
    if rule:
        d.add(Line(0, 0, spec.width, 0, strokeColor=RULE_SOFT, strokeWidth=0.5))
    return d


# ── Labels, tables and the front matter ───────────────────────────────────────

class TrackedLabel(Flowable):
    """An uppercase letter-spaced label, as a flowable.

    A `Paragraph` cannot track — ReportLab's `ParagraphStyle` has no character
    spacing at all — so every uppercase label that has to live inside a table
    cell or a flowable stream comes through here instead.
    """

    def __init__(self, label: str, *, style: Type = CELL_HEAD,
                 color: colors.Color | None = None, align: str = "start",
                 width: float | None = None, pad_bottom: float = 2.0):
        super().__init__()
        self.label = label
        self.style = style
        self.color = color if color is not None else INK_3
        self.align = align
        self.width = width if width is not None else CONTENT_WIDTH
        self.pad_bottom = pad_bottom
        self.height = style.leading + pad_bottom

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return (availWidth, self.height)

    def draw(self):
        x = {"start": 0.0, "middle": self.width / 2, "end": self.width}[self.align]
        draw_tracked(self.canv, x, self.pad_bottom + 1.5, self.label,
                     self.style, self.color, anchor=self.align, upper=True)


def table(rows, widths, *, headers=None, align=None, head_band: bool = True,
          row_rules: bool = True, pad: float = 4.0, para=None) -> Table:
    """A print table: a tinted header band, hairlines between rows, nothing else.

    No vertical rules and no outer box. A ruled grid is how a page of figures
    stops being readable — the columns are already aligned, and a line between
    every one of them is ink doing no work.

    A cell may be a string, a `Drawing` (one of the five primitives) or any
    flowable. Strings become `Paragraph`s so a long name wraps inside its
    column instead of colliding with the next; ``para`` names the style, and
    ``align`` is a per-column "l"/"r"/"c".
    """
    st = styles()
    aligns = list(align or ["l"] * len(widths))
    style_for = {"l": para or "cell", "r": "cell_right", "c": "cell_center"}

    def cell(value, col):
        if isinstance(value, (list, tuple)):
            # Platypus stacks a list of flowables inside one cell. Left to the
            # coercion below, a two-line name cell printed its own repr — three
            # hundred characters of ParaFrag across the page, which is what a
            # 22-row nightly table looked like before this line existed.
            return [cell(v, col) for v in value]
        if isinstance(value, (Drawing, Flowable)):
            return value
        return Paragraph(text(value), st[style_for[aligns[col]]])

    body = [[cell(v, i) for i, v in enumerate(row)] for row in rows]
    if headers is not None:
        head = [TrackedLabel(h, align={"l": "start", "r": "end",
                                       "c": "middle"}[aligns[i]],
                             width=widths[i] - 2 * pad, pad_bottom=0.0)
                for i, h in enumerate(headers)]
        body = [head] + body

    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), pad),
        ("RIGHTPADDING", (0, 0), (-1, -1), pad),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
    ]
    first_body = 0
    if headers is not None:
        first_body = 1
        if head_band:
            cmds.append(("BACKGROUND", (0, 0), (-1, 0), TINT))
        cmds.append(("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE))
    if row_rules and len(body) > first_body + 1:
        cmds.append(("LINEBELOW", (0, first_body), (-1, -2), 0.5, RULE_SOFT))
    return Table(body, colWidths=list(widths), style=TableStyle(cmds),
                 hAlign="LEFT", repeatRows=first_body)


def cover_page(*, kicker: str, title: str, standfirst: str, facts,
               contents, note: str) -> list:
    """Page 1: who it is for, what window it covers, and what is inside.

    Provo's cover states four facts and then lists the packet's sections with
    their page ranges, and it is right to: the first question anybody asks of a
    62-page document is which part of it they have to read. ``facts`` and
    ``contents`` are already-resolved `(label, value)` pairs — the page ranges
    come from the second pass (`packet.Pagination`), never from this module.

    The cover carries no running head and no page number, so nothing sets the
    furniture before it.
    """
    st = styles()
    fact_rows = [[TrackedLabel(label, width=150, pad_bottom=0.0),
                  Paragraph(text(value), st["body"])] for label, value in facts]
    content_rows = [[Paragraph(text(label), st["body"]),
                     Paragraph(text(pages), st["cell_right"])]
                    for label, pages in contents]
    return [
        Spacer(0, 26),
        TrackedLabel(kicker, style=SECTION, color=ACCENT, pad_bottom=14.0),
        Paragraph(text(title), st["cover_title"]),
        Paragraph(text(standfirst), st["cover_lead"]),
        Spacer(0, 18),
        HairRule(color=INK, thickness=1.2, space_before=0, space_after=16),
        table(fact_rows, [150, CONTENT_WIDTH - 150], row_rules=False, pad=3.0),
        Spacer(0, 22),
        TrackedLabel("Contenido", style=SECTION, color=INK, pad_bottom=6.0),
        table(content_rows, [CONTENT_WIDTH - 90, 90], align=["l", "r"],
              pad=3.0),
        Spacer(0, 26),
        Paragraph(text(note), st["note"]),
    ]


def print_guide(*, heading_note: str, intro: str, sections, handouts,
                closing) -> list:
    """Page 2: what to print, and who each stack of paper goes to.

    Two tables, as Provo does. The first says what the packet contains and
    whether that section is meant to be printed at all; the second is the run
    sheet — one row per person at the table, with the pages and the number of
    copies. ``sections`` and ``handouts`` arrive as rows of strings; the copy
    counts behind them come from MISSION_ORG (`packet.hand_outs`).

    ``closing`` is a list of sentences, each its own small paragraph: the total
    paper, and whatever the roster could not answer.
    """
    st = styles()
    return [
        SectionHead("Guía de impresión", heading_note),
        Paragraph(text(intro), st["body"]),
        Spacer(0, 6),
        TrackedLabel("Qué contiene este paquete", style=CELL_HEAD,
                     pad_bottom=3.0),
        table(sections, [196, 62, 172, 90],
              headers=["Sección", "Páginas", "Para quién", "¿Imprimir?"],
              align=["l", "r", "l", "l"]),
        Spacer(0, 14),
        TrackedLabel("Orden de impresión — qué entregar", style=CELL_HEAD,
                     pad_bottom=3.0),
        table(handouts, [176, 96, 54, 194],
              headers=["Entregar a", "Páginas", "Copias", "Notas"],
              align=["l", "r", "r", "l"]),
        Spacer(0, 10),
    ] + [Paragraph(text(line), st["note"]) for line in closing]


# ── Page blocks ───────────────────────────────────────────────
#
# Compositions of the five primitives above, still knowing nothing about what a
# Key Indicator is: everything arrives as a `MetricLine`, a `Tile` or a tuple of
# strings that `packet.py` has already resolved. That boundary is what lets a
# page be laid out in a test with no model and no sheet behind it.

#: How wide a stat tile's own column is before it starts truncating its label.
TILE_MIN_WIDTH = 96.0
TILE_HEIGHT = 52.0


@dataclass(frozen=True)
class Tile:
    """One headline figure: what it is, how big, and how it is doing.

    ``note`` is the line under the number — Provo's "confirmed by Assistants to
    the President", or a status and its percentage. ``status`` colours the
    number's underline, never the number itself: a figure printed in amber on
    white is a figure a photocopier loses.
    """

    label: str
    value: str
    note: str = ""
    status: str | None = None


def _wrap(label: str, style: Type, limit: float, lines: int = 2) -> list:
    """`label` broken on spaces into at most `lines` runs that each fit.

    Measured, not counted, and the LAST line takes everything that is left and
    is truncated rather than dropped: "Amigos en la Reunión Sacramental" in a
    130pt column is three words too long for one line and exactly right for
    two, and an ellipsis after "Amigos en la Reunión" names nothing.
    """
    words = text(label).split()
    out, current = [], ""
    for i, word in enumerate(words):
        trial = f"{current} {word}".strip()
        if not current or width_of(trial, style) <= limit:
            current = trial
            continue
        out.append(current)
        if len(out) == lines - 1:
            current = " ".join(words[i:])
            break
        current = word
    out.append(fit(current, style, limit))
    return out


def stat_tiles(width: float, tiles, *, columns: int = 4) -> Drawing:
    """A band of headline figures, as Provo puts at the foot of a unit's page.

    Wraps into rows of ``columns``, so five tiles are four and one rather than
    five squeezed. A tile's LABEL wraps onto a second line — Provo's does the
    same with "New People Being Taught (NEW)" — because the Spanish names run
    long and a band of "AMIGOS EN LA REUNIÓN SACR..." tells a reader nothing
    they did not already know.
    """
    tiles = list(tiles)
    if not tiles:
        return Drawing(width, 1)
    columns = max(1, min(columns, int(width // TILE_MIN_WIDTH) or 1))
    rows = (len(tiles) + columns - 1) // columns
    height = rows * TILE_HEIGHT
    d = Drawing(width, height)
    col_w = width / columns
    for i, tile in enumerate(tiles):
        row, col = divmod(i, columns)
        x = col * col_w
        top = height - row * TILE_HEIGHT
        g = Group()
        for n, line in enumerate(_wrap(tile.label.upper(), TILE_LABEL,
                                       col_w - 10)):
            _tracked(g, x, top - 9 - n * (TILE_LABEL.leading - 1.5), line,
                     TILE_LABEL, INK_3)
        d.add(g)
        d.add(_string(x, top - 30, fit(tile.value, TILE_VALUE, col_w - 10),
                      TILE_VALUE, INK))
        d.add(Rect(x, top - 36, 22, 2, fillColor=status_color(tile.status),
                   strokeColor=None, strokeWidth=0))
        if tile.note:
            d.add(_string(x, top - 44, fit(tile.note, NOTE, col_w - 10), NOTE,
                          INK_3))
    return d


@dataclass(frozen=True)
class MetricLine:
    """One row of a metric table, already reduced to strings by `packet.py`.

    ``pct`` fills the bar and ``mark_pct`` is the violet leadership mark, both
    as percentages of the same goal. ``status`` colours the fill; None leaves
    it the single magnitude blue, which is what a nightly row wants — decision
    31 puts a nightly row's colour on its MOVEMENT, not on its distance from a
    goal set at roughly twice what the mission does.

    ``verdict`` is the words beside the bar ("al ritmo \u00b7 93%"), or the flag when
    the goal is not a yardstick. ``change`` is `(direction, text)`.
    """

    label: str
    value: str
    goal: str
    pct: float | None = None
    mark_pct: float | None = None
    status: str | None = None
    #: True when the bar is a size and not a verdict — it then draws in the one
    #: magnitude blue and the row's colour lives entirely in its change.
    magnitude: bool = False
    verdict: str = ""
    change: tuple | None = None
    note: str = ""


#: The metric table's columns at content width. The bar gets the most room of
#: anything because it is the only column a reader can scan without reading.
METRIC_COLUMNS = (150.0, 44.0, 44.0, 120.0, 96.0, 66.0)


def change_chip(width: float, change, *, height: float = 9.0) -> Drawing:
    """A direction and a size, right-aligned: a drawn triangle and its number.

    The triangle rather than an arrow glyph — see this module's docstring — and
    the number carries its own sign, so a photocopy that loses the colour keeps
    the direction twice over.

    A ``direction`` of 0 draws no triangle and prints the figure in the muted
    ink. That is what a change measured across a window too thin to trust looks
    like: the number is still there, because decision 6 says a partial
    comparison is shown, but it does not claim a direction it cannot know.
    """
    d = Drawing(width, height)
    if not change:
        return d
    direction, label = change
    label = text(label)
    w = width_of(label, CELL)
    d.add(_string(width, 1.5, label, CELL,
                  INK_2 if direction else INK_3, anchor="end"))
    tri = change_mark(width - w - 7, 1.8, int(direction), size=4.2)
    if tri is not None:
        d.add(tri)
    return d


def metric_table(lines, *, widths=METRIC_COLUMNS, headers=None) -> Table:
    """Every metric of a unit, one row each — the packet's workhorse table.

    Provo prints METRIC / ACTUAL / GOAL / AGAINST GOAL. This adds the bar, so
    the column a reader scans is a length rather than a number, and the change,
    because a council's question is which way a thing is moving.

    The row padding is 3.5pt rather than the table default's 4. Measured: the
    nightly table is twenty-two rows, and with its three closing notes the
    block came to 693pt against 688pt of frame — five points over, which put
    the last note alone on a page of its own behind every unit in the packet.
    """
    st = styles()
    headers = headers or ("Métrica", "Real", "Meta", "", "Contra la meta",
                          "Cambio")
    bar_width = widths[3] - 8
    rows = []
    for line in lines:
        name = Paragraph(text(line.label), st["cell_bold"])
        if line.note:
            name = [name, Paragraph(text(line.note), st["note"])]
        rows.append([
            name,
            Paragraph(text(line.value), st["cell_right"]),
            Paragraph(text(line.goal), st["cell_right"]),
            bar_vs_goal(bar_width, pct=line.pct, status=line.status,
                        mark_pct=line.mark_pct, track_color=RULE_SOFT,
                        fill=SERIES[0] if line.magnitude else None),
            Paragraph(text(line.verdict), st["cell"]),
            change_chip(widths[5] - 8, line.change),
        ])
    return table(rows, widths, headers=headers, pad=3.5,
                 align=["l", "r", "r", "l", "l", "l"])


#: Above this many complete weeks the value columns stop fitting and the strip
#: falls back to the line alone. Six is a transfer; "Ano" can run to thirty-
#: eight, and thirty-eight columns of 13pt is not a table anybody can read.
WEEK_COLUMN_LIMIT = 6
WEEK_ROW_HEIGHT = 15.0


def week_table(width: float, weeks, rows, *, boundaries=(), footer=None,
               spark_width: float = 70.0) -> Drawing:
    """A metric per line: its name, its shape, every week's figure, the total.

    Provo prints the weeks' own numbers and is right to: over a transfer there
    are at most six of them, and a line through two points is a straight line
    whatever the two points are — which is precisely what the current transfer
    has, and what made the first version of this block say nothing at all.

    The spark stays, narrow, because shape is faster to read than six numbers
    when a reader is scanning seven rows for the one that turned. Every spark
    is drawn on its OWN scale: seven Key Indicators whose totals run from 1 to
    364 share no axis worth having, and the figures carry the size.

    ``boundaries`` are the indices of the weeks that OPEN a transfer — a dashed
    rule is drawn down the table immediately before each (decision 9), so a
    companionship change is visible as the discontinuity it is.

    ``footer`` is `(label, values, total)` printed under a rule, and on this
    table it is not optional in practice: these are RAW weekly sums, and CCSM's
    weekly reporting has run 26 to 36 areas of 45 between one week and the
    next. Without the count of areas that filed sitting under the figures, a
    week where nine fewer companionships sent a form reads as a mission that
    halved its work (§1.3's reporting-rate trap).
    """
    rows, weeks = list(rows), list(weeks)
    if not rows:
        return Drawing(width, 1)
    show_weeks = 0 < len(weeks) <= WEEK_COLUMN_LIMIT
    total_w = 48.0
    label_w = 150.0
    week_w = ((width - label_w - spark_width - total_w) / len(weeks)
              if show_weeks else 0.0)
    if show_weeks and week_w < 26:
        show_weeks, week_w = False, 0.0
    if not show_weeks:
        spark_width = width - label_w - total_w - 10

    weeks_x = label_w + spark_width + 10
    height = (len(rows) + 1 + (1.6 if footer else 0)) * WEEK_ROW_HEIGHT
    d = Drawing(width, height)

    head_y = height - 9
    g = Group()
    if show_weeks:
        for i, week in enumerate(weeks):
            right = weeks_x + i * week_w + week_w - 4
            _tracked(g, right, head_y, es_display.day_month(week), CELL_HEAD,
                     INK_3, anchor="end")
    _tracked(g, width, head_y, "total", CELL_HEAD, INK_3, anchor="end",
             upper=True)
    d.add(g)
    d.add(Line(0, height - WEEK_ROW_HEIGHT, width, height - WEEK_ROW_HEIGHT,
               strokeColor=RULE, strokeWidth=0.5))

    if show_weeks:
        for index in boundaries or ():
            if 0 < index <= len(weeks):
                x = weeks_x + index * week_w - week_w - 2
                d.add(Line(x, 0, x, height - WEEK_ROW_HEIGHT + 4,
                           strokeColor=RULE, strokeWidth=0.6,
                           strokeDashArray=[1.6, 1.6]))

    for i, (label, values, total) in enumerate(rows):
        top = height - (i + 1) * WEEK_ROW_HEIGHT
        base = top - 10
        d.add(_string(0, base, fit(label, CELL, label_w - 8), CELL, INK_2))
        spark = sparkline(spark_width, WEEK_ROW_HEIGHT - 5, values)
        holder = Group(*spark.contents)
        holder.transform = (1, 0, 0, 1, label_w, top - WEEK_ROW_HEIGHT + 2)
        d.add(holder)
        if show_weeks:
            for n, value in enumerate(values[:len(weeks)]):
                right = weeks_x + n * week_w + week_w - 4
                shown = es_display.NA if value is None else es_display.integer(value)
                d.add(_string(right, base, shown, CELL,
                              INK_2 if value is not None else INK_3,
                              anchor="end"))
        d.add(_string(width, base, total, CELL, INK, anchor="end"))
        if i:
            d.add(Line(0, top, width, top, strokeColor=RULE_SOFT,
                       strokeWidth=0.5))
    if footer:
        label, values, total = footer
        top = height - (len(rows) + 1) * WEEK_ROW_HEIGHT
        base = top - 11
        d.add(Line(0, top - 2, width, top - 2, strokeColor=RULE,
                   strokeWidth=0.5))
        d.add(_string(0, base, fit(label, NOTE, label_w + spark_width), NOTE,
                      INK_3))
        if show_weeks:
            for n, value in enumerate(values[:len(weeks)]):
                right = weeks_x + n * week_w + week_w - 4
                d.add(_string(right, base, es_display.integer(value), NOTE,
                              INK_3, anchor="end"))
        if total:
            d.add(_string(width, base, total, NOTE, INK_3, anchor="end"))
    return d


def legend(width: float, sentence: str = "") -> Drawing:
    """The three states, spelled out, and the sentence that qualifies them.

    On every page that grades anything. A packet gets photocopied, read by
    somebody who was not in the room when it was built, and argued with — so
    the key travels with the page rather than living once on page 2.
    """
    height = 9.0 + (NOTE.leading if sentence else 0)
    d = Drawing(width, height)
    x = 0.0
    for state in ("good", "warn", "bad"):
        d.add(Rect(x, height - 8, 6, 6, fillColor=STATUS[state],
                   strokeColor=None, strokeWidth=0))
        word = STATUS_WORD[state]
        d.add(_string(x + 9, height - 7.5, word, NOTE, INK_2))
        x += 9 + width_of(word, NOTE) + 16
    if sentence:
        d.add(_string(0, 0, fit(sentence, NOTE, width), NOTE, INK_3))
    return d


__all__ = [
    "PAGE_SIZE", "PAGE_WIDTH", "PAGE_HEIGHT", "MARGIN_X", "MARGIN_TOP",
    "MARGIN_BOTTOM", "CONTENT_WIDTH", "CONTENT_HEIGHT",
    "FONT", "FONT_BOLD", "FONT_ITALIC", "Type", "TITLE", "SUBTITLE", "SECTION",
    "SECTION_NOTE", "BODY", "CELL", "CELL_HEAD", "NOTE", "TILE_VALUE",
    "TILE_LABEL", "FURNITURE",
    "pc", "INK", "INK_2", "INK_3", "RULE", "RULE_SOFT", "TINT", "PAPER",
    "MARK", "ACCENT", "NAVY", "STATUS", "SERIES", "UNGRADED", "status_color",
    "STATUS_WORD",
    "text", "is_printable", "width_of", "fit",
    "change_mark", "dot", "draw_tracked", "Furniture", "SetFurniture", "draw_furniture",
    "SectionHead", "HairRule", "TrackedLabel", "styles", "table",
    "cover_page", "print_guide", "COVER_TITLE", "COVER_LEAD",
    "Tile", "stat_tiles", "MetricLine", "METRIC_COLUMNS", "change_chip",
    "metric_table", "week_table", "WEEK_COLUMN_LIMIT", "legend",
    "bar_vs_goal", "sparkline", "stage_bars", "share_bar", "ranked_row",
    "RankedSpec",
]
