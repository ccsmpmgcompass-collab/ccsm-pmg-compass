"""Key Indicator ranking by sector, grouped by zone — four renderings in one PDF.

Usage:  python build_ki_ranking.py [--cached] [--out PATH]

Reads WEEKLY_KI + MISSION_ORG from the live COMPASS_CCSM sheet (or dump.json
with --cached). For the two most recent complete weeks it compares each
sector's results (ki_*_real) with the goal the companionship set for that week
(the ki_*_meta written on the PREVIOUS week's form), and shows next week's goal
(the meta on the latest week's form). A sector with no report counts as 0.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

DASH = r"C:\Users\ChileConcepciónSouth\Downloads\ccsm-pmg-compass\dashboard"
sys.path.insert(0, DASH)
sys.stdout.reconfigure(encoding="utf-8")

from reportlab.lib import colors                      # noqa: E402
from reportlab.lib.pagesizes import landscape, letter  # noqa: E402
from reportlab.pdfbase.pdfmetrics import stringWidth   # noqa: E402
from reportlab.pdfgen import canvas                    # noqa: E402

from app.reports import packet_parts as PP             # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ── Vocabulary ───────────────────────────────────────────────────────────────

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
TINY = {
    "ki_new_people": "Nuevas personas",
    "ki_member_lessons": "Lecc. c/ miembros",
    "ki_friends_sacrament": "Amigos sacramental",
    "ki_friends_first_week": "Amigos 1.ª semana",
    "ki_baptismal_date": "Fecha bautismal",
    "ki_baptized_confirmed": "Bautismos",
    "ki_rc_at_church": "Conversos Iglesia",
}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct",
         "nov", "dic"]

F, FB, FI = PP.FONT, PP.FONT_BOLD, PP.FONT_ITALIC
INK, INK2, INK3 = PP.INK, PP.INK_2, PP.INK_3
RULE, RULE_SOFT, TINT, NAVY, ACCENT = PP.RULE, PP.RULE_SOFT, PP.TINT, PP.NAVY, PP.ACCENT
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


# ── Data ─────────────────────────────────────────────────────────────────────

def fetch():
    import tomllib
    import gspread
    from google.oauth2.service_account import Credentials
    s = tomllib.load(open(os.path.join(DASH, ".streamlit", "secrets.toml"), "rb"))
    cd = dict(s["gcp_service_account"])
    cd["private_key"] = cd["private_key"].replace("\\n", "\n")
    gc = gspread.authorize(Credentials.from_service_account_info(cd, scopes=[
        "https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))
    sh = gc.open(s["COMPASS_SHEET_NAME"])
    out = {t: sh.worksheet(t).get_all_values()
           for t in ["WEEKLY_KI", "MISSION_ORG", "WEEKLY_FORM_RAW", "QUESTIONS_CONFIG"]}
    out["_fetched"] = datetime.now().isoformat(timespec="minutes")
    json.dump(out, open(os.path.join(HERE, "dump.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    return out


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


def ki_from_raw(raw):
    """WEEKLY_KI as CCSM_Agent5A.gs a5a_writeWeeklyKI would write it right now.

    Agent5A rebuilds WEEKLY_KI once a day, so a form sent after that run is in
    WEEKLY_FORM_RAW but not yet in WEEKLY_KI. Same rules: the section is the
    one whose area column is filled, offsets are learned from the first
    section by header text, the self-reported date maps to the Sunday on or
    after it, and the latest submission per area+week wins.
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


def build_model(raw, w2, baseline=None):
    w1, w0 = w2 - timedelta(days=7), w2 - timedelta(days=14)
    from_raw = "WEEKLY_FORM_RAW" in raw
    ki = ki_from_raw(raw) if from_raw else dicts(raw["WEEKLY_KI"])
    zones_reporting = {r["Zone"] for r in dicts(raw["WEEKLY_KI"])}
    roster = [r for r in dicts(raw["MISSION_ORG"])
              if r["Active"].upper() == "TRUE" and r["Zone"] in zones_reporting]
    idx, notes = index_rows(ki, w2)
    if from_raw:
        notes.append("Los datos se leen directamente de las respuestas del formulario "
                     "semanal, así que incluyen informes enviados después de la "
                     "actualización diaria del dashboard.")
    # Compare like with like: a baseline that carried the raw form is read the
    # way that version was built.
    base_idx = (index_rows(ki_from_raw(baseline) if "WEEKLY_FORM_RAW" in baseline
                           else dicts(baseline["WEEKLY_KI"]), w2)[0]
                if baseline else None)

    def updated(area):
        """Weeks whose report is new or changed since the baseline."""
        if base_idx is None:
            return []
        out = []
        for label, wk in (("semana 1", w1), ("semana 2", w2)):
            k = (area, wk.isoformat())
            if k in idx and (k not in base_idx or any(
                    num(idx[k].get(c, 0)) != num(base_idx[k].get(c, 0))
                    for c in idx[k] if c.startswith("ki_"))):
                out.append(label)
        return out

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
        u.new_weeks = updated(u.name)
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
            "sectors": sectors, "fetched": raw.get("_fetched", ""),
            "baseline": (baseline or {}).get("_fetched", "")}


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


def updated_tag(c, x, y, size=5.6):
    s = "ACTUALIZADO"
    w = stringWidth(s, FB, size) + 6
    box(c, x, y - 1.6, w, size + 3.2, fill=ACCENT, r=1.5)
    T(c, x + 3, y, s, size, FB, WHITE)
    return w


def rank_badge(c, cx, cy, n, r=7, col=NAVY):
    c.setFillColor(col)
    c.circle(cx, cy, r, fill=1, stroke=0)
    T(c, cx, cy - 2.6, str(n), 7.2 if n < 10 else 6.6, FB, WHITE, "c")


class Doc:
    def __init__(self, path, model):
        self.c = canvas.Canvas(path, pagesize=(PW, PH))
        self.c.setTitle("Indicadores clave por sector — clasificación por zona")
        self.c.setAuthor("PMG Compass")
        self.m = model
        self.page = 0
        self.toc = []

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
        stamp = self.m["fetched"].replace("T", " ")
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


def zone_sub(zu, m):
    return (f"{zu.n} sectores · informaron {zu.f1}/{zu.n} la semana 1 y "
            f"{zu.f2}/{zu.n} la semana 2 · cumplimiento de la zona {pct_s(zu.score)} "
            f"· puesto {zu.rank} de {len(m['zone_units'])} zonas")


# ── Cover ────────────────────────────────────────────────────────────────────

def cover(doc, starts, show_options=True):
    m, c = doc.m, doc.c
    zone = getattr(doc, "zone", None)
    doc.start("PMG Compass · Indicadores clave",
              f"Zona {zone} — indicadores clave por sector" if zone
              else "Indicadores clave por sector — clasificación por zona",
              period_line(m))
    y = CONTENT_TOP - 4
    T(c, M, y, "CÓMO LEER ESTE DOCUMENTO", 7.5, FB, NAVY)
    y -= 14
    paras = [
        "Cada sector de las cuatro zonas que usan PMG Compass (Angol, Los Ángeles "
        "Norte, San Pedro y Temuco Ñielol) aparece con sus siete indicadores clave "
        "en las dos últimas semanas completas.",
        "La meta de cada semana es la que el compañerismo fijó para esa semana en "
        "el informe semanal anterior (la columna «Meta» del formulario). La meta de "
        "la próxima semana es la que fijó en el informe de la semana 2.",
        "Un sector que no envió su informe semanal cuenta como 0: 0 en resultados "
        "esa semana y 0 en la meta que habría fijado. Se marca con un cuadro rojo "
        "vacío y la etiqueta SIN INFORME.",
        "Clasificación: el cumplimiento de un sector es el promedio, en los siete "
        "indicadores, de resultado ÷ meta en las dos semanas juntas. Cada indicador "
        "tiene un tope de 150% para que uno solo no decida el puesto; un indicador "
        "sin meta y con resultado cuenta como 100%, y uno sin meta ni resultado no "
        "cuenta. Empates: gana el mayor total de resultados.",
        "Una semana sin meta no entra en el %: si falta el informe donde el sector "
        "fijó la meta de esa semana, sus resultados de esa semana no se califican; "
        "así, faltar un informe nunca sube el puesto. "
        "Faltar el informe de la semana misma sí cuenta: resultado 0 contra la meta.",
        "Colores: verde 90% o más de la meta, ámbar 60–89%, rojo menos de 60%, gris "
        "sin meta fijada — la misma escala que el paquete del consejo.",
    ]
    if getattr(doc, "weekly", False):
        paras = weekly_paras(m, getattr(doc, "zone", None))
    for p in paras:
        for ln in wrap(p, F, 8.5, 400):
            T(c, M, y, ln, 8.5, F, INK)
            y -= 11.5
        y -= 5
    notes = [] if getattr(doc, "weekly", False) else m["notes"]
    zone = getattr(doc, "zone", None)
    if zone:
        # A date-slip note names its sector first; keep only this zone's.
        mine = {sec.name for sec in m["sectors"] if sec.zone == zone}
        notes = [n for n in notes if " envió " not in n or n.split(" envió ")[0] in mine]
    if notes:
        T(c, M, y, "AJUSTES A LOS DATOS", 7.5, FB, NAVY)
        y -= 13
        for n in notes:
            for ln in wrap(n, F, 8, 400):
                T(c, M, y, ln, 8, F, INK2)
                y -= 11

    # Right column: the four options and who reported.
    x0 = 470
    y = CONTENT_TOP - 4
    if show_options:
        y = _options_index(c, x0, y, starts)
    T(c, x0, y, "INFORMES RECIBIDOS", 7.5, FB, NAVY)
    y -= 14
    cols = [x0, x0 + 120, x0 + 180, x0 + 240]
    for xx, h, al in zip(cols, ["Zona", "Sectores", dspan(m["w1"]), dspan(m["w2"])],
                         "lrrr"):
        T(c, xx + (40 if al == "r" else 0), y, h, 6.6, FB, INK3, al)
    y -= 4
    _cover_tail(doc, c, x0, y)


def _options_index(c, x0, y, starts):
    T(c, x0, y, "LAS CUATRO OPCIONES", 7.5, FB, NAVY)
    y -= 16
    opts = [("A", "Tabla de clasificación", "números por semana, meta debajo, próxima meta al lado"),
            ("B", "Mapa de calor", "% de la meta en las dos semanas, próximas metas a la derecha"),
            ("C", "Tarjetas por sector", "una tarjeta por sector con barras resultado vs. meta"),
            ("D", "Clasificación por indicador", "siete listas por zona, un puesto por indicador")]
    for (letter_, name, desc), pg in zip(opts, starts):
        c.setFillColor(OPT_COL[letter_])
        c.circle(x0 + 8, y + 2, 8, fill=1, stroke=0)
        T(c, x0 + 8, y - 0.6, letter_, 8, FB, WHITE, "c")
        T(c, x0 + 22, y + 2, f"Opción {letter_} · {name}", 9, FB, INK)
        T(c, PW - M, y + 2, f"pág. {pg}", 8, F, INK3, "r")
        T(c, x0 + 22, y - 9, desc, 7.2, F, INK2)
        y -= 28
    return y - 6


def _cover_tail(doc, c, x0, y):
    m = doc.m
    zone = getattr(doc, "zone", None)
    cols = [x0, x0 + 120, x0 + 180, x0 + 240]
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
    if m["baseline"]:
        fresh = [sec for sec in m["sectors"]
                 if sec.new_weeks and (not zone or sec.zone == zone)]
        b = datetime.fromisoformat(m["baseline"])
        y -= 12
        T(c, x0, y, f"ACTUALIZADOS DESDE LA VERSIÓN DEL {b.day} {MESES[b.month - 1].upper()} "
                    f"{b:%H:%M}", 7.5, FB, ACCENT)
        y -= 14
        if not fresh:
            T(c, x0, y, "Ningún informe nuevo.", 7.6, F, INK2)
        for sec in sorted(fresh, key=lambda u: (u.zone, u.name)):
            updated_tag(c, x0, y, 4.6)
            T(c, x0 + 44, y, sec.name, 7.6, FB, INK)
            T(c, x0 + 150, y, sec.zone, 7.2, F, INK2)
            T(c, PW - M, y, " y ".join(sec.new_weeks), 7.2, F, INK2, "r")
            y -= 12
        legend = ("Cada sector actualizado lleva la etiqueta ACTUALIZADO y una barra "
                  "azul a la izquierda en su página.")
        for ln in wrap(legend, F, 7.2, PW - M - x0):
            T(c, x0, y - 2, ln, 7.2, F, INK3)
            y -= 9.5


OPT_COL = {"A": NAVY, "B": PP.pc("#6f63c9"), "C": PP.pc("#1f7a8c"), "D": PP.pc("#b0562a")}


# ── Option A: the ranking table ─────────────────────────────────────────────

def opt_a_page(doc, title, sub, units, unit_word, total=None):
    c = doc.c
    doc.start("Opción A · Tabla de clasificación", title, sub, OPT_COL["A"])
    xr, xs, xc = M, M + 22, M + 132
    xk = M + 162
    sw = 23.4                      # one sub-column
    kw = sw * 3
    xsc = xk + kw * 7 + 4
    y = CONTENT_TOP
    # Header: KI names over S1 / S2 / Próx.
    for i, k in enumerate(KEYS):
        x = xk + i * kw
        if i % 2 == 0:
            box(c, x, y - 34, kw, 40, fill=TINT)
        lines = wrap(SHORT[k].upper(), FB, 6.1, kw - 4)
        for j, ln in enumerate(lines[:2]):
            T(c, x + kw / 2, y - 2 - j * 7.6 - (3.8 if len(lines) == 1 else 0), ln, 6.1, FB, INK, "c")
        for j, h in enumerate(["S1", "S2", "PRÓX."]):
            T(c, x + sw * j + sw / 2, y - 28, h, 5.8, FB, INK3 if j < 2 else ACCENT, "c")
    T(c, xr, y - 28, "#", 6.2, FB, INK3)
    T(c, xs, y - 28, unit_word.upper(), 6.2, FB, INK3)
    T(c, xc, y - 28, "INF.", 6.2, FB, INK3)
    T(c, PW - M, y - 2, "CUMPLI-", 6.1, FB, INK, "r")
    T(c, PW - M, y - 9.6, "MIENTO", 6.1, FB, INK, "r")
    T(c, PW - M, y - 28, "2 SEM.", 5.8, FB, INK3, "r")
    y -= 34
    line(c, M, y, PW - M, y, INK2, 0.8)

    rows = list(units) + ([total] if total else [])
    rh = min(27.0, (y - CONTENT_BOTTOM - 22) / max(len(rows), 1))
    for u in rows:
        is_total = u is total
        y -= rh
        if is_total:
            box(c, M, y, PW - 2 * M, rh, fill=tint(NAVY, 0.08))
            line(c, M, y + rh, PW - M, y + rh, INK2, 0.8)
        for i in range(7):
            if i % 2 == 0 and not is_total:
                box(c, xk + i * kw, y, kw, rh, fill=tint(TINT, 0.6))
        mid = y + rh / 2
        if not is_total:
            T(c, xr + 2, mid - 3, str(u.rank), 9, FB, NAVY)
        T(c, xs, mid + 1.5, u.name, 7.8, FB if is_total else FB, INK, maxw=106)
        group = u.n > 1 or is_total or unit_word == "Zona"
        if group:
            T(c, xs, mid - 7, f"{u.n} sectores · inf. {u.f1}/{u.n} y {u.f2}/{u.n}",
              6, F, INK3, maxw=106)
        elif not (u.f1 and u.f2):
            no_report_tag(c, xs, mid - 7.5, 5.4)
        else:
            T(c, xs, mid - 7, u.district, 6, F, INK3, maxw=106)
        if not group:
            chips(c, xc, mid - 2.6, [u.f1, u.f2])
        for i, k in enumerate(KEYS):
            x = xk + i * kw
            for j, (r, rg, g, filed) in enumerate(((u.r1[k], u.rg1[k], u.g1[k], u.f1),
                                                   (u.r2[k], u.rg2[k], u.g2[k], u.f2))):
                cx = x + sw * j + sw / 2
                p = rg / g if g > 0 else None
                if g > 0 or r > 0:
                    box(c, x + sw * j + 1.2, y + 2, sw - 2.4, rh - 4,
                        fill=tint(scol(p), 0.16), r=1.5)
                col = BAD if (not group and not filed) else (scol(p) if p is not None else INK)
                T(c, cx, mid + 0.5, fmt(r), 8, FB, col, "c")
                T(c, cx, mid - 7.2, f"de {fmt(g)}", 5.6, F, INK3, "c")
            T(c, x + sw * 2 + sw / 2, mid - 3, fmt(u.nx[k]), 8.4, FB,
              ACCENT if (group or u.f2) else BAD, "c")
        # Score: number plus a small bar.
        sc = u.score
        T(c, PW - M, mid + 0.5, pct_s(sc), 9, FB, scol(sc), "r")
        bw = 34
        box(c, PW - M - bw, mid - 7, bw, 3, fill=RULE_SOFT)
        box(c, PW - M - bw, mid - 7, bw * min(sc, 1.5) / 1.5, 3, fill=scol(sc))
        if not is_total:
            line(c, M, y, PW - M, y, RULE_SOFT)
    doc.legend(CONTENT_BOTTOM - 4, ["S1/S2 = resultado y, debajo, la meta de esa semana",
                                    "PRÓX. = meta fijada para la próxima semana"])


def option_a(doc):
    m = doc.m
    opt_a_page(doc, "Total de la misión — zonas clasificadas",
               period_line(m) + " · zonas ordenadas por cumplimiento",
               m["zone_units"], "Zona", total=m["mission"])
    for zu in m["zone_units"]:
        zone_unit, members = m["zones"][zu.name]
        opt_a_page(doc, f"Zona {zu.name}", zone_sub(zu, m), members, "Sector",
                   total=_named_total(zu))


def _named_total(zu):
    t = Unit(f"Total zona {zu.name}")
    t.add(zu)
    t.n = zu.n
    return t


# ── Option B: heat map ───────────────────────────────────────────────────────

B_KICKER = "Opción B · Mapa de calor"


def opt_b_page(doc, title, sub, units, unit_word, total=None):
    c = doc.c
    doc.start(B_KICKER, title, sub, OPT_COL["B"])
    xr, xs, xc = M, M + 22, M + 140
    xh = M + 170
    hw = 47.0
    xn = xh + hw * 7 + 12
    nw = 21.0
    y = CONTENT_TOP
    T(c, xh, y + 4, "RESULTADO DE LAS DOS SEMANAS · DE SU META", 6.2, FB, INK3)
    T(c, xn, y + 4, "METAS DE LA PRÓXIMA SEMANA", 6.2, FB, ACCENT)
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
    T(c, PW - M, y - 22, "PROM.", 6.2, FB, INK3, "r")
    y -= 28
    line(c, M, y, PW - M, y, INK2, 0.8)
    rows = list(units) + ([total] if total else [])
    rh = min(26.0, (y - CONTENT_BOTTOM - 22) / max(len(rows), 1))
    for u in rows:
        is_total = u is total
        y -= rh
        if is_total:
            line(c, M, y + rh, PW - M, y + rh, INK2, 0.8)
            box(c, M, y, xh - M - 4, rh, fill=tint(NAVY, 0.08))
        mid = y + rh / 2
        group = u.n > 1 or is_total or unit_word == "Zona"
        if not is_total:
            T(c, xr + 2, mid - 3, str(u.rank), 9, FB, NAVY)
        T(c, xs, mid + 1.5, u.name, 7.8, FB, INK, maxw=114)
        new = getattr(u, "new_weeks", None)
        if new and not group:
            box(c, M - 6, y + 2, 3, rh - 4, fill=ACCENT)
        if group:
            line2 = f"inf. {u.f1}/{u.n} y {u.f2}/{u.n}"
            T(c, xs, mid - 7, line2, 6, F, INK3)
            n_new = sum(1 for sec in doc.m["sectors"]
                        if sec.new_weeks and (is_total and unit_word == "Zona"
                                              or sec.zone == u.name
                                              or u.name.endswith(sec.zone)))
            if n_new:
                T(c, xs + stringWidth(line2, F, 6) + 4, mid - 7,
                  f"{n_new} actualizado{'s' if n_new > 1 else ''}", 6, FB, ACCENT)
        else:
            x2 = xs
            if new:
                x2 += updated_tag(c, x2, mid - 7.5, 5.4) + 3
            if not (u.f1 and u.f2):
                no_report_tag(c, x2, mid - 7.5, 5.4)
            else:
                T(c, x2, mid - 7, u.district, 6, F, INK3, maxw=114 - (x2 - xs))
        if not group:
            chips(c, xc, mid - 2.6, [u.f1, u.f2])
        for i, k in enumerate(KEYS):
            p = u.pct(k)
            x = xh + i * hw
            if p is None:
                fill, txt_col = (RULE_SOFT, INK3)
            else:
                strength = 0.95 if status(p) == "bad" and p < 0.3 else 0.85
                fill, txt_col = tint(scol(p), strength), WHITE
            box(c, x + 1, y + 1, hw - 2, rh - 2, fill=fill)
            big = fmt(u.Rg(k) if p is not None else u.R(k))
            small = f" de {fmt(u.G(k))}" if p is not None else ""
            bs, ss = 12.5, 7.4
            wb, ws = stringWidth(big, FB, bs), stringWidth(small, F, ss)
            fit = min(1.0, (hw - 7) / (wb + ws))      # three-digit totals
            bs, ss, wb, ws = bs * fit, ss * fit, wb * fit, ws * fit
            x0 = x + hw / 2 - (wb + ws) / 2
            base = y + rh * 0.42
            T(c, x0, base, big, bs, FB, txt_col)
            if small:
                T(c, x0 + wb, base, small, ss, F, txt_col)
            T(c, x + hw / 2, y + 3.4, pct_s(p) if p is not None else "sin meta",
              4.9, F, txt_col, "c")
        for i, k in enumerate(KEYS):
            x = xn + i * nw
            if i % 2 == 0:
                box(c, x, y, nw, rh, fill=tint(ACCENT, 0.07))
            T(c, x + nw / 2, mid - 3, fmt(u.nx[k]), 7.8, FB,
              BAD if (not group and not u.f2) else INK, "c")
        sc = u.score
        T(c, PW - M, mid - 3, pct_s(sc), 9.4, FB, scol(sc), "r")
        if not is_total:
            line(c, M, y, xh - 2, y, RULE_SOFT)
            line(c, xn, y, PW - M, y, RULE_SOFT)
    doc.legend(CONTENT_BOTTOM - 4, ["celda: resultado de meta; % abajo",
                                    "NP LM AS A1 FB BAU CR = los 7 indicadores en orden"])


def option_b(doc):
    m = doc.m
    opt_b_page(doc, "Total de la misión — mapa de calor por zona",
               period_line(m) + " · zonas ordenadas por cumplimiento",
               m["zone_units"], "Zona", total=m["mission"])
    for zu in m["zone_units"]:
        _, members = m["zones"][zu.name]
        opt_b_page(doc, f"Zona {zu.name}", zone_sub(zu, m), members, "Sector",
                   total=_named_total(zu))


# ── Option C: cards ──────────────────────────────────────────────────────────

CARD_W = (PW - 2 * M - 3 * 10) / 4
CARD_H = 140


def card(c, x, y, u, group=False, highlight=False):
    """A card with its top-left corner at (x, y)."""
    h = CARD_H
    filed = group or (u.f1 and u.f2)
    box(c, x, y - h, CARD_W, h, fill=WHITE,
        stroke=BAD if not filed else (NAVY if highlight else RULE),
        lw=1.1 if (highlight or not filed) else 0.6, r=3)
    head = tint(NAVY, 0.9) if highlight else (tint(BAD, 0.08) if not filed else TINT)
    box(c, x + 0.6, y - 26, CARD_W - 1.2, 25.4, fill=head, r=2.5)
    tc = WHITE if highlight else INK
    if u.rank and not highlight:
        rank_badge(c, x + 12, y - 13, u.rank, 7.5)
        nx0 = x + 24
    else:
        nx0 = x + 8
    T(c, nx0, y - 11, u.name, 8, FB, tc, maxw=CARD_W - (nx0 - x) - 40)
    if group:
        T(c, nx0, y - 21, f"{u.n} sectores · inf. {u.f1}/{u.n} y {u.f2}/{u.n}", 6,
          F, WHITE if highlight else INK3)
    elif not filed:
        no_report_tag(c, nx0, y - 21.5, 5.2)
        chips(c, nx0 + 46, y - 21, [u.f1, u.f2], 4.6, 1.8)
    else:
        T(c, nx0, y - 21, u.district, 6, F, INK3, maxw=70)
        chips(c, nx0 + 74, y - 21, [u.f1, u.f2], 4.6, 1.8)
    sc = u.score
    T(c, x + CARD_W - 7, y - 13, pct_s(sc), 10.5, FB,
      WHITE if highlight else scol(sc), "r")
    T(c, x + CARD_W - 7, y - 21.5, "cumplim.", 5.6, F, WHITE if highlight else INK3, "r")
    # Column heads
    yy = y - 34
    lw, bx, bw = 58, x + 68, CARD_W - 68 - 62
    T(c, x + 6, yy, "2 semanas: barra = resultado, raya = meta", 5.4, F, INK3)
    T(c, x + CARD_W - 24, yy, "r/meta", 5.4, F, INK3, "r")
    T(c, x + CARD_W - 6, yy, "próx.", 5.4, FB, ACCENT, "r")
    yy -= 4
    for k in KEYS:
        yy -= 14
        G = u.G(k)
        R = u.Rg(k) if G > 0 else u.R(k)
        p = u.pct(k)
        T(c, x + 6, yy + 1.5, TINY[k], 6.2, F, INK2, maxw=lw)
        scale = max(R, G, 1) * 1.08
        box(c, bx, yy, bw, 6.5, fill=RULE_SOFT)
        if R > 0:
            box(c, bx, yy, bw * R / scale, 6.5, fill=scol(p) if p is not None else INK3)
        if G > 0:
            gx = bx + bw * G / scale
            line(c, gx, yy - 2, gx, yy + 8.5, INK, 1.2)
        T(c, x + CARD_W - 24, yy + 1, f"{fmt(R)}/{fmt(G)}", 6.6, FB,
          scol(p) if p is not None else INK3, "r")
        T(c, x + CARD_W - 6, yy + 1, fmt(u.nx[k]), 6.8, FB,
          ACCENT if (group or u.f2) else BAD, "r")


def option_c(doc):
    m, c = doc.m, doc.c
    doc.start("Opción C · Tarjetas por sector", "Total de la misión y de cada zona",
              period_line(m) + " · zonas en orden de clasificación", OPT_COL["C"])
    y = CONTENT_TOP
    card(c, M, y, m["mission"], group=True, highlight=True)
    # A short explanation beside the mission card.
    ex = M + CARD_W + 16
    T(c, ex, y - 10, "CÓMO LEER UNA TARJETA", 7, FB, OPT_COL["C"])
    yy = y - 24
    for p in ["La barra es el resultado de las dos semanas juntas; la raya negra "
              "vertical es la meta. La barra pasa la raya cuando se superó la meta.",
              "r/meta = resultado de 2 semanas / meta de 2 semanas. próx. = la meta "
              "que el sector fijó para la próxima semana.",
              "Borde rojo y SIN INFORME: le falta al menos uno de los dos informes; "
              "los cuadros muestran cuál (izquierda = semana 1, derecha = semana 2) "
              "y lo que falta cuenta como 0."]:
        for ln in wrap(p, F, 7.6, PW - M - ex):
            T(c, ex, yy, ln, 7.6, F, INK2)
            yy -= 10.4
        yy -= 4
    y -= CARD_H + 22
    T(c, M, y + 8, "ZONAS", 7, FB, OPT_COL["C"])
    for i, zu in enumerate(m["zone_units"]):
        card(c, M + i * (CARD_W + 10), y, zu, group=True)
    doc.legend(CONTENT_BOTTOM - 4)

    per_page = 12
    for zu in m["zone_units"]:
        _, members = m["zones"][zu.name]
        chunks = [members[i:i + per_page] for i in range(0, len(members), per_page)]
        for pi, chunk in enumerate(chunks):
            suffix = f" ({pi + 1} de {len(chunks)})" if len(chunks) > 1 else ""
            doc.start("Opción C · Tarjetas por sector", f"Zona {zu.name}{suffix}",
                      zone_sub(zu, m), OPT_COL["C"])
            for i, u in enumerate(chunk):
                col, row = i % 4, i // 4
                card(c, M + col * (CARD_W + 10), CONTENT_TOP - row * (CARD_H + 10), u)
            doc.legend(CONTENT_BOTTOM - 4)


# ── Option D: one leaderboard per indicator ─────────────────────────────────

PANEL_W = (PW - 2 * M - 3 * 10) / 4


def panel(c, x, y, h, k, units, group):
    box(c, x, y - h, PANEL_W, h, fill=WHITE, stroke=RULE, lw=0.6, r=3)
    box(c, x + 0.6, y - 17, PANEL_W - 1.2, 16.4, fill=tint(OPT_COL["D"], 0.12), r=2.5)
    T(c, x + 6, y - 11.5, SHORT[k], 7.6, FB, INK, maxw=PANEL_W - 50)
    T(c, x + PANEL_W - 6, y - 11.5, "r/meta · próx.", 5.6, F, INK3, "r")

    def key(u):
        p = u.pct(k)
        filed = group or (u.f1 and u.f2)
        return (0 if p is not None else 1, -(min(p, 9) if p is not None else 0),
                -u.Rg(k), -u.R(k), 0 if filed else 1, u.name)
    order = sorted(units, key=key)
    rh = min(15.0 if len(order) > 6 else 22.0, (h - 24) / max(len(order), 1))
    yy = y - 20
    for i, u in enumerate(order, 1):
        yy -= rh
        p, G = u.pct(k), u.G(k)
        R = u.Rg(k) if G > 0 else u.R(k)
        filed = group or (u.f1 and u.f2)
        T(c, x + 10, yy + 3, str(i), 6.6, FB, NAVY, "r")
        T(c, x + 14, yy + 3, u.name, 6.4, F if filed else FI,
          INK if filed else BAD, maxw=56)
        bx, bw = x + 73, 30
        box(c, bx, yy + 2.4, bw, 5, fill=RULE_SOFT)
        if p is not None:
            box(c, bx, yy + 2.4, bw * min(p, 1.5) / 1.5, 5, fill=scol(p))
            line(c, bx + bw / 1.5, yy + 0.8, bx + bw / 1.5, yy + 9, INK, 0.7)
            T(c, bx + bw + 2, yy + 3, pct_s(p), 5.8, FB, scol(p))
        else:
            T(c, bx + 2, yy + 3, "sin meta", 5.4, FI, INK3)
        T(c, x + PANEL_W - 20, yy + 3, f"{fmt(R)}/{fmt(G)}", 6.2, F, INK2, "r")
        T(c, x + PANEL_W - 6, yy + 3, fmt(u.nx[k]), 6.4, FB,
          ACCENT if (group or u.f2) else BAD, "r")
        if i < len(order):
            line(c, x + 4, yy, x + PANEL_W - 4, yy, RULE_SOFT, 0.4)


def summary_panel(c, x, y, h, u, title):
    box(c, x, y - h, PANEL_W, h, fill=tint(NAVY, 0.05), stroke=NAVY, lw=0.8, r=3)
    T(c, x + 6, y - 12, title, 7.6, FB, NAVY, maxw=PANEL_W - 12)
    T(c, x + 6, y - 22, f"{u.n} sectores · informaron {u.f1}/{u.n} y {u.f2}/{u.n}",
      6, F, INK3)
    T(c, x + PANEL_W - 6, y - 40, pct_s(u.score), 16, FB, scol(u.score), "r")
    T(c, x + 6, y - 38, "cumplimiento", 6.4, F, INK2)
    T(c, x + 6, y - 46, "promedio, 2 semanas", 6.4, F, INK2)
    yy = y - 60
    T(c, x + 6, yy, "", 5.6, F, INK3)
    T(c, x + PANEL_W - 52, yy, "S1", 5.6, FB, INK3, "r")
    T(c, x + PANEL_W - 29, yy, "S2", 5.6, FB, INK3, "r")
    T(c, x + PANEL_W - 6, yy, "PRÓX.", 5.6, FB, ACCENT, "r")
    for k in KEYS:
        yy -= 15
        T(c, x + 6, yy + 3, SHORT[k], 6.2, F, INK2, maxw=PANEL_W - 82)
        for xo, r, g in ((52, u.r1[k], u.g1[k]), (29, u.r2[k], u.g2[k])):
            p = r / g if g > 0 else None
            T(c, x + PANEL_W - xo, yy + 5, fmt(r), 6.6, FB,
              scol(p) if p is not None else INK, "r")
            T(c, x + PANEL_W - xo, yy - 1.5, f"de {fmt(g)}", 4.8, F, INK3, "r")
        T(c, x + PANEL_W - 6, yy + 3, fmt(u.nx[k]), 6.8, FB, ACCENT, "r")


def opt_d_page(doc, title, sub, units, group, total, total_title):
    c = doc.c
    doc.start("Opción D · Clasificación por indicador", title, sub, OPT_COL["D"])
    h = (CONTENT_TOP - CONTENT_BOTTOM - 14 - 10) / 2
    for i, k in enumerate(KEYS):
        col, row = i % 4, i // 4
        panel(c, M + col * (PANEL_W + 10), CONTENT_TOP - row * (h + 10), h, k,
              units, group)
    summary_panel(c, M + 3 * (PANEL_W + 10), CONTENT_TOP - (h + 10), h, total,
                  total_title)
    doc.legend(CONTENT_BOTTOM - 4, ["barra: % de la meta en 2 semanas (raya = 100%)",
                                    "nombre en rojo = sin informe"])


def option_d(doc):
    m = doc.m
    opt_d_page(doc, "Total de la misión — las zonas en cada indicador",
               period_line(m), m["zone_units"], True, m["mission"],
               "Total de la misión")
    for zu in m["zone_units"]:
        _, members = m["zones"][zu.name]
        opt_d_page(doc, f"Zona {zu.name}", zone_sub(zu, m), members, False, zu,
                   f"Total zona {zu.name}")



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
        self.new = f"semana {which}" in (getattr(u, "new_weeks", None) or [])
        self.n_new = 0
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
    accent = OPT_COL["B"] if which == 2 else INK3
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
        if v.new and not group:
            box(c, M - 6, y + 2, 3, rh - 4, fill=ACCENT)
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
            line2 = f"informaron {v.filed}/{v.n}"
            T(c, xs, mid - 7, line2, 6, F, INK3)
            if v.n_new:
                T(c, xs + stringWidth(line2, F, 6) + 4, mid - 7,
                  f"{v.n_new} actualizado{'s' if v.n_new > 1 else ''}", 6, FB, ACCENT)
        else:
            x2 = xs
            if v.new:
                x2 += updated_tag(c, x2, mid - 7.5, 5.4) + 3
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
    for w in (1, 2):
        for v in zv[w]:
            v.n_new = sum(1 for sec in m["sectors"]
                          if sec.zone == v.name and f"semana {w}" in sec.new_weeks)
    mission = {w: WeekView(m["mission"], w, True) for w in (1, 2)}
    for w in (1, 2):
        mission[w].n_new = sum(v.n_new for v in zv[w])
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
            tv.n_new = zone_rank[w].n_new
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

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cached", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", choices=["B", "W"], default=None)
    ap.add_argument("--per-zone", action="store_true",
                    help="with --only W: one PDF per zone instead of one document")
    ap.add_argument("--baseline", default=None, help="an earlier dump.json to flag changes against")
    ap.add_argument("--week-end", default=None, help="Sunday ending week 2 (YYYY-MM-DD)")
    a = ap.parse_args()
    raw = (json.load(open(os.path.join(HERE, "dump.json"), encoding="utf-8"))
           if a.cached else fetch())
    if a.week_end:
        w2 = date.fromisoformat(a.week_end)
    else:
        today = date.today()
        w2 = today - timedelta(days=today.weekday() + 1)   # the last Sunday before today
    baseline = json.load(open(a.baseline, encoding="utf-8")) if a.baseline else None
    if "WEEKLY_FORM_RAW" in raw:
        n_live, diff, extra = check_against_weekly_ki(raw, ki_from_raw(raw))
        print(f"check: {n_live} WEEKLY_KI rows, {len(diff)} differ from the rebuild: {diff}")
        print(f"       not yet in WEEKLY_KI: {extra}")
    m = build_model(raw, w2, baseline)
    out = a.out or os.path.join(HERE, f"Clasificacion_KI_{w2.isoformat()}.pdf")

    # Page numbers for the cover's index: cover is 1, then 5 pages each for A,
    # B and D, and C has a mission page plus ceil(n/12) per zone.
    import math
    nz = len(m["zone_units"])
    c_pages = 1 + sum(math.ceil(len(m["zones"][z.name][1]) / 12) for z in m["zone_units"])
    starts = [2, 2 + (1 + nz), 2 + 2 * (1 + nz), 2 + 2 * (1 + nz) + c_pages]

    if a.only == "W" and a.per_zone:
        # One document per zone: <out stem>_<Zona>.pdf
        stem = out[:-4] if out.lower().endswith(".pdf") else out
        for zu in m["zone_units"]:
            path = f"{stem}_{zu.name.replace(' ', '_')}.pdf"
            zdoc = Doc(path, m)
            zdoc.c.setTitle(f"Zona {zu.name} — indicadores clave por sector")
            zdoc.weekly, zdoc.zone = True, zu.name
            cover(zdoc, None, show_options=False)
            weekly_pages(zdoc, zu.name)
            zdoc.save()
            print("PDF:", path, "pages:", zdoc.page)
        print("fetched", m["fetched"])
        return

    doc = Doc(out, m)
    if a.only == "W":
        doc.weekly = True
        cover(doc, None, show_options=False)
        weekly_pages(doc)
        doc.save()
        print("PDF:", out, "pages:", doc.page, "fetched", m["fetched"])
        return
    if a.only == "B":
        global B_KICKER
        B_KICKER = "PMG Compass · Indicadores clave"
        cover(doc, None, show_options=False)
        option_b(doc)
        doc.save()
        print("PDF:", out, "pages:", doc.page, "fetched", m["fetched"])
        print("updated:", [(u.name, u.new_weeks) for u in m["sectors"] if u.new_weeks])
        for zu in m["zone_units"]:
            print(f"{zu.rank}. {zu.name}: {pct_s(zu.score)}  inf {zu.f1}/{zu.n} {zu.f2}/{zu.n}")
        return
    cover(doc, starts)
    option_a(doc)
    assert doc.page + 1 == starts[1], (doc.page, starts)
    option_b(doc)
    option_c(doc)
    assert doc.page + 1 == starts[3], (doc.page, starts)
    option_d(doc)
    doc.save()

    print("PDF:", out, "pages:", doc.page)
    print("weeks:", m["w0"], m["w1"], m["w2"], "fetched", m["fetched"])
    for n in m["notes"]:
        print("NOTE:", n)
    for zu in m["zone_units"]:
        print(f"{zu.rank}. {zu.name}: {pct_s(zu.score)}  inf {zu.f1}/{zu.n} {zu.f2}/{zu.n}")
        for s in m["zones"][zu.name][1]:
            print(f"    {s.rank:2}. {s.name:24} {pct_s(s.score):>5}  f={s.f0}{s.f1}{s.f2}  tot={fmt(s.total)}")


if __name__ == "__main__":
    main()
