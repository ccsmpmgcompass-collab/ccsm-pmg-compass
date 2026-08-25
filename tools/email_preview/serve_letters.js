/**
 * serve_letters.js — serves tools/email_preview/.data over HTTP so rendered
 * letters can be MEASURED in a real browser.
 *
 * Two reasons this exists rather than opening the files directly:
 *   - file:// paths under the Windows short name (CHILEC~1) fail to open.
 *   - A raw letter has no <meta viewport>, so a browser lays it out at 980px
 *     and every measured height is wrong. This injects the viewport meta on
 *     the way out, so 375px means 375px.
 *
 *   node tools/email_preview/serve_letters.js   ->  http://localhost:8933/out/…
 */

'use strict';

const http = require('http');
const fs   = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '.data');
const PORT = 8933;
const HEAD = '<!doctype html><meta charset="utf-8">' +
             '<meta name="viewport" content="width=device-width,initial-scale=1">' +
             '<style>body{margin:0}</style>';

http.createServer((req, res) => {
  const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '');
  const file = path.join(ROOT, rel);
  // Never serve outside .data, whatever the request says.
  if (!file.startsWith(ROOT)) { res.writeHead(403).end('no'); return; }

  fs.stat(file, (err, st) => {
    if (err) { res.writeHead(404).end('not found'); return; }
    if (st.isDirectory()) {
      const names = fs.readdirSync(file).sort()
        .map((n) => '<a href="/' + path.posix.join(rel, n) + '">' + n + '</a>').join('<br>');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }).end(HEAD + names);
      return;
    }
    const body = fs.readFileSync(file);
    if (/\.html?$/.test(file)) {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }).end(HEAD + body.toString('utf8'));
    } else {
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' }).end(body);
    }
  });
}).listen(PORT, () => console.log('letters on http://localhost:' + PORT + '/out/'));
