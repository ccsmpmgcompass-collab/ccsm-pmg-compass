"""Which transfer are we in — one answer, for every page that asks.

The mission's calendar is six-week transfer cycles, and three separate places
need to know where today sits in one: the Traslados page (which week of the
cycle, days left), the Desgloses period picker ("Este cambio hasta hoy"), and
the Panel's compliance rankings. Before this module, only Traslados knew, in a
private function; audit item E2 was about not letting a second copy exist.

The source of truth is the TRANSFER_SCHEDULE tab — `Transfer_Number |
Start_Date | Weeks | Status`. It was empty until 2026-09-03 and now holds the
mission's real cycles (2026-06-15, 2026-07-27, and 2026-09-07 upcoming).

**Status does not decide which transfer is current.** The current transfer is
the latest row whose start date has arrived, whatever its Status says. That is
the behaviour `views/12_Traslados.py` has always had, and keeping it means the
row scheduled for 2026-09-07 becomes current on 2026-09-07 by itself, rather
than waiting for someone to remember to flip "Scheduled" to "Actual". Status
is still meaningful — `queries.get_recent_transfer_dates` filters on it for the
area-lineage badge, and CCSM_Agent2.gs reads only `Actual` rows when it
recalibrates goals — but that is a different question from "what week is it".

Falls back to AGENT_CONFIG's `TRANSFER_START_DATE` with a six-week assumption
when the schedule is empty, so a mission that has not filled the tab in still
gets a window; the caller can tell the two apart by the returned `source`.
"""

from __future__ import annotations

from datetime import date, timedelta

#: Assumed cycle length when a row does not say, or when there is no row at all
#: and only TRANSFER_START_DATE is available.
DEFAULT_WEEKS = 6


def transfer_rows() -> list[dict]:
    """TRANSFER_SCHEDULE as dicts, oldest first.

    Keys: ``number``, ``start`` (date), ``weeks`` (int >= 1), ``status``.

    A row whose Start_Date will not parse is dropped: a schedule row that
    cannot be placed on a calendar cannot tell anyone which week it is.
    """
    from app.db.sheets_client import read_tab

    df = read_tab("TRANSFER_SCHEDULE")
    if df.empty or "Start_Date" not in df.columns:
        return []
    out: list[dict] = []
    for _, r in df.iterrows():
        raw = str(r.get("Start_Date", "")).strip()[:10]
        try:
            start = date.fromisoformat(raw)
        except ValueError:
            continue
        try:
            weeks = int(float(str(r.get("Weeks", "")).strip() or DEFAULT_WEEKS))
        except (TypeError, ValueError):
            weeks = DEFAULT_WEEKS
        out.append({
            "number": str(r.get("Transfer_Number", "")).strip(),
            "start": start,
            "weeks": max(1, weeks),
            "status": str(r.get("Status", "")).strip(),
        })
    return sorted(out, key=lambda x: x["start"])


def _fallback_row() -> dict | None:
    """AGENT_CONFIG's TRANSFER_START_DATE as a single synthetic cycle.

    The same value CCSM_Agent3 measures its transfer-to-date totals from, so a
    mission running on the fallback still sees one window described two ways
    rather than two windows.
    """
    from app.db.queries import get_config_value

    raw = (get_config_value("TRANSFER_START_DATE", "") or "").strip()[:10]
    try:
        return {"number": "", "start": date.fromisoformat(raw),
                "weeks": DEFAULT_WEEKS, "status": ""}
    except ValueError:
        return None


def transfer_window(offset: int = 0, today: date | None = None) -> dict | None:
    """The transfer `offset` cycles back from the current one, or None.

    ``offset=0`` is the transfer today falls in; ``offset=1`` the one before
    it. Returns ``{"start", "end", "number", "weeks", "status", "source"}``
    with both dates inclusive, or None when that cycle is not in the schedule —
    which is the honest answer for "last transfer" on a mission whose schedule
    only reaches back one cycle.

    ``end`` is the day before the NEXT cycle starts when a next row exists, so
    a schedule that records a short or long cycle is described as it really
    was rather than as ``start + weeks``. Only the final row falls back to its
    own ``weeks``, since nothing follows it to bound it.

    ``source`` is ``"schedule"`` or ``"config"`` — the caller uses it to say
    out loud when a window is an assumption rather than a record.
    """
    if today is None:
        from app.utils.area_helpers import mission_today
        today = mission_today()

    rows = transfer_rows()
    source = "schedule"
    if not rows:
        fb = _fallback_row()
        if fb is None:
            return None
        rows, source = [fb], "config"

    # The current cycle is the latest one that has STARTED — not the latest
    # marked "Actual". See the module docstring.
    started = [i for i, r in enumerate(rows) if r["start"] <= today]
    if not started:
        return None
    idx = started[-1] - offset
    if idx < 0 or idx >= len(rows):
        return None

    row = rows[idx]
    if idx + 1 < len(rows):
        end = rows[idx + 1]["start"] - timedelta(days=1)
    else:
        end = row["start"] + timedelta(weeks=row["weeks"]) - timedelta(days=1)
    return {"start": row["start"], "end": end, "number": row["number"],
            "weeks": row["weeks"], "status": row["status"], "source": source}


def transfer_period_bounds(today: date | None = None) -> dict:
    """The two transfer windows the period pickers offer, as a label -> bounds
    map ready to hand to `_kpi_period_bounds` / `compliance_rankings`.

    ``{"This Transfer So Far": (start, today), "Last Transfer": (start, end)}``
    — a label is simply absent when the schedule cannot supply it, which is
    what makes the picker able to hide an option rather than offer one that
    resolves to nothing.

    "This Transfer So Far" ends TODAY, not at the cycle's end: it is an
    in-progress period like "This Month So Far", and running it to a future
    date would divide six weeks of goal by however many days had actually
    happened.
    """
    if today is None:
        from app.utils.area_helpers import mission_today
        today = mission_today()

    out: dict[str, tuple[date, date]] = {}
    cur = transfer_window(0, today)
    if cur:
        out["This Transfer So Far"] = (cur["start"], min(today, cur["end"]))
    prev = transfer_window(1, today)
    if prev:
        out["Last Transfer"] = (prev["start"], prev["end"])
    return out
