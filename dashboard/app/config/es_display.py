"""How Chile writes a date and a number, with no Streamlit in the way.

Here rather than in `app/i18n/formats.py` for the same reason the goal-bar
tiers moved to `theme.py`: **`app/i18n/__init__.py` imports Streamlit**, so
importing anything under that package — even a tuple of month names — drags a
browser into a layer that must run in a background build and in a test.
`app/reports` is pure by acceptance test, and the council packet is Spanish
only (decision 3), so it needs these without needing `get_lang()`.

`i18n/formats.py` takes its Spanish tables and its digit grouping from here, so
there is still one home for each of them: a month cannot be spelled two ways in
one app, and a thousand cannot be punctuated two ways on one page.

Two rules, both inherited from `formats.py` and both worth repeating:

* **Display only.** Nothing here may touch a value on its way to the sheet or
  into a comparison. Dates are stored, keyed and compared as ISO everywhere,
  and a `dd-mm-yyyy` string sorts wrong and re-parses wrong. Format at the
  edge.

* **No Python `locale`.** `setlocale(LC_TIME, "es_CL")` needs the locale
  generated in the OS image, which Streamlit Cloud's containers do not carry,
  and it is process-global besides — one page setting it would change
  formatting for every other user served by the same process.

`None` renders as an em dash, never as `0`: None is "we cannot tell" and 0 is
"they did nothing", and letting one print as the other is how a mission gets
told it scored zero when nobody had reported yet.
"""

from __future__ import annotations

from datetime import date

# ── Dates ─────────────────────────────────────────────────────────────────────

MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

MONTHS_ABBR = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)

#: What nothing prints as. An em dash, never a zero and never a blank cell.
NA = "—"


def day_month(value: date | None, *, with_year: bool = False) -> str:
    """`5 de ago`, or `5 de ago de 2026` — the compact form inside a range."""
    if not isinstance(value, date):
        return NA
    out = f"{value.day} de {MONTHS_ABBR[value.month - 1]}"
    return f"{out} de {value.year}" if with_year else out


def long_date(value: date | None) -> str:
    """`21 de septiembre de 2026` — a date written out, for a cover."""
    if not isinstance(value, date):
        return NA
    return f"{value.day} de {MONTHS[value.month - 1]} de {value.year}"


def day_range(start: date | None, end: date | None) -> str:
    """`7 de sep - 18 de oct de 2026`, with the year said once when they differ.

    The separator is a hyphen, not an en dash or an arrow: the packet's base-14
    encoding reaches neither without ReportLab silently switching typeface
    (`packet_parts.text`), and a range that prints in Symbol is worse than one
    that prints plainly.
    """
    if not isinstance(start, date) or not isinstance(end, date):
        return NA
    cross_year = start.year != end.year
    return (f"{day_month(start, with_year=cross_year)} - "
            f"{day_month(end, with_year=True)}")


# ── Numbers ───────────────────────────────────────────────────────────────────

#: Chile writes one thousand two hundred thirty-four point five as `1.234,5`.
#: To a Chilean reader `1,234.5` is one point two — a misreading that does not
#: look like an error, which is what makes it worth a module.
GROUP = "."
DECIMAL = ","


def group_digits(digits: str, sep: str) -> str:
    """`1234567` -> `1.234.567`. Shared with `i18n/formats.py`, which needs the
    same grouping with a different separator."""
    out = []
    for i, ch in enumerate(reversed(digits)):
        if i and i % 3 == 0:
            out.append(sep)
        out.append(ch)
    return "".join(reversed(out))


def number(value, places: int = 0) -> str:
    """A number, written the way Chile writes it. None is NA, never 0."""
    if value is None:
        return NA
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num != num or num in (float("inf"), float("-inf")):
        return NA
    sign = "-" if num < 0 else ""
    whole, _, frac = f"{abs(num):.{places}f}".partition(".")
    whole = group_digits(whole, GROUP)
    return f"{sign}{whole}{DECIMAL}{frac}" if frac else f"{sign}{whole}"


def integer(value) -> str:
    """A whole number. Rounds — use `number` for anything with decimals."""
    return number(value, places=0)


def percent(value, places: int = 0) -> str:
    """A percentage. ``value`` is ALREADY on the 0-100 scale, not a fraction.

    Named and documented this way on purpose: both conventions are common in
    this codebase, and a function that silently accepted either would turn 87%
    into 8700% without anything looking wrong.
    """
    if value is None:
        return NA
    return f"{number(value, places)}%"


def signed_percent(value, places: int = 0) -> str:
    """`+12%` / `-9%` — a CHANGE, where the sign is the point.

    The sign is written out because a change chip's triangle carries the
    direction in colour and shape, and a photocopy loses the colour.
    """
    if value is None:
        return NA
    sign = "+" if value > 0 else ""
    return f"{sign}{number(value, places)}%"
