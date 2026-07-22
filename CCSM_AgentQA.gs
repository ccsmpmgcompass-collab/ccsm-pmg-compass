/**
 * ============================================================
 * CCSM_AgentQA.gs — Q&A and Suggestion Agent
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of AgentQA.gs (docs/AgentQA.gs in PMG-Compass). Internal aqa_*
 * function names are kept identical to the Provo original so future diffs
 * stay readable. Handles form submissions from the PMG Compass
 * Suggestion/Question Form:
 *   For Suggestions: forwards to the mission's alerts inbox and sends a
 *     thank-you to the missionary — all Spanish.
 *   For Questions: loads the full KNOWLEDGE_BASE tab, passes it to Gemini in
 *     one call with a Spanish system prompt, and routes the answer by
 *     confidence:
 *       >= 7  -> confident answer emailed to the missionary
 *       5-6   -> hedged answer emailed + "contact us if this didn't help"
 *       < 5   -> escalate to leadership; leadership adds the answer to
 *                KNOWLEDGE_BASE
 *
 * SPANISH GEMINI PROMPT — every call to Gemini prepends the exact required
 * system-prompt prefix:
 *   'Responda siempre en español. Usted es PMG Compass, un asistente para
 *    la misión ' + getMissionName() + '. '
 * before the rest of the (also Spanish) prompt.
 *
 * KNOWLEDGE_BASE LANGUAGE FILTER — CCSM_TAB_SPECS' real KNOWLEDGE_BASE
 * header (CcsmData.gs, Task 2) is ID|Category|Question|Answer|Keywords|
 * Source|DateAdded|UseCount — 8 columns, no Language column (Task 2
 * deliberately dropped an earlier design-doc sketch that had one; see the
 * CCSM_TAB_SPECS header comment). aqa_loadKnowledgeBase() still checks for a
 * 'Language' column at runtime and filters to Language === 'ES' whenever it
 * IS present, so a future Language column (e.g. if the KB ever needs to
 * carry English rows too) works without a code change; on the current
 * 8-column schema the filter is simply a no-op.
 *
 * KNOWLEDGE_BASE seeding: unlike Provo, this file does NOT port
 * setupKnowledgeBase() (the Drive-JSON FAQ migration) — CCSM's KNOWLEDGE_BASE
 * content is seeded by CCSM_SeedContent.gs's seedCcsmKnowledgeBase() (a later
 * task). Run that first, then setupQA() to install the trigger.
 *
 * Config keys read from AGENT_CONFIG:
 *   SEND_FROM_EMAIL   — alerts inbox for escalations and suggestions
 *   GEMINI_QA_MODEL   — Gemini model for Q&A (separate quota from the Sunday
 *                       coaching chain's callGemini())
 *   NIGHTLY_FORM_LINK — optional, shown as a quick link in answer emails
 *   WEEKLY_FORM_LINK  — optional, shown as a quick link in answer emails
 *
 * Sheet tabs used:
 *   KNOWLEDGE_BASE — Q&A knowledge base (8 columns)
 *   SUGGESTIONS    — all incoming submissions (Question and Suggestion)
 *   AUDIT_LOG      — action log shared with other agents
 *
 * Helper prefix: aqa_ (all private helpers in this file, matching Provo).
 */


// ── Trigger setup ─────────────────────────────────────────────────────────────

/**
 * Installs an onFormSubmit trigger for onQAFormSubmit().
 * Safe to call multiple times — removes any existing triggers first.
 */
function setupQAFormTrigger() {
  deleteTriggerByName('onQAFormSubmit');
  ScriptApp.newTrigger('onQAFormSubmit')
    .forSpreadsheet(SpreadsheetApp.getActive())
    .onFormSubmit()
    .create();
  Logger.log('AgentQA: onFormSubmit trigger installed for onQAFormSubmit().');
}


// ── Main agent function ───────────────────────────────────────────────────────

/**
 * Entry point — called automatically by the onFormSubmit trigger.
 * Form field order (Timestamp is field 0, auto-populated by Forms):
 *   0: Timestamp
 *   1: ¿Es una pregunta o una sugerencia?
 *   2: Nombre    (sección de sugerencia)
 *   3: Correo    (sección de sugerencia)
 *   4: Mensaje   (sección de sugerencia)
 *   5: Nombre    (sección de pregunta)
 *   6: Correo    (sección de pregunta)
 *   7: Mensaje   (sección de pregunta)
 *
 * @param {GoogleAppsScript.Events.SheetsOnFormSubmit} e
 */
function onQAFormSubmit(e) {
  try {
    // ── Quota gate ─────────────────────────────────────────────────────────────
    var quota = MailApp.getRemainingDailyQuota();
    if (quota < 20) {
      Logger.log('AgentQA: daily email quota too low (' + quota + ') — aborting.');
      aqa_logAudit('QUOTA_LOW', 'onQAFormSubmit', 0, '', 'Remaining quota: ' + quota);
      return;
    }

    // ── Parse form values ──────────────────────────────────────────────────────
    var values    = e.values;
    var timestamp = new Date();
    var type      = String(values[1] || '').trim();
    var typeLower = type.toLowerCase();
    var isSuggestion = typeLower.indexOf('sugerencia') !== -1 || typeLower.indexOf('suggestion') !== -1;
    var isQuestion   = typeLower.indexOf('pregunta')   !== -1 || typeLower.indexOf('question')   !== -1;

    // ── Ignore submissions from OTHER forms ────────────────────────────────────
    // An installable onFormSubmit trigger on a spreadsheet-bound script fires
    // for EVERY form linked to the spreadsheet (nightly, weekly, etc.), not
    // just the Q&A/Suggestion form — bail BEFORE persisting so SUGGESTIONS
    // never gets polluted with non-Q/S submissions.
    if (!isSuggestion && !isQuestion) {
      Logger.log('AgentQA: ignoring non-Q/S submission (type="' + type + '").');
      aqa_logAudit('UNKNOWN_TYPE', 'ignored', 0, '', 'type=' + type);
      return;
    }

    var name, email, message;
    if (isSuggestion) {
      name    = String(values[2] || '').trim();
      email   = String(values[3] || '').trim();
      message = String(values[4] || '').trim();
    } else {
      name    = String(values[5] || '').trim();
      email   = String(values[6] || '').trim();
      message = String(values[7] || '').trim();
    }

    Logger.log('AgentQA: received ' + type + ' from ' + name + ' <' + email + '>');

    var sendFrom = getConfig('SEND_FROM_EMAIL') || '';

    // ── Persist to SUGGESTIONS tab ─────────────────────────────────────────────
    appendRow('SUGGESTIONS', [
      Utilities.formatDate(timestamp, getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss'),
      type,
      name,
      email,
      message
    ]);

    aqa_logAudit(type, 'received', 1, '', name + ' / ' + email);

    if (isSuggestion) {
      aqa_handleSuggestion(name, email, message, timestamp, sendFrom);
    } else {
      aqa_handleQuestion(name, email, message, timestamp, sendFrom);
    }

  } catch (err) {
    Logger.log('AgentQA ERROR: ' + err.message + '\n' + (err.stack || ''));
    aqa_logAudit('ERROR', 'onQAFormSubmit', 0, '', err.message);
  }
}


// ── Suggestion handler ────────────────────────────────────────────────────────

/**
 * Forwards a suggestion to the alerts inbox and thanks the missionary.
 */
function aqa_handleSuggestion(name, email, message, timestamp, sendFrom) {
  var tsFormatted = Utilities.formatDate(timestamp, getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss');

  if (sendFrom) {
    var mpSubject = 'Nueva Sugerencia de Misionero — ' + name;
    var mpBody    = aqa_buildSuggestionForwardBody(name, email, message, tsFormatted);
    sendEmail(sendFrom, mpSubject, mpBody, 'AgentQA');
    Logger.log('AgentQA: suggestion forwarded to alerts inbox.');
  } else {
    Logger.log('AgentQA: SEND_FROM_EMAIL not configured — suggestion not forwarded.');
  }

  if (email) {
    var tySubject = 'Gracias por su sugerencia';
    var tyBody    = aqa_buildSuggestionThankYouBody(name, message);
    sendEmail(email, tySubject, tyBody, 'AgentQA');
    Logger.log('AgentQA: thank-you email sent to ' + email);
  }

  aqa_logAudit('Suggestion', 'forwarded+thanked', 2, '', name + ' / ' + email);
}


// ── Question handler ──────────────────────────────────────────────────────────

/**
 * Loads the KNOWLEDGE_BASE, calls Gemini with full context, and routes the
 * answer to the missionary based on the confidence score Gemini returns.
 *
 * Routing tiers:
 *   confidence >= 7 -> confident answer email
 *   confidence 5-6  -> hedged answer email
 *   confidence < 5  -> escalate to leadership + pending notification
 *   result === null -> escalate to leadership + pending notification
 */
function aqa_handleQuestion(name, email, message, timestamp, sendFrom) {
  var kbEntries = aqa_loadKnowledgeBase();
  Logger.log('AgentQA: KNOWLEDGE_BASE loaded — ' + kbEntries.length + ' entries.');

  var result = null;
  try {
    result = aqa_askGeminiWithKB(message, kbEntries);
  } catch (geminiErr) {
    Logger.log('AgentQA: Gemini call threw unexpectedly — ' + geminiErr.message);
  }

  var confidence = result ? parseInt(result.confidence, 10) : 0;
  var matchedIds = (result && Array.isArray(result.matchedIds)) ? result.matchedIds : [];
  var tier       = 'unknown';

  if (result && confidence >= 7) {
    tier = 'confident';
    aqa_sendConfidentAnswer(name, email, message, result.answer, sendFrom);
    aqa_logAudit('Question', 'confident_answer:' + matchedIds.join(','), 1, '', name + ' / ' + email);

  } else if (result && confidence >= 5) {
    tier = 'hedged';
    aqa_sendHedgedAnswer(name, email, message, result.answer, sendFrom);
    aqa_logAudit('Question', 'hedged_answer:' + matchedIds.join(','), 1, '', name + ' / ' + email);

  } else {
    tier = 'escalate';
    if (sendFrom) {
      var escSubject = 'Pregunta Sin Responder de ' + name + ' — Agregar a la Base de Conocimiento';
      var escBody    = aqa_buildEscalationBody(name, email, message);
      sendEmail(sendFrom, escSubject, escBody, 'AgentQA');
      Logger.log('AgentQA: unanswered question escalated to alerts inbox.');
    } else {
      Logger.log('AgentQA: SEND_FROM_EMAIL not configured — escalation skipped.');
    }
    if (email) {
      var pendSubject = 'Hemos recibido su pregunta';
      var pendBody    = aqa_buildPendingAnswerBody(name, message);
      sendEmail(email, pendSubject, pendBody, 'AgentQA');
      Logger.log('AgentQA: pending-answer notification sent to ' + email);
    }
    aqa_logAudit('Question', 'escalated:confidence=' + confidence, 2, '', name + ' / ' + email);
  }

  Logger.log('AgentQA: routing tier=' + tier + ' | confidence=' + confidence +
    ' | matched=' + matchedIds.join(','));

  if (matchedIds.length > 0 && confidence >= 5) {
    aqa_incrementUseCount(matchedIds);
  }
}


// ── Knowledge base loader ─────────────────────────────────────────────────────

/**
 * Reads all rows from the KNOWLEDGE_BASE tab and returns them as plain
 * objects. Column order: ID | Category | Question | Answer | Keywords |
 * Source | DateAdded | UseCount. If a 'Language' column exists (not present
 * in the current CCSM schema — see file header note), rows are additionally
 * filtered to Language === 'ES'. Returns [] (never null) on any failure.
 */
function aqa_loadKnowledgeBase() {
  try {
    var sheet = getTab('KNOWLEDGE_BASE');
    if (!sheet || sheet.getLastRow() < 2) {
      Logger.log('AgentQA: KNOWLEDGE_BASE tab is empty or missing.');
      return [];
    }
    var data    = sheet.getDataRange().getValues();
    var headers = data[0].map(function(h) { return String(h).trim(); });
    var langCol = headers.indexOf('Language'); // -1 on the current 8-column schema

    return data.slice(1).map(function(row) {
      return {
        id:        String(row[0] || '').trim(),
        category:  String(row[1] || '').trim(),
        question:  String(row[2] || '').trim(),
        answer:    String(row[3] || '').trim(),
        keywords:  String(row[4] || '').trim(),
        source:    String(row[5] || '').trim(),
        dateAdded: String(row[6] || '').trim(),
        useCount:  parseInt(row[7], 10) || 0,
        language:  langCol !== -1 ? String(row[langCol] || '').trim() : ''
      };
    }).filter(function(entry) {
      if (entry.question.length === 0 || entry.answer.length === 0) return false;
      if (langCol !== -1 && entry.language && entry.language !== 'ES') return false;
      return true;
    });
  } catch (err) {
    Logger.log('AgentQA: error loading KNOWLEDGE_BASE — ' + err.message);
    return [];
  }
}

/**
 * Increments the UseCount column (col H, 1-based = 8) for each matched entry
 * ID. Called only when a confident or hedged answer is sent. Wrapped
 * defensively — a write failure here must never abort the email send.
 */
function aqa_incrementUseCount(ids) {
  if (!ids || ids.length === 0) return;
  try {
    var sheet   = getTab('KNOWLEDGE_BASE');
    var lastRow = sheet.getLastRow();
    if (lastRow < 2) return;

    var idRange = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
    var idSet   = {};
    ids.forEach(function(id) { idSet[String(id).trim()] = true; });

    idRange.forEach(function(rowArr, i) {
      var rowId = String(rowArr[0]).trim();
      if (!idSet[rowId]) return;
      var useCountCell = sheet.getRange(i + 2, 8);
      var currentCount = parseInt(useCountCell.getValue(), 10) || 0;
      useCountCell.setValue(currentCount + 1);
    });

    SpreadsheetApp.flush();
    Logger.log('AgentQA: UseCount incremented for: ' + ids.join(', '));
  } catch (err) {
    Logger.log('AgentQA: UseCount increment failed (non-fatal) — ' + err.message);
  }
}


// ── Gemini integration ────────────────────────────────────────────────────────

/**
 * Sends the full KNOWLEDGE_BASE + question to Gemini and returns a parsed
 * confidence object: {answer, confidence, reasoning, matchedIds}.
 * Returns null on any API failure or JSON parse failure — callers check for
 * null and escalate accordingly.
 */
function aqa_askGeminiWithKB(question, kbEntries) {
  if (!kbEntries || kbEntries.length === 0) {
    Logger.log('AgentQA: KNOWLEDGE_BASE is empty — cannot call Gemini, returning null.');
    return null;
  }

  var missionName = getMissionName();
  var resolvedEntries = kbEntries.map(function(entry) {
    return {
      id:       entry.id,
      category: entry.category,
      question: entry.question,
      answer:   String(entry.answer || '').replace(/\{mission_name\}/g, missionName)
    };
  });

  var kbText = resolvedEntries.map(function(entry) {
    return 'ID: ' + entry.id + '\n' +
           'Categoría: ' + entry.category + '\n' +
           'P: ' + entry.question + '\n' +
           'R: ' + entry.answer;
  }).join('\n\n---\n\n');

  var prompt = aqa_buildGeminiPrompt(question, kbText);
  var model  = getConfig('GEMINI_QA_MODEL') || 'gemini-2.5-flash';

  var raw = aqa_callGeminiQA_(prompt, model, 800);
  if (!raw) return null;

  var cleaned = raw
    .replace(/^```json\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/```\s*$/i, '')
    .trim();

  try {
    var parsed = JSON.parse(cleaned);

    if (typeof parsed.answer     !== 'string') parsed.answer     = '';
    if (typeof parsed.confidence !== 'number') parsed.confidence = parseInt(parsed.confidence, 10) || 0;
    if (!Array.isArray(parsed.matchedIds))      parsed.matchedIds = [];
    if (typeof parsed.reasoning  !== 'string') parsed.reasoning  = '';

    Logger.log('AgentQA: Gemini confidence=' + parsed.confidence +
      ' | reasoning=' + parsed.reasoning +
      ' | matchedIds=' + parsed.matchedIds.join(','));

    return parsed;
  } catch (parseErr) {
    Logger.log('AgentQA: JSON parse failed — raw Gemini response: ' + raw.substring(0, 500));
    return null;
  }
}

/**
 * Builds the full Gemini prompt for a knowledge-base-grounded Q&A call.
 * Every call MUST prepend the exact required Spanish system-prompt prefix.
 */
function aqa_buildGeminiPrompt(question, kbText) {
  var missionName = getMissionName();
  var spanishPrefix = 'Responda siempre en español. Usted es PMG Compass, un asistente para la misión ' + missionName + '. ';

  var body = [
    'Su función es responder preguntas de los misioneros sobre PMG Compass —',
    'el sistema de análisis e informes de la misión.',
    '',
    'REGLAS IMPORTANTES — siga todas sin excepción:',
    '1. Nunca use la palabra "investigador". Diga siempre "amigo" o "amigos".',
    '2. Escriba siempre con un tono cristiano: alentador, amable, honesto y edificante.',
    '3. Base su respuesta ÚNICAMENTE en la Base de Conocimiento proporcionada abajo.',
    '4. No agregue firma ni despedida — la plantilla de correo ya la incluye.',
    '5. Si un misionario pregunta por el enlace de un formulario, incluya la URL exacta de la base de conocimiento.',
    '6. Su respuesta DEBE ser JSON válido. No incluya markdown, bloques de código ni',
    '   texto de explicación fuera del objeto JSON.',
    '',
    'PREGUNTA DEL MISIONERO:',
    question,
    '',
    'BASE DE CONOCIMIENTO (use SOLO esta información para responder):',
    kbText,
    '',
    'FORMATO DE RESPUESTA — devuelva exactamente esta estructura JSON, nada más:',
    '{',
    '  "answer": "Su respuesta aquí — de 2 a 5 oraciones, escrita directamente al misionero.",',
    '  "confidence": 8,',
    '  "reasoning": "Una oración explicando qué entradas de la base de conocimiento coincidieron y por qué.",',
    '  "matchedIds": ["kb-002", "kb-032"]',
    '}',
    '',
    'GUÍA DE PUNTUACIÓN DE CONFIANZA:',
    '10 — La base de conocimiento tiene una respuesta directa y textual.',
    '8-9 — La base de conocimiento cubre claramente este tema con alta certeza.',
    '6-7 — Cubierto parcialmente; la respuesta es razonable pero no definitiva.',
    '4-5 — Apenas cubierto; se requiere inferencia significativa.',
    '1-3 — No cubierto. Establezca answer en "" y matchedIds en [].',
    '',
    'Si la confianza es menor a 5, establezca "answer" en "" y "matchedIds" en [].'
  ].join('\n');

  return spanishPrefix + body;
}

/**
 * Direct Gemini API call for Q&A — uses GEMINI_QA_MODEL so quota is
 * independent of the Sunday coaching chain's callGemini(). Retries once on
 * per-minute 429 errors and once on a 503.
 *
 * @returns {string|null} Raw response text, or null on failure
 */
function aqa_callGeminiQA_(prompt, model, maxTokens) {
  var apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!apiKey) {
    Logger.log('AgentQA: GEMINI_API_KEY not set in Script Properties.');
    return null;
  }

  var outputTokens = maxTokens || 500;
  var url = 'https://generativelanguage.googleapis.com/v1beta/models/' +
            model + ':generateContent?key=' + apiKey;

  var payload = JSON.stringify({
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { maxOutputTokens: outputTokens, temperature: 0.4 }
  });

  var options = {
    method:             'post',
    contentType:        'application/json',
    payload:            payload,
    muteHttpExceptions: true
  };

  var resp = UrlFetchApp.fetch(url, options);
  var code = resp.getResponseCode();
  var text = resp.getContentText();

  if (code === 200) {
    var json   = JSON.parse(text);
    var answer = json.candidates[0].content.parts[0].text.trim();
    Logger.log('AgentQA: Gemini QA responded via ' + model);
    return answer || null;
  }

  if (code === 429) {
    var retryMatch = text.match(/retry.*?(\d+(\.\d+)?)s/i);
    var retrySec   = retryMatch ? parseFloat(retryMatch[1]) : null;

    if (retrySec !== null && retrySec < 120) {
      var waitMs = (Math.ceil(retrySec) + 3) * 1000;
      Logger.log('AgentQA: Gemini QA per-minute limit — waiting ' +
        Math.ceil(retrySec + 3) + 's then retrying...');
      Utilities.sleep(waitMs);
      var resp2 = UrlFetchApp.fetch(url, options);
      var code2 = resp2.getResponseCode();
      if (code2 === 200) {
        var json2   = JSON.parse(resp2.getContentText());
        var answer2 = json2.candidates[0].content.parts[0].text.trim();
        Logger.log('AgentQA: Gemini QA retry succeeded.');
        return answer2 || null;
      }
      Logger.log('AgentQA: Gemini QA retry failed — HTTP ' + code2);
      return null;
    }

    Logger.log('AgentQA: Gemini QA daily limit or parse error — not retrying. Raw: ' +
      text.substring(0, 300));
    return null;
  }

  if (code === 503) {
    Logger.log('AgentQA: Gemini QA 503 (service unavailable) — waiting 10s then retrying...');
    Utilities.sleep(10000);
    var resp3 = UrlFetchApp.fetch(url, options);
    var code3 = resp3.getResponseCode();
    if (code3 === 200) {
      var json3   = JSON.parse(resp3.getContentText());
      var answer3 = json3.candidates[0].content.parts[0].text.trim();
      Logger.log('AgentQA: Gemini QA 503 retry succeeded.');
      return answer3 || null;
    }
    Logger.log('AgentQA: Gemini QA 503 retry failed — HTTP ' + code3);
    return null;
  }

  Logger.log('AgentQA: Gemini QA error — HTTP ' + code + ' on ' + model);
  return null;
}


// ── Email body builders (Spanish) ─────────────────────────────────────────────

function aqa_quickLinksHtml() {
  var nightlyLink = getConfig('NIGHTLY_FORM_LINK') || '';
  var weeklyLink  = getConfig('WEEKLY_FORM_LINK')  || '';
  if (!nightlyLink && !weeklyLink) return '';

  var html = '<p style="margin-top:16px;"><strong>Enlaces Rápidos:</strong></p><ul>';
  if (nightlyLink) html += '<li><a href="' + aqa_esc(nightlyLink) + '">Formulario de Informe Nocturno</a></li>';
  if (weeklyLink)  html += '<li><a href="' + aqa_esc(weeklyLink)  + '">Formulario de Informe Semanal</a></li>';
  html += '</ul>';
  return html;
}

/**
 * HTML email body for a confident Gemini answer (confidence >= 7).
 */
function aqa_buildConfidentAnswerBody(name, originalQuestion, answer) {
  return [
    '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;">',
    '<h2 style="color:#1a4d7c;">Su Pregunta a PMG Compass</h2>',
    '<p>Estimado/a ' + aqa_esc(name) + ',</p>',
    '<p>Gracias por su pregunta. Esto es lo que encontramos:</p>',
    '<p style="margin-top:16px;"><strong>Su pregunta:</strong></p>',
    '<blockquote style="margin:0;padding:10px 14px;background:#f0f4f8;border-left:4px solid #aac4e0;font-style:italic;">',
    aqa_esc(originalQuestion).replace(/\n/g, '<br>'),
    '</blockquote>',
    '<p style="margin-top:20px;"><strong>Respuesta:</strong></p>',
    '<blockquote style="margin:0;padding:12px 16px;background:#f9f9f9;border-left:4px solid #1a4d7c;">',
    aqa_esc(answer).replace(/\n/g, '<br>'),
    '</blockquote>',
    aqa_quickLinksHtml(),
    '<p style="margin-top:24px;">Si tiene más preguntas, escríbanos a ',
    '<a href="mailto:' + aqa_esc(getConfig('SEND_FROM_EMAIL') || '') + '">' + aqa_esc(getConfig('SEND_FROM_EMAIL') || '') + '</a>.</p>',
    '<p>¡Sigan adelante!<br><strong>Equipo de PMG Compass</strong></p>',
    '</body></html>'
  ].join('\n');
}

/**
 * HTML email body for a hedged Gemini answer (confidence 5-6).
 */
function aqa_buildHedgedAnswerBody(name, originalQuestion, answer) {
  var sendFrom = getConfig('SEND_FROM_EMAIL') || '';
  return [
    '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;">',
    '<h2 style="color:#1a4d7c;">Su Pregunta a PMG Compass</h2>',
    '<p>Estimado/a ' + aqa_esc(name) + ',</p>',
    '<p>Gracias por su pregunta. Esto es lo que encontramos:</p>',
    '<p style="margin-top:16px;"><strong>Su pregunta:</strong></p>',
    '<blockquote style="margin:0;padding:10px 14px;background:#f0f4f8;border-left:4px solid #aac4e0;font-style:italic;">',
    aqa_esc(originalQuestion).replace(/\n/g, '<br>'),
    '</blockquote>',
    '<p style="margin-top:20px;"><strong>Respuesta:</strong></p>',
    '<blockquote style="margin:0;padding:12px 16px;background:#f9f9f9;border-left:4px solid #1a4d7c;">',
    aqa_esc(answer).replace(/\n/g, '<br>'),
    '</blockquote>',
    '<p style="margin-top:16px;color:#555;font-size:13px;">',
    'Esta es nuestra mejor coincidencia para su pregunta. Si no respondió completamente lo que necesitaba,',
    'por favor escriba a <a href="mailto:' + aqa_esc(sendFrom) + '">' + aqa_esc(sendFrom) + '</a>',
    'y le daremos seguimiento personalmente.',
    '</p>',
    aqa_quickLinksHtml(),
    '<p style="margin-top:24px;">Si tiene más preguntas, escríbanos a ',
    '<a href="mailto:' + aqa_esc(sendFrom) + '">' + aqa_esc(sendFrom) + '</a>.</p>',
    '<p>¡Sigan adelante!<br><strong>Equipo de PMG Compass</strong></p>',
    '</body></html>'
  ].join('\n');
}

/**
 * HTML email body notifying the alerts inbox of an unanswered question.
 */
function aqa_buildEscalationBody(name, email, message) {
  return [
    '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;">',
    '<h2 style="color:#c0392b;">Pregunta de Misionero Sin Responder</h2>',
    '<p>PMG Compass recibió una pregunta que no pudo responderse desde la base de conocimiento.',
    'Esta pregunta requiere una respuesta personal de parte del liderazgo.</p>',
    '<table style="border-collapse:collapse;width:100%;margin:16px 0;">',
    '  <tr><td style="padding:8px;font-weight:bold;background:#f0f4f8;width:140px;">Nombre</td>',
    '      <td style="padding:8px;border-bottom:1px solid #e0e0e0;">' + aqa_esc(name) + '</td></tr>',
    '  <tr><td style="padding:8px;font-weight:bold;background:#f0f4f8;">Correo</td>',
    '      <td style="padding:8px;border-bottom:1px solid #e0e0e0;"><a href="mailto:' +
      aqa_esc(email) + '">' + aqa_esc(email) + '</a></td></tr>',
    '</table>',
    '<h3 style="color:#c0392b;">Su Pregunta</h3>',
    '<blockquote style="margin:0;padding:12px 16px;background:#fdf2f2;border-left:4px solid #c0392b;font-style:italic;">',
    aqa_esc(message).replace(/\n/g, '<br>'),
    '</blockquote>',
    '<div style="margin-top:24px;padding:16px;background:#fff8e1;border-left:4px solid #f59e0b;border-radius:4px;">',
    '<strong>ACCIÓN — Enseñe esta respuesta a la IA:</strong>',
    '<p style="margin:8px 0 0;">Abra COMPASS_CCSM → pestaña <strong>KNOWLEDGE_BASE</strong> y agregue una nueva fila al final.',
    'Use el siguiente ID secuencial (revise la última fila). Complete las 8 columnas:<br>',
    '<code>ID | Category | Question | Answer | Keywords | Source | DateAdded | UseCount</code><br>',
    'Establezca <code>Source = LEADERSHIP-ADDED</code> y <code>UseCount = 0</code>.',
    'La IA la usará automáticamente en la próxima pregunta — no se requiere cambio de código.</p>',
    '</div>',
    '<p style="margin-top:24px;color:#666;font-size:12px;">',
    'Se notificó al misionario que su pregunta está siendo revisada.',
    '</p>',
    '</body></html>'
  ].join('\n');
}

/**
 * HTML body letting the missionary know their question is being reviewed.
 */
function aqa_buildPendingAnswerBody(name, message) {
  return [
    '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;">',
    '<h2 style="color:#1a4d7c;">Hemos Recibido su Pregunta</h2>',
    '<p>Estimado/a ' + aqa_esc(name) + ',</p>',
    '<p>Gracias por escribirnos. Recibimos su pregunta:</p>',
    '<blockquote style="margin:16px 0;padding:12px 16px;background:#f9f9f9;border-left:4px solid #1a4d7c;font-style:italic;">',
    aqa_esc(message).replace(/\n/g, '<br>'),
    '</blockquote>',
    '<p>Queremos asegurarnos de darle la respuesta más precisa posible, así que la hemos pasado',
    'al liderazgo de la misión para su revisión. Puede esperar una respuesta personal pronto.</p>',
    '<p>¡Gracias por su paciencia!</p>',
    '<p>Con aprecio,<br><strong>Equipo de PMG Compass</strong></p>',
    '</body></html>'
  ].join('\n');
}

/**
 * HTML email body forwarding a suggestion to the alerts inbox.
 */
function aqa_buildSuggestionForwardBody(name, email, message, tsFormatted) {
  return [
    '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;">',
    '<h2 style="color:#1a4d7c;">Nueva Sugerencia de Misionero</h2>',
    '<p>Un misionario ha enviado una sugerencia a través de PMG Compass.</p>',
    '<table style="border-collapse:collapse;width:100%;margin:16px 0;">',
    '  <tr><td style="padding:8px;font-weight:bold;background:#f0f4f8;width:140px;">Nombre</td>',
    '      <td style="padding:8px;border-bottom:1px solid #e0e0e0;">' + aqa_esc(name) + '</td></tr>',
    '  <tr><td style="padding:8px;font-weight:bold;background:#f0f4f8;">Correo</td>',
    '      <td style="padding:8px;border-bottom:1px solid #e0e0e0;"><a href="mailto:' +
      aqa_esc(email) + '">' + aqa_esc(email) + '</a></td></tr>',
    '  <tr><td style="padding:8px;font-weight:bold;background:#f0f4f8;">Enviado</td>',
    '      <td style="padding:8px;border-bottom:1px solid #e0e0e0;">' + aqa_esc(tsFormatted) + '</td></tr>',
    '</table>',
    '<h3 style="color:#1a4d7c;">Su Sugerencia</h3>',
    '<blockquote style="margin:0;padding:12px 16px;background:#f9f9f9;border-left:4px solid #1a4d7c;font-style:italic;">',
    aqa_esc(message).replace(/\n/g, '<br>'),
    '</blockquote>',
    '<p style="margin-top:24px;color:#666;font-size:12px;">',
    'Este mensaje fue generado automáticamente por PMG Compass AgentQA.',
    '</p>',
    '</body></html>'
  ].join('\n');
}

/**
 * HTML thank-you body for the missionary who submitted a suggestion.
 */
function aqa_buildSuggestionThankYouBody(name, message) {
  return [
    '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;">',
    '<h2 style="color:#1a4d7c;">¡Gracias por su Sugerencia!</h2>',
    '<p>Estimado/a ' + aqa_esc(name) + ',</p>',
    '<p>Gracias por tomarse el tiempo de compartir sus ideas con nosotros. Apreciamos mucho',
    'su retroalimentación y el esfuerzo que puso en ayudar a mejorar PMG Compass para toda la misión.</p>',
    '<p>Su sugerencia ha sido enviada al liderazgo de la misión para su revisión:</p>',
    '<blockquote style="margin:16px 0;padding:12px 16px;background:#f9f9f9;border-left:4px solid #1a4d7c;font-style:italic;">',
    aqa_esc(message).replace(/\n/g, '<br>'),
    '</blockquote>',
    '<p>Le daremos seguimiento si tenemos preguntas o cuando se tome alguna acción. ¡Sigan con el gran trabajo!</p>',
    '<p>Con gratitud,<br><strong>Equipo de PMG Compass</strong></p>',
    '</body></html>'
  ].join('\n');
}


// ── Email dispatch wrappers ───────────────────────────────────────────────────

function aqa_sendConfidentAnswer(name, email, originalQuestion, answer, sendFrom) {
  if (!email) {
    Logger.log('AgentQA: cannot send confident answer — no email address.');
    return;
  }
  var subject = 'Su Pregunta a PMG Compass';
  var body    = aqa_buildConfidentAnswerBody(name, originalQuestion, answer);
  sendEmail(email, subject, body, 'AgentQA');
  Logger.log('AgentQA: confident answer sent to ' + email);
}

function aqa_sendHedgedAnswer(name, email, originalQuestion, answer, sendFrom) {
  if (!email) {
    Logger.log('AgentQA: cannot send hedged answer — no email address.');
    return;
  }
  var subject = 'Su Pregunta a PMG Compass';
  var body    = aqa_buildHedgedAnswerBody(name, originalQuestion, answer);
  sendEmail(email, subject, body, 'AgentQA');
  Logger.log('AgentQA: hedged answer sent to ' + email);
}


// ── Audit helper ──────────────────────────────────────────────────────────────

/**
 * Appends a row to AUDIT_LOG. Columns: Timestamp | Agent | Action |
 * Rows_Affected | Area | Notes.
 */
function aqa_logAudit(action, detail, rowsAffected, area, notes) {
  try {
    var ts = Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss');
    appendRow('AUDIT_LOG', [
      ts,
      'AgentQA',
      action + (detail ? ':' + detail : ''),
      rowsAffected,
      area  || '',
      notes || ''
    ]);
  } catch (auditErr) {
    Logger.log('AgentQA: audit log write failed — ' + auditErr.message);
  }
}


// ── HTML escape utility ───────────────────────────────────────────────────────

function aqa_esc(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


// ── Setup / verification functions ────────────────────────────────────────────

/**
 * One-time setup for AgentQA. Run AFTER CCSM_SeedContent.gs's
 * seedCcsmKnowledgeBase() has been run.
 *
 * Does three things:
 *   1. Creates the SUGGESTIONS tab (with headers) if it does not already exist.
 *   2. Installs the onFormSubmit trigger for onQAFormSubmit().
 *   3. Verifies that KNOWLEDGE_BASE tab exists and has at least 1 entry.
 *
 * Safe to re-run — duplicate triggers are removed before reinstalling, and
 * existing tabs are left untouched.
 */
function setupQA() {
  Logger.log('======= AgentQA Setup =======');
  var allPassed = true;

  try {
    var ss  = SpreadsheetApp.getActive();
    var tab = ss.getSheetByName('SUGGESTIONS');
    if (tab && tab.getLastRow() > 0) {
      Logger.log('[PASS] SUGGESTIONS tab already exists — left untouched.');
    } else {
      if (!tab) tab = ss.insertSheet('SUGGESTIONS');
      tab.appendRow(['Timestamp', 'Type', 'Name', 'Email', 'Message']);
      tab.getRange(1, 1, 1, 5).setFontWeight('bold');
      Logger.log('[PASS] SUGGESTIONS tab created with headers.');
    }
  } catch (e) {
    Logger.log('[FAIL] Could not create SUGGESTIONS tab: ' + e.message);
    allPassed = false;
  }

  try {
    setupQAFormTrigger();
    Logger.log('[PASS] onQAFormSubmit trigger installed.');
  } catch (e) {
    Logger.log('[FAIL] Could not install form trigger: ' + e.message);
    allPassed = false;
  }

  try {
    var kbEntries = aqa_loadKnowledgeBase();
    if (kbEntries.length > 0) {
      Logger.log('[PASS] KNOWLEDGE_BASE loaded — ' + kbEntries.length + ' entries.');
    } else {
      Logger.log('[FAIL] KNOWLEDGE_BASE tab is empty or missing. Run seedCcsmKnowledgeBase() first.');
      allPassed = false;
    }
  } catch (e) {
    Logger.log('[FAIL] Error loading KNOWLEDGE_BASE: ' + e.message);
    allPassed = false;
  }

  try {
    var qaModel = getConfig('GEMINI_QA_MODEL') || '';
    if (qaModel) {
      Logger.log('[PASS] GEMINI_QA_MODEL = ' + qaModel);
    } else {
      Logger.log('[WARN] GEMINI_QA_MODEL not set in AGENT_CONFIG — will default to gemini-2.5-flash.');
    }
  } catch (e) {
    Logger.log('[WARN] Could not read GEMINI_QA_MODEL: ' + e.message);
  }

  Logger.log('');
  Logger.log(allPassed ? 'ALL CHECKS PASSED — AgentQA is ready.' : 'ONE OR MORE CHECKS FAILED — review the log above and fix before launch.');
  Logger.log('======= Setup Complete =======');
}


// ── Test functions ────────────────────────────────────────────────────────────

/**
 * Dry-run test — verifies KB loading and confidence routing without sending
 * emails. Run manually from the Apps Script editor.
 */
function testQAAgent() {
  Logger.log('======= AgentQA DRY-RUN TEST =======');

  Logger.log('Test 1 — Load KNOWLEDGE_BASE');
  var kbEntries = aqa_loadKnowledgeBase();
  Logger.log('  Entries loaded: ' + kbEntries.length);
  if (kbEntries.length === 0) {
    Logger.log('  WARNING: No entries loaded. Run seedCcsmKnowledgeBase() first.');
  } else {
    var cats = {};
    kbEntries.forEach(function(e) { cats[e.category] = (cats[e.category] || 0) + 1; });
    Logger.log('  Category distribution:');
    Object.keys(cats).forEach(function(cat) { Logger.log('    ' + cat + ': ' + cats[cat]); });
  }

  Logger.log('');
  Logger.log('Test 2 — Confidence routing tiers (no Gemini call)');
  [{c:9, label:'confident'}, {c:6, label:'hedged'}, {c:4, label:'escalate'}, {c:0, label:'escalate (null)'}]
    .forEach(function(t) {
      var tier = t.c >= 7 ? 'confident' : (t.c >= 5 ? 'hedged' : 'escalate');
      Logger.log('  confidence=' + t.c + ' -> tier=' + tier +
        ' | expected=' + t.label + ' | ' + (tier === t.label ? 'OK' : 'MISMATCH'));
    });

  Logger.log('');
  Logger.log('======= DRY-RUN COMPLETE (no emails sent, no Gemini calls) =======');
}

/**
 * Live test — calls Gemini with a real question and logs the full response.
 * Run manually to verify the Gemini integration. Consumes one Gemini API call.
 */
function testGeminiFallback() {
  Logger.log('======= Gemini Fallback Test =======');

  var kbEntries = aqa_loadKnowledgeBase();
  if (kbEntries.length === 0) {
    Logger.log('FAIL: KNOWLEDGE_BASE is empty or missing. Run seedCcsmKnowledgeBase() first.');
    return;
  }
  Logger.log('KNOWLEDGE_BASE loaded: ' + kbEntries.length + ' entries.');

  var question = '¿Cuándo debo completar el formulario nocturno?';
  Logger.log('Test question: "' + question + '"');

  try {
    var result = aqa_askGeminiWithKB(question, kbEntries);
    if (!result) {
      Logger.log('RESULT: null — Gemini call failed or JSON parse failed. Would escalate.');
      return;
    }
    Logger.log('--- Gemini Response ---');
    Logger.log('confidence:  ' + result.confidence);
    Logger.log('matchedIds:  ' + (result.matchedIds || []).join(', '));
    Logger.log('reasoning:   ' + result.reasoning);
    Logger.log('answer:      ' + result.answer);
  } catch (e) {
    Logger.log('ERROR: ' + e.message);
  }

  Logger.log('======= Test Complete =======');
}


// ── Mission-leadership-approval email bridge ──────────────────────────────────

/**
 * Emails SEND_FROM_EMAIL once for each SUGGESTIONS_REVIEW row that has
 * reached Status='Final Approval' or Status='Done' — i.e. once someone has
 * actually ACTED on it. Deduped by EmailedToCompass, so an item can only
 * ever trigger one email. Runs on a ~10-minute time trigger.
 *
 * Reads ONLY the SUGGESTIONS_REVIEW tab (the app's triage state), never the
 * form-linked SUGGESTIONS response sheet.
 *   SUGGESTIONS_REVIEW columns: Key, Kind, Name, Email, Message, Status,
 *   ReviewedBy, ReviewedAt, ReviewerNote, EmailedToCompass
 */
function notifyAcceptedSuggestions() {
  var TO = getConfig('SEND_FROM_EMAIL') || '';
  var TRIGGER_STATUSES = ['Final Approval', 'Done'];
  var ss  = SpreadsheetApp.getActive();
  var tab = ss.getSheetByName('SUGGESTIONS_REVIEW');
  if (!tab) { Logger.log('notifyAcceptedSuggestions: no SUGGESTIONS_REVIEW tab.'); return; }
  if (!TO) { Logger.log('notifyAcceptedSuggestions: SEND_FROM_EMAIL not configured — skipping.'); return; }

  var values = tab.getDataRange().getValues();
  if (values.length < 2) return;

  var header = values[0].map(function(h) { return String(h).trim(); });
  var col = {};
  ['Kind', 'Name', 'Email', 'Message', 'Status', 'ReviewedBy', 'ReviewedAt',
   'ReviewerNote', 'EmailedToCompass'].forEach(function(name) { col[name] = header.indexOf(name); });
  if (col.Status === -1 || col.EmailedToCompass === -1) {
    Logger.log('notifyAcceptedSuggestions: triage columns missing — skipping.');
    return;
  }

  var sent = 0;
  for (var r = 1; r < values.length; r++) {
    var rowVals = values[r];
    var status  = String(rowVals[col.Status] || '').trim();
    var emailed = String(rowVals[col.EmailedToCompass] || '').trim().toUpperCase();
    if (TRIGGER_STATUSES.indexOf(status) === -1 || emailed === 'TRUE') continue;

    var kind    = String(rowVals[col.Kind] || '').trim() || 'Sugerencia';
    var name    = String(rowVals[col.Name] || '').trim();
    var email   = String(rowVals[col.Email] || '').trim();
    var message = String(rowVals[col.Message] || '').trim();
    var by      = String(rowVals[col.ReviewedBy] || '').trim();
    var at      = String(rowVals[col.ReviewedAt] || '').trim();
    var note    = String(rowVals[col.ReviewerNote] || '').trim();

    var isDone    = status === 'Done';
    var subject   = (isDone ? kind + ' marcada como Hecha' : kind + ' — Aprobación Final') +
                    ' — de ' + (name || 'un misionero');
    var headline  = isDone ? 'Marcada como Hecha' : 'Aprobación Final';
    var introLine = isDone
      ? 'Esta ' + aqa_esc(kind.toLowerCase()) + ' fue marcada como implementada/hecha en PMG Compass.'
      : 'Esta ' + aqa_esc(kind.toLowerCase()) + ' recibió aprobación final en PMG Compass.';

    var body = [
      '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;">',
      '<h2 style="color:#1a4d7c;">' + aqa_esc(kind) + ' — ' + headline + '</h2>',
      '<p>' + introLine + '</p>',
      '<table style="border-collapse:collapse;width:100%;margin:16px 0;">',
      '  <tr><td style="padding:8px;font-weight:bold;background:#f0f4f8;width:140px;">De</td>',
      '      <td style="padding:8px;border-bottom:1px solid #e0e0e0;">' + aqa_esc(name) + ' (' + aqa_esc(email) + ')</td></tr>',
      '  <tr><td style="padding:8px;font-weight:bold;background:#f0f4f8;">Por</td>',
      '      <td style="padding:8px;border-bottom:1px solid #e0e0e0;">' + aqa_esc(by) + (at ? ' el ' + aqa_esc(at) : '') + '</td></tr>',
      note ? ('  <tr><td style="padding:8px;font-weight:bold;background:#f0f4f8;">Nota del revisor</td><td style="padding:8px;border-bottom:1px solid #e0e0e0;">' + aqa_esc(note) + '</td></tr>') : '',
      '</table>',
      '<h3 style="color:#1a4d7c;">' + aqa_esc(kind) + '</h3>',
      '<blockquote style="margin:0;padding:12px 16px;background:#f9f9f9;border-left:4px solid #1a4d7c;font-style:italic;">',
      aqa_esc(message).replace(/\n/g, '<br>'),
      '</blockquote>',
      '</body></html>'
    ].join('');

    sendEmail(TO, subject, body, 'AgentQA');
    tab.getRange(r + 1, col.EmailedToCompass + 1).setValue('TRUE');
    sent++;
  }
  Logger.log('notifyAcceptedSuggestions: emailed ' + sent + ' finally-approved/done item(s).');
}

/**
 * DEPRECATED SHIM — delegates to setupAllCcsmTriggers() (CCSM_Setup.gs).
 *
 * This used to install a 10-MINUTE time-driven trigger on
 * notifyAcceptedSuggestions(), a handler name CCSM_TRIGGER_SCHEDULE does not
 * know about, so setupAllCcsmTriggers() could not clear it and it kept
 * burning ~144 executions a day polling a low-volume queue.
 *
 * CONSEQUENCE, FLAGGED IN THE CCSM_Setup.gs HEADER: after convergence
 * notifyAcceptedSuggestions() is NOT scheduled at all. It is zero-argument and
 * can be run by hand from the editor. If the mission wants it automated, add a
 * row to CCSM_TRIGGER_SCHEDULE — a daily hour is ample — rather than
 * re-enabling this installer.
 */
function setupSuggestionNotifyTrigger() {
  Logger.log('AgentQA: setupSuggestionNotifyTrigger() is DEPRECATED — the 10-minute ' +
    'notifyAcceptedSuggestions trigger it used to install is not on CCSM_TRIGGER_SCHEDULE. ' +
    'Delegating to setupAllCcsmTriggers(); run notifyAcceptedSuggestions() by hand, or add it ' +
    'to the schedule table.');
  setupAllCcsmTriggers();
}
