#!/usr/bin/env node
// oracles/beacon/run.mjs — cold-executable acceptance predicates for the first-party beacon.
//
//   node oracles/beacon/run.mjs      → exits 0 on all-pass, 1 on any divergence
//
// No network, no Cloudflare account, no deployed Worker. This is the ARCHITECT-side
// oracle described in oracles/README.md: it fixes what "correct" means for the beacon's
// decision logic before anyone argues about the implementation. It deliberately does NOT
// test the Worker shell (KV, routing) — that half is only checkable against a running
// deployment, which is precisely the half this run could not verify (see the FAIL in
// briefs/2026-08-08.md).
//
// PROVENANCE: authored 2026-08-08 by the same session that wrote src/beacon-core.js.
// That makes it a builder-authored corpus, which under v4's checker clause may NOT be
// used as the checker's oracle. It is a starting point for an independent architect
// pass, not ground truth. Recorded here so the next fire cannot mistake it for one.

import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  normalisePath, isBotUA, isSelfTraffic, dayKey, utcDate, decide, COUNTABLE,
} from '../../src/beacon-core.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

let pass = 0, fail = 0;
const bad = [];
function is(actual, expected, name) {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) { pass++; } else { fail++; bad.push(`${name}\n     expected ${e}\n     actual   ${a}`); }
}

// ---- normalisePath: only real ship paths become keys ------------------------------
is(normalisePath('/'), '/', 'hub root counts');
is(normalisePath('/index.html'), '/', 'hub index.html folds to root');
is(normalisePath('/002-gha-trigger/'), '/002-gha-trigger/', 'ship path counts');
is(normalisePath('/002-gha-trigger'), '/002-gha-trigger/', 'missing trailing slash normalised');
is(normalisePath('/002-gha-trigger/index.html'), '/002-gha-trigger/', 'ship index.html folds');

is(normalisePath('/002-gha-trigger/?x=1'), '/002-gha-trigger/', 'query stripped before match');
is(normalisePath('/002-gha-trigger/#frag'), '/002-gha-trigger/', 'fragment stripped before match');
// Unbounded-key defence: a crafted POST must not be able to invent storage.
is(normalisePath('/anything-else/'), null, 'unknown path dropped');
// CHECKER FINDING 3 (2026-08-08), the case the first oracle missed: a slug that is
// perfectly well-SHAPED but names no ship that exists. The first implementation
// accepted these and let a scripted client mint unbounded KV keys. Shape is not
// membership; these assertions are the ones that hold the allowlist in place.
is(normalisePath('/999-totally-fake-ship-nobody-built/'), null, 'valid-shape nonexistent ship dropped');
is(normalisePath('/001-x/'), null, 'valid-shape unbuilt ship dropped');
is(normalisePath('/003-codeowners/'), null, 'killed ship is not countable');
is(normalisePath('/006-npm-publish-preflight/'), null, 'failed/unmerged ship is not countable');
is(normalisePath('/2-short/'), null, 'non-NNN prefix dropped');
is(normalisePath('/002-gha-trigger/sub/'), null, 'sub-path dropped');
is(normalisePath('/../etc/passwd'), null, 'traversal dropped');
is(normalisePath('//evil.example/'), null, 'protocol-relative dropped');
is(normalisePath('https://evil.example/'), null, 'absolute URL dropped');
// NOTE: written as an escape, never as a literal NUL byte. A raw \x00 here made git
// and GitHub classify this file as BINARY, so the 2026-08-09 commit that replaced the
// hand-rolled script walker rendered as 'Binary files differ' with zero visible diff --
// the single most safety-relevant change in the fix cycle, invisible to review.
// (round-3 checker finding #3)
is(normalisePath('/002-\u0000/'), null, 'control character dropped');
is(normalisePath('/' + 'a'.repeat(300) + '/'), null, 'over-long path dropped');
is(normalisePath(''), null, 'empty dropped');
is(normalisePath(null), null, 'non-string dropped');
is(normalisePath('/002-GHA-TRIGGER/'), null, 'uppercase slug dropped (paths are lowercase by construction)');

// ---- isBotUA: conservative, but the obvious crawlers must not count ---------------
const REAL_BROWSERS = [
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
];
REAL_BROWSERS.forEach((ua, i) => is(isBotUA(ua), false, `real browser ${i} counts`));
[
  'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
  'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
  'Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)',
  'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot',
  'Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)',
  'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
  'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)',
  'curl/8.4.0',
  'python-requests/2.32.3',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 HeadlessChrome/127.0.0.0 Safari/537.36',
  'Mozilla/5.0 (compatible; UptimeRobot/2.0; http://www.uptimerobot.com/)',
].forEach((ua, i) => is(isBotUA(ua), true, `bot ${i} dropped: ${ua.slice(0, 34)}`));
is(isBotUA(''), true, 'empty UA dropped');
is(isBotUA(undefined), true, 'absent UA dropped');

// ---- isSelfTraffic: Theshin's own clicks never inflate the threshold --------------
is(isSelfTraffic({ self: true }, '/'), true, 'explicit self flag dropped');
is(isSelfTraffic({}, '/002-gha-trigger/?self=1'), true, 'self=1 in query dropped');
is(isSelfTraffic({}, '/002-gha-trigger/?a=1&self=1'), true, 'self=1 after another param dropped');
is(isSelfTraffic({}, '/002-gha-trigger/?self=1#x'), true, 'self=1 before fragment dropped');
is(isSelfTraffic({}, '/002-gha-trigger/?self=0'), false, 'self=0 counts');
is(isSelfTraffic({}, '/002-gha-trigger/?myself=1'), false, 'myself=1 is not the marker');
// Case authored by the 2026-08-09 rebuild CHECKER (finding 7): nested-'?' query where
// client and server used to disagree — the browser calls this self, so must the server.
is(isSelfTraffic({}, '/002-gha-trigger/?a=?self=1&b=:'), true, 'nested-? self marker dropped (checker case)');
is(isSelfTraffic({}, '/002-gha-trigger/'), false, 'ordinary visit counts');

// ---- keys -------------------------------------------------------------------------
is(utcDate(Date.UTC(2026, 7, 8, 23, 59, 59)), '2026-08-08', 'utc date, late');
is(utcDate(Date.UTC(2026, 7, 9, 0, 0, 0)), '2026-08-09', 'utc date rolls at UTC midnight');
is(dayKey('2026-08-08', '/002-gha-trigger/'), 'v1:2026-08-08:/002-gha-trigger/', 'key shape');

// ---- decide(): the whole path, and the drop reasons -------------------------------
const UA = REAL_BROWSERS[0], NOW = Date.UTC(2026, 7, 8, 12, 0, 0);
is(decide({ payload: { path: '/002-gha-trigger/' }, userAgent: UA, nowMs: NOW }),
   { count: true, key: 'v1:2026-08-08:/002-gha-trigger/', path: '/002-gha-trigger/' }, 'qualified visit counts');
is(decide({ payload: { path: '/002-gha-trigger/?self=1' }, userAgent: UA, nowMs: NOW }).reason, 'self', 'self dropped');
is(decide({ payload: { path: '/' }, userAgent: 'Googlebot/2.1', nowMs: NOW }).reason, 'bot', 'bot dropped');
is(decide({ payload: { path: '/nope/' }, userAgent: UA, nowMs: NOW }).reason, 'unknown-path', 'unknown path dropped');
is(decide({ payload: null, userAgent: UA, nowMs: NOW }).reason, 'no-path', 'null payload dropped');
is(decide({ payload: {}, userAgent: UA, nowMs: NOW }).reason, 'no-path', 'missing path dropped');
// Ordering matters: a bot hitting ?self=1 must be dropped, not double-counted anywhere.
is(decide({ payload: { path: '/?self=1' }, userAgent: 'Googlebot/2.1', nowMs: NOW }).count, false, 'bot+self dropped');

// ---- THE ARTIFACT, not just the module ---------------------------------------------
// CHECKER FINDING 1 + 6 (2026-08-08). The first oracle imported beacon-core.js and
// nothing else, so it went 53/53 green while the beacon was INERT on all five pages:
// the inliner had captured a fragment of an HTML comment along with the <script>, and
// per the HTML5 script raw-text content model the whole thing collapsed into one broken
// element whose body was not JavaScript. An oracle that only tests the module cannot
// see that. These cases test the shipped bytes.
const SNIPPET = fs.readFileSync(path.join(ROOT, 'lib/beacon-firstparty.snippet.html'), 'utf8').trim();

is(SNIPPET.startsWith('<script>') && SNIPPET.endsWith('</script>'), true, 'snippet is exactly one script element');
is((SNIPPET.match(/<script/g) || []).length, 1, 'snippet opens exactly one script tag');
is((SNIPPET.match(/<\/script>/g) || []).length, 1, 'snippet closes exactly one script tag');
is(SNIPPET.includes('<!--') || SNIPPET.includes('-->'), false, 'snippet contains no HTML comment (the finding-1 vector)');

const PAGES = ['lib/template.html', 'public/index.html', 'public/002-gha-trigger/index.html',
               'public/004-khanya-school-tutor/index.html', 'public/005-maccleaner/index.html'];

// ---- STATIC HTML BAND: ADVISORY ONLY since 2026-08-09 — it GATES NOTHING -------------
// Rebuild checker findings 1+2 (2026-08-09), measured: the html-scripts.py static band
// (a) false-FAILed a page carrying ordinary <noscript>-wrapped JSON-LD that a real
// browser fired the beacon from anyway, and (b) false-PASSed the round-4 severe vector
// (`<template><noscript></template>` desync) that leaves the beacon inert in Chromium.
// A static parse of "is this snippet live" has now been wrong in BOTH directions across
// five incidents (BOTTLENECKS #1). THE LIVENESS AUTHORITY IS browser-truth.mjs — a real
// Chromium firing a real POST at a real socket. This oracle's exit code makes NO
// liveness claim; its 95/95 must never be cited as liveness evidence. The static checks
// below still PRINT (they catch honest mistakes early, cheaply, e.g. a forgotten
// snippet or an accidental edit) but they cannot fail the run.
{
  const advisory = [];
  const note = (cond, name) => { if (!cond) advisory.push(name); };
  const CHECKER = path.join(ROOT, 'lib/checks/html-scripts.py');
  const SNIPPET_FILE = path.join(ROOT, 'lib/beacon-firstparty.snippet.html');
  const st = spawnSync('python3', [CHECKER, '--selftest'], { encoding: 'utf8' });
  note(st.status === 0, 'html-scripts.py self-test failed');
  const r = spawnSync('python3', [CHECKER, '--snippet', SNIPPET_FILE, ...PAGES.map((f) => path.join(ROOT, f))], { encoding: 'utf8' });
  let parsed = null;
  try { parsed = JSON.parse(r.stdout); } catch (e) { /* advisory only */ }
  if (Array.isArray(parsed)) {
    parsed.forEach((rep, idx) => note(!!(rep && rep.ok), `${PAGES[idx]}: static band reports not-ok${rep && rep.errors && rep.errors.length ? ' — ' + rep.errors.join(' | ') : ''}`));
  } else {
    advisory.push('html-scripts.py did not return reports');
  }
  for (const rel of PAGES) {
    const html = fs.readFileSync(path.join(ROOT, rel), 'utf8');
    note(html.includes(SNIPPET), `${rel}: canonical snippet not found byte-for-byte`);
  }
  if (advisory.length) {
    console.log('\nADVISORY (static band — NOT gating; liveness authority is browser-truth.mjs):\n  ' + advisory.join('\n  '));
  }
}

// ---- the allowlist must equal what is actually deployed -----------------------------
// So a new ship cannot go uncounted by omission, and a removed one cannot linger.
const shipDirs = fs.readdirSync(path.join(ROOT, 'public'), { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .map((d) => `/${d.name}/`)
  .filter((p) => p !== '/dashboard/');   // operator console — self-traffic by definition
const expected = new Set(['/', ...shipDirs]);
is([...COUNTABLE].sort(), [...expected].sort(),
   'COUNTABLE equals { "/" } U every ship directory under public/, minus the dashboard — add a line with every new ship');
is(COUNTABLE.has('/dashboard/'), false, 'the operator console is never counted as a visit');
is(normalisePath('/dashboard/'), null, 'dashboard hits are dropped, not counted');

console.log(`\nbeacon oracle: ${pass} passed, ${fail} failed`);
if (fail) { console.log('\nDIVERGENCES:\n  ' + bad.join('\n  ') + '\n'); process.exit(1); }
process.exit(0);
