"""Which Key Indicators are LEVELS — pure, so the packet can ask without
Streamlit (decision 30's boundary).

"Amigos con Fecha Bautismal" is how many friends hold a baptismal date that
week, not a count of what happened in it (Zackary, 2026-10-17;
PLAN-2026-10-17-fechas-level.md decision L1). Its week's number moves by new
dates, minus baptisms, minus dates dropped, so it is never added across weeks,
and leadership's goal for it is a level to hold (L2). Conversos Recientes and
the sacrament counts are weekly Sunday counts and stay out (L1).

`metric_catalog` re-exports both names; this module exists so `app/reports`
does not import the catalogue (and Streamlit with it) to ask the question.
"""

LEVEL_METRICS: frozenset[str] = frozenset({"ki_baptismal_date_real"})


def is_level(key: str) -> bool:
    """True for a Key Indicator whose weekly figure is a level: one week's
    value stands for the period, and its goal is a level, not a total over
    weeks."""
    return key in LEVEL_METRICS
