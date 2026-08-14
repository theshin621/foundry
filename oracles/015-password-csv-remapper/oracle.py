#!/usr/bin/env python3
"""ORACLE for ship 015 password-csv-remapper. Written BEFORE any product code exists.

    usage:  python3 oracle.py <page.html | http://host/path/>  [--json] [--fixture NAME]
    exit:   0 = PASS      1 = FAIL      2 = CANNOT-CERTIFY

=============================================================================
WHAT MAKES THIS DIFFERENT FROM THE SIX ORACLES BEFORE IT
=============================================================================
BOTTLENECKS.md entry #1 is at count 5 (+5 unadjudicated). Every incident in it shares
one mechanism: the artifact was checked against predicates THE MAKER AUTHORED, so each
fix cycle revealed the next rule the maker had not thought of, and the defects climbed
from the product into the oracle and then into the oracle's own fixtures (#014).

This oracle does not author the correctness criterion. `pass_import` does, and it is on
BOTH ends of the comparison:

    fixture bytes ──[pass_import.ChromeCSV / BitwardenCSV / LastpassCSV / OnePassword8CSV]──> REFERENCE records
    fixture bytes ──[the page under test, executing in real Chromium]──> output CSV
                    ──[pass_import.BitwardenCSV]────────────────────────> ACTUAL records
    PASS iff  REFERENCE records == ACTUAL records   (as multisets, per non-empty field)

`pass_import` is a mature third-party importer supporting dozens of managers, and its
column mappings ARE the spec for these four formats. The maker cannot quietly redefine
the target set mid-fix-cycle, because the target set is computed by a library the maker
does not control. That is the specific mechanism entry #1 has been asking for since
2026-08-06, and in fifteen days the loop has never once used it.

=============================================================================
THE PAGE IS EXECUTED, NEVER PARSED
=============================================================================
Entry #1 clause 3, five incidents deep: "for ANY liveness-of-markup claim the oracle
EXECUTES the page in a real browser and observes behaviour; hand-written HTML
parse-and-match walkers are FORBIDDEN." Every claim here is a behaviour claim -- does
this page, given these bytes, produce those records -- so there is no markup inspection
anywhere in this file. Chromium loads the page, a real File is handed to a real file
input, and the DOM is read afterwards. No browser => CANNOT-CERTIFY, never PASS.
A missing tool must not read as a blessing.

THE BOM FIXTURE IS NOT DECORATIVE, and this is where #014's lesson bites. `chrome_bom.csv`
tests that THE PAGE tolerates a UTF-8 BOM. If the oracle stripped the BOM before handing
the bytes over, the fixture would pass without ever exercising the claim -- exactly the
"decorative fixture" defect #014 shipped. So: the browser side receives RAW BYTES, read
'rb', and the BOM is stripped only on the reference side, where the job is to establish
what the logical content IS. Enforced by P0.bytes below.

=============================================================================
INTERFACE CONTRACT (fixed here, before the builder starts)
=============================================================================
The page MUST provide:
  * <input type="file" id="src">              the file input
  * #status with:
        data-state  = "ok" | "empty" | "refused"
        data-count  = integer, entries converted (0 for empty/refused)
        data-format = detected format id ("chrome"|"bitwarden"|"lastpass"|"onepassword")
                      or "" when refused
  * #out                                      element whose .value/.textContent is the
                                              output Bitwarden CSV ("" unless state==ok)
Conversion must complete within PER_FIXTURE_TIMEOUT_MS of the file being set, signalled
by #status carrying a non-empty data-state.
"""
import argparse
import io
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
FIXDIR = os.path.join(HERE, 'fixtures')
# 45s is sized for chrome_5k.csv (5000 rows through a real FileReader). probe.py lowers
# it, because a page that never settles would otherwise cost 45s x every fixture and the
# probe would take longer than the day. Lowered ONLY where the scale fixture is excluded.
PER_FIXTURE_TIMEOUT_MS = 45000

# The fields compared. Restricted to what all four source formats can carry, so the
# comparison is about data preservation and not about schema trivia.
CORE = ('title', 'login', 'password', 'url', 'comments', 'group', 'otpauth')


def _reference_records(fmt, path):
    """Ground truth, computed by pass_import and not by this file."""
    from pass_import.managers import (BitwardenCSV, ChromeCSV, LastpassCSV,
                                      OnePassword8CSV)
    ref = {'chrome': ChromeCSV, 'bitwarden': BitwardenCSV,
           'lastpass': LastpassCSV, 'onepassword': OnePassword8CSV}[fmt]
    # utf-8-sig on the REFERENCE side only: here the job is to say what the logical
    # content is. The page gets the BOM. See the module docstring.
    with open(path, encoding='utf-8-sig') as fh:
        text = fh.read()
    m = ref()
    m.file = io.StringIO(text)
    m.parse()
    return [_norm(r) for r in m.data]


def _actual_records(csv_text):
    """Parse the PAGE's output with the reference's Bitwarden parser.

    Blank input is zero records, not an exception. `BitwardenCSV.parse()` raises
    TypeError on an empty string (csv.DictReader leaves `fieldnames` None and
    pass_import's checkheader does `in None`), and letting that escape cost this
    oracle a verdict during probe-the-oracle -- see PROBE FINDING 1 in README.md.
    Callers that need to distinguish 'no records' from 'not parseable' get the
    FormatError, which is raised for a non-empty body with the wrong header."""
    from pass_import.managers import BitwardenCSV
    if not csv_text or not csv_text.strip():
        return []
    m = BitwardenCSV()
    m.file = io.StringIO(csv_text)
    m.parse()
    return [_norm(r) for r in m.data]


def _norm(rec):
    """Compare on fields that actually carry data. A field empty on both sides is not
    evidence of anything, and including it would pad the comparison with agreement."""
    out = {}
    for k in CORE:
        v = rec.get(k)
        if v is None:
            continue
        v = str(v)
        if v == '':
            continue
        out[k] = v
    return out


def _multiset(records):
    from collections import Counter
    return Counter(tuple(sorted(r.items())) for r in records)


def _diff(expected, actual, limit=4):
    """A failure must name the offending item, not just the count."""
    e, a = _multiset(expected), _multiset(actual)
    missing, extra = (e - a), (a - e)
    parts = []
    for label, ms in (('MISSING (reference has, page lost)', missing),
                      ('EXTRA (page invented or mangled)', extra)):
        if ms:
            shown = list(ms.elements())[:limit]
            parts.append('%s x%d: %s%s' % (
                label, sum(ms.values()), '; '.join(repr(dict(s)) for s in shown),
                ' ...' if sum(ms.values()) > limit else ''))
    return ' | '.join(parts)


class Findings:
    """Each check is a named predicate that can independently flip the verdict.
    probe.py neuters every one in turn and fails if any of them changes no verdict --
    #014's lesson, that a predicate with no isolating control is decoration."""

    def __init__(self, disabled=()):
        self.rows = []
        self.disabled = set(disabled)

    def check(self, name, ok, detail=''):
        if name in self.disabled:
            self.rows.append((name, True, 'NEUTERED'))
            return True
        self.rows.append((name, bool(ok), detail))
        return bool(ok)

    @property
    def failed(self):
        return [r for r in self.rows if not r[1]]


def run(target, only=None, disabled=(), exclude=(), settle_ms=None, quiet=False):
    f = Findings(disabled)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return 'CANNOT-CERTIFY', f, 'playwright unavailable: %s' % exc

    manifest = json.load(open(os.path.join(FIXDIR, 'manifest.json')))
    if only:
        manifest = [m for m in manifest if m['file'] == only]
        if not manifest:
            return 'CANNOT-CERTIFY', f, 'no such fixture: %s' % only
    if exclude:
        dropped = [m['file'] for m in manifest if m['file'] in set(exclude)]
        manifest = [m for m in manifest if m['file'] not in set(exclude)]
        # NO SILENT CAPS. A reduced fixture set is recorded as a predicate in the run's
        # own output, so a verdict can never quietly mean less than it appears to.
        f.check('P0.subset', True, 'fixtures deliberately excluded: %s' % dropped)

    # P0: the oracle's own honesty checks. If these fail, nothing below means anything.
    for m in manifest:
        p = os.path.join(FIXDIR, m['file'])
        f.check('P0.exists[%s]' % m['file'], os.path.exists(p), 'fixture missing')
    bom_path = os.path.join(FIXDIR, 'chrome_bom.csv')
    if os.path.exists(bom_path):
        raw = open(bom_path, 'rb').read()
        f.check('P0.bytes', raw.startswith(b'\xef\xbb\xbf'),
                'chrome_bom.csv must actually start with a BOM or the fixture is decorative')

    url = target if target.startswith('http') else 'file://' + os.path.abspath(target)
    settle_fail = {'n': 0}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=['--no-sandbox'])
            try:
                for m in manifest:
                    # STRUCTURAL, and the most important line in this file.
                    #
                    # PROBE FINDING 2. Before this, ANY exception raised while handling
                    # ANY fixture aborted the loop and returned CANNOT-CERTIFY for the
                    # whole run. The effect during probe-the-oracle was that TEN of
                    # eleven negative controls came back CANNOT-CERTIFY instead of FAIL,
                    # so the probe could not tell "the oracle caught this defect" from
                    # "the oracle fell over" -- every red light was uninformative, and a
                    # weaker probe would have read them as catches and declared success.
                    #
                    # This is BOTTLENECKS #1's own lesson arriving one layer up again:
                    # "a fix that widens what an instrument observes widens what can
                    # wedge it" (#014). The scope of CANNOT-CERTIFY is therefore narrowed
                    # to what it actually means -- the oracle could not RUN AT ALL (no
                    # Playwright, no browser). A fixture that explodes is a FAIL of that
                    # fixture, named, with its traceback attached.
                    if settle_fail['n'] >= 2:
                        # EARLY ABORT, logged as a predicate rather than done silently.
                        # Two fixtures failing to settle establishes that the page does
                        # not settle; paying the timeout twelve more times proves nothing.
                        f.check('P0.aborted', True,
                                'stopped after 2 settle failures; remaining fixtures not '
                                'run: %s' % [x['file'] for x in manifest[manifest.index(m):]])
                        break
                    try:
                        _one(browser, url, m, f, settle_ms=settle_ms, settle_fail=settle_fail)
                    except Exception:
                        f.check('PX.oracle_error[%s]' % m['file'], False,
                                'the oracle itself raised while handling this fixture '
                                '(this is a FAIL of the fixture, never a blessing of the '
                                'page):\n%s' % traceback.format_exc())
            finally:
                browser.close()
    except Exception:
        # Reserved for "could not run": launch failure, missing browser binary.
        return 'CANNOT-CERTIFY', f, 'browser could not be launched:\n' + traceback.format_exc()

    verdict = 'FAIL' if f.failed else 'PASS'
    return verdict, f, ''


def _one(browser, url, m, f, settle_ms=None, settle_fail=None):
    """Drive ONE fixture through the real page in a real browser."""
    name = m['file']
    path = os.path.join(FIXDIR, name)
    expect = m['expect']
    timeout_ms = settle_ms or PER_FIXTURE_TIMEOUT_MS

    ctx = browser.new_context()
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.goto(url, wait_until='load', timeout=30000)

        # RAW BYTES. Not decoded, not BOM-stripped, not re-encoded. See the docstring.
        payload = open(path, 'rb').read()
        page.set_input_files('#src', {'name': name,
                                     'mimeType': 'text/csv',
                                     'buffer': payload})

        try:
            page.wait_for_function(
                "() => { const s = document.querySelector('#status');"
                "        return s && s.dataset && s.dataset.state; }",
                timeout=timeout_ms)
        except Exception:
            f.check('P1.settles[%s]' % name, False,
                    'no #status[data-state] within %dms -- page never settled '
                    '(hang, crash, or missing interface contract)' % timeout_ms)
            if settle_fail is not None:
                settle_fail['n'] += 1
            return
        f.check('P1.settles[%s]' % name, True)

        state = page.eval_on_selector('#status', 'e => e.dataset.state') or ''
        count_raw = page.eval_on_selector('#status', 'e => e.dataset.count')
        fmt_seen = page.eval_on_selector('#status', 'e => e.dataset.format') or ''
        out = page.eval_on_selector(
            '#out', "e => e.value !== undefined && e.value !== null ? e.value : e.textContent") or ''

        # An uncaught error DURING this fixture's conversion invalidates it. Scoped to
        # this page and this fixture: #014's other lesson is that widening what an
        # instrument observes widens what can wedge it, so an unrelated error elsewhere
        # must not fail a correct conversion.
        f.check('P2.noerror[%s]' % name, not errors,
                'uncaught page error during conversion: %s' % (errors[:2],))

        expected_state = {'convert': 'ok', 'empty': 'empty', 'refuse': 'refused'}[expect]
        f.check('P3.state[%s]' % name, state == expected_state,
                'expected data-state=%r, page said %r' % (expected_state, state))

        if expect == 'refuse':
            # A refusal is a CORRECT output. But it must be a refusal, not a silent
            # success with an empty result -- and it must emit nothing at all, because
            # a half-converted password file is worse than a refused one.
            f.check('P4.refuse_noout[%s]' % name, out.strip() == '',
                    'refused but still emitted %d chars of output' % len(out.strip()))
            f.check('P5.refuse_nofmt[%s]' % name, fmt_seen == '',
                    'refused but claimed to detect format %r' % fmt_seen)
            f.check('P6.refuse_zero[%s]' % name, str(count_raw) in ('0', 'None', ''),
                    'refused but reported data-count=%r' % count_raw)
            return

        ref = _reference_records(m['format'], path)

        f.check('P7.format[%s]' % name, fmt_seen == m['format'],
                'expected detected format %r, page said %r' % (m['format'], fmt_seen))

        try:
            count = int(count_raw)
        except (TypeError, ValueError):
            count = -1
        f.check('P8.count[%s]' % name, count == len(ref),
                'reference has %d records, page reported data-count=%r'
                % (len(ref), count_raw))

        if expect == 'empty':
            # Compute ONCE, then describe. Building the failure message by calling the
            # parser again is what crashed this oracle during probe-the-oracle: Python
            # evaluates a `%`-formatted detail argument eagerly, so the description ran
            # even when the condition short-circuited past it. PROBE FINDING 1.
            empty_recs = _actual_records(out)
            f.check('P9.empty_noout[%s]' % name, empty_recs == [],
                    'header-only input produced %d output records' % len(empty_recs))
            return

        # NON-VACUITY. Without this, a page that reports the right count and emits
        # nothing would satisfy a naive multiset comparison of [] against [] on an
        # empty reference. The reference here is never empty, and this pins it.
        f.check('P10.nonvacuous[%s]' % name, len(ref) > 0 and out.strip() != '',
                'reference n=%d, page output %d chars -- a convert fixture must produce '
                'records, and this predicate exists so that "matches" cannot mean "both '
                'empty"' % (len(ref), len(out.strip())))
        if not (len(ref) > 0 and out.strip() != ''):
            return

        try:
            actual = _actual_records(out)
        except Exception as exc:
            f.check('P11.parses[%s]' % name, False,
                    'page output is not valid Bitwarden CSV per the reference parser: '
                    '%s: %s' % (type(exc).__name__, exc))
            return
        f.check('P11.parses[%s]' % name, True)

        # THE BINDING PREDICATE. Everything above is a precondition on this one.
        same = _multiset(ref) == _multiset(actual)
        f.check('P12.differential[%s]' % name, same, _diff(ref, actual))
    finally:
        ctx.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target', help='page.html path or http(s) URL')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--fixture')
    ap.add_argument('--settle-timeout', type=int, default=None,
                    help='ms to wait for #status[data-state]; probe.py lowers this')
    ap.add_argument('--exclude', action='append', default=[],
                    help='skip a fixture by filename; recorded as P0.subset in the '
                         'output so a reduced run can never read as a full one')
    ap.add_argument('--neuter', action='append', default=[],
                    help='INTERNAL, used by probe.py clause (a) only')
    a = ap.parse_args()

    verdict, f, note = run(a.target, only=a.fixture, disabled=a.neuter,
                           exclude=a.exclude, settle_ms=a.settle_timeout)

    if a.json:
        print(json.dumps({'verdict': verdict, 'note': note,
                          'checks': [{'name': n, 'ok': o, 'detail': d} for n, o, d in f.rows]},
                         indent=1))
    else:
        for n, o, d in f.rows:
            if not o:
                print('  FAIL %-34s %s' % (n, d))
        npass = sum(1 for _, o, _ in f.rows if o)
        print('\n%d/%d predicates ok' % (npass, len(f.rows)))
        if note:
            print(note)
        print('VERDICT: %s' % verdict)

    sys.exit({'PASS': 0, 'FAIL': 1, 'CANNOT-CERTIFY': 2}[verdict])


if __name__ == '__main__':
    main()
