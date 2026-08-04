/* lib/codeowners.js — CODEOWNERS parser + path matcher, LINEAR TIME.
 * Contributed by ship 003 (codeowners, 2026-08-04). Ships INLINE a copy (pages
 * stay self-contained); this file is the canonical source.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * SEMANTICS ARE BORROWED, NOT INVENTED.
 *   Source:  hmarr/codeowners — parse.go and match.go
 *   Licence: MIT (Copyright (c) 2020 Harry Marr)
 *   Pinned:  commit 11d3ff2659b769bcb43ddef81a6ab19d1205d9c2
 *   https://github.com/hmarr/codeowners
 * `parseRule`'s two-state character machine, the isPatternChar / isOwnersChar /
 * isOwnersChar sets, the three owner regexps, `newPattern`'s left-anchored-literal
 * fast path, and `buildPatternRegex`'s segment rules are a line-for-line port.
 * Ruleset.Match's "iterate from the end, first hit wins" is likewise verbatim —
 * that IS GitHub's documented precedence: "Order is important; the last matching
 * pattern takes the most precedence."
 *
 * ── THE TRAP INSIDE THE BORROW — read this before "simplifying" ──────────────
 *   hmarr/codeowners is linear-time because Go's `regexp` is RE2: no backtracking.
 *   buildPatternRegex itself emits ORDINARY regex text — `(?:.+/)?`, `[^/]+`,
 *   `(?:/.+)?`, `(?:/.*)?`. JavaScript's RegExp is a BACKTRACKING engine, so a
 *   verbatim port into `new RegExp(...)` reintroduces exactly the ReDoS that
 *   failed ship 002 twice. **This file therefore never calls RegExp on a
 *   user-supplied pattern.** It builds the same language as an NFA and runs it on
 *   the Pike VM in lib/nfa.js: O(len(path) x len(program)), no backtracking
 *   possible by construction.
 *   (The three owner regexps ARE real RegExps — they are fixed literals applied to
 *   short tokens, contain no nested quantifiers, and are not user-supplied patterns.)
 *
 * ── FIXED 2026-08-04, fix cycle 2 (second cycle authorised in session) ──────
 * The targeted re-check measured a 1,101-1,291 ms main-thread block against a page promising
 * ~750 ms, and named two unmetered stretches: runes() and lib/nfa.js's addThread(). Both are
 * metered now. The bigger finding was underneath them: literalBytes() called the UTF-8 encoder
 * ONCE PER LITERAL CHARACTER, which is 214 ms of a 526 ms parse on a 300k-character pattern.
 * That is fixed at the cost, not at the budget — an ASCII code point is its own UTF-8 byte, so
 * the encoder is not needed at all for it. The clock is also consulted 4x more often, which is
 * what bounds the overshoot past the deadline.
 *
 * ── FIXED 2026-08-04, after the first checker round ─────────────────────────
 * `?` compiled to "one BYTE that is not /" instead of "one RUNE that is not /", so a
 * pattern like `docs/report-v?.md` failed to match `docs/report-v<non-ascii>.md` that the
 * reference matches. See segOne() below. Also: parsing and compiling a pattern are now
 * CHARGED against the work budget (they were free, so a ~1 MiB pattern froze the tab for
 * seconds before any metered work began), and the budget now carries a wall-clock deadline
 * as well as a step counter.
 *
 * ── TWO DELIBERATE, DOCUMENTED DIVERGENCES FROM THE REFERENCE ────────────────
 * 1. WHOLE-FILE ERROR HANDLING. hmarr's ParseFile ABORTS the whole file on the
 *    first malformed line. GitHub does not: "If any line in your CODEOWNERS file
 *    contains invalid syntax, that line will be skipped." Since the entire point
 *    of this ship is to show a user which of their lines GitHub is silently
 *    dropping, parseFile() here SKIPS the bad line, records why, and continues.
 *    Per-line parse outcomes and all matching behaviour are unchanged, so the
 *    differential harness against the Go implementation still applies line by line.
 * 2. EMPTY PATTERN. Go's newPattern indexes patternStr[0] before checking length,
 *    which would panic on "". The caller never produces an empty pattern, so the
 *    path is unreachable there; here it returns the "empty pattern" error instead
 *    of crashing. Same outcome for every reachable input.
 *
 * ── PATH SEPARATORS ─────────────────────────────────────────────────────────
 * Go's match() calls filepath.ToSlash(), which is a NO-OP on Linux and rewrites
 * "\" to "/" on Windows. GitHub evaluates repository paths, which always use "/",
 * so this port does not rewrite anything — matching the Linux behaviour the
 * differential oracle is built on. A literal backslash in a path stays a
 * backslash.
 *
 * ── NEVER THROWS ────────────────────────────────────────────────────────────
 * Every entry point returns a value; malformed input comes back as {error}.
 * Callers MUST still escape anything they render (lib/esc.js) — ship 002's second
 * security finding was untrusted input reaching innerHTML via a thrown Error.
 * ───────────────────────────────────────────────────────────────────────────── */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(
    (typeof module === 'object' && module.exports) ? require('./nfa.js') : root.nfa);
  else root.codeowners = factory(root.nfa);
})(typeof self !== 'undefined' ? self : this, function (nfa) {
  'use strict';

  var BYTE_NL = 0x0A, BYTE_SLASH = 0x2F;

  /* ── character classes: a verbatim port of parse.go ─────────────────────── */
  function isWhitespace(ch) { return ch === ' ' || ch === '\t' || ch === '\n'; }

  /* Go's unicode.IsSpace, exactly — NOT JavaScript's \s.
     FIXED 2026-08-04 (fix cycle 3): a checker proved the two sets differ in BOTH directions.
     JS \s contains U+FEFF (a byte-order mark) and Go's does not, so a file beginning with a
     BOM parsed here and was REJECTED by the reference; Go's contains U+0085 (NEL) and JS's
     does not, so the opposite. Either one changes which rules exist — i.e. who gets requested
     for review — so this is a wrong-answer bug, not a cosmetic one. */
  var GO_SPACE_CLASS = '\\t\\n\\v\\f\\r \\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
  var GO_TRIM_RE = new RegExp('^[' + GO_SPACE_CLASS + ']+|[' + GO_SPACE_CLASS + ']+$', 'g');
  function goTrim(s) { return String(s == null ? '' : s).replace(GO_TRIM_RE, ''); }

  /* UTF-8 byte length. The reference reports error positions as BYTE offsets (Go's
     `for i, ch := range s` yields a byte index), so a rune index drifts the moment a
     multi-byte character precedes the error on the same line. */
  function byteLenOf(ch) {
    if (ch.length > 1) return 4;                 /* surrogate pair */
    var c = ch.charCodeAt(0);
    if (c < 0x80) return 1;
    if (c < 0x800) return 2;
    return 3;
  }
  function byteLenStr(s) {
    var n = 0, i, c;
    for (i = 0; i < s.length; i++) {
      c = s.charCodeAt(i);
      if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length) { n += 4; i++; }
      else if (c < 0x80) n += 1;
      else if (c < 0x800) n += 2;
      else n += 3;
    }
    return n;
  }
  function isAlphanumeric(ch) {
    return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9');
  }
  var PATTERN_CHARS = '*?./@_+-:\\()|{}[]~^';
  var OWNERS_CHARS = '.@/_%+-';
  function isPatternChar(ch) { return PATTERN_CHARS.indexOf(ch) !== -1 || isAlphanumeric(ch); }
  function isOwnersChar(ch) { return OWNERS_CHARS.indexOf(ch) !== -1 || isAlphanumeric(ch); }

  /* ── owner matchers: the three regexps from parse.go, unchanged ─────────── */
  var EMAIL_RE = /^[A-Z0-9a-z._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,6}$/;
  var TEAM_RE = /^@([a-zA-Z0-9\-]+\/[a-zA-Z0-9_\-]+)$/;
  var USER_RE = /^@([a-zA-Z0-9\-_]+)$/;

  function newOwner(s) {
    var m = EMAIL_RE.exec(s);
    if (m) return { value: m[0], type: 'email', text: m[0] };
    m = TEAM_RE.exec(s);
    if (m) return { value: m[1], type: 'team', text: '@' + m[1] };
    m = USER_RE.exec(s);
    if (m) return { value: m[1], type: 'username', text: '@' + m[1] };
    return { error: "invalid owner format '" + s + "'" };
  }

  /* ── pattern → NFA. A port of match.go's buildPatternRegex. ─────────────── */
  /* Byte-level constructs equivalent to Go's rune-level ones — see lib/nfa.js on
     why "any byte except X" equals "any rune except X" for ASCII X in UTF-8. */
  function anyPlus() { return nfa.plus(nfa.chNot(BYTE_NL)); }        /* .+       */
  function anyStar() { return nfa.star(nfa.chNot(BYTE_NL)); }        /* .*       */
  function segPlus() { return nfa.plus(nfa.chNot(BYTE_SLASH)); }     /* [^/]+    */
  function segStar() { return nfa.star(nfa.chNot(BYTE_SLASH)); }     /* [^/]*    */
  /* [^/] — EXACTLY ONE RUNE that is not "/".
     FIXED after ship 003's first checker round. This was previously chNot(BYTE_SLASH),
     i.e. exactly one BYTE, and that is a real divergence: lib/nfa.js's byte/rune
     equivalence argument holds for REPEATED constructs (.+ , [^/]+ , [^/]* accept the
     same strings byte-wise as rune-wise) but NOT for a single non-repeated occurrence.
     Go's `[^/]` consumes one whole rune, so `docs/report-v?.md` matched
     `docs/report-va.md` here but NOT `docs/report-v<alpha>.md`, which the reference
     matches. `?` is the only single-occurrence wildcard in this grammar; literals emit
     their exact bytes and "/" is ASCII, so nothing else was affected.
     Well-formed UTF-8 only: a lone continuation byte is not accepted. Input reaching
     this always came through TextEncoder, which never emits ill-formed sequences. */
  var M_ASCII = nfa.byteSet([[0x00, 0x7F]], BYTE_SLASH);
  var M_CONT = nfa.byteSet([[0x80, 0xBF]]);
  var M_LEAD2 = nfa.byteSet([[0xC2, 0xDF]]);
  var M_LEAD3 = nfa.byteSet([[0xE0, 0xEF]]);
  var M_LEAD4 = nfa.byteSet([[0xF0, 0xF4]]);
  function segOne() {
    return nfa.alt([
      nfa.chSet(M_ASCII),
      nfa.cat([nfa.chSet(M_LEAD2), nfa.chSet(M_CONT)]),
      nfa.cat([nfa.chSet(M_LEAD3), nfa.chSet(M_CONT), nfa.chSet(M_CONT)]),
      nfa.cat([nfa.chSet(M_LEAD4), nfa.chSet(M_CONT), nfa.chSet(M_CONT), nfa.chSet(M_CONT)])
    ]);
  }
  function slash() { return nfa.chLit(BYTE_SLASH); }

  /* ASCII fast path. This is called once per literal character of a pattern, and routing every
     one of them through the UTF-8 encoder cost 214 ms on a 300,000-character pattern (measured,
     ship 003 fix cycle 2). A code point below 0x80 IS its own UTF-8 byte, so no encoder is
     needed; only the rare non-ASCII literal pays for one. */
  function literalBytes(str, out) {
    if (str.length === 1) {
      var c = str.charCodeAt(0);
      if (c < 0x80) { out.push(nfa.chLit(c)); return; }
    }
    var b = nfa.utf8(str), i;
    for (i = 0; i < b.length; i++) out.push(nfa.chLit(b[i]));
  }

  /* Iterate code points, mirroring Go's `for _, ch := range seg` over runes. */
  /* runes(s, budget) — mirrors Go's `for _, ch := range s` over runes. METERED: it allocates one
     array element per code point, and ship 003's targeted re-check named it (with addThread) as
     one of the two remaining unmetered stretches behind a 1.1-1.3 s block. Returns null when the
     budget runs out; every caller must treat null as "cannot evaluate", never as an empty string. */
  function runes(s, budget) {
    var out = [], i, c, c2;
    if (budget) {
      budget.left -= (s.length >> 2);        /* the allocation itself, charged up front */
      if (budget.left <= 0) { budget.exceeded = true; return null; }
    }
    for (i = 0; i < s.length; i++) {
      if (budget && (i & 255) === 0 && nfa.tick(budget)) return null;
      c = s.charCodeAt(i);
      if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length) {
        c2 = s.charCodeAt(i + 1);
        if (c2 >= 0xDC00 && c2 <= 0xDFFF) { out.push(s.substr(i, 2)); i++; continue; }
      }
      out.push(s.charAt(i));
    }
    return out;
  }

  function buildPatternAst(pattern, budget) {
    /* Edge cases first — same order as the reference. */
    if (pattern.indexOf('***') !== -1) return { error: 'pattern cannot contain three consecutive asterisks' };
    if (pattern === '') return { error: 'empty pattern' };
    if (pattern === '/') return { ast: nfa.empty() };   /* `\A\z` — matches only "" */

    if (budget) {
      budget.left -= (pattern.length >> 2);   /* split() allocates a segment array */
      if (budget.left <= 0) { budget.exceeded = true; return { budgetExceeded: true }; }
      if (nfa.tick(budget)) return { budgetExceeded: true };
    }
    var segs = pattern.split('/');

    if (segs[0] === '') {
      segs = segs.slice(1);                              /* leading slash: anchored at root */
    } else if (segs.length === 1 || (segs.length === 2 && segs[1] === '')) {
      /* single-segment pattern matches at any depth (an implicit leading double-star + slash) */
      if (segs[0] !== '**') segs = ['**'].concat(segs);
    }
    if (segs.length > 1 && segs[segs.length - 1] === '') segs[segs.length - 1] = '**';

    var last = segs.length - 1;
    var needSlash = false;
    var parts = [];
    var i, j, rs, ch, escape;

    for (i = 0; i < segs.length; i++) {
      if (budget) {
        budget.left -= 4;
        if (budget.left <= 0) { budget.exceeded = true; return { budgetExceeded: true }; }
        if (nfa.tick(budget)) return { budgetExceeded: true };
      }
      var seg = segs[i];
      if (seg === '**') {
        if (i === 0 && i === last) parts.push(anyPlus());                                  /* .+        */
        else if (i === 0) { parts.push(nfa.opt(nfa.cat([anyPlus(), slash()]))); needSlash = false; }
        else if (i === last) parts.push(nfa.cat([slash(), anyStar()]));                    /* /.*       */
        else { parts.push(nfa.opt(nfa.cat([slash(), anyPlus()]))); needSlash = true; }     /* (?:/.+)?  */
      } else if (seg === '*') {
        if (needSlash) parts.push(slash());
        parts.push(segPlus());
        needSlash = true;
      } else {
        if (needSlash) parts.push(slash());
        rs = runes(seg, budget);
        if (rs === null) return { budgetExceeded: true };
        escape = false;
        for (j = 0; j < rs.length; j++) {
          if (budget) {
            budget.left -= 2;                 /* building the AST is real, chargeable work */
            if (budget.left <= 0) { budget.exceeded = true; return { budgetExceeded: true }; }
            if (nfa.tick(budget)) return { budgetExceeded: true };
          }
          ch = rs[j];
          if (escape) { escape = false; literalBytes(ch, parts); continue; }
          if (ch === '\\') { escape = true; continue; }
          else if (ch === '*') parts.push(segStar());
          else if (ch === '?') parts.push(segOne());
          else literalBytes(ch, parts);   /* includes [ and ] — CODEOWNERS has no ranges */
        }
        /* No trailing slash (that would have hit the "**" case), so match descendants. */
        if (i === last) parts.push(nfa.opt(nfa.cat([slash(), anyStar()])));
        needSlash = true;
      }
    }
    return { ast: nfa.cat(parts) };
  }

  /* newPattern: the left-anchored-literal fast path, then the NFA. */
  function newPattern(patternStr, budget) {
    var p = { pattern: patternStr };
    if (patternStr === '') return { pattern: patternStr, error: 'empty pattern' };
    if (budget) {
      budget.left -= patternStr.length;
      if (budget.left <= 0) { budget.exceeded = true; return { pattern: patternStr, budgetExceeded: true }; }
      if (nfa.tick(budget)) return { pattern: patternStr, budgetExceeded: true };
    }

    if (patternStr.indexOf('*') === -1 && patternStr.indexOf('?') === -1 &&
        patternStr.indexOf('\\') === -1 && patternStr.charAt(0) === '/') {
      p.leftAnchoredLiteral = true;
      /* Go does these comparisons on BYTES; do the same so a non-ASCII pattern
         cannot drift on UTF-16 code-unit indices. */
      var prefix = patternStr.slice(1);                 /* strip the anchoring slash */
      p.prefixBytes = nfa.utf8(prefix);
      p.prefixIsDir = prefix.length > 0 && prefix.charAt(prefix.length - 1) === '/';
      return p;
    }
    var built = buildPatternAst(patternStr, budget);
    if (built.budgetExceeded) return { pattern: patternStr, budgetExceeded: true };
    if (built.error) return { pattern: patternStr, error: built.error };
    p.compiled = nfa.compile(built.ast, budget);
    if (p.compiled.budgetExceeded) return { pattern: patternStr, budgetExceeded: true };
    return p;
  }

  function bytesEqualAt(hay, needle, from) {
    for (var i = 0; i < needle.length; i++) if (hay[from + i] !== needle[i]) return false;
    return true;
  }

  /* patternMatch: a port of match.go's (p pattern) match(testPath). */
  function patternMatch(p, pathBytes, budget) {
    if (!p || p.error) return false;
    if (p.leftAnchoredLiteral) {
      var pre = p.prefixBytes, n = pre.length, m = pathBytes.length;
      if (budget) {                                    /* charge for the byte compare */
        budget.left -= n + 1;
        if (budget.left <= 0) { budget.exceeded = true; return false; }
      }
      if (n === 0) return false;                       /* pattern "/" never reaches here */
      if (p.prefixIsDir) return m >= n && bytesEqualAt(pathBytes, pre, 0);
      if (m === n) return bytesEqualAt(pathBytes, pre, 0);
      if (m > n && pathBytes[n] === BYTE_SLASH) return bytesEqualAt(pathBytes, pre, 0);
      return false;
    }
    return nfa.matches(p.compiled, pathBytes, budget);
  }

  /* ── parseRule: a port of parse.go's two-state machine ──────────────────── */
  var STATE_PATTERN = 1, STATE_OWNERS = 2;

  /* maxPattern: a single path pattern longer than this is not evaluated. This is a DOMAIN
     bound, not a budget dodge — a CODEOWNERS pattern is a path pattern, and the pathological
     inputs that survived the budget (a 300,000-character literal, a 150,000-segment ** chain,
     a 262,000-`?` run) are not patterns anyone writes; they are allocation bombs. Metering them
     bounds the CPU but not the garbage collector, which is the last thing between a 750 ms
     promise and a 954 ms measurement. Refusing them at the door removes the class instead.
     Aggregate load (many rules x many paths) is still the budget's job, and it handles it. */
  function parseRule(ruleStr, budget, maxPattern) {
    var line = goTrim(ruleStr);
    var r = { owners: [], comment: '', ownerErrors: [] };
    var state = STATE_PATTERN;
    var escaped = false;
    var buf = '';
    var rs = runes(line, budget);
    if (rs === null) return { budgetExceeded: true };
    var i, ch, pat, own;
    var bpos = 0;                                  /* BYTE offset, mirroring Go's range index */

    for (i = 0; i < rs.length; i++) {
      ch = rs[i];
      if (budget) {
        budget.left -= 2;      /* an owner list has no length cap — charge for reading it */
        if (budget.left <= 0) { budget.exceeded = true; return { budgetExceeded: true }; }
        if ((i & 255) === 0 && nfa.tick(budget)) return { budgetExceeded: true };
      }
      if (ch === '#') {                       /* comments consume the rest of the line */
        r.comment = goTrim(rs.slice(i + 1).join(''));
        break;
      }
      if (state === STATE_PATTERN) {
        if (ch === '\\') { escaped = true; buf += ch; bpos += byteLenOf(ch); continue; }
        else if (isWhitespace(ch) && !escaped) {
          if (maxPattern && buf.length > maxPattern) return { patternTooLong: buf.length };
          pat = newPattern(buf, budget);
          if (pat.budgetExceeded) return { budgetExceeded: true };
          if (pat.error) return { error: pat.error, rawPattern: buf };
          r.pattern = pat; r.rawPattern = buf;
          buf = '';
          state = STATE_OWNERS;
        } else if (isPatternChar(ch) || escaped) {
          buf += ch;
        } else {
          return { error: "unexpected character '" + ch + "' at position " + (bpos + 1), rawPattern: buf };
        }
        escaped = false;
      } else {
        if (isWhitespace(ch)) {
          if (buf.length > 0) {
            own = newOwner(buf);
            if (own.error) return { error: own.error + ' at position ' + (bpos + 1 - byteLenStr(buf)), rawPattern: r.rawPattern };
            r.owners.push(own);
            buf = '';
          }
        } else if (isOwnersChar(ch)) {
          buf += ch;
        } else {
          return { error: "unexpected character '" + ch + "' at position " + (bpos + 1), rawPattern: r.rawPattern };
        }
      }
      bpos += byteLenOf(ch);
    }

    if (state === STATE_PATTERN) {
      if (buf.length === 0) return { error: 'unexpected end of rule', rawPattern: '' };
      if (maxPattern && buf.length > maxPattern) return { patternTooLong: buf.length };
      pat = newPattern(buf, budget);
      if (pat.budgetExceeded) return { budgetExceeded: true };
      if (pat.error) return { error: pat.error, rawPattern: buf };
      r.pattern = pat; r.rawPattern = buf;
    } else if (buf.length > 0) {
      own = newOwner(buf);
      if (own.error) return { error: own.error + ' at position ' + (byteLenStr(line) + 1 - byteLenStr(buf)), rawPattern: r.rawPattern };
      r.owners.push(own);
    }
    return r;
  }

  /* ── parseFile: GitHub's skip-the-bad-line behaviour (divergence 1 above) ── */
  function parseFile(text, budget, maxPattern) {
    var src = String(text == null ? '' : text);
    /* Go's bufio.Scanner splits on "\n" ONLY and drops one trailing "\r" from each token.
       FIXED 2026-08-04 (fix cycle 3): this used to split on a bare "\r" as well, so a
       classic-Mac file parsed into several valid rules here while the reference saw a single
       malformed line — a WRONG-OWNER divergence, not cosmetic. A bare "\r" mid-line now stays
       in the line and is rejected as an unexpected character, exactly as the reference does. */
    var lines = src.split('\n');
    var rules = [], skipped = [], i, raw, trimmed, rule;
    for (i = 0; i < lines.length; i++) {
      if (budget) {
        budget.left -= 8;
        if (budget.left <= 0) budget.exceeded = true;
        if (budget.exceeded || nfa.tick(budget))
          return { rules: rules, skipped: skipped, lineCount: lines.length, budgetExceeded: true };
      }
      raw = lines[i];
      if (raw.charAt(raw.length - 1) === '\r') raw = raw.slice(0, -1);
      if (budget) {
        budget.left -= (raw.length >> 3);     /* the trim scans the line */
        if (budget.left <= 0) { budget.exceeded = true; }
        if (budget.exceeded)
          return { rules: rules, skipped: skipped, lineCount: lines.length, budgetExceeded: true };
      }
      trimmed = goTrim(raw);
      if (trimmed.length === 0 || trimmed.charAt(0) === '#') continue;   /* blank + comment */
      rule = parseRule(trimmed, budget, maxPattern);
      if (rule.budgetExceeded)
        return { rules: rules, skipped: skipped, lineCount: lines.length, budgetExceeded: true };
      if (rule.patternTooLong)
        return { rules: rules, skipped: skipped, lineCount: lines.length,
                 patternTooLong: { line: i + 1, length: rule.patternTooLong } };
      if (rule.error) { skipped.push({ line: i + 1, text: raw, error: rule.error }); continue; }
      rule.line = i + 1;
      rule.text = raw;
      rules.push(rule);
    }
    return { rules: rules, skipped: skipped, lineCount: lines.length, budgetExceeded: false };
  }

  /* ── resolve: last matching rule wins (Ruleset.Match, verbatim) ─────────── */
  /* Returns { winner, alsoMatched, budgetExceeded } per path. `alsoMatched` is
     everything the reference implementation never has to compute — it is what
     makes this a debugger rather than a lookup. */
  function resolve(parsed, path, budget) {
    var bytes = nfa.encode(path, budget);
    if (budget && budget.exceeded) return { budgetExceeded: true, winner: null, alsoMatched: [] };
    var rules = parsed.rules, i, hits = [];
    if (budget && nfa.tick(budget)) return { budgetExceeded: true, winner: null, alsoMatched: [] };
    for (i = rules.length - 1; i >= 0; i--) {
      if (budget && (budget.exceeded || nfa.tick(budget))) return { budgetExceeded: true, winner: null, alsoMatched: [] };
      if (patternMatch(rules[i].pattern, bytes, budget)) hits.push(rules[i]);
    }
    if (budget && budget.exceeded) return { budgetExceeded: true, winner: null, alsoMatched: [] };
    return { winner: hits.length ? hits[0] : null, alsoMatched: hits.slice(1), budgetExceeded: false };
  }

  return {
    parseFile: parseFile,
    parseRule: parseRule,
    newPattern: newPattern,
    patternMatch: patternMatch,
    resolve: resolve,
    newOwner: newOwner,
    _source: 'hmarr/codeowners @ 11d3ff2659b769bcb43ddef81a6ab19d1205d9c2 (MIT) — semantics ported, execution replaced with the lib/nfa.js Pike VM'
  };
});
