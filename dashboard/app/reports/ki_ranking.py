"""The weekly Key Indicator ranking PDFs: every sector, zone by zone.

PLAN-2026-10-10-ki-autosend.md (K9). Moved here from tools/build_ki_ranking.py,
weekly document only, so the Monday GitHub job (`app.ingestion.ki_pdf_runner`)
can build what Zackary approved on 2026-10-05/06: the mission document (cover,
the mission pair, each zone's pair) and one document per zone (cover and that
zone's pair). Each page is ONE week, latest first, named by its dates.

A week's goal is the companionship's ki_*_meta from the PREVIOUS week's form.
Score = mean over the 7 KIs of result ÷ goal, each capped at 150%; a KI with no
goal but a result counts 100%. A sector missing its goal-setting report has an
ungraded week (SIN META, ranked last); a sector with no report counts 0 (SIN
INFORME). Grading is the council packet's 90/60 palette.

Reads WEEKLY_FORM_RAW, not WEEKLY_KI: Agent5A rebuilds WEEKLY_KI once a day, so
a late form would be missing. `ki_from_raw` ports a5a_writeWeeklyKI; with a
`cutoff` it keeps only forms stamped at or before it — the moment Agent1A read
the forms for the letter (K3), so the PDFs and the letter count the same forms.

No Streamlit here: the job runs headless.
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.reports import packet_parts as PP

KEYS = ["ki_new_people", "ki_member_lessons", "ki_friends_sacrament",
        "ki_friends_first_week", "ki_baptismal_date", "ki_baptized_confirmed",
        "ki_rc_at_church"]
SHORT = {
    "ki_new_people": "Nuevas personas",
    "ki_member_lessons": "Lecciones c/ miembros",
    "ki_friends_sacrament": "Amigos en sacramental",
    "ki_friends_first_week": "Amigos 1.ª semana",
    "ki_baptismal_date": "Fecha bautismal",
    "ki_baptized_confirmed": "Bautismos",
    "ki_rc_at_church": "Conversos en la Iglesia",
}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct",
         "nov", "dic"]

F, FB = PP.FONT, PP.FONT_BOLD
INK, INK2, INK3 = PP.INK, PP.INK_2, PP.INK_3
RULE, RULE_SOFT, NAVY, ACCENT = PP.RULE, PP.RULE_SOFT, PP.NAVY, PP.ACCENT
GOOD, WARN, BAD = PP.STATUS["good"], PP.STATUS["warn"], PP.STATUS["bad"]
WHITE = colors.white

PW, PH = landscape(letter)
M = 36
CONTENT_TOP = PH - 96
CONTENT_BOTTOM = 46


def tint(col, a):
    """`col` laid over white at opacity `a`."""
    return colors.Color(1 - (1 - col.red) * a, 1 - (1 - col.green) * a,
                        1 - (1 - col.blue) * a)


def status(p):
    if p is None:
        return None
    return "good" if p >= 0.9 else "warn" if p >= 0.6 else "bad"


def scol(p):
    return {"good": GOOD, "warn": WARN, "bad": BAD}.get(status(p), INK3)


def fmt(n):
    n = round(n)
    return f"{n:,}".replace(",", ".")


def pct_s(p):
    return "—" if p is None else f"{round(p * 100)}%"


def dfa(end):
    start = end - timedelta(days=6)
    if start.month == end.month:
        return f"del {start.day} al {end.day} {MESES[end.month - 1]}"
    return f"del {start.day} {MESES[start.month - 1]} al {end.day} {MESES[end.month - 1]}"


def dspan(end):
    start = end - timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}–{end.day} {MESES[end.month - 1]}"
    return f"{start.day} {MESES[start.month - 1]}–{end.day} {MESES[end.month - 1]}"


def num(x):
    try:
        return float(str(x).replace(",", "."))
    except ValueError:
        return 0.0


def dicts(table):
    head = table[0]
    return [dict(zip(head, r)) for r in table[1:]]


# CcsmData.gs CCSM_FORM_STRUCTURAL
AREA_Q, ZONE_Q, DATE_Q = "¿En qué área sirve?", "¿En qué zona sirve?", "¿Qué fecha está ingresando?"


def _norm(h):
    return re.sub(r"\s+", " ", str(h).lower().replace("'", "").replace("’", "")).strip()


def _parse_date(v):
    v = str(v).strip().split(" ")[0]
    for f in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, f).date()
        except ValueError:
            pass
    return None


def _parse_ts(v):
    for f in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"):
        try:
            return datetime.strptime(str(v).strip(), f)
        except ValueError:
            pass
    return datetime.min


def _parse_float(v):
    """JavaScript parseFloat: the leading number, else 0."""
    m = re.match(r"\s*[-+]?(\d+(\.\d*)?|\.\d+)", str(v))
    return float(m.group(0)) if m else 0.0


def ki_from_raw(raw, cutoff=None):
    """WEEKLY_KI as CCSM_Agent5A.gs a5a_writeWeeklyKI would write it right now.

    Agent5A rebuilds WEEKLY_KI once a day, so a form sent after that run is in
    WEEKLY_FORM_RAW but not yet in WEEKLY_KI. Same rules: the section is the
    one whose area column is filled, offsets are learned from the first
    section by header text, the self-reported date maps to the Sunday on or
    after it, and the latest submission per area+week wins.

    With `cutoff` (a naive datetime on the SHEET's clock, the one the form
    stamps are written in — ki_pdf_runner.to_sheet_clock), a form stamped
    after it is left out, exactly as if it had not arrived yet.
    """
    table = raw["WEEKLY_FORM_RAW"]
    head = [str(h).strip() for h in table[0]]
    headers = {q["Metric_Key"]: q["Form_Column_Header"]
               for q in dicts(raw["QUESTIONS_CONFIG"])
               if q["Form_Type"] == "WEEKLY" and q["Metric_Key"].startswith("ki_")}
    area_cols = [i for i, h in enumerate(head) if _norm(h) == _norm(AREA_Q)]
    zone_idx = next(i for i, h in enumerate(head) if _norm(h) == _norm(ZONE_Q))
    start = area_cols[0]
    end = area_cols[1] if len(area_cols) > 1 else len(head)
    off = {}
    for i in range(start, end):
        off.setdefault(_norm(head[i]), i - start)
    date_off = off[_norm(DATE_Q)]
    moff = {k: off[_norm(h)] for k, h in headers.items() if _norm(h) in off}
    assert len(moff) == 14, sorted(set(headers) - set(moff))
    lookup = {r["Area_Name"].lower(): r for r in dicts(raw["MISSION_ORG"]) if r["Area_Name"]}
    agg = {}
    for row in table[1:]:
        row = list(row) + [""] * (len(head) - len(row))
        st, area = next(((c, row[c].strip()) for c in area_cols if row[c].strip()), (None, ""))
        if not area or area.lower() not in lookup:
            continue
        o = lookup[area.lower()]
        d = _parse_date(row[st + date_off])
        if not d:
            continue
        week_end = (d + timedelta(days=6 - d.weekday())).isoformat()
        ts = _parse_ts(row[0])
        if cutoff is not None and ts > cutoff:
            continue
        key = (o["Area_Name"], week_end)
        if key in agg and agg[key][0] >= ts:
            continue
        rec = {"Week_End_Date": week_end, "Area": o["Area_Name"],
               "Zone": row[zone_idx].strip(), "District": o.get("District", "")}
        for k, o_ in moff.items():
            rec[k] = _parse_float(row[st + o_])
        agg[key] = (ts, rec)
    return [rec for _, rec in agg.values()]


def check_against_weekly_ki(raw, rebuilt):
    """Every WEEKLY_KI row must come out of the rebuild unchanged."""
    live = {(r["Area"], r["Week_End_Date"]): r for r in dicts(raw["WEEKLY_KI"])}
    mine = {(r["Area"], r["Week_End_Date"]): r for r in rebuilt}
    cols = [k for k in mine[next(iter(mine))] if k.startswith("ki_")]
    diff = [k for k in live if k not in mine or any(
        num(live[k][c]) != num(mine[k][c]) for c in cols)]
    extra = sorted((k for k in mine if k not in live), key=lambda k: (k[1], k[0]))
    return len(live), diff, extra


def index_rows(ki, w2):
    idx, notes = {}, []
    for r in ki:
        idx[(r["Area"], r["Week_End_Date"])] = r          # last row wins
    # A report dated after the latest complete week is a date-entry slip for
    # that week, as long as the sector has no report for it already.
    for (area, wk), r in list(idx.items()):
        if wk > w2.isoformat() and (area, w2.isoformat()) not in idx:
            idx[(area, w2.isoformat())] = r
            del idx[(area, wk)]
            notes.append(f"{area} envió su informe con la fecha {wk}; se tomó "
                         f"como la semana que termina el {w2.isoformat()}.")
    return idx, notes


class Unit:
    """A sector, a zone or the mission: two weeks of results and goals, and
    next week's goals."""

    def __init__(self, name, zone="", district=""):
        self.name, self.zone, self.district = name, zone, district
        self.r1 = dict.fromkeys(KEYS, 0.0)
        self.g1 = dict.fromkeys(KEYS, 0.0)
        self.r2 = dict.fromkeys(KEYS, 0.0)
        self.g2 = dict.fromkeys(KEYS, 0.0)
        self.nx = dict.fromkeys(KEYS, 0.0)
        # Results in weeks that HAVE a goal — the only results a % is taken of.
        self.rg1 = dict.fromkeys(KEYS, 0.0)
        self.rg2 = dict.fromkeys(KEYS, 0.0)
        # Report flags: the goal-setting week (W0), W1, W2. For a group these
        # are counts of sectors that filed.
        self.f0 = self.f1 = self.f2 = 0
        self.n = 1
        self.rank = 0

    def R(self, k):
        return self.r1[k] + self.r2[k]

    def G(self, k):
        return self.g1[k] + self.g2[k]

    def Rg(self, k):
        """Results of the weeks that had a goal. A week whose goal-setting
        report is missing has a goal of 0, and grading its results against
        nothing would reward the missing report."""
        return self.rg1[k] + self.rg2[k]

    def grade(self):
        for k in KEYS:
            self.rg1[k] = self.r1[k] if self.g1[k] > 0 else 0.0
            self.rg2[k] = self.r2[k] if self.g2[k] > 0 else 0.0

    def pct(self, k):
        g = self.G(k)
        return self.Rg(k) / g if g > 0 else None

    @property
    def score(self):
        parts = []
        for k in KEYS:
            g, r = self.G(k), self.R(k)
            if g > 0:
                parts.append(min(self.Rg(k) / g, 1.5))
            elif r > 0:
                parts.append(1.0)
        return sum(parts) / len(parts) if parts else 0.0

    @property
    def total(self):
        return sum(self.R(k) for k in KEYS)

    def add(self, other):
        for attr in ("r1", "g1", "r2", "g2", "nx", "rg1", "rg2"):
            mine, theirs = getattr(self, attr), getattr(other, attr)
            for k in KEYS:
                mine[k] += theirs[k]
        self.f0 += other.f0
        self.f1 += other.f1
        self.f2 += other.f2


def rank(units):
    units.sort(key=lambda u: (-round(u.score, 6), -u.total, u.name))
    for i, u in enumerate(units, 1):
        u.rank = i
    return units


def build_model(raw, w2, cutoff=None, stamp=""):
    """Two weeks (w2 = the Sunday ending the latest) of every sector, zone and
    the mission. `stamp` is what the footer says the forms were read at."""
    w1, w0 = w2 - timedelta(days=7), w2 - timedelta(days=14)
    ki = ki_from_raw(raw, cutoff)
    # The zones that use the weekly form: the four pilot zones.
    zones_reporting = {r["Zone"] for r in ki}
    roster = [r for r in dicts(raw["MISSION_ORG"])
              if r["Active"].upper() == "TRUE" and r["Zone"] in zones_reporting]
    idx, notes = index_rows(ki, w2)

    def vals(area, wk, suffix):
        r = idx.get((area, wk.isoformat()))
        return ({k: num(r.get(f"{k}_{suffix}", 0)) for k in KEYS} if r
                else dict.fromkeys(KEYS, 0.0)), r is not None

    zone_order = []
    sectors = []
    for r in roster:
        u = Unit(r["Area_Name"], r["Zone"], r["District"])
        u.r1, u.f1 = vals(u.name, w1, "real")
        u.g1, u.f0 = vals(u.name, w0, "meta")
        u.r2, u.f2 = vals(u.name, w2, "real")
        u.g2, _ = vals(u.name, w1, "meta")
        u.nx, _ = vals(u.name, w2, "meta")
        u.f0, u.f1, u.f2 = int(u.f0), int(u.f1), int(u.f2)
        u.grade()
        sectors.append(u)
        if u.zone not in zone_order:
            zone_order.append(u.zone)

    zones = {}
    for z in zone_order:
        zu = Unit(z)
        zu.n = 0
        members = [s for s in sectors if s.zone == z]
        for s in members:
            zu.add(s)
            zu.n += 1
        zones[z] = (zu, rank(members))
    mission = Unit("Total de la misión")
    mission.n = 0
    for zu, members in zones.values():
        mission.add(zu)
        mission.n += zu.n
    zone_units = rank([zu for zu, _ in zones.values()])
    return {"w0": w0, "w1": w1, "w2": w2, "zones": zones,
            "zone_units": zone_units, "mission": mission, "notes": notes,
            "sectors": sectors, "stamp": stamp}


# ── Drawing primitives ───────────────────────────────────────────────────────

def T(c, x, y, s, size=7.5, font=F, color=INK, align="l", maxw=None):
    s = PP.text(s)
    if maxw:
        cut = False
        while s and stringWidth(s, font, size) > maxw:
            s, cut = s[:-1], True
        if cut:
            s = s.rstrip() + "…"
    c.setFont(font, size)
    c.setFillColor(color)
    {"l": c.drawString, "r": c.drawRightString, "c": c.drawCentredString}[align](x, y, s)


def wrap(s, font, size, maxw):
    words, lines, cur = PP.text(s).split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if stringWidth(trial, font, size) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def box(c, x, y, w, h, fill=None, stroke=None, lw=0.5, r=0):
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(lw)
    if r:
        c.roundRect(x, y, w, h, r, fill=int(fill is not None), stroke=int(stroke is not None))
    else:
        c.rect(x, y, w, h, fill=int(fill is not None), stroke=int(stroke is not None))


def line(c, x1, y1, x2, y2, col=RULE, lw=0.5):
    c.setStrokeColor(col)
    c.setLineWidth(lw)
    c.line(x1, y1, x2, y2)


def chips(c, x, y, flags, size=5.2, gap=2.2):
    """One square per week: filled = filed, hollow red = no report (counted as 0)."""
    for i, f in enumerate(flags):
        xx = x + i * (size + gap)
        if f:
            box(c, xx, y, size, size, fill=NAVY)
        else:
            box(c, xx, y, size, size, fill=WHITE, stroke=BAD, lw=0.8)


def no_report_tag(c, x, y, size=5.6):
    s = "SIN INFORME"
    w = stringWidth(s, FB, size) + 6
    box(c, x, y - 1.6, w, size + 3.2, fill=tint(BAD, 0.12), r=1.5)
    T(c, x + 3, y, s, size, FB, BAD)
    return w


class Doc:
    def __init__(self, out, model, zone=None):
        self.c = canvas.Canvas(out, pagesize=(PW, PH))
        self.c.setTitle(f"Zona {zone} — indicadores clave por sector" if zone
                        else "Indicadores clave por sector — clasificación por zona")
        self.c.setAuthor("PMG Compass")
        self.m = model
        self.zone = zone
        self.page = 0

    def start(self, kicker, title, subtitle, accent=NAVY):
        if self.page:
            self.c.showPage()
        self.page += 1
        c = self.c
        box(c, 0, PH - 6, PW, 6, fill=accent)
        T(c, M, PH - 30, kicker.upper(), 7, FB, accent)
        T(c, M, PH - 52, title, 18, FB, INK)
        T(c, M, PH - 67, subtitle, 8.5, F, INK2, maxw=PW - 2 * M)
        line(c, M, PH - 78, PW - M, PH - 78, RULE, 0.6)
        line(c, M, 34, PW - M, 34, RULE, 0.6)
        stamp = self.m["stamp"]
        T(c, M, 22, f"PMG Compass · Misión Chile Concepción Sur · formulario semanal "
                    f"al {stamp} · un sector sin informe cuenta como 0",
          6.4, F, INK3)
        T(c, PW - M, 22, f"Página {self.page}", 6.4, F, INK3, "r")

    def legend(self, y, extra=()):
        """The shared key: grading colours and report squares."""
        c, x = self.c, M
        for col, word in ((GOOD, "90% o más de la meta"), (WARN, "60–89%"),
                          (BAD, "menos de 60%"), (INK3, "sin meta fijada")):
            box(c, x, y, 7, 7, fill=col, r=1)
            T(c, x + 10, y + 1, word, 6.6, F, INK2)
            x += 18 + stringWidth(word, F, 6.6)
        x += 6
        chips(c, x, y + 1, [True])
        T(c, x + 8, y + 1, "informó", 6.6, F, INK2)
        x += 40
        chips(c, x, y + 1, [False])
        T(c, x + 8, y + 1, "sin informe (se cuenta como 0)", 6.6, F, INK2)
        x += 8 + stringWidth("sin informe (se cuenta como 0)", F, 6.6) + 12
        for s in extra:
            T(c, x, y + 1, s, 6.6, F, INK2)
            x += stringWidth(s, F, 6.6) + 12

    def save(self):
        self.c.save()


# ── Shared text ──────────────────────────────────────────────────────────────

def period_line(m):
    return (f"Semanas {dfa(m['w1'])} y {dfa(m['w2'])} {m['w2'].year}  ·  "
            f"Metas para la semana {dfa(m['w2'] + timedelta(days=7))}")


# ── Cover ────────────────────────────────────────────────────────────────────

def cover(doc):
    m, c, zone = doc.m, doc.c, doc.zone
    doc.start("PMG Compass · Indicadores clave",
              f"Zona {zone} — indicadores clave por sector" if zone
              else "Indicadores clave por sector — clasificación por zona",
              period_line(m))
    y = CONTENT_TOP - 4
    T(c, M, y, "CÓMO LEER ESTE DOCUMENTO", 7.5, FB, NAVY)
    y -= 14
    for p in weekly_paras(m, zone):
        for ln in wrap(p, F, 8.5, 400):
            T(c, M, y, ln, 8.5, F, INK)
            y -= 11.5
        y -= 5

    # Right column: who reported.
    x0 = 470
    y = CONTENT_TOP - 4
    T(c, x0, y, "INFORMES RECIBIDOS", 7.5, FB, NAVY)
    y -= 14
    cols = [x0, x0 + 120, x0 + 180, x0 + 240]
    for xx, h, al in zip(cols, ["Zona", "Sectores", dspan(m["w1"]), dspan(m["w2"])],
                         "lrrr"):
        T(c, xx + (40 if al == "r" else 0), y, h, 6.6, FB, INK3, al)
    y -= 4
    line(c, x0, y, PW - M, y, RULE)
    y -= 11
    shown = ([m["zones"][zone][0]] if zone
             else [z for z, _ in m["zones"].values()])
    for zu in shown + [m["mission"]]:
        bold = zu is m["mission"]
        fnt = FB if bold else F
        T(c, cols[0], y, "Misión (4 zonas)" if bold else zu.name, 7.6, fnt, INK)
        T(c, cols[1] + 40, y, str(zu.n), 7.6, fnt, INK, "r")
        T(c, cols[2] + 40, y, f"{zu.f1}", 7.6, fnt, INK, "r")
        T(c, cols[3] + 40, y, f"{zu.f2}", 7.6, fnt, WARN if zu.f2 < zu.n * 0.8 else INK, "r")
        y -= 12
    line(c, x0, y + 8, PW - M, y + 8, RULE_SOFT)
    y -= 2
    miss = m["zones"][zone][0] if zone else m["mission"]
    whose = "de la zona " if zone else ""
    note = (f"Faltan informes de la semana {dfa(m['w2'])}: {miss.n - miss.f2} sectores "
            f"{whose}aún no lo envían. Esos sectores figuran con 0 esa semana y 0 en la "
            f"meta de la semana {dfa(m['w2'] + timedelta(days=7))}. Si llegan más "
            f"informes, el documento se puede volver a generar."
            if miss.f2 < miss.n else
            f"Todos los sectores {whose}enviaron su informe del {dspan(m['w2'])}.")
    for ln in wrap(note, F, 7.4, PW - M - x0):
        T(c, x0, y, ln, 7.4, F, BAD if miss.f2 < miss.n * 0.8 else INK2)
        y -= 10


#: The week pages' accent (the heat-map draft "B" he chose).
WEEK_ACCENT = PP.pc("#6f63c9")


def _named_total(zu):
    t = Unit(f"Total zona {zu.name}")
    t.add(zu)
    t.n = zu.n
    return t


# ── One page per week ────────────────────────────────────────────────────────

class WeekView:
    """One week of a Unit: that week's results against that week's goal."""

    def __init__(self, u, which, group=False):
        self.u, self.which, self.group = u, which, group
        self.name, self.zone, self.district, self.n = u.name, u.zone, u.district, u.n
        if which == 1:
            self.r, self.g, self.rg, self.nx = u.r1, u.g1, u.rg1, u.g2
            self.filed, self.goal_filed = u.f1, u.f0
        else:
            self.r, self.g, self.rg, self.nx = u.r2, u.g2, u.rg2, u.nx
            self.filed, self.goal_filed = u.f2, u.f1
        self.prev = None
        self.rank = 0

    def pct(self, k):
        g = self.g[k]
        return self.rg[k] / g if g > 0 else None

    @property
    def score(self):
        # A sector whose goal-setting report is missing has nothing to be
        # graded against that week; grading its results as "no goal = 100%"
        # would reward the missing report.
        if not self.group and not self.goal_filed:
            return None
        parts = []
        for k in KEYS:
            if self.g[k] > 0:
                parts.append(min(self.rg[k] / self.g[k], 1.5))
            elif self.r[k] > 0:
                parts.append(1.0)
        return sum(parts) / len(parts) if parts else None

    @property
    def total(self):
        return sum(self.r.values())


def rank_weeks(views):
    views.sort(key=lambda v: (v.score is None, -(v.score or 0), -v.total, v.name))
    for i, v in enumerate(views, 1):
        v.rank = i
    return views


def link(this_week, last_week):
    prev = {v.name: v for v in last_week}
    for v in this_week:
        v.prev = prev.get(v.name)


def triangle(c, x, y, w, up, col):
    h = w * 0.85
    path = c.beginPath()
    if up:
        path.moveTo(x, y); path.lineTo(x + w, y); path.lineTo(x + w / 2, y + h)
    else:
        path.moveTo(x, y + h); path.lineTo(x + w, y + h); path.lineTo(x + w / 2, y)
    path.close()
    c.setFillColor(col)
    c.drawPath(path, fill=1, stroke=0)


def delta_width(d, size):
    if d == 0:
        return stringWidth("=", FB, size)
    return size * 0.8 + 1 + stringWidth(fmt(abs(d)), FB, size)


def draw_delta(c, x, y, d, size, col=None, unit=""):
    """A drawn triangle and the size of the change, from (x, y). Returns width."""
    if d == 0:
        T(c, x, y, "=", size, FB, col or INK3)
        return stringWidth("=", FB, size)
    tc = col or (GOOD if d > 0 else BAD)
    w = size * 0.8
    triangle(c, x, y + 0.2, w, d > 0, tc)
    txt = fmt(abs(d)) + unit
    T(c, x + w + 1, y, txt, size, FB, tc)
    return w + 1 + stringWidth(txt, FB, size)


def week_page(doc, which, title, sub, views, unit_word, total):
    c, m = doc.c, doc.m
    accent = WEEK_ACCENT if which == 2 else INK3
    doc.start(f"PMG Compass · Indicadores clave · {m['w2'].year}", title, sub, accent)
    xr, xs, xc = M, M + 22, M + 140
    xh = M + 156
    hw = 49.0
    xn = xh + hw * 7 + 10
    nw = 20.0
    y = CONTENT_TOP
    T(c, xh, y + 4, "RESULTADO DE LA SEMANA · DE SU META", 6.2, FB, INK3)
    nx_label = (f"METAS PARA LA SEMANA {dfa(m['w2'] + timedelta(days=7)).upper()}" if which == 2
                else f"METAS QUE FIJARON PARA LA SEMANA {dfa(m['w2']).upper()}")
    T(c, xn, y + 4, nx_label, 6.2, FB, ACCENT)
    for i, k in enumerate(KEYS):
        for j, ln in enumerate(wrap(SHORT[k], FB, 6.3, hw - 4)[:2]):
            T(c, xh + i * hw + hw / 2, y - 8 - j * 7.6, ln, 6.3, FB, INK, "c")
        ab = {"ki_new_people": "NP", "ki_member_lessons": "LM",
              "ki_friends_sacrament": "AS", "ki_friends_first_week": "A1",
              "ki_baptismal_date": "FB", "ki_baptized_confirmed": "BAU",
              "ki_rc_at_church": "CR"}[k]
        T(c, xn + i * nw + nw / 2, y - 12, ab, 6.3, FB, ACCENT, "c")
    T(c, xr, y - 22, "#", 6.2, FB, INK3)
    T(c, xs, y - 22, unit_word.upper(), 6.2, FB, INK3)
    T(c, xc, y - 22, "INF.", 6.2, FB, INK3)
    T(c, PW - M, y - 22, "CUMPLIM.", 6.2, FB, INK3, "r")
    y -= 28
    line(c, M, y, PW - M, y, INK2, 0.8)
    rows = list(views) + [total]
    rh = min(26.0, (y - CONTENT_BOTTOM - 22) / max(len(rows), 1))
    for v in rows:
        is_total = v is total
        group = v.group
        y -= rh
        if is_total:
            line(c, M, y + rh, PW - M, y + rh, INK2, 0.8)
            box(c, M, y, xh - M - 4, rh, fill=tint(NAVY, 0.08))
        mid = y + rh / 2
        # Rank, and on the last week how far it moved.
        if not is_total:
            T(c, xr + 2, mid - 1, str(v.rank), 9, FB, NAVY)
            # Only between two graded weeks: an ungraded week sits at the
            # bottom by rule, and climbing out of it is not progress.
            if (which == 2 and v.prev is not None and v.score is not None
                    and v.prev.score is not None):
                draw_delta(c, xr + 2, y + 3.2, v.prev.rank - v.rank, 5.2)
        # Name and the second line.
        T(c, xs, mid + 1.5, v.name, 7.8, FB, INK, maxw=114)
        if group:
            T(c, xs, mid - 7, f"informaron {v.filed}/{v.n}", 6, F, INK3)
        else:
            x2 = xs
            if not v.filed:
                no_report_tag(c, x2, mid - 7.5, 5.4)
            elif not v.goal_filed:
                sz = 5.4
                w = stringWidth("SIN META", FB, sz) + 6
                box(c, x2, mid - 9.1, w, sz + 3.2, fill=RULE_SOFT, r=1.5)
                T(c, x2 + 3, mid - 7.5, "SIN META", sz, FB, INK2)
            else:
                T(c, x2, mid - 7, v.district, 6, F, INK3, maxw=114 - (x2 - xs))
            chips(c, xc, mid - 2.6, [v.filed])
        # The seven cells.
        show_delta = (which == 2 and v.prev is not None
                      and (group or v.prev.filed))
        for i, k in enumerate(KEYS):
            p = v.pct(k)
            x = xh + i * hw
            if p is None:
                fill, txt_col = RULE_SOFT, INK3
            else:
                strength = 0.95 if status(p) == "bad" and p < 0.3 else 0.85
                fill, txt_col = tint(scol(p), strength), WHITE
            box(c, x + 1, y + 1, hw - 2, rh - 2, fill=fill)
            big = fmt(v.rg[k] if p is not None else v.r[k])
            small = f" de {fmt(v.g[k])}" if p is not None else ""
            bs, ss = 12.5, 7.4
            wb, ws = stringWidth(big, FB, bs), stringWidth(small, F, ss)
            fit = min(1.0, (hw - 7) / (wb + ws))
            bs, ss, wb, ws = bs * fit, ss * fit, wb * fit, ws * fit
            x0 = x + hw / 2 - (wb + ws) / 2
            base = y + rh * 0.42
            T(c, x0, base, big, bs, FB, txt_col)
            if small:
                T(c, x0 + wb, base, small, ss, F, txt_col)
            foot = pct_s(p) if p is not None else "sin meta"
            fs = 4.9
            if show_delta:
                d = v.r[k] - v.prev.r[k]
                wf = stringWidth(foot, F, fs)
                wd = delta_width(d, 5.0)
                fx = x + hw / 2 - (wf + 4 + wd) / 2
                T(c, fx, y + 3.4, foot, fs, F, txt_col)
                draw_delta(c, fx + wf + 4, y + 3.3, d, 5.0, txt_col)
            else:
                T(c, x + hw / 2, y + 3.4, foot, fs, F, txt_col, "c")
        # Goals they set for the following week.
        for i, k in enumerate(KEYS):
            x = xn + i * nw
            if i % 2 == 0:
                box(c, x, y, nw, rh, fill=tint(ACCENT, 0.07))
            T(c, x + nw / 2, mid - 3, fmt(v.nx[k]), 7.8, FB,
              BAD if (not group and not v.filed) else INK, "c")
        # The week's score, and its change.
        sc = v.score
        T(c, PW - M, mid - (0 if which == 2 else 3), pct_s(sc), 9.4, FB,
          scol(sc) if sc is not None else INK3, "r")
        if which == 2 and v.prev is not None and sc is not None and v.prev.score is not None:
            d = round(sc * 100) - round(v.prev.score * 100)
            wd = delta_width(d, 5.6) + stringWidth(" pts", FB, 5.6)
            draw_delta(c, PW - M - wd, y + 3.4, d, 5.6, unit=" pts")
        if not is_total:
            line(c, M, y, xh - 2, y, RULE_SOFT)
            line(c, xn, y, PW - M, y, RULE_SOFT)
    extra = ["celda: resultado de meta; % abajo"]
    if which == 2:
        extra.append(f"flechas: cambio frente a la semana {dfa(m['w1'])}")
    doc.legend(CONTENT_BOTTOM - 4, extra)


def weekly_pages(doc, zone=None):
    """The mission pair then every zone's pair, or with `zone` that zone's alone.

    Ranks are always computed across all four zones, so a zone's own document
    still says where it stands in the mission."""
    m = doc.m
    zone_units = [zu for zu, _ in m["zones"].values()]
    zv = {w: rank_weeks([WeekView(zu, w, True) for zu in zone_units]) for w in (1, 2)}
    link(zv[2], zv[1])
    mission = {w: WeekView(m["mission"], w, True) for w in (1, 2)}
    for w in (2, 1):
        if zone:
            break
        mv = mission[w]
        week_page(doc, w, f"Total de la misión · semana {dfa(m['w' + str(w)])}",
                  f"informaron {mv.filed}/{mv.n} sectores · cumplimiento {pct_s(mv.score)} "
                  f"· zonas ordenadas por cumplimiento de esa semana",
                  zv[w], "Zona", mv)
    for zv2 in zv[2]:
        if zone and zv2.name != zone:
            continue
        zu, members = m["zones"][zv2.name]
        sv = {w: rank_weeks([WeekView(sec, w) for sec in members]) for w in (1, 2)}
        link(sv[2], sv[1])
        tot = _named_total(zu)
        zone_rank = {w: next(v for v in zv[w] if v.name == zu.name) for w in (1, 2)}
        for w in (2, 1):
            tv = WeekView(tot, w, True)
            zr = zone_rank[w]
            week_page(doc, w, f"Zona {zu.name} · semana {dfa(m['w' + str(w)])}",
                      f"{zu.n} sectores · informaron {zr.filed}/{zu.n} · cumplimiento de la "
                      f"zona {pct_s(zr.score)} · puesto {zr.rank} de {len(zv[w])} zonas "
                      f"esa semana", sv[w], "Sector", tv)


def weekly_paras(m, zone=None):
    if zone:
        intro = [
            f"Cada sector de la zona {zone} aparece con sus siete indicadores clave.",
            f"Este documento tiene dos páginas con las mismas columnas: la semana "
            f"{dfa(m['w2'])} y la semana {dfa(m['w1'])}. Así se ve el avance de una "
            f"semana a la otra pasando la página. El puesto de la zona se cuenta entre "
            f"las cuatro zonas de la misión.",
        ]
    else:
        intro = [
            "Cada sector de las cuatro zonas que usan PMG Compass (Angol, Los Ángeles "
            "Norte, San Pedro y Temuco Ñielol) aparece con sus siete indicadores clave.",
            f"Cada zona tiene dos páginas seguidas, con las mismas columnas: la semana "
            f"{dfa(m['w2'])} y la semana {dfa(m['w1'])}. Así se ve el avance de una "
            f"semana a la otra pasando la página. La misión abre con el mismo par de "
            f"páginas, por zona.",
        ]
    return intro + _rules(m)


def _rules(m):
    return [
        "La meta de cada semana es la que el compañerismo fijó para esa semana en el "
        "informe semanal anterior (la columna «Meta» del formulario). A la derecha de "
        "cada página están las metas que fijaron al final de esa semana para la "
        "siguiente.",
        "Un sector que no envió su informe semanal cuenta como 0 esa semana. Se marca "
        "con un cuadro rojo vacío y la etiqueta SIN INFORME.",
        "Clasificación de cada semana: el promedio, en los siete indicadores, de "
        "resultado ÷ meta de esa semana, con tope de 150% por indicador; un indicador "
        "sin meta pero con resultado cuenta como 100%. Si falta el informe donde el "
        "sector fijó las metas de esa semana, la semana no se califica (SIN META) y "
        "el sector va al final. Empates: gana el mayor total de resultados.",
        f"Avance: en la página de la semana {dfa(m['w2'])}, la flecha bajo cada número "
        f"es el cambio del resultado frente a la semana {dfa(m['w1'])}, la flecha bajo "
        f"el puesto son los lugares que subió o bajó, y la de la derecha el cambio del "
        f"cumplimiento en puntos.",
        "Colores: verde 90% o más de la meta, ámbar 60–89%, rojo menos de 60%, gris "
        "sin meta fijada — la misma escala que el paquete del consejo.",
    ]


# ── The documents ────────────────────────────────────────────────────────────

def file_stem(model):
    """The week in a file name: '28sep-4oct'."""
    w2 = model["w2"]
    w1s = w2 - timedelta(days=6)
    return f"{w1s.day}{MESES[w1s.month - 1]}-{w2.day}{MESES[w2.month - 1]}"


def render(model, zone=None):
    """One document as PDF bytes: the mission's, or with `zone` that zone's."""
    buf = io.BytesIO()
    doc = Doc(buf, model, zone)
    cover(doc)
    weekly_pages(doc, zone)
    doc.save()
    return buf.getvalue(), doc.page


def build_documents(raw, w2, cutoff=None, stamp=""):
    """Every document for the week ending `w2`, mission first then each zone in
    rank order, as [{"scope": "MISSION" | <zone>, "file_name", "pdf", "pages"}].

    `raw` holds the WEEKLY_FORM_RAW, MISSION_ORG and QUESTIONS_CONFIG grids."""
    model = build_model(raw, w2, cutoff, stamp)
    week = file_stem(model)
    pdf, pages = render(model)
    docs = [{"scope": "MISSION", "file_name": f"Indicadores_clave_mision_{week}.pdf",
             "pdf": pdf, "pages": pages}]
    for zu in model["zone_units"]:
        pdf, pages = render(model, zu.name)
        docs.append({"scope": zu.name,
                     "file_name": f"Indicadores_clave_{zu.name.replace(' ', '_')}_{week}.pdf",
                     "pdf": pdf, "pages": pages})
    return docs
