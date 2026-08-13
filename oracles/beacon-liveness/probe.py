#!/usr/bin/env python3
"""
oracles/beacon-liveness/probe.py — PROBE-THE-ORACLE for beacon-liveness.

Mandatory under PLAYBOOK §ARCHITECT (v4). Three clauses:

  (a) NEGATIVE CONTROL — break the artifact in each way the oracle claims to catch and
      confirm it goes RED.
  (b) INDEPENDENT BREAK ATTEMPT — construct a page the oracle still passes while the
      thing it certifies is not true. Survivors are recorded as KNOWN LIMITS in
      oracle.py's docstring rather than quietly left in.
  (c) NO DECORATION — added 2026-08-13 after the checker refuted this file's own
      predecessor. Every predicate is NEUTERED IN TURN and at least one control must
      flip. A predicate whose neutering changes no verdict is not verified by this
      suite, and saying "23/23" about it is the failure BOTTLENECKS #1 (entry #2,
      round 3) already paid for once: ten predicates with no control, reported 18/18,
      headline fix never exercised. The previous version of this file made exactly
      that claim and three of its predicates were decoration. This clause is now a
      machine-checked property rather than a sentence in a commit message.

Each fixture is observed in a real browser ONCE; the recorded observations are then
re-judged under every neutering. Browser time is the expensive part, and re-judging is
free, so clause (c) costs almost nothing.

Run:  python3 oracles/beacon-liveness/probe.py [-v]
Exit: 0 everything behaved · 1 a control misbehaved or a predicate is decoration.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle  # noqa: E402  (the real module — predicates are never re-implemented here)

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


def post(body_js, path="'/_b'"):
    return ("<script>fetch(%s,{method:'POST',body:%s,"
            "headers:{'content-type':'text/plain'}}).catch(function(){});</script>"
            % (path, body_js))


SELF_OK = "JSON.stringify({path:location.pathname+location.search,self:false})"

# name -> (html, request-path, expected verdict, what it controls)
CASES = [
    # ---- positive controls ------------------------------------------------------
    ("live-snippet", page(LIVE), "/live-snippet/", "PASS",
     "the real artifact must be blessed"),
    ("self-1-declared", None, "/live-snippet/?self=1", "PASS",
     "P6 bidirectional: the real snippet honours ?self=1"),

    # ---- (a) the inert-markup vectors a substring test passes -------------------
    ("absent", page(""), "/absent/", "FAIL", "no snippet at all"),
    ("in-template", page("<template>%s</template>" % LIVE), "/in-template/", "FAIL",
     "BOTTLENECKS #1 incident #4 vector"),
    ("in-noscript", page("<noscript>%s</noscript>" % LIVE), "/in-noscript/", "FAIL",
     "BOTTLENECKS #1 incident #4 vector"),
    ("in-comment", page("<!-- %s -->" % LIVE), "/in-comment/", "FAIL", "commented out"),
    ("as-json-block", page(LIVE.replace("<script>", '<script type="application/json">')),
     "/as-json-block/", "FAIL", "BOTTLENECKS #1 incident #009 vector"),

    # ---- (a) P4: delivery, with each reason isolated ----------------------------
    ("wrong-path", page(LIVE.replace("'/_b'", "'/_beacon'")), "/wrong-path/", "FAIL",
     "P4: exact path, not a near miss"),
    ("prefix-path", page("<script>fetch('/_bootstrap.js').catch(function(){});</script>"),
     "/prefix-path/", "FAIL", "P4: /_bootstrap.js must not satisfy /_b"),
    ("img-get-only", page("<img src='/_b' alt=''>"), "/img-get-only/", "FAIL",
     "P4: a GET sends no payload"),
    ("empty-body", page(post("''")), "/empty-body/", "FAIL", "P4: empty is not delivery"),
    ("not-json", page(post("'hello'")), "/not-json/", "FAIL", "P4: body must parse"),
    ("json-no-path", page(post("JSON.stringify({self:false})")), "/json-no-path/",
     "FAIL", "P4: body must carry a path"),
    ("json-path-not-string", page(post("JSON.stringify({path:42,self:false})")),
     "/json-path-not-string/", "FAIL", "P4: path must be a string"),

    # ---- (a) P5: binding, ISOLATED. The checker's finding 2 was that the old
    # binding fixture also tripped the self-flag check, so neutering the binding
    # predicate changed nothing and it shipped unverified. self is correct here.
    ("wrong-page-bound", page(post("JSON.stringify({path:'/somewhere-else/',self:false})")),
     "/wrong-page-bound/", "FAIL", "P5 ISOLATED: binds to another page, self correct"),
    ("redirects", page("<script>location.replace('/live-snippet/');</script>"),
     "/redirects/", "PASS",
     "P5: a client redirect delivers a real beacon and must NOT be called dead"),

    # ---- (a) P6: the self flag, isolated in both directions ---------------------
    ("always-self", page(post("JSON.stringify({path:location.pathname,self:true})")),
     "/always-self/", "FAIL", "P6 ISOLATED: hides from its own stats, binding correct"),
    ("no-self-key", page(post("JSON.stringify({path:location.pathname})")),
     "/no-self-key/", "FAIL", "P6: the flag must be present, not merely falsy"),
    ("self-1-consistent", None, "/always-self/?self=1", "PASS",
     "P6 must not fail a page whose self:true is CORRECT"),

    # ---- (a) P7: uncaught errors, isolated (a live, bound, correctly-flagged
    # beacon that also throws) ----------------------------------------------------
    ("throws", page(post(SELF_OK) + "<script>null.x;</script>"), "/throws/", "FAIL",
     "P7 ISOLATED: everything else passes, the page still threw"),

    # ---- (b) independent break attempts -----------------------------------------
    ("b1-handrolled", page(post(SELF_OK)), "/b1-handrolled/", "PASS",
     "(b) EXPECTED — certifies behaviour, not markup provenance"),
    ("b2-popup", page(
        "<script>var w=window.open('about:blank');"
        "w.fetch('/_b',{method:'POST',body:" + SELF_OK +
        ",headers:{'content-type':'text/plain'}}).catch(function(){});</script>"),
     "/b2-popup/", "PASS",
     "(b) a popup's beacon is still this page's beacon"),
    ("b3-gesture-only", page(
        "<script>document.addEventListener('click',function(){fetch('/_b',{method:'POST',"
        "body:" + SELF_OK + ",headers:{'content-type':'text/plain'}});});</script>"),
     "/b3-gesture-only/", "FAIL",
     "(b) SURVIVES as a false RED — KNOWN LIMIT 1"),
]

# ---- (a) verdict-class controls: ground truth unavailable -----------------------
SPECIAL = [
    ("missing-page", ["/does-not-exist/"], "CANNOT-CERTIFY", {},
     "P2: a page that did not load cannot be judged dead"),
    ("no-targets", [], "CANNOT-CERTIFY", {},
     "P1: zero targets is not a clean bill of health"),
    ("p3-flag-up", ["/live-snippet/"], "CANNOT-CERTIFY", {"mask_webdriver": False},
     "P3: bot guard up -> decline, never a confident false FAIL"),
    ("one-dead-among-live", ["/live-snippet/", "/in-template/", "/live-snippet/"],
     "FAIL", {}, "#008 round 4: N expectations must not share one live element"),
]

PREDICATES = ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]


def main():
    verbose = "-v" in sys.argv
    rows, failures = [], []
    observed = {}  # name -> records, judged repeatedly under different neuterings

    with tempfile.TemporaryDirectory() as td:
        for name, html, path, _exp, _why in CASES:
            if html is None:
                continue
            d = os.path.join(td, name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.html"), "w") as fh:
                fh.write(html)

        sink = []
        httpd, base = oracle.serve(td, sink)
        try:
            for name, _html, path, expected, why in CASES:
                recs = oracle.observe(base, [path], sink)
                observed[name] = recs
                got, _ = oracle.judge(recs)
                ok = got == expected
                rows.append((name, expected, got, ok, why))
                if not ok:
                    failures.append("%s: expected %s, got %s\n%s"
                                    % (name, expected, got, oracle.judge(recs)[1]))

            for name, paths, expected, kw, why in SPECIAL:
                recs = oracle.observe(base, paths, sink, **kw)
                observed[name] = recs
                got, _ = oracle.judge(recs)
                ok = got == expected
                rows.append((name, expected, got, ok, why))
                if not ok:
                    failures.append("%s: expected %s, got %s\n%s"
                                    % (name, expected, got, oracle.judge(recs)[1]))
        finally:
            httpd.shutdown()

    # ------- clause (c): neuter each predicate, demand that a control flips -------
    baseline = {n: oracle.judge(r)[0] for n, r in observed.items()}
    decoration, controlled = [], []
    for pid in PREDICATES:
        flipped = [n for n, r in observed.items()
                   if oracle.judge(r, neuter={pid})[0] != baseline[n]]
        if flipped:
            controlled.append((pid, flipped))
        else:
            decoration.append(pid)

    width = max(len(n) for n, *_ in rows)
    for name, exp, got, ok, why in rows:
        print("%-*s  expect %-14s got %-14s %s   %s"
              % (width, name, exp, got, "ok" if ok else "MISMATCH", why if verbose else ""))

    print("\n-- clause (c): every predicate must have a control that flips it --")
    for pid, flipped in controlled:
        print("%-4s controlled by %s" % (pid, ", ".join(sorted(flipped)[:4])))
    for pid in decoration:
        print("%-4s DECORATION — neutering it changes no verdict in this suite" % pid)

    print("\n%d/%d controls behaved · %d/%d predicates genuinely controlled"
          % (len(rows) - len(failures), len(rows), len(controlled), len(PREDICATES)))

    if failures or decoration:
        for f in failures:
            print("\n--- %s" % f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
