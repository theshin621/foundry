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
  /* A bare domain with a path, or with a TLD people actually share links on. Requiring one
   * or the other is what keeps "i.e." and "chat.txt" out of it. Checker finding 5: the page
   * claims links are stripped and "site is example.com/reset?token=abc" sailed through. */
  var BARE_TLD = 'com|net|org|io|co|za|uk|us|de|fr|nl|app|dev|me|info|biz|ly|gg|tv|xyz|ai|sh|so|to|cc';
  var BARE_DOMAIN = new RegExp(
    '\\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\.)+(?:' + BARE_TLD + ')(?:\\.[a-z]{2})?' +
    '(?:\\/[^\\s<>"\']*)?(?![\\w@.-])', 'gi');
  var PHONEISH = /\+?\d[\d\s().\-]{5,}\d/g;
  var VCARD_NAME = /^(?:FN|N|NICKNAME)[;:][^\r\n]*$/gim;

  var SENTINEL = '\uE000';

  function rx(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function digits(s) { return (s.match(/\d/g) || []).length; }

  /* Latin letter -> every codepoint that folds to it. Built at load time from Unicode's
   * own decomposition rather than from a hand-typed table, because a hand-typed table is
   * the shape of thing that is 95% right forever. */
  var FOLD = (function () {
    var m = {}, cp, ch, base;
    for (cp = 0xC0; cp <= 0x24F; cp++) {
      ch = String.fromCharCode(cp);
      base = ch.normalize('NFD').replace(/\p{M}/gu, '');
      if (base.length === 1 && /[A-Za-z]/.test(base)) {
        base = base.toLowerCase();
        if (!m[base]) m[base] = [];
        if (m[base].indexOf(ch) < 0) m[base].push(ch);
      }
    }
    return m;
  })();

  function fold(s) { return s.normalize('NFD').replace(/\p{M}/gu, ''); }

  /* Word-ish boundary that respects non-ASCII names. \b is ASCII-only and would fail on
   * "Zoë" outright.
   *
   * CHECKER ROUND 1 (2026-08-11) killed the first version of this function with two
   * findings that are the same defect wearing different clothes: it matched the name as a
   * LITERAL, so "ALICE" and "alice" survived (SEVERE), and so did "Zoe" for a participant
   * spelled "Zoë" (MEDIUM). Both are the ordinary way humans type a name. The repair is not
   * two more special cases — it is to stop matching literals: the needle is folded to base
   * letters, each letter becomes a class of everything that folds to it, and the whole
   * pattern is case-insensitive. Over-matching is the correct direction of error here. */
  function boundedAll(needle) {
    var src = '', i, c, k, variants;
    var f = fold(needle);
    for (i = 0; i < f.length; i++) {
      c = f.charAt(i);
      k = c.toLowerCase();
      variants = FOLD[k];
      if (variants && /[A-Za-z]/.test(c)) {
        src += '[' + rx(c) + rx(variants.join('')) + ']';
      } else {
        src += rx(c);
      }
      /* tolerate combining marks sitting on the letter in the source text */
      src += '\\p{M}*';
    }
    return new RegExp('(?<![\\p{L}\\p{N}_])' + src + '(?![\\p{L}\\p{N}_])', 'giu');
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
  /* WhatsApp's group-management lines. These are generated by WhatsApp, not typed by a
   * human, so they are a small closed grammar rather than free text — which is why matching
   * them explicitly is safe where harvesting capitalised words from arbitrary message bodies
   * would not be. CHECKER ROUND 1 finding 1 (SEVERE): a person who is added to a group and
   * never sends a message was left in the file by name, while the page said DONE. The vCard
   * case had already taught this exact lesson ("an author-set-only redactor passes a
   * bijection test and still leaks a person") and the lesson was applied to vCards only.
   * LIMIT, stated rather than hidden: English-locale system lines. A German or isiZulu
   * export's system lines are not recognised, and the page says so. */
  var SYSTEM_LINES = [
    /^(.+?) added (.+)$/,
    /^(.+?) removed (.+)$/,
    /^(.+?) was added by (.+)$/,
    /^(.+?) was removed by (.+)$/,
    /^(.+?) left$/,
    /^(.+?) joined using this group's invite link$/,
    /^(.+?) changed the subject/,
    /^(.+?) changed this group's icon$/,
    /^(.+?) changed their phone number/,
    /^(.+?) created group/,
    /^(.+?) pinned a message$/,
    /^(.+?) turned (?:on|off) disappearing messages/,
    /^(.+?) is now an admin$/,
    /^(.+?) added you$/
  ];

  function splitNameList(s) {
    return s.split(/\s*,\s*|\s+and\s+/).map(function (x) {
      return x.replace(/^[\s"'\u2018\u2019\u201c\u201d]+|[\s"'.\u2018\u2019\u201c\u201d]+$/g, '');
    });
  }

  function collectWhatsapp(text) {
    var out = [], seen = {};
    /* `capped` is passed ONLY for strings captured out of a system line, where the pattern
     * can over-capture a subject or an invite blurb; redacting a 60-character blob would
     * mangle the file for no privacy gain. Authors and vCard names come from a parser and
     * are not capped -- an author string CAN legitimately be long, and capping it silently
     * dropped a real participant the first time this cap was written. */
    function add(v, capped) {
      v = String(v == null ? '' : v).trim();
      if (!v || !/\p{L}/u.test(v) || seen[v]) return;
      if (capped && v.length > 40) return;
      seen[v] = 1; out.push(v);
    }

    var recs = whatsappChatParser.parseString(text);
    recs.forEach(function (r) {
      if (r.author) { add(r.author); return; }
      var msg = String(r.message || '');
      for (var i = 0; i < SYSTEM_LINES.length; i++) {
        var m = msg.match(SYSTEM_LINES[i]);
        if (!m) continue;
        add(m[1], true);
        if (m[2]) splitNameList(m[2]).forEach(function (x) { add(x, true); });
        break;
      }
    });

    /* Names that are never a message author and never a system-line actor — the vCard case. */
    (text.match(VCARD_NAME) || []).forEach(function (line) {
      var v = line.slice(line.search(/[;:]/) + 1).replace(/^[^:]*:/, '').trim();
      v.split(';').forEach(add);
    });
    return out;
  }

  /* CHECKER ROUND 1 finding 2 (SEVERE): the same defect as finding 1, in the other format —
   * names inside a service message's `members` array were never collected, so neither the
   * array nor any later mention of those people was redacted.
   *
   * The repair is deliberately NOT "also read members". Walking only the shapes we happen to
   * have seen is what produced both severe findings, and BOTTLENECKS #1 is a file full of
   * fixes that grew siblings one line away. So: recurse the WHOLE document and collect by
   * KEY NAME, wherever the key appears and however deeply it is nested. A Telegram export
   * that grows a new name-carrying container is then covered by construction, as long as it
   * reuses one of these key names — which is how the format has behaved so far. */
  var TG_NAME_KEYS = { from: 1, actor: 1, members: 1, inviter: 1, saved_from: 1,
                       forwarded_from: 1, first_name: 1, last_name: 1, contact_name: 1 };
  var TG_ID_KEYS = { from_id: 1, actor_id: 1, inviter_id: 1, user_id: 1 };
  var TG_PHONE_KEYS = { phone_number: 1 };

  function collectTelegram(text) {
    var j = JSON.parse(text), out = [], seen = {};
    function add(v, owner) {
      if (v === undefined || v === null) return;
      v = String(v).trim();
      if (!v || seen[v]) return;
      seen[v] = 1;
      out.push(owner ? { value: v, owner: owner } : { value: v });
    }
    function walk(node, owner) {
      if (node === null || typeof node !== 'object') return;
      if (Array.isArray(node)) { node.forEach(function (x) { walk(x, owner); }); return; }
      var mine = (typeof node.from === 'string' && node.from) ||
                 (typeof node.actor === 'string' && node.actor) || owner;
      Object.keys(node).forEach(function (k) {
        var v = node[k];
        if (TG_NAME_KEYS[k] || TG_PHONE_KEYS[k]) {
          if (typeof v === 'string' || typeof v === 'number') add(v);
          else if (Array.isArray(v)) v.forEach(function (x) {
            if (typeof x === 'string') add(x);
          });
        }
        if (TG_ID_KEYS[k] && (typeof v === 'string' || typeof v === 'number')) add(v, mine);
      });
      Object.keys(node).forEach(function (k) { walk(node[k], mine); });
    }
    walk(j, null);
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
    /* ORDER IS LOAD-BEARING (checker finding 6). Scheme-URLs go first: a credentialed URL
     * https://user:pass@host/x contains something the email rule matches, and letting the
     * email rule bite first produced "[link removed] removed]/x" — no leak, but visibly
     * broken output on a file whose whole job is to look trustworthy. Nothing that starts
     * with http/https/www can be an email, so this ordering has no cost. */
    body = body.replace(URL, '[link removed]');
    body = body.replace(EMAIL, '[email removed]');
    body = body.replace(BARE_DOMAIN, '[link removed]');
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
