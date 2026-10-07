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

from dataclasses import dataclass, field
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

    @property
    def weekly_mean(self) -> float:
        if self.weeks_left <= 0:
            return 0.0
        return (self.mid - self.actual) / self.weeks_left

    @property
    def needed_per_week(self) -> float | None:
        """What each remaining week would need to reach the goal, or None."""
        if not self.goal or self.weeks_left <= 0:
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
    one), ``goals`` leadership's whole-transfer goal per key for these areas.
    """
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
#: The forecast horizon: six weeks, a transfer.
HORIZON = 42
#: How far back the conversion is fitted: month-ends over the last 15 months
#: whose six weeks have fully happened.
FIT_MONTHS = 15
#: How many of those month-ends the backtest reports on.
BACKTEST_MONTHS = 12


@dataclass(frozen=True)
class Pipeline:
    """The open baptismal dates and what they are likely to turn into.

    ``expected`` is the sum of each open date's chance of a baptism in the
    next six weeks, by its age (P4). ``low``/``high`` are an 80% range: the
    wider of the Poisson-binomial spread and the backtest's typical miss.
    ``miss`` is that typical miss as a fraction — the median of |forecast −
    what happened| / what happened over the last twelve month-ends.
    """

    open_dates: int
    expected: float
    low: float
    high: float
    by_bucket: tuple = ()          # ((label, open, p), ...)
    miss: float | None = None
    backtests: int = 0
    asof: date | None = None


@dataclass(frozen=True)
class PipelineFit:
    """The mission-wide conversion by age bucket, fitted once per export."""

    p: tuple = ()                  # one probability per bucket
    miss: float | None = None
    backtests: int = 0


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
    """
    n = [0] * (len(BUCKETS) - 1)
    h = [0] * (len(BUCKETS) - 1)
    per_t = []
    set_ns, conf_ns = _ns(set_d), _ns(conf_d)
    for t in _month_ends(asof, FIT_MONTHS):
        mask = _open_at(set_d, conf_d, t)
        if not mask.any():
            continue
        tt = _t(t)
        ages = (tt - set_ns[mask]) // _DAY
        buckets = _bucket(ages)
        later = conf_ns[mask]
        hit = (later > tt) & (later <= tt + HORIZON * _DAY)
        counts = buckets.value_counts().to_dict()
        hits = buckets[hit].value_counts().to_dict()
        for b, c in counts.items():
            if pd.notna(b):
                n[int(b)] += int(c)
                h[int(b)] += int(hits.get(b, 0))
        per_t.append((t, counts, int(hit.sum())))
    p = tuple(h[i] / n[i] if n[i] else 0.0 for i in range(len(n)))
    misses = []
    for t, counts, actual in per_t[-BACKTEST_MONTHS:]:
        forecast = sum(p[int(b)] * c for b, c in counts.items() if pd.notna(b))
        if actual:
            misses.append(abs(forecast - actual) / actual)
    miss = (sorted(misses)[len(misses) // 2] if misses else None)
    return PipelineFit(p=p, miss=miss, backtests=len(misses))


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
                    backtests=fit.backtests, asof=asof)


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
