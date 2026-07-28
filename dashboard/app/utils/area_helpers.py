from datetime import date, datetime, timedelta, time

# Nightly submissions for "today" aren't reliably in the sheet until the evening
# refresh/report cycle (Agent3 at 9 PM, Agent7 at 9:30 PM, Mountain Time). Before
# this cutoff we don't count the current day at all, so it doesn't read as a miss
# and break the streak.
NIGHTLY_CUTOFF = time(21, 30)  # 9:30 PM
_MOUNTAIN_TZ = "America/Denver"


def _mountain_now() -> datetime:
    """Current wall-clock time in mission (Mountain) time. Falls back to naive
    local time if zoneinfo is unavailable so callers never crash."""
    try:
        import zoneinfo
        return datetime.now(zoneinfo.ZoneInfo(_MOUNTAIN_TZ))
    except Exception:
        return datetime.now()


def mission_today(now: datetime = None) -> date:
    """Today's date in mission (Mountain) time.

    Always prefer this over date.today() for anything user-facing: the app runs
    on Streamlit Cloud in UTC, which rolls over to tomorrow in the early evening
    Mountain — i.e. right when the nightly reports are being submitted.
    `now` is injectable for testing.
    """
    return (now or _mountain_now()).date()


def compliance_anchor_date(now: datetime = None) -> date:
    """The most recent day that should count toward submission compliance.

    Returns today once it's past NIGHTLY_CUTOFF (9:30 PM MT); otherwise returns
    yesterday, so the current in-progress day is not counted until submissions
    have had a chance to land. `now` is injectable for testing.
    """
    if now is None:
        now = _mountain_now()
    if now.time() >= NIGHTLY_CUTOFF:
        return now.date()
    return now.date() - timedelta(days=1)


def calc_compliance_stats(
    submitted_dates: set,
    window_start: str,
    window_end: str,
) -> dict:
    """
    Returns submitted, possible, rate, current_streak, longest_streak
    for the given YYYY-MM-DD window.
    current_streak counts consecutive submitted days backward from window_end.
    """
    s, e = date.fromisoformat(window_start), date.fromisoformat(window_end)
    all_days = []
    d = s
    while d <= e:
        all_days.append(d.isoformat())
        d += timedelta(days=1)

    possible = len(all_days)
    submitted = sum(1 for day in all_days if day in submitted_dates)
    rate = submitted / possible if possible > 0 else 0.0

    longest = run = 0
    for day in all_days:
        if day in submitted_dates:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    current = 0
    for day in reversed(all_days):
        if day in submitted_dates:
            current += 1
        else:
            break

    return {
        "submitted": submitted,
        "possible": possible,
        "rate": rate,
        "current_streak": current,
        "longest_streak": longest,
    }


def latest_due_sunday(now: datetime = None) -> date:
    """The most recent week-ending Sunday whose weekly report is 'due'.

    The weekly report covers Mon–Sun. A week's ending Sunday only counts toward
    compliance once we're past it (Monday onward), so an in-progress week never
    reads as a miss. If today is Sunday, the week ending today isn't due yet, so
    step back to the previous Sunday. `now` is injectable for testing.
    """
    d = (now or _mountain_now()).date()
    offset = (d.weekday() + 1) % 7      # days since Sunday (Sun=0, Mon=1, …)
    last_sun = d - timedelta(days=offset)
    if offset == 0:                     # today IS Sunday → not due yet
        last_sun -= timedelta(days=7)
    return last_sun


def submission_week_sunday(submission_date: str) -> str:
    """Week-ending Sunday a weekly submission belongs to, keyed by the DAY it was
    submitted (not the in-form date field). A Sunday submission → that Sunday; a
    late Mon/Tue submission → the prior Sunday. Returns '' on unparseable input."""
    try:
        d = date.fromisoformat(str(submission_date)[:10])
    except (ValueError, TypeError):
        return ""
    return (d - timedelta(days=(d.weekday() + 1) % 7)).isoformat()


def weekly_due_weeks(
    window_start: str,
    anchor_sunday: date = None,
    n_weeks: int = 8,
) -> list:
    """List of week-ending Sunday date-strings (oldest first) that are 'due',
    going back n_weeks from anchor_sunday and floored at window_start.

    anchor_sunday defaults to latest_due_sunday(). window_start ('' = no floor)
    is typically SYSTEM_START_DATE (or TRANSFER_START_DATE for renamed areas);
    weeks whose Sunday falls before it are dropped so pre-tracking weeks aren't
    counted as misses.
    """
    end = anchor_sunday if anchor_sunday is not None else latest_due_sunday()
    weeks = [(end - timedelta(weeks=i)).isoformat() for i in range(n_weeks)]
    weeks.reverse()                      # oldest first
    if window_start:
        weeks = [w for w in weeks if w >= window_start]
    return weeks


_METRIC_LABEL_OVERRIDES = {
    "nm_doors":              "NM Attempted",
    "nm_lessons":            "NM Lessons",
    "nm_contacted":          "NM Contacted",
    "nm_meaningful":         "NM Meaningful Convos",
    "nm_texts":              "NM Texts Sent",
    "mmm_sent":              "MMM Sent",
    "lsi_given":             "LSI Given",
    "lsi_followups":         "LSI Follow-Ups",
    "rc_lessons":            "RC Lessons",
    "la_lessons":            "LA Lessons",
    "la_Attempt":            "LA Attempted",
    "fellowshipper_Attempt": "Fellowshipper Attempted",
    "aux_Attempt":           "Aux/Coord Attempted",
    "info_Attempt":          "Informational Attempted",
    "locos_Attempt":         "LOCOS Attempted",
    "rc_total":              "RC Could Have Attended",
    "date_metric":           "Date",
}


def format_metric_label(key: str) -> str:
    """Convert a metric key to its display label (snake_case → Title Case
    fallback, with overrides for keys whose friendly name differs)."""
    key = str(key)
    if key in _METRIC_LABEL_OVERRIDES:
        return _METRIC_LABEL_OVERRIDES[key]
    return key.replace("_", " ").title()


def build_calendar_data(
    submitted_dates: set,
    window_end_date: str,
    n_weeks: int = 5,
    anchor_date: date = None,
    blitz_dates: set = None,
) -> list:
    """
    Build n_weeks x 7 calendar grid ending on window_end_date (week aligns to Sunday).
    Returns list of weeks (oldest first). Each week is 7 dicts:
      {"date": "YYYY-MM-DD", "submitted": bool, "future": bool, "blitz": bool}

    Days after `anchor_date` are marked future (uncounted). anchor_date defaults
    to today; pass compliance_anchor_date() so the current day reads as future
    (not a miss) until the 9:30 PM cutoff.

    Days in `blitz_dates` are marked blitz (True); all others default to False.
    """
    end = date.fromisoformat(window_end_date)
    days_to_sunday = (6 - end.weekday()) % 7
    grid_end = end + timedelta(days=days_to_sunday)
    grid_start = grid_end - timedelta(weeks=n_weeks) + timedelta(days=1)
    today = anchor_date if anchor_date is not None else date.today()

    weeks = []
    week_start = grid_start
    for _ in range(n_weeks):
        week = []
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            day_str = day.isoformat()
            week.append({
                "date": day_str,
                "submitted": day_str in submitted_dates,
                "future": day > today,
                "blitz": day_str in (blitz_dates or set()),
            })
        weeks.append(week)
        week_start += timedelta(weeks=1)
    return weeks
