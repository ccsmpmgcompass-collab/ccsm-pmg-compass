"""
gemini_chat.py
─────────────────────────────────────────────────────────────────────────────
Chatbot backend for the PMG Compass Home page — the "Mission Assistant".

Design goal: answer ANY question a Mission President or AP could ask about the
mission, its data, or the app itself — and NEVER fabricate. Every fact the bot
states is grounded in one of the context blocks assembled here. If the data
needed isn't present, the grounding rules force the bot to say so instead of
guessing.

Public functions:
  load_kb_context()              — KNOWLEDGE_BASE tab → formatted str
  load_live_data_context()       — current-week mission/zone/area data → str
  load_supplemental_contexts()   — dict of all the other labeled data blocks
  ask_gemini(...)                — call Gemini 2.5 Flash, return answer str

Individual supplemental loaders (each returns "" on any failure, never raises):
  load_goals_context, load_org_context, load_daily_context,
  load_weekly_trends_context, load_compliance_context,
  load_notes_context, load_metrics_glossary
"""

import functools
import math
import time
from datetime import date, timedelta

import pandas as pd
from google import genai

from app.db.sheets_client import read_tab
from app.db.queries import (
    get_meta, get_mission_totals, get_zone_totals, get_live_snapshot,
    get_goals_df, get_areas_df, get_daily_log,
    get_weekly_ki_trends, get_weekly_ki_totals, get_alltime_compliance,
    get_notes, get_question_metrics, get_config_value,
)

def _key_metrics() -> list[tuple[str, str]]:
    """Leadership-relevant metrics for computed leaderboards / standouts, as
    (key in LIVE_SNAPSHOT/zone data, human label).

    Was a hardcoded list of four Utah Provo metrics, inherited with the fork,
    none of them a question on a CCSM form. Feeding those to the model is worse
    than feeding it nothing: it produces fluent, confident answers about metrics
    this mission has never collected, and a missionary has no way to tell that
    apart from a real one.

    Now the mission's own weekly Key Indicators, from QUESTIONS_CONFIG.

    (The old keys are deliberately not named here — tests/
    test_gemini_prompt_vocabulary.py scans this whole file for them, and an
    exemption for docstrings would be an exemption a future prompt string could
    hide behind.)
    """
    from app.config.metric_catalog import key_indicator_metrics
    return list(key_indicator_metrics().items())

_MAX_OUTPUT_TOKENS = 8192


class GeminiRateLimitError(Exception):
    pass


class GeminiError(Exception):
    pass


def _is_blank(val) -> bool:
    """Return True if val is empty, whitespace-only, NaN, or the string 'nan'."""
    try:
        if math.isnan(float(val)):
            return True
    except (TypeError, ValueError):
        pass
    return not str(val).strip()


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════

def load_kb_context() -> str:
    """Read KNOWLEDGE_BASE tab and return all entries as plain text.

    Returns empty string (never raises) if the tab is unavailable.
    """
    df = read_tab("KNOWLEDGE_BASE")
    if df.empty:
        return ""

    lines = []
    for _, row in df.iterrows():
        entry_id = str(row.get("ID", "")).strip()
        category = str(row.get("Category", "")).strip()
        question = str(row.get("Question", "")).strip()
        answer = str(row.get("Answer", "")).strip()
        if _is_blank(question) or _is_blank(answer):
            continue
        lines.append(f"[{entry_id}] ({category})\nQ: {question}\nA: {answer}")

    return "\n\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# CURRENT-WEEK LIVE DATA
# ══════════════════════════════════════════════════════════════════════════════

def load_live_data_context() -> str:
    """Load mission and zone data and format as readable text.

    Tries DASHBOARD_SUMMARY first (Agent5A), then falls back to LIVE_SNAPSHOT
    (Agent3) for per-area and zone-level data. Returns empty string on failure.
    """
    parts = []

    meta = get_meta()
    if meta:
        week_start = meta.get("current_week_start", "")
        week_end = meta.get("current_week_end", "")
        generated = meta.get("generated_at", "")
        if week_start and week_end:
            parts.append(f"Current week: {week_start} to {week_end}")
        if generated:
            parts.append(f"Data last refreshed: {generated}")

    # ── Mission + zone totals from DASHBOARD_SUMMARY (Agent5A) ────────────────
    mission_df = get_mission_totals()
    if not mission_df.empty:
        rows = []
        for _, row in mission_df.iterrows():
            metric = str(row.get("metric_name", row.get("metric_key", ""))).strip()
            val = row.get("val_7d", 0)
            goal = row.get("goal_weekly", 0)
            if metric:
                try:
                    goal_str = f" (goal: {int(float(goal))})" if goal and float(goal) > 0 else ""
                    rows.append(f"  {metric}: {int(float(val))}{goal_str}")
                except (ValueError, TypeError):
                    rows.append(f"  {metric}: {val}")
        if rows:
            parts.append("Mission totals (week-to-date):\n" + "\n".join(rows))

    zone_df = get_zone_totals()
    if not zone_df.empty and "zone" in zone_df.columns:
        zone_names = sorted(zone_df["zone"].dropna().unique().tolist())
        zone_lines = []
        for zone in zone_names:
            z = zone_df[zone_df["zone"] == zone]
            metrics = []
            for _, row in z.iterrows():
                metric = str(row.get("metric_name", row.get("metric_key", ""))).strip()
                try:
                    val = float(row.get("val_7d", 0))
                except (ValueError, TypeError):
                    val = 0.0
                if metric and val > 0:
                    metrics.append(f"{metric}: {int(val)}")
            zone_lines.append(f"  {zone}: " + (", ".join(metrics[:6]) if metrics else "no data"))
        if zone_lines:
            parts.append("Zone breakdown (week-to-date):\n" + "\n".join(zone_lines))

    # ── Per-area detail from LIVE_SNAPSHOT (Agent3) ───────────────────────────
    snap_df = get_live_snapshot()
    if not snap_df.empty:
        id_cols = {"Area", "Zone", "District", "Last_Updated"}
        # Only expose the 7-day window so Gemini doesn't confuse 14d/28d/transfer
        # figures with "this week" numbers. Fallback to all metric cols if no _7d
        # columns exist (e.g. fresh install where Agent3 hasn't run yet).
        all_metric_cols = [c for c in snap_df.columns if c not in id_cols]
        metric_cols = [c for c in all_metric_cols if c.endswith("_7d")] or all_metric_cols

        if not mission_df.empty is False and mission_df.empty:
            totals = snap_df[metric_cols].sum(numeric_only=True)
            total_lines = [f"  {col}: {int(v)}" for col, v in totals.items() if v > 0]
            if total_lines:
                parts.append("Mission totals (from snapshot):\n" + "\n".join(total_lines))

        if "Zone" in snap_df.columns and zone_df.empty:
            zone_snap = snap_df.groupby("Zone")[metric_cols].sum(numeric_only=True)
            zone_snap_lines = []
            for zone, row in zone_snap.iterrows():
                metrics = [f"{col}: {int(v)}" for col, v in row.items() if v > 0]
                zone_snap_lines.append(f"  {zone}: " + (", ".join(metrics[:6]) if metrics else "no data"))
            if zone_snap_lines:
                parts.append("Zone breakdown (from snapshot):\n" + "\n".join(sorted(zone_snap_lines)))

        area_lines = []
        for _, row in snap_df.iterrows():
            area = str(row.get("Area", "")).strip()
            zone = str(row.get("Zone", "")).strip()
            if not area:
                continue
            metrics = [f"{col}={int(float(row[col]))}" for col in metric_cols
                       if not _is_blank(row.get(col)) and float(row.get(col, 0)) > 0]
            area_lines.append(f"  {area} ({zone}): " + (", ".join(metrics) if metrics else "no submissions this week"))
        if area_lines:
            parts.append("Per-area data (current week):\n" + "\n".join(area_lines))

    return "\n\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# SUPPLEMENTAL DATA LOADERS
# Each returns "" on any failure so a missing tab never breaks the chat — the
# grounding rules then make the bot say it can't retrieve that data.
# ══════════════════════════════════════════════════════════════════════════════

def load_goals_context() -> str:
    """Per-area weekly goals from GOALS_CONFIG."""
    try:
        df = get_goals_df()
        if df.empty or "Area" not in df.columns:
            return ""
        metric_cols = [c for c in df.columns if c != "Area"]
        lines = []
        for _, row in df.iterrows():
            area = str(row.get("Area", "")).strip()
            if not area:
                continue
            goals = []
            for col in metric_cols:
                try:
                    v = float(row.get(col, 0))
                    if v > 0:
                        goals.append(f"{col}={int(v)}")
                except (ValueError, TypeError):
                    pass
            if goals:
                lines.append(f"  {area}: " + ", ".join(goals))
        return "\n".join(lines) if lines else ""
    except Exception:
        return ""


def load_org_context() -> str:
    """Area structure + leadership roles (+ companion names when on file) from
    MISSION_ORG.

    Companion-name columns are often blank in the sheet, but the area / zone /
    district / leadership structure is always useful — so structural rows are
    always included and names are appended only when present. This lets the bot
    answer "how many areas in zone X", "what district is Y in", and "which area
    holds the Zone Leaders" even when individual missionary names aren't recorded.
    """
    try:
        df = get_areas_df(active_only=True)
        if df.empty:
            return ""
        lines = []
        any_names = False
        for _, row in df.iterrows():
            area = str(row.get("Area_Name", row.get("Area", ""))).strip()
            zone = str(row.get("Zone", "")).strip()
            district = str(row.get("District", "")).strip()
            if not area or zone.upper() == "ALL":
                continue
            c1 = str(row.get("Companion1_Name", "")).strip()
            c2 = str(row.get("Companion2_Name", "")).strip()
            is_mp = str(row.get("Is_MP", "")).upper() == "TRUE"
            is_ap = str(row.get("Is_AP", "")).upper() == "TRUE"
            is_zl = str(row.get("Is_ZL", "")).upper() == "TRUE"
            is_stl = str(row.get("Is_STL", "")).upper() == "TRUE"
            is_dl = str(row.get("Is_DL", "")).upper() == "TRUE"
            if is_mp or is_ap:
                continue
            role = ""
            if is_zl:
                role = " [holds ZONE LEADER]"
            elif is_stl:
                role = " [holds SISTER TRAINING LEADER]"
            elif is_dl:
                role = " [holds DISTRICT LEADER]"
            companions = " + ".join(
                n for n in [c1, c2] if n and n.lower() not in ("nan", "")
            )
            loc = f"{zone} / {district}" if district and district.lower() != "nan" else zone
            if companions:
                any_names = True
                lines.append(f"  {area} ({loc}): {companions}{role}")
            else:
                lines.append(f"  {area} ({loc}):{role}")
        if not lines:
            return ""
        header = (
            f"{len(lines)} areas. Format is 'Area (Zone / District): companions [leadership]'."
        )
        if not any_names:
            header += (
                " NOTE: individual missionary names are NOT recorded in the system, "
                "so you can give the area, zone, district, and which area holds a "
                "leadership assignment, but you cannot name specific missionaries."
            )
        return header + "\n" + "\n".join(lines)
    except Exception:
        return ""


def load_daily_context() -> str:
    """Recent nightly-form activity (last 7 days) from DAILY_LOG."""
    try:
        df = get_daily_log(days=7)
        if df.empty:
            return ""

        today = date.today()
        parts = []

        date_counts = df.groupby("Date")["Area"].count().sort_index()
        if not date_counts.empty:
            count_lines = [f"  {d}: {n} area(s) submitted" for d, n in date_counts.items()]
            parts.append("Submission counts by day:\n" + "\n".join(count_lines))

        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        yest_df = df[df["Date"] == yesterday]
        if not yest_df.empty:
            metric_cols = [c for c in yest_df.columns if c not in ("Date", "Area", "Zone", "District")]
            area_lines = []
            for _, row in yest_df.sort_values("Area").iterrows():
                area = str(row.get("Area", "")).strip()
                if not area:
                    continue
                metrics = []
                for col in metric_cols:
                    try:
                        v = float(row.get(col, 0))
                        if v > 0:
                            metrics.append(f"{col}={int(v)}")
                    except (ValueError, TypeError):
                        pass
                area_lines.append(f"  {area}: " + (", ".join(metrics) if metrics else "submitted (all zeros)"))
            if area_lines:
                parts.append(f"Yesterday ({yesterday}) per-area submissions:\n" + "\n".join(area_lines))

        three_ago = (today - timedelta(days=3)).strftime("%Y-%m-%d")
        submitted_recently = set(df[df["Date"] >= three_ago]["Area"].dropna().unique())
        all_areas = set(df["Area"].dropna().unique())
        missing = sorted(all_areas - submitted_recently)
        if missing:
            parts.append(
                "Areas with NO submission in the last 3 days "
                "(among areas that appear in the log):\n"
                + "\n".join(f"  {a}" for a in missing)
            )

        return "\n\n".join(parts)
    except Exception:
        return ""


def _current_week_monday_str() -> str:
    """ISO date (YYYY-MM-DD) of this reporting week's Monday. Any week_end_date >=
    this is the in-progress week and must not be compared as a completed week."""
    today = date.today()
    return (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")


def _partial_tag(week_end: str, monday_str: str) -> str:
    """Suffix that warns the model not to read a partial week as a real decline."""
    if week_end and week_end >= monday_str:
        return " (PARTIAL — current week still in progress; lower numbers here are NOT a decline)"
    return ""


def load_weekly_trends_context() -> str:
    """Historical weekly trends: nightly-metric rollups + baptism-pipeline KIs.

    The most recent row is usually the in-progress week; it is tagged PARTIAL so
    the model never misreads an incomplete week as a performance drop.
    """
    try:
        parts = []
        monday = _current_week_monday_str()

        nightly = get_weekly_ki_trends(8)
        if not nightly.empty and "week_end_date" in nightly.columns:
            metric_cols = [c for c in nightly.columns if c != "week_end_date"]
            lines = []
            for _, row in nightly.iterrows():
                week = str(row.get("week_end_date", "")).strip()
                vals = []
                for col in metric_cols:
                    try:
                        v = float(row.get(col, 0))
                        if v != 0:
                            vals.append(f"{col}={int(v)}")
                    except (ValueError, TypeError):
                        pass
                lines.append(f"  week ending {week}: " + (", ".join(vals) if vals else "no data") + _partial_tag(week, monday))
            if lines:
                parts.append(
                    "Mission-wide weekly totals from the nightly form (last 8 weeks, oldest first):\n"
                    + "\n".join(lines)
                )

        ki = get_weekly_ki_totals(8)
        if not ki.empty and "week_end_date" in ki.columns:
            ki_cols = [c for c in ki.columns if c != "week_end_date"]
            lines = []
            for _, row in ki.iterrows():
                week = str(row.get("week_end_date", "")).strip()
                vals = []
                for col in ki_cols:
                    try:
                        v = float(row.get(col, 0))
                        vals.append(f"{col}={int(v)}")
                    except (ValueError, TypeError):
                        pass
                lines.append(f"  week ending {week}: " + ", ".join(vals) + _partial_tag(week, monday))
            if lines:
                # The glossary is built from QUESTIONS_CONFIG, not written out.
                # It used to read "pew=brought friend to church,
                # date_metric=baptismal dates set, gate=baptisms,
                # renew=reactivations, rc_total=recent converts" — Provo's
                # metrics, none of which CCSM collects. Handing a model a
                # glossary for data it will never see is how you get fluent,
                # confident answers about things that did not happen, and a
                # missionary cannot tell those from real ones.
                #
                # `_real` is what the companionship achieved; `_meta` is the
                # goal they set for themselves. The model is told so explicitly,
                # because summing or conflating them would report the mission as
                # having met targets it did not.
                from app.config.metric_catalog import metric_options
                _cat = metric_options(include_rates=False)
                _glossary = ", ".join(
                    f"{c}={_cat[c]}" for c in ki_cols if c in _cat
                )
                parts.append(
                    "Mission-wide weekly Key Indicators from the weekly form"
                    + (f" ({_glossary})" if _glossary else "")
                    + ". Keys ending _real are what the companionship ACHIEVED; "
                      "keys ending _meta are the GOAL they set for that week — "
                      "never add the two together. Last 8 weeks, oldest first:\n"
                    + "\n".join(lines)
                )

        return "\n\n".join(parts)
    except Exception:
        return ""


def load_compliance_context() -> str:
    """All-time per-area submission compliance since system start."""
    try:
        df = get_alltime_compliance()
        if df.empty:
            return ""
        df = df.sort_values("pct", ascending=False)
        lines = []
        for _, row in df.iterrows():
            area = str(row.get("area", "")).strip()
            if not area:
                continue
            zone = str(row.get("zone", "")).strip()
            sub = int(row.get("days_submitted", 0))
            poss = int(row.get("days_possible", 0))
            pct = int(row.get("pct", 0))
            last = str(row.get("last_date", "")).strip()
            last_str = f", last submitted {last}" if last else ", never submitted"
            lines.append(f"  {area} ({zone}): {sub}/{poss} days = {pct}%{last_str}")
        return (
            "Cumulative nightly-form submission rate per area since the system "
            "started (higher % = more consistent):\n" + "\n".join(lines)
        ) if lines else ""
    except Exception:
        return ""


def load_notes_context() -> str:
    """Open (unresolved) area notes that are visible to everyone."""
    try:
        df = get_notes(user_email=None, show_resolved=False)
        if df.empty:
            return ""
        if "visible_to" in df.columns:
            df = df[df["visible_to"].astype(str).str.lower().str.strip() == "all"]
        if df.empty:
            return ""
        lines = []
        for _, row in df.iterrows():
            content = str(row.get("content", "")).strip()
            if not content:
                continue
            area = str(row.get("area", "")).strip()
            zone = str(row.get("zone", "")).strip()
            tags = str(row.get("tags", "")).strip()
            follow = str(row.get("follow_up_date", "")).strip()
            created = str(row.get("created_at", "")).strip()
            scope = area or zone or "mission-wide"
            extras = []
            if tags and tags.lower() != "nan":
                extras.append(f"tags: {tags}")
            if follow and follow.lower() != "nan":
                extras.append(f"follow-up: {follow}")
            if created and created.lower() != "nan":
                extras.append(f"created: {created}")
            extra_str = f" ({'; '.join(extras)})" if extras else ""
            lines.append(f"  [{scope}] {content}{extra_str}")
        return "Open area notes:\n" + "\n".join(lines) if lines else ""
    except Exception:
        return ""


def load_metrics_glossary() -> str:
    """Metric-key → human meaning, from QUESTIONS_CONFIG."""
    try:
        metrics = get_question_metrics()
        if not metrics:
            return ""
        lines = []
        for key, name, ftype in metrics:
            form = ftype.lower() if ftype else "unknown"
            lines.append(f"  {key} = {name} ({form} form)")
        return (
            "Metric-key glossary (left side is the raw column key seen in the "
            "data above; suffixes _7d/_14d/_28d/_transfer mean rolling 7/14/28-day "
            "and transfer-to-date windows):\n" + "\n".join(lines)
        )
    except Exception:
        return ""


def load_analytics_context() -> str:
    """Pre-computed insight layer: zone leaderboards, per-area standouts, the
    baptism-pipeline funnel with conversion rates, and compliance extremes.

    Every number here is computed in Python from live data (exact, never the
    model's arithmetic). This is what turns the bot from a lookup tool into an
    analyst — it can rank, compare, and flag without re-deriving from raw tables.
    """
    try:
        parts = []

        # ── Zone leaderboards (last 7 days) ──────────────────────────────────
        zone_df = get_zone_totals()
        if not zone_df.empty and "metric_key" in zone_df.columns:
            for key, name in _key_metrics():
                sub = zone_df[zone_df["metric_key"] == key]
                if sub.empty:
                    continue
                ranked = sub.groupby("zone")["val_7d"].sum().sort_values(ascending=False)
                ranked = ranked[ranked > 0]
                if ranked.empty:
                    continue
                line = " > ".join(f"{z} {int(v)}" for z, v in ranked.items())
                parts.append(f"Zone ranking by {name} (last 7 days): {line}")

        # ── Per-area standouts (last 7 days) ─────────────────────────────────
        snap = get_live_snapshot()
        if not snap.empty:
            standout_blocks = []
            for key, name in _key_metrics():
                col = f"{key}_7d"
                if col not in snap.columns:
                    continue
                s = snap[["Area", "Zone", col]].copy()
                s = s[s[col] > 0].sort_values(col, ascending=False)
                if len(s) < 2:
                    continue
                top = s.head(5)
                bottom = s.tail(5).sort_values(col)
                top_line = ", ".join(f"{r['Area']} ({int(r[col])})" for _, r in top.iterrows())
                bot_line = ", ".join(f"{r['Area']} ({int(r[col])})" for _, r in bottom.iterrows())
                standout_blocks.append(
                    f"{name}: highest -> {top_line}; lowest (still active) -> {bot_line}"
                )
            if standout_blocks:
                parts.append("Per-area standouts (last 7 days):\n  " + "\n  ".join(standout_blocks))

        # ── Baptism-pipeline funnel + conversion rates ───────────────────────
        ki = get_weekly_ki_totals(8)
        tr = get_weekly_ki_trends(8)
        if not ki.empty and "week_end_date" in ki.columns:
            monday = _current_week_monday_str()
            ki_sorted = ki.sort_values("week_end_date")
            ki_pool = ki_sorted[ki_sorted["week_end_date"] < monday]  # completed weeks only
            if ki_pool.empty:
                ki_pool = ki_sorted  # fall back if no completed week yet
            # Built from the mission's OWN Key Indicators. This block used to
            # index ["pew","date_metric","gate","renew","rc_total"] directly —
            # Provo's columns — which raises KeyError against CCSM's frame, and
            # the bare `except Exception: return ""` at the end of this function
            # swallowed it, so the model silently received NO analytics context
            # at all and answered from the raw tables alone.
            from app.config.metric_catalog import key_indicator_metrics
            ki_labels = key_indicator_metrics()
            present = [k for k in ki_labels if k in ki_pool.columns]
            if present:
                active = ki_pool[ki_pool[present].sum(axis=1) > 0]
                row = (active.iloc[-1] if not active.empty else ki_pool.iloc[-1])
                wk = str(row["week_end_date"])

                def _n(key):
                    try:
                        return int(float(row.get(key, 0)))
                    except (TypeError, ValueError):
                        return 0

                funnel = [f"{ki_labels[k]} {_n(k)}" for k in present]

                # Conversion rates only between stages that genuinely feed one
                # another. These are per-window counts, not a strict funnel — a
                # later stage CAN exceed an earlier one, so a "rate" over 100%
                # is real data, not a bug. Only ratios the mission itself tracks
                # are shown, and only when the denominator is non-zero.
                convs = []
                _date, _bap = "ki_baptismal_date_real", "ki_baptized_confirmed_real"
                if _date in present and _bap in present and _n(_date):
                    convs.append(
                        f"{ki_labels[_date]} -> {ki_labels[_bap]}: "
                        f"{round(_n(_bap) / _n(_date) * 100)}%"
                    )
                block = (f"Key Indicators for the latest completed week (ending {wk}): "
                         + " | ".join(funnel))
                if convs:
                    block += "\n  Conversion rates: " + ", ".join(convs)
                parts.append(block)

        # ── Compliance extremes ──────────────────────────────────────────────
        comp = get_alltime_compliance()
        if not comp.empty and "pct" in comp.columns:
            comp = comp.sort_values("pct", ascending=False)
            best = comp.head(5)
            worst = comp[comp["pct"] < 100].tail(5).sort_values("pct")
            best_line = ", ".join(f"{r['area']} {int(r['pct'])}%" for _, r in best.iterrows())
            parts.append(f"Most consistent areas (all-time submission rate): {best_line}")
            if not worst.empty:
                worst_line = ", ".join(f"{r['area']} {int(r['pct'])}%" for _, r in worst.iterrows())
                parts.append(f"Least consistent areas needing attention: {worst_line}")

        return "\n\n".join(parts)
    except Exception:
        return ""


# Ordered registry of supplemental contexts: label -> loader. Insertion order is
# the order they appear in the prompt. Add new data sources here only.
_SUPPLEMENTAL_LOADERS = {
    "COMPUTED ANALYTICS (rankings, pipeline, standouts — exact, pre-calculated)": load_analytics_context,
    "PER-AREA WEEKLY GOALS": load_goals_context,
    "MISSIONARY ASSIGNMENTS & LEADERSHIP": load_org_context,
    "RECENT NIGHTLY ACTIVITY (last 7 days)": load_daily_context,
    "HISTORICAL WEEKLY TRENDS (last 8 weeks)": load_weekly_trends_context,
    "ALL-TIME SUBMISSION COMPLIANCE": load_compliance_context,
    "OPEN AREA NOTES": load_notes_context,
    "METRIC GLOSSARY": load_metrics_glossary,
}


def load_supplemental_contexts() -> dict:
    """Run every supplemental loader and return {label: content} in prompt order.

    Each loader already swallows its own errors and returns "" on failure, so
    this never raises — a dead tab just yields an empty block, which the prompt
    renders as 'unavailable' so the bot declines instead of inventing data.
    """
    return {label: loader() for label, loader in _SUPPLEMENTAL_LOADERS.items()}


# ══════════════════════════════════════════════════════════════════════════════
# STATIC APP / SYSTEM KNOWLEDGE
# ══════════════════════════════════════════════════════════════════════════════

_APP_KNOWLEDGE = (
    "APP PAGES (what each does and where to find things):\n"
    "- Home: the Mission Assistant chatbot (this conversation). Ask anything about mission data, procedures, performance, people, or how the app works. An 'App Guide' expander lists every page.\n"
    "- Dashboard: whole-mission executive snapshot — weekly KPIs vs goals, the mission Key Indicators, a ranked zone leaderboard, two 8-week trend charts, daily activity, effort breakdown, and submission compliance (nightly + weekly calendars, combined score, per-area detail heatmap). Sourced from DASHBOARD_SUMMARY (refreshed daily at noon by Agent5A). Mission level only — no per-area drill-down.\n"
    "- Goals: every area's progress against its weekly and transfer goals, color-coded (green=met, yellow=close, red=behind). Goals are edited inline here and stored in GOALS_CONFIG.\n"
    "- Breakdowns: one page with Zone / District / Area selectors — the deepest selection is what gets broken down. Zone or district: period comparisons across that group's areas, the Key Indicator pipeline, and per-area trends. Area: a compliance calendar (which nights they submitted), anomaly flags (metric drops vs a 4-week baseline), and that area's notes. (Replaced the former separate Zone Breakdown and Area Breakdown pages.)\n"
    "- Scores: three tabs. Scores — weekly composite scores per area across four dimensions (Effort, Skill, KI, Effectiveness), weighting configurable with an inline editor. Daily Activity — a day-by-day explorer of the nightly form across every metric, area, and date (from DAILY_LOG). Analyze — automatic anomaly detection (areas down >30% vs their 4-week baseline) and next-week projections via linear regression. (Merged into one page July 2026.)\n"
    "- Finding Funnel: the finding-to-baptism pipeline built from uploaded Tableau CSV exports, plus area rankings. Requires a manual Tableau upload.\n"
    "- Notes: area notes with tags, full-text search, and follow-up-date email reminders.\n"
    "- Maintenance: the back office — weekly maintenance to-do, data freshness + agent-run health, adding knowledge-base Q&As, agent configuration settings, form-question activation, test mode, and cache controls. (Absorbed the former Data Status page.)\n"
    "\n"
    "AGENTS (Google Apps Script automations that run on a schedule):\n"
    "- Agent1A (Mon ~9:45 PM): collects and analyses the past week of nightly form data, builds per-area coaching stats, then triggers Agent1B.\n"
    "- Agent1B: selects random coaching messages from the MESSAGE_BANK for each area, then triggers Agent1C.\n"
    "- Agent1C: sends personalised Monday coaching emails to missionaries, district leaders, zone leaders, APs, and the Mission President — including Gemini-generated narratives for leadership.\n"
    "- Agent3 (nightly ~9:30 PM): processes that night's nightly form submissions, updates DAILY_LOG and LIVE_SNAPSHOT rolling windows (7/14/28-day and transfer-to-date).\n"
    "- Agent5A (daily at noon): the main aggregator — writes DASHBOARD_SUMMARY (mission totals, zone totals, compliance counts, metadata). This is what the Dashboard reflects.\n"
    "- Agent6 (Friday PM, weekly): sends Friday encouragement emails.\n"
    "- Agent7 (nightly ~10:15 PM): generates the nightly report for the Mission President's wife.\n"
    "- AgentQA (email-triggered): answers questions emailed to ccsm.pmg.compass@gmail.com using the same Knowledge Base, and replies by email.\n"
    "- AgentReminder (weekly, Monday): emails compliance reminders to areas that missed the weekly Google Form.\n"
    "\n"
    "DATA FLOW:\n"
    "1. Missionaries fill the nightly or weekly Google Form -> the response lands in a RAW tab in the COMPASS_CCSM spreadsheet.\n"
    "2. The same night, Agent3 processes the nightly form -> DAILY_LOG and LIVE_SNAPSHOT update. On Mondays, Agent1A/1B/1C also run to send the weekly coaching emails.\n"
    "3. The weekly form flows WEEKLY_FORM_RAW -> WEEKLY_KI, aggregated by Agent5A at noon.\n"
    "4. Agent5A runs daily at noon -> writes DASHBOARD_SUMMARY -> the Dashboard shows the new totals.\n"
    "5. The app reads everything live from Google Sheets through a service account; there is no separate database.\n"
    "\n"
    "FORMS & CADENCE:\n"
    "- Nightly form: submitted each evening; due before the 9:30 PM mission-local cutoff to count toward that day's compliance.\n"
    "- Weekly form: submitted Sunday night; carries the seven Key Indicators, each as a Real (achieved) and a Meta (goal) value.\n"
    "\n"
    # The metric glossary is NOT written here. It used to list Provo's — NM
    # Lessons, NM Attempted, Pew, Date, Gate, Renew, RC, plus a "baptism
    # pipeline order" over metrics CCSM does not collect. Handing a model
    # definitions for data it will never see produces fluent, confident answers
    # about things that never happened, which a missionary cannot distinguish
    # from real ones. load_metrics_glossary() supplies the real list from
    # QUESTIONS_CONFIG at prompt-assembly time instead.
    "KEY METRICS: see the METRICS GLOSSARY data section, which is generated from "
    "this mission's own form configuration. Do not describe or reason about any "
    "metric that is not listed there, and never infer a metric's meaning from "
    "its name alone.\n"
    "Metric keys ending _real are what a companionship ACHIEVED that week; keys "
    "ending _meta are the GOAL they set for themselves. Never add the two "
    "together, and never report a _meta value as an accomplishment.\n"
    "\n"
    "MISSION STRUCTURE: organized into zones, subdivided into districts and "
    "areas (each area is a companionship). Hierarchy is Mission -> Zone -> "
    "District -> Area. Leadership roles: Mission President (MP), Assistant to the "
    "President (AP), Zone Leader (ZL), Sister Training Leader (STL), District "
    "Leader (DL). For the exact current list and count of zones and areas, use the "
    "MISSIONARY ASSIGNMENTS data section — do not state a zone or area count "
    "from memory."
)


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════

_SYSTEM_HEADER_TEMPLATE = """\
You are the Mission Assistant for the Mission President and Assistant Presidents \
(APs) of the {mission} of The Church of Jesus Christ of Latter-day \
Saints. You are their single smartest source of truth about this mission and \
this app.

WHO YOU SERVE:
Senior leaders making decisions about missionary training, goal-setting, area \
assignments, and mission culture. They need accurate, specific, actionable \
answers — never generic filler.

═══════════════════════════════════════════════════════════════════════════════
ABSOLUTE GROUNDING RULES — THESE OVERRIDE EVERYTHING ELSE:
1. Every fact, number, name, goal, date, or status you state MUST come directly \
from the DATA and KNOWLEDGE sections below, or the APP & SYSTEM KNOWLEDGE block. \
You have NO other source of truth.
2. NEVER invent, estimate, guess, approximate, round-to-make-it-look-real, or \
"fill in" any number, name, goal, date, or fact. Inventing data is the single \
worst thing you can do.
3. If the specific data needed to answer is NOT present below, say so plainly — \
e.g. "I don't have that data available right now" — and, when useful, point to \
the page or person who would have it. Do NOT substitute an estimate.
4. If a data section is marked "(currently unavailable)", tell the user you \
can't retrieve that data right now rather than answering from memory or another \
section.
5. Arithmetic is allowed ONLY on numbers that are explicitly present (summing \
zones, computing percent-of-goal, comparing two listed weeks). Never compute on \
numbers you don't actually see.
6. You MAY interpret, rank, compare, and give an assessment — but clearly base \
every interpretation on the listed data. Distinguish "the data shows X" from \
"my read is Y".
7. If a question is outside this mission and app entirely, say it's outside \
your scope.

CRITICAL LANGUAGE RULE: NEVER use the word "investigator(s)". Always say \
"friend(s)" for people being taught.

WHERE TO LOOK:
- App / "how do I" / "when does X run" -> APP & SYSTEM KNOWLEDGE.
- Policy / definitions / counting rules -> synthesize across ALL relevant \
Knowledge Base entries, not just the first match.
- Rankings, "who's best/worst", pipeline, conversion rates, standouts -> \
COMPUTED ANALYTICS (already calculated for you — use it, don't re-derive).
- Current numbers -> CURRENT MISSION DATA. Trends / "over time" / "vs last week" \
-> HISTORICAL WEEKLY TRENDS. Key Indicators -> the \
weekly-form KI lines and the pipeline block.
- Per-area goals -> PER-AREA WEEKLY GOALS. Who serves where / leadership -> \
MISSIONARY ASSIGNMENTS. Recent submissions -> RECENT NIGHTLY ACTIVITY. Overall \
consistency -> ALL-TIME SUBMISSION COMPLIANCE. Operational context -> OPEN AREA \
NOTES. Cryptic column keys -> METRIC GLOSSARY.

ANSWER LIKE A SHARP CHIEF OF STAFF (this is what makes leaders trust you):
- LEAD WITH THE ANSWER. First sentence is the bottom line, not preamble.
- Bold the key numbers and names with **markdown** so a busy leader can skim.
- Make every number MEAN something: pair it with a rank, a comparison, a trend, \
or a share of the whole ("**528** lessons with friends — led by **that zone \
(71)**, up sharply from last week"). A number with no context is a missed \
opportunity. Use metric and zone names taken from the data sections you were \
given, never from this example: the example's shape is what matters, and \
inventing a plausible-sounding zone or metric is the one thing you must not do.
- For BROAD or STRATEGIC questions ("give me a briefing", "what should I focus \
on", "what's concerning", "how are we doing") deliver a tight executive briefing \
with short bold headers, e.g.:
    **Bottom line:** one-sentence verdict.
    **What's strong:** the 1-3 brightest spots, with numbers.
    **Needs attention:** the 1-3 real concerns (silent areas, drops, laggards).
    **Where I'd focus:** one concrete, data-backed recommendation.
  Keep the whole thing skimmable — leaders read it in 30 seconds.
- Be proactive: if the data shows something important and clearly relevant to \
the question, surface it even if not explicitly asked — but never pad, and never \
invent to fill a section. If a briefing section has no real data, say "nothing \
notable" rather than fabricating.
- Be thorough for complex questions, crisp for simple ones. Quality over length.
"""

_SECTION_TEMPLATE = "\n═══ {label} ═══\n{content}\n"


def _render_section(label: str, content: str) -> str:
    body = content.strip() if content and content.strip() else "(currently unavailable — tell the user you cannot retrieve this data right now)"
    return _SECTION_TEMPLATE.format(label=label, content=body)


def _build_prompt(
    question: str,
    history: list,
    kb_context: str,
    live_context: str,
    extra_contexts: dict = None,
) -> str:
    kb_count = len([l for l in kb_context.splitlines() if l.startswith("[kb-")]) if kb_context else 0

    mission = get_config_value("MISSION_NAME", "Mission")
    sections = [_SYSTEM_HEADER_TEMPLATE.format(mission=mission)]
    sections.append(_render_section("APP & SYSTEM KNOWLEDGE", _APP_KNOWLEDGE))
    sections.append(_render_section(
        f"KNOWLEDGE BASE ({kb_count} entries) — policies, definitions, counting rules",
        kb_context,
    ))
    sections.append(_render_section(
        "CURRENT MISSION DATA (this week; refreshed daily at noon)",
        live_context,
    ))
    for label, content in (extra_contexts or {}).items():
        sections.append(_render_section(label, content))

    system = "".join(sections)

    history_text = ""
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n\n"

    if history_text:
        return (
            f"{system}\n═══ CONVERSATION SO FAR ═══\n{history_text}"
            f"User's current question: {question}\n\nAnswer (grounded strictly in the data above):"
        )
    return f"{system}\nUser's question: {question}\n\nAnswer (grounded strictly in the data above):"


@functools.lru_cache(maxsize=1)
def _get_genai_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def ask_gemini(
    question: str,
    history: list,
    kb_context: str,
    live_context: str,
    api_key: str,
    extra_contexts: dict = None,
) -> str:
    """Call Gemini 2.5 Flash and return the answer string.

    history: prior messages as [{"role": "user"|"assistant", "content": str}]
    extra_contexts: {label: content} of supplemental data blocks (goals, org,
        daily, trends, compliance, notes, glossary). Order is preserved.
    Raises GeminiRateLimitError on 429, GeminiError on other failures.
    """
    client = _get_genai_client(api_key)
    prompt = _build_prompt(question, history, kb_context, live_context, extra_contexts)

    last_exc = None
    for attempt in range(3):  # one call + up to 2 retries on transient overload
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "max_output_tokens": _MAX_OUTPUT_TOKENS,
                    "thinking_config": {"thinking_budget": 16000},
                },
            )
            return response.text
        except Exception as e:
            last_exc = e
            err = str(e).lower()
            if "429" in err or "resource_exhausted" in err or "quota" in err:
                raise GeminiRateLimitError(str(e)) from e
            # 503 / overloaded / unavailable are transient — back off and retry
            if attempt < 2 and ("503" in err or "unavailable" in err or "overloaded" in err):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise GeminiError(str(e)) from e
    raise GeminiError(str(last_exc))
