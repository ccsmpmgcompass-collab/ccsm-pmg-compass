# PLAN — The weekly letter, model v2 in the real code (2026-10-11)

Sources: `AUDIT-2026-10-06-weekly-letter.md` (R1–R5), the approved model v2
(`tools/email_preview/.data/modelo/index.html`, 5 tabs; the Temuco Ñielol
model at the repo root), PLAN-2026-10-10-ki-autosend.md K10 (what it left
for this plan).

**Goal:** every one of the 45 sector letters (plus the President and the two
APs at their own addresses) goes out in the v2 layout. Zackary approves the
previews of all of them BEFORE anything is pasted.

## 1. Decisions (settled; do not re-ask)

1. **Model v2 as approved, no changes.** Temuco Ñielol's leaders asked for
   none (Zackary, 2026-10-11).
2. **Totals use the KI-PDF rule** (2026-10-11). A sector that filed no form
   the week before has no goal: its cell is grey, "sin meta", and its result
   is left out of the graded part of any total. A total cell is
   Σ(results of sectors with a goal) "de" Σ(goals). Same as
   `app/reports/ki_ranking.py` `Unit.Rg/G`, so the letter and the PDF agree.
3. **The date-slip rule** stays (already live): a form dated after the
   graded week counts for it when the sector has no row for it.
4. **Companionships see only themselves** (Q2). Leaders' letters may name
   sectors.
5. **No mission news in any letter** (2026-10-06). The APs' own mission
   figures are their letter's content.
6. **Keep the per-area table** (`a1c_buildAreaDataTable_`) verbatim, font
   9px → 10.5px; it opens section 3 of the DL and ZL/STL letters.
7. **Attachments as already live**: APs the mission PDF only, ZL/STL their
   zone's, nobody else.
8. **Colours are the 90/60 palette** of the KI PDFs and the council packet:
   green ≥ 90%, amber 60–89%, red < 60%, grey = no goal.
9. **Missing weekly form → one kind line, never an empty box** (R1): "Aún no
   recibimos su informe semanal de esta semana", the link to the form, and
   the rest of the letter (their nightly numbers) as normal.
10. **The coaching paragraph follows the focus KI** (R2.3): the focus is the
    KI furthest below its goal that has a nightly chain (`A1A_KI_FEEDERS`);
    the message-bank paragraph is the growth message for that chain's
    weakest nightly feeder, and the same nightly topic is not used two weeks
    running (`FEEDBACK_HISTORY.Last_Growth_Metric`).
11. **AP letter headline: the certified year-to-date baptisms** from
    TABLEAU_BAPTISMS (MISSION rows of the year, "353 de 527"). The model's
    "6 bautismos certificados esta semana" has no weekly certified source in
    the sheet, so the week's figure is the one the forms reported.

## 2. Answered after the previews (2026-10-11)

12. **Q5: the mission report stops for the APs** (Zackary). It goes to the
    President only (`amr_loadLeadershipEmails`); the APs' one weekly email
    is the letter. The Liderazgo page's help text says so.
13. **Launch Monday 2026-10-12, 21:30** (Zackary: "push everything and get
    it ready to be sent out on monday"), the same night as the first real
    KI-PDF auto-send run.
14. **Every letter stays under Gmail's ~102 KB clip.** The grids carry
    shared styles on the table, not per cell; in section 3 the band shows as
    the cell's tint (the number keeps the table colour) and ▲▼ take the
    cell's colour. Largest live letter 98 KB (Los Angeles Norte ZL);
    `tests/test_weekly_letter_v2.js` holds a 13-sector ZL under 100 KB.

## 3. Steps

1. **Agent1A carries four weeks per sector.** `kiWeeks` (4 weeks of the 7 KI
   results, the goal each week was graded against, whether it filed),
   `nightWeeks` (4 weeks of every nightly number, nights reported, effort),
   and `focus` (decision 10). One WEEKLY_KI read for five weeks.
2. **The letter builders (new section of CCSM_Agent1C.gs, prefix `a1c_v2`).**
   Header, preheader, highlight, "Recibimos sus informes", KI grid with four
   weeks, focus, next week's goals, the nightly table (22 + 4 rates, four
   weeks, this week against its goal, next goal).
3. **Leader sections.** Section 2 (KI grid by sector / district / zone, the
   action lists) and section 3 (the per-area table, then every number per
   unit with ▲▼ against last week, the total and last week's total). DL,
   ZL/STL and AP variants.
4. **Subjects that carry news** (`a1c_buildSubject`).
5. **Render all letters** for the week ending 4 Oct (complete data, same
   week as the approved model) with `render.js --now`, measure at 375 px,
   publish the previews for Zackary.
6. **After his approval:** fix the JS test suite to the new layout, retire
   the old builders, push, and Zackary pastes CCSM_Agent1A.gs +
   CCSM_Agent1C.gs. First live letter: the next Monday 21:30 after the paste.

## 4. STATUS

- 2026-10-11: plan written. `render.js` gained `--now ISO` (render a past
  Monday from today's dump), `--forms-until ISO` (weekly forms stamped after
  it are dropped; default = --now, so a later week's form is never taken for
  a date slip) and `--payload FILE` (write A1B_DATA). `dump_tabs.py` now
  dumps TABLEAU_BAPTISMS, and its placeholder MESSAGE_BANK is keyed by
  Metric_Key (it was keyed by Question_ID, so most coaching paragraphs
  rendered empty in every earlier preview).
- 2026-10-11: **steps 1–5 BUILT, NOT PASTED, NOT COMMITTED.**
  - Agent1A: `a1a_loadKiRows_`, `a1a_kiWeeks_`, `a1a_nightWeeks_`,
    `a1a_weekGoalMap_`, `a1a_pickFocus_`; area payload gains `kiWeeks`,
    `nightWeeks`, `focus`, `goals`; `growth` = the focus KI's weakest feeder.
  - Agent1C: new section "THE WEEKLY LETTER, MODEL v2" at the end of the
    file (`a1c_v2*`); runAgent1C sends `a1c_v2letter_()`'s subject + html;
    the Gemini narrative pre-generation is no longer called (v2 has none).
    The old builders (a1c_buildEmail etc.) are still in the file, unused,
    for step 6. `a1c_buildAreaDataTable_` takes an optional font size.
  - Preview: `node tools/email_preview/render.js --now 2026-10-05T21:30:00
    --forms-until 2026-10-08T00:00:00 --ki-pdfs Vista_previa_KI_asistentes
    --out tools/email_preview/.data/v2_1005` → 48 letters (47 distinct; the
    two APs share one). Mission graded total 203/267 new people = the KI PDF.
  - Phone length at 375 px: companionship 3.2–3.7, DL 6.8–7.7, ZL/STL
    14.5–16.8, mission 4.7–4.8. No horizontal overflow.
  - Published for Zackary: https://claude.ai/artifact/DuyY14JAJgMHoRuA3AAz2k
    (built by scratchpad build_review.py; letters inlined via srcdoc).
  - JS suite: 15 files fail; 5 already failed at HEAD (agent5b6, ccsm_data,
    ccsm_helpers, harness_selftest, quota_guards); the other 10 assert the
    old letter's text (agent1c, *_consistency_glossary, *_key_indicators,
    *_ki_pdfs, *_numbers, *_sector_goals, *_trend_goalgrid,
    *_youvsyou_funnel, full_pipeline's "Entrenamiento Semanal" subject,
    ki_prior_week_metas' "12 / 12" cell) → rewrite in step 6.
- 2026-10-11 (later): **approved; step 6 done except retiring the old
  builders.** Size budget (decision 14); FEEDBACK_HISTORY records only the
  growth message (v2 prints no strength message); mission report → the
  President only (decision 12). Tests: 6 suites for dropped sections
  removed, `test_weekly_letter_v2.js` added, test_agent1c / *_ki_pdfs /
  full_pipeline / ki_prior_week_metas / agent_mission_report moved to v2.
  JS suite: 38 pass, 5 fail -- the same 5 that fail at HEAD before this
  work (agent5b6, ccsm_data, ccsm_helpers, harness_selftest, quota_guards).
  Committed and pushed.
- **OWED BY ZACKARY before Mon 10-12 21:15:** paste CCSM_Agent1A.gs,
  CCSM_Agent1C.gs and CCSM_AgentMissionReport.gs into the Apps Script
  project; Reboot the Streamlit app (help text).
- **NEXT (Tue 10-13):** check AGENT_RUN_LOG for Agent1A/1B/1C (48 sent, 0
  errors, KI PDFs attached: 11) and that the APs got no 22:00 report; open
  one letter of each role in Gmail and confirm nothing is clipped.
- **LATER (cleanup, not urgent):** delete the old builders (a1c_buildEmail,
  a1c_buildAreaSection, scoreboard, trend, capsules, Rumbo, Cumplimiento,
  Metas-Esfuerzo, glossary, Gemini narratives) and their direct-call tests
  (area_capsules, cumplimiento_block, duplicate_leadership_section,
  leader_ki_block, leadership_citations_withheld, metas_esfuerzo_block,
  rumbo_block); they are no longer called by runAgent1C.
