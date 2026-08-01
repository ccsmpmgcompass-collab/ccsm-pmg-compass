"""Locale-aware DISPLAY formatting for numbers, percentages and dates.

Translating the words but leaving `1,234.5` and `2026-08-05` on the page only
half-localises it. Chile writes one thousand two hundred thirty-four point five
as `1.234,5` and today as `01-08-2026`; to a Chilean reader `1,234.5` is one
point two, and `08-01-2026` is the 8th of January. Neither misreading looks like
an error — the same shape of bug as the Provo metric vocabulary.

Two rules this module exists to keep:

* **Display only.** Nothing here may touch a value on its way to the sheet or
  into a comparison. Dates are stored, keyed and compared as ISO `YYYY-MM-DD`
  everywhere (DAILY_LOG.Date, WEEKLY_KI.week_end_date, every groupby), and a
  `dd-mm-yyyy` string sorts wrong and re-parses wrong. Format at the edge, at
  the moment of rendering, never upstream. Same lesson as
  [[feedback-translated-values-must-not-reach-the-sheet]].

* **No Python `locale`.** `locale.setlocale(locale.LC_TIME, "es_CL")` needs the
  locale to be generated in the OS image; Streamlit Cloud's containers do not
  carry it, so it raises there while working on a dev machine — and
  `setlocale` is process-global, so one page setting it would change formatting
  for every other user served by the same process. The month names and
  separators are therefore tables in this file.

`None` renders as an em dash, never as `0`: None means "we cannot tell" (no
submission yet, or a non-numeric metric) and 0 means "they did nothing". Letting
one print as the other is how a mission gets told it scored zero when in fact
nobody had reported yet.
"""

from __future__ import annotations

from datetime import date, datetime

from app.i18n import get_lang

#: What a missing value looks like. Deliberately not "0" and not "".
NA = "—"

#: Separator and date conventions per display language.
#:
#: Chile (es_CL) uses a comma decimal separator and a dot thousands separator —
#: the reverse of en_US — and writes dates day-first. Every Spanish locale this
#: platform is likely to serve (es_CL, es_MX, es_AR, es_PE) agrees on all three,
#: so the table is keyed by language rather than by full locale; mission_locale()
#: below is still read so a mission that genuinely diverges can be spotted.
_CONVENTIONS: dict[str, dict[str, str]] = {
    "es": {"decimal": ",", "group": ".", "date": "%d-%m-%Y"},
    "en": {"decimal": ".", "group": ",", "date": "%Y-%m-%d"},
}

#: Lowercase per RAE: Spanish month names are common nouns, not proper nouns,
#: and capitalising them is a visible error to a native reader.
_MONTHS_ES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
_MONTHS_ES_ABBR = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)
_MONTHS_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_MONTHS_EN_ABBR = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def mission_locale() -> str:
    """The mission's BCP-47-ish locale from AGENT_CONFIG (CCSM: `es_CL`).

    Read rather than assumed, for the same reason mission_timezone() is: it is
    the mission's own declaration of how it writes things, and it sits beside
    MISSION_TIMEZONE and MISSION_LANGUAGE in the tab the agents already read.
    Imported lazily so pure-logic callers and tests need no live sheet.
    """
    try:
        from app.db.queries import get_config_value
        return (get_config_value("MISSION_LOCALE", "") or "").strip()
    except Exception:
        return ""


def _conv() -> dict[str, str]:
    return _CONVENTIONS.get(get_lang(), _CONVENTIONS["en"])


# ── Numbers ───────────────────────────────────────────────────────────────────

def _group(digits: str, sep: str) -> str:
    out = []
    for i, ch in enumerate(reversed(digits)):
        if i and i % 3 == 0:
            out.append(sep)
        out.append(ch)
    return "".join(reversed(out))


def fmt_number(value, places: int = 0) -> str:
    """A number written the way the active language writes it.

    fmt_number(1234.5, 1) -> "1.234,5" in Spanish, "1,234.5" in English.
    """
    if value is None:
        return NA
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num != num or num in (float("inf"), float("-inf")):  # NaN / inf
        return NA

    conv = _conv()
    sign = "-" if num < 0 else ""
    text = f"{abs(num):.{places}f}"
    whole, _, frac = text.partition(".")
    whole = _group(whole, conv["group"])
    return f"{sign}{whole}{conv['decimal']}{frac}" if frac else f"{sign}{whole}"


def fmt_int(value) -> str:
    """A whole number. Rounds — use fmt_number for anything with decimals."""
    return fmt_number(value, places=0)


def fmt_percent(value, places: int = 0) -> str:
    """A percentage. `value` is ALREADY on the 0-100 scale, not a 0-1 fraction.

    Named and documented this way on purpose: the two conventions are both
    common in this codebase, and a function that silently accepted either would
    turn 87% into 8700% without anything looking wrong. Convert before calling.
    """
    if value is None:
        return NA
    return f"{fmt_number(value, places)}%"


# ── Dates ─────────────────────────────────────────────────────────────────────

def _as_date(value) -> date | None:
    """Coerce the shapes this app carries dates in. Returns None if it is not a
    date, so callers render NA rather than a half-parsed string."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def fmt_date(value) -> str:
    """A date for reading: `01-08-2026` in Spanish, `2026-08-01` in English.

    NEVER use this to build a sheet value, a dict key, or anything that gets
    compared or sorted — see this module's docstring.
    """
    d = _as_date(value)
    if d is None:
        return NA
    return d.strftime(_conv()["date"])


def fmt_month_year(value) -> str:
    """`agosto de 2026` / `August 2026`.

    Replaces `strftime("%B %Y")`, which emits English month names regardless of
    the interface language because it follows the process locale, not ours.
    """
    d = _as_date(value)
    if d is None:
        return NA
    if get_lang() == "es":
        return f"{_MONTHS_ES[d.month - 1]} de {d.year}"
    return f"{_MONTHS_EN[d.month - 1]} {d.year}"


def fmt_day_month(value, with_year: bool = False) -> str:
    """`5 de ago` / `Aug 5` — the compact form used inside date ranges."""
    d = _as_date(value)
    if d is None:
        return NA
    if get_lang() == "es":
        text = f"{d.day} de {_MONTHS_ES_ABBR[d.month - 1]}"
        return f"{text} de {d.year}" if with_year else text
    text = f"{_MONTHS_EN_ABBR[d.month - 1]} {d.day}"
    return f"{text}, {d.year}" if with_year else text


def fmt_date_range(start, end) -> str:
    """`5 de ago – 11 de ago de 2026` / `Aug 5 – Aug 11, 2026`.

    The year is carried once, on the end date, so a range does not read as two
    unrelated dates.
    """
    a, b = _as_date(start), _as_date(end)
    if a is None and b is None:
        return NA
    if a is None or b is None:
        return fmt_day_month(a or b, with_year=True)
    if a == b:
        return fmt_day_month(a, with_year=True)
    return f"{fmt_day_month(a)} – {fmt_day_month(b, with_year=True)}"
