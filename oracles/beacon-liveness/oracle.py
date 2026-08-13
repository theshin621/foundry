#!/usr/bin/env python3
"""
oracles/beacon-liveness/oracle.py — does the beacon actually FIRE?

WHY THIS EXISTS
---------------
`public/health.json` has carried a field named `has_beacon` since the fleet moved
first-party. Its implementation is a substring test on the response bytes:

    'has_beacon': "'/_b'" in body            # .github/workflows/health-check.yml

That is a liveness-of-markup claim asserted by string matching — the exact construct
BOTTLENECKS.md entry #1 clause 3 forbids ("the hand-written parse-and-match band is
deleted, not repaired"). It reports true for a snippet inside <template>, <noscript>,
an HTML comment, or <script type="application/json"> — every vector incidents #4 and
#009 already paid for, all of which leave the string in `body` and the beacon dead.
The field has ALREADY failed this way once: until 2026-08-10 it matched
'cloudflareinsights.com', a third-party beacon ship 008 had removed, so every page
reported has_beacon:true while the field measured a script the loop no longer used.

This oracle does no static analysis. It executes the page in Chromium and watches the
network.

THE TRAP THAT MOTIVATES P4, MEASURED 2026-08-13 BEFORE THIS FILE EXISTED
------------------------------------------------------------------------
The beacon snippet's first line is `if(navigator.webdriver) return;`. A browser-truth
oracle that does not neutralise that flag observes ZERO beacon requests on a perfectly
live page and reports a confident false RED — the naive browser method is wrong in the
opposite direction from the substring method. Neutralisation is therefore not assumed:
P4 *measures* `navigator.webdriver` from inside the page and declines to certify if it
is not false. An unverified neutralisation makes every other predicate meaningless.

WHAT EACH PREDICATE BUYS, AND THE BREAK IT CLOSES
-------------------------------------------------
P1-P3 establish that there is anything to judge at all (targets exist, pages loaded,
   the bot guard is down). All three decline rather than condemn.
P4 the delivery claim: a payload reached `/_b` that parses as JSON carrying a string
   `path`. Exact-path, so `/_bootstrap.js` does not satisfy it; delivery-based, so
   `<img src="/_b">` (a GET carrying nothing) does not either. Its `detail` names WHICH
   of the four ways it failed, which is why it is one predicate and not four —
   see judge()'s docstring on decoration.
P5 binds the payload to the page that ACTUALLY SENT IT — `page.url` after navigation,
   not the URL requested. #008 round 4 died because `verify_bodies` matched each
   expectation independently, so N directives could be satisfied by one live element.
P6 the countability claim, which is not the same as the liveness claim: a page that
   always declares `self:true` fires perfectly and is discarded by the worker as
   self-traffic, so it is invisible in `/_b/stats` forever. Checked both ways.
P7 fails a page that raised an uncaught error, because a page that throws may have
   thrown before the beacon ran, and some other code path's beacon would still
   satisfy P4-P6.

KNOWN LIMITS — what survived probe.py clause (b), stated rather than glossed
---------------------------------------------------------------------------
1. FALSE RED on gesture-gated beacons. A page that beacons only on click/scroll is
   live for a human and silent for a headless load, and this oracle calls it FAIL.
   The current fleet does not do this (the snippet fires at parse time), so the limit
   is unreachable today — but it becomes reachable the moment a ship defers its
   beacon, and the failure would look like a real regression. `probe.py` keeps
   `b3-gesture-only` as a standing record of it.
2. It certifies BEHAVIOUR, not the provenance of the markup. A page that hand-rolls
   an equivalent POST passes without containing the canonical snippet
   (`probe.py` b1-handrolled). That is the intended reading of the claim, not a
   defect: the loop steers by visits that arrive, not by bytes that are present. It
   is written down so the PASS is not overread as "the page carries lib/'s snippet".
3. It observes a LOCAL serve of `public/`, not tailorfarms.com. It proves the built
   artifact is live; it cannot prove the CDN served that artifact. `health.json`'s
   HTTP probe remains the check on delivery, and the two claims are now separate
   rather than conflated in one misnamed field.

VERDICTS
--------
PASS            every target page fired a bindable first-party beacon POST
FAIL            a page loaded cleanly, the flag was down, and no such POST occurred
CANNOT-CERTIFY  ground truth could not be established (no browser, no targets, a page
                that did not load, or a flag that could not be put down). Declining is
                a legitimate outcome; blessing a page it cannot read is not.

Exit codes: 0 PASS · 1 FAIL · 2 CANNOT-CERTIFY.

Usage:
    oracle.py                                  # serve ./public, targets from ledger.json
    oracle.py --pages-dir DIR --paths / /a/    # serve DIR, explicit targets
    oracle.py --json                           # machine-readable report on stdout
"""
import argparse
import functools
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BEACON_PATH = "/_b"
SETTLE_MS = 2500


# --------------------------------------------------------------------------- targets
def targets_from_ledger(ledger_path):
    """Live, page-bearing ships only. Infra rows have no page of their own (row 8 is
    inlined into the others), which is why health-check.yml skips them too."""
    with open(ledger_path) as fh:
        ships = json.load(fh).get("ships", [])
    out = []
    for s in ships:
        if s.get("status") != "live" or s.get("kind") == "infra":
            continue
        out.append("/" if s.get("slug") == "hub" else "/%03d-%s/" % (s["n"], s["slug"]))
    return out


# ---------------------------------------------------------------------------- server
class _Quiet(http.server.SimpleHTTPRequestHandler):
    """Static server that also PLAYS THE WORKER for /_b and keeps the bytes.

    The body is captured here, at the receiving end, and not from Playwright's request
    object. That is not a workaround, it is the stronger observation: `sendBeacon`
    ships a Blob and Playwright reports `post_data == None` for exactly the request
    this oracle exists to see, so a client-side body check would fail every live page.
    The server sees what a real worker would see."""

    received = None  # set to a list by serve(); appended under the class lock
    lock = threading.Lock()

    def log_message(self, *a):
        pass

    def do_POST(self):
        try:
            n = int(self.headers.get("content-length") or 0)
        except ValueError:
            n = 0
        raw = self.rfile.read(n) if n > 0 else b""
        if urllib.parse.urlsplit(self.path).path == BEACON_PATH:
            with _Quiet.lock:
                if _Quiet.received is not None:
                    _Quiet.received.append({
                        "body": raw.decode("utf-8", "replace"),
                        "referer": self.headers.get("referer"),
                    })
        self.send_response(204)
        self.end_headers()


def serve(directory, sink):
    _Quiet.received = sink
    handler = functools.partial(_Quiet, directory=directory)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "http://127.0.0.1:%d" % httpd.server_address[1]


# --------------------------------------------------------------------------- observe
def observe(base_url, paths, sink, mask_webdriver=True):
    """Load each path in its own browser context, SERIALLY, and record what the network
    did. Pages are loaded one at a time and `sink` is snapshotted around each load, so a
    body received by the server is bound to the page that was open when it arrived — no
    cross-page attribution is possible. Raises RuntimeError for anything that means 'no
    ground truth' rather than 'dead'."""
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("playwright is not importable: %s: %s" % (type(e).__name__, e))

    records = []
    with sync_playwright() as pw:
        try:
            # TWO independent maskings, kept deliberately. Measured 2026-08-13: the
            # launch flag ALONE already yields navigator.webdriver === false in
            # Chromium 141, so the init script is currently redundant — but which of
            # the two works is a Chromium implementation detail that has changed
            # before, and P4 measures the result rather than trusting either. Both are
            # dropped together by mask_webdriver=False so probe.py can actually
            # exercise P4.
            args = ["--no-sandbox"]
            if mask_webdriver:
                args.append("--disable-blink-features=AutomationControlled")
            browser = pw.chromium.launch(args=args)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError("chromium did not launch: %s: %s" % (type(e).__name__, e))

        try:
            for path in paths:
                ctx = browser.new_context()
                # Neutralise the snippet's own bot guard. VERIFIED below, never
                # assumed. `mask_webdriver=False` exists ONLY so probe.py can build a
                # negative control for P4 — it is never used by a real run.
                if mask_webdriver:
                    ctx.add_init_script(
                        "Object.defineProperty(navigator,'webdriver',{get:()=>false});"
                    )
                page = ctx.new_page()
                beacons, errors = [], []

                def on_request(req, s=beacons):
                    if urllib.parse.urlsplit(req.url).path == BEACON_PATH:
                        s.append({"method": req.method})

                def wire(pg):
                    # CONTEXT-level, not page-level: a beacon fired from a popup is
                    # still this page's beacon. (Checker 2026-08-13 finding 3.)
                    pg.on("request", on_request)
                    pg.on("pageerror", lambda e, s=errors: s.append(str(e)[:300]))

                wire(page)
                ctx.on("page", wire)

                with _Quiet.lock:
                    start = len(sink)

                rec = {"path": path, "beacons": beacons, "errors": errors}
                try:
                    resp = page.goto(base_url + path, wait_until="load", timeout=30000)
                    rec["http"] = resp.status if resp else None
                except Exception as e:  # noqa: BLE001
                    rec["http"] = None
                    rec["load_error"] = "%s: %s" % (type(e).__name__, e)

                page.wait_for_timeout(SETTLE_MS)

                try:
                    rec["webdriver"] = page.evaluate("() => navigator.webdriver")
                except Exception as e:  # noqa: BLE001
                    rec["webdriver"] = "unreadable: %s" % type(e).__name__

                # The beacon reports where the page ENDED UP, so the binding check must
                # compare against that, not against what was requested. Before this,
                # a page that client-redirected delivered a perfect beacon and was
                # called dead. (Checker 2026-08-13 finding 1.)
                try:
                    rec["final_path"] = urllib.parse.urlsplit(page.url).path
                except Exception:  # noqa: BLE001
                    rec["final_path"] = None

                ctx.close()  # flushes any beacon still in flight before the snapshot
                with _Quiet.lock:
                    rec["delivered"] = list(sink[start:])
                records.append(rec)
        finally:
            browser.close()
    return records


# ------------------------------------------------------------------------ predicates
def judge(records, neuter=()):
    """Returns (verdict, predicate_results).

    `neuter` forces the named predicate IDs to pass. It is a TEST SEAM, reachable only
    from probe.py and never from the CLI: probe.py neuters each predicate in turn and
    requires at least one control to flip, which turns "every predicate has a control"
    from a claim in a commit message into a machine-checked property. The 2026-08-13
    checker showed why that matters — three of the original predicates had no isolating
    control anywhere in the suite while the commit message asserted 23/23.

    THE PREDICATE SET IS DELIBERATELY SMALL. The first version had P5 (browser issued a
    POST), P6 (server received a non-empty body) and P7 (the body parses as JSON with a
    path) as three predicates. They are not independent: nothing can be received unless
    it was sent, and nothing parses unless it was received, so P5 and P6 could never fail
    while a later one passed. Neutering either changed no verdict — the definition of
    decoration. They are now ONE predicate with a detailed reason string, which keeps the
    diagnostic value without pretending to be three independent checks. Deleted, not
    repaired.
    """
    P = []

    def add(pid, desc, ok, detail="", kind="FAIL"):
        if pid in neuter:
            ok, detail = True, "NEUTERED by probe"
        P.append({"id": pid, "desc": desc, "ok": bool(ok), "detail": detail, "kind": kind})

    add("P1", "at least one live page-bearing target", len(records) > 0,
        "%d targets" % len(records), "CANNOT-CERTIFY")

    bad_http = [r["path"] for r in records if r.get("http") != 200]
    add("P2", "every target returned HTTP 200", not bad_http,
        "not-200: %s" % bad_http, "CANNOT-CERTIFY")

    bad_wd = [(r["path"], r.get("webdriver")) for r in records
              if r.get("webdriver") is not False]
    add("P3", "navigator.webdriver measured false inside every page", not bad_wd,
        "flag still up: %s" % bad_wd, "CANNOT-CERTIFY")

    def bodies(r):
        """Delivered payloads that are a JSON object carrying a string `path`."""
        out = []
        for d in r["delivered"]:
            try:
                obj = json.loads(d["body"])
            except Exception:  # noqa: BLE001
                continue
            if isinstance(obj, dict) and isinstance(obj.get("path"), str):
                out.append(obj)
        return out

    def why_silent(r):
        if not r["delivered"]:
            return "nothing arrived at %s" % BEACON_PATH
        if not [d for d in r["delivered"] if (d["body"] or "").strip()]:
            return "arrived with an empty body"
        return "arrived but no payload is JSON carrying a string 'path'"

    silent = [(r["path"], why_silent(r)) for r in records if not bodies(r)]
    add("P4", "every page DELIVERED a first-party beacon payload to %s" % BEACON_PATH,
        not silent, "not counted: %s" % silent)

    unbound = []
    for r in records:
        bs = bodies(r)
        if not bs:
            continue  # already fatal under P4; reporting it twice hides the real cause
        want = r.get("final_path") or urllib.parse.urlsplit(r["path"]).path
        if not any(urllib.parse.urlsplit(b["path"]).path == want for b in bs):
            unbound.append((r["path"], want, [b["path"] for b in bs]))
    add("P5", "every payload binds to the page that actually sent it", not unbound,
        "mismatched (path, expected, delivered): %s" % unbound)

    # A page can satisfy everything above and still be invisible in /_b/stats forever by
    # always declaring self:true — the worker discards self-traffic. "The beacon fires"
    # and "the visit is countable" are different claims and only the second is what the
    # ledger steers by. Checked in BOTH directions so a hard-coded self:false also fails.
    miscounted = []
    for r in records:
        q = urllib.parse.urlsplit(r.get("final_path") or r["path"]).query
        if not q:
            q = urllib.parse.urlsplit(r["path"]).query
        asked = "self=1" in q.split("&")
        for b in bodies(r):
            if b.get("self") is not asked:
                miscounted.append((r["path"], "self=%r, requested self=1: %r"
                                   % (b.get("self"), asked)))
    add("P6", "the self-traffic flag matches how the page was requested",
        not miscounted, "miscounted: %s" % miscounted)

    threw = [(r["path"], r["errors"]) for r in records if r["errors"]]
    add("P7", "no page raised an uncaught error", not threw, "errors: %s" % threw)

    if [p for p in P if not p["ok"] and p["kind"] == "CANNOT-CERTIFY"]:
        return "CANNOT-CERTIFY", P
    if [p for p in P if not p["ok"]]:
        return "FAIL", P
    return "PASS", P


# ------------------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages-dir", default=os.path.join(ROOT, "public"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "ledger.json"))
    ap.add_argument("--paths", nargs="*", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-webdriver-mask", action="store_true",
                    help="probe-only: negative control for P4")
    args = ap.parse_args(argv)

    report = {"pages_dir": args.pages_dir}
    try:
        paths = args.paths if args.paths is not None else targets_from_ledger(args.ledger)
    except Exception as e:  # noqa: BLE001
        verdict, P, paths = "CANNOT-CERTIFY", [{
            "id": "P2", "desc": "targets readable", "ok": False,
            "detail": "%s: %s" % (type(e).__name__, e), "kind": "CANNOT-CERTIFY"}], []
        report.update(verdict=verdict, predicates=P, targets=paths, records=[])
        return emit(report, args.json)

    if not os.path.isdir(args.pages_dir):
        report.update(verdict="CANNOT-CERTIFY", targets=paths, records=[], predicates=[{
            "id": "P0", "desc": "pages dir exists", "ok": False,
            "detail": "no such directory: %s" % args.pages_dir, "kind": "CANNOT-CERTIFY"}])
        return emit(report, args.json)

    sink = []
    httpd, base = serve(args.pages_dir, sink)
    try:
        records = observe(base, paths, sink,
                          mask_webdriver=not args.no_webdriver_mask)
    except RuntimeError as e:
        report.update(verdict="CANNOT-CERTIFY", targets=paths, records=[], predicates=[{
            "id": "P1", "desc": "a real browser is available", "ok": False,
            "detail": str(e), "kind": "CANNOT-CERTIFY"}])
        return emit(report, args.json)
    finally:
        httpd.shutdown()

    verdict, P = judge(records)
    report.update(verdict=verdict, targets=paths, predicates=P, records=[
        {"path": r["path"], "final_path": r.get("final_path"),
         "http": r.get("http"), "webdriver": r.get("webdriver"),
         "requests": [b["method"] for b in r["beacons"]],
         "delivered": r["delivered"],
         "errors": r["errors"]} for r in records])
    return emit(report, args.json)


def emit(report, as_json):
    if as_json:
        print(json.dumps(report, indent=1))
    else:
        for p in report.get("predicates", []):
            print("%-4s %-6s %s%s" % (
                p["id"], "ok" if p["ok"] else "FAIL", p["desc"],
                "" if p["ok"] else "   <- " + p["detail"]))
        for r in report.get("records", []):
            print("     %-32s http=%s webdriver=%s requests=%s delivered=%d" % (
                r["path"], r["http"], r["webdriver"], r["requests"],
                len(r["delivered"])))
        print("VERDICT %s" % report["verdict"])
    return {"PASS": 0, "FAIL": 1}.get(report["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main())
