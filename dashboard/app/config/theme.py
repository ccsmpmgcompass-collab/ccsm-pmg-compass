CHART_COLORS = [
    "#003087",  # Church navy
    "#0066CC",  # Medium blue
    "#4A90D9",  # Sky blue
    "#7AB3E0",  # Light blue
    "#B3D1F0",  # Pale blue
    "#F5A623",  # Amber accent
    "#D0021B",  # Alert red
]

# ── Categorical series palette (per-entity identity on the dark chart surface) ─
# Eight fixed hues, assigned IN ORDER and never cycled. The order is the
# colourblind-safety mechanism rather than a cosmetic choice — it was derived by
# maximising the minimum adjacent separation, so re-sequencing it silently
# weakens the palette. Blue leads and violet sits at 7 to stay close to the
# app's own blue/indigo accents (#0066CC, #6366f1); the remaining hues have to
# spread out to stay tellable apart, which is the whole job of this list.
#
# Measured against the real chart surface (#08080e) under simulated protanopia
# and deuteranopia (Machado 2009, severity 1.0), OKLab ΔE×100:
#   worst adjacent CVD ΔE 8.4 (target >= 8) · worst normal-vision ΔE 19.3
#   (floor >= 15) · all eight >= 3:1 contrast · all inside the dark lightness
#   band (L 0.48–0.67) and above the chroma floor.
# Re-measure with the dataviz skill's validate_palette.py before touching these.
#
# NOT CHART_COLORS, which stays put for the pages still using it: that list is a
# five-step blue RAMP and can't do identity work on this surface. Measured, it
# fails outright — its navy renders at 1.69:1 (near-invisible on near-black),
# and its two palest blues sit ΔE 11.0 apart, which a reader with full colour
# vision still can't separate. A ramp encodes magnitude, not which-one-is-this.
SERIES_COLORS = [
    "#3987e5",  # 1 blue
    "#008300",  # 2 green
    "#d55181",  # 3 magenta
    "#c98500",  # 4 yellow
    "#199e70",  # 5 aqua
    "#d95926",  # 6 orange
    "#9085e9",  # 7 violet
    "#e66767",  # 8 red
]

# Past eight series, hue alone cannot stay distinct — eight is the most that
# survives the separation checks, so a 9th colour would be a hue that only
# LOOKS distinct while measuring closer than a reader can resolve. Instead the
# 9th+ series reuses a hue with a different dash (lines) or fill pattern
# (bars), so no two series are ever identical even when a zone is large.
# Cycling colour alone is exactly the bug this replaced.
SERIES_DASHES = ["solid", "dash", "dot", "dashdot"]
SERIES_PATTERNS = ["", "/", ".", "x"]


def series_style(i: int) -> tuple[str, str, str]:
    """(colour, line dash, bar pattern) for the i-th series in a fixed order.

    Callers must pass a STABLE index for an entity — its position in a sorted
    list of the group's members, not its rank in the current sort. Colour has to
    follow the area, not its score, or re-sorting a chart repaints it and the
    bar/line colours stop agreeing.
    """
    n = len(SERIES_COLORS)
    tier = (i // n) % len(SERIES_DASHES)
    return SERIES_COLORS[i % n], SERIES_DASHES[tier], SERIES_PATTERNS[tier]


SEVERITY_COLORS = {
    "HIGH":   "#D32F2F",
    "MEDIUM": "#F57C00",
    "LOW":    "#388E3C",
}

MISSION_NAVY  = "#003087"
MISSION_LIGHT = "#F5F7FA"
TEXT_DARK     = "#1A1A1A"


# Shared neutral for any series beyond SERIES_COLORS' fixed length in the
# leader-weekly-email PNG charts (rendered via reportlab, not this app's
# usual Plotly components, so dash/pattern variation via series_style()
# isn't available there — see app/export/chart_png.py). Never cycle back
# through SERIES_COLORS for a 9th+ series.
CHART_OTHER_COLOR = "#9AA5B1"
