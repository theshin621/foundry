/* lib/sshconfig.js — OpenSSH client-config parser + first-obtained-wins resolver.
 * Contributed by ship 007 (ssh-config-resolver, 2026-08-08).
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * EVERY SEMANTIC RULE BELOW WAS MEASURED, NOT REMEMBERED.
 *
 * The rule earned on 2026-08-07 and written into lib/README.md is: *where a real
 * implementation exists, install it and diff against it — a maker's own oracle
 * proves only that the code agrees with the maker.* Ship 006 died with a 23/23
 * self-written oracle that was wrong about npm's most pervasive behaviour.
 *
 * So this file was not written from the man page. It was written against
 * `ssh -G`, OpenSSH_9.6p1 Ubuntu-3ubuntu13.18, probed in-container on
 * 2026-08-08, and every claim in the comments below is a recorded probe in
 * lib/checks/ssh-config-oracle.json. Where OpenSSH surprised the author, the
 * surprise is written down next to the rule.
 *
 * ── THE SURPRISES, NAMED ─────────────────────────────────────────────────────
 *  1. `Host` pattern matching is case-SENSITIVE; `Match host` is case-INSENSITIVE.
 *     (`Host FOO` does NOT match `foo`; `Match host ALPHA` DOES match `alpha`.)
 *     This asymmetry is the single most surprising thing in the file format and
 *     is most of the reason this ship exists.
 *  2. `Host` takes WHITESPACE-separated patterns. `Match host` takes a
 *     COMMA-separated list. `Host a.ex,b.ex` is ONE pattern containing a comma
 *     and matches neither a.ex nor b.ex.
 *  3. `Host` matches the ORIGINAL host argument. It is never re-matched against
 *     a `Hostname` that an earlier block substituted.
 *  4. `Match host` matches the CURRENT hostname — i.e. after any `Hostname` seen
 *     EARLIER in the file, and against the original host if none has been seen
 *     yet. Same for `Match user` and `User`. Position in the file changes the
 *     answer; this is not a parse, it is a sequential evaluation.
 *  5. A pattern list of negations only (`Host !foo`) matches NOTHING. A negation
 *     vetoes regardless of its position in the list.
 *  6. An unknown keyword is a FATAL error in OpenSSH, not a warning: the whole
 *     config is refused and ssh exits.
 *  7. The default `Hostname` is the LOWERCASED host argument, while the reported
 *     `host` keeps its original case.
 *  8. Six keywords ACCUMULATE instead of first-wins (measured list below).
 * ───────────────────────────────────────────────────────────────────────────── */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(
    (typeof module === 'object' && module.exports) ? require('./nfa.js') : root.nfa);
  else root.sshconfig = factory(root.nfa);
})(typeof self !== 'undefined' ? self : this, function (nfa) {
  'use strict';

  /* ── the keyword table, DERIVED BY PROBE not by memory ────────────────────
     Built 2026-08-08 by extracting every lowercase token (and every SUFFIX of
     every token — the linker tail-merges short string literals, which is why a
     naive `strings` pass silently loses `host`, `user`, `port` and `match`) from
     /usr/bin/ssh, then feeding all 3,436 candidates to the real binary one at a
     time and keeping those that did NOT produce "Bad configuration option".
     134 survived. Two of the 3,436 suffix-only candidates were real keywords the
     first pass had missed, which is the evidence that the suffix expansion was
     necessary rather than paranoid.

     HONESTY BOUND, and it is load-bearing: this list is COMPLETE FOR OpenSSH
     9.6p1 ONLY AS FAR AS THE PROBE COULD SEE. A keyword absent from it is
     reported as "not recognised by this tool", which is a weaker and different
     claim from "invalid". Never phrase it as the latter. */
  var KEYWORDS = ('addkeystoagent addressfamily afstokenpassing batchmode bindaddress bindinterface ' +
    'canonicaldomains canonicalizefallbacklocal canonicalizehostname canonicalizemaxdots ' +
    'canonicalizepermittedcnames casignaturealgorithms certificatefile ' +
    'challengeresponseauthentication channeltimeout checkhostip cipher ciphers ' +
    'clearallforwardings compression compressionlevel connectionattempts connecttimeout ' +
    'controlmaster controlpath controlpersist dsaauthentication dynamicforward ' +
    'enableescapecommandline enablesshkeysign escapechar exitonforwardfailure fallbacktorsh ' +
    'fingerprinthash forkafterauthentication forwardagent forwardx11 forwardx11timeout ' +
    'forwardx11trusted gatewayports globalknownhostsfile globalknownhostsfile2 ' +
    'gssapiauthentication gssapiclientidentity gssapidelegatecredentials gssapikexalgorithms ' +
    'gssapikeyexchange gssapirenewalforcesrekey gssapiserveridentity gssapitrustdns ' +
    'hashknownhosts host hostbasedacceptedalgorithms hostbasedauthentication hostbasedkeytypes ' +
    'hostkeyalgorithms hostkeyalias hostname identitiesonly identityagent identityfile ' +
    'identityfile2 ignoreunknown include ipqos kbdinteractiveauthentication ' +
    'kbdinteractivedevices keepalive kerberosauthentication kerberostgtpassing kexalgorithms ' +
    'knownhostscommand localcommand localforward loglevel logverbose macs match ' +
    'nohostauthenticationforlocalhost numberofpasswordprompts obscurekeystroketiming ' +
    'passwordauthentication permitlocalcommand permitremoteopen pkcs11provider port ' +
    'preferredauthentications protocol protocolkeepalives proxycommand proxyjump ' +
    'proxyusefdpass pubkeyacceptedalgorithms pubkeyacceptedkeytypes pubkeyauthentication ' +
    'rekeylimit remotecommand remoteforward requesttty requiredrsasize revokedhostkeys ' +
    'rhostsauthentication rhostsrsaauthentication rsaauthentication securitykeyprovider ' +
    'sendenv serveralivecountmax serveraliveinterval sessiontype setenv setuptimeout ' +
    'skeyauthentication smartcarddevice stdinnull streamlocalbindmask streamlocalbindunlink ' +
    'stricthostkeychecking syslogfacility tag tcpkeepalive tisauthentication tunnel ' +
    'tunneldevice updatehostkeys useblacklistedkeys useprivilegedport user userknownhostsfile ' +
    'userknownhostsfile2 useroaming usersh verifyhostkeydns visualhostkey xauthlocation'
  ).split(' ');
  var KWSET = {};
  for (var _i = 0; _i < KEYWORDS.length; _i++) KWSET[KEYWORDS[_i]] = true;

  /* MEASURED accumulating set (2026-08-08): each keyword was set twice, to two
     distinct valid values, and `ssh -G` printed BOTH. Everything else printed
     only the first. Do not add to this list from memory — re-probe.
     Note in particular that `setenv` is NOT here: it looks like a list type and
     behaves first-wins in 9.6p1. That is exactly the kind of assumption the
     probe exists to kill. */
  var ACCUMULATES = { identityfile: 1, certificatefile: 1, localforward: 1,
                      remoteforward: 1, dynamicforward: 1, sendenv: 1 };

  /* Of those six, five DE-DUPLICATE: an identical value appearing twice is kept
     once, and the de-duplication is global rather than adjacent (a repeat three
     lines later is still dropped). `sendenv` alone keeps both copies. Found by
     the differential harness on run 2 — a duplicated CertificateFile was the
     entire failure. There is no way to reach this rule from the man page. */
  var DEDUPES = { identityfile: 1, certificatefile: 1, localforward: 1,
                  remoteforward: 1, dynamicforward: 1 };

  /* MEASURED: these four take THE REST OF THE LINE, raw. A `#` in them is part
     of the command, not a comment, and quotes are not unwrapped:
        `RemoteCommand uptime   # note`  ->  value `uptime   # note`
        `HostKeyAlias  aa       # note`  ->  value `aa`
     Trailing whitespace is stripped; internal whitespace is preserved. Applying
     the normal tokeniser to these silently truncates the user's command at the
     first `#`, which is a wrong answer that looks like a right one. */
  var REST_OF_LINE = { proxycommand: 1, localcommand: 1, remotecommand: 1, knownhostscommand: 1 };

  /* Criteria this resolver evaluates. Anything else is REFUSED BY NAME rather
     than guessed at — see REFUSABLE below. */
  var MATCH_CRITERIA_WITH_ARG = { host: 1, originalhost: 1, user: 1, localuser: 1, tagged: 1 };
  var MATCH_CRITERIA_NO_ARG = { all: 1, canonical: 1, final: 1 };
  /* `exec` needs a subprocess, `canonical`/`final` need OpenSSH's second
     resolution pass, `tagged` needs -P. A page in a browser has none of them.
     Refusing loudly beats answering wrongly — ship 006's lesson. */
  var UNSUPPORTED_CRITERIA = {
    exec: 'runs a shell command — a page in your browser cannot execute it',
    canonical: 'depends on OpenSSH hostname canonicalisation (a second resolution pass)',
    final: 'depends on OpenSSH’s second resolution pass',
    tagged: 'depends on a tag supplied with ssh -P'
  };

  /* ── tokeniser ────────────────────────────────────────────────────────────
     Measured behaviour this reproduces:
       `Port 1818 # comment`      -> value "1818"      (comment stripped)
       `HostKeyAlias bo#b`        -> value "bo#b"      (# mid-token is literal)
       `HostKeyAlias "bo#b"`      -> value "bo#b"
       `HostKeyAlias "a\"b"`      -> value 'a"b'
       `User "bo b"`              -> value "bo b"
       `Host=alpha bravo`         -> keyword host, patterns [alpha, bravo]
       tabs, CRLF, trailing space -> all tolerated                            */
  function tokenize(s) {
    var toks = [], i = 0, n = s.length, cur = null, q = false;
    while (i < n) {
      var c = s.charAt(i);
      if (!q && (c === ' ' || c === '\t' || c === '\r')) { if (cur !== null) { toks.push(cur); cur = null; } i++; continue; }
      if (!q && c === '#' && cur === null) break;          /* comment: only at a token start */
      if (c === '"') { q = !q; if (cur === null) cur = ''; i++; continue; }
      if (c === '\\' && q && i + 1 < n && s.charAt(i + 1) === '"') { cur = (cur === null ? '' : cur) + '"'; i += 2; continue; }
      cur = (cur === null ? '' : cur) + c; i++;
    }
    if (cur !== null) toks.push(cur);
    return { tokens: toks, unterminatedQuote: q };
  }

  /* Split "keyword<sep>rest" where sep is whitespace and/or a single '='. */
  function splitKeyword(line) {
    var i = 0, n = line.length;
    while (i < n && (line.charAt(i) === ' ' || line.charAt(i) === '\t')) i++;
    var start = i;
    while (i < n && ' \t=\r'.indexOf(line.charAt(i)) === -1) i++;
    var kw = line.slice(start, i);
    while (i < n && (line.charAt(i) === ' ' || line.charAt(i) === '\t')) i++;
    if (i < n && line.charAt(i) === '=') { i++; while (i < n && (line.charAt(i) === ' ' || line.charAt(i) === '\t')) i++; }
    return { keyword: kw, rest: line.slice(i), col: start };
  }

  /* ── pattern matching on lib/nfa.js ──────────────────────────────────────
     `*` = any run of bytes (including empty), `?` = exactly one BYTE, everything
     else literal. Byte semantics is not an approximation: OpenSSH's match.c
     walks C `char`s, so `?` there is one byte too. Compiling to an NFA instead of
     a RegExp is inherited from ships 002/003 — a pattern from a paste must not be
     able to backtrack the tab into a freeze. */
  var ANY = null;
  function anyByte() { if (!ANY) ANY = nfa.byteSet([[0, 255]]); return ANY; }

  function compilePattern(pat, budget) {
    var parts = [], i, bytes = nfa.utf8(pat);
    for (i = 0; i < bytes.length; i++) {
      var b = bytes[i];
      if (b === 42) parts.push(nfa.star(nfa.chSet(anyByte())));          /* '*' */
      else if (b === 63) parts.push(nfa.chSet(anyByte()));               /* '?' */
      else parts.push(nfa.chLit(b));
    }
    return nfa.compile(nfa.cat(parts), budget);
  }

  var _cache = null;
  function matchOne(pat, value, budget) {
    if (!_cache) _cache = {};
    var c = _cache[pat];
    if (!c) { c = compilePattern(pat, budget); if (c.budgetExceeded) return null; _cache[pat] = c; }
    if (budget && budget.exceeded) return null;
    var r = nfa.matches(c, value, budget);
    if (budget && budget.exceeded) return null;
    return r;
  }
  function resetCache() { _cache = null; }

  /* matchList(patterns, value, foldCase, budget)
     -> {matched:bool, by:pattern|null, vetoedBy:pattern|null} or null on budget.
     MEASURED: a negated pattern vetoes wherever it appears in the list, and a
     list with no positive pattern matches nothing. */
  function matchList(pats, value, foldCase, budget) {
    var v = foldCase ? String(value).toLowerCase() : String(value);
    var hit = null, i, p, neg;
    for (i = 0; i < pats.length; i++) {
      p = pats[i]; neg = false;
      if (p.charAt(0) === '!') { neg = true; p = p.slice(1); }
      var pp = foldCase ? p.toLowerCase() : p;
      var m = matchOne(pp, v, budget);
      if (m === null) return null;
      if (m) { if (neg) return { matched: false, by: null, vetoedBy: pats[i] }; if (hit === null) hit = pats[i]; }
    }
    return { matched: hit !== null, by: hit, vetoedBy: null };
  }

  /* ── parse ───────────────────────────────────────────────────────────────
     Returns { blocks, errors, directives }. Never throws (ship 002's second
     security finding was a thrown message reaching innerHTML). */
  function parse(text) {
    /* MEASURED 2026-08-08, after an independent checker refuted the first
       version: OpenSSH splits on LF ONLY. A lone CR is ordinary whitespace, not a
       line break — `Host *\rPort 9\r` is ONE line to ssh and leaves port at its
       default 22. Splitting on /\r\n|\r|\n/ (the obvious, wrong thing) invented a
       second line and reported port 9. CRLF still works because the trailing CR is
       stripped as whitespace. */
    var lines = String(text == null ? '' : text).split('\n');
    var blocks = [], errors = [], fatal = [], cur = null, i;
    /* OpenSSH does not warn about a malformed config — it REFUSES THE WHOLE FILE
       and exits, printing nothing. An earlier version of this parser collected
       these as notes and carried on rendering a confident table, which two
       independent checkers refuted on 2026-08-08 with four separate reproductions
       (unknown keyword, `Match all` combined, a keyword with no argument, an
       unterminated quote). A table that ssh would never have produced is worse
       than no table: it is a wrong answer wearing the costume of a right one. */
    function fail(line, message) { fatal.push({ line: line, message: message }); }

    function newBlock(kind, lineNo, raw) {
      cur = { kind: kind, line: lineNo, raw: raw, directives: [], patterns: null, criteria: null,
              unsupported: null, error: null };
      blocks.push(cur);
      return cur;
    }
    /* The implicit block that owns any directive appearing before the first
       Host/Match. MEASURED: those apply to every host. */
    newBlock('global', 0, '');

    for (i = 0; i < lines.length; i++) {
      var lineNo = i + 1, raw = lines[i];
      /* CR counts as whitespace here, which matters for two reasons at once: a
         CRLF file leaves a trailing CR on every line after the LF split, and a
         blank line in a CRLF file is the single character "\r". Treating that as
         a directive produced an empty keyword and then a fatal "unknown keyword"
         on every blank line of every CRLF config — found by this ship's own
         extended harness, 2026-08-08, on the first run that mixed CRLF with the
         new refusal check. */
      var trimmed = raw.replace(/^[ \t\r]+/, '');
      if (trimmed === '' || trimmed.charAt(0) === '#') continue;
      var sk = splitKeyword(raw);
      var kwRaw = sk.keyword, kw = kwRaw.toLowerCase();
      if (kw === '') continue;                       /* whitespace-only line */
      var tk = tokenize(sk.rest);
      var args = tk.tokens;

      if (tk.unterminatedQuote) fail(lineNo, 'invalid quotes — an unterminated double quote. ' +
        'OpenSSH refuses the whole file with "invalid quotes".');

      if (kw === 'host') {
        if (!args.length) { fail(lineNo, 'Host with no pattern. OpenSSH refuses the whole file ' +
          'with "no argument after keyword \"host\"".'); continue; }
        newBlock('host', lineNo, raw); cur.patterns = args;
        continue;
      }
      if (kw === 'match') {
        if (!args.length) { fail(lineNo, 'Match with no criteria. OpenSSH refuses the whole file ' +
          'with "Missing Match criteria".'); continue; }
        newBlock('match', lineNo, raw);
        var crit = [], unsupported = [], j = 0, bad = null, seen = 0;
        while (j < args.length) {
          var name = String(args[j]).toLowerCase();
          /* MEASURED, and the rule is not the one anybody would guess. `all` is
             refused when MORE THAN ONE attribute has already been seen, OR when
             anything at all follows it. So `Match host foo all` is legal,
             `Match user root all` is legal, `Match all host foo` is fatal, and
             `Match host foo,bar user root all` is fatal. Probed exhaustively
             2026-08-08 after a checker found the naive version accepted the
             fatal forms. */
          if (name === 'all') {
            if (seen > 1 || j + 1 < args.length) {
              bad = '\'all\' cannot be combined with other Match attributes'; break;
            }
            crit.push({ name: 'all', args: null }); seen++; j++; continue;
          }
          if (UNSUPPORTED_CRITERIA[name]) {
            var needsArg = (name === 'exec' || name === 'tagged');
            if (needsArg && j + 1 >= args.length) { bad = 'Missing Match criteria for ' + name; break; }
            unsupported.push({ name: name, why: UNSUPPORTED_CRITERIA[name] });
            seen++; j += needsArg ? 2 : 1;
            continue;
          }
          if (MATCH_CRITERIA_WITH_ARG[name]) {
            if (j + 1 >= args.length) { bad = 'Missing Match criteria for ' + name; break; }
            crit.push({ name: name, args: String(args[j + 1]).split(',') }); seen++; j += 2; continue;
          }
          bad = 'Bad Match condition — unknown criterion "' + args[j] + '"'; break;
        }
        cur.criteria = crit;
        cur.unsupported = unsupported.length ? unsupported : null;
        if (bad) { cur.error = bad; fail(lineNo, bad + '. OpenSSH refuses the whole file.'); }
        continue;
      }
      if (kw === 'include') {
        cur.directives.push({ line: lineNo, keyword: kwRaw, key: kw, args: args,
          value: args.join(' '), refused: 'Include pulls in another file from disk; a page in your ' +
          'browser has no filesystem, so this tool cannot follow it' });
        continue;
      }
      var value = REST_OF_LINE[kw] ? sk.rest.replace(/[ \t\r]+$/, '') : args.join(' ');
      cur.directives.push({ line: lineNo, keyword: kwRaw, key: kw, args: args,
        value: value,
        restOfLine: REST_OF_LINE[kw] ? true : false,
        unknown: KWSET[kw] ? false : true,
        expands: /[%~]/.test(value) });
      if (!KWSET[kw]) {
        fail(lineNo, '"' + kwRaw + '" is not in this tool’s probed OpenSSH 9.6p1 keyword table. ' +
          'OpenSSH refuses an unknown keyword outright ("Bad configuration option") and exits, so ' +
          'no options are resolved. If this keyword is real and newer than 9.6p1, that is a limit ' +
          'of this page, not of your file.');
      } else if (!args.length) {
        /* MEASURED: all 132 non-block keywords were probed with no argument and ALL
           132 are fatal. There is no keyword that legally stands alone. */
        fail(lineNo, 'no argument after keyword "' + kwRaw + '". OpenSSH refuses the whole file.');
      }
    }
    if (blocks.length && blocks[0].kind === 'global' && !blocks[0].directives.length) blocks.shift();
    fatal.sort(function (a, b) { return a.line - b.line; });
    return { blocks: blocks, errors: errors, fatal: fatal, lineCount: lines.length };
  }

  /* ── resolve ─────────────────────────────────────────────────────────────
     opts: { host (original, required), user (from user@host or -l, optional),
             localuser (optional) }
     Sequential, in file order. MEASURED: `Match host`/`Match user` see the values
     as they stand AT THAT POINT, so a Hostname/User set earlier changes what a
     later Match sees, and one set later does not. */
  function resolve(parsed, opts, budget) {
    resetCache();
    var host = String(opts.host == null ? '' : opts.host);
    var localuser = String(opts.localuser == null ? '' : opts.localuser);
    var effective = {}, order = [], shadowed = [], trace = [], notes = [];
    /* An UNDECIDABLE block (Match exec / canonical / final / tagged) poisons
       everything downstream of it, and the first version of this resolver did not
       say so: it skipped the block and then presented a later block's value with
       full confidence. A checker refuted it on 2026-08-08 with
       `Match exec "true"` / Port 1 followed by `Host *` / Port 2 — the real ssh
       says 1, the page said 2 and looked certain. Because the undecidable block
       might have set ANY keyword first, and first wins, every value first obtained
       after it is marked uncertain, and the fact that unset keywords might also
       have been set there is stated once. */
    var undecidableAt = null;

    /* MEASURED: default Hostname is the LOWERCASED host argument; the reported
       `host` keeps its original case. */
    var curHostname = host.toLowerCase();
    var curUser = (opts.user == null || opts.user === '') ? localuser : String(opts.user);
    var userFromCmdline = !(opts.user == null || opts.user === '');

    function record(d, blockIdx) {
      var k = d.key;
      if (ACCUMULATES[k]) {
        if (!effective[k]) { effective[k] = { key: k, accumulates: true, entries: [],
                                              uncertainAfter: undecidableAt }; order.push(k); }
        var acc = effective[k].entries;
        if (DEDUPES[k]) {
          for (var q = 0; q < acc.length; q++) {
            if (acc[q].value === d.value) {
              shadowed.push({ key: k, value: d.value, line: d.line, block: blockIdx,
                              lostTo: acc[q].line, duplicate: true });
              return;
            }
          }
        }
        acc.push({ value: d.value, line: d.line, block: blockIdx, expands: d.expands });
        return;
      }
      /* MEASURED 2026-08-08: a user given on the command line (`ssh -l u host` or
         `ssh u@host`) OUTRANKS every `User` line in the file — the config lines do
         not merely lose the tie, they never apply, and `Match user` keeps seeing
         the command-line user no matter what a `User` line earlier in the file
         says. Treat them as shadowed by the command line, not by each other.
         Found by the differential harness, not by reading: the first 200-case run
         produced six `user` mismatches and this was all of them. */
      if (k === 'user' && userFromCmdline) {
        shadowed.push({ key: k, value: d.value, line: d.line, block: blockIdx,
                        lostTo: null, lostToCmdline: true });
        return;
      }
      if (!effective[k]) {
        effective[k] = { key: k, accumulates: false, value: d.value, line: d.line,
                         block: blockIdx, expands: d.expands, unknown: d.unknown,
                         uncertainAfter: undecidableAt };
        order.push(k);
        if (k === 'hostname' && !d.expands) curHostname = String(d.value).toLowerCase();
        if (k === 'user' && !userFromCmdline && !d.expands) curUser = String(d.value);
        if ((k === 'hostname' || k === 'user') && d.expands) {
          notes.push({ line: d.line, message: 'Line ' + d.line + ' sets ' + k + ' using a %-token or ~. ' +
            'OpenSSH expands those and this page does not, so any later "Match ' +
            (k === 'hostname' ? 'host' : 'user') + '" is evaluated against the UNEXPANDED text and may be wrong.' });
        }
      } else {
        shadowed.push({ key: k, value: d.value, line: d.line, block: blockIdx,
                        lostTo: effective[k].line });
      }
    }

    for (var b = 0; b < parsed.blocks.length; b++) {
      var blk = parsed.blocks[b], entry = { block: b, kind: blk.kind, line: blk.line,
        matched: false, reason: '', detail: null, undecidable: false };

      if (blk.kind === 'global') { entry.matched = true; entry.reason = 'applies to every host (before any Host or Match block)'; }
      else if (blk.kind === 'host') {
        /* MEASURED: matched against the ORIGINAL host, case-SENSITIVELY. */
        var r = matchList(blk.patterns, host, false, budget);
        if (r === null) return { budgetExceeded: true };
        entry.matched = r.matched;
        entry.reason = r.matched
          ? 'pattern ' + JSON.stringify(r.by) + ' matches the host argument ' + JSON.stringify(host) + ' (case-sensitive)'
          : (r.vetoedBy ? 'negated pattern ' + JSON.stringify(r.vetoedBy) + ' vetoes this block'
                        : 'no pattern matches the host argument ' + JSON.stringify(host) + ' (Host matching is case-SENSITIVE)');
      } else {
        if (blk.error) { entry.matched = false; entry.undecidable = true; entry.reason = blk.error; }
        else if (blk.unsupported) {
          entry.matched = false; entry.undecidable = true;
          entry.reason = 'cannot be evaluated here: ' + blk.unsupported.map(function (u) {
            return 'Match ' + u.name + ' ' + u.why; }).join('; ');
        } else {
          var all = true, why = [];
          for (var c = 0; c < blk.criteria.length; c++) {
            var cr = blk.criteria[c], ok, subject, fold;
            if (cr.name === 'all') { why.push('all'); continue; }
            if (cr.name === 'host') { subject = curHostname; fold = true; }
            else if (cr.name === 'originalhost') { subject = host; fold = true; }
            else if (cr.name === 'user') { subject = curUser; fold = true; }
            else { subject = localuser; fold = true; }
            var mr = matchList(cr.args, subject, fold, budget);
            if (mr === null) return { budgetExceeded: true };
            ok = mr.matched;
            why.push('Match ' + cr.name + ' ' + JSON.stringify(cr.args.join(',')) + ' vs ' +
              JSON.stringify(subject) + ' → ' + (ok ? 'yes' : (mr.vetoedBy ? 'vetoed by ' + JSON.stringify(mr.vetoedBy) : 'no')));
            if (!ok) { all = false; break; }
          }
          entry.matched = all && blk.criteria.length > 0;
          entry.reason = why.join(' · ') || 'no criteria';
        }
      }
      trace.push(entry);
      if (entry.undecidable && undecidableAt === null) {
        undecidableAt = blk.line;
        notes.push({ line: blk.line, message: 'Line ' + blk.line + ' is a block this page cannot decide (' +
          entry.reason + '). Because the FIRST value obtained wins, that block could have set any option ' +
          'before the blocks below it did — so every value below is marked uncertain, and an option this ' +
          'page reports as unset might in fact be set there. Run `ssh -G` on your own machine for a ' +
          'definitive answer on this file.' });
      }
      if (!entry.matched) continue;
      for (var d = 0; d < blk.directives.length; d++) {
        var dir = blk.directives[d];
        if (dir.refused) { notes.push({ line: dir.line, message: dir.refused }); continue; }
        if (dir.unknown) { notes.push({ line: dir.line, message: 'line ' + dir.line + ': "' + dir.keyword +
          '" is not in this tool’s OpenSSH 9.6p1 keyword table, so no value is resolved for it. ' +
          'OpenSSH rejects an unknown keyword outright — check the spelling.' }); continue; }
        record(dir, b);
      }
    }

    return { effective: effective, order: order, shadowed: shadowed, trace: trace,
             notes: notes, finalHostname: curHostname, finalUser: curUser };
  }

  return { parse: parse, resolve: resolve, KEYWORDS: KEYWORDS, KWSET: KWSET,
           ACCUMULATES: ACCUMULATES, DEDUPES: DEDUPES, RESTS_OF_LINE: REST_OF_LINE,
           tokenize: tokenize, matchList: matchList,
           _resetCache: resetCache };
});
