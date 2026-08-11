#!/usr/bin/env python3
"""Mechanical inliner for ship 012. page.src.html + lib/ -> index.html.

WHY IT IS A SCRIPT AND NOT A COPY-PASTE (ship 011's lesson, kept): a hand-inlined page
drifts from lib/ the moment either is edited, and the drift is invisible in review. This
substitutes three marked slots and nothing else, then asserts the result.

It lives under public/012-.../ rather than tools/ because PLAYBOOK Amendment 2026-08-02
clause 9 reserves tools/ to main: a ship branch that edits tools/ is exactly how the
one-click merge grows a conflict.

    python3 public/012-chat-export-redactor/build.py [--check]

--check exits 1 if index.html is not byte-identical to a fresh build (the drift predicate).
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "public/012-chat-export-redactor/page.src.html"
OUT = ROOT / "public/012-chat-export-redactor/index.html"

SLOTS = {
    "/*__VENDOR_PARSER__*/": ROOT / "lib/vendor/whatsapp-chat-parser-4.0.2.min.js",
    "/*__ESC__*/": ROOT / "lib/esc.js",
    "/*__CHAT_REDACT__*/": ROOT / "lib/chat-redact.js",
}


def build():
    html = SRC.read_text()
    for slot, path in SLOTS.items():
        if slot not in html:
            raise SystemExit("FAIL: slot %s missing from page.src.html" % slot)
        body = path.read_text()
        # A </script> inside an inlined module would terminate the host <script> early.
        # This is the exact class of bug BOTTLENECKS #1 incident #008 died on, so it is
        # checked rather than assumed.
        if "</script" in body.lower():
            raise SystemExit("FAIL: %s contains a script end tag and cannot be inlined" % path)
        html = html.replace(slot, body)
    for slot in SLOTS:
        assert slot not in html, slot
    return html


def main():
    html = build()
    if "--check" in sys.argv:
        cur = OUT.read_text() if OUT.exists() else ""
        if cur != html:
            print("DRIFT: index.html does not match a fresh build of page.src.html + lib/")
            return 1
        print("no drift: index.html == fresh build (%d bytes)" % len(html))
        return 0
    OUT.write_text(html)
    print("built %s (%d bytes)" % (OUT, len(html)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
