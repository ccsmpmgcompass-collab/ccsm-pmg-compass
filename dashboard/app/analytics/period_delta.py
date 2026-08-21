"""Change over time, computed so the arrow and the number above it agree.

`DASHBOARD_SUMMARY` already carries `val_7d` / `val_14d` / `val_28d`, and the
audit (H3) called a delta the cheapest fix on the board because prior-7d is just
`val_14d - val_7d`. That arithmetic is right and the conclusion was wrong. Run
live on 2026-08-21 it produced +134% on contact attempts, +153% on new people
and +236% on church invites — not because the mission tripled, but because
`DAILY_LOG` begins 2026-08-10 and the "prior seven days" held five days of data
against the current seven. Every arrow on the page would have been green.

So two rules, and this module exists to hold them:

  * **A window is only comparable if it has enough days in it.** A date counts
    as a day of data only when at least half the mission's active areas filed
    that night — otherwise 2026-08-09, a single stray row from one area out of
    43, counts as a full seventh of a week and quietly inflates everything
    measured against it.

  * **Normalize the prior side onto the current side's basis, then compare in
    the tile's own units.** The basis is days for a nightly window and reporting
    areas for a weekly one, but the move is the same either way: scale the prior
    figure up to what it would have been on the current window's footing, and
    subtract. The tile's big number stays a mission total, and so does the
    change printed under it — no tile ever shows a total with a per-day rate
    beneath it.

The window boundaries are computed here rather than reused from Apps Script on
purpose. `CCSM_Agent3.gs:571` cuts at `date >= today - 7`, which spans **eight**
calendar dates, while the prior window derived from `val_14d - val_7d` spans
seven. That is a permanent ~14% inflation that appears each evening as the
eighth day's reports land and settles back at the next nightly rebuild.

Pure: no Streamlit, no sheet access. Formatting is deliberately left to the
caller — this module decides *what* to say about a change, `render_kpi_row`
decides how it looks.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

#: Share of the mission's active areas that must file on a date before that
#: date counts as a day of data. Same 0.5 as zone_comparison's
#: DEFAULT_KI_MIN_SHARE, and for the same reason: a handful of areas is not
#: the mission, and a measurement resting on them should not look like one
#: that rests on all of them.
REPORTING_MIN_SHARE = 0.5

#: How many reporting days a window needs before it may be compared at all.
#: Below this the arrow is suppressed and the section says why.
MIN_COMPARABLE_DAYS = 5

#: Length of a comparison window, in days.
WINDOW_DAYS = 7

#: A prior value below this prints an absolute change instead of a percentage.
#: A percentage on a small count is noise dressed as a trend: baptisms going
#: 3 -> 5 is "+67%", which is the same fact as "+2" and the only one of the two
#: that admits how small the sample is. Catches baptisms, baptismal calendars,
#: member referrals and RC lessons; leaves contacts, lessons and texts on
#: percentages.
SMALL_COUNT_MAX = 25.0

#: A change smaller than this reads as flat rather than as a trend. Week-to-week
#: noise across 43 areas is comfortably 3-4%; painting a -3% wobble amber trains
#: the reader to ignore the colour altogether.
NEUTRAL_BAND_PCT = 5.0

#: Below this a fall is red rather than amber.
SEVERE_DROP_PCT = -15.0

#: A rate that moves less than this many percentage points reads as flat.
#:
#: Two, not one, and the live data is why: contact_rate went 47,5% to 46,4%
#: between the two windows either side of 2026-08-20, and at a one-point band
#: that 1,1-point wobble would have drawn an amber down-arrow on the mission's
#: contacting. Same reasoning as NEUTRAL_BAND_PCT's five percent — a colour
#: spent on noise teaches the reader to stop believing the colours. It still
#: lets through everything that moved for a reason: mc_rate's -2,0 and
#: close_rate's +2,3 both register.
#:
#: This is a provisional figure. DAILY_LOG began 2026-08-10, so there is not yet
#: enough history to measure how much these four rates actually vary week to
#: week; revisit once six to eight weeks are in.
NEUTRAL_BAND_POINTS = 2.0

#: Below this a fall in a rate is red rather than amber. Five points off a
#: conversion rate is a different order of event from five percent off a count:
#: contact_rate going 46 -> 41 means a tenth of the mission's contacting stopped
#: landing.
SEVERE_DROP_POINTS = -5.0

UP, FLAT, DOWN = 1, 0, -1

#: What `period_delta` puts in "show". POINTS is `point_delta`'s.
PERCENT, ABSOLUTE, POINTS = "percent", "absolute", "points"


def _dates(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["Date"], errors="coerce").dt.date


def reporting_dates(daily_log: pd.DataFrame, active_areas: int,
                    *, min_share: float = REPORTING_MIN_SHARE) -> list:
    """Dates in ``daily_log`` on which the mission actually reported.

    A date qualifies when at least ``min_share`` of the active areas filed a
    nightly report. Pass ``len(get_submitting_areas())`` as ``active_areas``.

    With ``active_areas`` unknown (0 or less) there is nothing to take a share
    of, so every date holding any row qualifies — a degraded but honest reading,
    rather than silently returning nothing and blanking the whole page.
    """
    if daily_log is None or daily_log.empty:
        return []
    if "Date" not in daily_log.columns or "Area" not in daily_log.columns:
        return []
    counts = daily_log.assign(__d=_dates(daily_log)).dropna(subset=["__d"])
    if counts.empty:
        return []
    per_date = counts.groupby("__d")["Area"].nunique()
    if active_areas and active_areas > 0:
        per_date = per_date[per_date >= min_share * active_areas]
    return sorted(per_date.index)


def window_pair(anchor: date, *, window_days: int = WINDOW_DAYS) -> tuple:
    """``(current_start, current_end, prior_start, prior_end)`` around ``anchor``.

    ``anchor`` is the most recent *reporting* day, not today. The nightly agent
    runs before every area has filed, so on any given afternoon `DAILY_LOG`'s
    newest date is yesterday's; anchoring on today would average seven days over
    a six-day sample and dip every morning.

    Both windows are exactly ``window_days`` long and do not overlap.
    """
    cur_end = anchor
    cur_start = anchor - timedelta(days=window_days - 1)
    prior_end = cur_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=window_days - 1)
    return cur_start, cur_end, prior_start, prior_end


def window_totals(daily_log: pd.DataFrame, start: date, end: date) -> dict:
    """Mission-wide totals per metric for ``start``..``end`` inclusive.

    Non-numeric DAILY_LOG columns (effort's "Todo", exchanges' "TRUE") coerce to
    NaN and sum to 0, which is what the nightly agent does with them too.
    """
    if daily_log is None or daily_log.empty or "Date" not in daily_log.columns:
        return {}
    if start is None or end is None or end < start:
        return {}
    d = _dates(daily_log)
    window = daily_log[(d >= start) & (d <= end)]
    if window.empty:
        return {}
    cols = [c for c in window.columns
            if c not in ("Date", "Area", "Zone", "District")]
    if not cols:
        return {}
    totals = window[cols].apply(pd.to_numeric, errors="coerce").sum()
    return {k: float(v) for k, v in totals.items() if pd.notna(v)}


def window_areas(daily_log: pd.DataFrame, start: date, end: date) -> int:
    """Distinct areas that filed a nightly report in ``start``..``end``."""
    if daily_log is None or daily_log.empty:
        return 0
    if "Date" not in daily_log.columns or "Area" not in daily_log.columns:
        return 0
    if start is None or end is None or end < start:
        return 0
    d = _dates(daily_log)
    window = daily_log[(d >= start) & (d <= end)]
    return int(window["Area"].nunique()) if not window.empty else 0


def days_in_window(dates, start: date, end: date) -> int:
    """How many of ``dates`` (from ``reporting_dates``) fall in the window."""
    if not dates or start is None or end is None:
        return 0
    return sum(1 for d in dates if start <= d <= end)


def period_delta(current, prior, *, current_basis, prior_basis,
                 min_basis: int = MIN_COMPARABLE_DAYS,
                 small_count_max: float = SMALL_COUNT_MAX,
                 neutral_band: float = NEUTRAL_BAND_PCT) -> dict | None:
    """How ``current`` compares to ``prior``, or ``None`` if it may not be said.

    ``current_basis`` / ``prior_basis`` are what each figure rests on — days of
    data for a nightly window, reporting areas for a weekly one. The prior side
    is scaled onto the current side's basis before subtracting, so the returned
    change is in the same units as ``current`` and can sit under it without
    changing what the tile is measuring.

    Returns ``None`` when either basis is below ``min_basis``, and when the
    prior side is zero with nothing new to report. It returns a result — not
    ``None`` — for a rise from zero: a week that went 0 baptisms to 5 is the
    best news the page can carry, and a division by zero should not swallow it.

    The dict is a description, not a rendering:

      ``pct``        percent change, or None when the prior side was zero
      ``change``     absolute change, in the tile's own units
      ``show``       PERCENT or ABSOLUTE — which of the two to print
      ``direction``  UP / FLAT / DOWN, already through the neutral band
      ``prior_adjusted``  the prior figure on the current basis
    """
    try:
        current = float(current)
        prior = float(prior)
        current_basis = float(current_basis)
        prior_basis = float(prior_basis)
    except (TypeError, ValueError):
        return None

    if current_basis < min_basis or prior_basis < min_basis:
        return None
    if prior_basis <= 0 or current_basis <= 0:
        return None

    prior_adjusted = prior * (current_basis / prior_basis)
    change = current - prior_adjusted

    if prior_adjusted <= 0:
        if current <= 0:
            return None
        # No baseline to take a percentage of. The absolute rise is the whole
        # of what can honestly be said, and it is worth saying.
        return {"pct": None, "change": change, "show": ABSOLUTE,
                "direction": UP, "prior_adjusted": prior_adjusted}

    pct = change / prior_adjusted * 100.0

    if abs(pct) < neutral_band:
        direction = FLAT
    elif pct > 0:
        direction = UP
    else:
        direction = DOWN

    # The small-count test is on the prior side, because the prior side is the
    # denominator that makes a percentage swing.
    show = ABSOLUTE if prior_adjusted < small_count_max else PERCENT

    # An absolute change that rounds away to nothing is flat, whatever the
    # percentage says: "up 0" under an arrow is not a claim worth making.
    if show == ABSOLUTE and round(change) == 0:
        direction = FLAT

    return {"pct": pct, "change": change, "show": show,
            "direction": direction, "prior_adjusted": prior_adjusted}


def point_delta(current, prior, *, current_basis, prior_basis,
                min_basis: int = MIN_COMPARABLE_DAYS,
                neutral_band: float = NEUTRAL_BAND_POINTS) -> dict | None:
    """How a RATE moved, in percentage points. The ratio counterpart of `period_delta`.

    Both arguments are already on the 0-100 scale. The result carries ``points``
    where `period_delta` carries ``change``, and its ``show`` is always
    ``POINTS``.

    Two things are deliberately different from `period_delta`:

      * **Nothing is scaled.** A rate is a ratio, so it does not grow with the
        number of days behind it the way a total does; normalizing the prior
        side onto the current basis would be arithmetic with no meaning. The
        bases are still required, and still gate — a rate computed over four
        days of reporting is as unreliable a baseline as a total is — but they
        only decide whether the comparison may be made, never what it says.

      * **The change is not expressed as a percentage.** A percent change of a
        percentage is the most reliable way to overstate a small movement:
        close_rate going 7,4% to 9,7% is "+31%", which reads as a mission
        transformed and means it invited about two more people per hundred
        lessons. The honest unit is the point.

    Returns None when either side is unreadable (a window with no denominator
    has no rate to compare) or either basis is below ``min_basis``.
    """
    if current is None or prior is None:
        return None
    try:
        current = float(current)
        prior = float(prior)
        current_basis = float(current_basis)
        prior_basis = float(prior_basis)
    except (TypeError, ValueError):
        return None
    if current != current or prior != prior:  # NaN
        return None
    if current_basis < min_basis or prior_basis < min_basis:
        return None

    points = current - prior
    if abs(points) < neutral_band:
        direction = FLAT
    elif points > 0:
        direction = UP
    else:
        direction = DOWN

    return {"pct": None, "change": None, "points": points, "show": POINTS,
            "direction": direction, "prior_adjusted": prior}
