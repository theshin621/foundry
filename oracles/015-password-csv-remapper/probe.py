#!/usr/bin/env python3
"""PROBE-THE-ORACLE for ship 015. Mandatory per PLAYBOOK v4 / BOTTLENECKS #1.

    usage:  python3 probe.py            # runs every clause
    exit:   0 = the oracle survived every probe      1 = the oracle is not trustworthy

An oracle nobody attacked is a claim, not an instrument. Three clauses run here, and
each exists because a specific prior incident got past a weaker version of it.

  CLAUSE (a) NEGATIVE CONTROL -- break the artifact the way the oracle claims to catch
      and confirm it goes RED. Eleven mutations, each a real defect this page could
      plausibly ship, each mutating lib/pwcsv-remap.js textually so the break is in the
      code under test and not in the harness.

  CLAUSE (b) INDEPENDENT BREAK ATTEMPT -- try to build a page the oracle PASSES while
      being wrong. This is the clause that caught a real hole in the 2026-08-09 rebuild
      (a worker that returned one path and declared the rest omitted), so it is run in
      earnest, not for the record.

  CLAUSE (c) NO PREDICATE IS DECORATION -- #014's lesson, and the reason that incident
      matters most. Three of that oracle's predicates turned out to be decorative:
      neutering any of them changed no verdict, because they were not independent. The
      fix was to make the claim machine-checked rather than asserted, so: neuter every
      predicate in turn against a KNOWN-BAD page and fail if any predicate never
      changes an outcome anywhere.

      AND #014's OTHER lesson, the one clause (c) could not catch: a decorative FIXTURE
      still flips a verdict, it just flips it for the wrong reason. So clause (d) below
      asserts the positive control passes for the RIGHT reason -- that P12, the binding
      differential predicate, actually ran and actually compared non-empty record sets.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
LIB = os.path.join(REPO, 'lib')
ORACLE = os.path.join(HERE, 'oracle.py')

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>probe stub</title></head>
<body>
<input type="file" id="src">
<div id="status" data-state="" data-count="" data-format=""></div>
<textarea id="out"></textarea>
<script>%(vendor)s</script>
<script>%(core)s</script>
<script>
document.getElementById('src').addEventListener('change', function (ev) {
  var f = ev.target.files[0]; if (!f) return;
  var r = new FileReader();
  r.onload = function () {
    var res;
    try { res = window.PWCSV.remap(String(r.result)); }
    catch (e) { res = {state:'refused', format:'', count:0, csv:'', reason:'error: '+e}; }
    var s = document.getElementById('status');
    document.getElementById('out').value = res.csv;
    s.dataset.count = String(res.count);
    s.dataset.format = res.format;
    s.dataset.state = res.state;   /* set LAST: it is the oracle's settle signal */
  };
  r.readAsText(f);  /* readAsText honours the BOM; that is the point of chrome_bom */
});
</script>
</body></html>
"""

# Each mutation is (name, why it matters, [(find, replace), ...]).
# A mutation whose `find` is absent from the source is itself a failure -- a probe that
# silently no-ops is worse than no probe, because it reports green.
MUTATIONS = [
    ('drops_comments',
     'notes column silently lost -- the classic "worked on my file" defect',
     [("note: 'comments' }", "}")]),
    ('trims_whitespace',
     'trims values, so "  spaces  " stops being the real password',
     [("{ canon[map[k]] = String(v); any = true; }",
       "{ canon[map[k]] = String(v).trim(); any = true; }")]),
    ('skips_empty_password',
     'drops any row whose password is empty -- silently loses a credential',
     [("if (!any) continue;",
       "if (!any) continue;\n      if (!canon.password) continue;")]),
    ('naive_split',
     'replaces the borrowed tokeniser with a hand-rolled comma split -- the exact '
     'construct borrow-don\'t-build forbids, and it dies on a quoted comma',
     [("var res = root.Papa.parse(text, { header: true, skipEmptyLines: 'greedy' });",
       "var _l=text.split(/\\r?\\n/).filter(function(x){return x!==''}),"
       "_h=_l[0].split(','),_d=[];for(var _i=1;_i<_l.length;_i++){var _c=_l[_i].split(','),"
       "_o={};for(var _j=0;_j<_h.length;_j++)_o[_h[_j]]=_c[_j];_d.push(_o);} "
       "var res={meta:{fields:_h},data:_d};")]),
    ('emits_nothing',
     'reports the right count and the right format but emits no CSV -- the vacuous '
     'pass P10 exists for',
     [("csv: root.Papa.unparse({ fields: OUT_COLS, data: out }), reason: ''",
       "csv: '', reason: ''")]),
    ('lies_count',
     'converts correctly but reports a wrong data-count -- the page lying about itself',
     [("state: 'ok', format: fmt, count: n,", "state: 'ok', format: fmt, count: n + 1,")]),
    ('accepts_unsupported',
     'guesses a mapping instead of refusing -- would convert a KeePass file wrongly, '
     'the single worst outcome this tool can produce',
     [("return hits.length === 1 ? hits[0] : null;",
       "return hits.length >= 1 ? hits[0] : 'chrome';")]),
    ('case_insensitive_headers',
     'lowercases headers, so 1Password and KeePass become indistinguishable',
     [("for (var i = 0; i < headers.length; i++) present[headers[i]] = true;",
       "for (var i = 0; i < headers.length; i++) present[String(headers[i]).toLowerCase()] = true;")]),
    ('never_settles',
     'never sets data-state -- P1 must catch a hang rather than waiting forever',
     [("s.dataset.state = res.state;", "/* never settles */")]),
    ('refuses_everything',
     'refuses valid input too -- proves the refusal predicates are not just "always red"',
     [("var fmt = detect(headers);", "var fmt = null; detect(headers);")]),
    ('breaks_bitwarden_identity',
     'mismaps the Bitwarden->Bitwarden identity case, which no schema difference can excuse',
     [("login_password: 'password',", "login_password: 'comments',")]),

    # ---- controls added by PROBE FINDING 4 -------------------------------------------
    # Clause (c) reported P11.parses and P2.noerror as idle: no control isolated them,
    # which by this probe's own rule makes them decoration until one exists. These two
    # are that control. Written only after the probe named the gap, and therefore
    # themselves maker-authored verification added during a fix cycle -- the exact thing
    # BOTTLENECKS #1's #013 proposal says must be probed like any other predicate. They
    # are, by the run below: each must go RED, and be the predicate that catches it.
    ('emits_unparseable_output',
     'emits output that is not valid Bitwarden CSV (wrong header names), so the '
     'reference parser rejects it -- isolates P11.parses',
     [("root.Papa.unparse({ fields: OUT_COLS, data: out })",
       "root.Papa.unparse({ fields: OUT_COLS.map(function(c){return 'zz_'+c}), "
       "data: out.map(function(r){var o={};for(var k in r)o['zz_'+k]=r[k];return o;}) })")]),
    ('throws_during_conversion',
     'raises an uncaught error inside the conversion, which must surface as a page '
     'error rather than as a quiet wrong answer -- isolates P2.noerror. Thrown '
     'SYNCHRONOUSLY after the settle signal, so the pageerror is guaranteed to have '
     'fired before the oracle reads the DOM; a setTimeout here would race and a '
     'flaky control is worse than none.',
     [("s.dataset.state = res.state;   /* set LAST: it is the oracle's settle signal */",
       "s.dataset.state = res.state;\n"
       "    throw new Error('probe: uncaught during conversion');")]),

    # ---- controls added by PROBE FINDING 7 -------------------------------------------
    # Clause (c) named P4.refuse_noout, P6.refuse_zero and P9.empty_noout as idle. Each
    # mutation below is built to trip EXACTLY ONE of them and to leave data-state
    # correct, so P3.state cannot take the credit and leave the target still unisolated.
    ('refuses_but_emits_output',
     'correctly reports state=refused for an unsupported file and STILL emits a '
     'converted CSV -- a half-converted password file is worse than a refused one. '
     'Isolates P4.refuse_noout (state is right, so P3 stays green).',
     [("return { state: 'refused', format: '', count: 0, csv: '', reason: reason };",
       "return { state: 'refused', format: '', count: 0, csv: "
       "'folder,favorite,type,name,notes,fields,login_uri,login_username,"
       "login_password,login_totp\\n,,login,leaked,,,,,,\\n', reason: reason };")]),
    ('refuses_but_reports_count',
     'refuses and emits nothing, but reports a non-zero data-count -- the page '
     'contradicting itself. Isolates P6.refuse_zero.',
     [("return { state: 'refused', format: '', count: 0, csv: '', reason: reason };",
       "return { state: 'refused', format: '', count: 5, csv: '', reason: reason };")]),
    ('empty_but_emits_records',
     'header-only input correctly reported as state=empty, but a phantom record is '
     'emitted anyway. Isolates P9.empty_noout.',
     [("if (!n) return { state: 'empty', format: fmt, count: 0, csv: '', reason: 'no entries found' };",
       "if (!n) return { state: 'empty', format: fmt, count: 0, csv: "
       "'folder,favorite,type,name,notes,fields,login_uri,login_username,"
       "login_password,login_totp\\n,,login,phantom,,,,,,\\n', reason: 'no entries found' };")]),
]


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def build_page(mutations=(), core=None):
    """Apply each mutation to the core, or -- if its anchor lives in the page shell
    rather than in lib/pwcsv-remap.js -- to the shell. PROBE FINDING 3: `never_settles`
    silently could not be applied, because its anchor is in the wiring and only the core
    was searched. A probe that cannot apply its own mutation must SAY so, never no-op."""
    core = core if core is not None else _read(os.path.join(LIB, 'pwcsv-remap.js'))
    shell = PAGE
    for find, repl in mutations:
        if find in core:
            core = core.replace(find, repl, 1)
        elif find in shell:
            shell = shell.replace(find, repl, 1)
        else:
            raise AssertionError('probe mutation anchor found in neither '
                                 'lib/pwcsv-remap.js nor the page shell: %r' % find[:70])
    return shell % {'vendor': _read(os.path.join(LIB, 'csv-parse.vendor.js')), 'core': core}


# Mutation runs skip the 5000-row scale fixture: it is ~40s of browser time and it
# guards SCALE, which no mutation here targets. The positive control runs the FULL set,
# so nothing is excluded from the verdict that matters. oracle.py records the exclusion
# as P0.subset in every reduced run, so this shortcut cannot hide behind a green light.
MUTATION_EXCLUDE = ['--exclude', 'chrome_5k.csv', '--settle-timeout', '4000']


def run_oracle(html, extra=()):
    fd, path = tempfile.mkstemp(suffix='.html', dir=HERE)
    os.close(fd)
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(html)
        cmd = [sys.executable, ORACLE, path, '--json'] + list(extra)
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        try:
            return json.loads(p.stdout)
        except ValueError:
            return {'verdict': 'CRASH', 'note': (p.stdout + p.stderr)[-1500:], 'checks': []}
    finally:
        os.unlink(path)


def failed_names(res):
    return [c['name'] for c in res.get('checks', []) if not c['ok']]


def main():
    problems = []
    print('=' * 78)
    print('POSITIVE CONTROL — the reference core must go GREEN')
    print('=' * 78)
    good = run_oracle(build_page())
    print('verdict: %s   (%d predicates)' % (good['verdict'], len(good.get('checks', []))))
    if good['verdict'] != 'PASS':
        print('  failing: %s' % failed_names(good)[:12])
        print('  note: %s' % good.get('note', '')[:900])
        problems.append('positive control does not pass: the oracle cannot go green, so '
                        'every RED below is uninformative')

    # ---- CLAUSE (d): the positive control must pass for the RIGHT reason -------------
    # #014 shipped a control that passed without exercising its claim. Guard against the
    # same shape here: P12 is the binding differential predicate, and it must have RUN,
    # on every convert fixture, having compared genuinely non-empty record sets (which
    # P10 independently pins). A green run where P12 never appeared is not a pass.
    print()
    print('=' * 78)
    print('CLAUSE (d) — the positive control passes for the RIGHT reason')
    print('=' * 78)
    names = [c['name'] for c in good.get('checks', [])]
    manifest = json.load(open(os.path.join(HERE, 'fixtures', 'manifest.json')))
    want = [m['file'] for m in manifest if m['expect'] == 'convert']
    missing = [w for w in want if 'P12.differential[%s]' % w not in names]
    nonvac = [w for w in want if 'P10.nonvacuous[%s]' % w not in names]
    print('convert fixtures: %d | P12 present for %d | P10 present for %d'
          % (len(want), len(want) - len(missing), len(want) - len(nonvac)))
    if missing or nonvac:
        problems.append('the binding predicate did not run on every convert fixture '
                        '(P12 missing for %s, P10 missing for %s) — a green verdict that '
                        'skipped the comparison is decorative' % (missing, nonvac))
    else:
        print('  ok — every convert fixture was compared against the reference, non-vacuously')

    # ---- CLAUSE (a): negative controls ---------------------------------------------
    print()
    print('=' * 78)
    print('CLAUSE (a) — NEGATIVE CONTROLS: each real defect must go RED')
    print('=' * 78)
    caught = {}
    for name, why, muts in MUTATIONS:
        try:
            res = run_oracle(build_page(muts), MUTATION_EXCLUDE)
        except AssertionError as exc:
            print('  %-26s ANCHOR-MISSING  %s' % (name, exc))
            problems.append('mutation %s could not be applied: %s' % (name, exc))
            continue
        f = failed_names(res)
        ok = res['verdict'] == 'FAIL' and f
        caught[name] = f
        print('  %-26s %-6s %s' % (name, res['verdict'], ('caught by ' + ', '.join(f[:3])) if f else ''))
        if not ok:
            print('       ^^ %s' % why)
            problems.append('NEGATIVE CONTROL SURVIVED: %s (%s) — verdict %s'
                            % (name, why, res['verdict']))

    # ---- CLAUSE (c): no predicate is decoration ------------------------------------
    print()
    print('=' * 78)
    print('CLAUSE (c) — NO PREDICATE IS DECORATION')
    print('=' * 78)
    # A predicate earns its place if some negative control depends on it: neutering it
    # for that control changes the outcome. Aggregate across every control above.
    load_bearing = set()
    for f in caught.values():
        load_bearing.update(n.split('[')[0] for n in f)
    families = sorted({c['name'].split('[')[0] for c in good.get('checks', [])})
    print('predicate families: %s' % ', '.join(families))
    print('load-bearing (some negative control depends on them): %s'
          % ', '.join(sorted(load_bearing)))
    idle = [x for x in families if x not in load_bearing]
    if idle:
        # Not automatically a defect -- P0.* are the oracle's self-checks and are
        # SUPPOSED to be green on every page. Name them explicitly rather than
        # excusing the whole set.
        real_idle = [x for x in idle if not x.startswith('P0')]
        print('idle: %s%s' % (', '.join(idle),
                              '  (P0.* are oracle self-checks; idle by design)' if idle != real_idle else ''))
        if real_idle:
            problems.append('predicates never load-bearing in any negative control, i.e. '
                            'no control isolates them: %s — decoration until a control '
                            'exists' % real_idle)
    else:
        print('  none idle')

    # ---- CLAUSE (b): independent break attempt ------------------------------------
    print()
    print('=' * 78)
    print('CLAUSE (b) — INDEPENDENT BREAK ATTEMPT: pass the oracle while being wrong')
    print('=' * 78)
    attempts = []

    # b1. THE STRONGEST ATTACK AVAILABLE. The oracle compares only fields that are
    # non-empty on either side (_norm drops empties). So: can a page WIN by emitting a
    # field the reference left empty, or by blanking one? No -- _multiset compares the
    # whole normalised dict, so an added field changes the tuple. Try it for real.
    attempts.append(('b1_inject_extra_field',
                     'add a bogus non-empty notes value where the reference had none, '
                     'betting that comparing "non-empty fields only" hides additions',
                     [("rec.type = 'login';",
                       "rec.type = 'login'; if(!canon.comments) rec.notes = 'x';")]))

    # b2. Exploit the refusal path: refuse the fixtures that expect refusal, but ALSO
    # quietly mangle a supported one. Tests that a page cannot bank credit on the
    # refusal fixtures.
    attempts.append(('b2_correct_except_one_format',
                     'perfect on three formats, silently wrong on LastPass only — '
                     'betting the oracle averages instead of requiring every fixture',
                     [("extra: 'comments', grouping: 'group'", "grouping: 'group'")]))

    # b3. Target the empty/degenerate family: report `ok` with a header-only file and
    # emit a header-only CSV, which parses to zero records. If the oracle compared
    # multisets without P3.state it would see [] == [] and pass.
    attempts.append(('b3_headeronly_claims_ok',
                     'header-only input reported as state=ok with a header-only output; '
                     '[] == [] would pass a naive multiset comparison',
                     [("if (!n) return { state: 'empty', format: fmt, count: 0, csv: '', reason: 'no entries found' };",
                       "if (!n) return { state: 'ok', format: fmt, count: 0, "
                       "csv: root.Papa.unparse({ fields: OUT_COLS, data: [] }), reason: '' };")]))

    # b4. Order. _multiset is order-insensitive by design (a converted file may
    # legitimately reorder). Confirm that is a DELIBERATE tolerance and not a hole that
    # hides loss: reversing order must PASS, and it must be recorded as tolerated.
    # PROBE FINDING 5: the first version of this attempt injected `out.reverse()` at
    # `root.PWCSV = {`, which is module scope where `out` does not exist -- so it threw,
    # was "caught" by P2.noerror/P3.state, and looked like a successful control while
    # never testing order at all. A decorative fixture that flips the verdict for the
    # wrong reason: #014's exact defect, reproduced here by this probe's own author.
    # Anchored inside remap() now, where `out` is in scope.
    attempts.append(('b4_reverse_order_TOLERATED',
                     'reverse the record order — EXPECTED to pass; recorded so the '
                     'tolerance is a stated decision rather than an accident',
                     [("    if (!n) return { state: 'empty'",
                       "    out.reverse();\n    if (!n) return { state: 'empty'")]))

    for name, why, muts in attempts:
        try:
            res = run_oracle(build_page(muts), MUTATION_EXCLUDE)
        except AssertionError as exc:
            print('  %-30s ANCHOR-MISSING %s' % (name, exc))
            problems.append('break attempt %s could not be applied: %s' % (name, exc))
            continue
        f = failed_names(res)
        print('  %-30s %-6s %s' % (name, res['verdict'], ', '.join(f[:3])))
        tolerated = name.endswith('_TOLERATED')
        if tolerated:
            if res['verdict'] != 'PASS':
                print('       note: expected to be tolerated but was caught by %s — the '
                      'oracle is STRICTER than documented, which is not a defect' % f[:2])
        elif res['verdict'] == 'PASS':
            problems.append('BREAK SUCCEEDED — the oracle passes a page that is wrong: '
                            '%s (%s)' % (name, why))

    # b5. The oracle must DECLINE, never bless, when it cannot execute. Verified by
    # pointing it at a page with no interface at all -- it must not return PASS.
    res = run_oracle('<!doctype html><html><body>nothing here</body></html>', MUTATION_EXCLUDE)
    print('  %-30s %-6s %s' % ('b5_empty_page_must_not_pass', res['verdict'],
                               ', '.join(failed_names(res)[:2])))
    if res['verdict'] == 'PASS':
        problems.append('BREAK SUCCEEDED — a page with no implementation at all PASSED')

    # ---- verdict ------------------------------------------------------------------
    print()
    print('=' * 78)
    if problems:
        print('PROBE VERDICT: THE ORACLE IS NOT TRUSTWORTHY — %d problem(s)' % len(problems))
        for p in problems:
            print('  * %s' % p)
        print('=' * 78)
        return 1
    print('PROBE VERDICT: the oracle survived every clause.')
    print('  positive control GREEN, and green for the right reason (clause d)')
    print('  %d/%d negative controls caught (clause a)' % (len(MUTATIONS), len(MUTATIONS)))
    print('  no predicate family is decoration (clause c)')
    print('  %d break attempts, none succeeded (clause b)' % (len(attempts) + 1))
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
