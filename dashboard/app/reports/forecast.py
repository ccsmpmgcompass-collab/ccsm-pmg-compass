"""What is coming — the packet's forward view (decision 48, PLAN-2026-10-06
Phase 2).

Four forecasts, each printed as a RANGE with its method in one line and
never coloured as a verdict:

  * **transfer finish** — where each Key Indicator ends the transfer at the
    pace of recent weeks, and what it would take per week to reach
    leadership's goal;
  * **needed per week** — the same arithmetic turned around, against the
    pace the unit actually has;
  * **annual landing** — where the year's baptisms land against the 527
    (decision 46), from four simple anchors, with the same months of the two
    previous years beside it;
  * **baptism pipeline** — how many of the people holding a baptismal date
    today are likely to be baptised in the next six weeks, from how dates of
    the same age have converted before (P4).

Pure: frames in, dataclasses out. `model.py` decides which unit gets what;
the renderers only draw. Nothing here grades.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
import math

import numpy as np
import pandas as pd

# ── Transfer finish and needed per week ───────────────────────────────────────

#: How many complete weeks the pace is read from. Six is a transfer: enough
#: weeks for a worst and a best, few enough that it is still "now".
PACE_WEEKS = 6


@dataclass(frozen=True)
class KIFinish:
    """One Key Indicator's transfer, finished forward at recent pace.

    ``actual`` is the raw sum over the transfer's complete weeks — the same
    figure the Key Indicator table prints. ``low``/``mid``/``high`` add the
    remaining weeks at the worst, the average and the best of the last
    ``pace_weeks`` complete weeks' raw totals: "si lo que falta es como la
    peor, el promedio o la mejor semana reciente". Raw totals carry today's
    reporting with them, and the method line says so.

    ``goal`` is leadership's goal for the WHOLE transfer for every area in
    scope; ``goal_complete`` is False when an area has none.

    A LEVEL (``level``, PLAN-2026-10-17 L1–L3) is not added up: ``actual``
    is the latest complete week's level ("hoy"), ``goal`` the level to hold,
    and ``low``/``mid``/``high`` carry today's level to the transfer's close
    at the worst, the average and the best weekly CHANGE of the pace weeks,
    floored at zero. What is missing is ``gap`` — the goal minus today's
    level — never a figure per week.
    """

    key: str
    label: str
    actual: float
    weeks_done: int
    weeks_left: int
    pace_weeks: int
    low: float
    mid: float
    high: float
    goal: float | None = None
    goal_complete: bool = False
    level: bool = False

    @property
    def gap(self) -> float | None:
        """A level's distance to its goal today, or None (a flow, no goal)."""
        if not self.level or not self.goal:
            return None
        return self.goal - self.actual

    @property
    def weekly_mean(self) -> float:
        if self.weeks_left <= 0:
            return 0.0
        return (self.mid - self.actual) / self.weeks_left

    @property
    def needed_per_week(self) -> float | None:
        """What each remaining week would need to reach the goal, or None.
        None for a level, whose goal is held, not accumulated (`gap`)."""
        if not self.goal or self.weeks_left <= 0 or self.level:
            return None
        return max(0.0, (self.goal - self.actual) / self.weeks_left)

    @property
    def factor(self) -> float | None:
        """Needed per week as a multiple of the recent average week."""
        need, mean = self.needed_per_week, self.weekly_mean
        if need is None or not mean:
            return None
        return need / mean

    def pct(self, value: float) -> float | None:
        return value / self.goal * 100 if self.goal else None


def transfer_finish(weekly_ki: pd.DataFrame, areas, keys, labels: dict, *,
                    cycle_weeks, full_weeks: int, pace_weeks_list,
                    goals: dict, goals_complete: bool) -> tuple:
    """`KIFinish` per key.

    ``cycle_weeks`` are the transfer's COMPLETE weeks so far (ISO week-end
    dates), ``pace_weeks_list`` the last up-to-six complete weeks the pace is
    read from (they may reach back into the previous transfer early in a new
    one), ``goals`` leadership's whole-transfer goal per key for these areas
    — for a LEVEL key the level to hold (see `KIFinish`).
    """
    from app.config.levels import is_level
    if weekly_ki is None or weekly_ki.empty:
        return ()
    wanted = set(areas)
    rows = weekly_ki[weekly_ki["_area"].isin(wanted)]
    done = rows[rows["_week"].isin(set(cycle_weeks))]
    pace = rows[rows["_week"].isin(set(pace_weeks_list))]
    weeks_left = max(0, int(full_weeks) - len(cycle_weeks))
    out = []
    for key in keys:
        if key not in rows.columns:
            continue
        actual = float(pd.to_numeric(done[key], errors="coerce").sum())
        by_week = (pd.to_numeric(pace[key], errors="coerce")
                   .groupby(pace["_week"]).sum())
        # A week nobody in scope reported is a zero for a raw total — the
        # pace has to carry the silence it will meet again.
        weekly = [float(by_week.get(w, 0.0)) for w in pace_weeks_list]
        if is_level(key):
            out.append(_level_finish(key, labels.get(key, key), done, pace,
                                     key_weeks=list(cycle_weeks),
                                     pace_weeks_list=list(pace_weeks_list),
                                     weeks_left=weeks_left,
                                     goal=goals.get(key),
                                     goal_complete=goals_complete))
            continue
        if weekly:
            lo, mean, hi = min(weekly), sum(weekly) / len(weekly), max(weekly)
        else:
            lo = mean = hi = 0.0
        out.append(KIFinish(
            key=key, label=labels.get(key, key), actual=actual,
            weeks_done=len(cycle_weeks), weeks_left=weeks_left,
            pace_weeks=len(weekly),
            low=actual + weeks_left * lo, mid=actual + weeks_left * mean,
            high=actual + weeks_left * hi,
            goal=goals.get(key), goal_complete=goals_complete))
    return tuple(out)


def _level_finish(key, label, done, pace, *, key_weeks, pace_weeks_list,
                  weeks_left, goal, goal_complete) -> KIFinish:
    """A LEVEL's transfer (see `KIFinish`): today's level, carried to the
    close at the pace weeks' worst, mean and best week-to-week change."""
    def level_in(frame, week):
        mine = frame[frame["_week"] == week]
        return float(pd.to_numeric(mine[key], errors="coerce").fillna(0).sum())

    # Today is the transfer's latest complete week; with none yet, the
    # latest pace week (the previous transfer's close).
    today_week = (key_weeks[-1] if key_weeks
                  else pace_weeks_list[-1] if pace_weeks_list else None)
    source = done if key_weeks else pace
    actual = level_in(source, today_week) if today_week else 0.0
    levels = [level_in(pace, w) for w in pace_weeks_list]
    steps = [b - a for a, b in zip(levels, levels[1:])]
    if steps:
        lo, mean, hi = min(steps), sum(steps) / len(steps), max(steps)
    else:
        lo = mean = hi = 0.0
    return KIFinish(
        key=key, label=label, actual=actual,
        weeks_done=len(key_weeks), weeks_left=weeks_left,
        pace_weeks=len(levels),
        low=max(0.0, actual + weeks_left * lo),
        mid=max(0.0, actual + weeks_left * mean),
        high=max(0.0, actual + weeks_left * hi),
        goal=goal, goal_complete=goal_complete, level=True)


# ── The year's baptisms against the annual goal ───────────────────────────────

@dataclass(frozen=True)
class YearLanding:
    """The year's baptisms and where they land (decision 46: 527 rules).

    ``monthly`` is ``{year: [12 values or None]}`` for this year and up to two
    before it, closed months only. ``anchors`` maps a one-line method to its
    landing; ``low``/``high`` are their min and max. ``source`` says which
    figure this is — certified (the mission) or Tableau's person records (a
    zone, decision 47) — and the renderers print it.
    """

    year: int
    months: int
    total: int
    monthly: dict
    anchors: tuple = ()
    goal: float | None = None
    best: tuple | None = None            # (count, "dic 2024")
    open_count: int | None = None
    source: str = ""

    @property
    def low(self) -> float | None:
        return min(v for _, v in self.anchors) if self.anchors else None

    @property
    def high(self) -> float | None:
        return max(v for _, v in self.anchors) if self.anchors else None

    @property
    def months_left(self) -> int:
        return 12 - self.months

    @property
    def needed_per_month(self) -> float | None:
        if not self.goal or self.months_left <= 0:
            return None
        return max(0.0, (self.goal - self.total) / self.months_left)

    def same_months(self, year: int) -> int | None:
        """The given year's total over the months this year has closed."""
        values = self.monthly.get(year)
        if not values or self.months == 0:
            return None
        head = values[:self.months]
        if any(v is None for v in head):
            return None
        return int(sum(head))


MONTH_ABBR = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep",
              "oct", "nov", "dic")


def _series(by_month: dict, year: int) -> list:
    return [by_month.get(f"{year:04d}-{m:02d}") for m in range(1, 13)]


def year_landing(by_month: dict, year: int, *, goal: float | None,
                 open_count: int | None = None,
                 source: str = "") -> YearLanding | None:
    """The four anchors (AUDIT-2026-10-06 C4(b)), from closed months only.

    * the last two months' pace, carried to December;
    * the last three months' pace;
    * the straight line — the year so far, scaled to twelve months;
    * the previous years' remaining months, scaled by how this year compares
      with each of them over the same months.
    """
    this = _series(by_month, year)
    closed = 0
    for value in this:
        if value is None:
            break
        closed += 1
    if closed == 0:
        return None
    total = int(sum(this[:closed]))
    left = 12 - closed
    anchors = []
    for n, words in ((2, "el ritmo de los últimos 2 meses"),
                     (3, "el ritmo de los últimos 3 meses")):
        if closed >= n:
            anchors.append((words, total + left * sum(this[closed - n:closed]) / n))
    anchors.append(("la línea recta del año", total / closed * 12))
    scaled = []
    for prior in (year - 1, year - 2):
        before = _series(by_month, prior)
        if any(v is None for v in before):
            continue
        head = sum(before[:closed])
        if head:
            scaled.append(total + sum(before[closed:]) * total / head)
    if scaled:
        anchors.append(("el resto de los años anteriores, a la escala de este",
                        sum(scaled) / len(scaled)))
    monthly = {y: _series(by_month, y) for y in (year - 2, year - 1, year)
               if any(v is not None for v in _series(by_month, y))}
    best = None
    for key, value in by_month.items():
        if value is not None and (best is None or value > best[0]):
            y, m = key.split("-")
            best = (int(value), f"{MONTH_ABBR[int(m) - 1]} {y}")
    return YearLanding(year=year, months=closed, total=total, monthly=monthly,
                       anchors=tuple(anchors), goal=goal, best=best,
                       open_count=open_count, source=source)


# ── The baptism pipeline (P4) ─────────────────────────────────────────────────

#: Age buckets, in days since the baptismal date was set.
BUCKETS = (0, 15, 31, 61, 91, 181, 366)
BUCKET_LABELS = ("0-14 días", "15-30", "31-60", "61-90", "91-180", "181-365")
#: A date this many days old or more is "stale": the packet's "revisar o
#: liberar" and the zones' share of old dates (step 3.1). A bucket edge, so
#: the pipeline's own buckets answer it.
STALE_DAYS = 91
#: The forecast horizon: six weeks, a transfer.
HORIZON = 42
#: How far back the conversion is fitted: the last 6 month-ends whose six
#: weeks have fully happened (decision 68). 2026 dates convert at about half
#: the 2025 rate, and the 15-month pooled fit overshot ×1,7–2,1 from June.
FIT_MONTHS = 6
#: How many month-ends the backtest reports on. Each is forecast with the fit
#: that existed AT that month-end — what the packet would have printed then —
#: never with a fit that already saw its answer (step 2.0).
BACKTEST_MONTHS = 12


@dataclass(frozen=True)
class Pipeline:
    """The open baptismal dates and what they are likely to turn into.

    ``expected`` is the sum of each open date's chance of a baptism in the
    next six weeks, by its age (P4). ``low``/``high`` are an 80% range: the
    wider of the Poisson-binomial spread and the backtest's typical miss.
    ``miss`` is that typical miss as a fraction — the median of |forecast −
    what happened| / what happened over the last twelve month-ends, each
    forecast with the fit of its own day. ``high`` counts the backtests that
    forecast more than happened.
    """

    open_dates: int
    expected: float
    low: float
    high: float
    by_bucket: tuple = ()          # ((label, open, p), ...)
    miss: float | None = None
    backtests: int = 0
    asof: date | None = None
    over: int = 0

    @property
    def old(self) -> int:
        """Open dates STALE_DAYS old or more (step 3.1)."""
        return sum(c for (label, c, _), lo in zip(self.by_bucket, BUCKETS)
                   if lo >= STALE_DAYS)

    @property
    def old_share(self) -> float | None:
        return self.old / self.open_dates if self.open_dates else None

    @property
    def miss_clause(self) -> str:
        """", el cálculo hecho en su momento falló por un 45% típico (alto en
        10)" — both renderers' backtest words, or "" with no backtest."""
        if self.miss is None or not self.backtests:
            return ""
        from app.config import es_display as ES
        line = (f"en los últimos {ES.integer(self.backtests)} cierres de mes, "
                f"el cálculo hecho en su momento falló por un "
                f"{ES.percent(self.miss * 100, 0)} típico")
        if self.over * 3 >= self.backtests * 2:
            line += f" y se quedó alto en {ES.integer(self.over)}"
        elif (self.backtests - self.over) * 3 >= self.backtests * 2:
            line += f" y se quedó bajo en {ES.integer(self.backtests - self.over)}"
        return line


@dataclass(frozen=True)
class PipelineFit:
    """The mission-wide conversion by age bucket, fitted once per export."""

    p: tuple = ()                  # one probability per bucket
    miss: float | None = None
    backtests: int = 0
    over: int = 0


def _bucket(age_days) -> pd.Series:
    return pd.cut(pd.Series(age_days), bins=list(BUCKETS), right=False,
                  labels=False)


#: Every comparison below runs on plain ``datetime64[ns]`` arrays. Comparing a
#: pandas datetime Series with a Timestamp raises a NumPy "generic timedelta"
#: DeprecationWarning from inside pandas on this stack (NumPy 2.5, pandas
#: 2.3), once per comparison and 758 times per test run.
_DAY = np.timedelta64(1, "D")


def _ns(values) -> np.ndarray:
    return np.asarray(pd.to_datetime(pd.Series(values)), dtype="datetime64[ns]")


def _t(value) -> np.datetime64:
    return np.datetime64(pd.Timestamp(value).to_datetime64(), "ns")


def _open_at(set_d, conf_d, t) -> np.ndarray:
    """Dates set in the year before ``t`` and not yet confirmed at ``t``."""
    set_d, conf_d, t = _ns(set_d), _ns(conf_d), _t(t)
    return ((set_d <= t) & (set_d > t - 365 * _DAY)
            & (np.isnat(conf_d) | (conf_d > t)))


def _month_ends(asof: date, count: int) -> list:
    """The last ``count`` month-ends whose six weeks have fully happened,
    oldest first. Plain dates: `pd.date_range` warns on this NumPy."""
    last = asof - timedelta(days=HORIZON)
    end = date(last.year, last.month, 1) - timedelta(days=1)
    if (last + timedelta(days=1)).day == 1:          # `last` is a month-end
        end = last
    ends = []
    while len(ends) < count:
        ends.append(pd.Timestamp(end))
        end = date(end.year, end.month, 1) - timedelta(days=1)
    return ends[::-1]


def fit_pipeline(set_d: pd.Series, conf_d: pd.Series, asof: date) -> PipelineFit:
    """Conversion within six weeks by age bucket, pooled over month-ends.

    At each month-end T whose six weeks have fully happened, every open date
    is aged and bucketed, and counted a hit if a confirmation followed in
    (T, T + 42 days]. Pooling the T's gives P(baptised within six weeks | still
    open at this age) — the conditional probability P4 asks for, measured
    rather than assumed.

    The backtest forecasts each of the last ``BACKTEST_MONTHS`` month-ends T
    with the fit as of T (the ``FIT_MONTHS`` month-ends before it whose six
    weeks had happened by T), so ``miss`` is the error the packet would have
    printed, not the error of a fit that already saw the answer.
    """
    k = len(BUCKETS) - 1
    set_ns, conf_ns = _ns(set_d), _ns(conf_d)
    stats = {}                    # month-end -> (open per bucket, hits per bucket)

    def at(t):
        if t not in stats:
            mask = _open_at(set_d, conf_d, t)
            tt = _t(t)
            buckets = _bucket((tt - set_ns[mask]) // _DAY)
            later = conf_ns[mask]
            hit = (later > tt) & (later <= tt + HORIZON * _DAY)
            counts = buckets.value_counts().to_dict()
            hits = buckets[hit].value_counts().to_dict()
            n, h = [0] * k, [0] * k
            for b, c in counts.items():
                if pd.notna(b):
                    n[int(b)] += int(c)
                    h[int(b)] += int(hits.get(b, 0))
            stats[t] = (n, h)
        return stats[t]

    def fit_at(day):
        n, h = [0] * k, [0] * k
        for t in _month_ends(day, FIT_MONTHS):
            tn, th = at(t)
            n = [a + b for a, b in zip(n, tn)]
            h = [a + b for a, b in zip(h, th)]
        if not any(n):
            return None
        return tuple(h[i] / n[i] if n[i] else 0.0 for i in range(k))

    p = fit_at(asof)
    if p is None:
        return PipelineFit(p=tuple([0.0] * k))
    misses, over = [], 0
    for t in _month_ends(asof, BACKTEST_MONTHS):
        then = fit_at(t.date())
        n, h = at(t)
        actual = sum(h)
        if then is None or not actual:
            continue
        forecast = sum(q * c for q, c in zip(then, n))
        misses.append(abs(forecast - actual) / actual)
        over += forecast > actual
    miss = (sorted(misses)[len(misses) // 2] if misses else None)
    return PipelineFit(p=p, miss=miss, backtests=len(misses), over=over)


def pipeline(set_d: pd.Series, conf_d: pd.Series, asof: date,
             fit: PipelineFit, mask=None) -> Pipeline | None:
    """The open dates today (optionally only the rows in ``mask``) through
    ``fit``. None when the fit has no history to stand on."""
    if not fit.p:
        return None
    open_now = _open_at(set_d, conf_d, asof)
    if mask is not None:
        open_now = open_now & np.asarray(mask, dtype=bool)
    ages = (_t(asof) - _ns(set_d)[open_now]) // _DAY
    buckets = _bucket(ages).value_counts().to_dict()
    expected, var, rows = 0.0, 0.0, []
    for i, label in enumerate(BUCKET_LABELS):
        c = int(buckets.get(i, 0))
        p = fit.p[i]
        expected += c * p
        var += c * p * (1 - p)
        rows.append((label, c, p))
    spread = max(1.2816 * math.sqrt(var), (fit.miss or 0.0) * expected)
    return Pipeline(open_dates=int(open_now.sum()), expected=expected,
                    low=max(0.0, expected - spread), high=expected + spread,
                    by_bucket=tuple(rows), miss=fit.miss,
                    backtests=fit.backtests, asof=asof, over=fit.over)


# ── What a date is worth (PLAN-2026-10-13 step 3.1, C4, decision 65) ─────────

#: A date set within this many days of the person being found is "quick".
QUICK_DAYS = 7
#: How many whole calendar months the cohorts compare, 2025 against 2026.
COHORT_MONTHS = 3


@dataclass(frozen=True)
class DateAges:
    """The open dates on one day, by age — `_open_at`'s definition: set in
    the year before and not yet baptised (Tableau has no "dropped" field)."""

    asof: date
    open: int = 0
    old: int = 0          # STALE_DAYS or more
    fresh: int = 0        # under 31 days

    def share(self, n: int) -> float | None:
        return n / self.open if self.open else None


@dataclass(frozen=True)
class DateCohort:
    """The dates set inside [start, end] and what became of them: baptised
    within ``HORIZON`` days, set within ``QUICK_DAYS`` of being found, and set
    after the person first attended church."""

    start: date
    end: date
    dates: int = 0
    baptized: int = 0
    quick: int = 0
    after_church: int = 0

    def share(self, n: int) -> float | None:
        return n / self.dates if self.dates else None


@dataclass(frozen=True)
class DateQuality:
    """Step 3.1 (decision 65): how many dates, how old, how many arrive.

    ``now``/``before`` are the open dates today and on the same day a year
    ago. ``cohorts`` is (last year, this year) over the same ``COHORT_MONTHS``
    whole months, the latest whose dates have all had their six weeks.
    ``found``/``set``/``certified`` are (last year, this year) people found,
    dates set and certified baptisms in those same months — the jump the
    packet states with both readings, over one window. Measures only:
    nothing here names a cause (Q-J).
    """

    now: DateAges
    before: DateAges
    cohorts: tuple = ()
    found: tuple = ()
    set: tuple = ()
    certified: tuple = ()

    @staticmethod
    def ratio(pair) -> float | None:
        return pair[1] / pair[0] if pair and pair[0] else None


def _ages_at(set_ns, conf_ns, t: date) -> DateAges:
    open_ = _open_at(set_ns, conf_ns, t)
    ages = (_t(t) - set_ns[open_]) // _DAY
    return DateAges(asof=t, open=int(open_.sum()),
                    old=int((ages >= STALE_DAYS).sum()),
                    fresh=int((ages < 31).sum()))


def cohort_window(asof: date, months: int = COHORT_MONTHS) -> tuple | None:
    """The last ``months`` whole calendar months whose every date has had its
    ``HORIZON`` days by ``asof``: on 2026-10-16, 1 Jun - 31 Aug."""
    last = asof - timedelta(days=HORIZON)
    end = date(last.year, last.month, 1) - timedelta(days=1)
    if (last + timedelta(days=1)).day == 1:
        end = last
    start = date(end.year, end.month, 1)
    for _ in range(months - 1):
        start = date(start.year - (start.month == 1),
                     12 if start.month == 1 else start.month - 1, 1)
    return start, end


def _cohort(found_ns, set_ns, conf_ns, attend_ns, start: date,
            end: date) -> DateCohort:
    pick = (set_ns >= _t(start)) & (set_ns < _t(end + timedelta(days=1)))
    s, c = set_ns[pick], conf_ns[pick]
    f, a = found_ns[pick], attend_ns[pick]
    baptized = ~np.isnat(c) & (c >= s) & (c <= s + HORIZON * _DAY)
    quick = ~np.isnat(f) & (s - f <= QUICK_DAYS * _DAY)
    after = ~np.isnat(a) & (a <= s)
    return DateCohort(start=start, end=end, dates=int(pick.sum()),
                      baptized=int(baptized.sum()), quick=int(quick.sum()),
                      after_church=int(after.sum()))


def _between(values, start: date, end: date) -> int:
    return int(((values >= _t(start))
                & (values < _t(end + timedelta(days=1)))).sum())


def _months_total(by_month: dict, start: date, end: date) -> int | None:
    """Certified baptisms over whole months [start, end], or None if any of
    them has no figure."""
    total, day = 0, start
    while day <= end:
        value = (by_month or {}).get(f"{day:%Y-%m}")
        if value is None:
            return None
        total += value
        day = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
    return int(total)


def date_quality(found: pd.Series, set_d: pd.Series, conf_d: pd.Series,
                 attend: pd.Series, asof: date, *,
                 through: date | None = None,
                 by_month: dict | None = None) -> DateQuality:
    """`DateQuality` off Tableau's person rows. ``asof`` ages the open dates
    (the build day, as `pipeline` does); ``through`` is where the export
    stops, which bounds the cohorts' six weeks. ``by_month`` is the certified
    monthly baptisms, read for the cohorts' months."""
    found_ns, set_ns = _ns(found), _ns(set_d)
    conf_ns, attend_ns = _ns(conf_d), _ns(attend)
    year_ago = _same_day(asof, asof.year - 1)
    out = DateQuality(now=_ages_at(set_ns, conf_ns, asof),
                      before=_ages_at(set_ns, conf_ns, year_ago))
    window = cohort_window(min(through or asof, asof))
    if window is None:
        return out
    spans = [(_same_day(window[0], window[0].year + shift),
              _same_day(window[1], window[1].year + shift))
             for shift in (-1, 0)]
    certified = tuple(_months_total(by_month, a, b) for a, b in spans)
    return replace(
        out,
        cohorts=tuple(_cohort(found_ns, set_ns, conf_ns, attend_ns, a, b)
                      for a, b in spans),
        found=tuple(_between(found_ns, a, b) for a, b in spans),
        set=tuple(_between(set_ns, a, b) for a, b in spans),
        certified=certified if None not in certified else ())


def stale_by_area(names: pd.Series, set_d: pd.Series, conf_d: pd.Series,
                  asof: date, areas) -> tuple:
    """``((area, open dates STALE_DAYS old or more), ...)`` for each area, in
    the order given — the district page's "revisar o liberar". Counts only:
    the packet never names the people (step 3.1)."""
    set_ns, conf_ns = _ns(set_d), _ns(conf_d)
    open_ = _open_at(set_ns, conf_ns, asof)
    old = open_.copy()
    old[open_] = (_t(asof) - set_ns[open_]) // _DAY >= STALE_DAYS
    named = np.asarray(names.astype(str).str.strip())
    return tuple((a, int((old & (named == a)).sum())) for a in areas)


# ── The gap to 527 and what would close it (C6, C8, decision 64) ─────────────

#: The open dates a bet moves (b), and the age whose conversion it borrows.
OLD_BUCKET = "91-180"
YOUNG_BUCKET = "31-60"


@dataclass(frozen=True)
class Bet:
    """One measured lever, sized in baptisms to 31 December, as a range."""

    label: str
    low: float
    high: float
    how: str = ""


@dataclass(frozen=True)
class YearGap:
    """527 less where the year lands, and the measured levers beside it.

    ``low``/``high`` is the gap: the goal less the landing's high and low
    anchors (never below zero). ``bets`` are what each lever would add by 31
    December. 527 is fixed (decision 64): this says what closes the gap, and
    nothing here proposes moving the goal.
    """

    goal: float
    low: float
    high: float
    bets: tuple = ()

    @property
    def bets_low(self) -> float:
        return sum(b.low for b in self.bets)

    @property
    def bets_high(self) -> float:
        return sum(b.high for b in self.bets)


def transfers_left(year: int, today: date) -> float:
    """Six-week transfers from ``today`` to 31 December of ``year``."""
    return max(0.0, (date(year, 12, 31) - today).days / 7) / 6


def year_gap(year: "YearLanding | None", pipeline: "Pipeline | None",
             levers, today: date) -> YearGap | None:
    """The gap to the annual goal and two bets (PLAN-2026-10-13 step 2.3):

    (a) every zone's largest leak converting like the mission — `focus.Lever`
        is per six weeks of finding, so it is carried over the transfers
        left in the year (weeks to 31 December ÷ 6);
    (b) the open dates 91–180 days old converting like the 31–60-day ones,
        from the pipeline fit's own age buckets, over its six weeks. Its
        range carries the fit's backtest miss; when the fit has run high in
        two-thirds of its backtests the range only runs down from the
        figure.

    Reporting is NOT a bet: the certified baptisms do not depend on forms.
    """
    if year is None or not year.goal or year.low is None:
        return None
    gap = YearGap(goal=year.goal, low=max(0.0, year.goal - year.high),
                  high=max(0.0, year.goal - year.low))
    bets = []
    transfers = transfers_left(year.year, today)
    sized = [v for v in (levers or ()) if v.baptisms]
    if sized and transfers:
        lo = sum(v.baptisms[0] for v in sized) * transfers
        hi = sum(v.baptisms[1] for v in sized) * transfers
        bets.append(Bet(
            label="La mayor fuga de cada zona, convirtiendo como la misión",
            low=lo, high=hi,
            how=(f"{len(sized)} zonas, por traslado de hallazgo, por los "
                 f"{transfers:.1f}".replace(".", ",")
                 + " traslados que quedan del año")))
    if pipeline is not None:
        rows = {label: (n, q) for label, n, q in pipeline.by_bucket}
        if OLD_BUCKET in rows and YOUNG_BUCKET in rows:
            n, q_old = rows[OLD_BUCKET]
            _, q_young = rows[YOUNG_BUCKET]
            extra = n * max(0.0, q_young - q_old)
            miss = pipeline.miss or 0.0
            ran_high = (pipeline.backtests
                        and pipeline.over * 3 >= pipeline.backtests * 2)
            bets.append(Bet(
                label="Las fechas de 91 a 180 días, convirtiendo como las de "
                      "31 a 60",
                low=extra * max(0.0, 1 - miss),
                high=extra if ran_high else extra * (1 + miss),
                how=(f"{n} fechas abiertas de esa edad, en seis semanas")))
    return replace(gap, bets=tuple(bets))


# ── A unit's baptisms from Tableau's person records (decision 47) ─────────────

@dataclass(frozen=True)
class UnitBaptisms:
    """A zone's or a district's baptisms, from Tableau's person-level export,
    by roster area — "registros de Tableau" (decision 47). The mission keeps
    the certified figure; below it this is the only baptism figure there is.

    ``share`` is the unit's part of every baptism Tableau recorded in the last
    twelve closed months, and ``reference`` 527 × that share: "lo que le toca
    si la misión llega a 527 repartida como siempre" (P2) — printed, never
    coloured. ``year_total`` is the unit's records this year, closed months.
    """

    count: int
    start: date
    end: date
    share: float | None = None
    reference: float | None = None
    year_total: int | None = None
    months: int = 0
    annual_goal: float | None = None

    @property
    def sentence(self) -> str:
        """The line both renderers print on a zone's or district's opening."""
        from app.config import es_display as ES
        line = (f"Bautismos en el período, registros de Tableau: "
                f"{ES.integer(self.count)} ({ES.day_month(self.start)} - "
                f"{ES.day_month(self.end, with_year=True)})")
        if self.year_total is not None:
            line += (f" · {ES.integer(self.year_total)} en lo que va del año "
                     f"({ES.integer(self.months)} meses cerrados)")
        return line + "."


def unit_baptisms(conf_d: pd.Series, mask, start: date, end: date, *,
                  today: date, annual_goal: float | None) -> UnitBaptisms:
    """Confirmations dated inside [start, end] for the rows in ``mask``."""
    conf = _ns(conf_d)
    mask = np.asarray(mask, dtype=bool)
    lo, hi = _t(start), _t(end)
    count = int((mask & (conf >= lo) & (conf <= hi)).sum())
    first_day = date(today.year, today.month, 1)
    first = _t(first_day)
    year_lo = _t(pd.Timestamp(first_day) - pd.DateOffset(months=12))
    window_all = (conf >= year_lo) & (conf < first)
    total_12 = int(window_all.sum())
    mine_12 = int((window_all & mask).sum())
    share = mine_12 / total_12 if total_12 else None
    jan = _t(date(today.year, 1, 1))
    ytd = int((mask & (conf >= jan) & (conf < first)).sum())
    return UnitBaptisms(
        count=count, start=start, end=end, share=share,
        reference=(annual_goal * share if annual_goal and share is not None
                   else None),
        year_total=ytd, months=today.month - 1, annual_goal=annual_goal)


def monthly_counts(conf_d: pd.Series, mask, today: date) -> dict:
    """``{"YYYY-MM": count}`` for the closed months the rows in ``mask`` hold —
    a zone's year from Tableau's records, in `year_landing`'s shape."""
    first_day = date(today.year, today.month, 1)
    conf = _ns(conf_d)[np.asarray(mask, dtype=bool)]
    conf = conf[~np.isnat(conf) & (conf < _t(first_day))]
    if not len(conf):
        return {}
    months = conf.astype("datetime64[M]").astype(str)
    keys, numbers = np.unique(months, return_counts=True)
    counts = {str(k)[:7]: int(c) for k, c in zip(keys, numbers)}
    out = {}
    for month in pd.period_range(pd.Timestamp(conf.min()),
                                 pd.Timestamp(first_day) - pd.Timedelta(days=1),
                                 freq="M"):
        key = month.strftime("%Y-%m")
        out[key] = int(counts.get(key, 0))
    return out


# ── The same weeks in other years (PLAN-2026-10-06 4B.1, decision 52) ────────

#: What Tableau can carry back past the weekly form, which starts 2026-08-09:
#: the person export's own milestone dates, under their own names — never
#: the Key Indicators' (decision 34: a Tableau figure never shares a table
#: with a form figure, and never borrows its name).
OTHER_YEAR_ROWS = (
    ("Personas encontradas", "event_date_selected"),
    ("Asistieron a la iglesia por primera vez", "first_sacrament_date"),
    ("Fecha bautismal fijada", "first_baptism_goal_date_set"),
    ("Bautizados (fecha de confirmación)", "confirmation_date"),
)


@dataclass(frozen=True)
class OtherYears:
    """Tableau's milestones over the same calendar days in up to three years.

    ``rows`` is ``((label, (count per year, oldest first)), ...)``; ``end``
    is where the export stops, so the window never asks a year for days this
    year cannot have yet.
    """

    start: date
    end: date
    years: tuple = ()
    rows: tuple = ()

    def last_two(self, label: str) -> tuple | None:
        """``(this year, last year)`` for one row."""
        for name, counts in self.rows:
            if name == label and len(counts) >= 2:
                return counts[-1], counts[-2]
        return None


def _same_day(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:                      # 29 Feb
        return day.replace(year=year, day=28)


def other_years(columns, mask, start: date, end: date, *,
                years: int = 3) -> OtherYears | None:
    """``columns`` is ``[(label, parsed date Series)]``; ``mask`` the rows of
    the unit (None = all). Counts each milestone dated inside [start, end]
    and inside the same calendar days of the years before."""
    if end < start or not columns:
        return None
    span = tuple(range(end.year - years + 1, end.year + 1))
    rows = []
    for label, dates in columns:
        values = _ns(dates)
        if mask is not None:
            values = values[np.asarray(mask, dtype=bool)]
        counts = []
        for year in span:
            shift = year - end.year
            lo = _t(_same_day(start, start.year + shift))
            hi = _t(_same_day(end, year) + timedelta(days=1))
            counts.append(int(((values >= lo) & (values < hi)).sum()))
        rows.append((label, tuple(counts)))
    return OtherYears(start=start, end=end, years=span, rows=tuple(rows))


# ── How good the forecasts have been (PLAN-2026-10-06 4C.1) ──────────────────

@dataclass(frozen=True)
class Backtest:
    """The same forecast, made at the same point in earlier periods, against
    what then happened. ``cases`` is ``((when, low, high, actual), ...)``;
    ``hits`` how many actuals fell inside their range; ``miss`` the typical
    (median) distance of the range's centre from the actual, in percent."""

    cases: tuple = ()

    @property
    def hits(self) -> int:
        return sum(1 for _, lo, hi, a in self.cases if lo <= a <= hi)

    @property
    def miss(self) -> float | None:
        errs = [abs((lo + hi) / 2 - a) / a * 100 for _, lo, hi, a in self.cases
                if a]
        return float(np.median(errs)) if errs else None

    @property
    def sentence(self) -> str:
        from app.config import es_display as ES
        if not self.cases:
            return ""
        n = len(self.cases)
        out = (f"Hecho igual en {ES.integer(n)} "
               f"{'momento anterior' if n == 1 else 'momentos anteriores'}, "
               f"el rango acertó {ES.integer(self.hits)} "
               f"{'vez' if self.hits == 1 else 'veces'}")
        if self.miss is not None:
            out += f" y el centro erró por un {ES.percent(self.miss, 0)} típico"
        return out + "."


def landing_backtest(by_month: dict, year: int, closed: int) -> Backtest:
    """`year_landing` made with only ``closed`` months of each earlier year
    that is complete, against that year's real total — the same point of the
    year as today's forecast."""
    cases = []
    for prior in (year - 1, year - 2):
        months = _series(by_month, prior)
        if any(v is None for v in months) or closed < 1:
            continue
        cut = {k: v for k, v in by_month.items()
               if int(k[:4]) < prior
               or (int(k[:4]) == prior and int(k[5:7]) <= closed)}
        fit = year_landing(cut, prior, goal=None)
        if fit is None or fit.low is None:
            continue
        cases.append((f"{MONTH_ABBR[closed - 1]} {prior}", fit.low, fit.high,
                      int(sum(months))))
    return Backtest(cases=tuple(cases))


def finish_backtest(dates: pd.Series, asof: date, *, weeks_done: int,
                    weeks_total: int = 6, pace_weeks: int = PACE_WEEKS,
                    windows: int = 40) -> Backtest:
    """The transfer finish's method — what is done plus the weeks left at
    the worst and best of the last ``pace_weeks`` — run on Tableau's weekly
    counts of one milestone (the form's history is nine weeks; Tableau's is
    nearly three years). Each case is a six-week window ending before
    ``asof``, forecast after ``weeks_done`` weeks."""
    values = _ns(dates)
    values = values[~np.isnat(values)]
    if not len(values):
        return Backtest()
    end_week = asof - timedelta(days=(asof.weekday() + 1) % 7 + 7)
    # Weekly counts in one pass, over at most the weeks the windows need: a
    # stray 1900 date in the export must not walk the loop back a century.
    span = windows * weeks_total + pace_weeks + weeks_total
    first = max(pd.Timestamp(values.min()).date(),
                end_week - timedelta(weeks=span))
    edges = [end_week - timedelta(weeks=k) for k in range(span + 1)]
    edges = [d for d in reversed(edges) if d >= first]
    if len(edges) < pace_weeks + weeks_total + 1:
        return Backtest()
    bins = np.array([_t(d + timedelta(days=1)) for d in edges])
    counts = np.histogram(values.astype("datetime64[ns]").astype("int64"),
                          bins=bins.astype("datetime64[ns]").astype("int64"))[0]
    weekly = {edges[k + 1]: int(c) for k, c in enumerate(counts)}
    weeks = sorted(weekly)
    cases = []
    step = weeks_total
    for i in range(len(weeks) - 1, pace_weeks + weeks_total - 1, -step):
        window = weeks[i - weeks_total + 1:i + 1]
        done = window[:weeks_done]
        left = weeks_total - weeks_done
        pace = [weekly[w] for w in weeks[i - weeks_total + 1 - pace_weeks
                                          + weeks_done:i - weeks_total + 1
                                          + weeks_done]]
        if len(pace) < pace_weeks:
            continue
        so_far = sum(weekly[w] for w in done)
        actual = sum(weekly[w] for w in window)
        cases.append((window[-1].isoformat(), so_far + left * min(pace),
                      so_far + left * max(pace), actual))
        if len(cases) >= windows:
            break
    return Backtest(cases=tuple(cases))
