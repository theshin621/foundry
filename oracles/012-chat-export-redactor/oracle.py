#!/usr/bin/env python3
"""
ORACLE — ship 012 chat-export-redactor.

WRITTEN BEFORE THE ARTIFACT (v4: NO ORACLE, NO BUILD). It drives a page it has never
seen through the contract fixed in manifest.json, in a REAL BROWSER, and judges the
files a real user would actually download.

WHY A BROWSER AND NOT A PARSER (BOTTLENECKS.md entry #1, clause 3, five incidents):
every claim this ship makes is a claim about behaviour, not about markup. "The file
never leaves your machine" is a claim about network traffic. "The payload does not
execute" is a claim about a JS engine. A static walker over the HTML can be green on a
page that is provably broken when a browser runs it -- that is exactly how #008 failed
four times. So this oracle observes Chromium: it intercepts every request, it reads
window state after execution, and it captures the real download streams.

USAGE
    python3 oracles/012-chat-export-redactor/oracle.py <path-to-index.html>
    python3 oracles/012-chat-export-redactor/oracle.py --url http://127.0.0.1:8012/012-chat-export-redactor/

EXIT 0 = PASS (every predicate green). EXIT 1 = FAIL. EXIT 2 = CANNOT-CERTIFY (the
oracle could not run; it declines to bless a page it could not read -- ship 009's one
good idea, kept).
"""
import functools
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / "manifest.json").read_text())
FIX = HERE / "fixtures"
C = MANIFEST["page_contract"]

results = []          # (id, ok, detail)
def rec(pid, ok, detail=""):
    results.append((pid, bool(ok), detail))
    return ok


# ---------------------------------------------------------------- helpers
def occurrences(needle, hay):
    """Case-insensitive count. Plain substring on purpose: a residual identifier is a
    residual identifier whether or not it sits on a word boundary."""
    return hay.lower().count(needle.lower())


def in_order(seq, hay):
    """Every item appears, and in the given relative order."""
    pos = 0
    for s in seq:
        i = hay.find(s, pos)
        if i < 0:
            return False, s
        pos = i + len(s)
    return True, None


# ---------------------------------------------------------------- the run
def serve(directory):
    """Serve the artifact over http rather than file://.

    NOT a convenience. A file:// page is a different security origin to the one real
    visitors get: Chromium refuses blob: downloads there, and an oracle that worked
    around that (by reading the DOM instead of the download) would be certifying a
    code path no user ever runs. The page is judged on the transport it ships on.
    """
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "http://127.0.0.1:%d/" % httpd.server_address[1]


def run(target, is_url):
    from playwright.sync_api import sync_playwright

    httpd = None
    if not is_url:
        art = pathlib.Path(target).resolve()
        httpd, base = serve(art.parent)
        target, is_url = base + art.name, True
    origin = target.rsplit("/", 1)[0] + "/"

    fixtures = MANIFEST["fixtures"]

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-gpu"])

        def process(fixture_file, ctx=None, collect_requests=False):
            """Drive one fixture through the page. Returns dict with clean/map/status/
            requests/window flags. Everything measured, nothing assumed."""
            own = ctx is None
            if own:
                ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()
            reqs = []
            if collect_requests:
                page.on("request", lambda r: reqs.append(r.url))
            page.goto(target)
            page.wait_for_selector(C["file_input"], timeout=15000)
            page.set_input_files(C["file_input"], str(FIX / fixture_file))
            # Wait for the page's own completion flag OR an error status; never sleep
            # a fixed number of seconds and call that "done".
            try:
                page.wait_for_function(
                    "() => window.__CR_DONE === true || "
                    "(document.querySelector(%r) && /ERROR/i.test("
                    "document.querySelector(%r).textContent))"
                    % (C["status_el"], C["status_el"]),
                    timeout=20000,
                )
            except Exception:
                pass
            status = page.eval_on_selector(
                C["status_el"], "e => e.textContent"
            ) if page.query_selector(C["status_el"]) else ""
            preview = page.eval_on_selector(
                C["preview_el"], "e => e.textContent"
            ) if page.query_selector(C["preview_el"]) else ""
            preview_html = page.eval_on_selector(
                C["preview_el"], "e => e.innerHTML"
            ) if page.query_selector(C["preview_el"]) else ""
            pwned = page.evaluate(
                "() => [typeof window.__pwned, typeof window.__pwned2]"
            )

            clean = mapping = None
            btn = page.query_selector(C["download_clean_btn"])
            visible = bool(btn and btn.is_visible() and not btn.is_disabled())
            if visible:
                with page.expect_download(timeout=15000) as di:
                    btn.click()
                d = di.value
                clean = pathlib.Path(d.path()).read_bytes().decode("utf-8", "replace")
            mbtn = page.query_selector(C["download_map_btn"])
            if mbtn and mbtn.is_visible() and not mbtn.is_disabled():
                with page.expect_download(timeout=15000) as di2:
                    mbtn.click()
                mapping = pathlib.Path(di2.value.path()).read_bytes().decode(
                    "utf-8", "replace")

            out = dict(status=status, preview=preview, preview_html=preview_html,
                       clean=clean, mapping=mapping, requests=reqs,
                       clean_offered=visible, pwned=pwned)
            page.close()
            if own:
                ctx.close()
            return out

        # ---- per-fixture predicates -------------------------------------
        for f in fixtures:
            name = f["file"]
            tag = name.split(".")[0]
            src = (FIX / name).read_bytes().decode("utf-8", "replace")
            r = process(name, collect_requests=True)

            # P10 — bad input must announce itself, and must NOT offer a download.
            if f.get("expect_error"):
                rec("P10.status:%s" % tag,
                    C["status_error_token"].lower() in (r["status"] or "").lower(),
                    "status=%r" % (r["status"] or "")[:120])
                rec("P10.nodownload:%s" % tag, not r["clean_offered"],
                    "a sanitised download was offered for an unparsed file")
                continue

            if r["clean"] is None:
                rec("P0.processed:%s" % tag, False,
                    "no sanitised download produced; status=%r" % (r["status"] or "")[:120])
                continue
            rec("P0.processed:%s" % tag, True)
            clean = r["clean"]

            # P1 — the architectural claim, measured.
            leaks = [u for u in r["requests"]
                     if not re.search(r"(/_b(\b|/)|cloudflareinsights\.com"
                                      r"|^data:|^blob:|^about:)", u)
                     and not u.startswith(origin)]
            rec("P1.clientside:%s" % tag, not leaks, "egress: %s" % leaks[:3])

            # P2 — zero residual identifiers.
            resid = [i for i in f.get("identifiers", []) if occurrences(i, clean)]
            rec("P2.residual:%s" % tag, not resid, "still present: %s" % resid[:6])

            # P4 — structure preserved.
            if "lines" in f:
                rec("P4.lines:%s" % tag,
                    len(clean.splitlines()) == len(src.splitlines()),
                    "in=%d out=%d" % (len(src.splitlines()), len(clean.splitlines())))
            ok, missing = in_order(f.get("timestamps_verbatim", []), clean)
            rec("P4.timestamps:%s" % tag, ok, "missing/out-of-order: %r" % missing)

            # P6 — not just blanked.
            gone = [t for t in f.get("must_survive", []) if not occurrences(t, clean)]
            rec("P6.survive:%s" % tag, not gone, "destroyed: %s" % gone)

            # P3 + P8 — mapping bijective, and not leaked into the sanitised file.
            if r["mapping"] is not None:
                try:
                    m = json.loads(r["mapping"])
                    pairs = m.get("map", m) if isinstance(m, dict) else {}
                    vals = list(pairs.values())
                    rec("P3.injective:%s" % tag, len(set(vals)) == len(vals),
                        "pseudonyms collide: %s" % vals)
                    if "participants" in f:
                        rec("P3.count:%s" % tag,
                            len({v for k, v in pairs.items()}) >= f["participants"],
                            "distinct pseudonyms=%d expected>=%d"
                            % (len(set(vals)), f["participants"]))
                    leaked = [k for k in pairs if occurrences(k, clean)]
                    rec("P8.nomapleak:%s" % tag, not leaked,
                        "originals found in sanitised file: %s" % leaked[:4])
                except Exception as e:
                    rec("P3.parse:%s" % tag, False, "mapping not JSON: %s" % e)
            elif not f.get("xss_probe"):
                rec("P3.mapping:%s" % tag, False, "no mapping download offered")

            # P7 — telegram stays valid JSON.
            if f["format"] == "telegram":
                try:
                    j = json.loads(clean)
                    msgs = j.get("messages", [])
                    rec("P7.json:%s" % tag,
                        len(msgs) == f["json_message_count"],
                        "messages=%d expected=%d" % (len(msgs), f["json_message_count"]))
                    froms = {m.get("from") for m in msgs if m.get("from")}
                    rec("P7.from:%s" % tag,
                        all("Mokoena" not in x and "Nkosi" not in x for x in froms),
                        "from values=%s" % froms)
                except Exception as e:
                    rec("P7.json:%s" % tag, False, "not valid JSON: %s" % e)

            # P9 — the payload must be inert in a real engine.
            if f.get("xss_probe"):
                rec("P9.inert:%s" % tag, r["pwned"] == ["undefined", "undefined"],
                    "window flags=%s" % r["pwned"])
                rec("P9.astext:%s" % tag,
                    "<img" not in (r["preview_html"] or "").lower()
                    or "&lt;img" in (r["preview_html"] or "").lower(),
                    "preview innerHTML contains a live tag")

        # ---- P5 determinism, across two independent contexts -------------
        a = process("wa-ios.txt")["clean"]
        b = process("wa-ios.txt")["clean"]
        rec("P5.determinism", a is not None and a == b,
            "two runs differ" if a != b else "")
        browser.close()

    if httpd:
        httpd.shutdown()
    return results


def main():
    args = sys.argv[1:]
    is_url = False
    if not args:
        print("usage: oracle.py <index.html> | --url <URL>", file=sys.stderr)
        return 2
    if args[0] == "--url":
        target, is_url = args[1], True
    else:
        target = args[0]
        if not os.path.exists(target):
            print("CANNOT-CERTIFY: artifact not found: %s" % target)
            return 2
    try:
        run(target, is_url)
    except Exception as e:
        print("CANNOT-CERTIFY: the oracle could not execute: %r" % e)
        return 2

    bad = [r for r in results if not r[1]]
    for pid, ok, detail in results:
        print("  %-4s %-26s %s" % ("ok" if ok else "FAIL", pid, detail if not ok else ""))
    print("\n%d/%d predicates green" % (len(results) - len(bad), len(results)))
    if bad:
        print("VERDICT: FAIL — %s" % ", ".join(p for p, _, _ in bad))
        return 1
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
