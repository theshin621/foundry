/* lib/chat-redact.js — ship 012's reusable core, deposited to lib/ per the builder contract.
 *
 * WHAT IT IS: a pure function that takes the raw text of a chat export and returns a
 * redacted copy of THE SAME BYTES with identities replaced, plus a bijective mapping.
 *
 * THE ONE DESIGN DECISION WORTH READING (architect, 2026-08-11). The obvious build parses
 * the chat into records and re-serialises them. That design cannot preserve timestamps
 * byte-identically, and it drags the whole locale zoo — day-first inference, AM/PM, RTL
 * marks, multi-line messages — into hand-written code. BOTTLENECKS.md #1's most recent
 * lesson is that the hand-written band around a borrowed primitive is exactly where the
 * defects now live, so the band is kept as small as the problem allows:
 *
 *     parse ONLY to learn who is in the file  ->  redact by substitution over the original
 *
 * Structure preservation is then true by construction rather than by test.
 *
 * BORROWED, NOT BUILT (Amendment 2026-08-02b.2). Author/header detection is
 * whatsapp-chat-parser v4.0.2 by Loris Bettazza (MIT), inlined verbatim by the ship page
 * and expected here as the global `whatsappChatParser`. The header regex below is copied
 * verbatim from that package (src line: the `v` pattern) so that the span this module
 * PROTECTS is exactly the span that package RECOGNISES — two different regexes for the
 * same boundary is how the two halves drift apart.
 *
 * NOT IN SCOPE, said plainly: media files, images inside a .zip export, voice notes, and
 * anything that identifies a person by writing style rather than by string. This tool
 * removes identifiers. It does not make a chat unattributable.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.ChatRedact = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* verbatim from whatsapp-chat-parser@4.0.2 (MIT) — the message-header pattern */
  var HEADER = /^(?:‎|‏)*\[?(\d{1,4}[-/.]\s?\d{1,4}[-/.]\s?\d{1,4})[,.]?\s\D*?(\d{1,2}[.:]\d{1,2}(?:[.:]\d{1,2})?)(?:\s([ap]\.?\s?m\.?))?\]?(?:\s-|:)?\s/;
  var ISO = /\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?/g;
  var EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/g;
  var URL = /\b(?:https?:\/\/|www\.)[^\s<>"']+/gi;
  var PHONEISH = /\+?\d[\d\s().\-]{5,}\d/g;
  var VCARD_NAME = /^(?:FN|N|NICKNAME)[;:][^\r\n]*$/gim;

  var SENTINEL = '\uE000';

  function rx(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function digits(s) { return (s.match(/\d/g) || []).length; }

  /* Word-ish boundary that respects non-ASCII names. \b is ASCII-only and would fail on
   * e.g. "Zoë" — a redactor that silently skips accented names is worse than no redactor. */
  function boundedAll(needle) {
    return new RegExp('(?<![\\p{L}\\p{N}_])' + rx(needle) + '(?![\\p{L}\\p{N}_])', 'gu');
  }

  function detect(text) {
    var t = text.replace(/^﻿/, '').trim();
    if (t.charAt(0) === '{' || t.charAt(0) === '[') {
      try {
        var j = JSON.parse(t);
        if (j && Array.isArray(j.messages)) return 'telegram';
      } catch (e) { /* fall through */ }
    }
    if (typeof whatsappChatParser === 'undefined') return null;
    try {
      var recs = whatsappChatParser.parseString(text);
      for (var i = 0; i < recs.length; i++) if (recs[i].author) return 'whatsapp';
    } catch (e) { /* fall through */ }
    return null;
  }

  /* --- identity collection -------------------------------------------------
   * Returns an ORDERED list of full names, first-appearance order, so pseudonyms
   * are deterministic across runs (predicate P5) and across machines. */
  function collectWhatsapp(text) {
    var out = [], seen = {};
    var recs = whatsappChatParser.parseString(text);
    recs.forEach(function (r) {
      if (r.author && !seen[r.author]) { seen[r.author] = 1; out.push(r.author); }
    });
    /* Names that are never a message author but sit in the body — the vCard case.
     * An author-set-only redactor passes a bijection test and still leaks a person. */
    (text.match(VCARD_NAME) || []).forEach(function (line) {
      var v = line.slice(line.search(/[;:]/) + 1).replace(/^[^:]*:/, '').trim();
      v.split(';').forEach(function (part) {
        part = part.trim();
        if (part && /\p{L}/u.test(part) && !seen[part]) { seen[part] = 1; out.push(part); }
      });
    });
    return out;
  }

  function collectTelegram(text) {
    var j = JSON.parse(text), out = [], seen = {};
    (j.messages || []).forEach(function (m) {
      var display = m.from || m.actor || null;
      if (display && !seen['n:' + display]) {
        seen['n:' + display] = 1;
        out.push({ value: display });
      }
      ['from_id', 'actor_id'].forEach(function (k) {
        if (m[k] === undefined || m[k] === null) return;
        var v = String(m[k]);
        if (seen['h:' + v]) return;
        seen['h:' + v] = 1;
        out.push({ value: v, owner: display });
      });
    });
    return out;
  }

  function redact(text, filename) {
    var format = detect(text);
    if (!format) {
      throw new Error('unrecognised format: this does not look like a WhatsApp .txt export ' +
        'or a Telegram result.json');
    }

    var names = format === 'telegram' ? collectTelegram(text) : collectWhatsapp(text);

    /* pseudonyms, first-appearance order.
     * Telegram exports carry BOTH a display name and a numeric handle per message. The
     * handle is pinned to its owner's number rather than given a number of its own, so the
     * sanitised file still reads as a coherent conversation instead of a lineup. */
    var map = {}, seen = {}, count = 0, i;
    for (i = 0; i < names.length; i++) {
      var nm = names[i].value !== undefined ? names[i].value : names[i];
      var owner = names[i].owner;
      if (seen[nm]) continue;
      seen[nm] = 1;
      if (owner !== undefined && map[owner]) {
        map[nm] = 'user_p' + map[owner].replace(/\D+/g, '');
      } else {
        map[nm] = 'Participant ' + (++count);
      }
    }
    var participants = Object.keys(map).filter(function (k) {
      return !/^user_p/.test(map[k]);
    });

    /* Substitution targets: full names first (longest wins), then their components, so a
     * bare first name in a message body is caught too. Components are internal only and
     * never appear in the downloadable mapping — that mapping stays injective. */
    var targets = [];
    Object.keys(map).forEach(function (nm) { targets.push([nm, map[nm]]); });
    Object.keys(map).forEach(function (nm) {
      if (/^user_p/.test(map[nm])) return;
      nm.split(/[\s,]+/).forEach(function (part) {
        part = part.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '');
        if (part.length >= 2 && /\p{L}/u.test(part)) targets.push([part, map[nm]]);
      });
    });
    targets.sort(function (a, b) { return b[0].length - a[0].length; });

    /* --- protect spans that must survive byte-identically -------------------
     * Timestamps look like phone numbers to any digit-run rule. Rather than making the
     * phone rule cleverer (and wrong in a new way), the spans are lifted out first and
     * put back last. */
    var vault = [];
    function stash(s) { vault.push(s); return SENTINEL + (vault.length - 1) + SENTINEL; }

    var lines = text.split('\n');
    var body = lines.map(function (line) {
      var m = line.match(HEADER);
      if (m && m.index === 0) return stash(m[0]) + line.slice(m[0].length);
      return line;
    }).join('\n');
    body = body.replace(ISO, function (s) { return stash(s); });

    /* --- redact ------------------------------------------------------------- */
    body = body.replace(EMAIL, '[email removed]');
    body = body.replace(URL, '[link removed]');
    body = body.replace(PHONEISH, function (s) {
      return digits(s) >= 7 ? '[number removed]' : s;
    });
    targets.forEach(function (t) {
      body = body.replace(boundedAll(t[0]), t[1]);
    });

    /* --- restore ------------------------------------------------------------ */
    var clean = body.replace(new RegExp(SENTINEL + '(\\d+)' + SENTINEL, 'g'),
      function (_, i) { return vault[+i]; });

    return {
      clean: clean,
      map: map,
      participants: participants,
      format: format === 'telegram' ? 'telegram' : 'whatsapp',
      filename: filename || 'chat.txt'
    };
  }

  return { redact: redact, _HEADER: HEADER };
});
