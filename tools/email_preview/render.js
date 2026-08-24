/**
 * render.js — see the weekly training email without sending it.
 *
 * Runs the REAL CCSM_Agent1A -> 1B -> 1C code, unmodified, in Node against a
 * dump of the live sheet, and writes the exact HTML each recipient would be
 * emailed. Nothing is sent and nothing is written back to the sheet.
 *
 * WHY THIS EXISTS. The email had no way to be previewed. Apps Script's own
 * previewOneCoachingEmail() (CCSM_Setup.gs:800) hand-rolls a simplified sample
 * and never calls a1c_buildEmail — the real builder is reached only from
 * runAgent1C:414 — so editing against it tells you nothing about what actually
 * goes out. And as of 2026-08-24 runAgent1C had never once completed on the
 * live project, so there was no sent email to look at either.
 *
 * HOW IT STAYS HONEST. Only the Apps Script PLATFORM is faked (Logger,
 * Utilities, SpreadsheetApp, PropertiesService, MailApp, UrlFetchApp,
 * ScriptApp). Every line of CCSM_*.gs is loaded as-is. If the layout changes,
 * this output changes with it, because it IS the shipping code.
 *
 *   node tools/email_preview/render.js [--gemini] [--out DIR]
 *
 * --gemini  actually call Gemini for the leadership narratives (needs
 *           GEMINI_API_KEY in AGENT_CONFIG). Off by default: the narrative is
 *           replaced with a clearly-marked placeholder so repeated renders are
 *           free, deterministic, and quota-safe.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HERE = path.resolve(__dirname);
const REPO = path.resolve(HERE, '..', '..');
const DATA = path.join(HERE, '.data', 'tabs.json');

const argv = process.argv.slice(2);
const USE_GEMINI = argv.includes('--gemini');
const outIdx = argv.indexOf('--out');
const OUT = path.resolve(outIdx >= 0 ? argv[outIdx + 1] : path.join(HERE, '.data', 'out'));

if (!fs.existsSync(DATA)) {
  console.error(`No sheet dump at ${DATA}\nRun first, from dashboard/:\n` +
                `  venv/Scripts/python.exe ../tools/email_preview/dump_tabs.py`);
  process.exit(1);
}
const GRIDS = JSON.parse(fs.readFileSync(DATA, 'utf8'));

// ─────────────────────────────────────────────────────────────────────────────
// Apps Script platform stubs
// ─────────────────────────────────────────────────────────────────────────────

const logLines = [];

/** A Range over a rectangular slice of a grid. 1-based, like Apps Script. */
function makeRange(grid, row, col, numRows, numCols) {
  return {
    getValues() {
      const out = [];
      for (let r = row - 1; r < row - 1 + numRows; r++) {
        const src = grid[r] || [];
        const line = [];
        for (let c = col - 1; c < col - 1 + numCols; c++) line.push(src[c] !== undefined ? src[c] : '');
        out.push(line);
      }
      return out;
    },
    setValues(vals) {
      vals.forEach((line, i) => {
        const r = row - 1 + i;
        if (!grid[r]) grid[r] = [];
        line.forEach((v, j) => { grid[r][col - 1 + j] = v; });
      });
    },
    setValue(v) {
      const r = row - 1;
      if (!grid[r]) grid[r] = [];
      grid[r][col - 1] = v;
    },
    // Cosmetic chainables the agents call on written ranges.
    setFontWeight() { return this; },
    setBackground() { return this; },
    setNumberFormat() { return this; },
    setHorizontalAlignment() { return this; },
  };
}

function makeSheet(name, grid) {
  return {
    getName: () => name,
    getLastRow: () => grid.length,
    getLastColumn: () => grid.reduce((m, r) => Math.max(m, r.length), 0),
    getDataRange: () => makeRange(grid, 1, 1, grid.length, grid.reduce((m, r) => Math.max(m, r.length), 0)),
    getRange: (r, c, nr, nc) => makeRange(grid, r, c, nr === undefined ? 1 : nr, nc === undefined ? 1 : nc),
    appendRow: (row) => { grid.push(row.slice()); },
    // Writes are in-memory only — this tool never touches the live sheet.
    clear() { grid.length = 0; return this; },
    setFrozenRows() { return this; },
    autoResizeColumns() { return this; },
    insertSheet() { return this; },
  };
}

const SHEETS = {};
Object.keys(GRIDS).forEach((name) => { SHEETS[name] = makeSheet(name, GRIDS[name]); });

const SpreadsheetApp = {
  getActiveSpreadsheet: () => ({
    getSheetByName: (n) => SHEETS[n] || null,
    getSheets: () => Object.keys(SHEETS).map((n) => SHEETS[n]),
    insertSheet: (n) => { GRIDS[n] = []; SHEETS[n] = makeSheet(n, GRIDS[n]); return SHEETS[n]; },
    getName: () => 'COMPASS_CCSM (offline copy)',
    getId: () => 'offline',
  }),
  openById() { return this.getActiveSpreadsheet(); },
  flush() {},
};

const _props = {};
const PropertiesService = {
  getScriptProperties: () => ({
    getProperty: (k) => (k in _props ? _props[k] : null),
    setProperty: (k, v) => { _props[k] = String(v); },
    deleteProperty: (k) => { delete _props[k]; },
    getProperties: () => Object.assign({}, _props),
    deleteAllProperties: () => { Object.keys(_props).forEach((k) => delete _props[k]); },
  }),
};

const Logger = { log: (m) => { logLines.push(String(m)); } };

/** Enough of Utilities.formatDate for the patterns the agents actually use. */
const Utilities = {
  formatDate(date, tz, fmt) {
    const d = date instanceof Date ? date : new Date(date);
    const p = (n, w) => String(n).padStart(w || 2, '0');
    // Longest token first so e.g. "dd" isn't left partially matched by "d".
    return String(fmt).replace(/yyyy|MM|dd|HH|mm|ss|M|d/g, (tok) => {
      switch (tok) {
        case 'yyyy': return d.getFullYear();
        case 'MM': return p(d.getMonth() + 1);
        case 'dd': return p(d.getDate());
        case 'HH': return p(d.getHours());
        case 'mm': return p(d.getMinutes());
        case 'ss': return p(d.getSeconds());
        case 'M': return d.getMonth() + 1;
        case 'd': return d.getDate();
      }
    });
  },
  sleep() {},
  getUuid: () => 'offline-uuid',
};

const sent = [];
const MailApp = {
  getRemainingDailyQuota: () => 1000,
  // Two call shapes: MailApp.sendEmail(to, subject, body, opts) and the
  // single-object form MailApp.sendEmail({to, subject, htmlBody}). Helpers'
  // sendEmail() uses the object form, so handling only the positional one
  // captured every recipient as "[object Object]".
  sendEmail: (a, subject, body, opts) => {
    if (a && typeof a === 'object') {
      sent.push({ to: a.to, subject: a.subject, html: a.htmlBody || a.body || '' });
    } else {
      sent.push({ to: a, subject, html: (opts && opts.htmlBody) || body });
    }
  },
};

const PLACEHOLDER_NARRATIVE =
  '[[ narrativa de Gemini — marcador de posición. Ejecute con --gemini para ver el texto real. ]]';

const UrlFetchApp = {
  fetch(url) {
    if (!USE_GEMINI && /generativelanguage|gemini/i.test(url)) {
      const payload = { candidates: [{ content: { parts: [{ text: PLACEHOLDER_NARRATIVE }] } }] };
      return {
        getResponseCode: () => 200,
        getContentText: () => JSON.stringify(payload),
      };
    }
    // Relay sends: swallow. Nothing leaves this process.
    return { getResponseCode: () => 200, getContentText: () => '{"ok":true}' };
  },
};

const ScriptApp = {
  // The chain is driven explicitly below, so scheduling is a no-op.
  newTrigger: () => ({
    timeBased: () => ({
      after: () => ({ create() {} }),
      everyDays: () => ({ atHour: () => ({ inTimezone: () => ({ create() {} }), create() {} }) }),
      onWeekDay: () => ({ atHour: () => ({ nearMinute: () => ({ inTimezone: () => ({ create() {} }) }), inTimezone: () => ({ create() {} }) }) }),
    }),
  }),
  getProjectTriggers: () => [],
  deleteTrigger: () => {},
  WeekDay: { MONDAY: 1, TUESDAY: 2, WEDNESDAY: 3, THURSDAY: 4, FRIDAY: 5, SATURDAY: 6, SUNDAY: 0 },
};

const Session = { getScriptTimeZone: () => 'America/Santiago' };
const CacheService = {
  getScriptCache: () => ({ get: () => null, put() {}, remove() {} }),
};

// ─────────────────────────────────────────────────────────────────────────────
// Load the real agent source
// ─────────────────────────────────────────────────────────────────────────────

const sandbox = {
  SpreadsheetApp, PropertiesService, Logger, Utilities, MailApp,
  UrlFetchApp, ScriptApp, Session, CacheService,
  console, JSON, Math, Date, String, Number, Object, Array, RegExp, isNaN, parseInt, parseFloat,
};
sandbox.globalThis = sandbox;
const ctx = vm.createContext(sandbox);

// Helpers first (everything else calls into it), then data specs, then the
// chain in dependency order. Order matters: these files share one scope in
// Apps Script and some declare top-level values the others read at load.
const FILES = [
  'CCSM_Helpers.gs',
  'CCSM_AgentTestMode.gs',
  'CcsmData.gs',
  'CCSM_Setup.gs',
  'CCSM_Agent1A.gs',
  'CCSM_Agent1B.gs',
  'CCSM_Agent1C.gs',
];

FILES.forEach((f) => {
  const p = path.join(REPO, f);
  if (!fs.existsSync(p)) { console.error(`missing ${f}`); process.exit(1); }
  try {
    vm.runInContext(fs.readFileSync(p, 'utf8'), ctx, { filename: f });
  } catch (e) {
    console.error(`\nFailed loading ${f}: ${e.message}`);
    process.exit(1);
  }
});

// Replace the narrative generator unless --gemini. callGemini() checks for an
// API key before it ever issues a fetch, and the key lives in Script
// Properties on the live project — not in the sheet — so stubbing UrlFetchApp
// alone leaves every narrative erroring out.
if (!USE_GEMINI) {
  ctx.callGemini = function () { return PLACEHOLDER_NARRATIVE; };
}

// ─────────────────────────────────────────────────────────────────────────────
// Run the chain and capture every email
// ─────────────────────────────────────────────────────────────────────────────

function run(fnName) {
  process.stdout.write(`  ${fnName} ... `);
  try {
    vm.runInContext(`${fnName}()`, ctx);
    console.log('ok');
  } catch (e) {
    console.log(`FAILED\n     ${e.message}`);
    return false;
  }
  return true;
}

// Apps Script caps the whole Script Properties store at 500 KB. A1A_DATA and
// A1B_DATA are both resident between 1A and 1C, and only Agent1C clears them
// -- the suspected cause of Agent1C never having run. Report the sizes after
// each step so any change to the payload shape is measured, not guessed.
// saveTempData splits big values across `KEY__0, KEY__1, ... KEY__chunks`, so
// group by the base key before '__' rather than looking for a bare KEY.
const PROP_LIMIT = 500 * 1024;
function reportPayloads(label) {
  const keys = Object.keys(_props);
  if (keys.length === 0) return;
  const byBase = {};
  let total = 0;
  keys.forEach((k) => {
    const base = k.split('__')[0];
    const n = _props[k].length + k.length;
    byBase[base] = (byBase[base] || 0) + n;
    total += n;
  });
  const parts = Object.keys(byBase).sort()
    .map((b) => `${b}=${(byBase[b] / 1024).toFixed(1)}KB`);
  const pct = ((total / PROP_LIMIT) * 100).toFixed(0);
  console.log(`     ${label}: ${parts.join('  ')}  ->  total ${(total / 1024).toFixed(1)}KB ` +
              `(${pct}% of the 500KB property-store limit)${total > PROP_LIMIT ? '  ** OVER LIMIT **' : ''}`);
}

console.log(`\nLoaded ${FILES.length} agent files. Gemini: ${USE_GEMINI ? 'LIVE' : 'placeholder'}\n`);
if (!run('runAgent1A')) process.exit(1);
reportPayloads('after 1A');
if (!run('runAgent1B')) process.exit(1);
reportPayloads('after 1B');
if (!run('runAgent1C')) process.exit(1);

fs.mkdirSync(OUT, { recursive: true });
fs.rmSync(path.join(OUT, 'index.html'), { force: true });

const safe = (s) => String(s).replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 80);
const index = [];
sent.forEach((m, i) => {
  const file = `${String(i + 1).padStart(3, '0')}_${safe(m.to)}.html`;
  fs.writeFileSync(path.join(OUT, file), m.html || '(no html body)', 'utf8');
  index.push(`<li><a href="${file}">${m.to}</a> — ${m.subject}</li>`);
});

fs.writeFileSync(path.join(OUT, 'index.html'),
  `<!doctype html><meta charset="utf-8"><title>Weekly training email — preview</title>` +
  `<body style="font-family:system-ui;max-width:800px;margin:2rem auto;">` +
  `<h1>Weekly training email — preview</h1>` +
  `<p>${sent.length} email(s), rendered by the real Agent1C. Nothing was sent.</p>` +
  `<ol>${index.join('')}</ol></body>`, 'utf8');

fs.writeFileSync(path.join(OUT, 'run.log'), logLines.join('\n'), 'utf8');

console.log(`\n${sent.length} email(s) captured -> ${OUT}`);
console.log(`  open ${path.join(OUT, 'index.html')}`);
console.log(`  agent log: ${path.join(OUT, 'run.log')}`);
