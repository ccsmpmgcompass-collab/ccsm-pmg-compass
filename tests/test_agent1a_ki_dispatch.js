// test_agent1a_ki_dispatch.js — Agent1A starts the KI PDF job itself
// (AUDIT-2026-10-28-monday-letters.md F2).
//
// GitHub ran the job's Monday schedule 2.5-4.25 h late every week, so the
// request now comes with a workflow_dispatch. Asserts:
//   (a) no token: nothing is fetched, and the note says the schedule will do it;
//   (b) a new request dispatches ki-pdfs.yml on main for that week, with the
//       token as a Bearer header, and a 204 reads "PDF job started";
//   (c) GitHub refusing (401) is a WARNING in the note, never a throw;
//   (d) a retry that keeps the request dispatches again only while its PDFs
//       are not built.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');

const WEEK = '2026-10-25';
const CUTOFF = '2026-10-26 21:30:05';

function setup(answer) {
  const calls = [];
  const env = makeGasEnv({
    urlFetch: (url, params) => {
      calls.push({ url, params });
      return { getResponseCode: () => answer.code, getContentText: () => answer.body || '' };
    },
  });
  const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_Agent5A.gs',
    'CCSM_Agent1A.gs'], env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  ss.insertSheet('KI_PDF_OUTBOX');
  return { env, scope, ss, calls };
}
const token = (env, t) => env.globals.PropertiesService.getScriptProperties().setProperty('GITHUB_DISPATCH_TOKEN', t);

// (a) no token
{
  const { scope, calls } = setup({ code: 204 });
  const note = scope.a1a_requestKiPdfs_(WEEK, CUTOFF);
  assert.strictEqual(calls.length, 0, 'nothing is fetched without a token');
  assert.ok(/KI PDFs requested/.test(note) && /no GITHUB_DISPATCH_TOKEN/.test(note), note);
}

// (b) a new request starts the job
{
  const { env, scope, calls } = setup({ code: 204 });
  token(env, ' github_pat_TEST ');
  const note = scope.a1a_requestKiPdfs_(WEEK, CUTOFF);
  assert.strictEqual(calls.length, 1);
  const { url, params } = calls[0];
  assert.strictEqual(url, 'https://api.github.com/repos/ccsmpmgcompass-collab/ccsm-pmg-compass/actions/workflows/ki-pdfs.yml/dispatches');
  assert.strictEqual(params.method, 'post');
  assert.strictEqual(params.headers.Authorization, 'Bearer github_pat_TEST');
  assert.strictEqual(params.muteHttpExceptions, true);
  assert.deepStrictEqual(JSON.parse(params.payload), { ref: 'main', inputs: { week_end: WEEK } });
  assert.ok(/PDF job started/.test(note), note);
  assert.ok(!/github_pat/.test(note), 'the note never carries the token');
}

// (c) GitHub says no
{
  const { env, scope } = setup({ code: 401, body: '{"message":"Bad credentials"}' });
  token(env, 'github_pat_OLD');
  const note = scope.a1a_requestKiPdfs_(WEEK, CUTOFF);
  assert.ok(/WARNING: PDF job NOT started \(GitHub answered 401/.test(note), note);
  assert.ok(/wrong or expired/.test(note), note);
}

// (d) a retry the same week
{
  const { env, scope, ss, calls } = setup({ code: 204 });
  token(env, 'github_pat_TEST');
  scope.a1a_requestKiPdfs_(WEEK, CUTOFF);
  assert.strictEqual(calls.length, 1);

  let note = scope.a1a_requestKiPdfs_(WEEK, '2026-10-26 21:41:00');
  assert.ok(/kept this week's request \(forms read at 2026-10-26 21:30:05\)/.test(note), note);
  assert.strictEqual(calls.length, 2, 'no PDFs yet: the job is started again');

  ss.getSheetByName('KI_PDF_OUTBOX').appendRow(['PDF', WEEK, 'MISSION', 'm.pdf', CUTOFF, '11', '1', 'JVBERi0=']);
  note = scope.a1a_requestKiPdfs_(WEEK, '2026-10-26 21:55:00');
  assert.strictEqual(calls.length, 2, 'the PDFs are built: nothing to start');
  assert.ok(!/PDF job/.test(note), note);
}

console.log('agent1a ki dispatch OK');
