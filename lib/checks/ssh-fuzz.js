#!/usr/bin/env node
/* lib/checks/ssh-fuzz.js — differential harness for lib/sshconfig.js.
 * Contributed by ship 007 (ssh-config-resolver, 2026-08-08).
 *
 * THIS FILE IS THE SHIP. The page is the presentation layer; this is the reason
 * to believe the page. It generates ssh_config files from a grammar and diffs
 * lib/sshconfig.js against the REAL `ssh -G` binary — not against a corpus the
 * maker wrote, which is exactly how ship 006 passed 23/23 and was still wrong.
 *
 * THE DIFF IS TOTAL, in both directions, which is the part that matters:
 *   forward  — every keyword we claim the config sets must have the value the
 *              real ssh reports;
 *   backward — every keyword the real ssh reports DIFFERENTLY from its default
 *              (measured per run with `-F /dev/null`) must be one we claimed.
 * Without the backward half, a resolver that silently drops half the file scores
 * a perfect run. Errors of omission are the ones a maker never thinks to test.
 *
 * Usage:  node lib/checks/ssh-fuzz.js [cases] [seed]
 * Requires: ssh(1) on PATH.  Verified against OpenSSH_9.6p1 Ubuntu-3ubuntu13.18.
 */
'use strict';
var fs = require('fs'), os = require('os'), path = require('path'), cp = require('child_process');
var sshconfig = require('../sshconfig.js');
var nfa = require('../nfa.js');

var N = parseInt(process.argv[2] || '2000', 10);
var SEED = parseInt(process.argv[3] || '20260808', 10);

/* Deterministic PRNG — a fuzz run that cannot be replayed is an anecdote. */
var _s = SEED >>> 0;
function rnd() { _s ^= _s << 13; _s >>>= 0; _s ^= _s >> 17; _s ^= _s << 5; _s >>>= 0; return _s / 4294967296; }
function pick(a) { return a[Math.floor(rnd() * a.length)]; }
function chance(p) { return rnd() < p; }
function int(lo, hi) { return lo + Math.floor(rnd() * (hi - lo + 1)); }

var TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'sshfuzz-'));
var CFG = path.join(TMP, 'c.cfg');
var LOCALUSER = cp.execSync('id -un').toString().trim();

/* Values chosen so `ssh -G` echoes them VERBATIM: no %-tokens, no ~, no case
   folding, no numeric renormalisation. Anything ssh would rewrite on the way out
   would turn a presentation difference into a false mismatch and train the
   author to ignore the harness — the worst possible outcome for it. */
var SCALARS = [
  ['port', function () { return String(int(1, 65535)); }],
  ['user', function () { return pick(['bob', 'alice', 'deploy', 'root', 'git', 'svc1']); }],
  ['hostname', function () { return pick(['a.ex', 'b.ex', 'inner.ex', 'x.y.ex', 'alpha', 'bravo']); }],
  ['hostkeyalias', function () { return pick(['ka1', 'ka2', 'ka3']); }],
  ['serveraliveinterval', function () { return String(int(0, 600)); }],
  ['serveralivecountmax', function () { return String(int(0, 10)); }],
  ['connecttimeout', function () { return String(int(0, 300)); }],
  ['connectionattempts', function () { return String(int(1, 10)); }],
  ['numberofpasswordprompts', function () { return String(int(0, 9)); }],
  ['forwardagent', function () { return pick(['yes', 'no']); }],
  ['compression', function () { return pick(['yes', 'no']); }],
  ['batchmode', function () { return pick(['yes', 'no']); }],
  ['checkhostip', function () { return pick(['yes', 'no']); }],
  ['tcpkeepalive', function () { return pick(['yes', 'no']); }],
  ['identitiesonly', function () { return pick(['yes', 'no']); }],
  ['exitonforwardfailure', function () { return pick(['yes', 'no']); }],
  ['forwardx11', function () { return pick(['yes', 'no']); }],
  ['requesttty', function () { return pick(['no', 'yes', 'force', 'auto']); }],
  ['stricthostkeychecking', function () { return pick(['yes', 'no', 'ask', 'accept-new', 'off']); }],
  ['controlmaster', function () { return pick(['yes', 'no', 'ask', 'auto', 'autoask']); }],
  ['controlpath', function () { return '/tmp/cm' + int(1, 9); }],
  ['proxyjump', function () { return pick(['jump1', 'u@jump2', 'jump3']); }],
  ['loglevel', function () { return pick(['QUIET', 'FATAL', 'ERROR', 'INFO', 'VERBOSE', 'DEBUG']); }],
  ['tag', function () { return pick(['t1', 't2']); }],
  ['remotecommand', function () { return pick(['uptime', 'whoami']); }],
  ['setenv', function () { return 'AA' + int(1, 3) + '=v' + int(1, 3); }],
  ['requiredrsasize', function () { return String(int(1024, 4096)); }]
];
var ACCUM = [
  ['identityfile', function () { return '/tmp/k' + int(1, 5); }],
  ['certificatefile', function () { return '/tmp/c' + int(1, 5) + '.pub'; }],
  ['sendenv', function () { return 'EE' + int(1, 5); }],
  ['dynamicforward', function () { return String(int(1024, 60000)); }]
];

var HOSTS = ['alpha', 'bravo', 'a.ex', 'b.ex', 'bad.ex', 'good.ex', 'web1', 'web2',
             'db1', 'ALPHA', 'Alpha', 'x', 'inner.ex', 'jump1'];
var PATBITS = ['alpha', 'bravo', '*', '*.ex', 'a.ex', 'b.ex', 'bad.ex', 'web*', 'w?b1',
               'ALPHA', '*1', 'db?', 'x', '?', 'a*b', 'inner.ex', 'jump1', 'nomatch*'];
var USERS = ['bob', 'alice', 'deploy', 'root', 'git', 'svc1'];

function hostPatternList() {
  var n = int(1, 3), out = [], i;
  for (i = 0; i < n; i++) { var p = pick(PATBITS); out.push(chance(0.2) ? '!' + p : p); }
  return out.join(' ');
}
function commaList(bits) {
  var n = int(1, 3), out = [], i;
  for (i = 0; i < n; i++) { var p = pick(bits); out.push(chance(0.2) ? '!' + p : p); }
  return out.join(',');
}
function matchHeader() {
  var parts = [], n = int(1, 2), i;
  if (chance(0.12)) return 'Match all';
  for (i = 0; i < n; i++) {
    var c = pick(['host', 'originalhost', 'user', 'localuser']);
    var bits = (c === 'user') ? USERS.concat(['*', 'b*', '!root', 'a?ice'])
             : (c === 'localuser') ? [LOCALUSER, '*', 'nobody', '!nobody']
             : PATBITS;
    parts.push(c + ' ' + commaList(bits));
  }
  return 'Match ' + parts.join(' ');
}
function directiveLine(pool) {
  var d = pick(pool), k = d[0], v = d[1]();
  var sep = chance(0.12) ? '=' : (chance(0.15) ? '\t' : ' ');
  var kw = chance(0.15) ? k.toUpperCase() : (chance(0.15) ? k.charAt(0).toUpperCase() + k.slice(1) : k);
  var val = chance(0.1) ? '"' + v + '"' : v;
  var tail = chance(0.12) ? '   # note' : '';
  var indent = chance(0.7) ? (chance(0.5) ? '  ' : '\t') : '';
  return indent + kw + sep + val + tail;
}
/* MALFORMATIONS. Added 2026-08-08 after two independent checkers refuted the
   first version of this harness by attacking what its grammar could not produce:
   it only ever emitted WELL-FORMED configs, so it was evidence about resolution
   and silent about rejection — and all four defects they found lived there.
   OpenSSH refuses a bad file wholesale rather than warning, so the property under
   test is an agreement about REFUSAL: the resolver must report a fatal error for
   exactly the files ssh exits non-zero on, and for no others. */
var MALFORM = [
  function () { return 'Frobnicate yes'; },                    /* unknown keyword          */
  function () { return 'Port'; },                              /* keyword, no argument     */
  function () { return pick(['User', 'Hostname', 'Compression']); },
  function () { return 'Match all ' + pick(['host foo', 'all', 'canonical']); },
  function () { return 'Match host foo,bar user root all'; },  /* >1 attribute before all  */
  function () { return 'Host'; },                              /* Host, no pattern         */
  function () { return 'Match'; },                             /* Match, no criteria       */
  function () { return 'Match host'; },                        /* criterion, no argument   */
  function () { return 'Match nosuchcriterion foo'; },
  function () { return '  HostKeyAlias "unterminated'; },
  function () { return 'Match exec'; },
  function () { return 'Host * ' + '\r' + 'Port 9'; },          /* lone CR is NOT a newline */
  function () { return 'Match host foo all'; },                /* LEGAL — must NOT be fatal */
  function () { return 'Match user root all'; },               /* LEGAL — must NOT be fatal */
  function () { return 'Match canonical all'; }                /* LEGAL — must NOT be fatal */
];

function genConfig() {
  var out = [], nBlocks = int(1, 5), i, j;
  if (chance(0.3)) { var g = int(1, 2); for (j = 0; j < g; j++) out.push(directiveLine(SCALARS)); }
  for (i = 0; i < nBlocks; i++) {
    if (chance(0.25)) out.push('# comment ' + i);
    if (chance(0.2)) out.push('');
    out.push(chance(0.35) ? matchHeader() : ('Host ' + hostPatternList()));
    var nd = int(1, 4);
    for (j = 0; j < nd; j++) out.push(directiveLine(chance(0.25) ? ACCUM : SCALARS));
  }
  if (chance(0.30)) out.splice(int(0, out.length), 0, pick(MALFORM)());
  return out.join(chance(0.05) ? '\r\n' : '\n') + '\n';
}

/* ── oracle ─────────────────────────────────────────────────────────────── */
function G(cfgPath, host, user) {
  var args = ['-F', cfgPath, '-G'];
  if (user) args.push('-l', user);
  args.push(host);
  var r = cp.spawnSync('ssh', args, { encoding: 'utf8' });
  return { out: r.stdout || '', err: r.stderr || '', code: r.status };
}
function toMap(out) {
  var m = Object.create(null);
  out.split('\n').forEach(function (L) {
    if (!L.trim()) return;
    var i = L.indexOf(' ');
    var k = i < 0 ? L : L.slice(0, i), v = i < 0 ? '' : L.slice(i + 1);
    (m[k] || (m[k] = [])).push(v);
  });
  return m;
}
var IGNORE = { host: 1 };            /* -G echoes the original host argument; not a resolved option */

/* `ssh -G` REWRITES values on the way out. These are presentation differences,
   not disagreements, and every one below was observed in a real run:
     yes/no        -> true/false        (controlmaster, requesttty, stricthostkeychecking…)
     off           -> false             (stricthostkeychecking off)
     QUIET         -> SILENT            (loglevel; an alias, not a level)
     whoami        -> "whoami"          (string options are re-quoted)
   Normalising them here is the only honest place: lib/sshconfig.js must keep
   showing the user the literal text in their own file, because that is what they
   are trying to find. Normalising in the LIBRARY would make the page lie to look
   like the harness; normalising in the HARNESS makes the harness see through a
   cosmetic difference to the semantic one underneath. */
var BOOL_TRUE = { yes: 1, true: 1 }, BOOL_FALSE = { no: 1, false: 1, off: 1 };
function normalise(k, v) {
  var s = String(v).trim();
  if (s.length > 1 && s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') s = s.slice(1, -1);
  s = s.toLowerCase();
  if (BOOL_TRUE[s]) return 'true';
  if (BOOL_FALSE[s]) return 'false';
  if (k === 'loglevel' && s === 'quiet') return 'silent';
  return s;
}
function sameList(a, b, k) {
  if (a.length !== b.length) return false;
  for (var i = 0; i < a.length; i++) if (normalise(k, a[i]) !== normalise(k, b[i])) return false;
  return true;
}

/* ── one case ───────────────────────────────────────────────────────────── */
function runCase(cfg, host, user) {
  fs.writeFileSync(CFG, cfg);
  var live = G(CFG, host, user);
  var parsed = sshconfig.parse(cfg);
  var sshRefused = (live.code !== 0 || !live.out.trim());

  /* THE REFUSAL AGREEMENT — both directions. Refusing a file ssh accepts is as
     wrong as accepting one ssh refuses; the first hides a real answer, the second
     invents one. */
  /* NOT every ssh refusal is a config-SYNTAX refusal. `ProxyJump jump1` while
     connecting to `jump1` makes ssh exit with "jumphost loop via jump1" — a fact
     about the resulting connection graph, not about the file. A static resolver
     cannot and should not detect it, so it is excluded BY NAME (never by a loose
     substring) and disclosed on the page rather than quietly absorbed. */
  var NON_SYNTAX = /jumphost loop via /;
  if (sshRefused && NON_SYNTAX.test(live.err)) {
    return { skipped: true, why: 'non-syntactic refusal: ' + live.err.trim().split('\n')[0] };
  }
  if (sshRefused && !parsed.fatal.length) {
    return { skipped: false, mismatches: [{ kind: 'should-have-refused', key: '-',
      ssh: (live.err.trim().split('\n')[0] || 'ssh exited ' + live.code) }] };
  }
  if (!sshRefused && parsed.fatal.length) {
    return { skipped: false, mismatches: [{ kind: 'refused-a-good-file', key: '-',
      ours: parsed.fatal.map(function (f) { return 'line ' + f.line + ': ' + f.message.slice(0, 90); }) }] };
  }
  if (sshRefused) return { skipped: false, mismatches: [], refusalAgreed: true };

  var base = G('/dev/null', host, user);
  if (base.code !== 0) return { skipped: true, why: 'baseline failed' };

  var L = toMap(live.out), B = toMap(base.out);
  var budget = nfa.makeBudget(20000000, 5000);
  var r = sshconfig.resolve(parsed, { host: host, user: user || '', localuser: LOCALUSER }, budget);
  if (r.budgetExceeded) return { skipped: true, why: 'budget exceeded' };

  var mism = [];
  /* forward: everything we claim must be right */
  Object.keys(r.effective).forEach(function (k) {
    if (IGNORE[k]) return;
    var e = r.effective[k];
    var ours = e.accumulates ? e.entries.map(function (x) { return x.value; }) : [e.value];
    var theirs = L[k];
    if (!theirs) { mism.push({ kind: 'we-claim-ssh-silent', key: k, ours: ours }); return; }
    if (!sameList(ours, theirs, k)) mism.push({ kind: 'value', key: k, ours: ours, theirs: theirs });
  });
  /* backward: everything the config demonstrably changed must be claimed.
     A first attempt compared against a `-F /dev/null` baseline and flagged any
     keyword ssh reported differently that we had not claimed. It produced false
     defects immediately, and the reason is worth recording: OpenSSH DERIVES some
     options from others — `BatchMode yes` silently sets `ServerAliveInterval 300`
     — so ssh reports a change no line in the file made, and a config resolver is
     right not to claim it. Filtering those by hand would mean maintaining a table
     of OpenSSH's internal side-effects, which is a maker's-own-oracle by another
     name. So the backward check was replaced by a stronger one:

     REPLAY. Take our answer, write it out as a minimal config (one `Host *`
     REPLAY. Take our answer, write it out as a minimal config (one `Host *`
     block containing exactly the keywords and values we claim), and run the real
     ssh over THAT. If our resolution is correct, ssh applied to our answer must
     produce byte-for-byte the same effective options as ssh applied to the user's
     original file — every one of the ~80 options it prints, not just the ones we
     thought to look at. Derived options come out right for free: we claim
     `batchmode yes`, so the replay derives `serveraliveinterval 300` exactly as
     the original did. A resolver that drops a directive, invents one, or picks
     the wrong winner cannot survive this, because the comparison is over ssh's
     entire output on both sides. */
  var recon = [], skipReplay = false;
  Object.keys(r.effective).forEach(function (k) {
    var e = r.effective[k];
    var vals = e.accumulates ? e.entries.map(function (x) { return x.value; }) : [e.value];
    vals.forEach(function (v) {
      if (/[\r\n]/.test(v)) { skipReplay = true; return; }
      /* ProxyCommand & friends take the rest of the line RAW — re-quoting their
         value would make the replay disagree with itself rather than with the
         resolver. (Caught here as five "replay" mismatches whose forward check
         passed: a harness artefact, and worth the note so a future reader does
         not "fix" the library to match a broken reconstruction.) */
      if (sshconfig.RESTS_OF_LINE[k]) recon.push('  ' + k + ' ' + v);
      else recon.push('  ' + k + ' "' + String(v).replace(/"/g, '\\"') + '"');
    });
  });
  var derived = [];
  if (!skipReplay) {
    var RCFG = CFG + '.replay';
    fs.writeFileSync(RCFG, 'Host *\n' + recon.join('\n') + '\n');
    var rep = G(RCFG, host, user);
    if (rep.code !== 0 || !rep.out.trim()) {
      mism.push({ kind: 'replay-refused', key: '-', detail: (rep.err.trim().split('\n')[0] || '') });
    } else {
      var R = toMap(rep.out);
      var keys = {};
      Object.keys(L).forEach(function (k) { keys[k] = 1; });
      Object.keys(R).forEach(function (k) { keys[k] = 1; });
      Object.keys(keys).forEach(function (k) {
        if (IGNORE[k]) return;
        var a = L[k] || [], b = R[k] || [];
        if (!sameList(a, b, k)) mism.push({ kind: 'replay', key: k, original: a, fromOurAnswer: b });
      });
    }
  }
  return { skipped: false, mismatches: mism, derived: derived };
}

/* ── main ───────────────────────────────────────────────────────────────── */
var stats = { run: 0, skipped: 0, bad: 0, refusals: 0 }, failures = [], derivedSeen = {};
for (var i = 0; i < N; i++) {
  var cfg = genConfig(), host = pick(HOSTS), user = chance(0.35) ? pick(USERS) : '';
  var res;
  try { res = runCase(cfg, host, user); }
  catch (e) { res = { skipped: false, mismatches: [{ kind: 'threw', key: '-', detail: String(e && e.message) }] }; }
  if (res.skipped) { stats.skipped++; continue; }
  stats.run++;
  (res.derived || []).forEach(function (d) { derivedSeen[d.key] = (derivedSeen[d.key] || 0) + 1; });
  if (res.refusalAgreed) stats.refusals++;
  if (res.mismatches.length) {
    stats.bad++;
    if (failures.length < 40) failures.push({ cfg: cfg, host: host, user: user, mismatches: res.mismatches });
  }
}
console.log(JSON.stringify({ seed: SEED, requested: N, evaluated: stats.run, skipped: stats.skipped,
  failed: stats.bad, refusalsAgreed: stats.refusals, derivedByOpenSSH: derivedSeen,
  ssh: cp.execSync('ssh -V 2>&1').toString().trim() }, null, 1));
if (failures.length) {
  console.log('\n===== FIRST ' + failures.length + ' FAILURES =====');
  failures.forEach(function (f, n) {
    console.log('\n--- #' + (n + 1) + '  host=' + JSON.stringify(f.host) + ' user=' + JSON.stringify(f.user));
    console.log(f.cfg.replace(/\r/g, '\\r'));
    f.mismatches.forEach(function (m) { console.log('   ' + JSON.stringify(m)); });
  });
  process.exit(1);
}
console.log('\nzero mismatches on ' + stats.run + ' evaluated cases.');
