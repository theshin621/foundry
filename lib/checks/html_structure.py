#!/usr/bin/env python3
"""lib/checks/html_structure.py — structural facts about an HTML page, from a real tokenizer.

WHY THIS EXISTS
===============
BOTTLENECKS.md entry #1, incident #4 (2026-08-08, ship 008 beacon-firstparty). The beacon was
inert on all five pages while every page returned HTTP 200 and the oracle read 53/53 green. The
one permitted fix cycle hardened the oracle with a hand-rolled `<script>` boundary walker
(`indexOf('<script')` / `indexOf('</script>')` index arithmetic). The round-2 checker falsified
the hardened walker in minutes: a stray unclosed `<script>` earlier in the page desynchronised the
index walk and reproduced the ORIGINAL failure — inert beacon, oracle green, 93/93.

The lesson recorded in BOTTLENECKS #1 is narrow and this module is its implementation:

    do not hand-roll a parser for a language that has a spec-defined tokenizer.

This is the borrow-don't-build rule (Amendment 2026-08-02b) applied to verification code rather
than to product code — the first time entry #1's pattern showed up inside the checker itself.

THE SECOND LESSON — the one the first fix missed
================================================
Swapping in a real tokenizer is necessary but NOT sufficient, and believing otherwise is how a
fix grows a sibling. Python's `html.parser` is a real tokenizer and it is correct on every close
variant that bit the walker, but it is **not** a full HTML5 tokenizer. It diverges from the spec
in one place that matters here: the **script-data-double-escaped state**.

Per the HTML5 tokenizer, inside script raw text the sequence `<!--` followed by `<script` +
[whitespace `/` `>`] enters the double-escaped state, in which the next `</script>` does **not**
close the element. `html.parser` closes it anyway. MEASURED 2026-08-09 in this container:

    input : <script>var s="<!--<script>";</script><b>after</b>
    spec  : script is UNCLOSED to EOF; <b> is inert script text
    html.parser: script closed at </script>; <b> is a real element

Both readings cannot be right, and a checker that silently picks one is exactly the class of
instrument that went green on an inert beacon.

So this module has THREE verdicts, not two:

    PASS            — the tokenizer's reading is trustworthy and the assertions hold
    FAIL            — the tokenizer's reading is trustworthy and an assertion is violated
    CANNOT-CERTIFY  — the page contains a construct where this tokenizer's reading is known
                      to diverge from a browser's, so no verdict is offered at all

**A verification tool must be able to say "this is beyond me."** An oracle with only PASS and FAIL
is forced to guess on the inputs it understands least, and it will guess green — which is the
failure this whole file exists to prevent. CANNOT-CERTIFY is not a weakness of this module; it is
the feature that stops entry #1 from regenerating one layer down.

PRESENT IS NOT EXECUTED (the finding that failed round 1, 2026-08-09)
=====================================================================
The first version of this module asked only "is the needle inside a `<script>` element?" An
independent checker refuted it in one pass: `<script type="application/json">BEACON()</script>`
returned PASS, and a browser never executes it. That is ship 008's failure reproduced inside its
own replacement — markup present, code inert, oracle green — reached by a mechanism the tokenizer
question cannot see. Three such mechanisms are now modelled explicitly:

  * **`type` / `nomodule`** — a script block executes only when `type` is absent, empty, `module`,
    or a JavaScript MIME type (the closed list in `_JS_MIME_TYPES`). `application/json`,
    `application/ld+json`, `text/template`, `importmap`, `speculationrules` are inert DATA BLOCKS.
    `nomodule` is skipped by every module-capable browser.
  * **`<template>` / `<noscript>`** — contents never execute: a template's children live in an
    inert DocumentFragment, and with scripting enabled a browser tokenizes `<noscript>` contents
    as raw text so the nested element is never instantiated at all.
  * **`<iframe srcdoc>`** — a nested document this module does not parse; a needle found only
    there is reported as such rather than silently counted or silently missed.

So `assert_inline_contains` reports three distinguishable outcomes — absent, present-but-inert
(naming the reason), and satisfied — because "the beacon is on the page" was exactly the true
statement that made ship 008's oracle read green.

Note that this fix does NOT reopen BOTTLENECKS #1's long-tail pattern. The JS MIME list and the
inert-container pair are **closed enumerations from the spec**, not a growing pile of special
cases; there is no next sibling to discover because the set is finite and written down.

DELIBERATE IMPRECISION (declared, so a checker disputes it rather than discovers it)
===================================================================================
The double-escape detector is CONSERVATIVE and knowingly over-refuses. It flags a script body
whenever a double-escape-opening `<script` appears between `<!--` and `-->`. But per spec a `-->`
returns the tokenizer from the double-escaped state to plain script data, so a body like

    <script>/* <!-- <script> --> */ BEACON()</script>

does in fact close at its `</script>` and a perfectly precise oracle would return PASS. This
module returns CANNOT-CERTIFY.

That is the intended trade and the reasoning is the whole point of the file: computing the exit
transition precisely means implementing the script-data-escaped / double-escaped / dash /
dash-dash state machine **by hand** — which is the exact move BOTTLENECKS #1 says not to make, and
which is how the previous fix grew a sibling. Given a choice between over-refusing and hand-rolling
a state machine, this module over-refuses. Refusing to bless a page is recoverable; blessing a page
whose structure we misread is the failure that started all of this.

Measured cost of the conservatism, 2026-08-09, on the whole real corpus (`public/index.html`,
`public/002-gha-trigger/`, `public/004-khanya-school-tutor/`, `public/005-maccleaner/`,
`public/dashboard/`, `lib/template.html`): **0 false CANNOT-CERTIFY — all six certify cleanly.**
The conservatism is free today. If a real page ever trips it, the fix is to change that page, not
to make this detector cleverer.

Stdlib only. No network. Cold-executable. Exit codes: 0 PASS · 1 FAIL · 2 CANNOT-CERTIFY.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List, Optional

PASS = "PASS"
FAIL = "FAIL"
CANNOT_CERTIFY = "CANNOT-CERTIFY"

EXIT = {PASS: 0, FAIL: 1, CANNOT_CERTIFY: 2}

# The spec trigger for script-data-double-escaped: `<!--` ... `<script` followed by one of
# TAB LF FF SPACE `/` `>`. Bare `<script` at EOF cannot trigger it (needs the terminator).
_DOUBLE_ESCAPE_OPEN = re.compile(r"<script[\t\n\f />]", re.IGNORECASE)

# HTML spec, "scripting" §4.12.1: a script block is a CLASSIC script only if its `type` is
# absent, the empty string, or an ASCII case-insensitive match for a JavaScript MIME type
# essence (leading/trailing ASCII whitespace stripped). Anything else — application/json,
# application/ld+json, text/template, importmap, speculationrules — is a DATA BLOCK that the
# browser never executes. This list is CLOSED and finite, which is why implementing it does not
# reopen BOTTLENECKS #1: there is no long tail here, only an enumeration.
_JS_MIME_TYPES = frozenset(
    {
        "application/ecmascript",
        "application/javascript",
        "application/x-ecmascript",
        "application/x-javascript",
        "text/ecmascript",
        "text/javascript",
        "text/javascript1.0",
        "text/javascript1.1",
        "text/javascript1.2",
        "text/javascript1.3",
        "text/javascript1.4",
        "text/javascript1.5",
        "text/jscript",
        "text/livescript",
        "text/x-ecmascript",
        "text/x-javascript",
    }
)

# Elements whose contents a browser never executes as script:
#   <template> — contents live in an inert DocumentFragment (§4.12.3); a nested <script> is
#                not executed unless other JS clones it into the document.
#   <noscript> — with scripting ENABLED (the normal case) the parser treats the contents as
#                raw text (§4.12.2), so a nested <script> is never instantiated at all.
_INERT_CONTAINERS = frozenset({"template", "noscript"})


@dataclass
class ScriptEl:
    """One script element as the tokenizer saw it."""

    line: int
    attrs: dict
    body: str = ""
    closed: bool = False
    inert_reason: Optional[str] = None  # set => present in the markup but never executed

    @property
    def is_external(self) -> bool:
        return "src" in self.attrs

    @property
    def executes(self) -> bool:
        """True only if a browser would run this element's body as live JavaScript."""
        return self.inert_reason is None and not self.is_external


def _classify_type(attrs: dict) -> Optional[str]:
    """Return an inert-reason string if the type/nomodule attributes stop this element from
    executing as a classic or module script, else None."""
    if "nomodule" in attrs:
        # Skipped by every browser that supports modules, i.e. every modern browser.
        return "has the `nomodule` attribute; module-capable browsers skip it"
    raw = attrs.get("type")
    if raw is None:
        return None
    t = raw.strip().lower()
    if t == "" or t in _JS_MIME_TYPES:
        return None
    if t == "module":
        return None  # a module script; it does execute
    return f'type={raw!r} is not a JavaScript MIME type — the browser treats this as an inert data block'


@dataclass
class Uncertainty:
    code: str
    line: int
    detail: str

    def __str__(self) -> str:
        return f"line {self.line}: [{self.code}] {self.detail}"


@dataclass
class Report:
    scripts: List[ScriptEl] = field(default_factory=list)
    uncertainties: List[Uncertainty] = field(default_factory=list)
    unclosed_script_line: Optional[int] = None
    parse_errors: List[str] = field(default_factory=list)
    srcdoc_values: List[tuple] = field(default_factory=list)

    @property
    def certain(self) -> bool:
        return not self.uncertainties

    def inline_bodies(self) -> List[str]:
        """Bodies of inline scripts a browser actually EXECUTES. Deliberately excludes inert
        data blocks and anything inside <template>/<noscript> — ship 008 failed because the
        beacon was present in the markup and inert, and an oracle that cannot tell those apart
        reproduces that failure."""
        return [s.body for s in self.scripts if s.executes]

    def inert_bodies(self) -> List[ScriptEl]:
        return [s for s in self.scripts if s.inert_reason is not None]


class _Collector(HTMLParser):
    """Collects script elements. Relies on html.parser's CDATA (raw-text) handling for
    script bodies — that is the whole point: the tokenizer decides where a script ends,
    not index arithmetic in this file."""

    def __init__(self) -> None:
        # convert_charrefs=False keeps script bodies byte-faithful. Charrefs are not
        # decoded inside CDATA elements either way; this just removes the question.
        super().__init__(convert_charrefs=False)
        self.report = Report()
        self._open: Optional[ScriptEl] = None
        self._inert_depth: List[str] = []  # stack of open <template>/<noscript>
        self.srcdoc_values: List[tuple] = []  # (line, value) for iframe srcdoc

    def _inert_container_reason(self) -> Optional[str]:
        if not self._inert_depth:
            return None
        tag = self._inert_depth[-1]
        if tag == "template":
            return "inside <template>; contents are an inert DocumentFragment and never execute"
        return "inside <noscript>; with scripting enabled the contents are raw text and never execute"

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "iframe" and "srcdoc" in d:
            self.srcdoc_values.append((self.getpos()[0], d["srcdoc"] or ""))
        if tag in _INERT_CONTAINERS:
            self._inert_depth.append(tag)
            return
        if tag == "script":
            if self._open is not None:
                # html.parser does not nest CDATA elements; if this ever fires the input
                # is outside the model this module claims to understand.
                self.report.uncertainties.append(
                    Uncertainty(
                        "NESTED_SCRIPT_START",
                        self.getpos()[0],
                        "a <script> start tag was reported while another script was still open",
                    )
                )
            el = ScriptEl(line=self.getpos()[0], attrs=d)
            el.inert_reason = self._inert_container_reason() or _classify_type(d)
            self._open = el
            self.report.scripts.append(el)

    def handle_startendtag(self, tag, attrs):
        # `<script/>` is NOT self-closing in HTML (foreign content aside). A browser treats
        # it as an open start tag; html.parser reports it here. Refuse to certify.
        if tag == "script":
            self.report.uncertainties.append(
                Uncertainty(
                    "SELF_CLOSING_SCRIPT",
                    self.getpos()[0],
                    "<script/> is not self-closing in HTML; a browser keeps the element open "
                    "while this tokenizer closes it",
                )
            )
            el = ScriptEl(line=self.getpos()[0], attrs=dict(attrs), closed=True)
            el.inert_reason = self._inert_container_reason() or _classify_type(dict(attrs))
            self.report.scripts.append(el)
            return
        # HTMLParser's default handle_startendtag delegates to start+end; this class overrides
        # the method, so the delegation must be restored explicitly or every self-closing tag
        # (notably `<iframe srcdoc=... />`) would be invisible to the trackers above.
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in _INERT_CONTAINERS:
            if self._inert_depth and self._inert_depth[-1] == tag:
                self._inert_depth.pop()
            elif tag in self._inert_depth:
                # crossed nesting, e.g. <template><noscript></template></noscript>
                while self._inert_depth and self._inert_depth.pop() != tag:
                    pass
            return
        if tag == "script" and self._open is not None:
            self._open.closed = True
            self._open = None

    def handle_data(self, data):
        if self._open is not None:
            self._open.body += data

    def close(self):
        super().close()
        if self._open is not None:
            self.report.unclosed_script_line = self._open.line


def analyze(html: str) -> Report:
    """Tokenize `html` and return structural facts plus any reasons we cannot certify it."""
    p = _Collector()
    try:
        p.feed(html)
        p.close()
    except Exception as exc:  # a tokenizer crash is itself a refusal to certify
        p.report.parse_errors.append(f"{type(exc).__name__}: {exc}")
        p.report.uncertainties.append(
            Uncertainty("TOKENIZER_ERROR", 0, f"parser raised {type(exc).__name__}")
        )
        return p.report

    rep = p.report
    rep.srcdoc_values = p.srcdoc_values

    if p._inert_depth:
        rep.uncertainties.append(
            Uncertainty(
                "UNCLOSED_INERT_CONTAINER",
                0,
                f"document ends with {p._inert_depth!r} still open; which scripts are inert "
                "cannot be determined",
            )
        )

    # THE KNOWN DIVERGENCE. If a script body contains `<!--` and, after it and before any
    # `-->`, a double-escape-opening `<script` — then per spec the element continues past the
    # `</script>` this tokenizer honoured. The trigger necessarily appears BEFORE the point of
    # divergence, so it is always inside the (possibly truncated) body we were handed; checking
    # the body is sound even though the body itself may be short.
    for s in rep.scripts:
        i = s.body.find("<!--")
        while i != -1:
            end = s.body.find("-->", i)
            region = s.body[i:] if end == -1 else s.body[i:end]
            if _DOUBLE_ESCAPE_OPEN.search(region):
                rep.uncertainties.append(
                    Uncertainty(
                        "SCRIPT_DOUBLE_ESCAPE",
                        s.line,
                        "script body enters the HTML5 script-data-double-escaped state "
                        "(`<!--` then `<script`); html.parser and a browser disagree about "
                        "where this element ends",
                    )
                )
                break
            i = s.body.find("<!--", i + 4)

    return rep


# ---------------------------------------------------------------------------------------------
# Assertions built on top of the facts. Each returns a list of failure strings.
# ---------------------------------------------------------------------------------------------


def assert_all_scripts_closed(rep: Report) -> List[str]:
    if rep.unclosed_script_line is not None:
        return [f"unclosed <script> element opened at line {rep.unclosed_script_line}"]
    return []


def assert_inline_contains(rep: Report, needle: str) -> List[str]:
    """The needle must appear inside the BODY of an inline script — i.e. as executable code,
    not as inert page text. This is the assertion the beacon oracle actually needed: ship 008
    failed because the beacon text was PRESENT on the page and INERT."""
    if any(needle in b for b in rep.inline_bodies()):
        return []

    # Distinguish ABSENT from PRESENT-BUT-INERT. This distinction is the entire lesson of
    # ship 008: the beacon markup was on all five pages and executed on none of them.
    for s in rep.inert_bodies():
        if needle in s.body:
            return [
                f"{needle!r} is PRESENT at line {s.line} but INERT — {s.inert_reason}. "
                "The markup is on the page; the browser never runs it."
            ]
    for s in rep.scripts:
        if s.is_external and needle in (s.attrs.get("src") or ""):
            return [
                f"{needle!r} appears only in the src of an external script at line {s.line}; "
                "this checker cannot see external script contents"
            ]
    for line, val in rep.srcdoc_values:
        if needle in val:
            return [
                f"{needle!r} appears only inside an <iframe srcdoc> at line {line}; that is a "
                "nested document this checker does not parse"
            ]
    return [f"{needle!r} does not appear in any executing inline <script> body"]


def assert_inline_absent(rep: Report, needle: str) -> List[str]:
    """Mirror of the above. NOTE the deliberate asymmetry: `require` counts only EXECUTING
    scripts, while `forbid` counts every inline script including inert ones. Both directions
    therefore fail safe — you cannot satisfy a requirement with dead markup, and you cannot
    hide a forbidden string by parking it in a data block that some later change might
    re-activate."""
    hits = [s.line for s in rep.scripts if not s.is_external and needle in s.body]
    return [f"{needle!r} appears in an inline <script> body at line {ln}" for ln in hits]


def verdict(rep: Report, failures: List[str]) -> str:
    """Uncertainty dominates. A page we cannot read correctly gets no PASS and no FAIL —
    reporting FAIL would be as much a guess as reporting PASS."""
    if not rep.certain:
        return CANNOT_CERTIFY
    return FAIL if failures else PASS


# ---------------------------------------------------------------------------------------------
# Self-test corpus. Cases D/P are the ones that killed the hand-rolled walker.
# ---------------------------------------------------------------------------------------------

_CORPUS = [
    # (name, html, expected_verdict, require_inline_needle_or_None)
    ("plain script closed", "<p>x</p><script>BEACON()</script>", PASS, "BEACON"),
    ("markup inside script body", '<script>var s="</div><p>";BEACON()</script>', PASS, "BEACON"),
    ("literal <script> in a JS string", '<script>var s="<script>";BEACON()</script>', PASS, "BEACON"),
    ("close tag with trailing space", "<script>BEACON()</script >", PASS, "BEACON"),
    ("uppercase close tag", "<script>BEACON()</SCRIPT>", PASS, "BEACON"),
    ("newline inside close tag", "<script>BEACON()</script\n>", PASS, "BEACON"),
    ("mixed-case tags", "<ScRiPt>BEACON()</ScRiPt>", PASS, "BEACON"),
    ("gt inside quoted attribute", '<script data-x="a>b">BEACON()</script>', PASS, "BEACON"),
    ("comment containing a script element", "<!-- <script>evil()</script> --><script>BEACON()</script>", PASS, "BEACON"),
    ("stray unclosed script earlier — THE WALKER KILLER",
     "<script>\n// <script>\n</script><script>BEACON()</script>", PASS, "BEACON"),
    # the beacon-008 failure itself: text present, not executable
    ("beacon present but INERT as page text", "<p>BEACON()</p><script>var a=1;</script>", FAIL, "BEACON"),
    ("external script does not satisfy inline", '<script src="b.js"></script>', FAIL, "BEACON"),
    ("unclosed script at EOF", "<p>a</p><script>BEACON()", FAIL, "BEACON"),
    # the divergence — must refuse, not guess
    ("double-escaped state", '<script>var s="<!--<script>";</script><b>after</b>', CANNOT_CERTIFY, "BEACON"),
    # DECLARED OVER-REFUSAL — see "Deliberate imprecision" in the module docstring. Per spec a
    # `-->` returns the tokenizer from double-escaped to plain script data, so this element does
    # close at its `</script>` and a perfectly precise oracle would say PASS. This module says
    # CANNOT-CERTIFY instead, on purpose. The expectation below records the conservative answer as
    # INTENDED behaviour, not as an accommodation to the implementation.
    ("double-escape exited by --> (declared over-refusal)",
     "<script>/* <!-- <script> --> */BEACON()</script>", CANNOT_CERTIFY, "BEACON"),
    ("plain <!-- in script is fine", "<script>/* <!-- */ BEACON()</script>", PASS, "BEACON"),
    ("self-closing script tag", '<script src="x.js"/><script>BEACON()</script>', CANNOT_CERTIFY, "BEACON"),
    # --- added 2026-08-09 after checker FAIL: present-but-inert, the ship-008 shape, via
    # --- mechanisms the first version of this module could not see at all.
    ("type=application/json is a data block", '<script type="application/json">BEACON()</script>', FAIL, "BEACON"),
    ("type=application/ld+json is a data block", '<script type="application/ld+json">BEACON()</script>', FAIL, "BEACON"),
    ("type=text/template is a data block", '<script type="text/template">BEACON()</script>', FAIL, "BEACON"),
    ("type=importmap is a data block", '<script type="importmap">BEACON()</script>', FAIL, "BEACON"),
    ("type=speculationrules is a data block", '<script type="speculationrules">BEACON()</script>', FAIL, "BEACON"),
    ("nomodule is skipped by modern browsers", "<script nomodule>BEACON()</script>", FAIL, "BEACON"),
    ("inside <template> is inert", "<template><script>BEACON()</script></template>", FAIL, "BEACON"),
    ("inside <noscript> is inert", "<noscript><script>BEACON()</script></noscript>", FAIL, "BEACON"),
    ("iframe srcdoc is a nested document", '<iframe srcdoc="<script>BEACON()</script>"></iframe>', FAIL, "BEACON"),
    # --- and the true positives that must NOT be broken by the fix above
    ("type absent executes", "<script>BEACON()</script>", PASS, "BEACON"),
    ("type empty executes", '<script type="">BEACON()</script>', PASS, "BEACON"),
    ("type=text/javascript executes", '<script type="text/javascript">BEACON()</script>', PASS, "BEACON"),
    ("type case/space insensitive", '<script type=" text/JavaScript ">BEACON()</script>', PASS, "BEACON"),
    ("type=module executes", '<script type="module">BEACON()</script>', PASS, "BEACON"),
    ("type=application/javascript executes", '<script type="application/javascript">BEACON()</script>', PASS, "BEACON"),
    ("real script after an inert template", "<template><script>x()</script></template><script>BEACON()</script>", PASS, "BEACON"),
    ("real script after an inert noscript", "<noscript><script>x()</script></noscript><script>BEACON()</script>", PASS, "BEACON"),
    ("real script after a data block", '<script type="application/json">{}</script><script>BEACON()</script>', PASS, "BEACON"),
    ("unclosed template ends the document", "<template><script>BEACON()</script>", CANNOT_CERTIFY, "BEACON"),
]


def self_test(verbose: bool = True) -> int:
    bad = 0
    for name, html, expected, needle in _CORPUS:
        rep = analyze(html)
        failures = assert_all_scripts_closed(rep)
        if needle:
            failures += assert_inline_contains(rep, needle)
        got = verdict(rep, failures)
        ok = got == expected
        bad += 0 if ok else 1
        if verbose or not ok:
            mark = "ok  " if ok else "FAIL"
            print(f"  [{mark}] {name}: expected {expected}, got {got}")
            if not ok:
                for u in rep.uncertainties:
                    print(f"         uncertainty: {u}")
                for f in failures:
                    print(f"         failure: {f}")
    print(f"self-test: {len(_CORPUS) - bad}/{len(_CORPUS)} cases as expected")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*", help="HTML files to check")
    ap.add_argument("--require-inline", action="append", default=[],
                    help="string that must appear inside an inline <script> body")
    ap.add_argument("--forbid-inline", action="append", default=[],
                    help="string that must NOT appear inside an inline <script> body")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.files:
        ap.error("no files given (or use --self-test)")

    worst = PASS
    for path in args.files:
        try:
            html = open(path, encoding="utf-8", errors="replace").read()
        except OSError as exc:
            print(f"{path}: CANNOT-CERTIFY — cannot read: {exc}")
            worst = CANNOT_CERTIFY
            continue

        rep = analyze(html)
        failures = assert_all_scripts_closed(rep)
        for n in args.require_inline:
            failures += assert_inline_contains(rep, n)
        for n in args.forbid_inline:
            failures += assert_inline_absent(rep, n)
        v = verdict(rep, failures)

        inline = len(rep.inline_bodies())
        print(f"{path}: {v}  ({len(rep.scripts)} script elements, {inline} inline)")
        for u in rep.uncertainties:
            print(f"    uncertain: {u}")
        for f in failures:
            print(f"    failure:   {f}")

        # CANNOT-CERTIFY outranks FAIL: it means the verdict itself is unavailable.
        if v == CANNOT_CERTIFY:
            worst = CANNOT_CERTIFY
        elif v == FAIL and worst != CANNOT_CERTIFY:
            worst = FAIL

    print(f"\noverall: {worst}")
    return EXIT[worst]


if __name__ == "__main__":
    sys.exit(main())
