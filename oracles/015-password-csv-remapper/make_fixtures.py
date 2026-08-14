#!/usr/bin/env python3
"""Generate the oracle's real dataset. Committed output, reproducible input.

WHY A GENERATOR AND NOT HAND-WRITTEN FILES: every fixture below states, in code, the
exact bytes it is testing. Hand-written CSV fixtures rot silently -- an editor eats a
BOM, normalises CRLF, or trims a trailing space, and the fixture stops testing the thing
it was named for while still passing. Generating them makes the intent inspectable and
the bytes exact. Run: python3 make_fixtures.py

The four supported source formats' column names are NOT invented here. They are read off
pass_import's own manager classes (the reference implementation) at generation time, so a
fixture cannot drift from what the reference expects:

    ChromeCSV       {'title':'name','password':'password','login':'username','url':'url','comments':'note'}
    BitwardenCSV    {'title':'name','password':'login_password','login':'login_username',
                     'url':'login_uri','comments':'notes','group':'folder','otpauth':'login_totp'}
    LastpassCSV     {'title':'name','password':'password','login':'username','url':'url',
                     'comments':'extra','group':'grouping'}
    OnePassword8CSV {'title':'Title','url':'Url','login':'Username','password':'Password',
                     'otpauth':'OTPAuth','favorite':'Favorite','archived':'Archived',
                     'tags':'Tags','comments':'Notes'}
"""
import csv
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, 'fixtures')

# The adversarial payload every format fixture carries. Each field is here because a
# naive hand-rolled CSV splitter gets it wrong in a specific, nameable way.
HARD_ROWS = [
    # title,            login,             password,                 url,                      comments
    ('GitHub',          'me@example.com',  'p,a"ss w0rd',            'https://github.com',     'comma and quote in password'),
    ('Bank of Nowhere', 'user1',           'line1\nline2',           'https://bank.example',   'embedded newline in password'),
    ('Unicode Ünïcødé', 'ü@example.com',   'påsswörd nbsp',     'https://xn--80ak6aa92e.com', 'unicode + nbsp'),
    ('Trailing space  ', ' leading',       '  spaces  ',             'https://sp.example',     'whitespace must be preserved verbatim'),
    ('Empty password',  'nopass@x.com',    '',                       'https://empty.example',  'empty password is a real row, not a skip'),
    ('Semicolon;delim', 'semi',            'a;b;c',                  'https://semi.example',   'semicolons must NOT be treated as delimiters'),
    ('=cmd|calc',       'csvinj',          '@SUM(1+1)',              'https://inj.example',    'formula-injection shapes stay literal text'),

    # ---- rows with EMPTY optional fields, added by PROBE FINDING 6 ------------------
    # Every row above carries a non-empty value in every column. That uniformity made a
    # whole class of defect invisible: clause (b)'s `b1_inject_extra_field` mutation --
    # which writes a bogus `notes` value into any row that has none -- PASSED the oracle,
    # not because the oracle was tolerant but because NO FIXTURE HAD AN EMPTY NOTES
    # FIELD, so the mutation never executed. A fixture that cannot reach the code it
    # exists to test is decoration (BOTTLENECKS #1, #014). These two rows are the fix:
    # they leave optional fields genuinely empty, so invention is detectable.
    ('No notes no url',  'sparse@example.com', 'sparsepass',          '',                       ''),
    ('Title and pw only', '',                  'onlypass',            '',                       ''),
]


def _write(name, text, newline=''):
    path = os.path.join(FIX, name)
    with open(path, 'w', encoding='utf-8', newline=newline) as f:
        f.write(text)
    return path


def _csv(headers, rows, crlf=False, bom=False):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\r\n' if crlf else '\n')
    w.writerow(headers)
    for r in rows:
        w.writerow(r)
    out = buf.getvalue()
    return ('﻿' + out) if bom else out


def build():
    os.makedirs(FIX, exist_ok=True)
    manifest = []

    def add(name, text, fmt, expect, note, newline=''):
        _write(name, text, newline=newline)
        manifest.append({'file': name, 'format': fmt, 'expect': expect, 'note': note})

    # ---- the four supported source formats, each carrying the same hard rows ----
    add('chrome_hard.csv',
        _csv(['name', 'url', 'username', 'password', 'note'],
             [(t, u, l, p, c) for (t, l, p, u, c) in HARD_ROWS]),
        'chrome', 'convert',
        'Chrome/Chromium export with every adversarial field shape.')

    add('bitwarden_hard.csv',
        _csv(['folder', 'favorite', 'type', 'name', 'notes', 'fields',
              'login_uri', 'login_username', 'login_password', 'login_totp'],
             [('', '', 'login', t, c, '', u, l, p, '') for (t, l, p, u, c) in HARD_ROWS]),
        'bitwarden', 'convert',
        'Bitwarden export re-imported to Bitwarden: the identity case. Any mangling here '
        'is unambiguous, because input and output share a schema.')

    add('lastpass_hard.csv',
        _csv(['url', 'username', 'password', 'totp', 'extra', 'name', 'grouping', 'fav'],
             [(u, l, p, '', c, t, '', '0') for (t, l, p, u, c) in HARD_ROWS]),
        'lastpass', 'convert',
        'LastPass export. Note `extra` is the notes column and `name` is NOT first.')

    add('onepassword_hard.csv',
        _csv(['Title', 'Url', 'Username', 'Password', 'OTPAuth', 'Favorite', 'Archived', 'Tags', 'Notes'],
             [(t, u, l, p, '', '', '', '', c) for (t, l, p, u, c) in HARD_ROWS]),
        'onepassword', 'convert',
        '1Password 8 export. Capitalised headers: a case-sensitive matcher fails this.')

    # ---- byte-level variants of the SAME logical content -------------------------
    # These exist because "it worked on my file" is the failure mode. The converted
    # records must be identical to chrome_hard.csv's; only the bytes differ.
    add('chrome_crlf.csv',
        _csv(['name', 'url', 'username', 'password', 'note'],
             [(t, u, l, p, c) for (t, l, p, u, c) in HARD_ROWS], crlf=True),
        'chrome', 'convert',
        'CRLF line endings (a Windows export). Must parse identically to chrome_hard.',
        newline='')

    add('chrome_bom.csv',
        _csv(['name', 'url', 'username', 'password', 'note'],
             [(t, u, l, p, c) for (t, l, p, u, c) in HARD_ROWS], bom=True),
        'chrome', 'convert',
        'UTF-8 BOM. A BOM glued to the first header breaks naive header matching, so the '
        'format is silently mis-detected or the first column is lost.')

    # ---- the empty / degenerate family ------------------------------------------
    # Expect `empty`, NOT `convert`: the page must say "0 entries" explicitly. An oracle
    # that accepted silence here would let a page that does nothing at all pass.
    add('chrome_header_only.csv',
        _csv(['name', 'url', 'username', 'password', 'note'], []),
        'chrome', 'empty',
        'Valid header, zero rows. Must report 0 entries explicitly, not fail and not '
        'silently emit a header-only file as if it had worked.')

    add('truly_empty.csv', '', None, 'refuse',
        'Zero bytes. No format can be detected, so this must be a named refusal.')

    add('whitespace_only.csv', '\n\n   \n\n', None, 'refuse',
        'Only blank lines. Must refuse, not crash and not report a phantom entry.')

    # ---- the refusal family: the tail is closed BY CONSTRUCTION ------------------
    # Ship 015 supports exactly four formats. Everything else is refused BY NAME.
    # A refusal is a correct output. These fixtures are what makes that claim testable.
    add('keepass_unsupported.csv',
        _csv(['Group', 'Title', 'Username', 'Password', 'URL', 'Notes'],
             [('Root', t, l, p, u, c) for (t, l, p, u, c) in HARD_ROWS]),
        None, 'refuse',
        'KeePass export -- a REAL fifth format, deliberately unsupported. The page must '
        'refuse by name and emit NO output. If a checker finds this mishandled the answer '
        'is a better refusal, never a fifth parser.')

    add('not_a_csv.csv',
        '{"this": "is json", "not": ["a", "csv"]}\n',
        None, 'refuse',
        'JSON with a .csv extension. Extension is not a format check.')

    add('headers_but_no_match.csv',
        _csv(['alpha', 'beta', 'gamma'], [('1', '2', '3')]),
        None, 'refuse',
        'Well-formed CSV whose headers match no supported format. Must refuse rather than '
        'guess a mapping -- a wrong guess on a password file is the worst outcome here.')

    # ---- scale ------------------------------------------------------------------
    add('chrome_5k.csv',
        _csv(['name', 'url', 'username', 'password', 'note'],
             [('Entry %d' % i, 'https://e%d.example' % i, 'u%d' % i, 'p,%d"x' % i, 'n%d' % i)
              for i in range(5000)]),
        'chrome', 'convert',
        '5000 rows. Guards against a page that works on 7 rows and wedges the browser on '
        'a real export.')

    with open(os.path.join(FIX, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=1)

    total = 0
    for m in manifest:
        n = os.path.getsize(os.path.join(FIX, m['file']))
        total += n
        print('%-28s %-12s %-8s %7d bytes' % (m['file'], m['format'] or '-', m['expect'], n))
    print('\n%d fixtures, %d bytes total' % (len(manifest), total))
    print('expect=convert: %d  empty: %d  refuse: %d' % (
        sum(1 for m in manifest if m['expect'] == 'convert'),
        sum(1 for m in manifest if m['expect'] == 'empty'),
        sum(1 for m in manifest if m['expect'] == 'refuse')))


if __name__ == '__main__':
    build()
