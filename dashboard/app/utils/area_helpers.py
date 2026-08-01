from datetime import date, datetime, timedelta, time

# Nightly submissions for "today" aren't reliably in the sheet until the evening
# refresh runs (CCSM_Agent3's evening trigger, 9 PM mission-local — see
# CCSM_TRIGGER_SCHEDULE in CCSM_Setup.gs). Before this cutoff we don't count the
# current day at all, so it doesn't read as a miss and break the streak.
NIGHTLY_CUTOFF = time(21, 30)  # 9:30 PM

# Fallback only. The real value comes from AGENT_CONFIG's MISSION_TIMEZONE,
# which is what every Apps Script agent uses (CCSM_Helpers.getMissionTimezone),
# so the dashboard and the agents agree on which day it is.
#
# This was hardcoded to "America/Denver" — Utah Provo's zone, inherited with the
# fork. Chile runs UTC-4/-3 against Denver's UTC-7/-6, so for the three-to-four
# hours around local midnight `mission_today()` returned YESTERDAY for CCSM.
# Everything date-anchored was affected: which day counts as missed, whether a
# streak survives, which week a submission lands in.
_FALLBACK_TZ = "America/Santiago"


def mission_timezone() -> str:
    """The mission's IANA timezone from AGENT_CONFIG.

    Imported lazily: this module is imported by pure-logic paths (and by tests)
    that must not require Streamlit secrets or a live sheet just to compute a
    date difference.
    """
    try:
        from app.db.queries import get_config_value
        return (get_config_value("MISSION_TIMEZONE", "") or "").strip() or _FALLBACK_TZ
    except Exception:
        return _FALLBACK_TZ


def _mission_now() -> datetime:
    """Current wall-clock time in the mission's timezone. Falls back to naive
    local time if zoneinfo is unavailable so callers never crash."""
    try:
        import zoneinfo
        return datetime.now(zoneinfo.ZoneInfo(mission_timezone()))
    except Exception:
        return datetime.now()


def mission_today(now: datetime = None) -> date:
    """Today's date in the mission's own timezone.

    Always prefer this over date.today() for anything user-facing: the app runs
    on Streamlit Cloud in UTC, which rolls over to tomorrow in the evening
    mission-local — i.e. right when the nightly reports are being submitted.
    `now` is injectable for testing.
    """
    return (now or _mission_now()).date()


def compliance_anchor_date(now: datetime = None) -> date:
    """The most recent day that should count toward submission compliance.

    Returns today once it's past NIGHTLY_CUTOFF (9:30 PM MT); otherwise returns
    yesterday, so the current in-progress day is not counted until submissions
    have had a chance to land. `now` is injectable for testing.
    """
    if now is None:
        now = _mission_now()
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
    d = (now or _mission_now()).date()
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


def format_metric_label(key: str) -> str:
    """Display label for a metric key.

    Delegates to app.config.metric_catalog, which reads the live
    QUESTIONS_CONFIG. This function used to carry its own override map — one of
    three copies of Utah Provo's metric vocabulary (nm_doors, lsi_given,
    locos_Attempt, date_metric …), none of which is a question on a CCSM form.
    Three copies meant three things to keep in step, and they were already out
    of step with each other and with the mission.

    Falls back to Title Case if the catalogue is unavailable, so a label never
    takes down a page that was only trying to draw a chart axis.
    """
    key = str(key)
    try:
        from app.config.metric_catalog import format_metric_label as _label
        from app.i18n import get_lang
        return _label(key, lang=get_lang())
    except Exception:
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
