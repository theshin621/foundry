#!/usr/bin/env node
// oracles/013-stats-window-floor/oracle.mjs
//
// THE ORACLE FOR SHIP 013 — written by the ARCHITECT before any code exists.
// Run cold:   node oracles/013-stats-window-floor/oracle.mjs
//             node oracles/013-stats-window-floor/oracle.mjs --worker src/worker.js
//
// WHAT IT IS. Not a static reader of src/worker.js. It EXECUTES the shipped fetch
// handler — the real file, byte-for-byte — against a stub KV populated with a known
// synthetic dataset, at fleet sizes 1..60, and observes what comes back. This is the
// same principle BOTTLENECKS #1's third clause applies to markup ("a browser observing
// the fire, not a walker reading the tags"): the claim under test is a behaviour, so
// the instrument runs the behaviour. There is no hand-written parse-and-match band.
//
// HOW IT VARIES THE FLEET WITHOUT EDITING THE SOURCE. src/worker.js does
// `import { decide, COUNTABLE } from './beacon-core.js'`. The harness writes a temp
// directory containing (a) an UNMODIFIED COPY of src/worker.js and (b) a shim
// beacon-core.js that is `export * from '<real beacon-core>'` plus a local
// `export const COUNTABLE = <synthetic set>`. Per the ES module spec an explicit local
// export shadows a star-re-export of the same name, so the worker sees the synthetic
// path set and every other binding (decide, normalisePath, …) is the real one. Nothing
// in the code under test is rewritten, so a defect cannot hide in the rewriting.
//
// THE DATASET. Deterministic and dense: every (path, day) in the last 60 days holds a
// count derived from a pure function of the two, so any off-by-one in date generation
// or key construction shows up as a wrong number rather than as an absent one. Days
// with a count of 0 are still written to KV as "0" so that "omitted because zero" and
// "omitted because never read" stay distinguishable.
//
// THE PREDICATES (all must hold at every fleet size; each prints its own line):
//   P1  WINDOW FLOOR      an all-paths read never returns window.days < 7.
//   P2  WINDOW WELL-FORMED window.days >= 1, dates.length === window.days, from <= to,
//                          both ISO dates. A zero-day window must be inexpressible.
//   P3  COUNTS EXACT      every count returned equals the synthetic dataset for that
//                          (path, day); no path in the window reports a number the
//                          dataset does not contain.
//   P4  TRUNCATION DECLARED  if any countable path is absent from `paths`, the response
//                          declares it: truncated.paths_omitted lists exactly the
//                          missing paths and truncated.reason is a non-empty string.
//                          Silence is the failure this ship exists to remove.
//   P5  SUBREQUEST BOUND  total env.BEACON.get calls per invocation <= 44.
//   P6  DEEP SINGLE PATH  ?path=X&days=30 returns 30 days of exact counts, <= 44 gets.
//   P7  ERROR PATHS       unknown ?path -> 404 unknown-path; env.BEACON absent -> 503
//                          kv-unbound. (Regression guard: the fix must not eat these.)
//   P9  COVERAGE EXACT    ADDED BY PROBE-THE-ORACLE CLAUSE (b) — see the note below.
//                          The endpoint must cover as many paths as the floor allows,
//                          not merely declare what it dropped.
//   P8  RELAY COMPLETE    lib/relay_fetch.py, driven against a stub HTTP origin at a
//                          fleet size that forces truncation, still commits a reading
//                          containing EVERY countable path with exact counts and a
//                          window >= 7 days. The artifact the loop actually reads must
//                          be complete even when one endpoint call cannot be.
//
// EXIT: 0 = PASS, 1 = FAIL. Every failure prints the fleet size and the offending value.
//
// ---------------------------------------------------------------------------------
// PROBE-THE-ORACLE, CLAUSE (b) — the independent attempt to break the oracle, and the
// hole it found. RECORDED HERE BECAUSE IT SUCCEEDED, which is the point of the clause.
//
// With P1-P8 only, this worker PASSES at every fleet size:
//
//     const paths = ['/'];                       // return the hub and nothing else
//     ... window.days = 10 ...
//     truncated = { paths_omitted: <every other countable path>, reason: 'subrequest-cap' }
//
// P1 holds (10 >= 7), P2 holds, P3 holds (the one path it returns is exact), P4 holds
// (the omission is declared, exactly and honestly), P5 holds (10 gets). The oracle was
// asking "did you tell me what you dropped?" and never "did you drop more than you had
// to?" — so a worker that measures one path and declares the other fifty-nine missing
// is blessed. That is the same failure the ship exists to fix, wearing a disclosure.
//
// This is the concrete form of the lesson BOTTLENECKS #1 recorded on 2026-08-11: an
// oracle fixes the target set to what its author already knew how to handle, and
// probe-the-oracle proves it can go RED without proving it looks in the right places.
// P9 is the correction. It pins the exact contract rather than a lower bound:
//
//     maxDays = 10, FLOOR = 7, HARD_CAP = 44
//     if n * maxDays <= HARD_CAP        -> days = maxDays,                 paths = n
//     else                              -> days = max(FLOOR, floor(CAP/n)),
//                                          paths = min(n, floor(CAP/days))
//
// A worker may not return fewer paths than that, and may not return more (which would
// breach P5). Degradation is now a computed obligation, not a discretionary courtesy.
// ---------------------------------------------------------------------------------

import { mkdtemp, writeFile, copyFile, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');

const argv = process.argv.slice(2);
const workerRel = (() => {
  const i = argv.indexOf('--worker');
  return i >= 0 && argv[i + 1] ? argv[i + 1] : 'src/worker.js';
})();
const WORKER = resolve(ROOT, workerRel);
const CORE = resolve(ROOT, 'src/beacon-core.js');
const RELAY = resolve(ROOT, 'lib/relay_fetch.py');

const FLOOR = 7;          // the trailing-7 window MOD-2's threshold is defined on
const HARD_CAP = 44;      // < the Free plan's 50 subrequests, the worker's own budget
const MAX_DAYS = 10;      // the endpoint's default/maximum all-paths window
const DEEP_DAYS = 30;

// The contract P9 enforces — the architect's, not the builder's. See the probe note above.
function contract(n) {
  if (n * MAX_DAYS <= HARD_CAP) return { days: MAX_DAYS, paths: n };
  const days = Math.max(FLOOR, Math.floor(HARD_CAP / n));
  return { days, paths: Math.min(n, Math.floor(HARD_CAP / days)) };
}

// ---------------------------------------------------------------- the dataset
// A pure function of (path, day): dense, deterministic, and different for every cell,
// so a mis-generated date or a mis-built key yields a WRONG number, not a missing one.
function synth(path, date) {
  let h = 2166136261;
  for (const ch of `${date}|${path}`) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); }
  return (h >>> 0) % 97;                      // 0..96, zeros included on purpose
}
function isoDaysAgo(i, nowMs) {
  return new Date(nowMs - i * 86400000).toISOString().slice(0, 10);
}
function fleetPaths(n) {
  // '/' is always countable in the real set; the rest are ship-shaped.
  const out = ['/'];
  for (let i = 2; out.length < n; i++) out.push(`/${String(i).padStart(3, '0')}-ship-${i}/`);
  return out.slice(0, n);
}

// ---------------------------------------------------------------- the stub KV
function makeKV(paths, nowMs, days = 70) {
  const store = new Map();
  for (const p of paths) {
    for (let i = 0; i < days; i++) {
      const d = isoDaysAgo(i, nowMs);
      store.set(`v1:${d}:${p}`, String(synth(p, d)));
    }
  }
  const counter = { gets: 0 };
  return {
    counter,
    kv: {
      async get(key) { counter.gets++; return store.has(key) ? store.get(key) : null; },
      async put() { /* unused by /_b/stats */ },
    },
  };
}

// ---------------------------------------------------------------- module loading
let tmpRoot = null;
const loaded = new Map();
async function loadWorker(paths) {
  const key = paths.join('|');
  if (loaded.has(key)) return loaded.get(key);
  if (!tmpRoot) tmpRoot = await mkdtemp(join(tmpdir(), 'oracle013-'));
  const dir = join(tmpRoot, `f${loaded.size}`);
  await import('node:fs/promises').then((fs) => fs.mkdir(dir, { recursive: true }));
  // (a) the shim: real module star-re-exported, COUNTABLE shadowed by a local export.
  await writeFile(join(dir, 'beacon-core.js'),
    `export * from ${JSON.stringify(pathToFileURL(CORE).href)};\n` +
    `export const COUNTABLE = new Set(${JSON.stringify(paths)});\n`);
  // (b) the code under test, copied verbatim — never rewritten.
  await copyFile(WORKER, join(dir, 'worker.js'));
  const mod = await import(pathToFileURL(join(dir, 'worker.js')).href);
  loaded.set(key, mod.default);
  return mod.default;
}

async function callStats(worker, kv, query = '') {
  const req = new Request(`https://tailorfarms.com/_b/stats${query}`, { method: 'GET' });
  const res = await worker.fetch(req, kv === null ? {} : { BEACON: kv }, { waitUntil() {} });
  let body = null;
  try { body = JSON.parse(await res.text()); } catch { /* body may legitimately not be JSON */ }
  return { status: res.status, body };
}

// ---------------------------------------------------------------- predicate runner
const failures = [];
function check(id, ok, detail) {
  if (!ok) failures.push(`${id}: ${detail}`);
  return ok;
}
const ISO = /^\d{4}-\d{2}-\d{2}$/;

async function runWorkerPredicates() {
  const nowMs = Date.now();
  const sizes = [];
  for (let n = 1; n <= 12; n++) sizes.push(n);
  for (const n of [15, 20, 22, 23, 30, 44, 45, 46, 60]) sizes.push(n);

  const seen = { p1: 0, p2: 0, p3: 0, p4: 0, p5: 0, p9: 0 };

  for (const n of sizes) {
    const paths = fleetPaths(n);
    const worker = await loadWorker(paths);
    const { kv, counter } = makeKV(paths, nowMs);
    counter.gets = 0;
    const { status, body } = await callStats(worker, kv);

    if (!check('P2', status === 200 && body && body.window && body.paths,
      `fleet=${n}: expected a 200 with window+paths, got status=${status} body=${JSON.stringify(body).slice(0, 160)}`)) continue;

    const w = body.window;

    // P1 — the window floor.
    if (check('P1', w.days >= FLOOR, `fleet=${n}: window.days=${w.days} < ${FLOOR}; the trailing-7 metric is unreadable`)) seen.p1++;

    // P2 — well-formed window. Recompute the day list independently of the worker.
    const expectDates = Array.from({ length: w.days }, (_, i) => isoDaysAgo(i, nowMs));
    const wellFormed = Number.isInteger(w.days) && w.days >= 1
      && ISO.test(String(w.from)) && ISO.test(String(w.to))
      && w.from <= w.to
      && w.to === expectDates[0] && w.from === expectDates[expectDates.length - 1];
    if (check('P2', wellFormed, `fleet=${n}: malformed window ${JSON.stringify(w)}`)) seen.p2++;

    // P3 — every returned count matches the dataset, for every day inside the window.
    let exact = true;
    for (const [p, byday] of Object.entries(body.paths)) {
      if (!paths.includes(p)) { exact = false; failures.push(`P3: fleet=${n}: response contains unknown path ${p}`); break; }
      for (const [d, v] of Object.entries(byday)) {
        if (!expectDates.includes(d)) { exact = false; failures.push(`P3: fleet=${n}: ${p} reports day ${d} outside the declared window`); break; }
        if (v !== synth(p, d)) { exact = false; failures.push(`P3: fleet=${n}: ${p} ${d} = ${v}, dataset says ${synth(p, d)}`); break; }
      }
      // and nothing inside the window that the dataset says is non-zero may be missing
      for (const d of expectDates) {
        const want = synth(p, d);
        if (want > 0 && byday[d] !== want) { exact = false; failures.push(`P3: fleet=${n}: ${p} ${d} missing/wrong (want ${want}, got ${byday[d]})`); break; }
      }
      if (!exact) break;
    }
    if (exact) seen.p3++;

    // P4 — truncation, if any, is declared and exact.
    const returned = new Set(Object.keys(body.paths));
    const omitted = paths.filter((p) => !returned.has(p));
    if (omitted.length === 0) {
      if (check('P4', !body.truncated, `fleet=${n}: nothing was omitted but a truncated block was returned: ${JSON.stringify(body.truncated)}`)) seen.p4++;
    } else {
      const t = body.truncated;
      const declared = t && Array.isArray(t.paths_omitted) ? [...t.paths_omitted].sort() : null;
      const ok = declared !== null
        && JSON.stringify(declared) === JSON.stringify([...omitted].sort())
        && typeof t.reason === 'string' && t.reason.length > 0;
      if (check('P4', ok, `fleet=${n}: ${omitted.length} path(s) omitted, declaration=${JSON.stringify(t)}`)) seen.p4++;
    }

    // P5 — subrequest bound.
    if (check('P5', counter.gets <= HARD_CAP, `fleet=${n}: ${counter.gets} KV gets > ${HARD_CAP}`)) seen.p5++;

    // P9 — coverage is an obligation, not a courtesy. (probe-the-oracle clause (b))
    const want = contract(n);
    const p9 = w.days === want.days && returned.size === want.paths;
    if (check('P9', p9, `fleet=${n}: returned ${returned.size} path(s) over ${w.days} days; the contract requires ${want.paths} over ${want.days}`)) seen.p9++;
  }

  // P6 — the deep single-path read the relay will lean on.
  {
    const paths = fleetPaths(20);
    const worker = await loadWorker(paths);
    const target = paths[7];
    const { kv, counter } = makeKV(paths, nowMs);
    counter.gets = 0;
    const { status, body } = await callStats(worker, kv, `?path=${encodeURIComponent(target)}&days=${DEEP_DAYS}`);
    const dates = Array.from({ length: DEEP_DAYS }, (_, i) => isoDaysAgo(i, nowMs));
    let ok = status === 200 && body && body.window && body.window.days === DEEP_DAYS && body.paths && body.paths[target];
    if (ok) {
      for (const d of dates) {
        const want = synth(target, d);
        if (want > 0 && body.paths[target][d] !== want) { ok = false; failures.push(`P6: ${target} ${d} = ${body.paths[target]?.[d]}, dataset says ${want}`); break; }
      }
      if (Object.keys(body.paths).length !== 1) { ok = false; failures.push(`P6: single-path read returned ${Object.keys(body.paths).length} paths`); }
    } else {
      failures.push(`P6: deep read failed: status=${status} window=${JSON.stringify(body?.window)}`);
    }
    check('P6', ok && counter.gets <= HARD_CAP, `deep read used ${counter.gets} gets`);
    if (ok && counter.gets <= HARD_CAP) console.log(`  P6 DEEP SINGLE PATH   ok — ${DEEP_DAYS} days, ${counter.gets} gets`);
  }

  // P10 — EXPLICIT ?days ON AN ALL-PATHS READ.
  // ADDED BY CHECKER ROUND 1, FINDING 1 [severe]. The oracle's own blind spot, and the
  // most valuable thing round 1 produced: every P1/P2/P9 call above sends an EMPTY query
  // string, and P6 is the only predicate that sends `?days=` — always together with
  // `?path=`, which routes through the single-path branch. So "?days=1 with no ?path="
  // was never executed, and the first draft answered it with a one-day all-paths window
  // and no declaration: the exact silent short window this ship exists to abolish,
  // reachable through a documented query parameter. P1's docstring claimed "an all-paths
  // read never returns window.days < 7" and the oracle had no case that could falsify it.
  // This is BOTTLENECKS #1's 2026-08-11 lesson landing again — an oracle fixes the target
  // set to what its author already knew how to handle — so the case enters the INSTRUMENT
  // rather than living in a review nobody re-runs.
  {
    const paths = fleetPaths(4);
    const worker = await loadWorker(paths);
    const nowMs2 = Date.now();
    let ok = true;
    for (const q of ['0', '1', '3', '6', '7', '9', '10', '-5', 'abc', '7.9', '1e9', '1&days=99', '']) {
      const { kv } = makeKV(paths, nowMs2);
      const { status, body } = await callStats(worker, kv, `?days=${q}`);
      const w = body && body.window;
      if (status !== 200 || !w || !(w.days >= FLOOR) || w.days !== (body.paths ? w.days : -1)) {
        ok = false; failures.push(`P10: ?days=${q} -> status=${status} window=${JSON.stringify(w)} (all-paths window below the ${FLOOR}-day floor or malformed)`); continue;
      }
      // The adjustment must be self-declaring: a consumer can see what it asked for.
      if (!Number.isInteger(w.requested) || w.floor !== FLOOR) {
        ok = false; failures.push(`P10: ?days=${q} -> window does not declare requested/floor: ${JSON.stringify(w)}`);
      }
    }
    // …and the single-path branch keeps its narrow range, declared as exempt.
    const { kv } = makeKV(paths, nowMs2);
    const narrow = await callStats(worker, kv, `?path=${encodeURIComponent(paths[1])}&days=2`);
    if (!(narrow.status === 200 && narrow.body.window.days === 2 && narrow.body.window.floor === null)) {
      ok = false; failures.push(`P10: single-path ?days=2 should stay narrow and declare floor:null, got ${JSON.stringify(narrow.body?.window)}`);
    }
    check('P10', ok, 'see above');
    if (ok) console.log('  P10 EXPLICIT ?days    ok — 13 all-paths asks held at the floor; single-path exempt and declared');
  }

  // P7 — the error paths must survive the fix.
  {
    const paths = fleetPaths(4);
    const worker = await loadWorker(paths);
    const { kv } = makeKV(paths, nowMs);
    const bad = await callStats(worker, kv, '?path=/nope/');
    const unbound = await callStats(worker, null, '');
    const ok = bad.status === 404 && bad.body?.error === 'unknown-path'
      && unbound.status === 503 && unbound.body?.error === 'kv-unbound';
    check('P7', ok, `unknown-path -> ${bad.status}/${JSON.stringify(bad.body)}; unbound -> ${unbound.status}/${JSON.stringify(unbound.body)}`);
    if (ok) console.log('  P7 ERROR PATHS        ok — 404 unknown-path, 503 kv-unbound');
  }

  console.log(`  P1 WINDOW FLOOR       ${seen.p1}/${sizes.length} fleet sizes kept window >= ${FLOOR}`);
  console.log(`  P2 WINDOW WELL-FORMED ${seen.p2}/${sizes.length}`);
  console.log(`  P3 COUNTS EXACT       ${seen.p3}/${sizes.length}`);
  console.log(`  P4 TRUNCATION DECL.   ${seen.p4}/${sizes.length}`);
  console.log(`  P5 SUBREQUEST BOUND   ${seen.p5}/${sizes.length} (<= ${HARD_CAP} gets)`);
  console.log(`  P9 COVERAGE EXACT     ${seen.p9}/${sizes.length}`);
}

// ---------------------------------------------------------------- P8, the relay
// A stub origin that speaks the SAME contract as the fixed worker, so the relay is
// tested against the interface rather than against the implementation. It truncates
// hard (returns at most 4 paths per all-paths call) to force the fan-out.
async function runRelayPredicate() {
  if (!existsSync(RELAY)) {
    failures.push('P8: lib/relay_fetch.py does not exist — the relay still depends on one all-paths call');
    return;
  }
  const nowMs = Date.now();
  const paths = fleetPaths(12);
  const days = 10;
  const dates = Array.from({ length: days }, (_, i) => isoDaysAgo(i, nowMs));

  const server = createServer((req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1');
    if (u.pathname !== '/_b/stats') { res.writeHead(404).end('{}'); return; }
    const one = u.searchParams.get('path');
    const d = Math.max(1, Math.min(parseInt(u.searchParams.get('days') || '10', 10) || 10, one ? 30 : 10));
    if (one && !paths.includes(one)) { res.writeHead(404, { 'content-type': 'application/json' }).end(JSON.stringify({ error: 'unknown-path' })); return; }
    const use = one ? [one] : paths.slice(0, 4);
    const omitted = one ? [] : paths.slice(4);
    const dd = Array.from({ length: d }, (_, i) => isoDaysAgo(i, nowMs));
    const out = {};
    for (const p of use) { out[p] = {}; for (const day of dd) { const n = synth(p, day); if (n > 0) out[p][day] = n; } }
    const payload = { generated: new Date().toISOString(), window: { days: d, from: dd[dd.length - 1], to: dd[0] }, paths: out };
    if (omitted.length) payload.truncated = { paths_omitted: omitted, reason: 'subrequest-cap' };
    res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(payload));
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;

  const out = await new Promise((resolvePromise) => {
    const child = spawn('python3', [RELAY, '--source', `${base}/_b/stats`, '--stdout'],
      { cwd: ROOT, env: { ...process.env, PATHS_HINT: paths.join(',') } });
    let so = '', se = '';
    child.stdout.on('data', (c) => { so += c; });
    child.stderr.on('data', (c) => { se += c; });
    child.on('close', (code) => resolvePromise({ code, so, se }));
  });
  server.close();

  if (out.code !== 0) { failures.push(`P8: relay_fetch.py exited ${out.code}: ${out.se.slice(0, 300)}`); return; }
  let doc = null;
  try { doc = JSON.parse(out.so); } catch { failures.push(`P8: relay stdout is not JSON: ${out.so.slice(0, 200)}`); return; }

  const st = doc.stats || {};
  const got = st.paths || {};
  const missing = paths.filter((p) => !(p in got));
  if (!check('P8', missing.length === 0, `relay artifact is missing ${missing.length} path(s): ${missing.slice(0, 4).join(', ')} — the fan-out did not cover the fleet`)) return;
  if (!check('P8', (st.window?.days || 0) >= FLOOR, `relay artifact window is ${st.window?.days} days, below the ${FLOOR}-day floor`)) return;
  const dd = Array.from({ length: st.window.days }, (_, i) => isoDaysAgo(i, nowMs));
  for (const p of paths) {
    for (const day of dd) {
      const want = synth(p, day);
      const gotv = got[p][day];
      if (want > 0 && gotv !== want) { failures.push(`P8: ${p} ${day} = ${gotv}, dataset says ${want}`); return; }
      if (want === 0 && gotv) { failures.push(`P8: ${p} ${day} = ${gotv}, dataset says 0`); return; }
    }
  }
  if (!check('P8', doc.ok === true, `relay reported ok=${doc.ok}`)) return;
  console.log(`  P8 RELAY COMPLETE     ok — ${paths.length}/${paths.length} paths, window ${st.window.days}d, exact counts`);
}

// ---------------------------------------------------------------- main
console.log(`ORACLE 013 stats-window-floor — worker under test: ${workerRel}`);
try {
  await runWorkerPredicates();
  await runRelayPredicate();
} catch (e) {
  failures.push(`HARNESS: ${e && e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : e}`);
} finally {
  if (tmpRoot) await rm(tmpRoot, { recursive: true, force: true });
}

if (failures.length) {
  console.log(`\nVERDICT: FAIL (${failures.length})`);
  for (const f of failures.slice(0, 40)) console.log('  FAIL ' + f);
  process.exit(1);
}
console.log('\nVERDICT: PASS');
