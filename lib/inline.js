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

text = text.replace(/^[ \t]*<!--[ \t]*inline:([A-Za-z0-9_\-./]+)[ \t]*-->[ \t]*$/gm, function (_m, rel) {
  var p = path.join(repoRoot, rel);
  var body = fs.readFileSync(p, 'utf8');
  /* A ship page is HTML: the one sequence that can escape a <script> element is
     "</script" in any case. No lib/ file contains one, and if a future one does we
     fail loudly rather than emit a broken (or injectable) page. */
  if (/<\/script/i.test(body)) throw new Error(rel + ' contains "</script" and cannot be inlined');
  used.push(rel);
  return '<script>/* inlined verbatim from ' + rel + ' — regenerate with lib/inline.js */\n' +
         body.replace(/\s+$/, '') + '\n</script>';
});

fs.writeFileSync(out, text);
console.error('inlined ' + used.length + ' module(s): ' + used.join(', ') + ' -> ' + out);
