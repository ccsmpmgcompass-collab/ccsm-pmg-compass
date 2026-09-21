"""When a report is about — and how honestly it can be compared to before.

Six periods, in the order the picker offers them (decision 5), defaulting to
"Este traslado". Each resolves to a day window AND the list of complete
week-ending Sundays inside it, because this report reads two sources with two
rhythms: DAILY_LOG is a day at a time, WEEKLY_KI is a Mon–Sun week keyed by its
closing Sunday.

**The rule for weekly data in any window is: a week belongs to the window when
its ENDING SUNDAY falls inside it.** Every alternative is worse. Splitting a
week's totals across a month boundary invents activity that was never reported
that way, and counting a week by its Monday would file the week of 31 August –
6 September under August, where five of its seven days did not happen. The rule
costs nothing on a transfer cycle, which starts on a Monday and ends on a
Sunday, and only shows itself on "Mes calendario" and "Año".

A week is only ever counted once it has FINISHED — `last_complete_week()`, which
is `area_helpers.latest_due_sunday` — so an in-progress week never drags a
period's totals down. That is the same guard `select_reporting_week` exists for:
on 2026-08-20 the Panel's tiles read 2 of 43 areas because nothing stopped them
using the current week.

**Comparisons degrade visibly, by construction** (§1.3). The twin of an
in-progress period is the matching PART of the period before it, never the
whole of it — two weeks into a transfer, "Traslado pasado" means that
transfer's first two weeks (decision 7), not all six. And a window is never
silently prorated to cover its gaps: `week_coverage()` reports how many of the
weeks actually carry data, and its `label` is the "4 de 6 semanas" caption
decision 6 requires beside any partial comparison.

Two comparison windows are offered rather than one — see COMPARE_KEYS — because
on CCSM today the period's own twin is largely empty and the weeks immediately
before it are not.

Pure: dates in, dataclasses out. The transfer cycles are handed in rather than
read here, for the same reason `breakdowns_engine._kpi_period_bounds` takes its
`transfers` argument — a sheet read inside would make this untestable and
un-reusable. `load_cycles()` is the one impure helper.

See PLAN-2026-09-21-informes.md §1.3 and §4 step R1.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Mapping

from app.config import es_display
from app.utils.area_helpers import latest_due_sunday

# ── The six periods ───────────────────────────────────────────────────────────

LAST_WEEK = "last_week"
THIS_TRANSFER = "this_transfer"
LAST_TRANSFER = "last_transfer"
LAST_6_WEEKS = "last_6_weeks"
CALENDAR_MONTH = "calendar_month"
YEAR = "year"

#: Display order, exactly as decision 5 lists them.
PERIOD_KEYS = (LAST_WEEK, THIS_TRANSFER, LAST_TRANSFER,
               LAST_6_WEEKS, CALENDAR_MONTH, YEAR)

#: Spanish only, screen and packet (decision 3). The labels live here rather
#: than in either renderer so the PDF and the page cannot drift apart.
PERIOD_LABELS = {
    LAST_WEEK: "Semana pasada",
    THIS_TRANSFER: "Este traslado",
    LAST_TRANSFER: "Traslado pasado",
    LAST_6_WEEKS: "Últimas 6 semanas",
    CALENDAR_MONTH: "Mes calendario",
    YEAR: "Año",
}

#: The transfer is the unit the mission plans and is judged in — a week is a
#: reporting rhythm and a month is an accident of the calendar. Same reasoning
#: that put the transfer first in `breakdowns_engine._KPI_PERIODS`.
DEFAULT_PERIOD = THIS_TRANSFER

#: How many weeks "Últimas 6 semanas" holds. Six because that is a transfer
#: cycle's length, so the rolling window and the planning unit are the same
#: size and can be read against each other.
ROLLING_WEEKS = 6

#: Below this share of possible area-weeks, a window is standing on one or two
#: areas rather than on a unit. `Coverage.thin` marks it; nothing hides it.
THIN_REPORTING_RATE = 0.25

# Why a comparison window has the shape it has. Renderers use this to caption
# the chip; `NO_COMPARISON` carries a reason instead.
SAME_WEEKS_ELAPSED = "same_weeks_elapsed"
SAME_DAYS_ELAPSED = "same_days_elapsed"
PRECEDING_WEEKS = "preceding_weeks"
PREVIOUS = "previous"
NO_COMPARISON = "none"

# ── What to compare against ───────────────────────────────────────────────────
#
# Two answers, because on CCSM today the obvious one is empty. The period's own
# twin — the transfer before this transfer, the month before this month — is
# what the mission plans in, and it is what decision 7 specifies. But WEEKLY_KI
# only starts 2026-08-16, so two weeks into 2026-6 that twin is the first two
# weeks of 2026-5, of which one holds a single area and the other holds nothing
# (§1.3). The comparison that is honestly available TODAY is the two weeks
# immediately before transfer day against the two since — which measures the
# transfer-day discontinuity, a different and genuinely interesting question.
#
# So the "Comparar contra" pills (§3.1) offer both, and `available_comparisons`
# drops the second when it would resolve to the same window as the first.

COMPARE_PRIOR = "prior_period"
COMPARE_PRECEDING = "preceding_weeks"

COMPARE_KEYS = (COMPARE_PRIOR, COMPARE_PRECEDING)

COMPARE_LABELS = {
    COMPARE_PRIOR: "Período anterior",
    COMPARE_PRECEDING: "Semanas anteriores",
}


# ── Week arithmetic ───────────────────────────────────────────────────────────

def week_end(day: date) -> date:
    """The Sunday that closes the Mon–Sun week `day` falls in.

    Sunday returns itself. This is the key WEEKLY_KI rows are written under
    (`CCSM_Agent5A.gs` rolls back to Monday and stamps the Sunday).
    """
    return day + timedelta(days=(6 - day.weekday()))


def last_complete_week(today: date) -> date:
    """The most recent week-ending Sunday whose week has finished.

    Delegates to `area_helpers.latest_due_sunday` rather than keeping a second
    copy of the rule — including its "if today IS Sunday, this week is not done
    yet" step back, which is the difference between a period ending on a Sunday
    counting that Sunday's half-reported week and not.
    """
    return latest_due_sunday(datetime.combine(today, time(12, 0)))


def weeks_ending_in(start: date, end: date) -> tuple[date, ...]:
    """Every week-ending Sunday inside [start, end], oldest first.

    Both ends inclusive. Empty when the window closes before its first Sunday —
    a four-day window from a Monday holds no complete week, and saying so is
    the honest answer.
    """
    if start is None or end is None or end < start:
        return ()
    out, sunday = [], week_end(start)
    while sunday <= end:
        out.append(sunday)
        sunday += timedelta(days=7)
    return tuple(out)


def complete_weeks(start: date, end: date, today: date) -> tuple[date, ...]:
    """`weeks_ending_in`, minus any week that has not finished yet."""
    if start is None or end is None:
        return ()
    return weeks_ending_in(start, min(end, last_complete_week(today)))


def _shift_year(day: date, years: int) -> date:
    """`day` the same number of years back, 29 February clamped to the 28th."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, month=2, day=28)


def _month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


# ── Transfer cycles ───────────────────────────────────────────────────────────

def load_cycles() -> list[dict]:
    """TRANSFER_SCHEDULE as `{number, start, end, weeks, status}`, oldest first.

    The one impure function here. `transfer_helpers.transfer_cycles()` owns the
    rule that a cycle ends the day before the next one starts, so a schedule
    recording a short or long cycle is described as it really was.
    """
    from app.utils.transfer_helpers import transfer_cycles
    return transfer_cycles()


def cycle_at(cycles: list[dict], today: date, offset: int = 0) -> dict | None:
    """The cycle `offset` back from the one `today` falls in, or None.

    The pure twin of `transfer_helpers.transfer_window`, which answers the same
    question but reads the sheet itself. Same rule for "current": the latest
    cycle that has STARTED, whatever its Status says — so the row scheduled for
    2026-10-19 becomes current on 2026-10-19 without anyone flipping a flag.

    None when the schedule does not reach that far back, which is the honest
    answer for "the transfer before last" on a mission two cycles old. The
    caller drops the period from the picker rather than offering one that
    resolves to nothing.
    """
    started = [i for i, c in enumerate(cycles or [])
               if c.get("start") and c["start"] <= today]
    if not started:
        return None
    idx = started[-1] - offset
    if idx < 0 or idx >= len(cycles):
        return None
    return cycles[idx]


def transfer_boundaries(cycles: list[dict], start: date,
                        end: date) -> tuple[tuple[date, str], ...]:
    """Cycle starts inside a window, as `(date, cycle number)` — decision 9.

    Every time axis in this report draws these as a dashed rule with the cycle
    number beside it, so a reader can see that a step in a line is a transfer
    and not a collapse.

    A cycle starting exactly on the window's own first day is excluded: a rule
    drawn on the axis edge is noise, and "Este traslado" would otherwise carry
    one on every chart. On a weekly axis the date falls BETWEEN two Sundays —
    2026-09-07 sits between the weeks ending 09-06 and 09-13 — and placing it
    there is the renderer's business, not this function's.
    """
    out = [(c["start"], str(c.get("number") or ""))
           for c in (cycles or [])
           if c.get("start") and start < c["start"] <= end]
    return tuple(sorted(out))


# ── A period ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Period:
    """One window of time, described as days and as complete weeks.

    ``end`` is where the window stops TODAY; ``full_end`` is where it stops
    when it is over. They differ only while a period is in progress, and
    keeping both is what lets a card read "progress toward this transfer's
    goal" instead of silently lowering the bar to a fortnight's worth of it —
    the rule `_kpi_period_bounds` already applies to "This Month So Far".

    ``weeks`` holds only FINISHED weeks. ``full_weeks`` is how many the period
    will hold when it closes, so the two together say "semana 2 de 6" without
    anyone having to divide dates.
    """

    key: str
    label: str
    start: date
    end: date
    weeks: tuple[date, ...]
    full_end: date
    full_weeks: int
    transfer: str | None = None

    @property
    def in_progress(self) -> bool:
        return self.end < self.full_end

    @property
    def weeks_elapsed(self) -> int:
        return len(self.weeks)

    @property
    def days(self) -> int:
        """Days elapsed in the window, both ends inclusive."""
        return (self.end - self.start).days + 1

    @property
    def window_label(self) -> str:
        """`7 de sep - 18 de oct de 2026` — the window, in words.

        The FULL window, not the elapsed one: a running head reading
        "7 de sep - 21 de sep" on a transfer that runs to 18 October would say
        the transfer is over. How far through it we are is `progress_label`'s
        sentence, and the two are printed side by side.
        """
        return es_display.day_range(self.start, self.full_end)

    @property
    def elapsed_label(self) -> str:
        """The window that has actually happened, for a figure's caption."""
        return es_display.day_range(self.start, self.end)

    @property
    def progress_label(self) -> str:
        """"2 de 6 semanas completas" — how far through the period we are.

        Says COMPLETAS out loud because the same screen carries a second,
        equally true count: `ki_drilldown` reads "semana 3 de 6", meaning the
        week today falls in, while this counts the weeks that have finished.
        Two weeks into a transfer both are right and "semana 2 de 6" beside
        "semana 3 de 6" reads like one of them is wrong.

        This is also NOT the same question as `Coverage.label`, which is how
        many of those elapsed weeks anyone actually reported. A period can be
        two weeks into six with both of them fully reported; conflating the two
        is how a report ends up claiming a third of a transfer is the whole
        of it.
        """
        noun = "semana completa" if self.full_weeks == 1 else "semanas completas"
        return f"{self.weeks_elapsed} de {self.full_weeks} {noun}"


@dataclass(frozen=True)
class Comparison:
    """The window a period is held against, or why there is not one.

    ``kind`` is one of SAME_WEEKS_ELAPSED, SAME_DAYS_ELAPSED, PREVIOUS or
    NO_COMPARISON. ``reason`` is filled only for NO_COMPARISON and is the
    Spanish the `sin comparación` chip shows.
    """

    period: Period | None
    kind: str
    reason: str = ""

    def __bool__(self) -> bool:
        return self.period is not None


def _period(key: str, label: str, start: date, end: date, today: date, *,
            full_end: date | None = None, transfer: str | None = None) -> Period:
    """Fill in the derived fields once, so no caller computes weeks by hand."""
    full_end = full_end or end
    return Period(
        key=key, label=label, start=start, end=end,
        weeks=complete_weeks(start, end, today),
        full_end=full_end,
        full_weeks=len(weeks_ending_in(start, full_end)),
        transfer=transfer,
    )


def _cycle_label(cycle: dict | None, fallback: str) -> str:
    """A cycle's number when the schedule gives one, else a plain name.

    Transfer_Number is a LABEL with no enforced format — CCSM's read "2026-4",
    "2026-5" — and a mission that leaves the column blank still gets a period
    it can name (the same reading `get_recent_transfer_dates` documents).
    """
    number = str((cycle or {}).get("number") or "").strip()
    return number or fallback


def resolve(key: str, today: date,
            cycles: list[dict] | None = None) -> Period | None:
    """One of PERIOD_KEYS as a window, or None when it cannot be built.

    None only ever means "the schedule does not reach": a mission whose
    TRANSFER_SCHEDULE holds one cycle has no "Traslado pasado", and the picker
    hides the option rather than offering an empty one. Every calendar period
    always resolves.
    """
    cycles = cycles or []

    if key == LAST_WEEK:
        end = last_complete_week(today)
        return _period(key, PERIOD_LABELS[key], end - timedelta(days=6), end, today)

    if key == THIS_TRANSFER:
        cur = cycle_at(cycles, today, 0)
        if not cur:
            return None
        return _period(key, _cycle_label(cur, PERIOD_LABELS[key]),
                       cur["start"], min(today, cur["end"]), today,
                       full_end=cur["end"], transfer=cur.get("number"))

    if key == LAST_TRANSFER:
        prev = cycle_at(cycles, today, 1)
        if not prev:
            return None
        return _period(key, _cycle_label(prev, PERIOD_LABELS[key]),
                       prev["start"], prev["end"], today,
                       transfer=prev.get("number"))

    if key == LAST_6_WEEKS:
        end = last_complete_week(today)
        start = end - timedelta(weeks=ROLLING_WEEKS - 1, days=6)
        return _period(key, PERIOD_LABELS[key], start, end, today)

    if key == CALENDAR_MONTH:
        start = today.replace(day=1)
        return _period(key, PERIOD_LABELS[key], start, today, today,
                       full_end=_month_end(today))

    if key == YEAR:
        start = date(today.year, 1, 1)
        return _period(key, str(today.year), start, today, today,
                       full_end=date(today.year, 12, 31))

    return None


def comparison_for(period: Period, today: date,
                   cycles: list[dict] | None = None,
                   against: str = COMPARE_PRIOR) -> Comparison:
    """The window `period` is honestly comparable to.

    "Honestly" is the whole job. Three days into September, holding 1–3
    September against the whole of August is not a comparison but arithmetic
    guaranteed to report a collapse; two weeks into a transfer, holding those
    two weeks against a completed six-week cycle is the same mistake at a
    larger scale. So an in-progress period is always twinned with the matching
    PART of the period before it — by weeks for the transfer periods
    (decision 7), by days for the calendar ones.

    ``against`` picks which pill is lit: COMPARE_PRIOR is that twin,
    COMPARE_PRECEDING is the same number of complete weeks immediately before
    this period began.

    A twin that reaches back before the mission's records is still returned.
    The caller sees `week_coverage` report zero weeks reported and says "sin
    comparación", which is the truth; clamping the window here would instead
    quietly shorten it and compare two different spans.
    """
    cycles = cycles or []

    if against == COMPARE_PRECEDING:
        return _preceding_weeks(period, today)

    if period.key == LAST_WEEK:
        end = period.end - timedelta(days=7)
        return Comparison(
            _period(period.key, "Semana anterior",
                    end - timedelta(days=6), end, today),
            PREVIOUS)

    if period.key == LAST_6_WEEKS:
        end = period.start - timedelta(days=1)
        start = end - timedelta(weeks=ROLLING_WEEKS - 1, days=6)
        return Comparison(
            _period(period.key, f"{ROLLING_WEEKS} semanas anteriores",
                    start, end, today),
            PREVIOUS)

    if period.key in (THIS_TRANSFER, LAST_TRANSFER):
        # One further back than the period itself: "Este traslado" compares
        # against the last one, "Traslado pasado" against the one before it.
        offset = 1 if period.key == THIS_TRANSFER else 2
        prev = cycle_at(cycles, today, offset)
        if not prev:
            return Comparison(
                None, NO_COMPARISON,
                "El calendario de traslados no llega tan atrás.")
        elapsed = period.weeks_elapsed
        if elapsed == 0:
            return Comparison(
                None, NO_COMPARISON,
                "Este traslado todavía no tiene una semana completa.")
        prev_weeks = weeks_ending_in(prev["start"], prev["end"])[:elapsed]
        if not prev_weeks:
            return Comparison(
                None, NO_COMPARISON,
                "El traslado anterior no tiene semanas completas.")
        # Same number of weeks elapsed, counted from that cycle's own start —
        # so a six-week cycle two weeks in is held against the first two weeks
        # of the cycle before it, never against all six.
        whole = len(prev_weeks) == len(weeks_ending_in(prev["start"], prev["end"]))
        suffix = "" if whole else f" (primeras {len(prev_weeks)} semanas)"
        return Comparison(
            _period(period.key,
                    _cycle_label(prev, "Traslado anterior") + suffix,
                    prev["start"], prev_weeks[-1], today,
                    transfer=prev.get("number")),
            PREVIOUS if whole else SAME_WEEKS_ELAPSED)

    if period.key == CALENDAR_MONTH:
        # Same elapsed days of last month. A month shorter than the elapsed
        # window (31 March against February) clamps at its own last day rather
        # than spilling forward into days already counted — the rule
        # `_kpi_prior_bounds` applies to "This Month So Far".
        last_day_prev = period.start - timedelta(days=1)
        start = last_day_prev.replace(day=1)
        end = min(start + timedelta(days=period.days - 1), last_day_prev)
        label = "Mes anterior" if end == last_day_prev else \
            f"Mes anterior (primeros {(end - start).days + 1} días)"
        return Comparison(
            _period(period.key, label, start, end, today,
                    full_end=last_day_prev),
            PREVIOUS if end == last_day_prev else SAME_DAYS_ELAPSED)

    if period.key == YEAR:
        start = date(period.start.year - 1, 1, 1)
        end = _shift_year(period.end, -1)
        return Comparison(
            _period(period.key, str(start.year), start, end, today,
                    full_end=date(start.year, 12, 31)),
            PREVIOUS if not period.in_progress else SAME_DAYS_ELAPSED)

    return Comparison(None, NO_COMPARISON, "Sin comparación.")


def _preceding_weeks(period: Period, today: date) -> Comparison:
    """The same number of complete weeks, ending the week before this period's
    first one.

    Counted off `period.weeks[0]` rather than off `period.start`, so the two
    windows are the same shape in the unit WEEKLY_KI is actually keyed in. Two
    weeks into 2026-6 this returns the weeks ending 2026-08-30 and 2026-09-06 —
    the pair §1.3 measured as the only comparison CCSM can honestly make today.
    """
    if not period.weeks:
        return Comparison(None, NO_COMPARISON,
                          "El período todavía no tiene una semana completa.")
    n = period.weeks_elapsed
    if n > ROLLING_WEEKS:
        # This pill exists to isolate the transfer-day discontinuity, which is
        # a question about a handful of weeks either side of a boundary. Asked
        # of "Año" it would hold 2026 against the 38 weeks ending last
        # December — a window with no name, overlapping the previous year the
        # other pill already offers.
        return Comparison(None, NO_COMPARISON,
                          "El período es demasiado largo para esta comparación.")
    end = period.weeks[0] - timedelta(days=7)
    start = end - timedelta(weeks=n - 1, days=6)
    label = "Semana anterior" if n == 1 else f"{n} semanas anteriores"
    return Comparison(_period(period.key, label, start, end, today),
                      PRECEDING_WEEKS)


def available(today: date, cycles: list[dict] | None = None) -> tuple[str, ...]:
    """The period keys that resolve on `today`, in display order.

    A label is simply absent when the schedule cannot supply it — the same
    behaviour `transfer_helpers.transfer_period_bounds` has, and the reason the
    picker can never offer a period that renders an empty page.
    """
    return tuple(k for k in PERIOD_KEYS if resolve(k, today, cycles) is not None)


def available_comparisons(period: Period, today: date,
                          cycles: list[dict] | None = None) -> tuple[str, ...]:
    """The "Comparar contra" pills worth offering for `period`.

    An option that resolves to nothing is dropped, and so is one that resolves
    to a window another option already covers: on "Últimas 6 semanas" the
    period's twin and the six weeks preceding it are the same six weeks, and
    two pills that do the same thing are worse than one.
    """
    seen: list[tuple[date, date]] = []
    out = []
    for key in COMPARE_KEYS:
        comp = comparison_for(period, today, cycles, against=key)
        if not comp:
            continue
        window = (comp.period.start, comp.period.end)
        if window in seen:
            continue
        seen.append(window)
        out.append(key)
    return tuple(out)


# ── Coverage ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Coverage:
    """How much of a window anyone actually reported (decision 6).

    Two numbers, because one of them alone lies. ``weeks_reported`` of
    ``weeks_expected`` is the caption decision 6 quotes — "4 de 6 semanas" —
    but a week counts as reported the moment ONE area files, and CCSM has a
    real WEEKLY_KI week holding a single area of forty-five. So
    ``reporting_rate`` carries the rest: area-weeks filed over area-weeks
    possible, which is the figure that keeps §1.3's reporting-rate trap
    visible. 26 of 45 areas on 2026-09-06 against 36 on 09-13 is a 38% swing in
    raw sums and nothing at all in the work; the rate is what says so.

    This is reporting coverage, not elapsed time — `Period.progress_label`
    answers that.
    """

    weeks_expected: int
    weeks_reported: int
    areas_in_scope: int
    area_weeks_reported: int

    @property
    def area_weeks_expected(self) -> int:
        return self.weeks_expected * self.areas_in_scope

    @property
    def reporting_rate(self) -> float | None:
        """Area-weeks filed as a fraction of area-weeks possible, or None when
        the window holds no complete week to have reported in."""
        possible = self.area_weeks_expected
        return self.area_weeks_reported / possible if possible else None

    @property
    def complete(self) -> bool:
        return (self.weeks_expected > 0
                and self.weeks_reported == self.weeks_expected)

    @property
    def usable(self) -> bool:
        """Whether anything was reported in this window at all.

        False is what turns a comparison into the `sin comparación` chip
        rather than into a percentage against zero. It is deliberately NOT a
        quality judgment: decision 6 says partial comparisons are shown with
        their coverage stated, and the chip appears only when there is
        genuinely nothing. A window this calls usable can still be one area of
        forty-five — see `thin` — so `label` and `reporting_rate` belong beside
        every figure drawn from it, always.
        """
        return self.weeks_reported > 0

    @property
    def thin(self) -> bool:
        """Reported so sparsely that the window is really one or two areas.

        For emphasis, never for suppression — a thin comparison is still shown
        (decision 6), it is just shown as the thing it is. The floor sits far
        below anything the mission has actually produced: CCSM's real WEEKLY_KI
        weeks run 26 to 36 areas of 45, i.e. 58%–80%, while the windows this
        catches are the ones resting on the single stray row dated 2026-08-09 —
        1.1% over the first two weeks of 2026-5, 0.4% over the six weeks before
        2026-08-10.
        """
        rate = self.reporting_rate
        return rate is not None and rate < THIN_REPORTING_RATE

    @property
    def label(self) -> str:
        """"4 de 6 semanas" — decision 6's caption, beside every partial figure."""
        noun = "semana" if self.weeks_expected == 1 else "semanas"
        return f"{self.weeks_reported} de {self.weeks_expected} {noun}"


def _as_date(value) -> date | None:
    """A week key as a date, whether it arrived as one or as 'YYYY-MM-DD'.

    WEEKLY_KI stores its week_end_date as a string (`get_weekly_ki` normalises
    it to the first ten characters); the periods here are real dates. Accepting
    both means no caller has to remember which side it is holding.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def week_coverage(period: Period, reported_by_week: Mapping,
                  areas_in_scope: int) -> Coverage:
    """Coverage of `period` from `{week_end: areas that reported}`.

    Only the period's own complete weeks are counted, so a stray WEEKLY_KI row
    for a week outside the window — CCSM has one dated 2026-09-27, a week that
    has not happened yet — cannot inflate anything.
    """
    counts: dict[date, int] = {}
    for raw, n in (reported_by_week or {}).items():
        day = _as_date(raw)
        if day is not None:
            counts[day] = counts.get(day, 0) + int(n or 0)
    reported = [counts.get(w, 0) for w in period.weeks]
    return Coverage(
        weeks_expected=len(period.weeks),
        weeks_reported=sum(1 for n in reported if n > 0),
        areas_in_scope=int(areas_in_scope or 0),
        area_weeks_reported=sum(reported),
    )
