"""
transfer_roster_transform.py — Transforms a raw IMOS "Organization Roster"
export into TRANSFER_IMPORT rows.

Ported from Utah Provo's app/ingestion/transfer_roster_transform.py.
ZONE_NAME_MAP starts EMPTY — Provo's export needed one because its zone names
carry a parenthetical code ("Kings Peak (KP)") that doesn't match MISSION_ORG's
plain-text zone names. CCSM's MISSION_ORG zones (Angol, Arauco, Camilo, Los
Angeles Norte, Los Angeles Sur, San Pedro, Temuco Cautín, Temuco Ñielol,
Victoria, Villarrica) have no such code, so there's no known mapping needed
yet — verify against a real IMOS download (Task 8) before relying on this,
and add entries here if the export's spelling doesn't match.
"""

from pathlib import Path

import pandas as pd

from app.utils.logger import get_logger

_logger = get_logger("ingestion.transfer_roster_transform")

# Column names as they appear in the raw "Current Organization" Excel export —
# UNVERIFIED for CCSM (Provo's own file carries the same caveat: these are
# best-known guesses from Provo's real 2026-07-01 export; CCSM's export
# format is assumed identical since it's the same IMOS portal, but this has
# not yet been confirmed against a real CCSM download).
RAW_HEADER_ROW = 2
RAW_COL_AREA = "Area"
RAW_COL_ZONE = "Zone"
RAW_COL_DISTRICT = "District"
RAW_COL_AREA_EMAIL = "Area Email"
RAW_COL_STATUS = "Status"
RAW_COL_POSITION = "Position"
RAW_COL_NAME = "Name"

_STATUS_IN_FIELD = "In Field"

_CALLING_MAP = {
    "MP": "MP",
    "AP": "AP",
    "DL": "DL",
    "DT": "DL",
    "STL1": "STL", "STL2": "STL", "STLT": "STL",
    "ZL1": "ZL", "ZL2": "ZL",
}
_CALLING_PRIORITY = ["MP", "AP", "DL", "STL", "ZL"]

# Empty until a real CCSM IMOS export shows a zone-name mismatch — see the
# module docstring.
ZONE_NAME_MAP: dict[str, str] = {}

# Starting guess, carried over from Provo's own confirmed set — verify against
# a real CCSM export and adjust if CCSM's mission office/senior-couple rows
# use different Zone/District text.
_NON_AREA_DISTRICTS = {"office", "other districts", "mp senior"}


def _normalize_zone(zone) -> str:
    return ZONE_NAME_MAP.get(str(zone).strip().lower(), str(zone).strip())


def _is_non_area_row(zone, district) -> bool:
    z = str(zone).strip().lower()
    d = str(district).strip().lower()
    return z.startswith("sr ") or d in _NON_AREA_DISTRICTS or z.endswith(" sm")


def _format_name(raw: str) -> str:
    """First Name + Last Name only — drops middle names, handles 'Last, First'
    order. CCSM's MISSION_ORG already stores companion names in "Last, First
    Middle" form (confirmed live, e.g. "Rees, Nicolas Clay") — this function's
    comma-handling branch is what normalizes that into "First Last" for the
    roster import, same as it does for Provo."""
    raw = str(raw).strip()
    if not raw:
        return ""
    if "," in raw:
        last, _, rest = raw.partition(",")
        rest_parts = rest.strip().split()
        first = rest_parts[0] if rest_parts else ""
        return f"{first} {last.strip()}".strip()
    parts = raw.split()
    if len(parts) <= 2:
        return raw
    return f"{parts[0]} {parts[-1]}"


def _pick_companions(names: list, positions: list) -> tuple:
    """Companion1 = the Position=='SC' missionary (or first in file order if
    no SC present); Companion2/3/4 = everyone else, one name per slot. CCSM's
    MISSION_ORG only has 2 companion slots, but a companionship of 3+ is
    still possible in the field (e.g. a trio) — keep the 4-slot ceiling so a
    real trio/quad doesn't raise, even though only slots 1-2 currently have
    anywhere to land in MISSION_ORG (apply_transfer's headers-driven merge
    just drops the extra slots harmlessly — see transfer_engine.py).

    A companionship of 5+ (seen live 2026-08-06 — a temporary training/
    zone-leader overlap in one area) logs a warning and drops whoever's left
    over past comp1-4, rather than raising: failing the ENTIRE roster pull
    over one outlier area is worse than losing a name that had nowhere to
    land in MISSION_ORG anyway. The SC (if any) is found before truncating,
    so a senior companion listed late in the raw file order is never the
    one dropped."""
    if len(names) == 1:
        return names[0], "", "", ""
    sc_idx = next((i for i, p in enumerate(positions) if p == "SC"), None)
    if sc_idx is not None:
        comp1 = names[sc_idx]
        rest = [n for i, n in enumerate(names) if i != sc_idx]
    else:
        comp1 = names[0]
        rest = names[1:]
    if len(rest) > 3:
        _logger.warning(
            "Companionship has %d missionaries, more than the 4-person "
            "ceiling — keeping %s plus %s, dropping %s",
            len(names), comp1, rest[:3], rest[3:],
        )
        rest = rest[:3]
    rest_padded = rest + [""] * (3 - len(rest))
    return comp1, rest_padded[0], rest_padded[1], rest_padded[2]


def _pick_calling(positions: list) -> str:
    found = {_CALLING_MAP[p] for p in positions if p in _CALLING_MAP}
    for rank in _CALLING_PRIORITY:
        if rank in found:
            return rank
    return ""


def build_transfer_rows(df: pd.DataFrame) -> list:
    """Raw roster DataFrame -> TRANSFER_IMPORT rows.

    Raises ValueError if any 'In Field' missionary is dropped during
    transform (e.g. a blank Area causes pandas groupby to silently exclude
    that row from every group).
    """
    df = df.dropna(how="all")
    df = df[df[RAW_COL_NAME].notna()]

    if RAW_COL_STATUS in df.columns:
        in_field = df[df[RAW_COL_STATUS].astype(str).str.strip() == _STATUS_IN_FIELD]
    else:
        in_field = df

    if len(in_field) > 0:
        non_area_mask = in_field.apply(
            lambda r: _is_non_area_row(r[RAW_COL_ZONE], r[RAW_COL_DISTRICT]), axis=1
        )
        in_field = in_field[~non_area_mask]

    total_missionaries = len(in_field)

    rows = []
    consumed = 0
    for area, group in in_field.groupby(RAW_COL_AREA):
        names = [_format_name(n) for n in group[RAW_COL_NAME]]
        positions = [str(p).strip().strip("()") for p in group[RAW_COL_POSITION]]
        comp1, comp2, comp3, comp4 = _pick_companions(names, positions)
        calling = _pick_calling(positions)
        consumed += len(names)
        area_email = group[RAW_COL_AREA_EMAIL].iloc[0] if RAW_COL_AREA_EMAIL in group.columns else ""
        rows.append({
            "Area": area,
            "Zone": _normalize_zone(group[RAW_COL_ZONE].iloc[0]),
            "District": group[RAW_COL_DISTRICT].iloc[0],
            "Companion1_Name": comp1,
            "Companion2_Name": comp2,
            "Companion3_Name": comp3,
            "Companion4_Name": comp4,
            "Calling": calling,
            "Area_Email": area_email,
        })

    if consumed != total_missionaries:
        raise ValueError(
            f"Transform dropped missionaries: {total_missionaries} 'In Field' "
            f"missionaries in the source file but only {consumed} were placed "
            f"into output rows (likely a blank Area value on one or more rows)."
        )

    _logger.info(f"Transformed {total_missionaries} missionaries into {len(rows)} area rows")
    return rows


def load_roster_excel(path) -> pd.DataFrame:
    return pd.read_excel(Path(path), header=RAW_HEADER_ROW)


def transform_roster(path) -> list:
    df = load_roster_excel(path)
    return build_transfer_rows(df)
