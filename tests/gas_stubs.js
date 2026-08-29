// gas_stubs.js — in-memory Google Apps Script global stubs, no npm deps.
//
// makeGasEnv(options) -> { globals, state }
//   state.spreadsheets : id -> true spreadsheet record { id, name, sheets: { name -> 2D array } , sheetOrder: [names] }
//   state.emails       : array of { to, subject, body, htmlBody, ... } captured from MailApp/GmailApp
//   state.logs         : array of strings captured from Logger.log
//   state.triggers     : array of trigger records created via ScriptApp
//   state.props        : in-memory script properties store
//
// Critical design point: SpreadsheetApp.openById(id) returns a FRESH wrapper
// object over state.spreadsheets[id] on every call. It never returns a
// cached/prior wrapper instance. This models real Apps Script behavior where
// each service call reads current server-side state (all pending writes from
// any handle are already "flushed" into state.spreadsheets by the time any
// other call reads it back), which later tests rely on to exercise
// dropped-write recovery paths.

// ---- Process timezone pin -------------------------------------------------
// In the real Apps Script runtime the PROJECT timezone IS the mission
// timezone (CCSM_Setup.gs's required one-time manual step), so the agents can
// and do freely mix two idioms: format-through-getMissionTimezone() (e.g.
// CCSM_AgentScores.gs:437) and plain local-calendar arithmetic on
// new Date(y, m, d) (e.g. CCSM_Agent5A.gs:888-896 a5a_getWeekEnd). Under Node
// those two only agree when the PROCESS's local timezone is the mission's —
// otherwise a machine east of Santiago turns local-midnight Sunday into
// Saturday 20:00 Santiago and every derived week-end slips a day.
//
// Pinning it here, at require() time, makes EVERY suite independent of the dev
// machine's timezone rather than just the one that remembered to do it. It
// does not paper over anything production hits: production genuinely runs with
// script timezone == mission timezone.
//
// WHAT A `TZ=<other> node tests/...` RUN DOES AND DOES NOT PROVE: this pin
// overwrites the ambient TZ, so such a run is byte-for-byte the same run as an
// unset one. It proves the pin holds on a differently-configured machine (a UTC
// CI runner included) — it does NOT independently exercise any timezone. Never
// cite two such runs as two pieces of evidence; they are one.
//
// CCSM_TEST_TZ_PIN=0 disables the pin and leaves the ambient TZ alone. That is
// the diagnostic mode for the question the pin otherwise hides — "does agent
// code still depend on the process's local calendar?" — and suites are EXPECTED
// to fail under it on a non-Santiago machine. Under that flag a failure is the
// finding, not a regression.
const MISSION_TZ = 'America/Santiago';
if (process.env.CCSM_TEST_TZ_PIN !== '0') process.env.TZ = MISSION_TZ;

let nextId = 1;
function genId() {
  return 'ss_' + (nextId++);
}

function makeGasEnv(options = {}) {
  const state = {
    spreadsheets: {},
    emails: [],
    logs: [],
    triggers: [],
    props: {},
    drive: { folders: {}, files: {} },
    // Gmail daily-send quota modeling. Configurable via
    // makeGasEnv({ remainingQuota: N }); defaults high (1000) so existing
    // tests that don't care about quota guards are unaffected. Decrements by
    // 1 on every MailApp/GmailApp.sendEmail() call so tests can exercise the
    // "stop mid-run once quota runs low" guard in CCSM_AgentReminder.gs /
    // CCSM_AgentEscalation.gs deterministically.
    remainingQuota: options.remainingQuota !== undefined ? options.remainingQuota : 1000,
  };

  // ---- Dropped-write modeling ---------------------------------------------
  // options.dropWriteRate (0..1): models Google Sheets occasionally dropping
  // a cell write under load. The FIRST attempt to write any given absolute
  // cell (sheetRecord + 1-indexed row/col) has a dropWriteRate chance of
  // silently no-op'ing (the cell keeps whatever value it already had — '' if
  // never written). Every subsequent attempt at that same cell is honest
  // (always applies). This lets a reopen-verify-fix loop's second attempt at
  // a previously-dropped cell always succeed, matching real-world recovery.
  const dropWriteRate = options.dropWriteRate || 0;

  function attemptCell(sheetRecord, row, col) {
    if (!dropWriteRate) return true; // no drop modeling configured
    if (!sheetRecord._attemptedCells) sheetRecord._attemptedCells = new Set();
    const key = row + ',' + col;
    if (sheetRecord._attemptedCells.has(key)) return true; // 2nd+ attempt: honest
    sheetRecord._attemptedCells.add(key);
    return Math.random() >= dropWriteRate; // true => write goes through
  }

  // ---- Range -------------------------------------------------------------
  // A Range is a view onto a rectangular slice of a sheet's backing 2D array.
  // It always reads/writes through to sheetRecord.data (the true stored
  // state for that sheet), so there is no separate "range cache" to get out
  // of sync with the sheet.
  class Range {
    constructor(sheetRecord, row, col, numRows, numCols) {
      this._sheet = sheetRecord;
      this._row = row; // 1-indexed
      this._col = col; // 1-indexed
      this._numRows = numRows;
      this._numCols = numCols;
    }

    _ensureCapacity(maxRow, maxCol) {
      const data = this._sheet.data;
      while (data.length < maxRow) data.push([]);
      for (let r = 0; r < data.length; r++) {
        while (data[r].length < maxCol) data[r].push('');
      }
    }

    getValues() {
      const data = this._sheet.data;
      const out = [];
      for (let r = 0; r < this._numRows; r++) {
        const row = [];
        for (let c = 0; c < this._numCols; c++) {
          const srcRow = data[this._row - 1 + r];
          row.push(srcRow && srcRow[this._col - 1 + c] !== undefined ? srcRow[this._col - 1 + c] : '');
        }
        out.push(row);
      }
      return out;
    }

    getValue() {
      return this.getValues()[0][0];
    }

    setValues(values) {
      this._ensureCapacity(this._row - 1 + values.length, this._col - 1 + (values[0] ? values[0].length : 0));
      const data = this._sheet.data;
      for (let r = 0; r < values.length; r++) {
        for (let c = 0; c < values[r].length; c++) {
          const absRow = this._row + r;
          const absCol = this._col + c;
          if (attemptCell(this._sheet, absRow, absCol)) {
            data[this._row - 1 + r][this._col - 1 + c] = values[r][c];
          }
        }
      }
      return this;
    }

    setValue(value) {
      this._ensureCapacity(this._row, this._col);
      if (attemptCell(this._sheet, this._row, this._col)) {
        this._sheet.data[this._row - 1][this._col - 1] = value;
      }
      return this;
    }

    // Formatting is not modeled beyond being no-ops that return `this` for chaining.
    setFontWeight() { return this; }
    setBackground() { return this; }
    setFontColor() { return this; }
  }

  // ---- Sheet ---------------------------------------------------------------
  // sheetRecord is the true stored state: { name, data: [][] , lastRow, lastCol, frozenRows }
  // The Sheet wrapper class is a thin API over a sheetRecord. parentId (the
  // owning spreadsheet's id) is threaded through so getParent() can hand back
  // a real Spreadsheet wrapper — needed by code that discovers a sheet via
  // one spreadsheet handle and then needs its OWN id (CCSM_SeedContent.gs's
  // csc_writeTab_ does exactly this for its reopen-and-verify step, and that
  // matters once a tab can live in a spreadsheet other than the caller's own
  // getSpreadsheet()).
  class Sheet {
    constructor(sheetRecord, parentId) {
      this._rec = sheetRecord;
      this._parentId = parentId;
    }

    getName() { return this._rec.name; }

    getParent() { return SpreadsheetApp.openById(this._parentId); }

    getLastRow() { return this._rec.data.length; }

    getLastColumn() {
      let max = 0;
      for (const row of this._rec.data) max = Math.max(max, row.length);
      return max;
    }

    getDataRange() {
      const lastRow = this.getLastRow();
      const lastCol = this.getLastColumn();
      return new Range(this._rec, 1, 1, Math.max(lastRow, 0), Math.max(lastCol, 0));
    }

    getRange(row, col, numRows, numCols) {
      return new Range(this._rec, row, col, numRows === undefined ? 1 : numRows, numCols === undefined ? 1 : numCols);
    }

    appendRow(arr) {
      const rowIndex = this._rec.data.length; // 0-indexed position of the new row
      const row = new Array(arr.length).fill('');
      for (let c = 0; c < arr.length; c++) {
        if (attemptCell(this._rec, rowIndex + 1, c + 1)) row[c] = arr[c];
      }
      this._rec.data.push(row);
      return this;
    }

    setFrozenRows(n) {
      this._rec.frozenRows = n;
      return this;
    }

    clear() {
      this._rec.data = [];
      this._rec.frozenRows = 0;
      return this;
    }

    clearContents() {
      this._rec.data = [];
      return this;
    }

    deleteRow(n) {
      this._rec.data.splice(n - 1, 1);
      return this;
    }

    getMaxColumns() {
      return Math.max(this.getLastColumn(), 26);
    }

    getMaxRows() {
      return Math.max(this.getLastRow(), 1000);
    }
  }

  // ---- Spreadsheet -----------------------------------------------------
  // Wraps a true spreadsheet record stored in state.spreadsheets[id].
  // Every SpreadsheetApp.create()/openById() call builds a NEW Spreadsheet
  // wrapper instance around the (possibly shared) record — see class doc
  // above for why this matters.
  class Spreadsheet {
    constructor(record) {
      this._rec = record;
    }

    getId() { return this._rec.id; }
    getName() { return this._rec.name; }
    getUrl() { return 'https://docs.google.com/spreadsheets/d/' + this._rec.id + '/edit'; }

    getSheetByName(name) {
      const rec = this._rec.sheets[name];
      return rec ? new Sheet(rec, this._rec.id) : null;
    }

    insertSheet(name) {
      if (!this._rec.sheets[name]) {
        this._rec.sheets[name] = { name, data: [], frozenRows: 0 };
        this._rec.sheetOrder.push(name);
      }
      return new Sheet(this._rec.sheets[name], this._rec.id);
    }

    deleteSheet(sheet) {
      const name = sheet.getName();
      delete this._rec.sheets[name];
      const idx = this._rec.sheetOrder.indexOf(name);
      if (idx !== -1) this._rec.sheetOrder.splice(idx, 1);
    }

    getSheets() {
      return this._rec.sheetOrder.map((name) => new Sheet(this._rec.sheets[name], this._rec.id));
    }
  }

  const SpreadsheetApp = {
    create(name) {
      const id = genId();
      state.spreadsheets[id] = { id, name, sheets: {}, sheetOrder: [] };
      return new Spreadsheet(state.spreadsheets[id]);
    },
    openById(id) {
      const record = state.spreadsheets[id];
      if (!record) throw new Error('No spreadsheet with id ' + id);
      // Fresh wrapper every call over the true stored state — models GAS
      // server flush semantics (see module doc comment).
      return new Spreadsheet(record);
    },
    getActiveSpreadsheet() {
      if (!state.activeSpreadsheetId) return null;
      return SpreadsheetApp.openById(state.activeSpreadsheetId);
    },
    // Real GAS exposes both spellings; CCSM_AgentQA.gs uses the short one.
    getActive() {
      return SpreadsheetApp.getActiveSpreadsheet();
    },
    flush() {
      // no-op: writes in this stub are always immediately committed to
      // state.spreadsheets, so there is nothing to flush.
    },
  };

  // ---- Logger ------------------------------------------------------------
  const Logger = {
    log(...args) {
      const line = args.map((a) => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ');
      state.logs.push(line);
      return Logger;
    },
  };

  // ---- Utilities -----------------------------------------------------------
  function formatDate(date, timeZone, pattern) {
    const parts = getDateParts(date, timeZone);
    return applyPattern(pattern, parts);
  }

  function getDateParts(date, timeZone) {
    const dtf = new Intl.DateTimeFormat('en-US', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      weekday: 'long',
    });
    const partsArr = dtf.formatToParts(date);
    const get = (type) => partsArr.find((p) => p.type === type).value;
    let hour24 = parseInt(get('hour'), 10);
    if (hour24 === 24) hour24 = 0; // some locales format midnight as 24
    const minute = parseInt(get('minute'), 10);
    const second = parseInt(get('second'), 10);
    return {
      year: get('year'),
      month: parseInt(get('month'), 10),
      day: parseInt(get('day'), 10),
      weekday: get('weekday'),
      hour24,
      minute,
      second,
    };
  }

  const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];
  // getDateParts() only requests `weekday: 'long'` from Intl.DateTimeFormat,
  // so it never has the abbreviated form on hand — derive EEE from EEEE.
  const WEEKDAY_ABBR = { Sunday: 'Sun', Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed',
    Thursday: 'Thu', Friday: 'Fri', Saturday: 'Sat' };

  function pad2(n) { return String(n).padStart(2, '0'); }

  // Recognized tokens, LONGEST FIRST within each letter group so a greedy
  // left-to-right scan never matches a short token (e.g. "M") inside a
  // longer one (e.g. "MMMM") it should have consumed whole.
  const TOKENS = ['yyyy', 'yy', 'MMMM', 'MMM', 'MM', 'M', 'dd', 'd',
    'EEEE', 'EEE', 'HH', 'H', 'hh', 'h', 'mm', 'm', 'ss', 's', 'a'];

  function tokenValue(token, parts) {
    let hour12 = parts.hour24 % 12;
    if (hour12 === 0) hour12 = 12;
    const ampm = parts.hour24 < 12 ? 'AM' : 'PM';
    switch (token) {
      case 'yyyy': return String(parts.year);
      case 'yy':   return String(parts.year).slice(-2);
      case 'MMMM': return MONTH_NAMES[parts.month - 1];
      case 'MMM':  return MONTH_NAMES[parts.month - 1].slice(0, 3);
      case 'MM':   return pad2(parts.month);
      case 'M':    return String(parts.month);
      case 'dd':   return pad2(parts.day);
      case 'd':    return String(parts.day);
      case 'EEEE': return parts.weekday;
      case 'EEE':  return WEEKDAY_ABBR[parts.weekday] || parts.weekday.slice(0, 3);
      case 'HH':   return pad2(parts.hour24);
      case 'H':    return String(parts.hour24);
      case 'hh':   return pad2(hour12);
      case 'h':    return String(hour12);
      case 'mm':   return pad2(parts.minute);
      case 'm':    return String(parts.minute);
      case 'ss':   return pad2(parts.second);
      case 's':    return String(parts.second);
      case 'a':    return ampm;
      default:     return token;
    }
  }

  // Tokenizes and substitutes `pattern` in a SINGLE left-to-right pass: at
  // each position, try each known token (longest-first) for a match:
  //   - on match, emit its substituted value and advance past the token in
  //     the SOURCE pattern (never re-scanning already-emitted output, so
  //     letters inside inserted names like "Thursday"/"July" can never be
  //     re-matched as tokens themselves);
  //   - otherwise emit the single literal character and advance by one.
  // This replaces the old chained-.replace() approach, which re-scanned the
  // whole string after each substitution and corrupted letters inside
  // inserted weekday/month names (e.g. "Thursday, July 9" -> "T2ursdPMy,
  // July 9" once the 'h'/'a'/'d' replacements ran over already-substituted
  // text).
  //
  // Quoted literals: java.text.SimpleDateFormat (what Apps Script's
  // Utilities.formatDate actually uses) treats text inside single quotes as a
  // LITERAL that must not be tokenized; '' is an escaped literal quote.
  //
  // This matters for real CCSM code: CCSM_AgentReminder.gs:423 formats with
  // "MMMM d, yyyy 'a las' h:mm a". Without quote handling the stub tokenized
  // the a/l/s inside 'a las' and emitted garbage ("'PM lPM9'") — i.e. the STUB
  // was wrong while the .gs was right. No test covered that string, which is
  // the only reason the suite was green. Left unfixed, the next person to test
  // a reminder body would have "fixed" correct production code to match a
  // broken stub, so this fidelity gap was more dangerous than a plain failure.
  function applyPattern(pattern, parts) {
    let out = '';
    let i = 0;
    outer:
    while (i < pattern.length) {
      if (pattern[i] === "'") {
        // '' outside a quoted run is a literal quote.
        if (pattern[i + 1] === "'") { out += "'"; i += 2; continue; }
        // Consume the quoted run character by character so that an embedded ''
        // yields a literal quote rather than ending the run (e.g. 'o''clock').
        i += 1;
        while (i < pattern.length) {
          if (pattern[i] === "'") {
            if (pattern[i + 1] === "'") { out += "'"; i += 2; continue; }
            i += 1;      // closing quote
            break;
          }
          out += pattern[i];
          i += 1;
        }
        continue;
      }
      for (const token of TOKENS) {
        if (pattern.startsWith(token, i)) {
          out += tokenValue(token, parts);
          i += token.length;
          continue outer;
        }
      }
      out += pattern[i];
      i += 1;
    }
    return out;
  }

  const Utilities = {
    sleep() {},
    formatDate,
  };

  // ---- PropertiesService --------------------------------------------------
  function makePropertyStore(bucketKey) {
    if (!state.props[bucketKey]) state.props[bucketKey] = {};
    const bucket = state.props[bucketKey];
    return {
      getProperty(key) {
        return Object.prototype.hasOwnProperty.call(bucket, key) ? bucket[key] : null;
      },
      setProperty(key, value) {
        bucket[key] = String(value);
        return this;
      },
      deleteProperty(key) {
        delete bucket[key];
        return this;
      },
      getProperties() {
        return Object.assign({}, bucket);
      },
      setProperties(obj) {
        Object.assign(bucket, obj);
        return this;
      },
    };
  }

  const PropertiesService = {
    getScriptProperties() { return makePropertyStore('script'); },
    getUserProperties() { return makePropertyStore('user'); },
    getDocumentProperties() { return makePropertyStore('document'); },
  };

  // ---- Drive ---------------------------------------------------------------
  // Minimal in-memory file/folder store — just enough for CCSM_Helpers.gs's
  // saveTempData/loadTempData/clearTempData (ccsmTempDataFolder_, createFile,
  // getFileById, getBlob().getDataAsString(), setTrashed). No real folder
  // hierarchy, sharing, or permissions modeled; state.drive is exposed on the
  // returned `state` for tests that want to assert on it directly.
  let nextDriveId = 1;
  function genDriveId() { return 'drive_' + (nextDriveId++); }

  function makeDriveFile(id) {
    return {
      getId() { return id; },
      getBlob() {
        const rec = state.drive.files[id];
        return { getDataAsString() { return rec.content; } };
      },
      setTrashed(trashed) {
        const rec = state.drive.files[id];
        if (rec) rec.trashed = !!trashed;
        return this;
      },
    };
  }

  function makeDriveFolder(id) {
    return {
      getId() { return id; },
      createFile(name, content, mimeType) {
        const fileId = genDriveId();
        state.drive.files[fileId] = { id: fileId, name, content: String(content), mimeType, folderId: id, trashed: false };
        return makeDriveFile(fileId);
      },
    };
  }

  const DriveApp = {
    getFoldersByName(name) {
      const matches = Object.values(state.drive.folders).filter((f) => f.name === name && !f.trashed);
      let i = 0;
      return {
        hasNext() { return i < matches.length; },
        next() { return makeDriveFolder(matches[i++].id); },
      };
    },
    createFolder(name) {
      const id = genDriveId();
      state.drive.folders[id] = { id, name, trashed: false };
      return makeDriveFolder(id);
    },
    getFolderById(id) {
      if (!state.drive.folders[id] || state.drive.folders[id].trashed) {
        throw new Error('No Drive folder with id ' + id);
      }
      return makeDriveFolder(id);
    },
    getFileById(id) {
      if (!state.drive.files[id] || state.drive.files[id].trashed) {
        throw new Error('No Drive file with id ' + id);
      }
      return makeDriveFile(id);
    },
  };

  const MimeType = { PLAIN_TEXT: 'text/plain' };

  // ---- ScriptApp -----------------------------------------------------------
  let nextTriggerId = 1;
  function makeTriggerBuilder(handlerFunctionName) {
    const spec = { handlerFunctionName, type: null };
    function create() {
      const trigger = {
        uid: 'trigger_' + (nextTriggerId++),
        handlerFunctionName,
        ...spec,
        // Real GAS Trigger objects expose accessors, not plain properties —
        // CCSM_Helpers.gs's deleteTriggerByName() (and any other agent code)
        // calls trigger.getHandlerFunction(), not trigger.handlerFunctionName.
        getHandlerFunction() { return handlerFunctionName; },
        getUniqueId() { return trigger.uid; },
        // CCSM_Setup.gs's converge-to-table installer tells time-based
        // triggers (which it owns and rebuilds) apart from installable
        // form-submit triggers (which it must leave alone) the same way real
        // Apps Script code does — by event type, not by handler name.
        getEventType() { return spec.type; },
      };
      state.triggers.push(trigger);
      return trigger;
    }
    const timeBuilder = {
      atHour(h) { spec.atHour = h; return timeBuilder; },
      nearMinute(m) { spec.nearMinute = m; return timeBuilder; },
      everyDays(n) { spec.everyDays = n; return timeBuilder; },
      everyHours(n) { spec.everyHours = n; return timeBuilder; },
      everyMinutes(n) { spec.everyMinutes = n; return timeBuilder; },
      onWeekDay(d) { spec.onWeekDay = d; return timeBuilder; },
      inTimezone(tz) { spec.timeZone = tz; return timeBuilder; },
      after(ms) { spec.after = ms; return timeBuilder; },
      at(date) { spec.at = date; return timeBuilder; },
      create,
    };
    // .forSpreadsheet(ss) starts an installable spreadsheet trigger;
    // .onFormSubmit() marks it as the ON_FORM_SUBMIT variant. CCSM installs
    // two of these (onNightlyFormSubmit, onQAFormSubmit).
    const sheetBuilder = {
      onFormSubmit() { spec.type = 'ON_FORM_SUBMIT'; return sheetBuilder; },
      onEdit() { spec.type = 'ON_EDIT'; return sheetBuilder; },
      onOpen() { spec.type = 'ON_OPEN'; return sheetBuilder; },
      onChange() { spec.type = 'ON_CHANGE'; return sheetBuilder; },
      create,
    };
    return {
      timeBased() {
        spec.type = 'CLOCK';
        return timeBuilder;
      },
      forSpreadsheet(ss) {
        spec.source = 'SPREADSHEETS';
        spec.spreadsheetId = ss && ss.getId ? ss.getId() : null;
        return sheetBuilder;
      },
    };
  }

  const ScriptApp = {
    // Real GAS exposes ScriptApp.WeekDay as an enum. Every CCSM setup*Trigger()
    // function (and CCSM_Setup.gs's setupAllCcsmTriggers) passes one of these
    // to .onWeekDay(), so the stub must expose it or those functions throw the
    // moment a test actually calls them. Modeled as plain uppercase strings —
    // the value is opaque to the code under test, which only ever passes it
    // straight through to the builder.
    WeekDay: {
      SUNDAY: 'SUNDAY', MONDAY: 'MONDAY', TUESDAY: 'TUESDAY', WEDNESDAY: 'WEDNESDAY',
      THURSDAY: 'THURSDAY', FRIDAY: 'FRIDAY', SATURDAY: 'SATURDAY',
    },
    // Same modelling choice as WeekDay: opaque uppercase strings. The values
    // trigger.getEventType() returns above are drawn from this same set.
    EventType: {
      CLOCK: 'CLOCK', ON_FORM_SUBMIT: 'ON_FORM_SUBMIT', ON_EDIT: 'ON_EDIT',
      ON_OPEN: 'ON_OPEN', ON_CHANGE: 'ON_CHANGE',
    },
    newTrigger(handlerFunctionName) {
      return makeTriggerBuilder(handlerFunctionName);
    },
    getProjectTriggers() {
      return state.triggers.slice();
    },
    deleteTrigger(trigger) {
      const idx = state.triggers.findIndex((t) => t === trigger || t.uid === trigger.uid);
      if (idx !== -1) state.triggers.splice(idx, 1);
    },
  };

  // ---- Session -------------------------------------------------------------
  // The Apps Script PROJECT timezone, which is a DIFFERENT setting from
  // AGENT_CONFIG's MISSION_TIMEZONE and is what plain local-date arithmetic
  // resolves against. This used to be hardcoded to MISSION_TZ, which made the
  // two permanently equal and the mismatch case (integration I-4) structurally
  // impossible to test — the stub quietly guaranteed the very invariant the
  // production code needed checked. makeGasEnv({ scriptTimeZone }) overrides
  // it so a mismatched project can be simulated.
  const scriptTimeZone = options.scriptTimeZone || MISSION_TZ;
  const Session = {
    getScriptTimeZone() { return scriptTimeZone; },
  };

  // ---- MailApp / GmailApp ---------------------------------------------------
  function sendEmail(...args) {
    let record;
    if (args.length === 1 && typeof args[0] === 'object') {
      record = Object.assign({}, args[0]);
    } else {
      const [to, subject, body] = args;
      record = { to, subject, body };
    }
    state.emails.push(record);
    state.remainingQuota -= 1;
    return record;
  }

  function getRemainingDailyQuota() {
    return state.remainingQuota;
  }

  const MailApp = { sendEmail, getRemainingDailyQuota };
  const GmailApp = { sendEmail, getRemainingDailyQuota };

  // ---- UrlFetchApp -----------------------------------------------------------
  const UrlFetchApp = {
    fetch(url, params) {
      if (options.geminiResponse !== undefined) {
        return options.geminiResponse;
      }
      throw new Error('UrlFetchApp.fetch: no stubbed response configured (options.geminiResponse)');
    },
  };

  // ---- HtmlService -----------------------------------------------------------
  const HtmlService = {
    createHtmlOutput(html) {
      return {
        _html: html,
        getContent() { return this._html; },
        setTitle() { return this; },
        setWidth() { return this; },
        setHeight() { return this; },
      };
    },
  };

  const globals = {
    SpreadsheetApp,
    Logger,
    Utilities,
    PropertiesService,
    DriveApp,
    MimeType,
    ScriptApp,
    Session,
    MailApp,
    GmailApp,
    UrlFetchApp,
    HtmlService,
  };

  return { globals, state };
}

module.exports = { makeGasEnv };
