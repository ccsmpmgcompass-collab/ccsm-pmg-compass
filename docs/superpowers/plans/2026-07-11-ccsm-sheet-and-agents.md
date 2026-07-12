# CCSM Sheet Builder + Agent Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `BuildCcsmSheet.gs` (creates the complete `COMPASS_CCSM` Google Sheet from scratch) and the full CCSM agent suite (`CCSM_*.gs`, Spanish, Santiago timezone, CCSM metric keys), forked from the Provo PMG Compass agents.

**Architecture:** Standalone Apps Script builder creates the sheet (config/content tabs pre-filled; processed tabs created empty because agents self-initialize their own headers — the Provo pattern). Agents are file-by-file forks of `C:\Users\2011794-MTS\Desktop\PMG-Compass\docs\*.gs` with three systematic adaptations: (1) Spanish form headers/emails, (2) CCSM metric keys via QUESTIONS_CONFIG, (3) config-driven mission identity + `America/Santiago`. A Node.js GAS-stub harness gives every task a runnable test cycle since Apps Script itself can't run locally.

**Tech Stack:** Google Apps Script (V8, `var`-style to match existing code), Node.js (test stubs only), Python+pandas (one-off org-export parsing).

**Spec:** `docs/superpowers/specs/2026-07-11-ccsm-sheet-and-agents-design.md` (read it first).

## Global Constraints

- **Never edit anything under `C:\Users\2011794-MTS\Desktop\PMG-Compass\`** — live production for Provo. Read-only source for forking.
- **No Provo data** may be copied into any CCSM file or sheet (confidential). Structure only.
- All work happens in `C:\Users\2011794-MTS\Desktop\Worldwide PMG Compass\CCSM PMG Compass\`.
- Spanish strings must match the ES form builders **character-for-character** (accents, `¿`, capitalization). Source of truth: `DailyReportForm_ES.gs` / `WeeklyReportForm_ES.gs` in this folder.
- Every `AGENT_CONFIG` read goes through `getConfig()`. Mission name/language/timezone are NEVER hardcoded in agent logic: `MISSION_NAME`, `MISSION_LANGUAGE = ES`, `MISSION_TIMEZONE = America/Santiago`, `MISSION_LOCALE = es_CL`.
- Ship state: `TEST_MODE = TRUE`, `TEST_INBOX_EMAIL = CCSM.PMG.Compass@gmail.com`. No triggers auto-created.
- Every timezone-sensitive call uses `getConfig('MISSION_TIMEZONE')` (e.g. `Utilities.formatDate(d, getConfig('MISSION_TIMEZONE'), 'yyyy-MM-dd')`), never `'America/Denver'` or `Session.getScriptTimeZone()`.
- The Sister Ellis system (Agent7), transfer web-app tooling (AgentTransfer/TransferWebApp/LineageReview), CleanupParkCity, ward-plan/intake/miracle utilities, and referral relay files are **not ported**.
- After any bulk Apps Script writes, verification must re-open the object by ID (`SpreadsheetApp.openById`) — never trust in-place reads of just-written state (the forms' dropped-writes lesson).
- Node tests live in `tests/` here and run with plain `node` (no npm packages).
- Cite Provo source line numbers when forking so review can diff (e.g. `// forked from Agent3.gs:245`).

---

### Task 0: Initialize git repo in the CCSM folder

The folder is not a git repo; the plan requires frequent commits.

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Init and first commit**

```bash
cd "C:/Users/2011794-MTS/Desktop/Worldwide PMG Compass/CCSM PMG Compass"
git init -b main
printf 'node_modules/\n*.xls\n' > .gitignore
git add -A
git commit -m "chore: baseline — existing form builders, setup guide, spec, plan"
```

Expected: clean `git status` afterward. (Local repo only — do not create any remote.)

---

### Task 1: Node GAS-stub test harness

Everything downstream is Apps Script, which cannot run locally. This harness stubs the GAS globals in-memory so agent logic (parsing, aggregation, email content) is testable with `node`.

**Files:**
- Create: `tests/gas_stubs.js`
- Create: `tests/load_gs.js`
- Create: `tests/test_harness_selftest.js`

**Interfaces:**
- Produces: `makeGasEnv(options)` → `{ globals, state }` where `state.spreadsheets` (id → in-memory spreadsheet), `state.emails` (array of captured `{to, subject, body}`), `state.logs` (Logger lines). `loadGs(files, globals)` concatenates .gs files and evaluates them inside the stub env, returning the env's global scope so tests can call any top-level function.
- In-memory sheet API must support (used by the Provo agents): `SpreadsheetApp.create(name)`, `.openById(id)`, `.getActiveSpreadsheet()`, spreadsheet `.getId() .getName() .getSheetByName() .insertSheet(name) .getSheets()`, sheet `.getName() .getLastRow() .getLastColumn() .getDataRange() .getRange(r,c[,nr,nc]) .appendRow(arr) .setFrozenRows(n) .clear() .clearContents() .deleteRow(n) .getMaxColumns() .getMaxRows()`, range `.getValues() .setValues() .getValue() .setValue() .setFontWeight() .setBackground() .setFontColor()`.
- Also stub: `Logger.log`, `Utilities.sleep` (no-op), `Utilities.formatDate(date, tz, fmt)` (implement `yyyy-MM-dd`, `EEEE`, `MMMM d, yyyy`, `h:mm a` at minimum, honoring an IANA tz via `Intl.DateTimeFormat`), `PropertiesService` (in-memory script properties), `ScriptApp` (`newTrigger` chain → records into `state.triggers`, `getProjectTriggers`, `deleteTrigger`), `Session.getScriptTimeZone()` → `'America/Santiago'`, `MailApp.sendEmail` + `GmailApp.sendEmail` → push to `state.emails`, `UrlFetchApp.fetch` → returns `options.geminiResponse` or throws (so tests exercise the no-Gemini fallback), `SpreadsheetApp.flush` (no-op), `HtmlService` minimal.
- **Critical stub behavior (dropped-writes modeling):** `openById` must return a view over the true stored state (fresh object each call), matching how the form-builder tests correctly modeled server flush semantics.

- [ ] **Step 1: Write the self-test first**

`tests/test_harness_selftest.js`:
```js
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const assert = require('assert');

const env = makeGasEnv();
const g = env.globals;

// spreadsheet round-trip
const ss = g.SpreadsheetApp.create('T');
const sh = ss.insertSheet('TAB1');
sh.appendRow(['A', 'B']);
sh.getRange(2, 1, 1, 2).setValues([[1, 2]]);
assert.strictEqual(sh.getLastRow(), 2);
assert.deepStrictEqual(sh.getDataRange().getValues(), [['A', 'B'], [1, 2]]);
// openById returns fresh true state
assert.deepStrictEqual(
  g.SpreadsheetApp.openById(ss.getId()).getSheetByName('TAB1').getDataRange().getValues(),
  [['A', 'B'], [1, 2]]);
// email capture
g.MailApp.sendEmail({ to: 'x@y.z', subject: 's', htmlBody: '<b>hi</b>' });
assert.strictEqual(env.state.emails.length, 1);
// formatDate honors tz + pattern
const d = new Date('2026-07-11T03:00:00Z'); // 2026-07-10 23:00 in Santiago (UTC-4)
assert.strictEqual(g.Utilities.formatDate(d, 'America/Santiago', 'yyyy-MM-dd'), '2026-07-10');
// loadGs evaluates a .gs snippet
const fs = require('fs'); const os = require('os'); const path = require('path');
const tmp = path.join(os.tmpdir(), 'snippet.gs');
fs.writeFileSync(tmp, 'function addOne(n) { return n + 1; }');
const scope = loadGs([tmp], g);
assert.strictEqual(scope.addOne(41), 42);
console.log('harness selftest OK');
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/test_harness_selftest.js`
Expected: FAIL — `Cannot find module './gas_stubs'`

- [ ] **Step 3: Implement `tests/gas_stubs.js` and `tests/load_gs.js`**

Implementation notes (write the real code, this is the shape):
```js
// gas_stubs.js — in-memory GAS environment. No npm deps.
function makeGasEnv(options = {}) {
  const state = { spreadsheets: {}, emails: [], logs: [], triggers: [], props: {} };
  // ...Sheet/Range classes backed by a 2-D array per sheet, auto-growing on
  // setValues/appendRow; getDataRange trims to lastRow/lastCol...
  // SpreadsheetApp.openById(id) => new Spreadsheet wrapper over state.spreadsheets[id]
  // (fresh wrapper each call — models server flush).
  const globals = { SpreadsheetApp, Logger, Utilities, PropertiesService,
                    ScriptApp, Session, MailApp, GmailApp, UrlFetchApp, HtmlService };
  return { globals, state };
}
module.exports = { makeGasEnv };
```
```js
// load_gs.js — concatenate .gs files and eval them in a shared scope with the stubs.
const fs = require('fs');
function loadGs(files, globals) {
  const src = files.map(f => fs.readFileSync(f, 'utf8')).join('\n;\n');
  const names = Object.keys(globals);
  const fn = new Function(...names, src + '\n;return (function(){ return eval("({" + __exports__() + "})"); })();');
  // Simpler reliable approach: wrap src, then extract declared functions via
  // a second pass: run `src + '; return { fnA: typeof fnA!=="undefined"?fnA:undefined, ... }'`
  // by scanning src for /^function\s+([A-Za-z0-9_]+)/gm and building the return object.
  const fnNames = [...src.matchAll(/^function\s+([A-Za-z0-9_$]+)/gm)].map(m => m[1]);
  const varNames = [...src.matchAll(/^var\s+([A-Za-z0-9_$]+)/gm)].map(m => m[1]);
  const returner = '\n;return {' + [...fnNames, ...varNames].map(n => n + ':' + n).join(',') + '};';
  return new Function(...names, src + returner)(...names.map(n => globals[n]));
}
module.exports = { loadGs };
```

- [ ] **Step 4: Run self-test to verify it passes**

Run: `node tests/test_harness_selftest.js`
Expected: `harness selftest OK`

- [ ] **Step 5: Smoke-load a real Provo file (read-only) to prove the harness handles production code**

Add to the end of `test_harness_selftest.js`, then re-run:
```js
const scope2 = loadGs(['C:/Users/2011794-MTS/Desktop/PMG-Compass/docs/Agent3.gs'], makeGasEnv().globals);
assert.strictEqual(typeof scope2.a3_normHeader, 'function');
assert.strictEqual(scope2.a3_normHeader("  What's  UP "), 'whats up');
console.log('provo smoke-load OK');
```
Expected: both OK lines. (Loading only — never editing the Provo file.)

- [ ] **Step 6: Commit**

```bash
git add tests/ && git commit -m "test: node GAS-stub harness for .gs agent logic"
```

---

### Task 2: CCSM data module — `CcsmData.gs` (metric map, org rows, config rows)

Single shared data file used by both the sheet builder and (as documentation) the agents. Keeping data separate from builder logic means mission #3 swaps one file.

**Files:**
- Create: `CcsmData.gs`
- Create: `tests/test_ccsm_data.js`
- Create: `tools/emit_mission_org.py` (one-off generator)

**Interfaces:**
- Produces (globals in `CcsmData.gs`):
  - `var CCSM_ZONES = {...}` — copied **verbatim** from `WeeklyReportForm.gs:42-53` (`ZONES`).
  - `var CCSM_NIGHTLY_QUESTIONS = [ {key, headerEs, type, displayEs, order}, ... ]` — the daily metric map (table below).
  - `var CCSM_WEEKLY_QUESTIONS = [ ... ]` — same shape for the weekly form (intro + `_real`/`_meta` KI pairs).
  - `var CCSM_FORM_STRUCTURAL = { zoneCol: '¿En qué zona sirve?', areaCol: '¿En qué área sirve?', dateCol: '¿Qué fecha está ingresando?', effortChoices: ['Todo', 'La mayor parte', 'Algo'] }`
  - `var CCSM_AGENT_CONFIG_ROWS = [ [key, value], ... ]`
  - `var CCSM_MISSION_ORG_HEADERS = [...]` and `var CCSM_MISSION_ORG_ROWS = [ [...], ... ]` (generated by the python tool).
  - `var CCSM_TAB_SPECS = [ {name, headers|null, prefill|null}, ... ]` — null headers = created empty (agent self-initializes).

**The daily metric map (exact content for `CCSM_NIGHTLY_QUESTIONS`):** keys/headers from the spec — `report_date`/'¿Qué fecha está ingresando?'/DATE, `exchanges`/'¿Participó en uno o más intercambios?'/YESNO, `roleplays`/'Prácticas de enseñanza realizadas hoy', `contacts_attempted`/'Intentos de contacto con amigos', `contacts_made`/'Contactos con amigos', `meaningful_conversations`/'Conversaciones significativas con amigos', `new_people_found`/'Nuevas personas encontradas', `friend_lessons`/'Lecciones con amigos', `pmf_lessons`/'Lecciones con familias en las que no todos son miembros', `rc_lessons`/'Lecciones con conversos recientes', `rc_lessons_mcp`/'Lecciones con conversos recientes usando Mi Senda de los Convenios', `friend_texts`/'Mensajes de texto enviados a amigos', `friend_calls`/'Llamadas telefónicas a amigos', `member_contacts`/'Contactos realizados con miembros del barrio', `lessons_member_present`/'Lecciones con un miembro presente', `references_asked`/'Referencias solicitadas', `member_referrals_received`/'Referencias de miembros recibidas hoy', `bom_shared`/'Copias del Libro de Mormón entregadas', `church_invites`/'Invitaciones a la Iglesia extendidas', `baptism_doctrine_lessons`/'Lecciones en las que se enseñó la doctrina del bautismo', `baptismal_invitations`/'Invitaciones al bautismo extendidas', `baptismal_calendars`/'Calendarios bautismales entregados' (all NUMBER), `effort`/'¿Dio todo, la mayor parte o algo de esfuerzo en el altar del sacrificio hoy?'/CHOICE.

**Weekly:** `report_date` (same date question), `leader_call`/'¿Recibió una llamada de sus líderes?'/YESNO, `correlation_meeting`/'¿Usted y sus líderes locales realizaron una reunión de coordinación semanal?'/YESNO, then for each KI base (`ki_new_people`/'Nuevas personas encontradas', `ki_member_lessons`/'Lecciones con miembros', `ki_friends_sacrament`/'Amigos en la reunión sacramental', `ki_friends_first_week`/'Amigos en la Iglesia durante su primera semana de enseñanza', `ki_baptismal_date`/'Amigos con fecha bautismal', `ki_baptized_confirmed`/'Bautizados y confirmados', `ki_rc_at_church`/'Conversos recientes en la Iglesia') two entries: `<base>_real` with header `<title> (Real)` and `<base>_meta` with header `<title> (Meta)`.

**`CCSM_AGENT_CONFIG_ROWS` exact content:** the spec's AGENT_CONFIG table, PLUS rate-target keys `CONTACT_RATE_TARGET=0.50`, `MC_RATE_TARGET=0.50`, `LESSON_RATE_TARGET=0.20`, `CLOSE_RATE_TARGET=0.25`, `EFFORT_SCORE_TARGET=2.75`, `TRANSFER_START_DATE=` (blank), and one `GOAL_<metric_key>=` blank row per numeric daily metric (Agent2 reads `GOAL_{key}`).

**MISSION_ORG headers (verified against live agent accessors — `Companion1_Email` etc. per Agent3.gs:641, AgentReminder.gs:509):**
`Area_Code | Area_Name | Zone | District | Companion1_Name | Companion1_Email | Companion2_Name | Companion2_Email | Is_DL | Is_ZL | Is_STL | Is_AP | Is_MP | Active`

- [ ] **Step 1: Reconcile MISSION_ORG headers against every forked agent's accessors (do this before writing data)**

Run: `cd "C:/Users/2011794-MTS/Desktop/PMG-Compass/docs" && grep -hoE "(areaObj|obj|o|a|areaRow)\['[A-Za-z_0-9]+'\]" Agent1A.gs Agent1B.gs Agent1C.gs Agent2.gs Agent3.gs Agent4.gs Agent5A.gs Agent5B.gs Agent6.gs AgentDuplicate.gs AgentEscalation.gs AgentQA.gs AgentReminder.gs AgentScores.gs AgentValidation.gs AgentTestMode.gs Helpers.gs | sort -u`
Also: `grep -hoE "indexOf\('[A-Za-z_0-9]+'\)" <same files> | sort -u`
Expected: every org-related field name appears in the header list above; if a new one appears (e.g. `Phone`), add it to `CCSM_MISSION_ORG_HEADERS` and note it in the task summary.

- [ ] **Step 2: Write `tools/emit_mission_org.py`**

```python
"""One-off: parse the IMOS CurrentOrganization export into CCSM_MISSION_ORG_ROWS
JS literal, printed to stdout for pasting into CcsmData.gs. No data leaves the machine."""
import pandas as pd, json, sys, unicodedata

SRC = r"C:\Users\2011794-MTS\Downloads\CurrentOrganization-Excel (3).xls"
raw = pd.read_excel(SRC, header=None)
hdr = raw.index[raw.apply(lambda r: (r == 'Zone').any(), axis=1)][0]
df = pd.read_excel(SRC, header=hdr)
df.columns = [str(c).strip() for c in df.columns]
df = df.dropna(subset=['Area'])
df['Position'] = df['Position'].fillna('')

rows, code = [], 0
for (zone, district, area), g in df.groupby(['Zone', 'District', 'Area'], sort=True):
    code += 1
    names = list(g['Name'].fillna(''))
    pos = ' '.join(g['Position'])
    flag = lambda *codes: 'TRUE' if any(c in pos for c in codes) else 'FALSE'
    rows.append([
        'A%03d' % code, str(area).strip(), str(zone).strip(), str(district).strip(),
        names[0] if len(names) > 0 else '', '',          # Companion1_Name, blank email
        names[1] if len(names) > 1 else '', '',          # Companion2_Name, blank email
        flag('(DL)'), flag('(ZL1)', '(ZL2)'), flag('(STL1)', '(STL2)', '(STLT)'),
        flag('(AP)'), 'FALSE', 'TRUE',
    ])
print('var CCSM_MISSION_ORG_ROWS = ' + json.dumps(rows, ensure_ascii=False, indent=1) + ';')
print('// rows: %d' % len(rows), file=sys.stderr)
```

- [ ] **Step 3: Run it and sanity-check**

Run: `python tools/emit_mission_org.py > /tmp/org_rows.js` (use the scratchpad dir on Windows)
Expected on stderr: `// rows: ~101` (must be within ±3 of 101; if not, inspect the groupby — some areas have 3 missionaries (trios): put the third name appended to Companion2_Name with ` / ` separator — adjust the script if trios exist).
Verify: every Area_Name in the output exists in `CCSM_ZONES` (write a 5-line python check comparing sets; area names in the export may have stray spaces — `.strip()` both sides). Fix mismatches by normalizing, not by editing `CCSM_ZONES` (the forms are already live with those values).

- [ ] **Step 4: Write the failing data test**

`tests/test_ccsm_data.js`:
```js
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const assert = require('assert');
const g = makeGasEnv().globals;
const d = loadGs(['CcsmData.gs'], g);

// zones match the live form builders exactly
const wf = loadGs(['WeeklyReportForm.gs'], makeGasEnv().globals);
assert.deepStrictEqual(d.CCSM_ZONES, wf.ZONES, 'CCSM_ZONES must equal the form ZONES verbatim');

// nightly questions: 23 entries, exactly one DATE / one YESNO / one CHOICE / 20 NUMBER
const byType = t => d.CCSM_NIGHTLY_QUESTIONS.filter(q => q.type === t).length;
assert.strictEqual(d.CCSM_NIGHTLY_QUESTIONS.length, 23);
assert.deepStrictEqual([byType('DATE'), byType('YESNO'), byType('CHOICE'), byType('NUMBER')], [1, 1, 1, 20]);

// nightly headers match the ES daily form titles verbatim
const df = loadGs(['DailyReportForm_ES.gs'], makeGasEnv().globals);
const formTitles = df.QUESTIONS.map(q => q.title);
d.CCSM_NIGHTLY_QUESTIONS.forEach(q =>
  assert.ok(formTitles.includes(q.headerEs), 'missing in ES form: ' + q.headerEs));

// weekly: 3 intro + 14 KI entries; every KI base has _real and _meta
assert.strictEqual(d.CCSM_WEEKLY_QUESTIONS.length, 17);
const kis = d.CCSM_WEEKLY_QUESTIONS.filter(q => q.key.startsWith('ki_'));
assert.strictEqual(kis.length, 14);
kis.forEach(q => assert.ok(/_(real|meta)$/.test(q.key), q.key));
kis.forEach(q => assert.ok(/ \((Real|Meta)\)$/.test(q.headerEs), q.headerEs));

// mission org: headers + ~101 rows, all areas in zones, emails blank
assert.deepStrictEqual(d.CCSM_MISSION_ORG_HEADERS,
  ['Area_Code','Area_Name','Zone','District','Companion1_Name','Companion1_Email',
   'Companion2_Name','Companion2_Email','Is_DL','Is_ZL','Is_STL','Is_AP','Is_MP','Active']);
const allAreas = Object.values(d.CCSM_ZONES).flat();
d.CCSM_MISSION_ORG_ROWS.forEach(r => {
  assert.ok(allAreas.includes(r[1]), 'org area not in ZONES: ' + r[1]);
  assert.strictEqual(r[5], ''); assert.strictEqual(r[7], '');   // emails blank
  assert.strictEqual(r[13], 'TRUE');
});
assert.ok(d.CCSM_MISSION_ORG_ROWS.length >= 98 && d.CCSM_MISSION_ORG_ROWS.length <= 104);
// leadership flags present: at least 2 AP=false? APs live in an office area — expect >=15 DL, >=8 ZL rows
assert.ok(d.CCSM_MISSION_ORG_ROWS.filter(r => r[8] === 'TRUE').length >= 15, 'DL flags missing');

// config rows include the required keys with required defaults
const cfg = Object.fromEntries(d.CCSM_AGENT_CONFIG_ROWS);
assert.strictEqual(cfg.TEST_MODE, 'TRUE');
assert.strictEqual(cfg.MISSION_TIMEZONE, 'America/Santiago');
assert.strictEqual(cfg.MISSION_LANGUAGE, 'ES');
assert.strictEqual(cfg.MISSION_NAME, 'Chile Concepción South Mission');
assert.ok('GOAL_new_people_found' in cfg && 'GOAL_baptismal_invitations' in cfg);
console.log('ccsm data OK');
```

- [ ] **Step 5: Run to verify it fails** — `node tests/test_ccsm_data.js` → FAIL (`CcsmData.gs` missing)

- [ ] **Step 6: Write `CcsmData.gs`** with all globals above; paste the generated `CCSM_MISSION_ORG_ROWS`; copy `CCSM_ZONES` verbatim from `WeeklyReportForm.gs`. Include `CCSM_TAB_SPECS`:

```js
var CCSM_TAB_SPECS = [
  // {name, headers: [..] or null (empty tab — agent writes its own), prefillVar: name of data var or null}
  { name: 'MISSION_ORG',       headers: CCSM_MISSION_ORG_HEADERS, prefill: 'CCSM_MISSION_ORG_ROWS' },
  { name: 'AGENT_CONFIG',      headers: ['Key', 'Value'],         prefill: 'CCSM_AGENT_CONFIG_ROWS' },
  { name: 'QUESTIONS_CONFIG',  headers: ['Question_ID','Form_Type','Form_Column_Header','Metric_Key','Metric_Display_Name','Data_Type','Include_In_Daily_Log','Include_In_Live_Snapshot','Include_In_Weekly_Breakdown','Display_Order','Active'], prefill: 'derived' },
  { name: 'GOALS_CONFIG',      headers: ['Area_Code','Area_Name','Metric_Key','Goal_Value'], prefill: null },
  { name: 'SCORE_CONFIG',      headers: null, prefill: null },   // seeded by CCSM_AgentScores setup fn (Task 12)
  { name: 'MESSAGE_BANK',      headers: ['Message_ID','Category','Metric','Subcategory','Subject_Line','Body_Text','PMG_Page','PMG_Description','Scripture','Scripture_Text','Active'], prefill: null }, // content in Task 13
  { name: 'KNOWLEDGE_BASE',    headers: ['Entry_ID','Category','Question_Pattern','Answer_Text','Source','Language','Added_By','Active'], prefill: null },
  { name: 'TRANSFER_SCHEDULE', headers: ['Transfer_Number','Start_Date','End_Date','Type'], prefill: null },
  { name: 'DAILY_LOG',         headers: null, prefill: null },
  { name: 'LIVE_SNAPSHOT',     headers: null, prefill: null },
  { name: 'WEEKLY_KI',         headers: null, prefill: null },
  { name: 'DASHBOARD_SUMMARY', headers: null, prefill: null },
  { name: 'WEEKLY_BREAKDOWNS', headers: null, prefill: null },
  { name: 'SCORES',            headers: null, prefill: null },
  { name: 'GOAL_RECALIBRATION',headers: null, prefill: null },
  { name: 'AGENT_RUN_LOG',     headers: ['Timestamp','Agent','Status','Records_Processed','Emails_Sent','Duration_ms','Notes','Error'], prefill: null },
  { name: 'AUDIT_LOG',         headers: null, prefill: null },
  { name: 'MISSING_LOG',       headers: null, prefill: null },
  { name: 'FEEDBACK_HISTORY',  headers: ['Area_Code','Last_Message_IDs','Last_Sent_Date','Last_Growth_Metric'], prefill: null },
  { name: 'ENCOURAGEMENT_HISTORY', headers: null, prefill: null },
  { name: 'SUGGESTIONS',       headers: null, prefill: null },
  { name: 'SUGGESTIONS_REVIEW',headers: null, prefill: null },
  { name: 'NOTES',             headers: ['Note_ID','Area_Code','Area_Name','Author_Email','Note_Text','Created_At','Reminder_DateTime','Reminder_Sent','Resolved','Resolved_At'], prefill: null }
];
```
**Implementation caution:** before finalizing each `headers:` list above, verify it against the forked agent that reads/writes that tab (grep the Provo file for the tab name and read the surrounding code). Where the Provo agent writes its own header (like `a3_updateDailyLog`), keep `headers: null`. Where an agent requires pre-existing headers (KNOWLEDGE_BASE, FEEDBACK_HISTORY, NOTES, AGENT_RUN_LOG, MESSAGE_BANK, QUESTIONS_CONFIG, GOALS_CONFIG, AGENT_CONFIG, MISSION_ORG, TRANSFER_SCHEDULE), the list here must match that agent's `indexOf('...')` calls exactly — adjust this spec to the code, never the reverse, and record any change in the commit message.

- [ ] **Step 7: Run test to verify it passes** — `node tests/test_ccsm_data.js` → `ccsm data OK`

- [ ] **Step 8: Commit**

```bash
git add CcsmData.gs tools/ tests/test_ccsm_data.js
git commit -m "feat: CCSM data module — metric map, org rows, config, tab specs"
```

---

### Task 3: `BuildCcsmSheet.gs` — builder + reopen-verify pass

**Files:**
- Create: `BuildCcsmSheet.gs`
- Test: `tests/test_build_sheet.js`

**Interfaces:**
- Consumes: all `CCSM_*` globals from `CcsmData.gs` (in Apps Script, both files are pasted into one standalone project, so globals are shared).
- Produces: `buildCcsmSheet()` (entry point; logs the new sheet URL), `ccsmExpectedState_()` (returns `{tabName: [[row1],[row2],...]}` expected cell state), `verifyCcsmSheet_(spreadsheetId)` (reopen-compare-fix loop, max 20 rounds, logs fixes per round, returns `true` when clean).

- [ ] **Step 1: Write the failing test**

`tests/test_build_sheet.js`:
```js
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const assert = require('assert');

const env = makeGasEnv();
const s = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs'], env.globals);
s.buildCcsmSheet();

const id = Object.keys(env.state.spreadsheets)[0];
const ss = env.globals.SpreadsheetApp.openById(id);

// every tab exists, default 'Sheet1' removed
const specs = s.CCSM_TAB_SPECS;
specs.forEach(t => assert.ok(ss.getSheetByName(t.name), 'missing tab ' + t.name));
assert.strictEqual(ss.getSheets().length, specs.length);

// header rows written where specified; empty tabs truly empty
const cfg = ss.getSheetByName('AGENT_CONFIG').getDataRange().getValues();
assert.deepStrictEqual(cfg[0], ['Key', 'Value']);
assert.ok(cfg.some(r => r[0] === 'MISSION_TIMEZONE' && r[1] === 'America/Santiago'));
assert.strictEqual(ss.getSheetByName('DAILY_LOG').getLastRow(), 0);

// MISSION_ORG fully populated
const org = ss.getSheetByName('MISSION_ORG').getDataRange().getValues();
assert.strictEqual(org.length - 1, s.CCSM_MISSION_ORG_ROWS.length);

// QUESTIONS_CONFIG: one row per nightly+weekly question, Form_Column_Header verbatim ES
const qc = ss.getSheetByName('QUESTIONS_CONFIG').getDataRange().getValues();
const qcHeaders = qc[0];
const colHdr = qcHeaders.indexOf('Form_Column_Header');
const colType = qcHeaders.indexOf('Form_Type');
assert.strictEqual(qc.length - 1, s.CCSM_NIGHTLY_QUESTIONS.length + s.CCSM_WEEKLY_QUESTIONS.length);
assert.ok(qc.some(r => r[colHdr] === 'Prácticas de enseñanza realizadas hoy' && r[colType] === 'NIGHTLY'));
assert.ok(qc.some(r => r[colHdr] === 'Nuevas personas encontradas (Meta)' && r[colType] === 'WEEKLY'));

// verify pass reports clean
assert.strictEqual(s.verifyCcsmSheet_(id), true);
console.log('build sheet OK');
```

- [ ] **Step 2: Run to verify it fails** — `node tests/test_build_sheet.js` → FAIL

- [ ] **Step 3: Implement `BuildCcsmSheet.gs`**

Structure (follow the form builders' conventions — header comment with HOW TO USE, then data-driven build):
```js
function buildCcsmSheet() {
  var ss = SpreadsheetApp.create('COMPASS_CCSM');
  CCSM_TAB_SPECS.forEach(function(spec) {
    var sh = ss.insertSheet(spec.name);
    if (spec.headers) {
      sh.getRange(1, 1, 1, spec.headers.length).setValues([spec.headers]);
      sh.getRange(1, 1, 1, spec.headers.length).setFontWeight('bold').setBackground('#173A72').setFontColor('#FFFFFF');
      sh.setFrozenRows(1);
    }
    var rows = ccsmPrefillRows_(spec);
    if (rows && rows.length) sh.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  });
  // remove the default sheet LAST (a spreadsheet can never have zero sheets)
  var def = ss.getSheetByName('Sheet1') || ss.getSheetByName('Hoja 1');
  if (def) ss.deleteSheet(def);   // stub must support deleteSheet — add to harness if missing
  SpreadsheetApp.flush();
  var ok = verifyCcsmSheet_(ss.getId());
  Logger.log('COMPASS_CCSM created: ' + ss.getUrl());
  Logger.log(ok ? 'VERIFY: all tabs & headers correct.' : 'VERIFY WARNING: see fix log above.');
  Logger.log('NEXT STEPS: (1) attach the ES daily form → rename its new tab to NIGHTLY_FORM_RAW; ' +
             '(2) attach the ES weekly form → rename to WEEKLY_FORM_RAW; ' +
             '(3) fill AGENT_CONFIG blanks (SYSTEM_START_DATE, form links, GEMINI key via Script Properties); ' +
             '(4) create the bound Apps Script project and paste the CCSM_*.gs files (Helpers first).');
}

function ccsmPrefillRows_(spec) {
  if (spec.prefill === 'CCSM_MISSION_ORG_ROWS') return CCSM_MISSION_ORG_ROWS;
  if (spec.prefill === 'CCSM_AGENT_CONFIG_ROWS') return CCSM_AGENT_CONFIG_ROWS;
  if (spec.name === 'QUESTIONS_CONFIG') return ccsmQuestionsConfigRows_();
  return null;
}

function ccsmQuestionsConfigRows_() {
  var rows = [], n = 0;
  CCSM_NIGHTLY_QUESTIONS.forEach(function(q) {
    n++;
    rows.push(['Q-N-' + ('00' + n).slice(-3), 'NIGHTLY', q.headerEs, q.key, q.displayEs,
               q.type, 'TRUE', 'TRUE', 'TRUE', q.order, 'TRUE']);
  });
  var w = 0;
  CCSM_WEEKLY_QUESTIONS.forEach(function(q) {
    w++;
    rows.push(['Q-W-' + ('00' + w).slice(-3), 'WEEKLY', q.headerEs, q.key, q.displayEs,
               q.type, 'FALSE', 'FALSE', 'TRUE', q.order, 'TRUE']);
  });
  return rows;
}

function ccsmExpectedState_() { /* build {tabName: rows} from the same data the builder used */ }

function verifyCcsmSheet_(spreadsheetId) {
  var expected = ccsmExpectedState_();
  for (var round = 1; round <= 20; round++) {
    var ss = SpreadsheetApp.openById(spreadsheetId);   // FRESH open — true server state
    var fixes = 0;
    Object.keys(expected).forEach(function(tabName) {
      var sh = ss.getSheetByName(tabName);
      if (!sh) { ss.insertSheet(tabName); fixes++; return; }
      var want = expected[tabName];
      if (!want.length) return;
      var got = sh.getLastRow() > 0 ? sh.getRange(1, 1, want.length, want[0].length).getValues() : [];
      for (var r = 0; r < want.length; r++) {
        for (var c = 0; c < want[r].length; c++) {
          var g = got[r] ? String(got[r][c]) : '';
          if (g !== String(want[r][c])) { sh.getRange(r + 1, c + 1).setValue(want[r][c]); fixes++; }
        }
      }
    });
    Logger.log('Verify round ' + round + ': applied ' + fixes + ' fix(es)');
    if (fixes === 0) return true;
    SpreadsheetApp.flush();
  }
  return false;
}
```
Add `deleteSheet` + `getUrl` to the harness stubs if the self-test doesn't cover them yet.

- [ ] **Step 4: Run to verify it passes** — `node tests/test_build_sheet.js` → `build sheet OK`

- [ ] **Step 5: Dropped-writes resilience test** — add to the same test file a second run using `makeGasEnv({ dropWriteRate: 0.4 })` (harness option: `setValue`/`setValues` silently no-op at that rate on the FIRST attempt, honest afterwards — implement in stubs if missing), assert `verifyCcsmSheet_` still returns `true` and final state matches expected. Run 10 iterations in a loop. Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add BuildCcsmSheet.gs tests/test_build_sheet.js tests/gas_stubs.js
git commit -m "feat: BuildCcsmSheet builder with reopen-verify-fix pass"
```

---

### Task 4: `CCSM_Helpers.gs` — shared library fork

**Files:**
- Create: `CCSM_Helpers.gs` (fork of `PMG-Compass/docs/Helpers.gs`, 765 lines)
- Test: `tests/test_ccsm_helpers.js`
- Create: `tests/fixtures.js` (shared fixture factory — used by all later agent tests)

**Interfaces:**
- Produces: everything Helpers.gs exports (`getSpreadsheet, getTab, getTabData, getTabHeaders, appendRow, overwriteTab, readAgentConfig, getConfig, sendEmail, callGemini, getMessageBank, pickMessage, checkNoRepeat, recordMessageSent, scheduleNext, deleteTriggerByName, saveTempData, loadTempData, logRun, getHeaders_, col_`) plus new globals `MISSION_NAME`, `MISSION_LANGUAGE`, `MISSION_TIMEZONE` (lazy getters `getMissionName()`, `getMissionTimezone()` — module-level `var` caching is fine since GAS resets globals per run).
- Produces (fixtures): `makeCcsmSpreadsheet(env, scope)` — builds an in-memory COMPASS_CCSM via `buildCcsmSheet()` and wires `SpreadsheetApp.getActiveSpreadsheet()` to it; `addNightlyRaw(env, ss, rows)` — creates `NIGHTLY_FORM_RAW` with the real ES multi-section header layout (Timestamp, zone col, then per zone: area col + date col + 21 metric questions in form order) and appends submission rows; `addWeeklyRaw(env, ss, rows)` — same for the weekly layout.

- [ ] **Step 1: Fork the file** — copy `Helpers.gs` → `CCSM_Helpers.gs`, then apply these changes:

| Location (Provo) | Change |
|---|---|
| Header comment | Rewrite title/notes for CCSM; keep the HARD RULE block verbatim |
| `getSpreadsheet()` | Keep `SpreadsheetApp.getActiveSpreadsheet()` (bound project) — no sheet ID constant |
| Near `SENDER_NAME` (~line 225) | `function getMissionName() { return getConfig('MISSION_NAME') || 'PMG Compass'; }`, `function getMissionTimezone() { return getConfig('MISSION_TIMEZONE') || 'America/Santiago'; }`, and `var SENDER_NAME` → computed `'PMG Compass — ' + getMissionName()` inside `sendEmail` (config isn't readable at parse time) |
| Every literal `'Utah Provo Mission'` | Replace with `getMissionName()` string concat (run `grep -n "Utah Provo" CCSM_Helpers.gs` → must return nothing) |
| Every `'America/Denver'` | `getMissionTimezone()` (grep must return nothing) |
| `sendEmail()` | Keep TEST_MODE redirect logic exactly as-is (it reads config) |
| `getMessageBank()` | Per the warning in `populateMessageBankStructure.gs`: change hardcoded column indices to header-name lookup via `getTabHeaders('MESSAGE_BANK')` |
| Relay functions (`testRelay`, RELAY_* use) | Keep — config-driven, blank config = disabled path; verify blank RELAY_1_URL doesn't throw at load time |

- [ ] **Step 2: Write the failing test**

`tests/test_ccsm_helpers.js`:
```js
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs'], env.globals);
makeCcsmSpreadsheet(env, scope);

assert.strictEqual(scope.getConfig('MISSION_TIMEZONE'), 'America/Santiago');
assert.strictEqual(scope.getMissionName(), 'Chile Concepción South Mission');

// TEST_MODE email redirect
scope.sendEmail('real.missionary@missionary.org', 'Asunto', '<p>hola</p>', 'TestAgent');
assert.strictEqual(env.state.emails.length, 1);
assert.strictEqual(env.state.emails[0].to, 'CCSM.PMG.Compass@gmail.com'); // TEST_MODE redirect
// After reading sendEmail's redirect branch, assert its real subject/prefix convention here
// with a concrete equality (NOT a tautology). Example if it prepends "[TEST] ":
// assert.ok(env.state.emails[0].subject.startsWith('[TEST]'));

// no Provo residue
const src = require('fs').readFileSync('CCSM_Helpers.gs', 'utf8');
assert.ok(!/Utah Provo/i.test(src));
assert.ok(!/America\/Denver/.test(src));
console.log('helpers OK');
```

- [ ] **Step 3: Run to verify it fails, implement fixtures.js, iterate until pass**

`tests/fixtures.js` must build `NIGHTLY_FORM_RAW` headers exactly as Google Forms will: column A `Marca temporal`, column B `¿En qué zona sirve?`, then for EACH of the 10 zones (in `Object.keys(CCSM_ZONES)` order): `¿En qué área sirve?`, `¿Qué fecha está ingresando?`, `¿Participó en uno o más intercambios?`, then the 20 numeric questions in `DailyReportForm_ES.gs` order, then the effort question. A submission row fills column A, column B, and only its zone's section columns. Weekly layout: `Marca temporal`, `¿En qué zona sirve?`, then per zone: area, date, 2 yes/no, 7 `(Real)`, 7 `(Meta)`.

Run: `node tests/test_ccsm_helpers.js` → `helpers OK`

- [ ] **Step 4: Commit** — `git add CCSM_Helpers.gs tests/ && git commit -m "feat: CCSM_Helpers — config-driven identity, header-based MESSAGE_BANK lookup"`

---

### Task 5: `CCSM_Agent3.gs` — nightly processing + missed-days alerts (the heart)

**Files:**
- Create: `CCSM_Agent3.gs` (fork of Agent3.gs, 1313 lines)
- Test: `tests/test_agent3.js`

**Interfaces:**
- Consumes: `CCSM_Helpers.gs` functions, fixtures.
- Produces: `runAgent3()`, `previewMissedDays()`, `setupAgent3Trigger()`, `setupAgent3EveningTrigger()` and all `a3_*` internals (names unchanged from Provo so future diffs stay readable).

- [ ] **Step 1: Fork and adapt.** Changes:

| Provo | CCSM |
|---|---|
| `A3_FORM_AREA_COL = 'What is your area?'` | `'¿En qué área sirve?'` |
| `A3_FORM_ZONE_COL = 'What zone are you in?'` | `'¿En qué zona sirve?'` |
| `A3_FORM_DATE_COL = 'What date are you inputting?'` | `'¿Qué fecha está ingresando?'` |
| `A3_FORM_BLITZ_COL` + all `is_blitz`/`Is_Blitz` logic | **Delete entirely** (no blitz question at CCSM). DAILY_LOG header therefore ends at the last metric — remove the `Is_Blitz` append & migration block in `a3_updateDailyLog` (Agent3.gs:439-443, 464, 474) |
| `a3_headerAlias()` aliases | Empty the alias map (`return null;`) — CCSM config headers are generated from the same source as the form, so no drift exists yet; keep the mechanism for future fixes |
| Effort/YESNO parsing in `a3_buildDailyRecords` | Numeric metrics parse as numbers (unchanged). `exchanges` (`Sí`/`No`) → store `'TRUE'`/`''`. `effort` (`Todo`/`La mayor parte`/`Algo`) → store the raw Spanish string in DAILY_LOG (agents that need a number map it: Todo=3, La mayor parte=2, Algo=1 — put `function ccsmEffortScore(v)` in CCSM_Helpers and use it in 1A/5B/Scores) |
| Missed-days email HTML (`a3_buildEscalationHtml`, `a3_buildMissedDaysHtml`, subject lines) | Full Spanish rewrite (Step 2 below) |
| `a3_loadMissedDayMessages()` | Reads MISSED_DAYS category from MESSAGE_BANK — works once Task 13 seeds Spanish rows; keep logic |
| Timezone in date helpers (`a3_toDateString` etc.) | `getMissionTimezone()` |
| `setupQuestionsConfig()` | **Delete** — builder owns QUESTIONS_CONFIG |
| Trigger times in `setupAgent3Trigger` comments/hours | Same clock hours (6 AM / 9 PM) — the bound project's timezone will be Santiago (set in Task 14), so `ScriptApp.newTrigger(...).atHour(21)` is already local |

- [ ] **Step 2: Spanish email templates (complete text — use exactly this):**

```js
function a3_buildEscalationHtml(areaName, dateList, count, formLink) {
  var items = dateList.map(function(d) { return '<li>' + a3_formatReadableDate(d) + '</li>'; }).join('');
  return '<div style="font-family: Arial, sans-serif; max-width: 600px;">' +
    '<h2 style="color:#173A72;">Alerta: Informes Nocturnos Faltantes</h2>' +
    '<p>Hola,</p>' +
    '<p>El área <strong>' + a3_escapeHtmlMail(areaName) + '</strong> no ha enviado su informe nocturno en ' +
    count + ' fecha(s):</p>' +
    '<ul>' + items + '</ul>' +
    '<p>Por favor, comuníquese con esta compañía para ayudarles a ponerse al día.</p>' +
    '<p><a href="' + formLink + '" style="background:#173A72;color:#fff;padding:10px 20px;' +
    'text-decoration:none;border-radius:4px;">Enviar Informe Nocturno</a></p>' +
    '<p style="color:#999;font-size:12px;">PMG Compass — ' + getMissionName() + '</p></div>';
}
```
Subject lines: missionary reminder `'Recordatorio: Informe Nocturno Pendiente — ' + areaName`; DL escalation `'Alerta de Informes Faltantes — ' + areaName`. For `a3_injectVars` templates, keep the `{AREA}`/`{DATES}`/`{LINK}` placeholder mechanism; the MISSED_DAYS MESSAGE_BANK rows (Task 13) carry the Spanish body text.

- [ ] **Step 3: Write the failing test** (`tests/test_agent3.js`):

```js
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_Agent3.gs'], env.globals);
const ss = makeCcsmSpreadsheet(env, scope);

// two submissions: one Arauco area (normal), one San Pedro area SAME area+date twice (must sum)
addNightlyRaw(env, ss, [
  { zone: 'Arauco', area: 'Arauco 1', date: '2026-07-10',
    metrics: { roleplays: 2, contacts_attempted: 15, contacts_made: 7, new_people_found: 1 },
    exchanges: 'Sí', effort: 'Todo' },
  { zone: 'San Pedro', area: 'San Pedro', date: '2026-07-10', metrics: { friend_lessons: 1 }, effort: 'Algo' },
  { zone: 'San Pedro', area: 'San Pedro', date: '2026-07-10', metrics: { friend_lessons: 2 }, effort: 'Algo' },
]);

scope.runAgent3();

const log = ss.getSheetByName('DAILY_LOG').getDataRange().getValues();
const h = log[0];
assert.deepStrictEqual(h.slice(0, 4), ['Date', 'Area', 'Zone', 'District']);
assert.ok(!h.includes('Is_Blitz'), 'blitz must be gone');
const row = a => log.find(r => r[1] === a);
assert.strictEqual(row('Arauco 1')[h.indexOf('roleplays')], 2);
assert.strictEqual(row('Arauco 1')[h.indexOf('exchanges')], 'TRUE');
assert.strictEqual(row('Arauco 1')[h.indexOf('effort')], 'Todo');
assert.strictEqual(row('San Pedro')[h.indexOf('friend_lessons')], 3, 'same-day rows must sum');

// LIVE_SNAPSHOT rebuilt with one row per active area
const snap = ss.getSheetByName('LIVE_SNAPSHOT').getDataRange().getValues();
assert.strictEqual(snap.length - 1, scope.CCSM_MISSION_ORG_ROWS.length);

// missed-days: with TEST_MODE, alert emails redirect to the test inbox and are Spanish
const alerts = env.state.emails.filter(e => /Informe/.test(e.subject));
alerts.forEach(e => assert.strictEqual(e.to, 'CCSM.PMG.Compass@gmail.com'));
console.log('agent3 OK');
```
Note: `runAgent3` gates on config dates (`SYSTEM_START_DATE`, `TRANSFER_START_DATE`) — the fixture must set both to `2026-07-01` in AGENT_CONFIG before running (add a `setConfig(env, ss, key, value)` helper to fixtures.js).

- [ ] **Step 4: Run → fail → implement → pass** — `node tests/test_agent3.js` → `agent3 OK`

- [ ] **Step 5: Residue scan + commit**

```bash
grep -n "Utah Provo\|America/Denver\|blitz\|Blitz\|What is your area" CCSM_Agent3.gs   # expect: no matches
git add CCSM_Agent3.gs tests/test_agent3.js tests/fixtures.js
git commit -m "feat: CCSM_Agent3 — Spanish nightly processing, no blitz, Spanish alerts"
```

---

### Task 6: `CCSM_Agent5A.gs` — dashboard summary + weekly KI from the weekly form

**Files:**
- Create: `CCSM_Agent5A.gs` (fork of Agent5A.gs, 742 lines)
- Test: `tests/test_agent5a.js`

**Interfaces:**
- Consumes: CCSM_Helpers, DAILY_LOG rows (Agent3 output shape), fixtures `addWeeklyRaw`.
- Produces: `runAgent5A()`, `setupAgent5ATrigger()`; `WEEKLY_KI` header: `Week_End_Date | Area | Zone | District |` then `ki_<base>_real` and `ki_<base>_meta` for the 7 bases (14 metric cols) `| leader_call | correlation_meeting`.

- [ ] **Step 1: Fork and adapt.**
  - `A5A_EFFORT_COL` → `'¿Dio todo, la mayor parte o algo de esfuerzo en el altar del sacrificio hoy?'`; effort breakdown maps `Todo`/`La mayor parte`/`Algo` via `ccsmEffortScore()`.
  - `DASHBOARD_SUMMARY` logic: unchanged apart from metric keys flowing from QUESTIONS_CONFIG.
  - **Replace `a5a_writeWeeklyKI(dailyLog, ...)` wholesale**: new implementation parses `WEEKLY_FORM_RAW` using the same section-structure technique as `a3_parseSectionStructure` (reuse it: area col `'¿En qué área sirve?'`, date col `'¿Qué fecha está ingresando?'`, metric headers from QUESTIONS_CONFIG WEEKLY rows — the `(Real)`/`(Meta)` suffixed titles). Week bucketing: `a5a_getWeekEnd(dateStr)` (keep — Sunday-ending weeks). One row per area per week-end; duplicate submissions for the same area+week: keep the LATEST by timestamp (goals/results are absolute values, not increments — do NOT sum). `Sí`/`No` → `TRUE`/`FALSE` for the two yes/no columns.
  - Timezone → `getMissionTimezone()`.

- [ ] **Step 2: Failing test** (`tests/test_agent5a.js`): fixture with two weekly submissions for `'Arauco 1'` in the same week (second one must win), one for `'Lota 1'`; assert WEEKLY_KI has 2 data rows, `ki_new_people_real` and `ki_new_people_meta` columns both present with the later submission's values, `leader_call === 'TRUE'`. Also seed DAILY_LOG via Agent3 fixture and assert DASHBOARD_SUMMARY is written (non-empty, contains a mission-total row). Follow the Task 5 test pattern exactly (same loadGs file list + `CCSM_Agent5A.gs`).

- [ ] **Step 3: Run → fail → implement → pass** — `node tests/test_agent5a.js`

- [ ] **Step 4: Commit** — `git commit -m "feat: CCSM_Agent5A — dashboard summary + WEEKLY_KI from weekly form (Real/Meta)"`

---

### Task 7: `CCSM_Agent1A.gs` + `CCSM_Agent1B.gs` — coaching data + message selection

**Files:**
- Create: `CCSM_Agent1A.gs` (fork, 576 lines), `CCSM_Agent1B.gs` (fork, 211 lines)
- Test: `tests/test_agent1ab.js`

**Interfaces:**
- Consumes: DAILY_LOG/WEEKLY_FORM_RAW/MESSAGE_BANK via CCSM_Helpers; `ccsmEffortScore`.
- Produces: `runAgent1A()` (saves week data to Script Properties, chains 1B), `runAgent1B()` (picks strength/growth messages, chains 1C). Rate-metric definitions (this is a **reviewed decision**, see spec):

```js
var A1A_RATE_METRICS = [
  { key: 'contact_rate', display: 'Tasa de Contacto', type: 'rate',
    configKey: 'CONTACT_RATE_TARGET', defaultTarget: 0.50, pmg: '157', scripture: 'D. y C. 4:4-5',
    num: 'contacts_made', den: 'contacts_attempted' },
  { key: 'mc_rate', display: 'Tasa de Conversaciones Significativas', type: 'rate',
    configKey: 'MC_RATE_TARGET', defaultTarget: 0.50, pmg: '85', scripture: 'D. y C. 11:21',
    num: 'meaningful_conversations', den: 'contacts_made' },
  { key: 'lesson_rate', display: 'Tasa de Lecciones', type: 'rate',
    configKey: 'LESSON_RATE_TARGET', defaultTarget: 0.20, pmg: '174', scripture: 'Alma 26:22',
    num: 'friend_lessons', den: 'contacts_attempted' },
  { key: 'close_rate', display: 'Tasa de Invitación Bautismal', type: 'rate',
    configKey: 'CLOSE_RATE_TARGET', defaultTarget: 0.25, pmg: '205', scripture: 'Moroni 10:4',
    num: 'baptismal_invitations', den: 'friend_lessons' },
  { key: 'effort_score', display: 'Nivel de Esfuerzo', type: 'rate',
    configKey: 'EFFORT_SCORE_TARGET', defaultTarget: 2.75, pmg: null, scripture: null }
];
```
(Provo's `nm_knocked_rate` is dropped — CCSM has no doors metric. Provo computes each rate in dedicated code around Agent1A.gs:261 — rewire the numerators/denominators to the `num`/`den` keys above.)

- [ ] **Step 1: Fork both files.** Header constants → Spanish (`A1A_FORM_AREA_COL = '¿En qué área sirve?'`, `A1A_FORM_DATE_COL = '¿Qué fecha está ingresando?'`, `A1A_EFFORT_COL =` effort ES title, `A1A_WEEKLY_AREA_COL = '¿En qué área sirve?'`, `A1A_WEEKLY_DATE_COL = '¿Qué fecha está ingresando?'`). Effort averaging uses `ccsmEffortScore`. Count metrics still load from QUESTIONS_CONFIG (`a1a_loadCountMetrics`) — verify it filters `Data_Type === 'NUMBER'` so `exchanges`/`effort` don't become count metrics; if Provo filters differently, add that filter.

- [ ] **Step 2: Failing test:** seed a week of DAILY_LOG (via Agent3 on fixture raw rows across Mon–Sun), run `runAgent1A()` then `runAgent1B()`; assert Script Properties contain per-area week data with `contact_rate` computed as `contacts_made/contacts_attempted` (check one known ratio), and 1B selects a strength + growth message per area from the seeded MESSAGE_BANK (Task 13 rows — for this test seed 2 minimal Spanish rows directly in the fixture), never generating text (assert chosen `Message_ID`s exist in the bank).

- [ ] **Step 3: Run → fail → implement → pass**, then **Step 4: Commit** — `git commit -m "feat: CCSM_Agent1A/1B — Spanish coaching metrics and message selection"`

---

### Task 8: `CCSM_Agent1C.gs` — coaching email assembly/sending

**Files:**
- Create: `CCSM_Agent1C.gs` (fork, 1651 lines — largest file; budget accordingly)
- Test: `tests/test_agent1c.js`

- [ ] **Step 1: Fork.** All email HTML structural text → Spanish, exact translations:
  - Subject: `'PMG Compass — Entrenamiento Semanal | ' + weekLabel`
  - `"Week ending {date}"` → `'Semana que termina el {date}'` (dates via `Utilities.formatDate(d, getMissionTimezone(), "d 'de' MMMM")` — verify GAS honors `es` month names via the sheet locale; if not, use a 12-entry Spanish month array)
  - `"💪 Strength — {metric}"` → `'💪 Fortaleza — {metric}'`
  - `"📈 Growth Focus — {metric}"` → `'📈 Área de Crecimiento — {metric}'`
  - `"Mission Summary"` → `'Resumen de la Misión'`; `"Zone Summary — {zone}"` → `'Resumen de Zona — {zone}'`; `"District Summary — {district}"` → `'Resumen de Distrito — {district}'`
  - `"View PMG Compass Dashboard"` → `'Ver el Panel de PMG Compass'`
  - Footer: `'PMG Compass — ' + getMissionName()`
  - Gemini leadership-narrative prompts: append `'\n\nIMPORTANTE: Escriba su respuesta en español.'` and replace mission-name references with `getMissionName()`
  - WEEKLY_BREAKDOWNS write: metric columns follow CCSM keys (flows from 1A data; verify header row written by 1C matches)

- [ ] **Step 2: Failing test:** run the full 1A→1B→1C chain on the Task 7 fixture with `geminiResponse` stubbed to a fixed narrative; assert ≥1 email captured, `to === 'CCSM.PMG.Compass@gmail.com'` (TEST_MODE), subject starts `'PMG Compass — Entrenamiento Semanal'`, body contains `'Fortaleza'` and `'Área de Crecimiento'` and NO English structural strings (`assert.ok(!/Growth Focus|Week ending|Mission Summary/.test(body))`), and WEEKLY_BREAKDOWNS gained one row per area.

- [ ] **Step 3: Run → fail → implement → pass**, **Step 4: Commit** — `git commit -m "feat: CCSM_Agent1C — Spanish coaching emails + weekly breakdowns"`

---

### Task 9: `CCSM_Agent5B.gs` + `CCSM_Agent6.gs` — Friday encouragement

**Files:**
- Create: `CCSM_Agent5B.gs` (fork, 463 lines), `CCSM_Agent6.gs` (fork, 352 lines)
- Test: `tests/test_agent5b6.js`

- [ ] **Step 1: Fork.** 5B: qualification reads DAILY_LOG (CCSM keys), goals from GOALS_CONFIG with `GOAL_*` config fallback; `'68 areas'` comments → dynamic (`missionOrg.length`). 6: email templates → Spanish. Complete template:
  - Subject: `'¡Buen trabajo, ' + areaName + '! 🎉'`
  - Greeting/body structure mirroring Provo but Spanish: `'¡Felicitaciones! Esta semana su área alcanzó el ' + pct + '% de su meta de ' + metricDisplay + '.'`; body text itself still comes from MESSAGE_BANK `FRIDAY_ENCOURAGEMENT` rows (never generated)
  - Footer `'PMG Compass — ' + getMissionName()`

- [ ] **Step 2: Failing test:** seed DAILY_LOG with an area that submitted Mon–Thu and beats 75% of a goal; run 5B then 6; assert one Spanish email captured (TEST_MODE inbox), and a non-qualifying area (missing Tuesday) gets nothing. Assert ENCOURAGEMENT_HISTORY gained a row.

- [ ] **Step 3: Run → fail → implement → pass**, **Step 4: Commit** — `git commit -m "feat: CCSM_Agent5B/6 — Friday encouragement in Spanish"`

---

### Task 10: `CCSM_AgentReminder.gs` + `CCSM_AgentDuplicate.gs` + `CCSM_AgentEscalation.gs`

**Files:**
- Create: `CCSM_AgentReminder.gs` (fork, 743), `CCSM_AgentDuplicate.gs` (fork, 368), `CCSM_AgentEscalation.gs` (fork, 1002)
- Test: `tests/test_agent_alerts.js`

- [ ] **Step 1: Fork all three.**
  - Reminder: weekly-form column lookups → `'¿En qué área sirve?'`; reminder email Spanish — subject `'Recordatorio: Informe Semanal — ' + getMissionName()`, body `'¡Hola! Este es su recordatorio para enviar el informe semanal de esta semana.'` + button `'Enviar Informe Ahora'` linking `getConfig('WEEKLY_FORM_LINK')`. NOTES-reminder half of the file: keep (Notes tab exists), Spanish subject `'Recordatorio de Nota — ' + areaName`.
  - Duplicate: works on raw tabs by header name — swap the area/date constants to the Spanish ones; dedup flag/audit text Spanish where user-visible, log text can stay English.
  - Escalation: `'America/Denver'` → `getMissionTimezone()` everywhere (grep!); DL/ZL escalation emails Spanish (mirror Task 5 template, subject `'Escalamiento: Informes Faltantes — ' + areaName`); `resolveTabName` TEST_MODE tab routing kept as-is.

- [ ] **Step 2: Failing test:** (a) duplicate detection — two identical nightly rows produce an AUDIT_LOG entry flagging the dup; (b) reminder — an area with no weekly submission since Sunday gets a Spanish reminder to the TEST inbox; an area that submitted gets nothing; (c) escalation — an area with ≥3 consecutive missed days triggers a DL email (Spanish subject).

- [ ] **Step 3: Run → fail → implement → pass**, **Step 4: Commit** — `git commit -m "feat: CCSM reminder/duplicate/escalation agents"`

---

### Task 11: `CCSM_Agent2.gs` + `CCSM_Agent4.gs` — recalibration + health check

**Files:**
- Create: `CCSM_Agent2.gs` (fork, 552), `CCSM_Agent4.gs` (fork, 1046)
- Test: `tests/test_agent2_4.js`

- [ ] **Step 1: Fork.**
  - Agent2: metric list from QUESTIONS_CONFIG (already dynamic); `GOAL_{key}` config reads work with the Task 2 config rows; TRANSFER_SCHEDULE tab exists (header from Task 2 — verify the exact header names Agent2 reads at `a2_loadTransferBoundaries` and align `CCSM_TAB_SPECS`, adjusting the builder if needed); GOAL_RECALIBRATION self-initializes.
  - Agent4: tab checklist (Agent4.gs:42) → the CCSM tab list from `CCSM_TAB_SPECS` names, MINUS Sister-Ellis/transfer-tooling tabs, PLUS `NIGHTLY_FORM_RAW`/`WEEKLY_FORM_RAW`; health email may stay functional-Spanish (subject `'PMG Compass — Informe de Salud del Sistema'`); remove Agent7/SISTER_ELLIS references (grep `-i "sister\|ellis\|agent7"` must return nothing).

- [ ] **Step 2: Failing test:** Agent2 — seed 2 transfers of DAILY_LOG history + `TRANSFER_START_DATE`, run, assert GOAL_RECALIBRATION rows contain `Suggested_Goal` numbers respecting the ×1.5 cap. Agent4 — run against the fixture sheet WITHOUT raw tabs attached; assert its report flags the two missing raw tabs and nothing else.

- [ ] **Step 3: Run → fail → implement → pass**, **Step 4: Commit** — `git commit -m "feat: CCSM_Agent2/4 — recalibration + health check"`

---

### Task 12: `CCSM_AgentScores.gs` + `CCSM_AgentQA.gs` + `CCSM_AgentValidation.gs` + `CCSM_AgentTestMode.gs`

**Files:**
- Create: `CCSM_AgentScores.gs` (fork, 1564), `CCSM_AgentQA.gs` (fork, 1282), `CCSM_AgentValidation.gs` (fork, 276), `CCSM_AgentTestMode.gs` (fork, 251)
- Test: `tests/test_agent_scores_qa.js`

- [ ] **Step 1: Fork.**
  - Scores: metric weights over CCSM keys. Add `setupCcsmScoreConfig()` that seeds SCORE_CONFIG (two-section Provo layout, `ALL` fallback row) with these defaults — Effort component: `contacts_attempted` 0.30, `roleplays` 0.20, `member_contacts` 0.20, `effort` 0.30; Skill component: `contact_rate` 0.30, `mc_rate` 0.25, `lesson_rate` 0.25, `close_rate` 0.20; KI component: equal weights over the 7 `ki_*_real` keys; sub-weights Effort/Skill/KI = 0.33/0.33/0.34. (User can retune in the sheet.) WEEKLY_KI reads use the Task 6 header shape.
  - QA: Gemini system prompt — prepend `'Responda siempre en español. Usted es PMG Compass, un asistente para la misión ' + getMissionName() + '. '`; KNOWLEDGE_BASE reads filter `Language === 'ES'` if the column exists (Task 2 header has it).
  - Validation/TestMode: mechanical fork; tab names updated; grep-verify no Provo residue.

- [ ] **Step 2: Failing test:** Scores — seed a week of DAILY_LOG + WEEKLY_KI, run `setupCcsmScoreConfig()` then `runAgentScores()` (use the Provo entry-point name), assert SCORES gains one row per area with all four score columns in [0, 100] (or Provo's actual scale — assert against whatever `AgentScores.gs` produces). QA — stub `geminiResponse` with a Message_ID-style answer; assert reply email is Spanish-prompted (inspect the captured UrlFetchApp request body for `'Responda siempre en español'`).

- [ ] **Step 3: Run → fail → implement → pass**, **Step 4: Commit** — `git commit -m "feat: CCSM scores/QA/validation/testmode agents"`

---

### Task 13: MESSAGE_BANK + KNOWLEDGE_BASE Spanish content — `CCSM_SeedContent.gs`

**Files:**
- Create: `CCSM_SeedContent.gs`
- Test: `tests/test_seed_content.js`

**Interfaces:**
- Produces: `seedCcsmMessageBank()` and `seedCcsmKnowledgeBase()` (run once in the bound project; safe to re-run — clears rows 2+ first, mirroring `populateMessageBankStructure.gs`). Categories consumed by agents: `SUNDAY_COACHING_STRENGTH`, `SUNDAY_COACHING_GROWTH` (per coaching metric: the 5 rate metrics of Task 7 + the 20 count metrics), `FRIDAY_ENCOURAGEMENT` (per count metric with goals), `MISSED_DAYS` (3 generic rows). **Verify the exact Category string values against `getMessageBank()`/Agent1B/5B code and use those.**

- [ ] **Step 1: Content matrix + write the messages.** Volume: strength + growth × (5 rate + 20 count metrics) × 3 variants = 150 rows; FRIDAY_ENCOURAGEMENT × 20 × 2 = 40; MISSED_DAYS 3. All Spanish, usted-form, warm and mission-focused; scripture references with Spanish LDS book names ('D. y C.', '1 Nefi', 'Moroni', 'Alma'); PMG references as 'Predicad Mi Evangelio, pág. N'. Two complete examples setting the tone — every other row follows this shape:

```js
['MSG-CS-ROLEPLAYS-01', 'SUNDAY_COACHING_STRENGTH', 'roleplays', '',
 '¡Su preparación se nota!',
 'Esta semana su área se destacó en las prácticas de enseñanza. El Señor honra la preparación diligente: ' +
 'cada práctica les acerca más a enseñar con el Espíritu. ¡Sigan así!',
 '175', 'Predicad Mi Evangelio, pág. 175 — La práctica mejora la enseñanza',
 'D. y C. 84:85', 'Atesorad continuamente en vuestra mente las palabras de vida.', 'TRUE'],
['MSG-CG-CONTACTS-01', 'SUNDAY_COACHING_GROWTH', 'contacts_attempted', '',
 'Una invitación: abran la boca',
 'Esta semana hubo menos intentos de contacto que de costumbre. Recuerden que cada persona es un hijo de Dios ' +
 'que espera escuchar el evangelio. Fijen una meta pequeña para mañana: cinco intentos más que hoy.',
 '156', 'Predicad Mi Evangelio, pág. 156 — Hablar con todos',
 'D. y C. 33:8-10', 'Abrid vuestra boca, y será llena.', 'TRUE'],
```
Writing the remaining ~190 rows is generative work for the implementer: keep every row to 2–4 sentences, no invented statistics, no promises of specific outcomes, correct names of Deity (Dios, Jesucristo, el Salvador, el Señor), and real scripture texts (quote the actual Spanish LDS edition wording; if unsure of exact wording leave `Scripture_Text` empty rather than paraphrasing). Batch-write 50 rows at a time with `Utilities.sleep(500)` between batches (Provo pattern).

KNOWLEDGE_BASE: 10 starter Spanish rows — how to submit the nightly/weekly form, what each KI means (7 rows, one per KI, drawn from the form help texts in `WeeklyReportForm_ES.gs`), who to contact (`CCSM.PMG.Compass@gmail.com`).

- [ ] **Step 2: Failing test** (`tests/test_seed_content.js`): run seeding against the fixture sheet; assert row counts per category match the matrix; every `Metric` value is a valid CCSM metric key or rate key; no row body matches `/[a-z]+ (the|your|this) /i` (English-leak heuristic); all `Active === 'TRUE'`; `Message_ID`s unique. Then assert `getMessageBank('SUNDAY_COACHING_STRENGTH', 'roleplays')` returns 3 rows.

- [ ] **Step 3: Run → fail → implement → pass**, **Step 4: Commit** — `git commit -m "feat: Spanish MESSAGE_BANK + KNOWLEDGE_BASE seed content"`
- [ ] **Step 5: Flag for human review** — add a `CONTENT_REVIEW.md` listing every message row in readable form for the user (and ideally a native speaker / mission leadership) to review before `TEST_MODE` is ever flipped. This is a launch gate, not optional.

---

### Task 14: `CCSM_Setup.gs` — triggers + smoke tests + full-pipeline test

**Files:**
- Create: `CCSM_Setup.gs`
- Test: `tests/test_setup.js`, `tests/test_full_pipeline.js`

**Interfaces:**
- Produces: `setupAllCcsmTriggers()` (creates every schedule below after deleting same-named existing triggers), `deleteAllCcsmTriggers()`, `smokeTestPipeline()` (in-sheet dry run), `previewOneCoachingEmail()` (sends a single sample to the test inbox).

Trigger schedule (all local Santiago time — the bound project's timezone must be set to `America/Santiago` in Project Settings, documented in the file header):

| Function | Schedule |
|---|---|
| `runAgent3` | Daily 6:00 AM |
| `runAgent3Evening` | Daily 9:00 PM |
| `runAgent5A` | Sunday 10:00 PM |
| `runAgent1A` | Sunday 9:00 PM (chains 1B → 1C) |
| `runAgent5B` | Friday 12:00 PM (chains Agent6) |
| `runAgentReminder` | Sunday 6:00 PM |
| `runAgentDuplicate` | Daily 9:30 PM |
| `runAgentEscalation` | Daily 7:00 AM |
| `runAgent4` | Monday 7:00 AM |
| `runAgentScores` | Monday 12:05 AM |
| `runAgent2` | none (manual, once per transfer) |

- [ ] **Step 1: Failing full-pipeline test** (`tests/test_full_pipeline.js`): load ALL CCSM files + CcsmData + Builder in one env; build sheet; attach fixture raw tabs; simulate 8 days of submissions for 3 areas (one perfect, one missing 2 days, one duplicate-submitting); run agents in schedule order for a simulated week; assert: DAILY_LOG rows correct, WEEKLY_KI written, coaching emails Spanish + TEST-inbox only, missed-days alert for the gap area, dup flagged in AUDIT_LOG, SCORES written, AGENT_RUN_LOG has a SUCCESS row per agent run, `state.emails.every(e => e.to === 'CCSM.PMG.Compass@gmail.com')`.

- [ ] **Step 2: Implement `CCSM_Setup.gs`**; `tests/test_setup.js` asserts `setupAllCcsmTriggers()` creates exactly the table above (inspect `state.triggers`) and is idempotent (run twice → same count).

- [ ] **Step 3: Run both → pass**, **Step 4: Commit** — `git commit -m "feat: CCSM_Setup — Santiago triggers, smoke tests, full-pipeline test green"`

---

### Task 15: Deployment runbook + memory update

**Files:**
- Create: `CCSM_DEPLOYMENT.md`
- Modify: memory `ccsm-sheet-and-agents.md`

- [ ] **Step 1: Write `CCSM_DEPLOYMENT.md`** — exact click-by-click for the user: (1) run `BuildCcsmSheet` standalone (paste CcsmData.gs + BuildCcsmSheet.gs into one script.google.com project as the CCSM Gmail account); (2) attach both ES forms + rename tabs; (3) open the sheet → Extensions → Apps Script → set project timezone to Santiago → paste files in order (CCSM_Helpers first, then agents, CCSM_SeedContent, CCSM_Setup) ; (4) Script Properties: `GEMINI_API_KEY`; (5) run `seedCcsmMessageBank()` + `seedCcsmKnowledgeBase()` + `setupCcsmScoreConfig()`; (6) fill AGENT_CONFIG blanks; (7) run `smokeTestPipeline()` + `previewOneCoachingEmail()`, submit one real test form response each way, run `runAgent3` manually, check DAILY_LOG; (8) content review gate (CONTENT_REVIEW.md signed off); (9) `setupAllCcsmTriggers()`; (10) flip `TEST_MODE=FALSE` only when emails in MISSION_ORG are populated and verified. Include the spec's testing checklist as checkboxes.
- [ ] **Step 2: Update memory** — record completion status, file inventory, and any deviations discovered during implementation in `ccsm-sheet-and-agents.md`.
- [ ] **Step 3: Final residue sweep** — `grep -rn "Utah Provo\|America/Denver\|Sister Ellis\|missionary\.org.*@" CCSM_*.gs BuildCcsmSheet.gs CcsmData.gs` → only legitimate hits (none expected; `@missionary.org` may appear in comments about email format — acceptable).
- [ ] **Step 4: Commit** — `git commit -m "docs: CCSM deployment runbook"`

---

## Self-Review Notes

- **Spec coverage:** sheet builder (T2–T3), verify pass (T3), QUESTIONS_CONFIG Spanish mapping (T2–T3), MISSION_ORG names+flags/blank emails (T2), agents incl. 5B (T5–T12), Sister Ellis cut (enforced greps T11/T15), Spanish content + review gate (T13), TEST_MODE safety (fixtures + assertions throughout), smoke tests + runbook (T14–T15), duplicate-column coalescing (T5 fixture layout forces it).
- **Known judgment calls needing user eyes during review:** rate-metric definitions (T7), SCORE_CONFIG default weights (T12), trigger times (T14).
- **Types/names:** `ccsmEffortScore` defined in CCSM_Helpers (T5) and consumed in T6/T7/T12; fixtures API (`makeCcsmSpreadsheet`, `addNightlyRaw`, `addWeeklyRaw`, `setConfig`) defined T4–T5, consumed T5–T14; `getMissionName`/`getMissionTimezone` defined T4, used everywhere.
