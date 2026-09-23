"""The Tableau side of a report: what the stored export covers, and whether it
covers the period being asked about.

**Decision 32.** The finding section is allowed to be absent. A packet dated
November that silently shows August finding data is worse than a packet with no
finding section at all, so every figure drawn from the export states the window
it actually rests on, and a period the export cannot cover gets a refusal with
its reason rather than a number.

**The gate is coverage of the PERIOD, not the age of the export.** Those come
apart, and conflating them fails in both directions. "Traslado pasado" ended on
2026-09-06 and an export pulled a month late still covers every day of it — a
staleness warning there would be noise. "Semana pasada" against an export six
days behind covers one day of seven, and that single evening captioned as a
week is exactly what decision 32 exists to prevent. Age is a fact this module
reports (`Export.age_days`, the freshness strip) and never the thing it gates
on.

Pure: dataframes and dates in, dataclasses out. No Streamlit, no ReportLab, no
sheet access — same rule as the rest of `app/reports/`, and the reason the
whole gate can be tested without a browser or a Google credential.

See PLAN-2026-09-21-informes.md §4 step T1 and decisions 20, 24, 32, 34, 35.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.analytics import annual_baptisms as AB
from app.analytics import finding_funnel as FF
from app.config import es_display
from app.reports import periods as P

#: A window resting on less than this fraction of the period's elapsed days is
#: refused rather than clipped. The same floor as `periods.THIN_REPORTING_RATE`
#: and for the same reason: below it the figure stops being a thin reading of
#: the period and becomes a reading of some other, much shorter window wearing
#: the period's name.
#:
#: Measured 2026-09-21 against the live export (ends 2026-09-17): the six
#: periods cover 57%, 73%, 100%, 93%, 81% and 98% of their own days, so the
#: floor refuses none of them today. It bites when the export goes a week or
#: more behind, which is precisely when "Semana pasada" would otherwise print
#: one day of finding and call it a week.
MIN_WINDOW_COVERAGE = 0.25

#: Beyond this many days behind today, the export is called stale on the
#: freshness strip. `finding_funnel.EXPORT_FRESH_DAYS`, not a second number —
#: the Embudo page and the packet must not disagree about what "fresh" means.
FRESH_DAYS = FF.EXPORT_FRESH_DAYS


# ── What the export is ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Export:
    """The stored Finding Detail export, described rather than trusted.

    `first` and `last` are derived from the data's own found-dates, never from
    a configured floor: `finding_funnel.data_date_bounds` documents the
    hardcoded floor that once hid 86% of the rows, and this module must not
    reintroduce one.

    `uploaded_at` is a string because that is what the tab and the Drive blob
    store, and parsing it into a date would invite it to be used as the
    export's end. It is not: an export pulled today can end four days ago, and
    on the live data it does.
    """

    rows: int = 0
    first: date | None = None
    last: date | None = None
    uploaded_at: str = ""
    uploaded_by: str = ""

    @property
    def present(self) -> bool:
        return self.rows > 0 and self.last is not None

    def age_days(self, today: date) -> int:
        """Days between the export's last found-date and `today`, floored at 0."""
        return FF.export_age_days(self.last, today)

    def stale(self, today: date, fresh_days: int = FRESH_DAYS) -> bool:
        return FF.export_is_stale(self.last, today, fresh_days)

    def freshness_label(self, today: date) -> str:
        """The strip decision 32 makes mandatory: what the export holds, how
        far it reaches, and how far behind that leaves it.

        Says the last found-date out loud rather than only the age, because
        "hace 4 días" alone invites the reader to subtract it from today and
        get a different answer than the figures rest on.
        """
        if not self.present:
            return "sin exportación de Tableau"
        age = self.age_days(today)
        when = es_display.day_month(self.last, with_year=True)
        if age == 0:
            tail = "hasta hoy"
        elif age == 1:
            tail = "hasta ayer"
        else:
            tail = f"{es_display.integer(age)} días atrás"
        return (f"Exportación de Tableau: {es_display.integer(self.rows)} "
                f"personas, hasta el {when} ({tail})")

    def source_label(self) -> str:
        """Who pulled it and when, for the data note. The auto-sync writes
        `auto:tableau`; a hand upload writes an address."""
        if not self.uploaded_by and not self.uploaded_at:
            return ""
        who = ("sincronización automática"
               if self.uploaded_by.startswith("auto:") else self.uploaded_by)
        if who and self.uploaded_at:
            return f"{who}, {self.uploaded_at}"
        return who or self.uploaded_at


def read_export(det: pd.DataFrame, uploaded_by: str = "",
                uploaded_at: str = "") -> Export:
    """Describe a Detail frame. The frame is whatever `queries.get_tableau_detail`
    returned, including an empty one."""
    if det is None or det.empty:
        return Export(rows=0, uploaded_by=uploaded_by or "",
                      uploaded_at=uploaded_at or "")
    ev = FF.parse_dates(det, "event_date_selected").dropna()
    first = ev.min().date() if not ev.empty else None
    last = ev.max().date() if not ev.empty else None
    return Export(rows=int(len(det)), first=first, last=last,
                  uploaded_by=uploaded_by or "", uploaded_at=uploaded_at or "")


# ── What it covers ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Window:
    """The days a Tableau figure actually rests on, and how that differs from
    the period it is printed under.

    A window that is not `usable` carries `reason` and nothing else: the
    renderers print the reason where the block would have been, which is
    decision 32's refusal. A window that IS usable can still be shorter than
    its period — that is the ordinary case for anything in progress — and then
    `clipped` is True and `shortfall_label` is the caption that has to appear
    beside every figure drawn from it.
    """

    start: date | None = None
    end: date | None = None
    period_days: int = 0
    reason: str = ""

    @property
    def usable(self) -> bool:
        return self.start is not None and self.end is not None

    @property
    def days(self) -> int:
        if not self.usable:
            return 0
        return (self.end - self.start).days + 1

    @property
    def coverage(self) -> float | None:
        """Days covered over the period's elapsed days, or None with no period."""
        if not self.period_days:
            return None
        return self.days / self.period_days

    @property
    def clipped(self) -> bool:
        return self.usable and self.days < self.period_days

    @property
    def label(self) -> str:
        """`7 – 17 de sep de 2026` — the window itself, never the period's."""
        if not self.usable:
            return "—"
        return es_display.day_range(self.start, self.end)

    @property
    def shortfall_label(self) -> str:
        """"11 de 15 días del período" — why the window is short, in words.

        Empty when the window covers the whole period, so a caller can print
        it unconditionally and get nothing when there is nothing to say.
        """
        if not self.clipped:
            return ""
        return (f"{es_display.integer(self.days)} de "
                f"{es_display.integer(self.period_days)} días del período")

    @property
    def caption(self) -> str:
        """What goes under every Tableau block: the source, then the window,
        then the shortfall if there is one.

        Decision 34's `fuente: Tableau` is part of this string rather than
        left to each caller, so a block cannot be drawn without it.
        """
        bits = ["fuente: Tableau", self.label]
        if self.shortfall_label:
            bits.append(self.shortfall_label)
        return " · ".join(bits)


def clip(period, export: Export, *,
         floor: float = MIN_WINDOW_COVERAGE) -> Window:
    """The window Tableau can honestly answer `period` over.

    The period's ELAPSED window (`period.start`..`period.end`), not its full
    one: a transfer that runs to October has no finding data for October and
    measuring the export against days that have not happened would call every
    in-progress period a failure.

    Four outcomes, each with its own sentence:

    * no export at all → refused;
    * the period ends before the export begins, or begins after it ends →
      refused, because there is no overlap to draw;
    * the overlap is below `floor` of the period → refused, with the real
      coverage named. This is the case decision 32 was written for;
    * otherwise the overlap, clipped, with `clipped` telling the renderers to
      print the shortfall beside every figure.
    """
    days = getattr(period, "days", 0) or 0
    if not export.present or export.first is None:
        return Window(period_days=days,
                      reason="no hay ninguna exportación de Tableau guardada")

    start = max(period.start, export.first)
    end = min(period.end, export.last)
    if end < start:
        if period.end < export.first:
            when = es_display.day_month(export.first, with_year=True)
            return Window(period_days=days,
                          reason=("la exportación de Tableau empieza el "
                                  f"{when}, después de este período"))
        when = es_display.day_month(export.last, with_year=True)
        return Window(period_days=days,
                      reason=("la exportación de Tableau llega hasta el "
                              f"{when} y no alcanza este período"))

    window = Window(start=start, end=end, period_days=days)
    coverage = window.coverage
    if coverage is not None and coverage < floor:
        when = es_display.day_month(export.last, with_year=True)
        return Window(period_days=days,
                      reason=("la exportación de Tableau llega hasta el "
                              f"{when} y sólo cubre {window.shortfall_label}; "
                              "es muy poco para hablar del período"))
    return window


def preceding(window: Window) -> Window:
    """The equal-length window ending the day before this one begins.

    Equal length is the whole point, and it is why the comparison is taken
    from the CLIPPED window rather than from the period: holding eleven days
    of this transfer against forty-two days of the last one would print a
    collapse that is entirely the two windows being different sizes.

    An unusable window has no comparison; the caller prints no change at all
    rather than a change against nothing.
    """
    if not window.usable:
        return Window(reason=window.reason)
    start, end = FF.previous_window(window.start, window.end)
    return Window(start=start, end=end, period_days=window.days)


def clamp(window: Window, export: Export) -> Window:
    """A comparison window trimmed to what the export actually holds.

    `preceding` walks backwards off the front of the export for any period
    near its start, and a window of eleven days holding four days of data
    would read as a two-thirds collapse. Refused rather than trimmed when the
    trim would make the two sides different lengths — an unequal comparison is
    worse than no comparison, and decision 6 shows partial figures, never
    partial COMPARISONS drawn as if they were whole.
    """
    if not window.usable or not export.present or export.first is None:
        return window
    if window.start >= export.first and window.end <= export.last:
        return window
    return Window(period_days=window.period_days,
                  reason=("la exportación de Tableau no cubre la ventana de "
                          "comparación completa"))


# ── Whose rows they are ───────────────────────────────────────────────────────
#
# The export carries its own zone, district and area columns. Only the AREA one
# is ever used to decide whether a row belongs to a unit of this report, and
# the zone and district a figure is filed under are MISSION_ORG's — `scope.py`'s
# standing rule, which exists because those columns record where an area was
# when the row was written. The export's own district column disagrees with the
# roster about four district names today and it changes no figure in this
# packet, because nothing reads it.
#
# The one exception is the mission's all-ten-zone block (decision 24), where six
# of the zones have no roster to be reconciled against at all. There the
# export's zone column is the only authority there is, and the block says so.

AREA_COL = "latest_teaching_area_name"
ZONE_COL = "latest_zone_name"


def _names(det: pd.DataFrame, column: str) -> pd.Series:
    """A Detail column as stripped strings, or an empty Series if it is absent."""
    resolved = FF.resolve_col(det, column) if det is not None else None
    if resolved is None:
        return pd.Series(dtype=str)
    return det[resolved].astype(str).str.strip()


def in_window(det: pd.DataFrame, window: Window) -> pd.DataFrame:
    """The export's rows whose found-date falls inside `window`.

    An unusable window yields nothing rather than everything: a refused gate
    must not fall through to the whole 2.7-year export.
    """
    if det is None or det.empty or not window.usable:
        return pd.DataFrame(columns=getattr(det, "columns", None))
    return FF.filter_by_range(det, window.start, window.end)


def for_areas(det: pd.DataFrame, areas) -> pd.DataFrame:
    """The rows belonging to a roster unit — matched on AREA NAME, never on the
    export's own zone or district column.

    An export area name that is not on the roster is dropped here, which is
    the exclusion decision 35 describes; `reconcile` is what counts what was
    dropped so it can be printed instead of disappearing.
    """
    if det is None or det.empty:
        return det if det is not None else pd.DataFrame()
    wanted = {str(a).strip() for a in areas}
    return det[_names(det, AREA_COL).isin(wanted)]


@dataclass(frozen=True)
class Reconciliation:
    """Export area names against MISSION_ORG, and what the mismatch costs.

    Decision 35. Provo's own packet prints this ("12 area names … accounting
    for 52 attempts — about 0.6% of activity") and it is the sentence that
    makes the rest of the section safe to argue with: a reader who wonders
    whether a zone's total is short can find out exactly how short.

    `unknown` is export names inside the pilot zones that the roster does not
    carry, each with its row count — these are excluded from every
    roster-scoped figure. `missing` is the other direction: roster areas the
    export never names at all, which are not an exclusion but a silence, and a
    zone leader should know which of their areas produced no finding rows.
    """

    unknown: tuple[tuple[str, int], ...] = ()
    missing: tuple[str, ...] = ()
    scoped_rows: int = 0
    total_rows: int = 0

    @property
    def unknown_rows(self) -> int:
        return sum(n for _, n in self.unknown)

    @property
    def unknown_share(self) -> float | None:
        """Excluded rows as a fraction of the rows inside the pilot zones —
        the population they would have joined, not the whole export."""
        if not self.scoped_rows:
            return None
        return self.unknown_rows / self.scoped_rows

    @property
    def clean(self) -> bool:
        return not self.unknown and not self.missing

    @property
    def note(self) -> str:
        """The data-note sentence, or "" when there is nothing to report."""
        if self.clean:
            return ""
        bits = []
        if self.unknown:
            # Middots, not commas: "Huequen, Renaico & Tijeral 2" is one of
            # the three live names and a comma-separated list reads it as two.
            names = " · ".join(name for name, _ in self.unknown)
            share = self.unknown_share
            tail = (f" — {es_display.percent(share * 100, 2)} de la actividad "
                    f"de las zonas piloto" if share is not None else "")
            bits.append(
                f"{es_display.integer(len(self.unknown))} nombres de área de "
                f"Tableau no están en MISSION_ORG y quedan fuera de toda cifra "
                f"por unidad: {names}, con "
                f"{es_display.integer(self.unknown_rows)} personas{tail}.")
        if self.missing:
            bits.append(
                f"{es_display.integer(len(self.missing))} áreas del roster no "
                f"aparecen en la exportación: {', '.join(self.missing)}.")
        return " ".join(bits)


def reconcile(det: pd.DataFrame, roster: pd.DataFrame) -> Reconciliation:
    """Match the export's area names against the roster's, inside the pilot zones.

    Scoped to the zones MISSION_ORG actually knows about: the other six zones
    are not unmatched names, they are zones this pilot does not cover, and
    counting them as misses would report 57% of the mission as a data error.
    """
    if det is None or det.empty or roster is None or roster.empty:
        return Reconciliation(total_rows=0 if det is None else int(len(det)))

    areas = set(roster["Area_Name"].astype(str).str.strip())
    zones = set(roster["Zone"].astype(str).str.strip())
    in_pilot = det[_names(det, ZONE_COL).isin(zones)]
    found = _names(in_pilot, AREA_COL)

    counts = found[~found.isin(areas)].value_counts()
    unknown = tuple((str(name), int(n)) for name, n in counts.items() if name)
    return Reconciliation(
        unknown=unknown,
        missing=tuple(sorted(areas - set(found))),
        scoped_rows=int(len(in_pilot)),
        total_rows=int(len(det)),
    )


# ── The vocabulary ────────────────────────────────────────────────────────────
#
# Spanish for the things the export names in English. The stage and category
# strings are the ones `app/i18n/es.py` already carries, repeated here because
# importing that package pulls in Streamlit (P2's note on `es_display.py`, same
# reason). `test_report_tableau_blocks.py` asserts the two agree, so the packet
# and the Embudo page cannot drift apart without a test saying so.

STAGE_LABELS = {
    "Found":                  "Encontradas",
    "Contact Attempted":      "Intento de Contacto",
    "Successfully Contacted": "Contactadas con Éxito",
    "Being Taught":           "Recibiendo Lecciones",
    "Attended Church":        "Asistió a la Iglesia",
    "Baptism Date Set":       "Fecha de Bautismo Fijada",
    "Baptized":               "Bautizados",
    "Referred":               "Referidas",
}

CATEGORY_LABELS = {
    "Missionary":                  "Misioneros",
    "Member":                      "Miembros",
    "Media":                       "Medios",
    "Visitors Centers and Events": "Centros de visitantes y eventos",
    "Unknown":                     "Desconocido",
}

#: The finding sources the live export carries, translated. Nothing in the app
#: translated these before — the Embudo page prints them as written — and a
#: council packet is Spanish only (decision 3). Free text from Tableau, so an
#: unlisted value falls back to itself rather than to a placeholder: a source
#: the mission has never used before should appear, not disappear.
SOURCE_LABELS = {
    "Contacting in Public":              "Contacto en la calle",
    "Home to Home Contacting":           "Contacto casa por casa",
    "Through Person Being Taught":       "Por alguien que recibe lecciones",
    "Headquarters Paid Ad":              "Anuncio pagado de las oficinas",
    "Headquarters Local":                "Oficinas locales",
    "Headquarters Non-Paid Ad":          "Anuncio no pagado de las oficinas",
    "Facebook - Mission Ad":             "Facebook · anuncio de la misión",
    "Facebook - Mission and Zone Pages": "Facebook · páginas de misión y zona",
    "Facebook - Personal Profile":       "Facebook · perfil personal",
    "Member":                            "Miembro",
    "New Member":                        "Miembro nuevo",
    "Less Active":                       "Menos activo",
    "Sought out Church or Missionaries": "Buscó a la Iglesia o a los misioneros",
    "Visitors Centers and Events":       "Centros de visitantes y eventos",
    "Service":                           "Servicio",
    "English Class":                     "Clase de inglés",
    "Ward Council":                      "Consejo de barrio",
    "Church Activity":                   "Actividad de la Iglesia",
    "Chalkboard Activity":               "Actividad de pizarra",
    "Book of Mormon Experiment":         "Experimento del Libro de Mormón",
    "Family History":                    "Historia familiar",
    "Unknown":                           "Desconocido",
}


def stage_label(value: str) -> str:
    return STAGE_LABELS.get(str(value), str(value))


def category_label(value: str) -> str:
    return CATEGORY_LABELS.get(str(value), str(value))


def finding_source_label(value: str) -> str:
    return SOURCE_LABELS.get(str(value), str(value))


# ── How long a stage takes to fill ────────────────────────────────────────────
#
# The funnel is a COHORT reading: it takes the people FOUND in the window and
# asks how far each has since travelled. That is the right question, and it has
# one trap that would wreck a council packet if left alone — the bottom of the
# funnel is empty for a young cohort by construction, not by failure.
#
# Measured over the whole live export 2026-09-21, days from found to milestone
# (p75, among the people who reached it): contact attempted 6 · contacted 10 ·
# being taught 5 · attended church 33 · baptism date 52 · BAPTIZED 133. Over
# this transfer's eleven-day window exactly 1% of eventual baptisms have
# happened yet, so the stage reads 0 — beside a September baptism figure of 19
# on the same page, which is a flat contradiction nobody should have to
# reconcile.
#
# So a stage is called MATURE only when the window is at least as long as that
# stage's own p75 lag. An immature stage still prints its count — decision 25,
# no compression — and loses its conversion percentage, its direction and its
# eligibility to be named the funnel's worst step.
#
# p75 rather than the median because the median means half the eventual events
# have not happened yet, which is not a number to draw a conversion rate from.
# Measured from the export rather than hardcoded, so it tracks the mission's
# own pace; and it is conditioned on the people who DID reach the milestone,
# which biases it short — the direction p75 is there to compensate for.
MATURITY_QUANTILE = 0.75


def maturity_days(det: pd.DataFrame) -> dict:
    """`{English stage label: p75 days from found}` over the whole export.

    The whole export, never the window: the window is the thing being judged
    against this, and a fortnight asked how long a baptism takes would answer
    "at most a fortnight".
    """
    out = {}
    if det is None or det.empty:
        return out
    found = FF.parse_dates(det, "event_date_selected")
    for label, col in FF.FUNNEL_STAGES:
        if col is None:
            continue
        lag = (FF.parse_dates(det, col) - found).dt.days
        lag = lag[lag.notna() & (lag >= 0)]
        if len(lag):
            out[label] = float(lag.quantile(MATURITY_QUANTILE))
    return out


# ── The blocks ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Stage:
    """One step of the finding funnel, for one cohort."""

    label: str
    count: int
    before: int | None = None
    mature: bool = True
    lag_days: float | None = None

    @property
    def change(self) -> float | None:
        """Per cent against the equal-length window before it, or None.

        Only for a mature stage: an immature one compares two numbers that are
        both mostly unwritten, and a swing from one to three is not a 200%
        improvement in baptisms.
        """
        if not self.mature or self.before is None or self.before == 0:
            return None
        return (self.count - self.before) / self.before * 100


@dataclass(frozen=True)
class Share:
    """A slice of the channel mix, or one finding source."""

    label: str
    count: int
    before: int | None = None

    def share_of(self, total: int) -> float | None:
        return (self.count / total * 100) if total else None


@dataclass(frozen=True)
class UnitRow:
    """One zone, district or area in a Tableau ranking.

    `roster` is False for the six zones that run no Compass forms — decision
    24 puts them on the mission's page, and the row says which it is so that
    no reader takes a zone with no Compass figures for one that reported
    nothing.
    """

    name: str
    found: int
    contacted: int
    teaching: int
    roster: bool = True

    @property
    def contact_rate(self) -> float | None:
        return (self.contacted / self.found * 100) if self.found else None

    @property
    def teaching_rate(self) -> float | None:
        return (self.teaching / self.found * 100) if self.found else None


def funnel(det: pd.DataFrame, window: Window, *,
           before: pd.DataFrame | None = None,
           maturity: dict | None = None) -> tuple:
    """The seven stages for the cohort found in `window`, Spanish-labelled.

    `compute_funnel_stage_counts` reads "at least this far" rather than a bare
    per-column count, which is what keeps the funnel monotonic when a milestone
    is skipped — `finding_funnel` documents the bulge that taught it. This adds
    the maturity verdict and the comparison, and nothing else.
    """
    if det is None or det.empty:
        return ()
    counts = FF.compute_funnel_stage_counts(det)
    prior = FF.compute_funnel_stage_counts(before) if before is not None else {}
    lags = maturity or {}
    days = window.days
    out = []
    for label, _ in FF.FUNNEL_STAGES:
        lag = lags.get(label)
        out.append(Stage(
            label=stage_label(label),
            count=int(counts.get(label, 0)),
            before=(int(prior[label]) if label in prior else None),
            mature=(lag is None or days >= lag),
            lag_days=lag,
        ))
    return tuple(out)


def _counted(det: pd.DataFrame, column: str, labeller,
             before: pd.DataFrame | None = None, limit: int | None = None):
    """Value counts of one column as `Share` rows, biggest first."""
    if det is None or det.empty:
        return ()
    counts = _names(det, column).replace("", "Unknown").value_counts()
    prior = (_names(before, column).replace("", "Unknown").value_counts()
             if before is not None and not before.empty else None)
    rows = []
    for name, n in counts.items():
        if limit is not None and len(rows) >= limit:
            break
        rows.append(Share(
            label=labeller(name),
            count=int(n),
            before=(int(prior.get(name, 0)) if prior is not None else None),
        ))
    return tuple(rows)


def channel_mix(det: pd.DataFrame, before: pd.DataFrame | None = None) -> tuple:
    """Who found these people: missionaries, members, media, visitors' centres."""
    return _counted(det, "finding_category", category_label, before)


def top_sources(det: pd.DataFrame, before: pd.DataFrame | None = None,
                limit: int = 8) -> tuple:
    """The finding sources that actually produced people, biggest first."""
    return _counted(det, "finding_source", finding_source_label, before, limit)


def _unit_row(name: str, rows: pd.DataFrame, *, roster: bool = True) -> UnitRow:
    counts = FF.compute_funnel_stage_counts(rows)
    return UnitRow(name=name,
                   found=int(counts.get("Found", 0)),
                   contacted=int(counts.get("Successfully Contacted", 0)),
                   teaching=int(counts.get("Being Taught", 0)),
                   roster=roster)


def zone_rows(det: pd.DataFrame, pilot_zones=()) -> tuple:
    """Every zone the export knows, weakest first by contact rate (decision 24).

    Read off the export's OWN zone column, which is the only authority there is
    for the six zones MISSION_ORG does not carry. That is why this exists
    beside `unit_rows` rather than being the same function: the mission's
    ten-zone block is the one place in this report where the roster is not the
    authority, and the page says so.
    """
    if det is None or det.empty:
        return ()
    pilot = {str(z).strip() for z in pilot_zones}
    names = _names(det, ZONE_COL).replace("", "Unknown")
    rows = [_unit_row(str(zone), det[names == zone], roster=(zone in pilot))
            for zone in sorted(names.unique()) if zone]
    return tuple(sorted(rows, key=lambda r: (r.contact_rate is None,
                                             r.contact_rate or 0, r.name)))


def unit_rows(det: pd.DataFrame, units) -> tuple:
    """A roster unit's children, weakest first by contact rate.

    `units` are `Scope`s, so membership is MISSION_ORG's area list and a child
    that produced nothing keeps its row — a unit with no finding rows is a
    finding worth printing, not an absence to drop.
    """
    if det is None:
        return ()
    rows = [_unit_row(unit.name, for_areas(det, unit.areas)) for unit in units]
    return tuple(sorted(rows, key=lambda r: (r.found == 0,
                                             r.contact_rate is None,
                                             r.contact_rate or 0, r.name)))


# ── The year against its goal (M6) ────────────────────────────────────────────

@dataclass(frozen=True)
class Baptisms:
    """The mission's year of baptisms against the one annual goal it has.

    Decision 21. Two figures exist and they do not agree: TABLEAU_BAPTISMS
    carries the certified "Total People Baptized" and the weekly form carries
    what companionships typed in, which `queries.get_baptisms_actual` already
    documents as undercounting badly. This block is the certified one, always,
    and the page prints the form's own Key Indicator beside it under its own
    name rather than reconciling them into a single number.

    The current month is held apart from the certified series rather than
    appended to it. A month-to-date figure plotted as an ordinary point draws
    the year collapsing every time the packet is built mid-month — the same
    trap `get_mission_baptisms_by_month` was taught on 2026-09-19.
    """

    year: int
    goal: float | None = None
    certified: dict = None
    provisional: int | None = None
    provisional_through: date | None = None
    #: The selected period's own figure (decisions 41, 42) — the headline. The
    #: year above it is context: the pace, the projection and the month table
    #: stay on closed months exactly as before.
    period: "PeriodBaptisms" = None
    #: The year to today, certified: the closed months and the open one. The
    #: context tile beside a transfer's figure. None when the period is in a
    #: different year from today, where "so far this year" is not its year.
    year_to_date: "PeriodBaptisms" = None

    def __post_init__(self):
        object.__setattr__(self, "certified", dict(self.certified or {}))

    @property
    def cumulative(self) -> list:
        return AB.cumulative(self.certified, self.year)

    @property
    def pace(self) -> list | None:
        return AB.goal_pace(self.goal)

    @property
    def months(self) -> int:
        """How many months of the year are certified."""
        return AB.months_covered(self.cumulative)

    @property
    def total(self) -> int | None:
        """Baptisms so far this year, certified only."""
        n = self.months
        return int(self.cumulative[n - 1]) if n else None

    @property
    def gap(self) -> float | None:
        """How far ahead of the goal's pace the year stands. Negative is short."""
        return AB.pace_gap(self.cumulative, self.goal)

    @property
    def landing(self) -> dict | None:
        """Where the year ends if the certified months are representative."""
        return AB.landing_estimate(self.cumulative, self.goal)

    @property
    def attainment(self) -> float | None:
        """The year's total as a percentage of the whole annual goal.

        The whole goal, not the goal to date: a council asks how much of the
        year's work is done, and the pace comparison is `gap`'s job.
        """
        total = self.total
        if total is None or not self.goal:
            return None
        return total / float(self.goal) * 100

    @property
    def certified_label(self) -> str:
        """"319 bautismos certificados hasta agosto" — the figure and its reach."""
        total = self.total
        if total is None:
            return "sin meses certificados"
        month = es_display.MONTHS[self.months - 1] if self.months else ""
        return (f"{es_display.integer(total)} bautismos certificados "
                f"hasta {month}")

    @property
    def provisional_label(self) -> str:
        """The open month, said as the open thing it is, or ""."""
        if self.provisional is None:
            return ""
        through = (f" hasta el {es_display.day_month(self.provisional_through)}"
                   if self.provisional_through else "")
        return (f"{es_display.integer(self.provisional)} más en el mes en "
                f"curso{through}, sin cerrar")


# ── The period's own baptisms (decisions 41, 42) ──────────────────────────────
#
# Zackary, 2026-09-23: "if it's for transfer up to date, put all of them, if
# it's for the month, just include the baptisms up to the close of the month."
#
# Every answer here is CERTIFIED — TABLEAU_BAPTISMS for the month periods,
# TABLEAU_BAPTISM_WINDOWS (which the nightly job fills, decision 42) for the
# rest. The detail export's confirmation dates are never counted: R0.1 measured
# them 0-11% under the certified figure once a month closes, and decision 42
# chose a certified figure or none.

@dataclass(frozen=True)
class PeriodBaptisms:
    """The certified baptisms for exactly the days of the selected period, or
    the reason there is no such figure.

    `window` is the days the figure covers, measured against the period's
    elapsed days, so a capture one night behind reads "16 de 17 días del
    período" beside its number rather than passing for the whole period.

    `closed` and `open_count` are filled for "Año" only, which is the one figure
    built from two captures: the closed months, and the open month to date.
    Both are TABLEAU_BAPTISMS rows covering adjoining days, so adding them is
    counting one source's days once each — not the certified-plus-something-
    else sum decision 21 forbids.
    """

    count: int | None = None
    window: Window = None
    closed: int | None = None
    closed_months: int = 0
    open_count: int | None = None
    open_month: str = ""

    @property
    def present(self) -> bool:
        return (self.count is not None and self.window is not None
                and self.window.usable)

    @property
    def reason(self) -> str:
        if self.present:
            return ""
        return self.window.reason if self.window is not None else ""

    @property
    def caption(self) -> str:
        """`cifra certificada · fuente: Tableau · 7 de sep - 23 de sep de 2026`,
        then the shortfall when the capture stops short of the period."""
        if not self.present:
            return "cifra certificada · fuente: Tableau"
        return "cifra certificada · " + self.window.caption

    def sentence(self, period_label: str) -> str:
        """What the figure covers, in words — or why there is none.

        Both renderers print this under the headline, so the page and the
        packet cannot explain the same figure two ways. A period with no
        certified capture prints no figure at all rather than a different one
        (decision 42), and says so, so the dash is not read as a period with
        no baptisms.
        """
        if not self.present:
            why = self.reason
            return (f"No hay cifra certificada de bautismos para "
                    f"{period_label}{': ' + why if why else ''}. No se "
                    f"imprime otra en su lugar: los registros de Tableau "
                    f"quedan por debajo de la cifra certificada y el "
                    f"formulario semanal no siempre se anota (decisión 42).")
        days = self.window
        cross = days.start.year != days.end.year
        out = (f"Bautismos certificados por Tableau entre el "
               f"{es_display.day_month(days.start, with_year=cross)} y el "
               f"{es_display.day_month(days.end, with_year=True)}")
        if days.clipped:
            out += (f": {days.shortfall_label}, porque la última captura "
                    f"certificada llega hasta ahí")
        out += "."
        if self.composition:
            out += f" Son {self.composition}."
        return out

    @property
    def composition(self) -> str:
        """For "Año": which part is closed and which is still open, or ""."""
        if not self.present or self.open_count is None or self.closed is None:
            return ""
        month = es_display.MONTHS[int(self.open_month[5:7]) - 1]
        return (f"{es_display.integer(self.closed)} de meses cerrados y "
                f"{es_display.integer(self.open_count)} de {month}, que todavía "
                f"no cierra")


def _month_bounds(key: str) -> tuple[date, date] | None:
    try:
        first = date(int(key[:4]), int(key[5:7]), 1)
    except (ValueError, TypeError):
        return None
    nxt = date(first.year + first.month // 12, first.month % 12 + 1, 1)
    return first, date.fromordinal(nxt.toordinal() - 1)


def _captures(certified: dict, open_month: tuple, windows) -> list:
    """Every certified figure there is, as `(start, end, count)`."""
    out = [(s, e, int(n)) for s, e, n in (windows or ())]
    for key, n in (certified or {}).items():
        bounds = _month_bounds(key)
        if bounds and n is not None:
            out.append((bounds[0], bounds[1], int(n)))
    month, n, through = (tuple(open_month) + (None, None, None))[:3]
    bounds = _month_bounds(month) if month else None
    if bounds and n is not None and through is not None:
        out.append((bounds[0], through, int(n)))
    return out


def _refused(period, reason: str) -> PeriodBaptisms:
    return PeriodBaptisms(window=Window(period_days=period.days, reason=reason))


def _year_to_date(period, certified: dict, open_month: tuple,
                  floor: float) -> PeriodBaptisms:
    """"Año": the closed months, plus the open month's capture when it is the
    month right after them."""
    year = period.start.year
    series = AB.cumulative({k: v for k, v in (certified or {}).items()
                            if str(k).startswith(f"{year:04d}-")}, year)
    n = AB.months_covered(series)
    closed = int(series[n - 1]) if n else None
    end = _month_bounds(f"{year:04d}-{n:02d}")[1] if n else None

    month, count, through = (tuple(open_month or ()) + (None, None, None))[:3]
    open_count, open_key = None, ""
    if (n < 12 and month == f"{year:04d}-{n + 1:02d}" and count is not None
            and through is not None):
        open_count, open_key, end = int(count), month, through

    if closed is None and open_count is None:
        return _refused(period, f"TABLEAU_BAPTISMS no tiene ninguna captura "
                                f"de {year}")
    window = Window(start=period.start, end=min(end, period.end),
                    period_days=period.days)
    if window.coverage is not None and window.coverage < floor:
        return _refused(period, f"la captura certificada cubre sólo "
                                f"{window.shortfall_label}")
    return PeriodBaptisms(count=(closed or 0) + (open_count or 0),
                          window=window, closed=closed, closed_months=n,
                          open_count=open_count, open_month=open_key)


def period_baptisms(period, *, certified: dict, open_month: tuple = (),
                    windows=(), floor: float = MIN_WINDOW_COVERAGE
                    ) -> PeriodBaptisms:
    """The certified figure for `period`'s own days, or its refusal.

    Looked up by DAYS, not by period name: a capture answers when it starts on
    the period's first day and ends on or before its last, and the latest such
    capture wins. So "Mes calendario" is answered by the month's own capture,
    a transfer by its window capture, and a capture one night behind answers
    with its own shorter window and says so. Below `floor` of the period — the
    same 25% the finding section uses — the figure would be some other, much
    shorter window wearing the period's name, and it is refused.
    """
    if period.key == P.YEAR:
        return _year_to_date(period, certified, open_month, floor)

    fits = [c for c in _captures(certified, open_month, windows)
            if c[0] == period.start and c[1] <= period.end]
    if not fits:
        return _refused(period, "la sincronización nocturna todavía no ha "
                                "capturado la cifra certificada de estos días")
    start, end, count = max(fits, key=lambda c: c[1])
    window = Window(start=start, end=end, period_days=period.days)
    if window.coverage is not None and window.coverage < floor:
        return _refused(period, f"la última captura certificada cubre sólo "
                                f"{window.shortfall_label}")
    return PeriodBaptisms(count=count, window=window)


# ── One unit's finding section ────────────────────────────────────────────────

@dataclass(frozen=True)
class Block:
    """Everything a unit's finding pages need, or the reason there are none.

    `ReportModel.tableau` holds one of these. A block whose `window` is not
    usable carries nothing but the refusal, and both renderers print the
    reason where the section would have been — decision 32, and the reason
    the packet's page count is generated rather than fixed (§5 risk 2).
    """

    export: Export
    window: Window
    before: Window = None
    stages: tuple = ()
    mix: tuple = ()
    sources: tuple = ()
    units: tuple = ()
    reconciliation: Reconciliation = None
    baptisms: Baptisms = None
    #: True only for the mission's block, which covers every zone the export
    #: knows rather than the roster's four (decision 24).
    whole_mission: bool = False
    #: What `units` are, for the ranking's heading: "zonas", "distritos", "áreas".
    unit_noun: str = ""

    @property
    def present(self) -> bool:
        return self.window is not None and self.window.usable

    @property
    def reason(self) -> str:
        return "" if self.present else (self.window.reason if self.window else "")

    @property
    def found(self) -> int:
        return self.stages[0].count if self.stages else 0

    @property
    def scope_note(self) -> str:
        """The sentence that keeps decision 34 true on the page.

        The mission's block covers all ten zones while every form-sourced
        figure in this packet covers four. Nothing else in the document
        changes population between one page and the next, so it is said
        outright rather than left to a footnote.
        """
        if self.whole_mission:
            return ("Esta sección cubre las 10 zonas de la misión, no sólo "
                    "las 4 del piloto de Compass. Ninguna cifra de Tableau se "
                    "suma con una cifra de los formularios.")
        return ("Áreas del roster de MISSION_ORG, emparejadas por nombre de "
                "área; la zona y el distrito son los del roster, no los de "
                "Tableau.")

    @property
    def maturity_note(self) -> str:
        """Why the bottom of a young funnel is empty, in one sentence."""
        young = [s for s in self.stages if not s.mature]
        if not young:
            return ""
        names = " · ".join(s.label.lower() for s in young)
        return (f"{names.capitalize()} tardan más que la ventana en ocurrir, "
                f"así que van sin porcentaje ni dirección: esa cohorte aún no "
                f"ha tenido tiempo. Los bautismos reales del período están en "
                f"la página de bautismos, no aquí.")


def build_block(det: pd.DataFrame, export: Export, period, *,
                areas=None, units=(), unit_noun: str = "",
                whole_mission: bool = False, reconciliation: Reconciliation = None,
                baptisms: Baptisms = None, maturity: dict = None,
                window: Window = None, before: Window = None) -> Block:
    """One unit's finding section, gated first and computed only if it passes.

    `areas` is None for the mission's whole-export block and the unit's roster
    areas everywhere else. `window` and `before` are passed in by the model,
    which resolves them once for all 63 scopes rather than 63 times.
    """
    window = window if window is not None else clip(period, export)
    if not window.usable:
        return Block(export=export, window=window, before=before,
                     reconciliation=reconciliation, baptisms=baptisms,
                     whole_mission=whole_mission, unit_noun=unit_noun)

    if before is None:
        before = clamp(preceding(window), export)
    now_rows = in_window(det, window)
    prior_rows = in_window(det, before) if before.usable else None
    if areas is not None:
        now_rows = for_areas(now_rows, areas)
        prior_rows = for_areas(prior_rows, areas) if prior_rows is not None else None

    return Block(
        export=export,
        window=window,
        before=before,
        stages=funnel(now_rows, window, before=prior_rows, maturity=maturity),
        mix=channel_mix(now_rows, prior_rows),
        sources=top_sources(now_rows, prior_rows),
        units=units,
        reconciliation=reconciliation,
        baptisms=baptisms,
        whole_mission=whole_mission,
        unit_noun=unit_noun,
    )
