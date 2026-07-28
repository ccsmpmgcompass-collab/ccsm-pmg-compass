"""
app/config/metrics.py
────────────────────────────────────────────────────────────────────────────────
Shared tracked-metric catalogue for the Breakdowns dashboard (training-mode
sections) and the Zone/District Leader weekly email — kept in one place so
the two surfaces can't silently drift on which metrics are tracked.
"""

# Count metrics — can be summed per area for comparison tables and bar charts.
# Keys must match column names in WEEKLY_KI / WEEKLY_BREAKDOWNS exactly.
METRIC_OPTIONS = {
    # Finding
    "new_found":              "New People Being Taught (NEW)",
    "nm_contacted":           "NM Contacted",
    "nm_meaningful":          "Meaningful Contacts",
    "nm_doors":               "NM Attempted",
    "nm_texts":               "NM Texts Sent",
    "online_referrals":       "Online Referrals",
    "referrals_today":        "Member Referrals",
    "lsi_given":              "LSI Given",
    "lsi_followups":          "LSI Follow-Ups",
    # Teaching
    "nm_lessons":             "NM Lessons",
    "member_lessons":         "Lessons With a Member Participating (MATE)",
    "rc_lessons":             "RC Lessons",
    "la_lessons":             "Less Active Lessons",
    # Weekly KI (from Sunday form)
    "pew":                    "People at Sacrament Meeting (PEW)",
    "date_metric":            "Baptismal Date (DATE)",
    "gate":                   "Baptized & Confirmed (GATE)",
    "renew":                  "New Members at Sacrament Meeting (RENEW)",
    "rc_total":               "RC Could Attend",
    # Attempt breakdown
    "la_Attempt":             "Less Active Attempted",
    "fellowshipper_Attempt":  "Fellowshipper Attempted",
    "aux_Attempt":            "Aux/Coord Attempted",
    "info_Attempt":           "Informational Attempted",
    "locos_Attempt":          "LOCOS Attempted",
    # Rates (display only — not summed in comparison table)
    "contact_rate":           "Contact to Friend",
    "mc_rate":                "Member-Present Rate",
    "door_lesson_rate":       "Door-to-Lesson Rate",
    "close_rate":             "Close Rate",
    "nm_knocked_rate":        "NM Attempt Rate",
    "effort_score":           "Effort Score",
}

# Rate/score metrics should not be summed across areas — averaged instead.
RATE_METRICS = {
    "contact_rate", "mc_rate", "door_lesson_rate",
    "close_rate", "nm_knocked_rate", "effort_score",
}

WF_KEYS = {"pew", "date_metric", "gate", "renew", "rc_total"}
DAILY_META = {"Date", "Area", "Zone", "District"}

# Score dimensions shown in the leader training view's Scores-by-area section —
# column order matches get_scores_by_area()'s return frame.
SCORE_LABELS = {
    "Effort_Score":        "Effort",
    "Skill_Score":          "Skill",
    "KI_Score":             "KI",
    "Effectiveness_Score":  "Effectiveness",
}
