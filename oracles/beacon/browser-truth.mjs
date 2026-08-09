#!/usr/bin/env node
// oracles/beacon/browser-truth.mjs — LIVENESS oracle for the first-party beacon.
//
//   REPO RULE (.gitignore): package.json/node_modules are never committed. To run:
//     cd oracles/beacon && npm install playwright   (lands gitignored, per convention)
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node browser-truth.mjs   → 0 all-pass, 1 any fail
//     node browser-truth.mjs --root /path/to/public                      → override page root
//   Worker-shell end-to-end (optional, recommended): npm install wrangler, then
//     npx wrangler dev --local --port 8787   and drive POST /_b + GET /_b/stats cold.
//
// WHY THIS FILE EXISTS (BOTTLENECKS #1, five incidents, rounds 2-4 of ship 008):
// every attempt to prove "the beacon snippet is LIVE on this page" by PARSING the HTML
// was defeated — a hand-rolled <script> walker, then a byte-equality contract beaten by
// <template>/<noscript> wrapping, then an ancestor stack desynchronised by a
// `</template>` inside an open `<noscript>`. The generalisation from round 4: borrowing
// a correct primitive does not make the code that CALLS it correct. So this oracle
// deletes the calling band entirely. There is NO HTML parsing here — not stdlib, not
// regex, nothing. The page is loaded in a real Chromium and the only measured fact is:
// DID AN HTTP POST TO /_b ARRIVE AT A REAL SOCKET. A browser executing the page is the
// spec-defined tokenizer for the whole problem, and the socket is the instrument.
//
// What it asserts, per real page under --root (default ../../public):
//   HUMAN pass (webdriver masked, real-Chrome UA): exactly ONE POST /_b arrives,
//     body is JSON {path:<the page's path>, self:false}, no Cookie header.
//   AUTOMATION pass (navigator.webdriver true, as Playwright ships): ZERO POSTs —
//     the snippet's own bot self-filter works.
//   SELF pass (hub only, ?self=1): the POST arrives with self:true (the server-side
//     drop of self-traffic is decision logic, proven cold in run.mjs, not here).
//
// PROBE-THE-ORACLE (v4 mandatory step — negative controls, each must read INERT):
//   c1 snippet wrapped in <template>            (round-3 defeat vector)
//   c2 snippet wrapped in <noscript>
//   c3 snippet inside an HTML comment
//   c4 stray unclosed <script> before snippet   (round-2 defeat vector)
//   c5 `<template><noscript></template>` desync (round-4 defeat vector)
//   c6 snippet absent
//   c7 POSITIVE control: lib/template.html rendered as a fake ship page must read LIVE
// If any control misreads, THIS ORACLE is broken and the run must FAIL itself.
//
// Provenance note (v4 checker clause): authored 2026-08-09 by the live fix session as
// ARCHITECT. The checker must still drive it cold and attempt independent breaks — an
// oracle is trusted only after the probe, never on authorship.
//
// DEPENDENCY PINNING (rebuild checker finding 9): the repo rule forbids committing
// package.json/lockfiles, so the Playwright version FLOATS on a fresh clone. The
// 2026-08-09 verdicts were produced with playwright@1.62.1 driving the pre-installed
// Chromium at /opt/pw-browsers. If a future run sees unexplained divergence, pin first
// (`npm install playwright@1.62.1`) before debugging anything else.
//
// KNOWN LIMITATIONS, recorded not hidden (rebuild checker finding 5 — both vectors
// adversary-with-write only; no fleet page has either, grepped 2026-08-09): the settle
// window measures ~1s after load, so a page that RE-fires on a timer (meta-refresh,
// setInterval) reads as one POST though a real visitor emits many; and a page that
// registers a service worker answering /_b reads LIVE though every RETURNING visit
// reports nothing. Single-engine truth: Chromium only — Firefox/WebKit/content-blocker
// behaviour is outside what any local oracle here can observe.

import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const argRoot = (() => {
  const i = process.argv.indexOf('--root');
  return i > -1 ? path.resolve(process.argv[i + 1]) : path.resolve(HERE, '../../public');
})();

const REAL_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };

// ---- a cold static server that IS the instrument: it records every POST /_b it receives.
function serve(root) {
  const hits = [];
  const srv = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/_b') {
      let body = '';
      req.on('data', (c) => (body += c));
      req.on('end', () => {
        hits.push({ body, cookie: req.headers.cookie || null, ct: req.headers['content-type'] || null });
        res.writeHead(204, { 'cache-control': 'no-store' }).end();
      });
      return;
    }
    let p = decodeURIComponent((req.url || '/').split('?')[0]);
    if (p.endsWith('/')) p += 'index.html';
    const file = path.join(root, p);
    if (!file.startsWith(root) || !fs.existsSync(file)) { res.writeHead(404).end('nope'); return; }
    res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' });
    res.end(fs.readFileSync(file));
  });
  return new Promise((ok) => srv.listen(0, '127.0.0.1', () => ok({ srv, hits, port: srv.address().port })));
}

async function visit(browser, port, pagePath, { human }) {
  const ctx = await browser.newContext({ userAgent: human ? REAL_UA : undefined });
  if (human) await ctx.addInitScript(() => Object.defineProperty(Object.getPrototypeOf(navigator), 'webdriver', { get: () => false }));
  const page = await ctx.newPage();
  await page.goto(`http://127.0.0.1:${port}${pagePath}`, { waitUntil: 'load', timeout: 20000 });
  await page.waitForTimeout(700); // sendBeacon is fire-and-forget; give the socket a beat
  await ctx.close();              // context close flushes pending beacons
  await new Promise((r) => setTimeout(r, 300));
}

let pass = 0, fail = 0; const bad = [];
function is(cond, name, detail = '') { if (cond) pass++; else { fail++; bad.push(`${name}${detail ? ' — ' + detail : ''}`); } }

const SNIPPET = fs.readFileSync(path.resolve(HERE, '../../lib/beacon-firstparty.snippet.html'), 'utf8');
function controlPage(name, bodyHtml) {
  return `<!doctype html><html><head><meta charset="utf-8"><title>${name}</title></head><body><h1>${name}</h1>\n${bodyHtml}\n</body></html>`;
}

const browser = await chromium.launch(
  fs.existsSync('/opt/pw-browsers/chromium') && !fs.existsSync(process.env.PLAYWRIGHT_BROWSERS_PATH || '/nonexistent')
    ? { executablePath: '/opt/pw-browsers/chromium' } : {}
).catch(() => chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }));

// ---------- PART 1: every real page under --root ----------
const pages = ['/'];
for (const d of fs.readdirSync(argRoot, { withFileTypes: true })) {
  if (d.isDirectory() && fs.existsSync(path.join(argRoot, d.name, 'index.html'))) pages.push(`/${d.name}/`);
}
const { srv, hits, port } = await serve(argRoot);

for (const p of pages) {
  const isDash = p === '/dashboard/';
  hits.length = 0;
  await visit(browser, port, p, { human: true });
  if (isDash) {
    // operator console: server-side allowlist drops it regardless; client firing is not asserted either way
    is(true, `dashboard ${p} observed (client fires: ${hits.length}) — not a liveness target`);
  } else {
    is(hits.length === 1, `LIVE ${p} — exactly one beacon POST (human)`, `got ${hits.length}`);
    if (hits.length === 1) {
      let j = null; try { j = JSON.parse(hits[0].body); } catch {}
      is(j && j.path === p && j.self === false, `payload ${p} = {path:${p}, self:false}`, hits[0].body.slice(0, 120));
      is(hits[0].cookie === null, `no cookies sent ${p}`);
    }
    hits.length = 0;
    await visit(browser, port, p, { human: false });
    is(hits.length === 0, `AUTOMATION self-filter ${p} — zero POSTs with webdriver=true`, `got ${hits.length}`);
  }
}
// self-traffic marker, hub only
hits.length = 0;
await visit(browser, port, '/?self=1', { human: true });
{
  let j = null; try { j = JSON.parse((hits[0] || {}).body || 'null'); } catch {}
  is(hits.length === 1 && j && j.self === true, 'SELF /?self=1 — POST arrives marked self:true', JSON.stringify(hits[0] || null));
}
srv.close();

// ---------- PART 2: PROBE-THE-ORACLE — negative controls in a temp root ----------
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'beacon-probe-'));
const controls = {
  'c1-template-wrapped':   controlPage('c1', `<template>${SNIPPET}</template>`),
  'c2-noscript-wrapped':   controlPage('c2', `<noscript>${SNIPPET}</noscript>`),
  'c3-html-comment':       controlPage('c3', `<!-- ${SNIPPET.replaceAll('--', '- -')} -->`),
  // c4a: a GENUINELY unclosed <script> swallows everything after it as raw script text
  // (the round-2 defeat vector) — the snippet never executes → INERT.
  'c4a-unclosed-script':   controlPage('c4a', `<script>\n// stray, never closed — everything below is raw text to the parser\n<div>${'x'.repeat(64)}</div>${SNIPPET}`),
  // c4b: `</script disabled>` LOOKS unclosed to hand-reasoning but IS a legal close
  // (attributes on an end tag are a parse error; the tag still closes) → the snippet
  // runs → LIVE. Recorded because this oracle's own author first expected INERT here
  // and the browser corrected him — the exact class of error that produced BOTTLENECKS
  // #1 rounds 2-4, caught by the probe instead of by a checker three rounds later.
  'c4b-sneaky-closed':     controlPage('c4b', `<script>\n// stray, "never closed"\n</script disabled><div>${'x'.repeat(64)}</div>${SNIPPET}`),
  'c5-round4-desync':      controlPage('c5', `<template><noscript></template>${SNIPPET}</noscript>`),
  'c6-absent':             controlPage('c6', `<p>no beacon here</p>`),
};
for (const [name, html] of Object.entries(controls)) {
  fs.mkdirSync(path.join(tmp, name), { recursive: true });
  fs.writeFileSync(path.join(tmp, name, 'index.html'), html);
}
// c7 positive control: the template rendered as a fake ship page
fs.mkdirSync(path.join(tmp, 'c7-template-positive'), { recursive: true });
fs.writeFileSync(path.join(tmp, 'c7-template-positive', 'index.html'),
  fs.readFileSync(path.resolve(HERE, '../../lib/template.html'), 'utf8'));

const probe = await serve(tmp);
for (const name of Object.keys(controls)) {
  probe.hits.length = 0;
  await visit(browser, probe.port, `/${name}/`, { human: true });
  const expectFire = name === 'c4b-sneaky-closed'; // the one control that must read LIVE — see its comment
  is((probe.hits.length > 0) === expectFire, `PROBE ${name} must read ${expectFire ? 'LIVE' : 'INERT'}`, `got ${probe.hits.length} POSTs`);
}
probe.hits.length = 0;
await visit(browser, probe.port, '/c7-template-positive/', { human: true });
is(probe.hits.length === 1, 'PROBE c7 template positive-control must read LIVE', `got ${probe.hits.length}`);
probe.srv.close();

await browser.close();
fs.rmSync(tmp, { recursive: true, force: true });

console.log(`\nbrowser-truth: ${pass} pass, ${fail} fail`);
if (bad.length) { console.log(bad.map((b) => '  FAIL ' + b).join('\n')); }
process.exit(fail ? 1 : 0);
