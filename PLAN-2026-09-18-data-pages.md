# PMG Compass — Data Pages Redesign Plan

**Written 2026-09-18.** Panel, Desgloses and Embudo de Búsqueda, rebuilt to a
professional standard for the Mission President and Assistants. Paired with the
audit artifact (findings X1–X7, P1–P7, D1–D7, E1–E6, mockups):
https://claude.ai/artifact/8q6QCBMVKwrUELty6Hspn7

Convention as before: audit first, then this numbered plan, one commit per
step, every step verified in the running app before its commit, the suite run
against its baseline before every push. A push touching `app/` needs a Reboot
of the deployed app (`dashboard/DEPLOYING.md`).

---

## §1 — Decisions (Zackary, 2026-09-18)

Recorded here so no step below re-opens them.

| # | Decision | Consequence |
|---|---|---|
| 1 | **Laptops are the primary device**; phones must still be readable. | Design target 1400px; every component must also wrap cleanly at 375px. Verified at both widths before each commit. |
| 2 | The two phone screenshots he sent are the Church's official app, **context only**. | Not a reference to copy. One thing IS borrowed from it — see decision 6. |
| 3 | **The Panel opens on the seven Key Indicators**; baptisms vs the 527 annual goal is the second block. | §4 Step C1. |
| 4 | **Cuts as recommended**: the "Lecciones por día" chart, the combined-compliance box and the rate-arithmetic table go; the effort section becomes an expander under Informes; the two 8-week spaghetti charts become small multiples. | §4 Steps C4, C5. |
| 5 | **A tapped Key Indicator opens "Por semana, este cambio"** — weekly bars vs goal, with the same weeks of the previous cambio as ghost bars ON by default. Tabs: Por cambio · Por área · Tabla. | §3 Step B2. |
| 6 | **The goal bar on every Key Indicator card is the companionships' own meta** (`ki_*_meta` from the weekly form), because that is the number the official app shows the Assistants and the two must agree. The leadership transfer goal from Metas is a labelled mark on the same bar and its own line in the drill-down. | Reverses the tier order `_resolve_group_goal` applies to the seven KIs (`breakdowns_engine.py:487`). Nightly metrics are unaffected (they have no meta). See §1.1 for the cambio-grain nuance. |
| 7 | **The zone comparison is the seven Key Indicators**, per-area weekly average, one row per zone, clickable into Desgloses. The nightly funnel columns move behind a toggle. | §4 Step C3. |
| 8 | **Embudo's Tableau export will be re-run or automated.** Embudo stays a separate page, fully repaired and restyled, with a freshness header. | §6, all of Phase E. |
| 9 | **A shortlist of ~8 nightly metrics above the fold** on Desgloses; the other twelve behind "Ver todos". | §5 Step D3. Shortlist in §1.2. |
| 10 | **Three grading states, no blue**: on pace (green, ≥ 90% of pace), behind (amber, 60–89%), far behind (red, < 60%). Blue means "this metric / this period" on every chart. | §2 Step A3. `_GOAL_BAR_TIERS` (`design_system.py:503`) becomes two thresholds. |
| 11 | **KI card labels, everywhere**: Nuevas personas · Lecciones c/ miembro · Amigos en sacramental · Amigos · 1ª semana · Con fecha bautismal · Bautizados · CR en la Iglesia. | `_KI_SHORT_LABELS` (`01_Panel.py:~620`) moves into the design system as the one source. |
| 12 | Phase order **A → B → C → D → E → F**. | Below. |

### 1.1 — Decision 6 at the two grains

The weekly form writes a week's meta on the PREVIOUS week's form
(`get_ki_goals_for_week`, `queries.py:740`), so:

- **Weekly grain** (Panel scoreboard, drill-down "Por semana"): the bar's goal is
  the sum of the metas written for that week by the areas in scope. This is
  exactly what the official app shows. The leadership goal's weekly share
  (transfer total ÷ cycle weeks) is the mark.
- **Cambio grain** (Desgloses on "Este cambio hasta hoy", drill-down "Por
  cambio"): companionship metas only exist for weeks already planned, so the bar
  compares *actual so far* against *metas set so far*; the full-cycle mark is
  the leadership transfer goal. The caption names both in one line:
  "225 de 254 propuesto · meta del cambio 2.038".
- **No meta written** (an area that left the goal blank): no bar, "sin meta" —
  never a zero goal. `test_a_meta_nobody_set_does_not_draw_a_bar` already pins
  this.

### 1.2 — The nightly shortlist (decision 9)

`contacts_made`, `contacts_attempted`, `friend_lessons`,
`lessons_member_present`, `baptismal_invitations`, `church_invites`,
`referrals_received`, `baptismal_calendars`. Keys verified against
`nightly_metrics()`; the remaining twelve render under "Ver todos" in the same
row component, grouped Contactar · Enseñar · Miembros · Invitar.

### 1.3 — What the data can show (probed live 2026-09-18)

- `WEEKLY_KI`: six complete weeks, 2026-08-16 → 09-13, plus 09-20 in progress.
- `DAILY_LOG`: 2026-08-09 → 09-17.
- Cambio **2026-6** in progress (09-07 → 10-18, week 2 of 6); **2026-5** is a
  partial twin (its weeks from 08-09); 2026-4 has no data. "Por cambio" starts
  with two bars and grows one per cycle.
- `AREA_TRANSFER_GOALS`: all 45 areas for 2026-6.
- `TABLEAU_BAPTISMS`: monthly through 2026-07.
- Tableau detail (Embudo): ends 2026-08-09 until re-run.

---

## §2 — Phase A: Foundation (design system)

Nothing changes meaning in this phase; every page gets the wrapping cards and
the one chart language. Fixes X1–X7.

### A1 — The card wraps and carries a sparkline and a link
`app/components/design_system.py:607` (`render_kpi_row`), `_CSS` at :25.

- Replace the outer `display:flex` with a CSS grid:
  `grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))`, gap 12px.
  Four cards per row at 1400px, two at 375px, never a crushed column. The
  `chunk 4-up` loops on Desgloses (`breakdowns_engine.py:2098, 2230`) are
  deleted — the grid wraps by itself.
- New optional keys on the metric dict:
  - `spark`: a list of numbers → an inline SVG polyline (last point emphasised),
    26px tall, one hue (`SERIES_COLORS[0]`). No axes. Empty list → no sparkline.
  - `href`: when present the whole card is an `<a>` with the query string
    (`?ki=<key>`), styled identically, `cursor:pointer`, hover border. This is
    what makes a card clickable (Phase B reads the param).
  - `mark`: a second labelled tick on the goal bar (the leadership goal,
    decision 6). Rendered like the pace tick in a distinct colour, with a
    `title=` tooltip naming it.
- **One caption line.** The card prints label, value, change chip, bar, and ONE
  line under the bar: `"{pct}% de {goal}"` plus, if paced, `" · día {n}/{m}"`.
  `goal_note`, the per-area pair, the projection and the leadership note move
  to a `details` string that the section's ⓘ (A4) shows. The three-line
  caption tests in `tests/test_kpi_goal_bar.py` and `tests/test_kpi_pace_goal.py`
  that assert the old wording are updated to the one-line contract; the
  arithmetic tests (`goal_bar_state`) are untouched.
- Caption colour `#4b5563` → `#9aa0ad` (7.9:1). `test_section_labels.py`'s
  contrast helper is reused in a new test that the caption clears 4.5:1.
- Value font 2rem → 1.9rem with `tabular-nums` (already), label 0.68rem →
  0.72rem, sentence case, no letter-spacing shout; `min-height: 2.4em` so a
  two-line label and a one-line label sit on the same baseline in a row.

Acceptance: the Panel's KI row renders as 4+3 cards at 1400px and 2-per-row at
375px, every value legible; `render_kpi_row` tests green; suite at baseline.

### A2 — One chart helper
New `app/components/charts.py`.

- `chart(fig, *, height, key)` applies ONE layout: `pmg_dark` template, font
  system-ui 12px, `margin=dict(l=44,r=16,t=8,b=36)`, no in-chart title (the
  section label is the title), legend horizontal below the plot only when
  ≥ 2 series, `config={"displayModeBar": False, "responsive": True}`,
  `use_container_width=True`, minimum height 220 on any width. It is the ONLY
  call site of `st.plotly_chart` on the three pages after this phase.
- `bars_vs_goal(labels, actual, goal, *, twin=None, pace_index=None)`: the
  drill-down's bar chart (mockup 3.2): blue bars, dashed amber goal line, dotted
  outline ghost bars for the twin, a white pace tick on the in-progress bucket,
  the value on each bar.
- `small_multiples(series: dict[label, (x, y)], cols=4)`: one mini line per
  metric, one hue, its own y-axis, last value printed; replaces the 8-week
  spaghetti (P4).
- `stage_bars(stages: list[(label, value)])`: horizontal single-hue bars with
  the step conversion written between rows (mockup 3.3); replaces both Plotly
  funnels (D5, E4).
- `ranked_list(rows, *, value_fmt, bar_max, href=None)`: the compliance-rankings
  row generalised (rank · dot · name · sub-line · inline bar · change · value),
  extracted from `views/01_Panel.py:1785` (`_rank_row_html`) so the Panel's
  rankings call it too. Pure HTML; rows may carry an `href`.

Tests: `tests/test_charts.py` — every helper returns a figure/HTML without a
Streamlit runtime; `bars_vs_goal` places the goal line and the tick at the right
indices; `stage_bars` writes the right conversion percentages; `ranked_list`
escapes names.

### A3 — One palette
`app/config/theme.py`, `design_system.py:23, 503`.

- `PALETTE` is retired from charts. `SERIES_COLORS` (eight validated hues) is
  the identity palette; `SERIES_COLORS[0]` ("#3987e5") is the single magnitude
  hue; the twin/ghost colour is `rgba(255,255,255,.35)`; status is
  `STATUS = {"good": "#3ecf6f", "warn": "#f2b134", "bad": "#f0645a"}`. The
  compliance calendars keep their green/amber/red tints since they ARE status.
- `_GOAL_BAR_TIERS = ((90, STATUS["good"]), (60, STATUS["warn"]))`, below →
  `STATUS["bad"]` (decision 10). `test_kpi_pace_goal.py::test_a_zone_exactly_on_pace…`
  and siblings keep passing (they test green/red); the one test that names the
  indigo tier is updated.
- `CHART_COLORS` (the blue ramp) is no longer imported by the three pages.
  It stays in `theme.py` for the pages not in scope.
- Run the dataviz validator once on the final six-colour set against `#08080e`
  and record the result in the commit message.

### A4 — Section labels: two tiers, no numbers, an ⓘ
`design_system.py:952` (`render_section_label`).

- `numbered=False` becomes the default; the circled-number machinery stays for
  any page that still passes `numbered=True` (Puntajes, Metas are out of scope).
  `test_section_labels.py::test_sections_are_numbered_in_render_order` and the
  three numbering tests are kept and switched to call with `numbered=True`.
- `render_section_label(text, *, emphasis=False, info: str | None = None,
  right: str | None = None)`: `info` renders an ⓘ that toggles a muted
  paragraph under the label (pure CSS `<details>`, no rerun); `right` renders a
  short muted string at the label's right edge (the period, the coverage).
  This is where every explanatory caption from X4 goes — one per section.

### A5 — KI vocabulary in one place
- `_KI_SHORT_LABELS` (`01_Panel.py`), `_strip_real` (`breakdowns_engine.py:1878`)
  and the header's suffix-strip (`:1466`) collapse into
  `metric_catalog.ki_short_label(key)` with decision 11's eight labels, each
  through `t()`. Tests in `test_metric_catalog.py`.

### A6 — i18n sweep (X7)
- Wrap in `t()` and add to `es.py`: Embudo's twelve KPI labels
  (`07_Embudo…py:280–345`), the donut legend (category values mapped through a
  small dict, English kept as the sheet value), the two trend captions in
  `breakdowns_engine.py:2940–2960`, the "Expectation …" annotations (`:2380,
  :2540`), the compliance cell titles (`:1170–1300`). `test_i18n_coverage.py`
  groups task9/task10/leftovers must pass with nothing added to an ignore list.

Phase A ships as five commits (A1, A2, A3+A5, A4, A6). Push, reboot.

---

## §3 — Phase B: The drill-down

Fixes D1, D3, D4. Depends on A.

### B1 — The series module
New `app/analytics/ki_history.py`. Pure functions, no Streamlit.

- `weekly_series(scope_areas, metric, cycle) -> list[WeekPoint]`: for each
  Mon–Sun week of the cycle: actual (sum of `ki_*_real` over the scope's rows
  for that `week_end_date`), meta (sum of that week's metas, via the offset rule
  in `get_ki_goals_for_week`), reporting areas, `is_current`, `is_future`.
  Source `get_weekly_form_data()` (`queries.py:548`), scoped with
  `_scope_to_areas` (`breakdowns_engine.py:646`).
- `twin_weekly(scope_areas, metric, cycle) -> list[float | None]`: the same
  week indices of `transfer_window(1)`; `None` past the twin's data.
- `cycle_series(scope_areas, metric) -> list[CyclePoint]`: one point per cycle
  in `transfer_cycles()` that has any data: actual, metas set so far,
  leadership total (`group_goal_totals`, `goals_queries.py`), weeks covered.
- `area_rows(scope_areas, metric, week_or_cycle) -> list[AreaRow]`: per area:
  actual, meta, pct, change vs twin (through `period_delta`, basis 1), nights
  missed in the window (from `DAILY_LOG`), for the ranked list.
- `leadership_weekly_mark(scope_areas, cycle, metric)`: transfer total ÷
  `weeks_in_cycle` for the mark on weekly bars.

Tests `tests/test_ki_history.py` with a synthetic weekly frame: the meta offset
(week W's goal comes from W-7), the twin truncation, a blank meta yields
`None`, the per-area change uses basis 1, an area with no row in the week is
present with actual 0 and "sin informe".

### B2 — The panel
New `app/components/ki_drilldown.py`, `render_ki_drilldown(scope_kind,
scope_value, scope_areas, metric, *, default_tab="week")`.

- Reads `st.query_params["ki"]`; the caller passes the scope. Renders under the
  scoreboard: header (label · scope · "9 áreas · meta del cambio 480"), four
  `st.pills` tabs (Por semana · Por cambio · Por área · Tabla), then:
  - **Por semana**: `bars_vs_goal` over B1's `weekly_series`, goal = metas,
    mark = leadership weekly share, twin ghosts on (decision 5). Caption right:
    "cambio 2026-6 · semana 2 de 6".
  - **Por cambio**: `bars_vs_goal` over `cycle_series`, goal = leadership total,
    a second thin bar for "propuesto hasta hoy".
  - **Por área**: `ranked_list` over `area_rows`, sorted by % of meta, rows
    `href` into Desgloses (`/Desgloses?bd_area=<name>` — the scope selector
    already keys on `bd_area_val`; B3 makes it read the param).
  - **Tabla**: the same numbers as a `render_table` plus a download button.
- A "✕ cerrar" pill clears the param.
- The seven KIs also render as an `st.pills` strip above the panel (the visible
  affordance; the card `href` is the tap target).

### B3 — Wiring
- Panel: the scoreboard's cards get `href=?ki=<key>`; the panel renders
  directly under the scoreboard when the param is set.
- Desgloses: same, inside `_scope_body`'s fragment. `render_scope_selectors`
  (`scope_selector.py:172`) seeds `bd_area_val` / `bd_zone_val` from
  `st.query_params` on first render so a link into an area opens on it.
- `tests/test_ki_drilldown.py`: renders with a stub `st` and asserts the four
  tabs, the closed state, and that the query param selects the metric.

Phase B ships as three commits. Push, reboot.

---

## §4 — Phase C: Panel

Fixes P1–P7. 13 sections → 5. Depends on A and B.

### C1 — Order and the scoreboard
`views/01_Panel.py`.

1. **Indicadores clave** (emphasis label, right: "cambio 2026-6 · semana 2 de 6
   · 39 de 45 áreas informaron"). One `st.pills` toggle: *Esta semana* /
   *Semana pasada* / *Este cambio*. Seven cards through A1 with sparkline (last
   six weeks from `get_weekly_ki_totals`), change (existing `period_delta`
   calls at `:690–760`), goal = metas (decision 6; `_cur_goals`/`_past_goals`
   from `get_ki_goals_for_week`, already computed at `:233`), mark = leadership
   share (`_leadership_week_goal`, `:640`), `href`. The two existing KI
   sections (`:596–795`) collapse into this one. The "—" tiles for the
   in-progress week keep their "llega el domingo" line.
2. **Bautismos 2026**: the existing chart (`:940–1060`) through `chart()`,
   hero line moved ABOVE the chart as a three-figure row (a `render_kpi_row` of
   "Bautismos hasta jul", "vs ritmo", "Proyección"), prior years dimmed,
   2026 in `SERIES_COLORS[0]`, goal pace amber dashed.
3. **Zonas** (C3).
4. **Actividad diaria** (C4).
5. **Informes** (C5).

`_PANEL_HIGHLIGHT_KEYS`, `_RATE_SHORT_LABELS` and their sections move down into
4; nothing is deleted from the data layer.

### C2 — Captions → ⓘ
Every `st.caption` under a section on the Panel (31 today) is either deleted
(it repeated the label), folded into the section's `right=` string (the window,
the reporting count), or moved into that section's `info=` text. The
"no comparison yet" honesty captions stay but render as the change chip's own
text ("sin comparación") rather than a paragraph.

### C3 — Zonas as a ranked list of the seven KIs
- New `zone_ki_table(...)` in `app/analytics/zone_comparison.py`: per zone, the
  per-area weekly average of each KI for the chosen week (from
  `get_weekly_form_data`), plus reporting share. The existing
  `zone_comparison_table` (nightly funnel) stays and drives the toggle view.
- Rendered with `ranked_list`, one row per zone, seven small numbers with the
  best/worst per column tinted, and an inline bar on the sort column; the
  mission row last as today. Sort picker stays (`st.selectbox`), the
  "Promedio por área / Total" radio becomes a pill. Row `href` →
  `/Desgloses?bd_zone=<zone>`.
- Tests: `tests/test_zone_per_area.py` extended for the KI table (per-area
  division by ALL active areas, as today).

### C4 — Actividad diaria
- One section: the three nightly highlights + four rates as one wrapping grid
  (A1), then `small_multiples` of the eight nightly-shortlist metrics over the
  last eight weeks (`get_nightly_weekly_trends`, `exclude_current_week`) and a
  second row of the seven KIs — replacing both spaghetti charts (`:990–1060`).
- Deleted: "Lecciones por día" (`:1075–1130`), the rate arithmetic expander
  (`:520–550`) — its content becomes the section's `info=`.

### C5 — Informes
- `render_section_tabs` is NOT used (it is a page-level idiom); instead one
  section label "Informes" with `st.pills` (*Cumplimiento* · *Esfuerzo*).
- Cumplimiento: the headline card, then the rankings (`:1600–1900`, unchanged
  arithmetic, now through `ranked_list`; the six-widget control block becomes
  one row: scope pills + three selectboxes), then BOTH calendars inside one
  expander "Calendarios". The combined-compliance box (`:1540–1560`) is deleted.
- Esfuerzo: the existing cards + stacked bar + per-area expander (`:1140–1320`)
  unchanged in arithmetic, inside the tab.

Acceptance for Phase C: the Panel is ≤ 5 screens at 1400px with Informes
collapsed; screenshots at 1400px and 375px in the commit; `test_renders_ccsm_*`
and `test_nav_and_locale_rendered.py` at baseline; no `st.plotly_chart` call
outside `charts.chart`.

Phase C ships as five commits. Push, reboot.

---

## §5 — Phase D: Desgloses

Fixes D2, D5–D7. Depends on A and B.

### D1 — Scoreboard replaces header + KI cards
`breakdowns_engine.py:1599–2110`.
- `_render_progression_header` is retired; its coverage line becomes the
  scoreboard's `right=` text and its three lines are the first three cards.
- The seven KI cards use A1 with `href`, sparkline (weekly series for the scope
  from B1), goal per decision 6/§1.1, mark = leadership share, twin change as
  today. The "no goal set for this cambio" captions become one `info=`.
- `test_progression_header.py` is retargeted at the scoreboard's coverage line.

### D2 — The drill-down under it (B2/B3), opening on the tapped metric.

### D3 — Actividad diaria as grouped rows
`:2115–2235`.
- The twenty cards become `ranked_list`-style rows (label · value · Δ chip ·
  goal % · 8-week sparkline), the eight shortlist metrics visible, the rest
  under an `st.expander("Ver todos los indicadores nocturnos")`, grouped by
  the four headings. The projection ("va camino a ~") moves to the row's
  hover `title`. Rows carry `href=?ki=<key>`; the drill-down's B1 gets a
  nightly variant (`daily_series`) bucketed Mon–Sun from `DAILY_LOG` — same
  shape, so B2 renders it unchanged.

### D4 — Por área replaces the bar wall; the line chart only at district scope
`:2240–2960`.
- The Metric picker is deleted; the drill-down's "Por área" tab IS the per-area
  view for any metric (KI or nightly). The 45-bar chart and its ghost logic
  (`:2430–2570`) are removed; `_bar_delta_chip` is reused by `area_rows`.
- The multi-line trend (`:2570–2960`) is kept ONLY when `len(group_areas) ≤ 8`
  (district scope, single area), restyled through `chart()`, legend below,
  isolate-on-click retained. At zone and mission scope the section is the
  drill-down. `test_breakdowns_chart_movement.py` keeps its ghost-bar
  arithmetic tests against `area_rows` instead of the figure.

### D5 — Proceso de enseñanza from the five weekly KIs
`_render_teaching_pipeline` (`:852–1085`).
- Stages: Nuevas personas → Lecciones c/ miembro → Amigos en sacramental →
  Con fecha bautismal → Bautizados, all from `weekly_wk`, through
  `stage_bars`, with the twin's values as a second thin bar. The Tableau
  "Enseñadas" stage and its three warnings are removed from this page (Embudo
  owns Tableau). The "not subsets" caveat becomes the section's `info=`.
- The "This Week" suppression stays (the weekly form has not landed).

### D6 — Compliance only at area and zone scope
`04_Desgloses.py:335` — `_render_compliance` is skipped when
`scope_kind == "Mission"`.

Phase D ships as five commits. Push, reboot.

---

## §6 — Phase E: Embudo de Búsqueda

Fixes E1–E6. Depends on A only; may run alongside C.

### E1 — Freshness header
`07_Embudo…py:230–275`. Under the page header: a status line
"Exportación de Tableau · datos del {first} al {last} · cargada {at} por {by}",
amber when `last` is more than 7 days old. The presets are computed relative to
`last`, and their labels say so ("Últimos 30 días de la exportación").

### E2 — Scoreboard
`:280–345`. The six KPIs through A1 (wrapping, translated per A6), "Bautismos
oficiales" shows its month-range rule as the section `info=`, not a six-line
caption.

### E3 — Stage bars replace the funnel; the donut becomes a single stacked bar
`:290–360`. `stage_bars` for the seven stages with step conversions (mockup
3.3), the 7%-to-church step highlighted as the largest drop. The finding-mix
donut becomes one 100% stacked bar with the four categories (identity hues from
`SERIES_COLORS`, legend below).

### E4 — Sources and zones as ranked lists
`:365–405`. `ranked_list` with full labels (fixes the 10px margin clipping),
top 10 sources, all zones with a "pilot zone" dot on the four.

### E5 — Trend by week with the prior period as ghosts
`:410–425`. `trend_series` gains a weekly bucket; `bars_vs_goal` with no goal
and the previous equal-length window as twin.

### E6 — Operational blocks collapsed
`:520–729`. One `st.expander("Datos y carga")` holding the four tables/PDF and
the uploaders. Behaviour unchanged.

Phase E ships as three commits. Push (views only → no reboot needed unless A
landed in the same push).

---

## §7 — Phase F: Verification

- Every section of the three pages screenshotted at 1400px and 375px, attached
  to the final commit message as a checklist.
- `venv/Scripts/python.exe -m pytest tests/ -q` at the 13-failure baseline
  (re-measured by stash-and-rerun on 2026-09-18 — see the commit that closes A1).
- `test_i18n_coverage.py` green with no ignore-list additions.
- No `st.plotly_chart` outside `charts.py`; no hex literal outside `theme.py`
  and `design_system.py` on the three pages (a grep in `tests/test_charts.py`).
- Push, Reboot, then read the deployed Panel on a phone and a laptop.

---

## STATUS

- 2026-09-18 — audit published, twelve questions answered (§1), plan written.
  Nothing built. Awaiting go-ahead for Phase A.
- 2026-09-18 — **A1 landed.** `render_kpi_row` is a wrapping CSS grid
  (`minmax(max(210px, 22%), 1fr)`, two columns under 640px), the Desgloses
  4-up loops are gone, and the card takes `spark`, `href`, `mark`/`mark_label`,
  `day`/`days` and `details`. Measured live: Panel 4+3 at 1400px (sidebar
  open or collapsed), 2 per row at 375px; Desgloses 7 and 20 cards in one grid
  each. Suite 13 failed / 1007 passed (same 13). Decisions made mid-build:
  (a) the caption's details (goal note, per-area pair, projection, due date)
  ride as the caption's hover `title` until a page passes them to A4's ⓘ, so
  nothing is lost in the interim; (b) the paced caption prints "día n/m" only
  when the caller passes `day`/`days`, else "{pace} esperado a hoy" — the
  engine does not yet pass day counts (Phase C/D wires them); (c) the 4-column
  cap is a 22% minimum, not a fixed track count, so a 3-card row still
  stretches. Noted, not fixed: at 375px a `render_table` on the Panel is
  451px wide and scrolls the main pane sideways — Phase C's tables.
- 2026-09-18 — **A2 landed.** `app/components/charts.py`: `chart()` (the only
  `st.plotly_chart` on the three pages — 13 call sites converted, 0 remain;
  the Desgloses trend keeps its own iframe until D4), `bars_vs_goal`,
  `small_multiples`, `stage_bars` (HTML), `ranked_list` (the Panel's rankings
  now call it). `theme.STATUS` added early because both A2 and A3 need it.
  Verified live at 1400px: Panel 5 charts, Embudo 5, Desgloses 2 + iframe, no
  in-chart titles, no modebars, no exceptions; Embudo's two bar charts show
  full y-labels (E2 fixed as a side effect of `automargin`). Suite 13 failed /
  1036 passed (same 13). Decisions: (a) the two-up 8-week charts and the
  effort chart lost their in-chart titles and gained `render_section_label(…,
  numbered=False)` above them, so nothing is unnamed before C4/C5 replace
  them; (b) `bars_vs_goal` takes `pace_value` beside `pace_index` — the tick
  needs a height, not just a bucket; (c) a per-bucket goal draws a dash over
  each bar (shapes), a scalar goal one `add_hline`.
- 2026-09-18 — **A3 + A5 landed** (one commit). `theme.STATUS` is the only
  grading palette: `_GOAL_BAR_TIERS` is two thresholds (90/60) over
  good/warn/bad, the change chips on the card and in the engine use it, the
  Plotly template's colorway is `SERIES_COLORS`, the Panel imports no
  `CHART_COLORS`, the Embudo donut uses `SERIES_COLORS`; `PALETTE` stays
  defined for out-of-scope pages. `metric_catalog.ki_short_label` /
  `KI_SHORT_LABELS` is the one KI vocabulary (sentence case); the Panel's
  `_KI_SHORT_LABELS`/`_ki_label`, the engine's `_strip_real` and its header
  suffix-strip are gone. Validator (dataviz `validate_palette.js`, dark,
  surface #08080e) on `#3987e5,#3ecf6f,#f2b134,#f0645a,#9085e9,#8b5cf6`:
  contrast all ≥ 3:1 PASS; the categorical checks FAIL (status hues sit above
  the dark lightness band, warn↔good ΔE 5.6 protan, the two violets ΔE 9.9)
  — recorded, not acted on: these six are never adjacent series; status is
  always paired with a percentage or an arrow, and the two violets never
  share a chart. Verified live on Panel, Desgloses, Embudo. Suite 13 failed /
  1040 passed (same 13; the A3+A5 commit message says 1041 — a miscount). Left for Phase D/E: the Desgloses funnel's and the
  Embudo funnel's own colour lists, which D5/E3 replace outright.
- 2026-09-18 — **A4 landed.** `render_section_label(text, *, emphasis,
  numbered=False, info, right)`: unnumbered by default (the ①②③ machinery
  stays for `numbered=True`; no page passes it now, so Puntajes/Metas lose
  their numbers too — out of scope, left as is), `info` renders an ⓘ and the
  whole label line is a `<details>` summary that opens a muted paragraph,
  `right` is a muted string after the rule. Verified live: Panel renders 16
  labels, no circled digits, no exceptions. Suite 13 failed / 1047 passed
  (same 13; the A4 commit message says 1050 — a miscount). No caller passes `info`/`right` yet — Phases C/D/E do.
- 2026-09-18 — **A6 landed. Phase A complete.** Wrapped in `t()` with es.py
  entries: Embudo's eleven KPI labels, the donut legend (sheet values stay
  English in the data; a `_FINDING_CATEGORY_LABELS` map translates the four
  live categories plus Unknown), the "Unknown" placeholder on the source/zone
  bars and the donut's centre, the engine's expectation annotations (both
  the per-metric dash and the group bar line), the three trend captions and
  the click instruction, and the compliance calendars' cell titles (daily and
  weekly). Found and fixed on the way: the two existing trend captions passed
  a trailing space into `t()` that es.py's keys lacked, so they rendered in
  English — all three now strip it and add the space outside. Verified live
  (Spanish): Embudo labels and legend, Desgloses trend caption and calendar
  titles at zone scope. Coverage test passes with nothing ignored. Suite
  13 failed / 1047 passed (same 13). **Phase A is done**; pushed,
  Zackary told to Reboot. Next: Phase B on his word.
- 2026-09-18 — **B1 landed.** `app/analytics/ki_history.py`: `weekly_series`,
  `twin_weekly`, `cycle_series`, `area_rows`, `leadership_weekly_mark` /
  `leadership_total`, plus the calendar helpers `cycle_weeks`,
  `cycle_position`, `sundays_between`. Pure; every sheet read sits behind a
  keyword (`weekly=`, `daily=`, `cycles=`, `goals_by_cycle=`, `totals=`) that
  defaults to the live loader. `tests/test_ki_history.py`: 22 tests on a
  synthetic frame (meta offset W-7, partial-twin None, blank meta → None,
  basis-1 change, silent area present with 0 and `reported=False`, nights
  missed up to yesterday). Decisions: (a) a past week nobody in scope
  reported carries `actual=None`, not 0 — the bar is absent, not a failure;
  (b) `meta_so_far` on a cycle sums the metas of weeks up to and including
  the CURRENT one, not next week's already-written meta, so "propuesto hasta
  hoy" and "actual hasta hoy" cover the same weeks; (c) the `_meta` column is
  derived by name from the `_real` key rather than through `goal_metric_key`,
  which would read QUESTIONS_CONFIG; (d) a cycle with no weekly rows at all
  is omitted from "Por cambio" rather than drawn empty.
- 2026-09-18 — **B2 landed.** `app/components/ki_drilldown.py`:
  `render_ki_drilldown(scope_kind, scope_value, scope_areas, metric=None, *,
  default_tab, key)` reads `?ki=` (`selected_ki`, validated against the
  catalogue), draws the seven-KI `st.pills` strip (+ "✕ cerrar" while open;
  a tap sets or clears the param and reruns), then the header
  (`render_section_label(…, right="45 áreas · meta del cambio 2.038")`),
  four `st.pills` tabs (Por semana · Por cambio · Por área · Tabla) and the
  tab body. `ki_href(metric, params)` builds the card link. `bars_vs_goal`
  gained `mark` / `mark_label` (scalar or per-bucket, dotted, the card's
  violet `#9085e9` as `charts.MARK_LINE`) so the companionships' amber meta
  and leadership's mark are two different marks on every chart. 34 es.py
  entries; the file is in the i18n gate's task11 group.
  `tests/test_ki_drilldown.py`: 11 tests against a recording stub `st`
  (closed state, invalid key closes, param opens with the four tabs, taps
  set / clear the param, the three other tabs' content, `ki_href`).
  Decisions: (a) the strip's widget key carries the open metric so a
  link-driven reload never meets a stale pills value; (b) the tab widget IS
  keyed (`{key}_tab`) so the chosen tab survives a metric switch; (c) the
  week in progress draws whatever weekly rows already exist (usually none →
  no bar) with a pace tick at meta × elapsed/7 — the Panel's nightly
  stand-ins are not borrowed; (d) "Por cambio" draws `meta_so_far` as the
  amber goal and the leadership total as the violet mark, same idiom as the
  weekly tab, rather than a second bar; (e) "Por área" rows link to
  `/Desgloses?bd_area=<name>&ki=<metric>` and the ranking is by % of meta,
  areas without a meta last; (f) the Tabla tab's CSV carries the raw
  numbers, the on-screen table the formatted ones.
- 2026-09-18 — **B3 landed. Phase B complete.** Panel: both KI blocks' cards
  carry `href=ki_href(k)` and the panel renders under 2b (mission scope =
  every submitting area, `key="panel_ki"`). Desgloses: the engine's KI cards
  carry `ki_href(k, {bd_zone|bd_district|bd_area: scope_value})` and
  `render_ki_drilldown(scope_kind, scope_value, group_areas, key="bd_ki")`
  renders right under them, inside the fragment. `render_scope_selectors`
  seeds `bd_*_val` from `?bd_zone / ?bd_district / ?bd_area` on page entry
  (`seed_from_params`, deepest wins, MISSION_ORG autofill fills the boxes
  above) and every pick callback drops those params so a later reload does
  not snap back. `tests/test_scope_seed_from_url.py` (5).
  Verified live at 1400px: `/?ki=ki_new_people_real` opens the Panel on the
  metric (14 card hrefs, legend "Cambio 2026-5 · Cambio 2026-6 · Meta de las
  compañerías · Meta del liderazgo, por semana · Esperado a hoy", week 1 =
  225 vs meta 203, ghosts 16/204/301/184/170); Por cambio caption "225 de
  474 propuesto · meta del cambio 2.038 · 1 de 6 semanas informadas"; Por
  área 45 rows ranked, Huequen 11 of meta 5 first; Tabla + CSV.
  `/Desgloses?bd_area=Huequen&ki=…` seeds Angol / Purén y Los Sauces /
  Huequen and opens "Nuevas personas · Huequen · 1 áreas · meta del cambio
  43"; `?bd_zone=Angol&ki=…` likewise. At 375px the strip and tabs wrap,
  charts and ranked rows are 339px wide, nothing of the panel overflows.
  Suite 13 failed / 1085 passed (same 13). One test adjusted:
  `test_renders_ccsm_with_data._text` now strips `href="…"` before the
  Provo-vocabulary scan — `?ki=ki_member_lessons_real` contains Provo's
  `member_lessons` as a substring and is a link target, not displayed text.
  Noted, not fixed: (a) at 375px the main pane still scrolls sideways —
  the zones table (766px) and the three long section labels (the Panel's
  two KI headings at 630/546px and the drill-down header at 521px) do not
  wrap; C1 renames the headings and Phase C's tables own the rest, and
  `render_section_label` should be allowed to wrap then; (b) the KI card's
  goal bar is still the leadership goal (2038/6 = 340) while the drill-down's
  weekly bars use the companionships' meta (203) — decision 6's tier
  reversal is C1's job, and until then the two disagree by design; (c) the
  live 2026-5 row carries a stray leadership goal of 6 for new people, which
  "Por cambio" draws honestly as a dot at 6 — a data question for Zackary,
  not a code one; (d) reading a freshly restarted server too early (first
  ~10s) shows the page before its query params are applied — a cold-start
  artefact, not a bug, seen once and not reproducible warm.
- 2026-09-18 — **C1 landed.** The Panel is reordered and the two Key Indicator
  sections are one scoreboard. Order is now: Indicadores clave (the seven cards
  + the drill-down) → Bautismos 2026 → Zonas → the old nightly/rates/trend/daily
  sections, renumbered 4a–4d → effort and compliance, renumbered 5a–5b for C4
  and C5 to fold in. **Decision 6 is applied and reverses the card's bar**: the
  goal is the companionships' `ki_*_meta` and the leadership transfer goal is
  the violet mark, so a card and the drill-down beneath it finally draw the
  same quantity (live: "76% de 221" against the panel's own weekly meta).
  The period is an `st.pills` toggle — *Esta semana* / *Semana pasada* / *Este
  cambio* — keyed on the open period so a deselect cannot strand a stale value,
  and it reruns on change so the heading's right-hand line and the cards always
  describe one period. The heading carries `right=` (cambio, week n of m,
  reporting coverage) and `info=` (the five captions those two rows used to
  carry). Bautismos leads with a three-card row — 283 · 54% de 527 · 307
  esperado a hoy, −24 vs. ritmo, ~485 proyección — above the chart instead of a
  caption below it. Decisions made mid-build: (a) **the default period is
  "Esta semana"**, matching the plan's own order and the page's standing
  "the week leadership can still act on leads" rule, even though four of seven
  cards read "—" early in the week — one line to change if Zackary wants
  "Semana pasada" instead; (b) `_KI_NIGHTLY_RELABEL` is gone — ki_baptismal_date
  no longer borrows `baptismal_calendars` as its VALUE under a relabelled tile,
  because one row of seven cannot carry a name that is not a Key Indicator
  (decision 11); the count survives as the card's note ("llega el domingo · 13
  calendarios bautismales entregados"); (c) the cambio arrows compare on
  AREA-WEEKS, not week counts — week counts alone set 225 against a twin week
  that two areas filed and printed "+209", so cambio 2026-5 is now refused by
  name with the half-the-mission gate; (d) `_today` is `mission_today()`, not
  `date.today()` — the drill-down already used mission time and the two must
  agree on what week it is; (e) the second `_night_anchor` (the compliance one)
  is `_due_anchor`, so C4 can move the nightly section past it safely;
  (f) `render_section_label`'s row wraps and its `right=` line wraps with it
  (B3 note a), which is what lets the heading fit 375px. Verified live at
  1400px (7 cards 4+3 at 216px, no sideways scroll, all three periods) and
  375px (2 per row at 164px, the right-hand line on its own row, nothing of
  the section overflowing — the zones table at 766px and the compliance
  calendar at 418px are all that still scroll sideways, and they are C3's and
  C5's). Suite **13 failed / 1102 passed** (same 13). One existing test
  changed: `test_key_indicator_headings_carry_the_emphasis_treatment` expected
  TWO headings and now expects one, renamed to the singular.
  `tests/test_panel_scoreboard.py` (15) is new and supplies the weekly-form
  frame the shared fixtures lack; `tests/test_section_labels.py` gained two.
- 2026-09-18 — **C2 landed.** The Panel's explanatory captions are gone: the
  page opened with a three-sentence paragraph (one sentence of which — "drill
  into a zone on the Breakdowns page" — stopped being true when every card
  became a link), and seven sections carried a caption apiece. Each is now the
  section's ⓘ, its `right=` line, or a chip on the card it describes. Live
  count: **8 sections carry an ⓘ, 2 `st.caption` elements remain on the whole
  page** (one empty, one the rankings' "las 5 mejores y las 5 últimas de 45
  áreas"). `render_kpi_row` gained `change_note` / `change_note_title`: where a
  comparison is refused the card says "sin comparación" with the reason on
  hover, and the page ALSO appends that reason to the section's ⓘ, because a
  phone has no hover — the plan's "render it as the chip's own text" plus the
  one thing that would otherwise be lost. Zones and Effort now compute their
  arithmetic ABOVE their heading so the ⓘ can quote it (Streamlit renders in
  source order); nothing about the arithmetic changed. Suite **13 failed /
  1102 passed** (same 13); `tests/test_kpi_card_layout.py` +3,
  `tests/test_panel_scoreboard.py` +4, 19 in that file now. Left for C5, as
  they belong to sections it rebuilds: the compliance rankings' "what is on
  screen" captions, the two calendar paragraphs under the heat maps (they are
  `st.markdown`, not captions, and their window averages are only known after
  the loop that draws them), and the "Esfuerzo por área" expander's own note.
- 2026-09-18 — **C3 landed.** Zones are a ranked list of the seven Key
  Indicators (decision 7), not a nine-column table of the nightly funnel.
  `zone_comparison.zone_ki_table` / `zone_ki_mission_row` are new and pure:
  per zone, each KI for ONE reporting week (the last complete one — the seven
  come from the weekly form), divided by every ACTIVE area, plus a `reporting`
  count so a quiet week reads as a quiet week rather than a bad one. Zone
  membership comes from MISSION_ORG, never from the weekly frame's own zone
  column. `charts.ranked_list` gained `columns` + per-row `cells` /
  `cell_status`: the row is two halves, who and how much on the left and the
  seven small numbers on the right, best and worst per column tinted, and the
  halves STACK below 720px with every number naming itself. Live at 375px the
  zone rows are 339px wide and the 766px table that scrolled the whole page
  sideways is gone (audit P5). The funnel is one tap away behind a
  `Indicadores Clave / Embudo nocturno` toggle and its figures are unchanged
  (Temuco 138,7 · 60,2 · 15,5 · 2,4 · 57,0, same as before). Rows link to
  `/Desgloses?bd_zone=<zone>`. Decisions mid-build: (a) the seven get a THIRD,
  shorter label set for column headers (`_ZONE_KI_LABELS`: Nuevas · Lecciones ·
  Sacramental · 1ª semana · Con fecha · Bautizados · CR) with the full decision-11
  name on hover — seven columns share ~600px, and `_ZONE_SHORT_LABELS` has been
  the same exception for the funnel since before this plan; (b) a row with
  columns carries NO headline number, because the sort column is already one of
  the seven and printing it twice reads as a mistake — the bar under the zone's
  name carries the ranking; (c) the per-area/total radio became pills under a
  NEW session key (`panel_zone_mode_val`), since Streamlit keeps a retired
  widget's state under its old key; (d) `_night_window` moved up into the shared
  header, because zones now renders before the nightly section that used to
  define it. Suite **13 failed / 1120 passed** (same 13).
  `tests/test_zone_per_area.py` +6 (the new table's own rules),
  `tests/test_panel_scoreboard.py` +5, and
  `test_the_zone_table_ends_with_a_mission_row` was renamed and re-pointed at
  the ranked list — what it asserts is unchanged. Still scrolling sideways at
  375px and left for C5: the "Esfuerzo por área" table (751px) and the
  compliance calendar (417px), both inside sections C5 rebuilds.
- 2026-09-18 — **C4 landed, and the suite baseline moved to 11.** Four sections
  became one "Actividad diaria": nightly highlights, conversion rates, the
  eight-week trend and the per-day bar chart. They described one subject — the
  nightly form — under four headings, across three windows and two chart
  idioms. Now: one heading, one window in its right-hand line, seven cards
  (three outcomes then four rates), then the eight-week history. Deleted:
  "Lecciones con amigos por día" (audit P6, one metric and a dropdown) and the
  rate-arithmetic expander, whose formulas are in the ⓘ and whose FIGURES are
  on each rate card now ("2.442 de 5.331") — better than either, since the
  evidence sits where the ratio is. `get_daily_summary(7)` is no longer read by
  the page at all.
  **The one deliberate departure from the plan:** the trends are drawn with a
  new `charts.spark_multiples` (a wrapping CSS grid of name · last value ·
  sparkline), NOT with `charts.small_multiples`. Measured at 375px: a Plotly
  subplot grid's column count is fixed when the figure is built, so four
  columns render at ~80px each — titles overlapped their neighbours, the value
  annotations landed in the next panel and the x labels read "2026-0". Plotly
  cannot reflow a subplot grid and Streamlit cannot tell the server the browser
  width, so the grid is HTML — the same reasoning that made `stage_bars` HTML
  in A2. `small_multiples` stays for desktop-only callers (D4) with that
  limitation now written into its docstring. Verified: 8 + 7 panels, 4 across
  at 1400px (301px each), 2 across at 375px (165px each), readable at both.
  Also fixed: **PLAN §1.2's shortlist has a key this mission does not have** —
  `referrals_received` is `member_referrals_received` on CCSM's nightly form.
  The wrong key drew nothing and drew it silently (a metric with no column is
  skipped), so the chart had seven panels where it should have eight.
  Suite **11 failed / 1128 passed**: the 13 became 11 because
  `test_kpi_numbers_use_chilean_separators` and its English twin now PASS —
  they assert a five-figure mission total reaches the screen in Chilean form,
  and until this step no component on the page printed one. Nothing was
  weakened to achieve that. One test WAS tightened:
  `test_dashboard_shows_the_four_conversion_rates` briefly passed for the wrong
  reason (the four rate names appear in the section's ⓘ formulas), so it now
  asserts against KPI card labels and fails again for its original reason —
  that fixture's DAILY_LOG is two months stale, so no nightly card renders.
  `tests/test_charts.py` +4, `tests/test_panel_scoreboard.py` +2.
- 2026-09-18 — **C5 landed. PHASE C IS COMPLETE.** Compliance and effort are
  one "Informes" section with two readings behind `st.pills`, and only the
  chosen one's body runs — the closed tab costs no sheet read, and DAILY_LOG at
  400 days and the effort log at 60 are the page's two most expensive. Inside
  Cumplimiento the order is now headline → rankings → **both calendars in one
  "Calendarios" expander**, and the combined-compliance box is deleted (an
  average of two averages sitting under the headline that already answered the
  question). The rankings' nine widgets became four (audit P7): a pills pair
  and three selectboxes on one row. **A feature was removed on purpose:** the
  zone/district/area/missionary filter above the rankings. The zone reading
  already answers "how does my zone compare", the top-5/bottom-5 fold already
  answers "this list is too long", and a ranking filtered to one district was
  a leaderboard of three rows; per-area compliance is read on Desgloses.
  `render_section_tabs` and `render_scope_selectors` are no longer imported by
  the Panel. Also fixed here, and it fixes a whole class of problem: `.pmg-tbl`
  gained `min-width:0`. Streamlit's block containers are flex columns, and a
  flex item's default `min-width:auto` refuses to shrink below its content, so
  the wrapper's `overflow-x:auto` had never once fired — an 8-column table
  widened its container and **the whole page scrolled sideways**. Every
  `render_table` on every page is contained now.
  **Acceptance met:** at 1400px the Panel is **4.8 screens** on Cumplimiento
  and 4.3 on Esfuerzo (plan asked ≤5), **five emphasis-tier sections**
  (Indicadores clave · Bautismos · Zonas · Actividad diaria · Informes) where
  there were thirteen, **zero sideways scroll at 375px** for the first time,
  no `st.plotly_chart` outside `charts.chart`, and no exceptions on any tab.
  Suite **11 failed / 1133 passed**; `tests/test_panel_scoreboard.py` is 31
  tests. Not done, and left where the plan left them: the rankings' two
  "what is on screen" captions (they depend on the fold, which is only known
  after the list is built) and the "Esfuerzo por área" expander's own note.

- 2026-09-19 — **E1 + E2 landed** (`5d012a3`), the first of Phase E, run
  ahead of Phase D on Zackary's word (E depends only on A). A freshness strip
  leads the page: the export's span, who loaded it and its age, muted inside a
  week and amber past one — live it reads *"datos del 1 de ene de 2024 al 3 de
  ago de 2026 · Cargado por backfill:tableau-detail · 2026-08-23 00:13 UTC ·
  47 días de antigüedad"*. Every preset counts back from the export's last
  date and never from today, so the labels say so ("Últimos 30 días de la
  exportación"); the row is full width, because at those longer labels the old
  3:2 split wrapped five presets onto **three lines at 1400px**, and the custom
  date boxes moved to their own row. The indigo "📅 … · 30 days" chip is gone —
  it restated the chosen preset and its day count was the one string on this
  page that never went through `t()`; the window is the scoreboard heading's
  `right=` now. E2: the six KPIs get "Resumen de búsqueda" with the
  whole-calendar-months rule as its ⓘ, and the card's note stops being an
  instruction. Decisions: (a) `PRESET_LABELS`, `EXPORT_FRESH_DAYS`,
  `export_age_days` and `export_is_stale` went into
  `app/analytics/finding_funnel.py`, not the page — the vocabulary and the
  staleness rule are facts about the export and are now unit-tested; (b) the
  freshness threshold is **more than** seven days, so a Monday pull still
  reads fresh on Friday. `tests/test_finding_funnel.py` +7.
- 2026-09-19 — **E3 + E4 landed** (`9a74a2f`). The Plotly funnel is
  `charts.stage_bars` (seven rows, one hue, the step conversion between them)
  and **the step that loses the most people is named on the chart** — live,
  2.545 recibiendo lecciones → 167 que asistieron a la Iglesia, "↓ 7% · mayor
  caída". That highlight is the largest ABSOLUTE fall, not the lowest rate:
  the lowest rate on this export is the 4% from 68 fechas fijadas to 3
  bautizados, which costs 65 people against 2.378, and pointing at it would be
  wrong. The two captions under the funnel — the inheritance rule and the
  six-line tracked-vs-certified one — are the section's ⓘ. The donut is
  `charts.share_bar`, one 100% stacked bar with the four categories in
  `SERIES_COLORS` identity hues and a legend carrying count and share; 430px +
  400px of chart became **284px + 59px**. E4: both horizontal bar charts
  (audit E2 — a 10px left margin clipped every category name to about two
  letters, in charts whose entire content is names) are `charts.ranked_list`,
  with the share on each source and "Zona piloto" under the four
  `AGENT_CONFIG.PILOT_ZONES`. Decisions: (a) the plan's "pilot zone dot" is a
  `sub` line instead — the row's dot is the grading colour, and tinting four
  zones green would read as "on pace"; (b) a stage label **wraps** rather than
  ellipsising, because at 375px the label column is 115px and "Fecha de
  Bautismo Fijada" needs 137; (c) `ranked_list` gained a `title` on the name,
  so a name too wide for a narrow column is still readable on hover — that is
  what E4 means by "full labels". `tests/test_charts.py` +11 (44).
- 2026-09-19 — **E5 + E6 landed** (`fc002ee`). **PHASE E IS COMPLETE.**
  The trend is seven-day blocks with the previous equal-length window behind
  them as ghosts, through the same `bars_vs_goal` the drill-down uses (no
  goal, so no goal line): live 206 · 1.213 · 1.025 · 1.088 · 879 for 5 Jul –
  3 Aug against 5 Jun – 4 Jul. The blocks come from the WINDOW and are counted
  BACK FROM ITS END, and both halves are load-bearing — back from the end so
  the newest block is always a whole week and any short one is the oldest
  (counted forward, a 30-day window ends on a 2-day stub that reads as a
  collapse); from the window rather than the calendar so the previous window
  buckets identically and the ghosts compare bar for bar. Ghosts are drawn
  only when the export reaches back that far, and the ⓘ says when it does not.
  `window_buckets` / `bucket_counts` / `previous_window` are new;
  `trend_series` takes an optional window and is unchanged without one.
  E6: five expanders under "DATOS DETALLADOS" are one "Datos y carga"
  expander with the four readings behind `st.pills`, nothing selected by
  default. **The uploaders are deliberately NOT behind a pill** — Streamlit
  drops a widget's session state the moment the widget stops rendering, and
  this page reads `st.session_state["detail"]/["ranking"]/["summary"] ` at the
  top of the script, so a pill that un-rendered them would throw away a
  just-uploaded file; they sit under the pills' output, always drawn.
  `st.expander` cannot nest, which is why this is pills and not five
  expanders inside one. `plotly.graph_objects` is no longer imported by the
  page: every figure on it goes through `charts.py`.
  **Acceptance met:** at 1400px the page is **2.9 screens** (it was six),
  **zero sideways scroll at 375px**, no `st.plotly_chart` outside
  `charts.chart`, no exceptions on any pill. Suite **11 failed / 1161
  passed** — the same 11 as after Phase C. `tests/test_finding_funnel.py` +10
  (43).
  **Noted, not fixed** (pre-existing, and outside E1–E6): the area-rankings
  table's column headers go through `t()` but have no `es.py` entries, so
  they render REFERRED / CONTACT % / CONTACTED % / TEACHING / CHURCH / BAP
  DATE in English on the Spanish interface. Six dictionary entries whenever
  someone wants them.
- 2026-09-19 — **D1 landed.** The progression header is retired and the seven
  Key Indicator cards are the scoreboard the page opens on. The header's three
  lines (baptisms, friends with a date, friends at sacrament) were three of the
  seven cards printed a second time six inches higher; its window and its
  coverage are now the heading's `right=` line ("semana al 13 de sep · 39 de 45
  áreas enviaron informe semanal · 87%") and its captions are the ⓘ.
  `_header_lines`, `_change_chip` and `_HEADER_METRICS` went with it;
  `_header_window` stayed, because the fallback is the reason the header
  existed — these seven arrive once a week, so "Esta semana" before Sunday and
  "Este mes hasta hoy" on the 3rd are periods with no weekly report in them,
  and the scoreboard falls back to the latest complete week and says so in the
  same line ("· esta semana aún no tiene informe semanal"). **Decision 6 is
  applied**: the bar is the companionships' summed `ki_*_meta` and leadership's
  transfer goal is the violet mark, so the card and the drill-down under it
  finally draw one quantity (live at mission scope: "77% de 203" with the mark
  at 2.038, where it read "13% de 2.038" before). Decisions made mid-build:
  (a) the metas are found from the weeks ON SCREEN (each shown week minus
  seven days), not from the period's dates — computed off p_start/p_end the
  fallback week would have been graded against nothing; extracted as
  `_metas_for_weeks` with its own tests, since decision 6 rests on that
  arithmetic; (b) **no pace tick on these seven** — their values are
  weekly-form totals over COMPLETE weeks, so there is no part-period to be
  partway through, and a tick on a bar made of metas-so-far would mean nothing;
  the pace against leadership's target stays in the drill-down (B2); (c) where
  no companionship wrote a meta the bar falls through to leadership's goal and
  carries NO mark, because two ticks saying one thing is not a comparison —
  live, Bautizados is the case; (d) the ⓘ's old "falls back to what the
  companionships set for themselves" sentence was reversed by decision 6 and
  now says the opposite, which is what the page actually does; (e) All Time's
  twin: the header handed `_header_window` its own None bounds, whose
  `_weeks_in` returns the WHOLE frame for them, so All Time compared itself
  against itself and every arrow read flat — now an explicit empty twin.
  **Two bugs fixed on the way, both found in the running app:** (1)
  `areas_with_goals` took no scope while `group_goal_totals` beside it did, so
  a zone's summed goal was divided by the MISSION's count of goal-setters —
  Angol's one baptism against a goal of 10 printed "64%", and now prints 13%;
  it takes `areas=` like its twin, and `tests/test_area_transfer_goals.py` +1.
  (2) `render_section_label`'s label span was `white-space:nowrap`, which was
  fine on the Panel and fatal here: every heading on this page carries its
  scope's name, "Indicadores Clave — Chile Concepción South Mission" is 542px,
  and all SEVEN sections scrolled the main pane sideways at 375px (B3 note a).
  The label wraps now, and the page's sideways scroll is **zero** — the first
  time on this page. `test_section_labels.py`'s
  `test_the_label_itself_still_does_not_wrap_mid_phrase` asserted the old
  behaviour and is reversed, with the reason in its docstring. Verified live at
  1400px (7 cards 4+3 at 216px, no sideways scroll) and 375px (2 per row at
  164px, the right-hand line on its own rows, nothing overflowing), at mission
  and at zone scope, and on the fallback period. Suite **11 failed / 1161
  passed** (the same 11). `tests/test_progression_header.py` is
  `tests/test_desgloses_scoreboard.py`: its `_header_window` tests are
  unchanged, its `_header_lines`/`_change_chip` tests went with those
  functions, and it gained six on `_scoreboard_window_line` and six on
  `_metas_for_weeks`.
