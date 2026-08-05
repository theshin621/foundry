/* lib/door.js — validate every dimension of a pasted text box AT THE DOOR,
 * counting without materialising. Contributed by ship 003 (codeowners rebuild,
 * 2026-08-05).
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THIS FILE EXISTS
 *
 * Ship 003's first attempt bounded its inputs and still froze. Six checker
 * verdicts over three fix cycles converged on ONE root cause, and it is general
 * enough that every paste-a-text-box ship will meet it:
 *
 *     AGGREGATE input was bounded. The DIMENSIONS that drive work were not.
 *
 * A 1 MiB cap says nothing about how many lines that MiB contains, how long the
 * longest one is, or how long a single whitespace-delimited FIELD inside a line
 * is. Each of those is a separate multiplier on downstream cost, and the field
 * dimension is the one that got missed: `** @` followed by 100,000 'a' is 100 KB
 * — comfortably inside every aggregate cap — and it cost 23,701 ms, because one
 * absurd owner token was re-drawn once per matching file.
 *
 * The second half of the lesson is subtler and is why this file exists at all
 * rather than five inline `if`s: the ACT OF MEASURING must not itself be the
 * cost. The obvious implementation —
 *
 *     text.split('\n').forEach(l => { if (l.length > MAX) ... })
 *
 * — allocates the entire line array before it can reject anything, so a hostile
 * paste has already won by the time the guard runs. Everything below is a single
 * forward pass over char codes with NO split, NO slice, NO regex and NO array of
 * lines, and it BAILS at the first violation. Cost is O(chars up to the first
 * violation), bounded by the aggregate cap the caller has already applied, with
 * an allocation count of zero.
 *
 * ── ORDER MATTERS ────────────────────────────────────────────────────────────
 * Call this BEFORE any split / trim / parse / compile. Zero work before
 * validation. A guard that runs after the parse is not a guard, it is a report.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.door = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var NL = 10, CR = 13, SP = 32, TAB = 9;

  function isSpace(c) { return c === SP || c === TAB || c === CR; }

  /* scan(text, limits) — one pass, no allocation, early bail.
   *
   * limits: {
   *   maxChars       total length of the box
   *   maxLines       maximum NON-BLANK lines. Blank lines are excluded on purpose:
   *                  they cost nothing downstream, and counting them made a file of
   *                  exactly maxLines rules saved the ordinary way — with a trailing
   *                  newline — fail the limit it was exactly at. (Found by the
   *                  independent checker, 2026-08-05: 20,000 rules + "\n" was
   *                  rejected as 20,001 while the identical file without the trailing
   *                  newline passed.) `lines` is still REPORTED, for messages and for
   *                  callers that need split-equivalence; only the CAP counts
   *                  non-blank lines, because only non-blank lines are work.
   *   maxLineLength  longest single line, in CHARS
   *   maxFieldLength optional — longest whitespace-delimited field within a line
   *   commentChar    optional — stop field scanning at the first occurrence of
   *                  this char on a line (fields after it are a comment)
   * }
   *
   * returns {ok:true, lines, nonBlank}
   *      or {ok:false, kind:'chars'|'lines'|'line'|'field', line, length, limit}
   *         where `line` is 1-based and `length` is the measured size that broke
   *         the limit — so the caller's refusal message can be exact rather than
   *         vague. Off-by-one exactness is a checkable property: a value equal to
   *         the limit must pass and limit+1 must fail.
   */
  function scan(text, limits) {
    var s = String(text == null ? '' : text);
    var maxChars = limits.maxChars, maxLines = limits.maxLines;
    var maxLine = limits.maxLineLength, maxField = limits.maxFieldLength;
    var commentCode = limits.commentChar ? limits.commentChar.charCodeAt(0) : -1;

    if (s.length > maxChars)
      return { ok: false, kind: 'chars', line: 0, length: s.length, limit: maxChars };

    var n = s.length;
    var line = 1, lineStart = 0, nonBlank = 0;
    var sawNonSpace = false, inComment = false;
    var fieldStart = -1;
    var i, c, term, lineEnd, lineLen, fieldLen;
    /* Which byte sequences end a line MUST match whatever the caller later splits
       on, or the door counts a different number of lines than the caller produces
       and the guard is decorative rather than binding. Measured 2026-08-05 across
       both consumers in this repo: lib/codeowners.js splits on "\n" only (a lone
       "\r" stays inside the line), while a path list split with
       /\r\n|\r|\n/ treats all three as terminators. So the caller declares it.
         'lf'  -> "\n" and "\r\n"          (lone "\r" is ordinary text)
         'any' -> "\n", "\r\n" and "\r"                                        */
    var loneCrEnds = limits.lineTerminators === 'any';

    /* One pass. Position `n` is a final virtual terminator, so the last line is
       validated on exactly the same path as every other line — the trailing-line
       special case is where off-by-one bugs live. A terminator at the very end
       DOES open a final empty line, because that is what String.prototype.split
       produces and matching it exactly is the whole point. */
    for (i = 0; i <= n; i++) {
      c = i < n ? s.charCodeAt(i) : NL;
      term = (i === n) ? 1
           : (c === NL ? 1
           : (c === CR ? (s.charCodeAt(i + 1) === NL ? 2 : (loneCrEnds ? 1 : 0)) : 0));

      if (!term) {
        if (commentCode !== -1 && c === commentCode) inComment = true;
        if (!isSpace(c)) sawNonSpace = true;

        if (maxField && !inComment) {
          if (isSpace(c)) {
            if (fieldStart !== -1) {
              fieldLen = i - fieldStart;
              if (fieldLen > maxField)
                return { ok: false, kind: 'field', line: line, length: fieldLen, limit: maxField };
              fieldStart = -1;
            }
          } else if (fieldStart === -1) {
            fieldStart = i;
          } else if (i - fieldStart >= maxField) {
            /* Bail INSIDE the field rather than waiting for its end: a single
               1 MiB field would otherwise be scanned in full before rejection.
               i - fieldStart === maxField means maxField+1 chars seen so far. */
            return { ok: false, kind: 'field', line: line, length: maxField + 1, limit: maxField };
          }
        }
        continue;
      }

      /* --- close the line at `i` (exclusive of the terminator) --- */
      lineEnd = i;
      lineLen = lineEnd - lineStart;
      if (lineLen > maxLine)
        return { ok: false, kind: 'line', line: line, length: lineLen, limit: maxLine };

      if (maxField && !inComment && fieldStart !== -1) {
        fieldLen = lineEnd - fieldStart;
        if (fieldLen > maxField)
          return { ok: false, kind: 'field', line: line, length: fieldLen, limit: maxField };
      }

      if (sawNonSpace) nonBlank++;
      if (nonBlank > maxLines)
        return { ok: false, kind: 'lines', line: line, length: nonBlank, limit: maxLines };
      if (i === n) break;

      line++;

      i += term - 1;                 /* skip the second char of a CRLF */
      lineStart = i + 1;
      sawNonSpace = false; inComment = false; fieldStart = -1;
    }

    return { ok: true, lines: line, nonBlank: nonBlank };
  }

  /* A bounded output buffer. The other half of the same lesson: bounding what is
     READ does nothing about what is WRITTEN, and a results view derived from
     input has no length cap of its own. Everything appended goes through here,
     so the emitted size is a CONSTANT regardless of input — bounded by
     construction, not by a budget that has to be consulted correctly. */
  function buffer(maxChars) {
    var parts = [], used = 0, capped = false;
    return {
      push: function () {
        var i, a;
        for (i = 0; i < arguments.length; i++) {
          a = String(arguments[i]);
          if (used + a.length > maxChars) { capped = true; return false; }
          parts.push(a); used += a.length;
        }
        return true;
      },
      capped: function () { return capped; },
      used: function () { return used; },
      toString: function () { return parts.join(''); }
    };
  }

  /* Truncate a single value for display, with a visible marker. Used for values
     that are already field-capped at the door — this is the second belt, so that
     a future caller who forgets a door limit still cannot emit an unbounded cell. */
  function clip(s, max) {
    var t = String(s == null ? '' : s);
    return t.length <= max ? t : t.slice(0, max) + '…';
  }

  return { scan: scan, buffer: buffer, clip: clip };
});
