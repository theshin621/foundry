#!/usr/bin/env python3
"""
oracles/beacon-liveness/probe.py — PROBE-THE-ORACLE for beacon-liveness.

Mandatory under PLAYBOOK §ARCHITECT (v4). Two clauses, both exercised here:

  (a) NEGATIVE CONTROL — break the artifact in each way the oracle claims to catch and
      confirm it goes RED. A predicate with no control that flips is decoration; entry
      #2 round 3 shipped ten of those and reported 18/18 while never exercising its own
      headline fix.
  (b) INDEPENDENT BREAK ATTEMPT — construct a page the oracle still passes while the
      thing it certifies is not true. Whatever survives is recorded as a KNOWN LIMIT in
      the oracle's docstring rather than quietly left in.

Every fixture is a full page built here, served from a temp dir, and run through the
real `oracle.py` as a subprocess — the same entry point a fire or a checker calls. The
probe never imports the predicates and re-implements them.

Run:  python3 oracles/beacon-liveness/probe.py [-v]
Exit: 0 all controls behaved · 1 at least one did not.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ORACLE = os.path.join(HERE, "oracle.py")

# The real snippet, byte-for-byte from lib/beacon-firstparty.snippet.html.
LIVE = """<script>
(function(){
  try{
    if(navigator.webdriver) return;
    var body = JSON.stringify({ path: location.pathname + location.search, self: /(^|[?&])self=1([&#]|$)/.test(location.search) });
    var blob = new Blob([body], {type:'text/plain'});
    if(!(navigator.sendBeacon && navigator.sendBeacon('/_b', blob))){ fetch('/_b', {method:'POST', body:body, keepalive:true, headers:{'content-type':'text/plain'}}).catch(function(){}); }
  }catch(e){}
})();
</script>"""


def page(inner):
    return ("<!doctype html><html><head><meta charset=utf-8><title>probe</title></head>"
            "<body><h1>probe</h1>%s</body></html>" % inner)


def raw_post(body_js, path="'/_b'"):
    return ("<script>fetch(%s,{method:'POST',body:%s,"
            "headers:{'content-type':'text/plain'}}).catch(function(){});</script>"
            % (path, body_js))


# name -> (page html, expected verdict, what it controls)
CASES = {
    # ---- positive control -------------------------------------------------------
    "live-snippet": (page(LIVE), "PASS", "the real artifact must be blessed"),

    # ---- clause (a): the inert-markup vectors the substring test passes ---------
    "absent": (page(""), "FAIL", "no snippet at all"),
    "in-template": (page("<template>%s</template>" % LIVE), "FAIL",
                    "BOTTLENECKS #1 incident #4 vector"),
    "in-noscript": (page("<noscript>%s</noscript>" % LIVE), "FAIL",
                    "BOTTLENECKS #1 incident #4 vector"),
    "in-comment": (page("<!-- %s -->" % LIVE), "FAIL", "commented out"),
    "as-json-block": (page(LIVE.replace("<script>", "<script type=\"application/json\">")),
                      "FAIL", "BOTTLENECKS #1 incident #009 vector"),

    # ---- clause (a): predicate-by-predicate controls ----------------------------
    "wrong-path": (page(LIVE.replace("'/_b'", "'/_beacon'")), "FAIL",
                   "P5: exact path, not a prefix"),
    "prefix-path": (page("<script>fetch('/_bootstrap.js').catch(function(){});</script>"),
                    "FAIL", "P5: /_bootstrap.js must not satisfy /_b"),
    "img-get-only": (page("<img src='/_b' alt=''>"), "FAIL",
                     "P6: a GET sends no beacon"),
    "empty-body": (page(raw_post("''")), "FAIL", "P6: empty body is not a delivery"),
    "not-json": (page(raw_post("'hello'")), "FAIL", "P7: body must parse"),
    "json-no-path": (page(raw_post("JSON.stringify({self:false})")), "FAIL",
                     "P7: body must carry a string path"),
    "json-path-not-string": (page(raw_post("JSON.stringify({path:42})")), "FAIL",
                             "P7: path must be a string"),
    "wrong-page-bound": (page(raw_post("JSON.stringify({path:'/somewhere-else/'})")),
                         "FAIL", "P8: body must bind to its own page"),
    "throws": (page(LIVE + "<script>null.x;</script>"), "FAIL",
               "P9: an uncaught error invalidates the observation"),

    # ---- P10 controls, added at design time after clause (b) broke the oracle ----
    "always-self": (page(raw_post("JSON.stringify({path:location.pathname,self:true})")),
                    "FAIL", "P10: a page that hides from its own stats is not live"),
    "no-self-key": (page(raw_post("JSON.stringify({path:location.pathname})")),
                    "FAIL", "P10: the flag must be present, not merely falsy"),
}


def run(pages_dir, paths, extra=()):
    r = subprocess.run(
        [sys.executable, ORACLE, "--pages-dir", pages_dir, "--paths", *paths, "--json",
         *extra],
        capture_output=True, text=True, timeout=180)
    try:
        return json.loads(r.stdout)["verdict"], r
    except Exception:  # noqa: BLE001
        return "UNPARSEABLE(rc=%s) %s" % (r.returncode, r.stderr[-300:]), r


def main():
    verbose = "-v" in sys.argv
    results, failures = [], []

    with tempfile.TemporaryDirectory() as td:
        for name, (html, expected, why) in CASES.items():
            d = os.path.join(td, name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.html"), "w") as fh:
                fh.write(html)
            got, r = run(td, ["/%s/" % name])
            ok = got == expected
            results.append((name, expected, got, ok, why))
            if not ok:
                failures.append((name, expected, got, r.stdout[-600:]))

        # ---- clause (a), the control this oracle exists because of --------------
        # A browser-truth oracle that does not neutralise navigator.webdriver reads
        # ZERO beacons on a live page. The correct behaviour is to DECLINE, never to
        # report a confident false FAIL. Measured live 2026-08-13 before oracle.py
        # existed; now a control.
        d = os.path.join(td, "live-snippet")
        got, r = run(td, ["/live-snippet/"], extra=["--no-webdriver-mask"])
        ok = got == "CANNOT-CERTIFY"
        results.append(("p4-flag-up", "CANNOT-CERTIFY", got, ok,
                        "P4: bot guard up -> decline, never a false FAIL"))
        if not ok:
            failures.append(("p4-flag-up", "CANNOT-CERTIFY", got, r.stdout[-600:]))

        # ---- P10 the OTHER way: self=1 traffic must declare itself, and the live
        # snippet does. Without this control P10 would be satisfiable by a page that
        # hard-codes self:false, which is the mirror-image lie.
        got, r = run(td, ["/live-snippet/?self=1"])
        ok = got == "PASS"
        results.append(("self-1-declared", "PASS", got, ok,
                        "P10 bidirectional: real snippet honours ?self=1"))
        if not ok:
            failures.append(("self-1-declared", "PASS", got, r.stdout[-600:]))

        got, r = run(td, ["/always-self/?self=1"])
        ok = got == "PASS"
        results.append(("self-1-consistent", "PASS", got, ok,
                        "P10 must not fail a page whose self:true is CORRECT"))
        if not ok:
            failures.append(("self-1-consistent", "PASS", got, r.stdout[-600:]))

        # ---- clause (a): ground truth unavailable -------------------------------
        got, r = run(td, ["/does-not-exist/"])
        ok = got == "CANNOT-CERTIFY"
        results.append(("missing-page", "CANNOT-CERTIFY", got, ok,
                        "P3: a page that did not load cannot be judged dead"))
        if not ok:
            failures.append(("missing-page", "CANNOT-CERTIFY", got, r.stdout[-600:]))

        # ---- clause (a): no vacuous all-pass on an empty target set -------------
        got, r = run(td, [])
        ok = got == "CANNOT-CERTIFY"
        results.append(("no-targets", "CANNOT-CERTIFY", got, ok,
                        "P2: zero targets is not a clean bill of health"))
        if not ok:
            failures.append(("no-targets", "CANNOT-CERTIFY", got, r.stdout[-600:]))

        # ---- clause (a): one dead page among live ones must not be masked -------
        got, r = run(td, ["/live-snippet/", "/in-template/", "/live-snippet/"])
        ok = got == "FAIL"
        results.append(("one-dead-among-live", "FAIL", got, ok,
                        "#008 round 4: N expectations must not share one live element"))
        if not ok:
            failures.append(("one-dead-among-live", "FAIL", got, r.stdout[-600:]))

        # ---- clause (b): INDEPENDENT BREAK ATTEMPTS -----------------------------
        # B1 — a page with no snippet that hand-rolls an equivalent POST. EXPECTED to
        # pass: the oracle certifies behaviour, not the provenance of the markup. This
        # is recorded so the claim is not overread, not treated as a defect.
        d = os.path.join(td, "b1-handrolled")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w").write(page(
            raw_post("JSON.stringify({path:location.pathname,self:false})")))
        b1, _ = run(td, ["/b1-handrolled/"])

        # B2 — THE REAL BREAK. The beacon fires, delivers, binds, and the visit is
        # still never counted, because the body always declares self:true and the
        # worker discards self-traffic. Every predicate is satisfied and the page is
        # invisible in /_b/stats forever.
        d = os.path.join(td, "b2-always-self")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w").write(page(
            raw_post("JSON.stringify({path:location.pathname,self:true})")))
        b2, _ = run(td, ["/b2-always-self/"])

        # B3 — the beacon fires only on a user gesture, so it is live for a human and
        # dead for the oracle's headless load. This is the mirror of B2: the oracle
        # would report FAIL on a page that genuinely counts real visitors.
        d = os.path.join(td, "b3-gesture-only")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w").write(page(
            "<script>document.addEventListener('click',function(){"
            + raw_post("JSON.stringify({path:location.pathname,self:false})")
              .replace("<script>", "").replace("</script>", "")
            + "});</script>"))
        b3, _ = run(td, ["/b3-gesture-only/"])

        breaks = [
            ("b1-handrolled", b1, "PASS",
             "EXPECTED — oracle certifies behaviour, not markup provenance"),
            ("b2-always-self", b2, "FAIL",
             "CLOSED at design time by P10 (was PASS before P10 existed)"),
            ("b3-gesture-only", b3, "FAIL",
             "SURVIVES as a FALSE RED — see KNOWN LIMIT 1 in oracle.py"),
        ]

    width = max(len(n) for n, *_ in results)
    for name, exp, got, ok, why in results:
        print("%-*s  expect %-14s got %-14s %s   %s" % (
            width, name, exp, got, "ok" if ok else "MISMATCH", why if verbose else ""))
    print("\n-- clause (b) independent break attempts --")
    for name, got, exp, note in breaks:
        print("%-*s  got %-14s %s" % (width, name, got, note))

    print("\n%d/%d controls behaved as specified" % (
        len(results) - len(failures), len(results)))
    if failures:
        for name, exp, got, out in failures:
            print("\n--- %s: expected %s, got %s ---\n%s" % (name, exp, got, out))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
