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

from app.analytics import finding_funnel as FF
from app.config import es_display

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
