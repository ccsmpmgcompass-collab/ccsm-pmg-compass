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
  1041 passed (same 13). Left for Phase D/E: the Desgloses funnel's and the
  Embudo funnel's own colour lists, which D5/E3 replace outright.
