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

# Containers in which a <script> element does NOT execute, or in which the byte sequence
# "<script>" is not a script element at all. Added 2026-08-09 round-3 checker finding #1,
# which defeated the byte-equality contract by wrapping the *byte-identical* canonical
# snippet in <template> — oracle green, beacon provably inert in a real browser (verified
# by the checker in Chromium). Every entry is here for a reason:
#   template  — contents are an inert DocumentFragment; scripts never run
#   noscript  — with scripting enabled, contents are parsed as raw text, not elements
#   title, textarea, xmp, plaintext — escapable-raw-text/raw-text elements. Python's
#       html.parser only treats script/style as CDATA, so it will happily report a
#       "script element" inside <title> that a browser would see as literal text.
#   iframe, style — same class of mismatch.
# These all require an explicit end tag, which is why tracking them with a small stack is
# safe even though html.parser does no implied-end-tag handling (we deliberately do NOT
# track <p>, <li> and friends — that WOULD be re-implementing a tree builder).
INERT_ANCESTORS = ("template", "noscript", "title", "textarea", "xmp", "plaintext",
                   "iframe", "style")


class _ScriptExtractor(html.parser.HTMLParser):
    """Collect the raw text of every <script> element, in document order.

    Relies on HTMLParser's own CDATA handling — set_cdata_mode() is entered by the base
    class on a <script> start tag and only leaves it at the first `</script`. We never
    look for those boundaries ourselves; that is the whole point of the file.

    Also records, per script element, the inert-container ancestors open at the time it
    started. Boundaries still come from the tokenizer; this only reads the tag events it
    already emits.
    """

    def __init__(self):
        # convert_charrefs=False: entity folding would rewrite script text and make a
        # byte-for-byte comparison against the canonical snippet meaningless.
        super().__init__(convert_charrefs=False)
        self.bodies = []
        self.ancestors = []          # parallel to bodies: inert containers open at start
        self._open = False
        self._buf = []
        self._stack = []             # only INERT_ANCESTORS are tracked; see the note above

    def handle_starttag(self, tag, attrs):
        if tag in INERT_ANCESTORS and not self._open:
            self._stack.append(tag)
        if tag in CDATA_TAGS:
            if self._open:
                # Unreachable via the tokenizer (a nested <script> inside raw text is
                # data, not a tag) — kept as a loud tripwire in case that ever changes.
                raise AssertionError("tokenizer reported a nested <script> start tag")
            self._open = True
            self._buf = []
            self._script_ancestors = list(self._stack)

    def handle_startendtag(self, tag, attrs):
        # <script /> is NOT self-closing in HTML; the tokenizer treats it as a start tag.
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._open:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag in CDATA_TAGS and self._open:
            self.bodies.append("".join(self._buf))
            self.ancestors.append(getattr(self, "_script_ancestors", []))
            self._open = False
            self._buf = []
            return
        if tag in INERT_ANCESTORS and not self._open and tag in self._stack:
            # pop back to and including the most recent matching open
            while self._stack:
                if self._stack.pop() == tag:
                    break

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
        p.ancestors.append(list(getattr(p, "_script_ancestors", [])))
        errors.append("an opened <script> element is never closed — everything after it "
                      "is swallowed into its raw text")

    double = [i for i, b in enumerate(p.bodies) if "<!--" in b]
    if double:
        errors.append("script body/bodies %s contain '<!--' — script-data-escaped state; "
                      "a following '<script' would make the next '</script>' fail to close "
                      "the element (incident #008's original defect). Rejected conservatively."
                      % double)

    inert = [i for i, a in enumerate(p.ancestors) if a]
    if inert:
        errors.append("script element(s) %s sit inside inert container(s) %s — a browser "
                      "does not execute them (round-3 checker finding #1: a byte-identical "
                      "snippet wrapped in <template> is dead code that every text-level "
                      "check calls healthy)."
                      % (inert, sorted({t for a in p.ancestors for t in a})))

    return {
        "ok": not errors,
        "unclosed": unclosed,
        "double_escape": bool(double),
        "inert": inert,
        "bodies": p.bodies,
        "ancestors": p.ancestors,
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
    # (name, html, want_ok = structurally clean, want_n = script elements found,
    #  want_verify = verify_snippet() accepts it as ONE live canonical script element)
    ("clean page", _GOOD, True, 1, True),

    # ROUND-2 DEFECT #1: a stray unclosed <script> placed anywhere earlier absorbs the
    # real snippet. The old indexOf walker reported 93/93 on this. Structurally the page
    # is fine (one closed element, no comment vector) — what kills it is that the merged
    # body is not byte-equal to the canonical snippet. Structure alone can never catch it,
    # because case "legal mention" below proves `<script` inside script text is lawful.
    ("stray earlier unclosed <script>",
     "<html><body><script>// stray leftover open tag\n<script>%s</script></body></html>"
     % _SNIPPET_BODY, True, 1, False),

    # ROUND-1 FINDING #1, the original inert-beacon corruption: a fragment of the doc
    # file's HTML comment left unwrapped around the snippet.
    ("comment fragment captured into script",
     "<html><body><script>below immediately before </body>\n<!-- <script>%s</script></body></html>"
     % _SNIPPET_BODY, False, 1, False),

    # The double-escape vector on its own: canonical body IS present and live, but the
    # page carries the escape state, so the contract must still reject.
    ("double-escape state",
     "<html><body><script>var s = '<!--'; var t = '<script';</script>"
     "<script>%s</script></body></html>" % _SNIPPET_BODY, False, 2, False),

    # A page that merely MENTIONS <script> inside JS text is legal and must still pass —
    # public/002-gha-trigger/index.html really does this, and an early hand-rolled
    # oracle failed it. A verifier that cries wolf gets switched off.
    ("legal mention of the string <script> in JS",
     "<html><body><script>var help = 'paste a &lt;script&gt; tag'; // like <script> here\n"
     "</script><script>%s</script></body></html>" % _SNIPPET_BODY, True, 2, True),

    ("no scripts at all", "<html><body><p>nothing</p></body></html>", True, 0, False),

    # ROUND-3 CHECKER FINDING #1, verbatim reproduction. The snippet is BYTE-IDENTICAL;
    # only its container changed. The checker confirmed in Chromium that the wrapped page
    # never fires the beacon while the previous version of this file called it healthy.
    ("byte-identical snippet inside <template>",
     "<html><body><template><script>%s</script></template></body></html>"
     % _SNIPPET_BODY, False, 1, False),
    ("byte-identical snippet inside <noscript>",
     "<html><body><noscript><script>%s</script></noscript></body></html>"
     % _SNIPPET_BODY, False, 1, False),
    # <title> is escapable raw text: the tokenizer yields NO script element at all, so the
    # snippet is literal characters on screen. Structurally clean, contract must reject.
    ("byte-identical snippet inside <title>",
     "<html><head><title><script>%s</script></title></head><body></body></html>"
     % _SNIPPET_BODY, True, 0, False),

    # A live snippet must still pass when an inert container exists ELSEWHERE on the page,
    # or the rule is useless in practice.
    ("live snippet plus an unrelated <template> elsewhere",
     "<html><body><template><p>tpl</p></template><script>%s</script></body></html>"
     % _SNIPPET_BODY, True, 1, True),

    # Duplication is not "exactly one" — a shadowed copy must not read as live.
    ("snippet duplicated",
     "<html><body><script>%s</script><script>%s</script></body></html>"
     % (_SNIPPET_BODY, _SNIPPET_BODY), True, 2, False),

    # ROUND-3 FINDING #5: CRLF must NOT false-alarm.
    ("snippet with CRLF line endings",
     ("<html><body><script>%s</script></body></html>" % _SNIPPET_BODY).replace("\n", "\r\n"),
     True, 1, True),
]


def _norm(s):
    """CRLF -> LF only. Round-3 checker finding #5: a functionally identical copy with
    Windows line endings false-FAILed byte-equality. Normalising the line terminator on
    BOTH sides removes the false alarm without weakening anything — not one of incident
    #008's failure modes (comment capture, merged bodies, double-escape, inert container)
    is a line-ending difference."""
    return s.replace("\r\n", "\n").replace("\r", "\n")


def verify_bodies(text, expected_bodies):
    """THE CONTRACT. Is each body in `expected_bodies` present in `text` as its own LIVE
    script element — one that a browser would actually execute?

    Shared by both callers (the beacon oracle and lib/inline.js) so there is exactly one
    definition of "the inlined script really runs" in the repo instead of one per caller
    drifting apart. Returns (ok, errors).

    Three things must hold, and each exists because a checker demonstrated its absence:
      1. the document is structurally clean (scripts_of: closed, no comment-escape, and
         no script inside an inert container) — round-3 finding #1;
      2. the body is a script element's ENTIRE text, not a substring of a larger one.
         Byte-equality is load-bearing: comment capture, merged bodies and double-escape
         all present as a body that CONTAINS the target but is not EQUAL to it — round-1
         finding #1 and round-2 defect #1;
      3. exactly once, so a duplicated or shadowed copy is not mistaken for a live one.
    """
    r = scripts_of(text)
    errors = list(r["errors"])
    live = [_norm(b) for b, a in zip(r["bodies"], r["ancestors"]) if not a]
    for want in expected_bodies:
        w = _norm(want)
        exact = sum(1 for b in live if b == w)
        if exact != 1:
            contained = sum(1 for b in live if w.strip() and w.strip() in b and b != w)
            label = (w.strip()[:60] + "...") if len(w.strip()) > 60 else w.strip()
            errors.append(
                "expected body %r is a LIVE script element's ENTIRE text %d time(s), "
                "expected exactly 1" % (label, exact)
                + ("; it appears merged into %d larger script body/bodies — present as "
                   "text but NOT a live script element (inert-artifact failure)"
                   % contained if contained else ""))
    return (not errors), errors


def verify_snippet(text, canonical_body):
    """One-body convenience wrapper. Kept because the beacon oracle names one snippet."""
    return verify_bodies(text, [canonical_body])


def _selftest():
    """Every case is a defect a real checker demonstrated against this loop, plus the
    false-alarm cases that keep the verifier usable. Expectations are asserted against
    the PUBLIC api only — scripts_of() for structure, verify_snippet() for the contract —
    so the test cannot drift into re-implementing what it is testing."""
    failures = []
    for name, doc, want_ok, want_n, want_verify in _CASES:
        r = scripts_of(doc)
        if r["ok"] != want_ok:
            failures.append("%s: scripts_of ok=%s expected %s (%s)" % (name, r["ok"], want_ok, r["errors"]))
        if len(r["bodies"]) != want_n:
            failures.append("%s: %d script bodies, expected %d" % (name, len(r["bodies"]), want_n))
        ok, errs = verify_snippet(doc, _SNIPPET_BODY)
        if ok != want_verify:
            failures.append("%s: verify_snippet ok=%s expected %s (%s)" % (name, ok, want_verify, errs))

    for f in failures:
        print("SELFTEST FAIL: " + f, file=sys.stderr)
    print("html-scripts selftest: %d/%d cases clean" % (len(_CASES) - len({f.split(":")[0] for f in failures}), len(_CASES)))
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

    # --expect <bodies.json>: a JSON list of exact script bodies that must EACH be one
    # live script element. Round-3 checker finding #2: lib/inline.js called this module
    # without any expectation at all, so its "output verified" message meant only
    # "structurally parseable" — and a merged, never-executing module passed it.
    expect = None
    if "--expect" in argv:
        i = argv.index("--expect")
        with open(argv[i + 1], encoding="utf-8") as fh:
            expect = json.load(fh)
        if not isinstance(expect, list) or not all(isinstance(x, str) for x in expect):
            print("--expect file must contain a JSON list of strings", file=sys.stderr)
            return 2
        argv = argv[:i] + argv[i + 2:]

    if not argv:
        print("usage: html-scripts.py [--snippet <snippet.html>] [--expect <bodies.json>] "
              "<file.html> [...] | --selftest", file=sys.stderr)
        return 2
    out = []
    rc = 0
    for f in argv:
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        r = scripts_of(text)
        wanted = list(expect) if expect else []
        if canonical is not None:
            wanted.append(canonical)
        if wanted:
            ok, errs = verify_bodies(text, wanted)
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
