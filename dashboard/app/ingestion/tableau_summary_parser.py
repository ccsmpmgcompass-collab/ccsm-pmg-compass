"""Parse a Tableau "Mission Finding Summary" PDF into one month of totals.

This is the source for ``TABLEAU_BAPTISMS``. It is deliberately NOT derived by
counting ``confirmation_date`` in the person-level Detail export: cross-checking
all 31 monthly PDFs (Jan 2024 - Jul 2026) against Detail showed the PDF totals
**1,071** baptisms where Detail counts only **834**, with just 1 of 31 months
matching exactly. The gap is large early (2024-01: 26 vs 1) and small recently
(2026: 0 to -6) - the signature of Preach My Gospel app adoption ramping through
2024, so a person baptized before their finding record existed has no Detail row.
The PDF figure is the certified one; Detail is the funnel's source, not the
baptism count's. See ``get_baptisms_actual()`` in app/db/queries.py, whose
docstring already names this view.

``parse_summary_text`` is pure and takes the already-extracted text, so the
parsing rules are unit-testable without carrying PDF fixtures in the repo.
``parse_summary_pdf`` is the thin wrapper that reads a file; it imports pypdf
lazily so that importing this module never requires the dependency.

Two extraction quirks, both discovered against the real files and both load-
bearing - do not "simplify" them away:

1. **The funnel's values arrive REVERSED relative to its labels.** Tableau
   renders the stage list bottom-to-top, so the text stream carries
   ``Baptized and Confirmed`` last among the labels but its value first among
   the numbers.

2. **The grand-total block is OFFSET BY ONE.** Each value is emitted *before*
   the label it belongs to, so the number sitting after ``Grand Total`` is
   actually Total People Baptized, and so on down the block.

Because those two regions are laid out independently, they cross-check each
other: the funnel's first value must equal the block's "New People Being Taught"
and its last must equal the block's "Total People Baptized". ``parse_summary_text``
refuses to return a result when they disagree, which is what makes a silent
mis-parse impossible rather than merely unlikely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict

#: Funnel stage order as the PDF LABELS them (top to bottom). Values in the
#: text stream are reversed against this - see quirk 1.
FUNNEL_LABELS = (
    "new_people_being_taught",
    "multiple_lessons",
    "church_attendance",
    "baptism_goal_date_set",
    "baptized_and_confirmed",
)

_RE_WINDOW = re.compile(
    r"Start Date (\d{1,2})/(\d{1,2})/(\d{4}) End Date (\d{1,2})/(\d{1,2})/(\d{4})"
)

# The four headline numbers. Note the capture groups sit BEFORE the label they
# belong to (quirk 2): group(1) is Baptized, group(2) is Being Taught, and so on.
_RE_TOTALS = re.compile(
    r"Grand Total ([\d,]+) "
    r"Total People Baptized ([\d,]+) "
    r"New People Being Taught ([\d,]+) "
    r"Total People Found ([\d,]+) "
    r"Total People Referred"
)

# The mission-wide funnel, which follows the "All Outcomes" heading. Five
# numbers, reversed (quirk 1).
_RE_FUNNEL = re.compile(
    r"All Outcomes.*?Baptized and Confirmed ((?:[\d,]+ ){4}[\d,]+)"
)


class SummaryParseError(ValueError):
    """Raised when a PDF's text does not parse, or fails its own cross-check."""


@dataclass(frozen=True)
class MonthlySummary:
    """One month of mission-wide finding totals."""

    month: str          # 'YYYY-MM', taken from the window INSIDE the file
    start_date: str     # 'YYYY-MM-DD'
    end_date: str       # 'YYYY-MM-DD'
    people_found: int
    people_referred: int
    people_being_taught: int
    multiple_lessons: int
    church_attendance: int
    baptism_goal_date_set: int
    baptized: int

    def as_dict(self) -> dict:
        return asdict(self)


def _num(raw: str) -> int:
    return int(raw.replace(",", "").strip())


def _flatten(text: str) -> str:
    """Collapse the PDF's tabs/newlines into single spaces.

    pypdf emits this layout with tab separators inside a line and newlines
    between them; every pattern here is written against a single flat string.
    """
    return re.sub(r"\s+", " ", text.replace("\t", " ")).strip()


def parse_summary_text(text: str) -> MonthlySummary:
    """Parse already-extracted PDF text into a :class:`MonthlySummary`.

    Raises :class:`SummaryParseError` if either region is missing or if the two
    regions disagree.
    """
    flat = _flatten(text)

    win = _RE_WINDOW.search(flat)
    if not win:
        raise SummaryParseError("no 'Start Date … End Date' window found")
    s_mo, s_day, s_yr, e_mo, e_day, e_yr = (int(g) for g in win.groups())

    tot = _RE_TOTALS.search(flat)
    if not tot:
        raise SummaryParseError("no Grand Total block found")
    # Offset by one - quirk 2.
    baptized, being_taught, found, referred = (_num(g) for g in tot.groups())

    fun = _RE_FUNNEL.search(flat)
    if not fun:
        raise SummaryParseError("no 'All Outcomes' funnel found")
    # Reversed - quirk 1.
    stages = list(reversed([_num(v) for v in fun.group(1).split()]))
    funnel = dict(zip(FUNNEL_LABELS, stages))

    # The two regions are laid out independently; if they agree, the parse is
    # right. If they don't, something about the export changed and a silent
    # wrong number is the worst possible outcome.
    if funnel["new_people_being_taught"] != being_taught:
        raise SummaryParseError(
            f"cross-check failed: funnel says {funnel['new_people_being_taught']} "
            f"being taught, totals block says {being_taught}"
        )
    if funnel["baptized_and_confirmed"] != baptized:
        raise SummaryParseError(
            f"cross-check failed: funnel says {funnel['baptized_and_confirmed']} "
            f"baptized, totals block says {baptized}"
        )

    return MonthlySummary(
        month=f"{s_yr:04d}-{s_mo:02d}",
        start_date=f"{s_yr:04d}-{s_mo:02d}-{s_day:02d}",
        end_date=f"{e_yr:04d}-{e_mo:02d}-{e_day:02d}",
        people_found=found,
        people_referred=referred,
        people_being_taught=being_taught,
        multiple_lessons=funnel["multiple_lessons"],
        church_attendance=funnel["church_attendance"],
        baptism_goal_date_set=funnel["baptism_goal_date_set"],
        baptized=baptized,
    )


def parse_summary_pdf(path) -> MonthlySummary:
    """Read a Mission Finding Summary PDF and parse its single page.

    The month comes from the window *inside* the file, never the filename -
    the real exports carry typos ("Spetember 2024", "Febuary 2025") and mixed
    languages ("Abril 2026"), none of which matter as a result.

    ``pypdf`` is imported here rather than at module scope so this module can be
    imported (and ``parse_summary_text`` tested) without the dependency present.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise SummaryParseError(
            "pypdf is required to read a PDF; parse_summary_text() works "
            "without it if you extract the text yourself"
        ) from exc

    reader = PdfReader(str(path))
    if not reader.pages:
        raise SummaryParseError(f"{path}: no pages")
    return parse_summary_text(reader.pages[0].extract_text() or "")


def baptisms_rows(summaries) -> list[list]:
    """Shape parsed summaries into ``TABLEAU_BAPTISMS`` rows.

    That tab's contract, per ``get_baptisms_actual()``: columns ``zone`` /
    ``month`` / ``baptisms``, where the reader selects ``zone == "MISSION"``.
    These exports are mission-wide (every Tableau filter reads "Todo"), so every
    row is a MISSION row. Sorted by month so the tab reads chronologically.

    **Deduplicated by month**, because a folder of downloads realistically holds
    the same month twice - the live set had both ``Mission Finding Summary
    (August 2024).pdf`` and ``... (August 2024) (1).pdf``, which without this
    put two rows for 2024-08 into the tab. ``get_baptisms_actual`` reads
    ``match.iloc[-1]``, so a duplicate would not crash; it would just make which
    row wins depend on file ordering. Duplicates of the same month are expected
    to be byte-identical re-downloads; if two disagree, that is a signal the
    export changed and :class:`SummaryParseError` is raised rather than silently
    picking one.
    """
    by_month: dict[str, MonthlySummary] = {}
    for s in summaries:
        prior = by_month.get(s.month)
        if prior is not None and prior.baptized != s.baptized:
            raise SummaryParseError(
                f"two exports for {s.month} disagree: "
                f"{prior.baptized} vs {s.baptized} baptisms"
            )
        by_month[s.month] = s
    return [["MISSION", m, by_month[m].baptized] for m in sorted(by_month)]
