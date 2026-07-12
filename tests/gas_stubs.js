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
  };

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
          data[this._row - 1 + r][this._col - 1 + c] = values[r][c];
        }
      }
      return this;
    }

    setValue(value) {
      this._ensureCapacity(this._row, this._col);
      this._sheet.data[this._row - 1][this._col - 1] = value;
      return this;
    }

    // Formatting is not modeled beyond being no-ops that return `this` for chaining.
    setFontWeight() { return this; }
    setBackground() { return this; }
    setFontColor() { return this; }
  }

  // ---- Sheet ---------------------------------------------------------------
  // sheetRecord is the true stored state: { name, data: [][] , lastRow, lastCol, frozenRows }
  // The Sheet wrapper class is a thin API over a sheetRecord.
  class Sheet {
    constructor(sheetRecord) {
      this._rec = sheetRecord;
    }

    getName() { return this._rec.name; }

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
      this._rec.data.push(arr.slice());
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

    getSheetByName(name) {
      const rec = this._rec.sheets[name];
      return rec ? new Sheet(rec) : null;
    }

    insertSheet(name) {
      if (!this._rec.sheets[name]) {
        this._rec.sheets[name] = { name, data: [], frozenRows: 0 };
        this._rec.sheetOrder.push(name);
      }
      return new Sheet(this._rec.sheets[name]);
    }

    getSheets() {
      return this._rec.sheetOrder.map((name) => new Sheet(this._rec.sheets[name]));
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
      hour12: false,
      weekday: 'long',
    });
    const partsArr = dtf.formatToParts(date);
    const get = (type) => partsArr.find((p) => p.type === type).value;
    let hour24 = parseInt(get('hour'), 10);
    if (hour24 === 24) hour24 = 0; // some locales format midnight as 24
    const minute = parseInt(get('minute'), 10);
    return {
      year: get('year'),
      month: parseInt(get('month'), 10),
      day: parseInt(get('day'), 10),
      weekday: get('weekday'),
      hour24,
      minute,
    };
  }

  const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];

  function pad2(n) { return String(n).padStart(2, '0'); }

  function applyPattern(pattern, parts) {
    let hour12 = parts.hour24 % 12;
    if (hour12 === 0) hour12 = 12;
    const ampm = parts.hour24 < 12 ? 'AM' : 'PM';
    switch (pattern) {
      case 'yyyy-MM-dd':
        return `${parts.year}-${pad2(parts.month)}-${pad2(parts.day)}`;
      case 'EEEE':
        return parts.weekday;
      case 'MMMM d, yyyy':
        return `${MONTH_NAMES[parts.month - 1]} ${parts.day}, ${parts.year}`;
      case 'h:mm a':
        return `${hour12}:${pad2(parts.minute)} ${ampm}`;
      default:
        // Best-effort fallback for any other pattern: substitute the tokens
        // we know about; leave anything else untouched.
        return pattern
          .replace(/yyyy/g, parts.year)
          .replace(/MMMM/g, MONTH_NAMES[parts.month - 1])
          .replace(/MM/g, pad2(parts.month))
          .replace(/dd/g, pad2(parts.day))
          .replace(/d/g, String(parts.day))
          .replace(/EEEE/g, parts.weekday)
          .replace(/hh/g, pad2(hour12))
          .replace(/h/g, String(hour12))
          .replace(/mm/g, pad2(parts.minute))
          .replace(/a/g, ampm);
    }
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

  // ---- ScriptApp -----------------------------------------------------------
  let nextTriggerId = 1;
  function makeTriggerBuilder(handlerFunctionName) {
    const spec = { handlerFunctionName, type: null };
    const timeBuilder = {
      atHour(h) { spec.atHour = h; return timeBuilder; },
      nearMinute(m) { spec.nearMinute = m; return timeBuilder; },
      everyDays(n) { spec.everyDays = n; return timeBuilder; },
      everyHours(n) { spec.everyHours = n; return timeBuilder; },
      everyMinutes(n) { spec.everyMinutes = n; return timeBuilder; },
      onWeekDay(d) { spec.onWeekDay = d; return timeBuilder; },
      inTimezone(tz) { spec.timeZone = tz; return timeBuilder; },
      create() {
        const trigger = {
          uid: 'trigger_' + (nextTriggerId++),
          handlerFunctionName,
          ...spec,
        };
        state.triggers.push(trigger);
        return trigger;
      },
    };
    return {
      timeBased() {
        spec.type = 'CLOCK';
        return timeBuilder;
      },
    };
  }

  const ScriptApp = {
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
  const Session = {
    getScriptTimeZone() { return 'America/Santiago'; },
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
    return record;
  }

  const MailApp = { sendEmail };
  const GmailApp = { sendEmail };

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
