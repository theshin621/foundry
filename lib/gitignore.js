/* lib/gitignore.js — gitignore-syntax pattern sets: parse + match, with NO regex
 * and NO backtracking. Contributed by ship 006 (npm-publish-preflight, 2026-08-07).
 * Ships INLINE a copy (pages stay self-contained); this file is the canonical source.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY IT IS A DYNAMIC-PROGRAM AND NOT A REGEX, AND NOT lib/nfa.js EITHER
 *
 * Three ships in this repo have now been failed by a matcher's COST rather than
 * its correctness, so the cost model is chosen first here and the code follows it.
 *
 *   * `new RegExp(userPattern)` is out on sight. JavaScript's engine backtracks;
 *     ship 002 failed twice on exactly that (see lib/codeowners.js's header).
 *
 *   * lib/nfa.js (Thompson NFA + Pike VM) is the repo's proven linear-time answer
 *     and it is the RIGHT tool when a few patterns run against many long strings:
 *     compile once, then O(len(input) x len(program)) per test.
 *     This ship has the opposite shape. A publish-set resolution is MANY patterns
 *     (an ignore file) x MANY short paths (a file list) — order 500 x 4,000 = 2e6
 *     tests — and each individual test is tiny and nearly always dies on its first
 *     segment. Under the Pike VM every one of those 2e6 tests pays the whole
 *     program width; under the segment walk below, the overwhelming majority pay
 *     ONE segment comparison and stop. Same asymptotic safety, ~3 orders of
 *     magnitude less constant. Choosing nfa.js here would have been borrowing the
 *     familiar tool instead of the fitting one.
 *
 *   * What is emphatically NOT used is the textbook RECURSIVE glob matcher
 *     (`if (p==='*') return m(s,p+1) || m(s+1,p)`). That one is exponential on
 *     `a*a*a*a*b` and is the same defect class as a backtracking regex wearing a
 *     different hat. Both matchers below are bottom-up DP over a boolean row:
 *     bounded by construction at O(n x m), no recursion, no backtracking possible.
 *
 * ── SEMANTICS ARE BORROWED, NOT INVENTED ─────────────────────────────────────
 *   Source: the gitignore pattern format as specified in `git help gitignore`
 *   (PATTERN FORMAT). npm states its own ignore files "work just like a
 *   .gitignore" — https://docs.npmjs.com/cli/v11/configuring-npm/package-json
 *   The clauses implemented, each traceable to that spec:
 *     - blank lines match nothing; `#` starts a comment; `\#` is a literal `#`
 *     - trailing spaces are ignored unless escaped with a backslash
 *     - `!` negates (re-includes); `\!` is a literal `!`
 *     - a trailing `/` makes the pattern match directories only
 *     - a `/` at the beginning or middle anchors the pattern to the ignore file's
 *       own directory; a pattern with no such `/` matches at ANY depth
 *     - `*` and `?` never match `/`; `[...]` is a character class (with `!`/`^`
 *       negation and `a-z` ranges) and never matches `/`
 *     - a segment that is exactly `**` matches zero or more directories; a
 *       TRAILING `/**` matches everything inside and so requires at least one
 *     - last matching rule wins
 *
 *   Deliberately NOT implemented, because git's own spec calls them out and a
 *   silent partial implementation is worse than a named gap:
 *     - POSIX bracket expressions ([[:alpha:]]) — parsed as ordinary class members
 *     - the "cannot re-include a file if a parent directory is excluded" rule is
 *       NOT enforced here; it is a property of walking a tree, not of matching one
 *       path, so it belongs to the caller. The caller must test ancestors itself.
 *       (npm's own walker prunes directories, so a caller that skips this WILL
 *       disagree with npm. Ship 006 tests every ancestor and memoises.)
 *
 * ── BUDGET ───────────────────────────────────────────────────────────────────
 * Every loop is metered. `budget` = { left: <steps>, deadline: <ms epoch or 0> }.
 * On exhaustion the call returns `{ exceeded: true }` and the caller must surface
 * that as an incomplete answer — never as "not ignored". Silence on exhaustion is
 * how a matcher lies. Callers must still call lib/door.js BEFORE this file: the
 * budget bounds the work, the door bounds the input, and they are not the same job.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.gitignore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* token kinds inside one path segment */
  var T_LIT = 1, T_STAR = 2, T_ANY = 3, T_CLASS = 4;
  /* whole-segment kinds */
  var S_DSTAR = '**', S_DSTAR_PLUS = '**+';

  function tick(b, n) {
    if (!b) return false;
    b.left -= (n || 1);
    if (b.left <= 0) { b.exceeded = true; return true; }
    if (b.deadline) {
      b.since = (b.since | 0) + 1;
      if (b.since >= 2048) {
        b.since = 0;
        if (Date.now() > b.deadline) { b.exceeded = true; return true; }
      }
    }
    return false;
  }

  /* ── compile one path segment into single-character tokens ──────────────────
     Every token except T_STAR consumes exactly one character, which is what makes
     the DP below a plain O(n x m) row sweep with no special cases. */
  function compileSegment(str) {
    var toks = [], i = 0, n = str.length, c, plain = true;
    while (i < n) {
      c = str.charAt(i);
      if (c === '\\' && i + 1 < n) { toks.push({ t: T_LIT, c: str.charAt(i + 1) }); i += 2; plain = false; continue; }
      if (c === '*') {
        /* collapse runs of '*' — '**' inside a segment is just '*' per the spec */
        while (i < n && str.charAt(i) === '*') i++;
        toks.push({ t: T_STAR }); plain = false; continue;
      }
      if (c === '?') { toks.push({ t: T_ANY }); i++; plain = false; continue; }
      if (c === '[') {
        var cls = parseClass(str, i);
        if (cls) { toks.push(cls.tok); i = cls.next; plain = false; continue; }
        /* an unterminated '[' is a literal '[' — git treats it as ordinary text */
        toks.push({ t: T_LIT, c: '[' }); i++; continue;
      }
      toks.push({ t: T_LIT, c: c }); i++;
    }
    /* Three cheap NECESSARY CONDITIONS, precomputed once per pattern and checked
       before the DP on every candidate string. Each can only reject what the DP
       would also reject, so they change no verdict — the oracle is run before and
       after any change here to keep that honest.
         lit     the whole segment is metacharacter-free -> one === compare
         minLen  every token except '*' consumes exactly one char, so a string
                 shorter than the token count cannot match
         pre/suf leading and trailing LITERAL runs must appear at the same ends of
                 the string. This is the one that matters at scale: '*.log' tested
                 against 'file912.js' dies on a 4-char suffix compare instead of a
                 66-cell DP, and an ignore file is mostly extension globs. */
    var pre = '', suf = '', k, minLen = 0, hasStar = false;
    for (k = 0; k < toks.length; k++) { if (toks[k].t === T_STAR) hasStar = true; else minLen++; }
    for (k = 0; k < toks.length && toks[k].t === T_LIT; k++) pre += toks[k].c;
    for (k = toks.length - 1; k >= 0 && toks[k].t === T_LIT; k--) suf = toks[k].c + suf;
    /* a segment with no '*' at all is fully described by pre; do not double-count */
    if (pre.length === toks.length) suf = '';
    return { toks: toks, lit: plain ? str : null, pre: pre, suf: suf, minLen: minLen, hasStar: hasStar };
  }

  function parseClass(str, start) {
    var i = start + 1, n = str.length, neg = false, items = [], c;
    if (i < n && (str.charAt(i) === '!' || str.charAt(i) === '^')) { neg = true; i++; }
    /* a ']' as the FIRST member is a literal ']' */
    if (i < n && str.charAt(i) === ']') { items.push({ a: ']', b: ']' }); i++; }
    while (i < n) {
      c = str.charAt(i);
      if (c === ']') return { tok: { t: T_CLASS, neg: neg, items: items }, next: i + 1 };
      if (c === '\\' && i + 1 < n) { items.push({ a: str.charAt(i + 1), b: str.charAt(i + 1) }); i += 2; continue; }
      if (i + 2 < n && str.charAt(i + 1) === '-' && str.charAt(i + 2) !== ']') {
        items.push({ a: c, b: str.charAt(i + 2) }); i += 3; continue;
      }
      items.push({ a: c, b: c }); i++;
    }
    return null;                                   /* unterminated */
  }

  function classHas(tok, ch) {
    var i, it, hit = false;
    for (i = 0; i < tok.items.length; i++) {
      it = tok.items[i];
      if (ch >= it.a && ch <= it.b) { hit = true; break; }
    }
    return tok.neg ? !hit : hit;
  }

  function tokMatch(tok, ch) {
    if (ch === '/') return false;                  /* no wildcard ever crosses a '/' */
    if (tok.t === T_LIT) return tok.c === ch;
    if (tok.t === T_ANY) return true;
    if (tok.t === T_CLASS) return classHas(tok, ch);
    return false;
  }

  /* Scratch rows, hoisted out of the matchers. A publish-set resolution runs the
     DP on the order of a million times, and allocating two Uint8Arrays per call
     was ~30% of the measured wall time. segMatch and pathMatch get SEPARATE pools
     because pathMatch's row must survive across the segMatch calls it makes —
     sharing one pool here would be a silent correctness bug, not just a slow one.
     Safe because JS is single-threaded and neither matcher is re-entrant. */
  function pool() {
    var a = new Uint8Array(64), b = new Uint8Array(64);
    return function (need) {
      if (a.length < need) { a = new Uint8Array(need); b = new Uint8Array(need); }
      a.fill(0, 0, need); b.fill(0, 0, need);
      return [a, b];
    };
  }
  var segPool = pool(), pathPool = pool();

  /* ── segment matcher: bottom-up DP, O(len(seg) x len(toks)), no recursion ──── */
  function segMatch(seg, str, budget) {
    if (seg.lit !== null) { tick(budget); return seg.lit === str; }
    var toks = seg.toks, m = toks.length, n = str.length, i, j, t;
    tick(budget);
    /* With no '*' anywhere, every token consumes exactly one character, so the
       lengths must be EQUAL — not merely sufficient. Without this an all-class
       pattern like x[a-z][a-z]...y is the one shape that walks past minLen, pre
       and suf and still pays a full row sweep on every candidate. */
    if (seg.hasStar ? (n < seg.minLen) : (n !== seg.minLen)) return false;
    if (seg.pre) {
      if (n < seg.pre.length) return false;
      for (i = 0; i < seg.pre.length; i++) if (str.charAt(i) !== seg.pre.charAt(i)) return false;
    }
    if (seg.suf) {
      if (n < seg.suf.length) return false;
      for (i = 0; i < seg.suf.length; i++)
        if (str.charAt(n - seg.suf.length + i) !== seg.suf.charAt(i)) return false;
    }
    var buf = segPool(m + 1), dp = buf[0], nd = buf[1];
    dp[0] = 1;
    for (j = 0; j < m; j++) { if (toks[j].t === T_STAR && dp[j]) dp[j + 1] = 1; else break; }
    for (i = 1; i <= n; i++) {
      if (tick(budget, m)) return false;
      nd[0] = 0;
      for (j = 1; j <= m; j++) {
        t = toks[j - 1];
        if (t.t === T_STAR) nd[j] = (nd[j - 1] || dp[j]) ? 1 : 0;
        else nd[j] = (dp[j - 1] && tokMatch(t, str.charAt(i - 1))) ? 1 : 0;
      }
      for (j = 0; j <= m; j++) dp[j] = nd[j];
    }
    return !!dp[m];
  }

  /* ── path matcher: the same DP one level up, over segments ──────────────────
     Two O(1)-ish NECESSARY-CONDITION checks run before the DP. Both are exact —
     they can only reject inputs the DP would also have rejected — and together
     they are what makes a realistic 300-rule x 3,000-path resolution finish in a
     click rather than in a second and a half.

       (a) LAST SEGMENT. If the pattern's last segment is concrete (not `**`), a
           full match REQUIRES it to match the path's last segment. Testing that
           one segment first turns a rule ending in a `.log` glob, tested against a
           `.js` file, from a 25-cell row sweep into a single failed compare.
           Measured on the worst door-legal input ship 006 accepts: 1,658 ms down
           to double digits, with every oracle verdict unchanged.
       (b) ARITY. With no `**` anywhere the segment counts must be equal; with
           `**` present the path needs at least one segment per concrete segment
           plus one per trailing `/**`.

     Order matters: both run BEFORE pathPool(), so a rejected pattern does not
     even pay for zeroing a scratch row. */
  function pathMatch(patSegs, pathSegs, budget) {
    var m = patSegs.length, n = pathSegs.length, i, j, p;
    if (m === 0) return n === 0;

    var last = patSegs[m - 1];
    if (last !== S_DSTAR && last !== S_DSTAR_PLUS) {
      if (n === 0) return false;
      if (!segMatch(last, pathSegs[n - 1], budget)) return false;
      if (budget && budget.exceeded) return false;
    }

    var hasD = false, need = 0;
    for (i = 0; i < m; i++) {
      p = patSegs[i];
      if (p === S_DSTAR) hasD = true;
      else if (p === S_DSTAR_PLUS) { hasD = true; need++; }
      else need++;
    }
    if (!hasD) { if (m !== n) return false; }
    else if (n < need) return false;

    var buf = pathPool(m + 1), dp = buf[0], nd = buf[1];
    dp[0] = 1;
    for (j = 0; j < m; j++) { if (patSegs[j] === S_DSTAR && dp[j]) dp[j + 1] = 1; else break; }
    for (i = 1; i <= n; i++) {
      if (tick(budget)) return false;
      nd[0] = 0;
      for (j = 1; j <= m; j++) {
        p = patSegs[j - 1];
        if (p === S_DSTAR) nd[j] = (nd[j - 1] || dp[j]) ? 1 : 0;
        else if (p === S_DSTAR_PLUS) nd[j] = (dp[j - 1] || dp[j]) ? 1 : 0;
        else nd[j] = (dp[j - 1] && segMatch(p, pathSegs[i - 1], budget)) ? 1 : 0;
        if (budget && budget.exceeded) return false;
      }
      for (j = 0; j <= m; j++) dp[j] = nd[j];
    }
    return !!dp[m];
  }

  /* ── parse one line into a rule (or null) ─────────────────────────────────── */
  function parseLine(raw, lineNo) {
    var s = raw, neg = false, dirOnly = false, i;

    /* strip trailing whitespace unless the last space is backslash-escaped */
    var end = s.length;
    while (end > 0 && (s.charAt(end - 1) === ' ' || s.charAt(end - 1) === '\t')) {
      var back = 0, k = end - 2;
      while (k >= 0 && s.charAt(k) === '\\') { back++; k--; }
      if (back % 2 === 1) break;                   /* escaped — keep it */
      end--;
    }
    s = s.slice(0, end);

    if (s === '') return null;
    if (s.charAt(0) === '#') return null;
    if (s.charAt(0) === '\\' && (s.charAt(1) === '#' || s.charAt(1) === '!')) s = s.slice(1);
    else if (s.charAt(0) === '!') { neg = true; s = s.slice(1); if (s === '') return { error: 'empty pattern after "!"', line: lineNo, raw: raw }; }

    if (s.length > 1 && s.charAt(s.length - 1) === '/') { dirOnly = true; s = s.slice(0, -1); }
    if (s === '' || s === '/') return { error: 'empty pattern', line: lineNo, raw: raw };

    var anchored = s.indexOf('/') !== -1;
    if (s.charAt(0) === '/') s = s.slice(1);
    if (s === '') return { error: 'empty pattern', line: lineNo, raw: raw };

    var parts = s.split('/'), segs = [], j;
    for (j = 0; j < parts.length; j++) {
      if (parts[j] === '**') segs.push(j === parts.length - 1 ? S_DSTAR_PLUS : S_DSTAR);
      else if (parts[j] === '') continue;          /* collapse '//' */
      else segs.push(compileSegment(parts[j]));
    }
    if (!segs.length) return { error: 'empty pattern', line: lineNo, raw: raw };
    if (!anchored) segs.unshift(S_DSTAR);

    return { neg: neg, dirOnly: dirOnly, segs: segs, raw: raw, line: lineNo };
  }

  /* compile(text, opts) — opts.maxRules caps the rule count (the door should have
     bounded the text already; this is the second belt). */
  function compile(text, opts) {
    opts = opts || {};
    var lines = String(text == null ? '' : text).split(/\r\n|\r|\n/);
    var rules = [], errors = [], i, r;
    var cap = opts.maxRules || 5000;
    for (i = 0; i < lines.length; i++) {
      if (rules.length >= cap) { errors.push({ line: i + 1, error: 'rule limit ' + cap + ' reached', raw: lines[i] }); break; }
      r = parseLine(lines[i], i + 1);
      if (!r) continue;
      if (r.error) { errors.push(r); continue; }
      rules.push(r);
    }
    return { rules: rules, errors: errors, lineCount: lines.length };
  }

  /* test(compiled, path, isDir, budget) — LAST matching rule wins, so the scan
     runs backwards and stops at the first hit. Returns the deciding rule so the
     caller can show WHY, which is the entire product in ship 006. */
  function test(compiled, path, isDir, budget) {
    var segs = String(path).split('/'), i, r;
    for (i = segs.length - 1; i >= 0; i--) if (segs[i] === '') segs.splice(i, 1);
    if (!segs.length) return { ignored: false, rule: null };
    for (i = compiled.rules.length - 1; i >= 0; i--) {
      r = compiled.rules[i];
      if (budget && budget.exceeded) return { exceeded: true, ignored: false, rule: null };
      if (r.dirOnly && !isDir) continue;
      if (pathMatch(r.segs, segs, budget)) {
        if (budget && budget.exceeded) return { exceeded: true, ignored: false, rule: null };
        return { ignored: !r.neg, rule: r };
      }
    }
    if (budget && budget.exceeded) return { exceeded: true, ignored: false, rule: null };
    return { ignored: false, rule: null };
  }

  /* matchOne — a single pattern string against a single path. Convenience for the
     package.json `files[]` allowlist, which is gitignore-ish but not an ignore file. */
  function matchOne(pattern, path, isDir, budget) {
    var r = parseLine(String(pattern), 0);
    if (!r || r.error) return false;
    var segs = String(path).split('/'), i;
    for (i = segs.length - 1; i >= 0; i--) if (segs[i] === '') segs.splice(i, 1);
    if (!segs.length) return false;
    if (r.dirOnly && !isDir) return false;
    return pathMatch(r.segs, segs, budget);
  }

  return {
    compile: compile,
    test: test,
    matchOne: matchOne,
    _parseLine: parseLine,
    _segMatch: segMatch,
    _compileSegment: compileSegment
  };
});
