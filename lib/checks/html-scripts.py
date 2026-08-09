#!/usr/bin/env python3
"""lib/checks/html-scripts.py — extract <script> elements the way an HTML tokenizer does.

WHY THIS FILE EXISTS (BOTTLENECKS.md entry #1, incident #008, 2026-08-08):
  The beacon oracle hand-rolled a <script> boundary walker with indexOf() arithmetic.
  An independent checker defeated it in minutes: a stray unclosed <script> earlier in
  the page silently absorbs the beacon snippet into ONE broken script element, so the
  page ships an inert beacon while the oracle reports 93/93 green. The lesson recorded
  that day, verbatim: *do not hand-roll a parser for a language that has a spec-defined
  tokenizer.* This is that lesson, made executable and shared.

  It is deliberately Python: the standard library ships a tokenizer that implements the
  raw-text content model for <script> (html.parser.HTMLParser puts `script` in
  CDATA_CONTENT_ELEMENTS, so its content is delivered as raw text terminated only by the
  first `</script`, exactly as §13.2.5.14 requires). Node's stdlib has no HTML parser,
  and adding a dependency to a verifier is worse than crossing a process boundary.

KNOWN FIDELITY GAP, stated rather than hidden:
  html.parser does NOT implement the script-data-double-escaped states (§13.2.5.18-21),
  where `<!--` followed by `<script` inside script raw text makes the NEXT `</script>`
  fail to close the element — the exact mechanism of incident #008's original defect.
  So this module adds one explicit, conservative rule on top of the tokenizer: a script
  body containing `<!--` is REJECTED outright, whether or not a `<script` follows it.
  Over-rejection is the correct failure direction for a verifier — it can produce a
  false alarm, never a false green. A page that legitimately needs `<!--` inside script
  text must say so and change this rule deliberately.

USAGE
  as a CLI:     python3 lib/checks/html-scripts.py <file.html> [...]   -> JSON on stdout
  as a module:  from html_scripts import scripts_of ; scripts_of(text) -> Report
  self-test:    python3 lib/checks/html-scripts.py --selftest          -> exits 0/1

The JSON shape per file:
  {"file":..., "ok":bool, "unclosed":bool, "double_escape":bool,
   "bodies":[str,...], "errors":[str,...]}
"""

import html.parser
import json
import sys

CDATA_TAGS = ("script",)


class _ScriptExtractor(html.parser.HTMLParser):
    """Collect the raw text of every <script> element, in document order.

    Relies on HTMLParser's own CDATA handling — set_cdata_mode() is entered by the base
    class on a <script> start tag and only leaves it at the first `</script`. We never
    look for those boundaries ourselves; that is the whole point of the file.
    """

    def __init__(self):
        # convert_charrefs=False: entity folding would rewrite script text and make a
        # byte-for-byte comparison against the canonical snippet meaningless.
        super().__init__(convert_charrefs=False)
        self.bodies = []
        self._open = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag in CDATA_TAGS:
            if self._open:
                # Unreachable via the tokenizer (a nested <script> inside raw text is
                # data, not a tag) — kept as a loud tripwire in case that ever changes.
                raise AssertionError("tokenizer reported a nested <script> start tag")
            self._open = True
            self._buf = []

    def handle_startendtag(self, tag, attrs):
        # <script /> is NOT self-closing in HTML; the tokenizer treats it as a start tag.
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._open:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag in CDATA_TAGS and self._open:
            self.bodies.append("".join(self._buf))
            self._open = False
            self._buf = []

    @property
    def unclosed(self):
        return self._open


def scripts_of(text):
    """Return a report dict for one HTML document."""
    p = _ScriptExtractor()
    errors = []
    try:
        p.feed(text)
        p.close()
    except AssertionError as e:  # tripwire above
        errors.append(str(e))
    except Exception as e:  # a tokenizer crash is a FAIL, never a pass
        errors.append("tokenizer error: %s: %s" % (type(e).__name__, e))

    unclosed = p.unclosed
    if unclosed:
        # The trailing raw text belongs to an element that never closed. Keep it so a
        # caller can see WHAT got swallowed, but the report is not ok.
        p.bodies.append("".join(p._buf))
        errors.append("an opened <script> element is never closed — everything after it "
                      "is swallowed into its raw text")

    double = [i for i, b in enumerate(p.bodies) if "<!--" in b]
    if double:
        errors.append("script body/bodies %s contain '<!--' — script-data-escaped state; "
                      "a following '<script' would make the next '</script>' fail to close "
                      "the element (incident #008's original defect). Rejected conservatively."
                      % double)

    return {
        "ok": not errors,
        "unclosed": unclosed,
        "double_escape": bool(double),
        "bodies": p.bodies,
        "errors": errors,
    }


# --------------------------------------------------------------------------------------
# self-test — negative controls first. A verifier that has never been shown failing is
# not a verifier. Each case below is a real defect this module exists to catch, taken
# from the checker verdicts recorded in ledger.json for ship #008.
# --------------------------------------------------------------------------------------
_SNIPPET_BODY = "\n(function(){ /* beacon */ navigator.sendBeacon('/_b'); })();\n"
_GOOD = "<html><body><p>hi</p><script>%s</script></body></html>" % _SNIPPET_BODY

_CASES = [
    # (name, html, expect_ok, expect_body_count, must_contain_beacon_exactly_once)
    ("clean page", _GOOD, True, 1, True),

    # ROUND-2 DEFECT #1, verbatim reproduction: a stray unclosed <script> placed anywhere
    # earlier absorbs the real snippet. The old indexOf walker reported 93/93 on this.
    #
    # NOTE the expectation: ok=True. Structurally this page is fine — one closed script
    # element, no comment vector — and no amount of tokenizing can tell a merged body
    # from an intentional one, because case 5 below proves `<script` inside script text
    # is legal. What kills it is that the merged body is NOT byte-equal to the canonical
    # snippet, i.e. the caller's contract (verify_snippet), not the structure report.
    # The selftest still pins the defect: exactly 1 body, canonical present 0 times.
    ("stray earlier unclosed <script>",
     "<html><body><script>// stray leftover open tag\n<script>%s</script></body></html>"
     % _SNIPPET_BODY, True, 1, False),

    # ROUND-1 FINDING #1, the original inert-beacon corruption: a fragment of the doc
    # file's HTML comment left unwrapped around the snippet.
    ("comment fragment captured into script",
     "<html><body><script>below immediately before </body>\n<!-- <script>%s</script></body></html>"
     % _SNIPPET_BODY, False, 1, False),

    # The double-escape vector on its own.
    ("double-escape state",
     "<html><body><script>var s = '<!--'; var t = '<script';</script>"
     "<script>%s</script></body></html>" % _SNIPPET_BODY, False, 2, True),

    # A page that merely MENTIONS <script> inside JS text is legal and must still pass —
    # public/002-gha-trigger/index.html really does this, and an early hand-rolled
    # oracle failed it. A verifier that cries wolf gets switched off.
    ("legal mention of the string <script> in JS",
     "<html><body><script>var help = 'paste a &lt;script&gt; tag'; // like <script> here\n"
     "</script><script>%s</script></body></html>" % _SNIPPET_BODY, True, 2, True),

    ("no scripts at all", "<html><body><p>nothing</p></body></html>", True, 0, False),
]


def verify_snippet(text, canonical_body):
    """THE CONTRACT. Is `canonical_body` present in `text` as its own live script element?

    This is the predicate both callers share — the beacon oracle and lib/inline.js — so
    there is exactly one definition of "the inlined script really executes" in the repo
    instead of one per caller drifting apart. Returns (ok, errors).

    Byte-equality is load-bearing and not pedantry: every failure mode in incident #008
    (comment fragment captured, stray earlier <script> merging bodies, double-escape)
    presents as a script body that CONTAINS the snippet but is not EQUAL to it. Equality
    is the one test all three fail.
    """
    r = scripts_of(text)
    errors = list(r["errors"])
    exact = sum(1 for b in r["bodies"] if b == canonical_body)
    if exact != 1:
        contained = sum(1 for b in r["bodies"] if canonical_body.strip() and
                        canonical_body.strip() in b and b != canonical_body)
        errors.append(
            "the canonical body is a script element's ENTIRE text %d time(s), expected exactly 1"
            % exact
            + ("; it appears merged into %d larger script body/bodies — the snippet is "
               "present as text but is NOT a live script element (inert-beacon failure)"
               % contained if contained else ""))
    return (not errors), errors


def _selftest():
    failures = []
    for name, doc, want_ok, want_n, want_beacon in _CASES:
        # verify_snippet is ok iff the page is structurally clean AND the canonical body
        # is exactly one whole script element.
        want_verify = want_ok and want_beacon
        ok, errs = verify_snippet(doc, _SNIPPET_BODY)
        if ok != want_verify:
            failures.append("%s: verify_snippet ok=%s expected %s (%s)" % (name, ok, want_verify, errs))
        r = scripts_of(doc)
        if r["ok"] != want_ok:
            failures.append("%s: ok=%s expected %s (errors=%s)" % (name, r["ok"], want_ok, r["errors"]))
        if len(r["bodies"]) != want_n:
            failures.append("%s: %d script bodies, expected %d" % (name, len(r["bodies"]), want_n))
        exact = sum(1 for b in r["bodies"] if b == _SNIPPET_BODY)
        if want_beacon and exact != 1:
            failures.append("%s: canonical body appeared %d times, expected exactly 1" % (name, exact))
        if not want_beacon and exact != 0:
            failures.append("%s: canonical body survived intact (%d) but should not have" % (name, exact))

    for f in failures:
        print("SELFTEST FAIL: " + f, file=sys.stderr)
    print("html-scripts selftest: %d/%d cases clean" % (len(_CASES) - len(failures), len(_CASES)))
    return 1 if failures else 0


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    # --snippet <file>: also assert that the file's script BODY (the text between the
    # outer <script> and </script> of a one-element snippet file) is exactly one live
    # script element in each page. This is the mode the beacon oracle calls.
    canonical = None
    if "--snippet" in argv:
        i = argv.index("--snippet")
        with open(argv[i + 1], encoding="utf-8") as fh:
            snip = fh.read().strip()
        srep = scripts_of(snip)
        if len(srep["bodies"]) != 1 or not srep["ok"]:
            print("snippet file is not exactly one clean script element: %s" % srep["errors"],
                  file=sys.stderr)
            return 2
        canonical = srep["bodies"][0]
        argv = argv[:i] + argv[i + 2:]

    if not argv:
        print("usage: html-scripts.py [--snippet <snippet.html>] <file.html> [...] | --selftest",
              file=sys.stderr)
        return 2
    out = []
    rc = 0
    for f in argv:
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        r = scripts_of(text)
        if canonical is not None:
            ok, errs = verify_snippet(text, canonical)
            r["ok"] = ok
            r["errors"] = errs
        r["file"] = f
        if not r["ok"]:
            rc = 1
        out.append(r)
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
