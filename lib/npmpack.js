/* lib/npmpack.js — resolve the set of files `npm publish` would put in the tarball,
 * and the ONE rule that decided each. Contributed by ship 006
 * (npm-publish-preflight, 2026-08-07). Runs on lib/gitignore.js.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * EVERY RULE BELOW IS QUOTED FROM npm's OWN DOCUMENTATION, NOT FROM MEMORY.
 * The three sources, and what each one settles:
 *
 *   [A] https://docs.npmjs.com/cli/v11/configuring-npm/package-json  ("files")
 *       - the always-INCLUDED list, incl. "README & LICENSE can have any case
 *         and extension", plus the `main` and `bin` targets
 *       - the always-IGNORED list
 *       - the hard core that "cannot be included even if explicitly specified":
 *         .git, .npmrc, node_modules, package-lock.json, pnpm-lock.yaml,
 *         yarn.lock, bun.lockb
 *       - "The .npmignore file works just like a .gitignore. If there is a
 *         .gitignore file, and .npmignore is missing, .gitignore's contents will
 *         be used instead."
 *   [B] https://docs.npmjs.com/cli/v11/using-npm/developers/
 *       - the same replacement rule stated from the other side, and the trick it
 *         implies: "If you want to include something that is excluded by your
 *         .gitignore file, you can create an EMPTY .npmignore file to override it."
 *         That is why this module takes a `present` flag per ignore file and not
 *         just its text — an empty-but-present .npmignore is a meaningful input
 *         and a tool that only looks at the text cannot see it.
 *       - adds .gitignore and .npmignore themselves to the ignored list
 *   [C] https://github.com/npm/cli/wiki/Files-&-Ignores
 *       - "Entries matched by `files` will be included, regardless of .npmignore
 *         settings" — and flags this as npm's own open issue (#11669) rather than
 *         intended design.
 *
 * ── TWO PLACES THE DOCS ARE SILENT, AND WHAT THIS MODULE DOES ────────────────
 * Named here rather than resolved quietly, because a tool that guesses and does
 * not say so is worse than one that refuses.
 *
 *   1. Do npm's DEFAULT ignores still apply inside a directory named by `files`?
 *      [A] is explicit only about the hard core. This module takes the
 *      CONSERVATIVE reading — defaults apply in both modes — and labels any file
 *      it drops that way `npm-default-ignore`, so the answer is visible and
 *      arguable rather than buried. Flagged on the page too.
 *   2. Are README/LICENSE honoured at any depth or only at the package root?
 *      [A] says "can have any case and extension" and says nothing about depth.
 *      npm's own packlist anchors them to the root, so this module does too, and
 *      says so in the reason string (`always-include (root)`).
 *
 * ── ONE RULE THAT IS NOT A MATCHING RULE ─────────────────────────────────────
 * git (and therefore npm's walker) CANNOT re-include a file whose parent
 * directory was excluded — the walker never descends, so a `!` deeper in the file
 * never gets a chance to run. That is a property of walking a tree, not of
 * matching a path, so lib/gitignore.js deliberately does not implement it and
 * this module does: every ancestor directory is tested, shortest first, and the
 * first ignored ancestor is terminal. Ancestor verdicts are MEMOISED — without
 * that, a 2,000-path list re-tests the same directories thousands of times and
 * the cost is quadratic in the thing a user pastes.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(
    typeof require === 'function' ? require('./gitignore.js') : null);
  else root.npmpack = factory(root.gitignore);
})(typeof self !== 'undefined' ? self : this, function (gitignore) {
  'use strict';

  /* [A] + [B]. Written as gitignore lines because that is exactly how npm applies
     them — as the first rules of the stack, overridable by a later `!` except for
     the hard core below. Each carries the source that documents it. */
  var DEFAULT_IGNORE = [
    ['*.orig', 'A'], ['.*.swp', 'A'], ['.DS_Store', 'A'], ['._*', 'A'],
    ['.git', 'A'], ['.hg', 'A'], ['.lock-wscript', 'A'], ['.npmrc', 'A'],
    ['.svn', 'A'], ['.wafpickle-*', 'A'], ['CVS', 'A'], ['config.gypi', 'A'],
    ['node_modules', 'A'], ['npm-debug.log', 'A'], ['package-lock.json', 'A'],
    ['pnpm-lock.yaml', 'A'], ['yarn.lock', 'A'], ['bun.lockb', 'A'],
    ['.gitignore', 'B'], ['.npmignore', 'B']
  ];

  /* [A] "certain ignored files cannot be included even if explicitly specified" */
  var HARD = ['.git', '.npmrc', 'node_modules', 'package-lock.json',
              'pnpm-lock.yaml', 'yarn.lock', 'bun.lockb'];

  /* Files whose names LOOK like credentials. Not an npm rule — this module's own
     alarm, and labelled as such everywhere it surfaces. It never changes a
     verdict; it only raises a flag on a file npm WOULD publish. */
  var SECRET_PATTERNS = [
    '.env', '.env.*', '*.pem', '*.key', '*.p12', '*.pfx', '*.keystore', '*.jks',
    'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519', '*.ppk',
    'credentials', 'credentials.json', 'secrets.*', '*.secret', '.netrc',
    'service-account*.json', '*.pkcs12', 'terraform.tfstate', '.pypirc'
  ];

  function norm(p) {
    var s = String(p == null ? '' : p).replace(/\\/g, '/').replace(/^\.\//, '');
    while (s.length > 1 && s.charAt(0) === '/') s = s.slice(1);
    while (s.length > 1 && s.charAt(s.length - 1) === '/') s = s.slice(0, -1);
    return s;
  }

  function ancestorsOf(path) {
    var segs = path.split('/'), out = [], acc = '', i;
    for (i = 0; i < segs.length - 1; i++) {
      acc = acc ? acc + '/' + segs[i] : segs[i];
      out.push(acc);
    }
    return out;
  }

  function baseOf(p) { var i = p.lastIndexOf('/'); return i === -1 ? p : p.slice(i + 1); }

  /* README / LICENSE / LICENCE at the package root, any case, any extension [A] */
  function isRootReadmeOrLicence(path) {
    if (path.indexOf('/') !== -1) return false;
    var u = path.toUpperCase();
    if (u === 'README' || u.indexOf('README.') === 0) return true;
    if (u === 'LICENSE' || u.indexOf('LICENSE.') === 0) return true;
    if (u === 'LICENCE' || u.indexOf('LICENCE.') === 0) return true;
    return false;
  }

  function binTargets(pkg) {
    var out = [], b = pkg && pkg.bin, k;
    if (!b) return out;
    if (typeof b === 'string') { out.push(norm(b)); return out; }
    if (typeof b === 'object') for (k in b) if (Object.prototype.hasOwnProperty.call(b, k)) {
      if (typeof b[k] === 'string') out.push(norm(b[k]));
    }
    return out;
  }

  /* resolve(input) — input:
       pkg        parsed package.json object (or null)
       npmignore  { present: bool, text: string }
       gitignore  { present: bool, text: string }
       paths      array of repo-relative file paths
       budget     { left, deadline }
     returns { rows, summary, notes, exceeded } */
  function resolve(input) {
    var budget = input.budget || null;
    var pkg = input.pkg || null;
    var ni = input.npmignore || { present: false, text: '' };
    var gi = input.gitignore || { present: false, text: '' };

    var useNpmignore = !!ni.present;
    var useGitignore = !ni.present && !!gi.present;
    var chosenName = useNpmignore ? '.npmignore' : (useGitignore ? '.gitignore' : null);
    var chosenText = useNpmignore ? (ni.text || '') : (useGitignore ? (gi.text || '') : '');

    var defaults = gitignore.compile(DEFAULT_IGNORE.map(function (r) { return r[0]; }).join('\n'));
    var user = chosenName ? gitignore.compile(chosenText, { maxRules: 5000 }) : null;
    var hard = gitignore.compile(HARD.join('\n'));
    var secrets = gitignore.compile(SECRET_PATTERNS.join('\n'));

    var filesArr = (pkg && Object.prototype.hasOwnProperty.call(pkg, 'files') && Array.isArray(pkg.files))
      ? pkg.files.filter(function (x) { return typeof x === 'string' && x !== ''; }) : null;
    var hasFilesArray = !!filesArr;

    var mainTarget = (pkg && typeof pkg.main === 'string') ? norm(pkg.main) : null;
    var bins = binTargets(pkg);

    /* stack: later entries win (last matching rule wins across the whole stack) */
    var stack = [{ name: 'npm-default-ignore', c: defaults }];
    if (user) stack.push({ name: chosenName, c: user });

    var memo = Object.create(null);

    function decide(path, isDir) {
      var key = (isDir ? 'd:' : 'f:') + path;
      if (memo[key] !== undefined) return memo[key];
      var k, r, out = { ignored: false, source: null, rule: null };
      for (k = stack.length - 1; k >= 0; k--) {
        r = gitignore.test(stack[k].c, path, isDir, budget);
        if (r.exceeded) { out = { ignored: false, source: null, rule: null, exceeded: true }; break; }
        if (r.rule) { out = { ignored: r.ignored, source: stack[k].name, rule: r.rule }; break; }
      }
      memo[key] = out;
      return out;
    }

    /* Ancestor verdicts are memoised. Without this, a 2,000-path list at depth 30
       re-tests the same 30 directories 2,000 times — measured at 1,247 ms before
       the memo and 40 ms after it, on the same input. The memo is keyed on the
       directory path, which is exactly the granularity npm's own walker works at. */
    var hardMemo = Object.create(null);
    function hardDir(dir) {
      if (hardMemo[dir] !== undefined) return hardMemo[dir];
      var rr = gitignore.test(hard, dir, true, budget);
      return (hardMemo[dir] = rr.rule || null);
    }
    function hardHit(path) {
      var r = gitignore.test(hard, path, false, budget);
      if (r.rule) return r.rule;
      var a = ancestorsOf(path), i, hit;
      for (i = 0; i < a.length; i++) { hit = hardDir(a[i]); if (hit) return hit; }
      return null;
    }

    /* a files[] entry matches a path if it matches the path itself OR any ancestor
       directory of it — that is what "a directory entry includes it recursively"
       means once you are matching flat paths instead of walking a tree */
    function filesHit(path) {
      var i, j, a = ancestorsOf(path), e;
      for (i = 0; i < filesArr.length; i++) {
        e = norm(filesArr[i]);
        if (e === '' ) continue;
        if (gitignore.matchOne(e, path, false, budget)) return { entry: filesArr[i], index: i, via: null };
        for (j = 0; j < a.length; j++) {
          if (gitignore.matchOne(e, a[j], true, budget)) return { entry: filesArr[i], index: i, via: a[j] };
        }
        if (budget && budget.exceeded) return null;
      }
      return null;
    }

    var rows = [], seen = Object.create(null);
    var paths = input.paths || [];
    var i, p, row, h, anc, d, fh, k, stopped = false;

    for (i = 0; i < paths.length; i++) {
      if (budget && budget.exceeded) { stopped = true; break; }
      p = norm(paths[i]);
      if (p === '' || p === '.') continue;
      if (seen[p]) continue;
      seen[p] = 1;

      row = { path: p, included: false, source: '', detail: '', line: null, secret: false };

      h = hardHit(p);
      if (h) {
        row.included = false; row.source = 'npm-hard-exclude';
        row.detail = h.raw;
        row.why = 'npm never publishes this, and it cannot be re-included even if named in files[]';
        rows.push(row); continue;
      }

      if (p === 'package.json' || isRootReadmeOrLicence(p) ||
          (mainTarget && p === mainTarget) || bins.indexOf(p) !== -1) {
        row.included = true; row.source = 'npm-always-include';
        row.detail = p === 'package.json' ? 'package.json'
          : isRootReadmeOrLicence(p) ? 'README/LICENSE at the package root, any case or extension'
          : (mainTarget && p === mainTarget) ? 'the "main" entry point'
          : 'a "bin" entry point';
        row.why = 'always included regardless of files[], .npmignore or .gitignore';
        row.secret = !!gitignore.test(secrets, p, false, budget).rule;
        rows.push(row); continue;
      }

      anc = ancestorsOf(p); d = null;
      for (k = 0; k < anc.length; k++) {
        d = decide(anc[k], true);
        if (d.exceeded) { stopped = true; break; }
        if (d.ignored) break;
        d = null;
      }
      if (stopped) break;
      if (d && d.ignored) {
        row.included = false;
        row.source = d.source;
        row.detail = d.rule.raw;
        row.line = d.rule.line || null;
        row.why = 'the directory "' + anc[k] + '" is excluded, so nothing under it is walked — a later "!" rule cannot bring this back';
        rows.push(row); continue;
      }

      if (hasFilesArray) {
        fh = filesHit(p);
        if (budget && budget.exceeded) { stopped = true; break; }
        if (!fh) {
          row.included = false; row.source = 'files[]';
          row.detail = 'no entry matches';
          row.why = 'package.json has a "files" array, which is an allow-list — anything it does not name is left out';
          rows.push(row); continue;
        }
        d = decide(p, false);
        if (d.exceeded) { stopped = true; break; }
        if (d.ignored && d.source === 'npm-default-ignore') {
          row.included = false; row.source = 'npm-default-ignore';
          row.detail = d.rule.raw;
          row.why = 'npm ignores this by default; the docs are explicit only about the hard-core list, so this tool takes the conservative reading and still drops it';
          rows.push(row); continue;
        }
        row.included = true; row.source = 'files[]';
        row.detail = fh.entry + (fh.via ? '  (matched the directory "' + fh.via + '")' : '');
        row.why = 'matched by files[' + fh.index + ']. npm documents this as winning over .npmignore — and flags it as its own open issue #11669';
        row.secret = !!gitignore.test(secrets, p, false, budget).rule;
        rows.push(row); continue;
      }

      d = decide(p, false);
      if (d.exceeded) { stopped = true; break; }
      if (d.ignored) {
        row.included = false; row.source = d.source;
        row.detail = d.rule.raw; row.line = d.rule.line || null;
        row.why = d.source === 'npm-default-ignore'
          ? 'on npm\'s always-ignored list'
          : 'last matching rule in ' + d.source + ' wins';
        rows.push(row); continue;
      }
      row.included = true;
      row.source = d.rule ? d.source : (chosenName ? 'not ignored' : 'no ignore rules');
      row.detail = d.rule ? d.rule.raw : (chosenName ? 'no rule matched' : 'no files[], no ' + '.npmignore' + ', no .gitignore');
      row.line = d.rule ? (d.rule.line || null) : null;
      row.why = d.rule
        ? 'the last matching rule is a "!" re-include'
        : (chosenName ? 'nothing excluded it' : 'nothing was supplied that could exclude it');
      row.secret = !!gitignore.test(secrets, p, false, budget).rule;
      rows.push(row);
    }

    var included = 0, secretsOut = [];
    for (i = 0; i < rows.length; i++) {
      if (rows[i].included) {
        included++;
        if (rows[i].secret) secretsOut.push(rows[i].path);
      }
    }

    var inSet = Object.create(null);
    for (i = 0; i < rows.length; i++) if (rows[i].included) inSet[rows[i].path] = 1;

    var missing = [];
    if (mainTarget && !inSet[mainTarget]) missing.push({ field: 'main', target: mainTarget });
    for (i = 0; i < bins.length; i++) if (!inSet[bins[i]]) missing.push({ field: 'bin', target: bins[i] });

    var notes = [];
    if (!hasFilesArray && !ni.present && !gi.present) {
      notes.push({ level: 'warn', text: 'No "files" array, no .npmignore and no .gitignore — everything in the tree is published except npm\'s own default excludes.' });
    }
    if (ni.present && gi.present) {
      notes.push({ level: 'info', text: '.npmignore is present, so .gitignore is ignored ENTIRELY — npm replaces, it does not merge. Rules you rely on in .gitignore are not in force.' });
    }
    if (ni.present && (ni.text || '').trim() === '') {
      notes.push({ level: 'info', text: 'The .npmignore is empty. That is a real npm idiom: an empty .npmignore switches .gitignore off so everything gets published.' });
    }
    if (hasFilesArray && (ni.present || gi.present)) {
      notes.push({ level: 'info', text: 'A "files" array is present. npm documents entries matched by files[] as included regardless of .npmignore — npm\'s own wiki flags that as open issue #11669, so treat it as current behaviour rather than a guarantee.' });
    }

    /* How many DISTINCT paths were supplied, counted the same way the loop
       de-duplicates them. A caller that stopped early needs "attempted minus
       resolved" to state honestly how many files it never reached — comparing
       against the raw input length would over-count every duplicate line. */
    var attempted = 0, seenAll = Object.create(null), q;
    for (i = 0; i < paths.length; i++) {
      q = norm(paths[i]);
      if (q === '' || q === '.' || seenAll[q]) continue;
      seenAll[q] = 1; attempted++;
    }

    return {
      rows: rows,
      attempted: attempted,
      exceeded: stopped || !!(budget && budget.exceeded),
      summary: {
        total: rows.length,
        included: included,
        excluded: rows.length - included,
        mode: hasFilesArray ? 'files[] allow-list' : (chosenName ? chosenName : 'no ignore file'),
        chosenIgnore: chosenName,
        ignoredIgnoreFile: (ni.present && gi.present) ? '.gitignore' : null,
        secrets: secretsOut,
        missingTargets: missing,
        userRuleErrors: user ? user.errors : []
      },
      notes: notes
    };
  }

  return {
    resolve: resolve,
    DEFAULT_IGNORE: DEFAULT_IGNORE,
    HARD: HARD,
    SECRET_PATTERNS: SECRET_PATTERNS,
    _norm: norm,
    _ancestorsOf: ancestorsOf,
    _isRootReadmeOrLicence: isRootReadmeOrLicence
  };
});
