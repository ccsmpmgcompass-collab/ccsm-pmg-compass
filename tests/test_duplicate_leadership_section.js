// test_duplicate_leadership_section.js — stops a leadership letter repeating
// the same summary.
//
// WHY THIS EXISTS. On CCSM's roster the two missionaries in a companionship
// usually SHARE one inbox: Companion1_Email and Companion2_Email hold the same
// address on 41 of the 43 active MISSION_ORG rows (the names differ, the
// mailbox does not). a1c_buildPeopleMap calls addCompanion once per companion
// column, so for a shared mailbox it runs twice against the SAME row.
//
// The area list had a guard for that (`indexOf(areaName) < 0`); the role list
// did not, so the row's leadership flag was pushed twice, and a1c_buildEmail's
// `person.roles.forEach` rendered the entire section twice -- two identical
// "Resumen de Zona" headings, two identical KPI tile blocks, two identical
// 44-row area tables. Measured on the live roster: 20 of the 21 leaders were
// getting a duplicate (9 DL, 6 STL, 4 ZL, 1 AP). Removing it cut the ZL letter
// from 15.2 phone screens to 9.8.
//
// The de-duplication keys on the SECTION a role renders, not on the role
// object, because several role types collapse onto one output -- see
// a1c_roleSectionKey_.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent1C.gs'],
  env.globals);
// a1c_buildEmail's footer calls getMissionName(), which reads AGENT_CONFIG.
makeCcsmSpreadsheet(env, scope);

const SHARED = 'comp@missionary.org';

function row(over) {
  const base = {
    Area_Name: 'Área Uno', Zone: 'Zona Uno', District: 'Distrito Uno',
    Companion1_Name: 'Elder Uno', Companion1_Email: SHARED,
    Companion2_Name: 'Elder Dos', Companion2_Email: SHARED,
    Is_DL: 'FALSE', Is_ZL: 'FALSE', Is_STL: 'FALSE',
    Is_AP: 'FALSE', Is_MP: 'FALSE', Active: 'TRUE'
  };
  Object.keys(over || {}).forEach((k) => { base[k] = over[k]; });
  return base;
}

// ===========================================================================
// 1. A shared mailbox yields ONE role, not two -- the actual production bug.
// ===========================================================================
['Is_DL', 'Is_ZL', 'Is_STL', 'Is_AP', 'Is_MP'].forEach((flag) => {
  const people = scope.a1c_buildPeopleMap([row({ [flag]: 'TRUE' })]);
  const person = people[SHARED];
  assert.ok(person, flag + ': the shared mailbox must still receive a letter');
  assert.strictEqual(person.roles.length, 1,
    flag + ': a shared companionship inbox must not duplicate the role');
  assert.strictEqual(person.areas.length, 1,
    flag + ': the area must not duplicate either');
});

// Two separate mailboxes on one leadership row: each person gets it once.
const split = scope.a1c_buildPeopleMap([row({
  Is_ZL: 'TRUE',
  Companion1_Email: 'uno@missionary.org',
  Companion2_Email: 'dos@missionary.org'
})]);
assert.strictEqual(split['uno@missionary.org'].roles.length, 1);
assert.strictEqual(split['dos@missionary.org'].roles.length, 1);

// ===========================================================================
// 2. Genuinely DIFFERENT callings still both render. The fix must suppress
//    repeats, never collapse real distinct responsibilities.
// ===========================================================================
const twoDistricts = scope.a1c_buildPeopleMap([
  row({ Is_DL: 'TRUE', Area_Name: 'Área Uno', District: 'Distrito Uno' }),
  row({ Is_DL: 'TRUE', Area_Name: 'Área Dos', District: 'Distrito Dos' })
]);
assert.strictEqual(twoDistricts[SHARED].roles.length, 2,
  'a leader over two districts must keep both summaries');

const twoZones = scope.a1c_buildPeopleMap([
  row({ Is_ZL: 'TRUE', Area_Name: 'Área Uno', Zone: 'Zona Uno' }),
  row({ Is_ZL: 'TRUE', Area_Name: 'Área Dos', Zone: 'Zona Dos' })
]);
assert.strictEqual(twoZones[SHARED].roles.length, 2,
  'a leader over two zones must keep both summaries');

// ===========================================================================
// 3. The key is the SECTION, not the role tuple. AP and MP both render the
//    mission summary and ignore the zone/district on their row, so two such
//    rows must NOT produce two identical "Resumen de la Misión" sections.
// ===========================================================================
const k = scope.a1c_roleSectionKey_;
assert.strictEqual(k({ type: 'AP', zone: 'Zona Uno', district: 'D1' }),
                   k({ type: 'MP', zone: 'Zona Dos', district: 'D2' }),
  'AP and MP both render the mission summary, so they share a section key');
assert.strictEqual(k({ type: 'ZL',  zone: 'Zona Uno', district: 'D1' }),
                   k({ type: 'STL', zone: 'Zona Uno', district: 'D2' }),
  'ZL and STL both render their zone summary, so the district must not matter');
assert.notStrictEqual(k({ type: 'ZL', zone: 'Zona Uno', district: 'D1' }),
                      k({ type: 'ZL', zone: 'Zona Dos', district: 'D1' }),
  'different zones are different sections');
assert.notStrictEqual(k({ type: 'DL', zone: 'Z', district: 'Distrito Uno' }),
                      k({ type: 'DL', zone: 'Z', district: 'Distrito Dos' }),
  'different districts are different sections');

// Two AP rows in different zones collapse to a single mission summary.
const twoAp = scope.a1c_buildPeopleMap([
  row({ Is_AP: 'TRUE', Area_Name: 'Área Uno', Zone: 'Zona Uno' }),
  row({ Is_AP: 'TRUE', Area_Name: 'Área Dos', Zone: 'Zona Dos' })
]);
assert.strictEqual(twoAp[SHARED].roles.length, 1,
  'two AP rows must not render the mission summary twice');

// ===========================================================================
// 4. End to end: the rendered letter carries exactly one section heading.
// ===========================================================================
const HEADINGS = /Resumen de (la Misión|Zona|Distrito)/g;
const areas = {
  'Área Uno': {
    zone: 'Zona Uno', district: 'Distrito Uno',
    stats: { submissions: 3, contacts_made: 40, meaningful_conversations: 20,
             new_people_found: 5, friend_lessons: 12, baptismal_invitations: 1,
             effort_score: 2.4 },
    growth: null, strength1: null, strength2: null, ki: null
  }
};
const summaries = {
  mission: { total_areas: 1, submitted: 1, contacts_made: 40 },
  zones:     { 'Zona Uno':     { total_areas: 1, submitted: 1, contacts_made: 40 } },
  districts: { 'Distrito Uno': { total_areas: 1, submitted: 1, contacts_made: 40 } }
};

[['Is_ZL', 'Zona'], ['Is_DL', 'Distrito'], ['Is_AP', 'la Misión']].forEach((pair) => {
  const people = scope.a1c_buildPeopleMap([row({ [pair[0]]: 'TRUE' })]);
  const html = scope.a1c_buildEmail(people[SHARED], areas, summaries, new Date(2026, 7, 23));
  const found = html.match(HEADINGS) || [];
  assert.strictEqual(found.length, 1,
    pair[0] + ' letter must contain exactly one leadership summary, got ' + found.length);
});

console.log('test_duplicate_leadership_section: OK');
