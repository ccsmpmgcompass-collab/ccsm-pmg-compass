"""Who a report is about: the mission, a zone, a district or an area.

**MISSION_ORG is the only authority.** Membership is never read off a data
row's own Zone/District column — those record where an area was when the row
was written, so an area that has since transferred would keep appearing under
its old zone. This is the same rule `breakdowns_engine._scope_to_areas` and the
old Informes page already documented; it lives here now so the model, the
screen and the packet all get it from one place.

Every function in this module is pure: a roster frame in, dataclasses out. No
Streamlit, no sheet reads, no I/O. `load_roster()` is the one impure helper and
it does nothing but call `queries.get_submitting_areas()`, which already drops
the leadership tracking rows (Zone Leader - …, District Leader - …) that would
otherwise be counted as teaching areas.

Measured live 2026-09-21: 45 active teaching areas, 4 zones, 13 districts, no
blank Zone or District among them.

See PLAN-2026-09-21-informes.md §2 and §4 step R1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

MISSION = "mission"
ZONE = "zone"
DISTRICT = "district"
AREA = "area"

#: Coarse to fine. A level's children are the next entry along.
LEVELS = (MISSION, ZONE, DISTRICT, AREA)

#: MISSION_ORG carries Companion1/Companion2 today; 3 and 4 are read anyway so
#: a trio or a quad does not silently lose a missionary off the area page
#: (decision 27 — the companionship IS the area). Same column list as
#: `components/scope_selector._COMPANION_COLS`, which cannot be imported here:
#: that module pulls in Streamlit, and this one must stay importable by tests,
#: by `packet.py`, and by anything else with no browser attached.
COMPANION_COLS = ("Companion1_Name", "Companion2_Name",
                  "Companion3_Name", "Companion4_Name")

#: Fallback when AGENT_CONFIG has no MISSION_NAME. Callers that can reach the
#: sheet pass the real one in.
DEFAULT_MISSION_NAME = "La misión"


@dataclass(frozen=True)
class Scope:
    """One unit of the mission, and every roster area inside it.

    ``areas`` is the membership set every figure in the report is computed
    over — including areas that reported nothing, so an absent area counts
    against compliance instead of vanishing from the denominator.

    ``key`` is a stable identifier for links and for packet page anchors.
    Districts carry their zone in the key because nothing guarantees district
    names are unique across zones; they happen to be in CCSM today (13
    distinct names) and that is not a fact worth depending on.
    """

    level: str
    name: str
    areas: tuple[str, ...]
    zone: str | None = None
    district: str | None = None
    companions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        if self.level == MISSION:
            return MISSION
        if self.level == DISTRICT:
            return f"{DISTRICT}:{self.zone or ''}/{self.name}"
        return f"{self.level}:{self.name}"

    @property
    def area_count(self) -> int:
        return len(self.areas)

    @property
    def child_level(self) -> str | None:
        """The level below this one — what a "ranked children" table lists.
        None at area level, which has no children (decision 27)."""
        i = LEVELS.index(self.level)
        return LEVELS[i + 1] if i + 1 < len(LEVELS) else None

    @property
    def trail(self) -> tuple[str, ...]:
        """The unit's ancestors below the mission, coarsest first — the
        packet's running head. The mission's own name is not repeated, since
        it heads every page.
        """
        out = []
        if self.zone and self.level != ZONE:
            out.append(self.zone)
        if self.district and self.level != DISTRICT:
            out.append(self.district)
        return tuple(out)


# ── Reading the roster ────────────────────────────────────────────────────────

def load_roster() -> pd.DataFrame:
    """Active teaching areas from MISSION_ORG, leadership rows already dropped.

    The single impure function here. Everything below takes the frame it
    returns, so a test can hand in four rows and never touch a sheet.
    """
    from app.db.queries import get_submitting_areas
    return get_submitting_areas()


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Area_Name / Zone / District as stripped strings, nameless rows dropped.

    SCORES, DAILY_LOG and WEEKLY_KI all carry names with stray whitespace, so
    the roster is stripped once here and every membership test downstream
    compares like with like.
    """
    if df is None or df.empty or "Area_Name" not in df.columns:
        return pd.DataFrame(columns=["Area_Name", "Zone", "District"])
    out = df.copy()
    for col in ("Area_Name", "Zone", "District"):
        out[col] = (out[col].astype(str).str.strip()
                    if col in out.columns else "")
    return out[out["Area_Name"] != ""]


def companion_names(row) -> tuple[str, ...]:
    """The missionaries serving an area, in roster order, blanks skipped."""
    names = [str(row.get(c, "") or "").strip() for c in COMPANION_COLS]
    return tuple(n for n in names if n)


# ── Building scopes ───────────────────────────────────────────────────────────
#
# Names sort with plain `sorted()`, which is what the scope selectors already
# do — so the packet's zone order and the dropdown's zone order match. It puts
# "Temuco Ñielol" in the same place either way here, the Ñ not being the first
# letter.

def mission_scope(df: pd.DataFrame, name: str = DEFAULT_MISSION_NAME) -> Scope:
    roster = _clean(df)
    return Scope(level=MISSION, name=name,
                 areas=tuple(sorted(roster["Area_Name"].unique())))


def zone_scopes(df: pd.DataFrame) -> list[Scope]:
    roster = _clean(df)
    out = []
    for zone in sorted(z for z in roster["Zone"].unique() if z):
        rows = roster[roster["Zone"] == zone]
        out.append(Scope(level=ZONE, name=zone, zone=zone,
                         areas=tuple(sorted(rows["Area_Name"].unique()))))
    return out


def district_scopes(df: pd.DataFrame, zone: str | None = None) -> list[Scope]:
    """Districts, grouped by (zone, district) — see `Scope.key`."""
    roster = _clean(df)
    if zone:
        roster = roster[roster["Zone"] == zone]
    pairs = sorted({(z, d) for z, d in
                    zip(roster["Zone"], roster["District"]) if d})
    out = []
    for z, d in pairs:
        rows = roster[(roster["Zone"] == z) & (roster["District"] == d)]
        out.append(Scope(level=DISTRICT, name=d, zone=z, district=d,
                         areas=tuple(sorted(rows["Area_Name"].unique()))))
    return out


def area_scopes(df: pd.DataFrame, zone: str | None = None,
                district: str | None = None) -> list[Scope]:
    roster = _clean(df)
    if zone:
        roster = roster[roster["Zone"] == zone]
    if district:
        roster = roster[roster["District"] == district]
    out = []
    for _, row in roster.sort_values("Area_Name").iterrows():
        out.append(Scope(level=AREA, name=row["Area_Name"],
                         zone=row["Zone"] or None,
                         district=row["District"] or None,
                         areas=(row["Area_Name"],),
                         companions=companion_names(row)))
    return out


def resolve(df: pd.DataFrame, level: str | None, *, zone: str | None = None,
            district: str | None = None, area: str | None = None,
            mission_name: str = DEFAULT_MISSION_NAME) -> Scope | None:
    """The scope a page's selectors point at, or None if it is not on the roster.

    ``level`` is what `render_scope_selectors` returns as its fourth value —
    None for the whole mission. The caller translates the selectors' ``ANY``
    sentinel to None before calling; this module knows nothing about it.

    None, rather than a mission-wide scope, when the named unit is not on the
    roster: a zone that has left MISSION_ORG should say so, not quietly report
    the whole mission's numbers under its name.
    """
    if level in (None, "", MISSION):
        return mission_scope(df, mission_name)
    if level == ZONE:
        return next((s for s in zone_scopes(df) if s.name == zone), None)
    if level == DISTRICT:
        found = [s for s in district_scopes(df) if s.name == district]
        if zone:
            found = [s for s in found if s.zone == zone]
        return found[0] if found else None
    if level == AREA:
        return next((s for s in area_scopes(df) if s.name == area), None)
    return None


def children(df: pd.DataFrame, scope: Scope) -> list[Scope]:
    """The units one level down, ranked later by the model (decision 14)."""
    if scope.level == MISSION:
        return zone_scopes(df)
    if scope.level == ZONE:
        return district_scopes(df, zone=scope.name)
    if scope.level == DISTRICT:
        return area_scopes(df, zone=scope.zone, district=scope.name)
    return []


def parent(df: pd.DataFrame, scope: Scope,
           mission_name: str = DEFAULT_MISSION_NAME) -> Scope | None:
    """The unit one level up — an area's district, a district's zone, a zone's
    mission. None above the mission."""
    if scope.level == AREA and scope.district:
        return resolve(df, DISTRICT, zone=scope.zone, district=scope.district)
    if scope.level == DISTRICT:
        return resolve(df, ZONE, zone=scope.zone)
    if scope.level == ZONE:
        return mission_scope(df, mission_name)
    return None


def walk(df: pd.DataFrame, mission_name: str = DEFAULT_MISSION_NAME) -> list[Scope]:
    """Every scope the packet prints, in packet order: the mission, then all
    zones, then all districts, then all areas (PLAN §3.2).

    Level-major rather than depth-first, because that is how the packet is
    handed out — the zone pages go to zone leaders as a block, the district
    pages to district leaders as a block. 1 + 4 + 13 + 45 = 63 scopes for CCSM
    today.
    """
    return ([mission_scope(df, mission_name)] + zone_scopes(df)
            + district_scopes(df) + area_scopes(df))
