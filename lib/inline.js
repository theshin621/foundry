#!/usr/bin/env node
/* lib/inline.js — assemble a self-contained ship page from a source file plus
 * lib/ modules. Contributed by ship 003 (codeowners, 2026-08-04).
 *
 * WHY: every ship page must be self-contained (one file, no external JS), but the
 * code it runs should stay canonical in lib/ so the next ship inherits fixes rather
 * than a fork. Ships 001 and 002 solved that by hand-copying, which means the
 * inlined copy silently drifts from lib/ and nobody notices. This makes the copy
 * mechanical and CHECKABLE: run it again, diff the output, and any drift is a
 * non-empty diff.
 *
 * Convention: put `<!-- inline:lib/foo.js -->` on its own line in the source file.
 * It is replaced by <script>…the file's exact bytes…</script>.
 *
 * Usage:  node lib/inline.js <src.html> <out.html>
 * Verify: node lib/inline.js <src.html> /tmp/o && diff /tmp/o <out.html>
 */
'use strict';
var fs = require('fs'), path = require('path');

var src = process.argv[2], out = process.argv[3];
if (!src || !out) { console.error('usage: node lib/inline.js <src.html> <out.html>'); process.exit(2); }

var repoRoot = path.resolve(__dirname, '..');
var text = fs.readFileSync(src, 'utf8');
var used = [];

var emitted = [];   /* the EXACT script bodies this run claims to have produced */

text = text.replace(/^[ \t]*<!--[ \t]*inline:([A-Za-z0-9_\-./]+)[ \t]*-->[ \t]*$/gm, function (_m, rel) {
  var p = path.resolve(repoRoot, rel);
  /* Repo containment. Round-3 checker finding #6: `<!-- inline:../../../../etc/hostname -->`
     was accepted and inlined. Not externally reachable (it needs control of the loop's own
     source file), but this is a shared lib/ tool every future ship inherits, and a build
     tool that will read any path on the box is a gift to the next mistake. */
  if (p !== repoRoot && p.indexOf(repoRoot + path.sep) !== 0) {
    throw new Error('inline directive escapes the repo: ' + rel + ' -> ' + p);
  }
  var body = fs.readFileSync(p, 'utf8');
  /* A ship page is HTML: the one sequence that can escape a <script> element is
     "</script" in any case. No lib/ file contains one, and if a future one does we
     fail loudly rather than emit a broken (or injectable) page. */
  if (/<\/script/i.test(body)) throw new Error(rel + ' contains "</script" and cannot be inlined');
  /* SECOND ESCAPE VECTOR — added 2026-08-09 after incident #008 (BOTTLENECKS #1).
     "</script" is NOT the only way out. Per HTML5 §13.2.5.15-21, "<!--" inside script
     raw text enters the script-data-escaped state, and a following "<script" enters the
     DOUBLE-escaped state, in which the next "</script>" does NOT close the element. The
     rest of the page is then swallowed into one broken script that never executes - the
     page still returns 200, and that is exactly how ship #008 shipped an inert beacon on
     five pages while every automated check stayed green. Reject the pair, loudly. */
  var cOpen = body.indexOf('<!--');
  if (cOpen !== -1 && /<script/i.test(body.slice(cOpen))) {
    throw new Error(rel + ' contains "<!--" followed by "<script": inlining it would enter the ' +
      'HTML script-data-double-escaped state and produce a script element that never closes ' +
      '(incident #008). Rewrite the source so the two do not co-occur.');
  }
  used.push(rel);
  var scriptBody = '/* inlined verbatim from ' + rel + ' — regenerate with lib/inline.js */\n' +
                   body.replace(/\s+$/, '') + '\n';
  emitted.push(scriptBody);
  return '<script>' + scriptBody + '</script>';
});

/* POST-CONDITION, added 2026-08-09, CORRECTED the same day after the round-3 checker
   demonstrated the first version was hollow. The two guards above are input rules; this
   is the output proof. Before writing anything, hand the assembled document to a
   spec-defined tokenizer (lib/checks/html-scripts.py, Python's html.parser) and refuse to
   emit a page unless EVERY body this run claims to have inlined is, byte for byte, one
   whole live script element in the result.

   The `--expect` argument is the whole point and its absence was checker finding #2: the
   first version called the checker with no expectation, so "verified" meant only
   "structurally parseable", and a source file with a stray `<script>` before the directive
   produced an output where the inlined module was merged into another element — inert, and
   passing. Structure without an expectation is not verification.

   If python3 or the checker is missing the inliner FAILS - it never degrades to
   "couldn't check, write it anyway". */
var checker = path.join(__dirname, 'checks', 'html-scripts.py');
var os = require('os');
var stamp = process.pid + '-' + used.length;
var tmp = path.join(os.tmpdir(), 'inline-verify-' + stamp + '.html');
var expectFile = path.join(os.tmpdir(), 'inline-expect-' + stamp + '.json');
fs.writeFileSync(tmp, text);
fs.writeFileSync(expectFile, JSON.stringify(emitted));
var res = require('child_process').spawnSync(
  'python3', [checker, '--expect', expectFile, tmp], { encoding: 'utf8' });
try { fs.unlinkSync(tmp); fs.unlinkSync(expectFile); } catch (e) {}
if (res.error || res.status === null) {
  throw new Error('cannot verify output: python3 ' + checker + ' did not run (' +
    (res.error || res.stderr) + '). Refusing to write an unverified page.');
}
if (res.status !== 0) {
  var why = res.stderr || '';
  try { why = JSON.parse(res.stdout).map(function (r) { return r.errors.join('; '); }).join(' | '); } catch (e) {}
  throw new Error('assembled page FAILS the script-structure check: ' + why);
}

fs.writeFileSync(out, text);
console.error('inlined ' + used.length + ' module(s): ' + used.join(', ') + ' -> ' + out +
              ' [all inlined bodies verified as live script elements by lib/checks/html-scripts.py]');
