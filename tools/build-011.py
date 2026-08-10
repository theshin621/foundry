#!/usr/bin/env python3
"""tools/build-011.py — assemble public/011-diffusion-curves/index.html.

Ships must be self-contained single files, and shared primitives must have exactly one source of
truth. Those two rules conflict unless the inlining is mechanical, so it is mechanical: this script
splices lib/esc.js, lib/wos-glsl.js and src/011-diffusion-curves/app.js into the shell VERBATIM.
The ship's oracle carries a drift predicate that re-runs this build and fails if the committed page
differs by a byte.
"""
import os, sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(REPO, "public", "011-diffusion-curves", "index.html")
PARTS = [("/*__ESC__*/", "lib/esc.js"),
         ("/*__WOS__*/", "lib/wos-glsl.js"),
         ("/*__APP__*/", "src/011-diffusion-curves/app.js")]


def build():
    html = open(os.path.join(REPO, "src", "011-diffusion-curves", "shell.html"), encoding="utf-8").read()
    for token, rel in PARTS:
        if token not in html:
            raise SystemExit(f"shell.html is missing the {token} slot")
        html = html.replace(token, open(os.path.join(REPO, rel), encoding="utf-8").read())
    return html


if __name__ == "__main__":
    out = build()
    if "--check" in sys.argv:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if cur != out:
            print("DRIFT: public/011-diffusion-curves/index.html does not match its sources")
            sys.exit(1)
        print("no drift")
        sys.exit(0)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(out)
    print(f"wrote {OUT} ({len(out)} bytes)")
