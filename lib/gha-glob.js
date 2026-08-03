/* lib/gha-glob.js — GitHub Actions filter-pattern matcher, LINEAR TIME.
 * Contributed by ship 002 (gha-trigger, rebuild 2026-08-03). Ships INLINE a copy
 * (pages stay self-contained); this file is the canonical source.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THIS FILE EXISTS
 *
 * Ship 002 shipped a hand-rolled glob→RegExp compiler twice and failed twice:
 * first an XSS, then catastrophic backtracking (ReDoS) that froze the tab on
 * ordinary pasted text. A static complexity budget was tried and PROVEN
 * INSUFFICIENT by the checker — a pattern sitting exactly at the cap still hung
 * >10s, and the budget broke a correct verdict on legitimate input.
 *
 * SEMANTICS ARE BORROWED, NOT INVENTED.
 *   Source: nektos/act, pkg/workflowpattern/workflow_pattern.go
 *   Licence: MIT (Copyright (c) 2019 nektos/act contributors)
 *   Pinned at commit 4f411281417e88660bea1c1a1749aa71ae0bd60f (2026-06-01)
 *   https://github.com/nektos/act/blob/master/pkg/workflowpattern/workflow_pattern.go
 * `PatternToRegex`, the `[...]` validation rules, and the `Skip`/`Filter` set
 * logic below are a line-for-line port.
 *
 * THE TRAP INSIDE THE BORROW — read this before "simplifying" this file:
 *   act is safe because Go's `regexp` is RE2: linear time, NO BACKTRACKING.
 *   act's PatternToRegex emits ordinary regex text; the safety lives entirely in
 *   Go's engine. JavaScript's RegExp is a BACKTRACKING engine. So porting
 *   PatternToRegex verbatim into `new RegExp(...)` reintroduces the exact ReDoS
 *   that killed ship 002. **This file therefore never calls RegExp on a
 *   user-supplied pattern.** It compiles to a Thompson NFA program and runs a
 *   Pike-VM state-set simulation: O(len(value) x len(program)), with no
 *   backtracking possible by construction. That is a property of the algorithm,
 *   not a budget that can be exceeded.
 *
 * BYTES, NOT CHARACTERS. Go indexes `pattern[pos]` as a BYTE and validates class
 * members with byte comparisons ('A'..'z' spans 0x41..0x7A, which deliberately
 * includes [ \ ] ^ _ ` ). This port encodes pattern and value as UTF-8 bytes so
 * those comparisons agree. Multi-byte runes never contain 0x0A or 0x2F, so
 * "any byte except \n" and "any byte except /" under * and + accept exactly the
 * same strings as Go's rune-wise `.` and `[^/]` do.
 * KNOWN, DELIBERATE DIVERGENCE: for a NON-ASCII literal in the *pattern*, Go
 * feeds single invalid-UTF-8 bytes to the regex parser, which turns each into
 * U+FFFD — so act does not match a non-ASCII literal against itself. This port
 * matches the bytes literally (the sane behaviour). GitHub's own behaviour here
 * is unverified, so callers should say so rather than claim it. The differential
 * harness in lib/checks is therefore run over ASCII.
 *
 * NEVER THROWS. Every entry point returns a value; invalid patterns come back as
 * `{error: "..."}`. Ship 002's second security finding was untrusted input
 * reaching innerHTML through a THROWN Error message — a function that cannot
 * throw cannot re-arm that sink. Callers must still escape `.error` (lib/esc.js).
 * ───────────────────────────────────────────────────────────────────────────── */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.ghaGlob = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ── opcodes ───────────────────────────────────────────────────────────── */
  var CHAR = 0, SPLIT = 1, JMP = 2, MATCH = 3;
  /* CHAR kinds */
  var LIT = 0, NOT = 1, SET = 2;

  var BYTE_NL = 0x0A, BYTE_SLASH = 0x2F;

  function utf8(s) {
    if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(s);
    /* Node <11 / exotic hosts */
    var out = [], i, c;
    for (i = 0; i < s.length; i++) {
      c = s.charCodeAt(i);
      if (c < 0x80) out.push(c);
      else if (c < 0x800) out.push(0xC0 | (c >> 6), 0x80 | (c & 63));
      else if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length) {
        var c2 = s.charCodeAt(++i);
        var cp = 0x10000 + ((c - 0xD800) << 10) + (c2 - 0xDC00);
        out.push(0xF0 | (cp >> 18), 0x80 | ((cp >> 12) & 63), 0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
      } else out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
    return new Uint8Array(out);
  }

  /* ── AST atoms ─────────────────────────────────────────────────────────── */
  function chLit(b) { return { t: 'ch', k: LIT, b: b }; }
  function chNot(b) { return { t: 'ch', k: NOT, b: b }; }
  function chSet(set) { return { t: 'ch', k: SET, s: set }; }
  function cat(list) { return { t: 'cat', a: list }; }
  function star(a) { return { t: 'star', a: a }; }
  function plus(a) { return { t: 'plus', a: a }; }
  function opt(a) { return { t: 'opt', a: a }; }

  /* ── emit AST → Pike-VM program ────────────────────────────────────────── */
  function emit(node, prog) {
    var sp, l1, i;
    switch (node.t) {
      case 'ch':
        prog.push({ op: CHAR, k: node.k, b: node.b, s: node.s });
        break;
      case 'cat':
        for (i = 0; i < node.a.length; i++) emit(node.a[i], prog);
        break;
      case 'star':
        l1 = prog.length;
        sp = { op: SPLIT, x: 0, y: 0 };
        prog.push(sp);
        sp.x = prog.length;
        emit(node.a, prog);
        prog.push({ op: JMP, x: l1 });
        sp.y = prog.length;
        break;
      case 'plus':
        l1 = prog.length;
        emit(node.a, prog);
        sp = { op: SPLIT, x: l1, y: 0 };
        prog.push(sp);
        sp.y = prog.length;
        break;
      case 'opt':
        sp = { op: SPLIT, x: 0, y: 0 };
        prog.push(sp);
        sp.x = prog.length;
        emit(node.a, prog);
        sp.y = prog.length;
        break;
    }
  }

  /* ── compile: a line-for-line port of act's PatternToRegex ─────────────── */
  /* Returns { pattern, negative, prog } or { pattern, negative, error }. */
  function compilePattern(rawpattern) {
    var raw = String(rawpattern == null ? '' : rawpattern);
    var negative = false, pattern = raw;
    if (pattern.charAt(0) === '!') { negative = true; pattern = pattern.slice(1); }

    var p = utf8(pattern), len = p.length;
    var atoms = [];                 /* sequence of AST atoms                */
    var quant = [];                 /* parallel repetition state of atom i:
                                       0 = plain atom (no repetition yet)
                                       1 = repeated, greedy
                                       2 = repeated, already flagged non-greedy
                                       Go's rule, confirmed by differential against
                                       RE2: a repetition takes AT MOST ONE trailing
                                       '?' (the non-greedy flag). A second '?', or
                                       any '+', is "invalid nested repetition
                                       operator". `a??` is legal; `a???`, `a?+`,
                                       `*??` and `*+` are all errors.            */
    var errors = [];                /* {pos, msg} — collected, like act      */
    var regexErr = null;            /* Go regexp.Compile-stage error         */
    var pos = 0;

    function push(node, qstate) { atoms.push(node); quant.push(qstate || 0); }

    while (pos < len) {
      var c = p[pos];

      if (c === 0x2A /* * */) {
        if (pos + 1 < len && p[pos + 1] === 0x2A) {
          if (pos + 2 < len && p[pos + 2] === BYTE_SLASH) {
            /* "(.+/)?" */
            push(opt(cat([plus(chNot(BYTE_NL)), chLit(BYTE_SLASH)])), 1);
            pos += 3;
          } else {
            /* ".*" */
            push(star(chNot(BYTE_NL)), 1);
            pos += 2;
          }
        } else {
          /* "[^/]*" */
          push(star(chNot(BYTE_SLASH)), 1);
          pos += 1;
        }
        continue;
      }

      if (c === 0x2B /* + */ || c === 0x3F /* ? */) {
        if (pos > 0) {
          var last = atoms.length - 1;
          if (last < 0) {
            /* pos>0 yet nothing emitted: only reachable through an error path */
            push(chLit(c), 0);
          } else if (quant[last] === 0) {
            /* first repetition on a plain atom */
            atoms[last] = (c === 0x2B) ? plus(atoms[last]) : opt(atoms[last]);
            quant[last] = 1;
          } else if (quant[last] === 1 && c === 0x3F) {
            /* '?' after a repetition = the non-greedy flag. Greediness changes
               WHICH match is found, never WHETHER one exists, and this matcher is
               whole-string existence-only — so it is a structural no-op. It may
               only be applied once. */
            quant[last] = 2;
          } else {
            if (!regexErr) regexErr = 'invalid nested repetition operator';
          }
        } else {
          /* act QuoteMeta()s a leading '+'/'?' — a literal */
          push(chLit(c), 0);
        }
        pos++;
        continue;
      }

      if (c === 0x5B /* [ */) {
        pos++;
        if (pos < len && p[pos] === 0x5D /* ] */) {
          errors.push({ pos: pos, msg: "Unexpected empty brackets '[]'" });
          pos++;
          continue;                      /* act: `break` out of the switch */
        }
        var set = new Uint8Array(256);
        var startPos = pos;
        var inRange = function (lo, hi, a, b) { return a >= lo && a <= hi && b >= lo && b <= hi && a <= b; };
        while (pos < len && p[pos] !== 0x5D) {
          if (p[pos] === 0x2D /* - */) {
            if (pos <= startPos || pos + 1 >= len) {
              errors.push({ pos: pos, msg: 'Invalid range' });
              pos++;
              continue;
            }
            var a = p[pos - 1], b = p[pos + 1];
            if (!inRange(0x41, 0x7A, a, b) && !inRange(0x30, 0x39, a, b)) {
              errors.push({ pos: pos, msg: 'Ranges can only include a-z, A-Z, A-z, and 0-9' });
              pos++;
              continue;
            }
            for (var x = a; x <= b; x++) set[x] = 1;
            pos += 2;
          } else {
            var m = p[pos];
            if (!(m >= 0x41 && m <= 0x7A) && !(m >= 0x30 && m <= 0x39)) {
              errors.push({ pos: pos, msg: 'Ranges can only include a-z, A-Z and 0-9' });
              pos++;
              continue;
            }
            set[m] = 1;
            pos++;
          }
        }
        if (pos >= len || p[pos] !== 0x5D) {
          errors.push({ pos: pos, msg: "Missing closing bracket ']' after '['" });
          pos++;
        }
        pos++;
        push(chSet(set), 0);
        continue;
      }

      if (c === 0x5C /* \ */) {
        if (pos + 1 >= len) {
          errors.push({ pos: pos, msg: 'Missing symbol after \\' });
          pos++;
          continue;
        }
        push(chLit(p[pos + 1]), 0);
        pos += 2;
        continue;
      }

      push(chLit(c), 0);
      pos++;
    }

    if (errors.length) {
      errors.sort(function (u, v) { return u.pos - v.pos; });
      var parts = errors.map(function (e) { return 'Position: ' + e.pos + ' Error: ' + e.msg; });
      return { pattern: pattern, negative: negative,
               error: "invalid Pattern '" + pattern + "': " + parts.join(', ') };
    }
    if (regexErr) {
      return { pattern: pattern, negative: negative,
               error: 'error parsing pattern: ' + regexErr };
    }

    var prog = [];
    emit(cat(atoms), prog);
    prog.push({ op: MATCH });
    return { pattern: pattern, negative: negative, prog: prog };
  }

  function compilePatterns(list) {
    var out = [], i, cp;
    for (i = 0; i < list.length; i++) {
      cp = compilePattern(list[i]);
      if (cp.error) return { error: cp.error, at: list[i] };
      out.push(cp);
    }
    return { patterns: out };
  }

  /* ── run: Pike VM. Linear in len(value) x len(prog). Cannot backtrack. ─── */
  function testByte(ins, b) {
    if (ins.k === LIT) return b === ins.b;
    if (ins.k === NOT) return b !== ins.b;
    return ins.s[b] === 1;
  }

  function addThread(prog, list, pc, gen, g, stack) {
    stack.length = 0;
    stack.push(pc);
    while (stack.length) {
      var q = stack.pop();
      if (gen[q] === g) continue;
      gen[q] = g;
      var ins = prog[q];
      if (ins.op === SPLIT) { stack.push(ins.y); stack.push(ins.x); }
      else if (ins.op === JMP) { stack.push(ins.x); }
      else list.push(q);
    }
  }

  /* Whole-string (anchored) match of `value` against a compiled pattern. */
  function matches(compiled, value) {
    if (!compiled || compiled.error || !compiled.prog) return false;
    var prog = compiled.prog, n = prog.length;
    var bytes = utf8(String(value == null ? '' : value));
    var gen = new Int32Array(n);
    for (var z = 0; z < n; z++) gen[z] = -1;
    var clist = [], nlist = [], stack = [], g = 0, i, k, pc, ins;

    addThread(prog, clist, 0, gen, g, stack);
    for (i = 0; i < bytes.length; i++) {
      if (clist.length === 0) return false;
      g++;
      nlist.length = 0;
      var b = bytes[i];
      for (k = 0; k < clist.length; k++) {
        pc = clist[k];
        ins = prog[pc];
        if (ins.op === CHAR && testByte(ins, b)) addThread(prog, nlist, pc + 1, gen, g, stack);
      }
      var t = clist; clist = nlist; nlist = t;
    }
    for (k = 0; k < clist.length; k++) if (prog[clist[k]].op === MATCH) return true;
    return false;
  }

  /* ── act's set logic, ported exactly ───────────────────────────────────── */

  /* Skip(): the semantics of an INCLUDE list (branches:, tags:, paths:).
     Returns true when the workflow should be SKIPPED. Trace entries explain why. */
  function skip(sequence, input, trace) {
    if (!sequence || sequence.length === 0) return false;
    for (var f = 0; f < input.length; f++) {
      var file = input[f], matched = false;
      for (var i = 0; i < sequence.length; i++) {
        var item = sequence[i];
        if (matches(item, file)) {
          if (item.negative) {
            matched = false;
            if (trace) trace.push({ value: file, pattern: '!' + item.pattern, effect: 'excluded' });
          } else {
            matched = true;
            if (trace) trace.push({ value: file, pattern: item.pattern, effect: 'included' });
          }
        }
      }
      if (matched) return false;
    }
    return true;
  }

  /* Filter(): the semantics of an IGNORE list (branches-ignore:, paths-ignore:).
     Returns true when the workflow should be SKIPPED. */
  function filter(sequence, input, trace) {
    if (!sequence || sequence.length === 0) return false;
    for (var f = 0; f < input.length; f++) {
      var file = input[f], matched = false;
      for (var i = 0; i < sequence.length; i++) {
        var item = sequence[i];
        if (matches(item, file) === !item.negative) {
          if (trace) trace.push({ value: file, pattern: (item.negative ? '!' : '') + item.pattern, effect: 'ignored' });
          matched = true;
          break;
        }
      }
      if (!matched) return false;
    }
    return true;
  }

  return {
    compilePattern: compilePattern,
    compilePatterns: compilePatterns,
    matches: matches,
    skip: skip,
    filter: filter,
    _source: 'nektos/act pkg/workflowpattern @ 4f411281417e88660bea1c1a1749aa71ae0bd60f (MIT) — semantics ported, execution replaced with a Pike VM'
  };
});
