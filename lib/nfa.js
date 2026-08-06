/* lib/nfa.js — the shared linear-time matcher core. Thompson NFA + Pike-VM
 * state-set simulation over BYTES, with a work budget measured in states visited.
 * Contributed by ship 003 (codeowners, 2026-08-04).
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THIS FILE EXISTS
 *
 * Ship 002 (gha-trigger) learned the expensive lesson twice: a glob/path pattern
 * compiled to a JavaScript `RegExp` is a BACKTRACKING match, and ordinary pasted
 * text can drive it into catastrophic backtracking that freezes the tab. The fix
 * was not a cleverer regex or a static complexity budget (the checker proved a
 * static budget cannot bound an exponential cost function — a pattern sitting
 * exactly at the cap still hung >10 s). The fix was to stop backtracking existing:
 * compile to an NFA and simulate the whole state SET at once, which is
 * O(len(value) x len(program)) BY CONSTRUCTION, not by budget.
 *
 * That engine lived inside lib/gha-glob.js, welded to GitHub Actions filter
 * syntax. Ship 003 needs the same engine for a DIFFERENT pattern language
 * (CODEOWNERS / gitignore-style), so the engine is extracted here as a primitive
 * any future ship can build a pattern language on top of: hand it an AST of
 * byte-matchers and it gives back a program that cannot blow up.
 *
 * lib/gha-glob.js is deliberately NOT rewritten to use this file. It is live in
 * production (ship 002) and carries three independent checker verdicts against
 * its exact bytes; re-pointing it at a new dependency would invalidate that
 * evidence for no user-visible gain. A future run may migrate it — with its own
 * checker round. Until then the duplication is the cheap side of the trade.
 *
 * ── WHY BYTES AND NOT CHARACTERS ─────────────────────────────────────────────
 * Reference implementations of these pattern languages are written in Go, where
 * `.` means "any rune except \n" and `[^/]` means "any rune except /". This VM
 * steps one BYTE at a time. That is equivalent, not an approximation: in UTF-8 no
 * byte of a multi-byte sequence is ever < 0x80, so neither 0x0A ("\n") nor 0x2F
 * ("/") can appear inside one. A byte-wise "any byte except \n" therefore accepts
 * exactly the same strings as a rune-wise ".". Any NEW exclusion byte a caller
 * adds must satisfy the same property (i.e. be ASCII) or the equivalence breaks.
 *
 * ── THE BUDGET IS A MEASUREMENT, NOT A PREDICTION ────────────────────────────
 * Linear time is not bounded time: both len(program) and len(value) are
 * attacker-controlled, so a large enough paste still blocks the main thread for
 * seconds. Every entry point takes a budget whose `left` counter is decremented
 * by states ACTUALLY VISITED and checked inside the loop. It can therefore never
 * be "satisfied and exceeded at once" the way ship 002's failed static budget
 * could. When it runs out the caller gets `budget.exceeded === true` and MUST
 * report "cannot evaluate" — never a verdict. Refusing to answer is honest; a
 * wrong answer or a frozen tab is not.
 *
 * ── NEVER THROWS ─────────────────────────────────────────────────────────────
 * Ship 002's second security finding was untrusted input reaching innerHTML
 * through a THROWN Error message. Nothing here throws; malformed input comes
 * back as a value. Callers still escape anything they render (lib/esc.js).
 * ───────────────────────────────────────────────────────────────────────────── */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.nfa = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ── opcodes ───────────────────────────────────────────────────────────── */
  var CHAR = 0, SPLIT = 1, JMP = 2, MATCH = 3;
  /* CHAR kinds */
  var LIT = 0, NOT = 1, SET = 2;

  var _enc = (typeof TextEncoder !== 'undefined') ? new TextEncoder() : null;
  function utf8(s) {
    /* ONE encoder, not one per call. Ship 003's second fix cycle measured `new TextEncoder()`
       per call costing 214 ms on a 300k-character pattern, because the CODEOWNERS port called
       utf8() once per literal character. Callers with an ASCII fast path should skip this
       entirely (see lib/codeowners.js literalBytes). */
    if (_enc) return _enc.encode(s);
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
  function chLit(b) { return { t: 'ch', k: LIT, b: b }; }        /* this exact byte      */
  function chNot(b) { return { t: 'ch', k: NOT, b: b }; }        /* any byte but this    */
  function chSet(set) { return { t: 'ch', k: SET, s: set }; }    /* Uint8Array(256) mask */
  function cat(list) { return { t: 'cat', a: list }; }
  function star(a) { return { t: 'star', a: a }; }
  function plus(a) { return { t: 'plus', a: a }; }
  function opt(a) { return { t: 'opt', a: a }; }
  function alt(list) { return { t: 'alt', a: list }; }
  function empty() { return { t: 'cat', a: [] }; }

  /* Build a 256-entry byte mask for chSet from inclusive ranges. */
  function byteSet(ranges, except) {
    var m = new Uint8Array(256), i, r;
    for (r = 0; r < ranges.length; r++) for (i = ranges[r][0]; i <= ranges[r][1]; i++) m[i] = 1;
    if (except != null) m[except] = 0;
    return m;
  }

  /* ── emit AST → program ────────────────────────────────────────────────── */
  /* METERED. Emission is where a big pattern actually costs time — ship 003's fix cycle
     measured a 262k-`?` pattern spending 1.7 s here while the AST walk above it looked
     cheap, because one `?` expands to a 13-instruction alternation. Charging only after
     emit() returns is charging after the bill is paid. Returns false when out of budget;
     every recursive call site checks and unwinds. */
  function emit(node, prog, budget) {
    var sp, l1, i;
    if (budget) {
      if (budget.exceeded) return false;
      budget.left -= 2;
      if (budget.left <= 0) { budget.exceeded = true; return false; }
      if (tick(budget)) return false;
    }
    switch (node.t) {
      case 'ch':
        prog.push({ op: CHAR, k: node.k, b: node.b, s: node.s });
        break;
      case 'cat':
        for (i = 0; i < node.a.length; i++) if (!emit(node.a[i], prog, budget)) return false;
        break;
      case 'star':
        l1 = prog.length;
        sp = { op: SPLIT, x: 0, y: 0 };
        prog.push(sp);
        sp.x = prog.length;
        if (!emit(node.a, prog, budget)) return false;
        prog.push({ op: JMP, x: l1 });
        sp.y = prog.length;
        break;
      case 'plus':
        l1 = prog.length;
        if (!emit(node.a, prog, budget)) return false;
        sp = { op: SPLIT, x: l1, y: 0 };
        prog.push(sp);
        sp.y = prog.length;
        break;
      case 'opt':
        sp = { op: SPLIT, x: 0, y: 0 };
        prog.push(sp);
        sp.x = prog.length;
        if (!emit(node.a, prog, budget)) return false;
        sp.y = prog.length;
        break;
      case 'alt': {
        var n = node.a.length;
        if (n === 0) break;
        if (n === 1) { if (!emit(node.a[0], prog, budget)) return false; break; }
        var jmps = [], q, j, end;
        for (q = 0; q < n - 1; q++) {
          sp = { op: SPLIT, x: 0, y: 0 };
          prog.push(sp);
          sp.x = prog.length;
          if (!emit(node.a[q], prog, budget)) return false;
          j = { op: JMP, x: 0 };
          prog.push(j); jmps.push(j);
          sp.y = prog.length;
        }
        if (!emit(node.a[n - 1], prog, budget)) return false;
        end = prog.length;
        for (q = 0; q < jmps.length; q++) jmps[q].x = end;
        break;
      }
    }
    return true;
  }

  /* compile(ast, budget) -> { prog: [...] } or { budgetExceeded: true }. The returned
     object also carries the VM's cached scratch state, so keep it and reuse it across
     values. Compilation is CHARGED: emitting a program is real work proportional to the
     pattern, and ship 003's first checker round proved that leaving it unmetered lets a
     single ~1 MiB pattern block the main thread for ~3.9 s while every match afterwards
     stays comfortably inside its budget. Anything that costs time is metered now. */
  function compile(ast, budget) {
    var prog = [];
    if (!emit(ast, prog, budget)) return { budgetExceeded: true, prog: null };
    prog.push({ op: MATCH });
    if (budget) {
      budget.left -= prog.length;
      if (budget.left <= 0) { budget.exceeded = true; return { budgetExceeded: true, prog: null }; }
      if (tick(budget)) return { budgetExceeded: true, prog: null };
    }
    return { prog: prog };
  }

  /* ── work budget ───────────────────────────────────────────────────────── */
  /* One "step" = one NFA state visited. Measured at roughly 40M steps/second in
     Chromium (ship 002, 2026-08-03), so the default ceiling is about 200 ms of
     worst-case compute for an ENTIRE evaluation — all patterns against all
     values. Callers share ONE budget across the whole evaluation. */
  var DEFAULT_STEP_BUDGET = 20000000;
  var DEFAULT_DEADLINE_MS = 750;

  /* makeBudget(steps, ms) — TWO ceilings, and the second one is the load-bearing one.
     The step counter meters NFA states visited. Measured throughput is SHAPE-DEPENDENT and
     that is exactly the problem: ~32M steps/s on V8 for one long path against one big program,
     ~20M steps/s for the realistic shape (hundreds of rules x hundreds of paths, where per-call
     overhead dominates) and only ~4-5M steps/s in Chromium for the pathological shape (20,000
     patterns x 5,000 paths, where almost no states are visited per call). Ship 003's first
     checker round measured a 2.1 s tab freeze in which the step counter barely moved. So a step
     counter alone is NOT a time bound. A wall-clock deadline is checked as well, and it is
     deliberately the BINDING ceiling (20M steps is ~1 s at the realistic rate; the 750 ms clock
     fires first) — the clock is the only bound that holds regardless of shape, and therefore
     the only one a UI may honestly quote to a user.
     750 ms comes from measurement, not taste: in-browser, 1,000 changed files against 200 rules
     costs ~160-198 ms (measured by an independent checker over 6 Chromium trials) and 500 x 500
     costs ~309 ms in node, so real pull requests finish comfortably inside the ceiling while the
     worst case a checker could construct is bounded.
     (An earlier revision of this comment quoted ~252 ms here, a node-side number, and disagreed
     with the page's "about a quarter of 750 ms". The page was right; the comment was the stale
     one. Corrected 2026-08-04.) */
  function makeBudget(steps, ms) {
    var t = (typeof ms === 'number' && ms > 0) ? ms : DEFAULT_DEADLINE_MS;
    return {
      left: (typeof steps === 'number' && steps > 0) ? steps : DEFAULT_STEP_BUDGET,
      exceeded: false,
      deadline: (typeof Date !== 'undefined' ? Date.now() : 0) + t,
      ms: t,
      _n: 0
    };
  }

  /* tick(budget) -> true when out of budget. Consults the clock every 256th call: often enough
     that the OVERSHOOT past the deadline is bounded by the work between two checks (the thing
     ship 003's re-checker measured at 1.1-1.3 s against a 750 ms promise), cheap enough that the
     check is not itself the cost (~78k Date.now() calls across a full 20M-step budget, ~1.5 ms).
     Call it anywhere work happens in a loop. */
  function tick(budget) {
    if (!budget) return false;
    if (budget.exceeded) return true;
    if ((++budget._n & 255) !== 0) return false;
    if (budget.deadline && Date.now() > budget.deadline) { budget.exceeded = true; return true; }
    return false;
  }

  /* Encode a value ONCE and reuse the bytes across every pattern. Re-encoding per
     pattern does no NFA steps but dominated the wall clock at ship 002 scale. */
  function encode(value, budget) {
    var str = String(value == null ? '' : value);
    if (budget) {
      budget.left -= (str.length >> 3);            /* charge for the encode itself */
      if (budget.left <= 0) { budget.exceeded = true; return new Uint8Array(0); }
    }
    return utf8(str);
  }

  /* ── run ───────────────────────────────────────────────────────────────── */
  function testByte(ins, b) {
    if (ins.k === LIT) return b === ins.b;
    if (ins.k === NOT) return b !== ins.b;
    return ins.s[b] === 1;
  }

  function addThread(prog, list, pc, gen, g, stack, budget) {
    stack.length = 0;
    stack.push(pc);
    while (stack.length) {
      var q = stack.pop();
      if (gen[q] === g) continue;
      gen[q] = g;
      if (budget) {
        budget.left--;
        /* This loop walks the whole epsilon-closure and can visit a large program in one go, so
           it needs its own clock check — without it a single addThread() call was an unmetered
           stretch (found by ship 003's targeted re-check). Bailing here leaves an INCOMPLETE
           state set, which is why every caller must treat budget.exceeded as "cannot evaluate"
           and never as a result. matches() and resolve() both do. */
        if (budget.left <= 0) { budget.exceeded = true; return; }
        if (tick(budget)) return;
      }
      var ins = prog[q];
      if (ins.op === SPLIT) { stack.push(ins.y); stack.push(ins.x); }
      else if (ins.op === JMP) { stack.push(ins.x); }
      else list.push(q);
    }
  }

  /* Whole-string (anchored) match. `value` may be a string or pre-encoded bytes. */
  function matches(compiled, value, budget) {
    if (!compiled || !compiled.prog) return false;
    if (budget) {
      /* A call that fails on byte 0 still costs scratch setup and a call frame. Charging a
         fixed entry cost is what makes "millions of tiny matches" visible to the counter at
         all — without it the step budget reads near-zero while the tab is frozen. */
      budget.left -= 8;
      if (budget.left <= 0) { budget.exceeded = true; return false; }
      if (tick(budget)) return false;
    }
    var prog = compiled.prog, n = prog.length;

    var bytes;
    if (value && typeof value !== 'string' && typeof value.length === 'number' &&
        typeof value.BYTES_PER_ELEMENT === 'number') {
      bytes = value;
    } else {
      bytes = encode(value, budget);
      if (budget && budget.exceeded) return false;
    }

    /* Scratch state is cached ON the compiled object and reused. Allocating a fresh
       Int32Array(prog) plus three arrays per (pattern, value) pair dominated the wall
       clock at scale (measured, ship 002, 2026-08-03). The generation counter makes
       reuse safe without clearing. */
    if (!compiled._gen || compiled._gen.length !== n || compiled._g > 2000000000) {
      compiled._gen = new Int32Array(n);
      for (var z = 0; z < n; z++) compiled._gen[z] = -1;
      compiled._g = 0;
      compiled._c = []; compiled._n = []; compiled._s = [];
    }
    var gen = compiled._gen;
    var clist = compiled._c, nlist = compiled._n, stack = compiled._s;
    clist.length = 0; nlist.length = 0;
    var g = ++compiled._g, i, k, pc, ins;
    compiled._g += bytes.length + 1;

    addThread(prog, clist, 0, gen, g, stack, budget);
    for (i = 0; i < bytes.length; i++) {
      if (clist.length === 0) return false;
      if (budget) {
        budget.left -= clist.length;
        if (budget.left <= 0) { budget.exceeded = true; return false; }
        if (tick(budget)) return false;
      }
      g++;
      nlist.length = 0;
      var b = bytes[i];
      for (k = 0; k < clist.length; k++) {
        pc = clist[k];
        ins = prog[pc];
        if (ins.op === CHAR && testByte(ins, b)) addThread(prog, nlist, pc + 1, gen, g, stack, budget);
      }
      var t = clist; clist = nlist; nlist = t;
    }
    compiled._c = clist; compiled._n = nlist;
    /* budget.exceeded can be set by the CLOCK while budget.left is still positive, so check
       both. An aborted run's state set is incomplete and must never be read as an answer. */
    if (budget && (budget.exceeded || budget.left <= 0)) { budget.exceeded = true; return false; }
    for (k = 0; k < clist.length; k++) if (prog[clist[k]].op === MATCH) return true;
    return false;
  }

  return {
    utf8: utf8, encode: encode,
    chLit: chLit, chNot: chNot, chSet: chSet,
    cat: cat, star: star, plus: plus, opt: opt, alt: alt, empty: empty,
    byteSet: byteSet,
    compile: compile,
    makeBudget: makeBudget, tick: tick,
    DEFAULT_STEP_BUDGET: DEFAULT_STEP_BUDGET, DEFAULT_DEADLINE_MS: DEFAULT_DEADLINE_MS,
    matches: matches
  };
});
