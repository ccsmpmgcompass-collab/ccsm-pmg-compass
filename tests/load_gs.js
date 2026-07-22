// load_gs.js — concatenate .gs files and evaluate them in a shared scope
// alongside the GAS stub globals, returning every top-level `function`,
// `var`, `const`, and `let` declared across those files so tests can call
// them directly.
const fs = require('fs');
const path = require('path');

// The repo root — one level up from tests/. File names passed to loadGs() are
// resolved against it rather than against process.cwd(), so a suite behaves
// the same however it was invoked. Absolute paths pass through unchanged.
const REPO_ROOT = path.join(__dirname, '..');
function resolveGs(f) {
  return path.isAbsolute(f) ? f : path.join(REPO_ROOT, f);
}

// Matches top-level (column 0) declarations only, so nested helpers inside
// other functions are correctly excluded. Handles regular functions,
// generator functions (function*), and var/const/let — including multiple
// comma-separated names on one `var a, b, c` line.
const FUNCTION_DECL_RE = /^function\s*\*?\s+([A-Za-z_$][A-Za-z0-9_$]*)/gm;
const VAR_DECL_RE = /^(?:var|const|let)\s+([A-Za-z_$][A-Za-z0-9_$]*(?:\s*,\s*[A-Za-z_$][A-Za-z0-9_$]*)*)/gm;

function declaredNames(src) {
  const names = new Set();

  for (const m of src.matchAll(FUNCTION_DECL_RE)) {
    names.add(m[1]);
  }
  for (const m of src.matchAll(VAR_DECL_RE)) {
    for (const n of m[1].split(',')) names.add(n.trim());
  }
  return [...names];
}

function loadGs(files, globals) {
  const src = files.map((f) => fs.readFileSync(resolveGs(f), 'utf8')).join('\n;\n');
  const names = Object.keys(globals);
  const values = names.map((n) => globals[n]);

  const declared = declaredNames(src);
  // Each declared name is returned only if it actually ended up defined in
  // scope after evaluation (defensive against names matched inside strings
  // or comments that slipped through the regex).
  const returner =
    '\n;return {' +
    declared
      .map((n) => `${JSON.stringify(n)}: (typeof ${n} !== 'undefined' ? ${n} : undefined)`)
      .join(',') +
    '};';

  const fn = new Function(...names, src + returner);
  return fn(...values);
}

module.exports = { loadGs };
