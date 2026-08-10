#!/usr/bin/env python3
"""
PROBE-THE-ORACLE — mandatory v4 step, run BEFORE the artifact is trusted.

Two duties, per BOTTLENECKS.md #1's second clause:
  (a) NEGATIVE CONTROL — break the artifact in the way the oracle claims to catch,
      and confirm the oracle goes RED. An oracle nobody has seen fail is not evidence.
  (b) AN INDEPENDENT ATTEMPT TO CONSTRUCT A BREAK THE ORACLE STILL PASSES. This is the
      part that matters, and it is written adversarially: the goal is to get invented
      numbers past the oracle, not to demonstrate that honest input passes.

The break attempt that shaped the oracle is B1 below — LAUNDERING. A fire that wanted to
report visits it never measured would not invent a run id (P6.exists catches that in one
API call). It would quote a REAL run id — there is a health-check run every single push —
and attach whatever numbers it liked. That artifact is internally perfect: fresh, well
typed, ok:true, and backed by a run GitHub confirms exists. Only P6.workflow and P6.sha
stop it. They were added because of this probe, which is the probe doing its job.
"""
import json, os, subprocess, sys, tempfile, datetime

HERE   = os.path.dirname(os.path.abspath(__file__))
ORACLE = os.path.join(HERE, "oracle.py")
NOW    = "2026-08-10T02:30:00Z"

# A REAL Actions run, read live from the API: health-check.yml, conclusion success.
REAL_BUT_WRONG_WORKFLOW = {
    "run_id": 31349144686,
    "run_url": "https://github.com/theshin621/foundry/actions/runs/31349144686",
    "head_sha": "12a99fb2fdd338fe418a91e198c09b1ca4ecb0e4",
}

def base():
    return {
        "fetched_utc": "2026-08-10T02:20:00Z",
        "source_url": "https://tailorfarms.com/_b/stats",
        "http": 200, "ok": True,
        "stats": {"/": {"2026-08-09": 4}, "/005-maccleaner/": {"2026-08-09": 2}},
        "provenance": {"run_id": 1, "run_url": "https://github.com/theshin621/foundry/actions/runs/1",
                       "run_attempt": 1, "repo": "theshin621/foundry",
                       "workflow_path": ".github/workflows/beacon-stats.yml",
                       "head_sha": "0" * 40, "runner": "ubuntu-latest"},
    }

def run(doc, label, expect):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(doc, f); p = f.name
    r = subprocess.run([sys.executable, ORACLE, p, "--now", NOW], capture_output=True, text=True)
    os.unlink(p)
    got = {0: "PASS", 1: "FAIL", 2: "CANNOT-CERTIFY"}.get(r.returncode, "?%d" % r.returncode)
    good = got == expect
    print("%s  %-46s expected %-14s got %-14s" % ("[ok] " if good else "[!!] ", label, expect, got))
    if not good:
        print("     ---- oracle said ----"); print("     " + r.stdout.replace("\n", "\n     "))
    return good

results = []

print("=== (a) NEGATIVE CONTROLS — each breaks the artifact the way the oracle claims to catch ===")

d = base(); d["provenance"]["run_id"] = 999999999999
d["provenance"]["run_url"] = "https://github.com/theshin621/foundry/actions/runs/999999999999"
results.append(run(d, "N1 invented run id", "FAIL"))

d = base(); d["fetched_utc"] = "2026-08-05T02:20:00Z"
results.append(run(d, "N2 stale artifact (5 days old)", "FAIL"))

d = base(); del d["stats"]
results.append(run(d, "N3 ok:true with no numbers", "FAIL"))

d = base(); d["ok"] = False; d["error"] = "timeout"
results.append(run(d, "N4 ok:false still carrying numbers", "FAIL"))

d = base(); d["stats"] = "<!doctype html><html><body>404 Not Found</body></html>"
results.append(run(d, "N5 served error page stored as the instrument", "FAIL"))

d = base(); d["ok"] = False; d["stats"] = None; d["error"] = ""
results.append(run(d, "N6 failure with no stated reason", "FAIL"))

d = base(); d["source_url"] = "https://tailorfarms.com/"
results.append(run(d, "N7 read the wrong endpoint", "FAIL"))

d = base(); d["fetched_utc"] = "2026-08-11T09:00:00Z"
results.append(run(d, "N8 timestamp in the future", "FAIL"))

d = base(); del d["provenance"]["head_sha"]
results.append(run(d, "N9 provenance missing head_sha", "FAIL"))

print()
print("=== (b) INDEPENDENT BREAK ATTEMPTS — trying to get invented numbers PAST the oracle ===")

# B1 — LAUNDERING. The realistic attack, and the one that shaped the oracle.
d = base()
d["stats"] = {"/": {"2026-08-09": 412}, "/005-maccleaner/": {"2026-08-09": 388}}   # numbers nobody measured
d["provenance"].update(REAL_BUT_WRONG_WORKFLOW)
results.append(run(d, "B1 real run id, wrong workflow (laundering)", "FAIL"))

# B2 — laundering with the workflow_path field corrected to lie about which workflow it was.
d = base()
d["stats"] = {"/": {"2026-08-09": 412}}
d["provenance"].update(REAL_BUT_WRONG_WORKFLOW)
d["provenance"]["workflow_path"] = ".github/workflows/health-check.yml"
results.append(run(d, "B2 laundering + self-consistent wrong workflow", "FAIL"))

# B3 — real run, real workflow claim, but head_sha swapped to a commit the run never saw.
d = base()
d["provenance"].update(REAL_BUT_WRONG_WORKFLOW)
d["provenance"]["head_sha"] = "da781f2000000000000000000000000000000000"
results.append(run(d, "B3 real run id with mismatched head_sha", "FAIL"))

# B4 — empty-but-valid instrument. NOT a break: zero visits is a TRUE reading and must
#      satisfy every content predicate. The oracle must not confuse "no traffic" with "no
#      measurement" — that conflation would make every honest quiet day look like an outage.
#      Asserted on PREDICATES, not on exit code: this fixture carries deliberately fake
#      provenance (run_id 1), so P6 must and does reject it. The claim under test is
#      narrower — that P1-P5 all hold on an empty payload.
def predicates(doc, label):
    import tempfile as _t
    with _t.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(doc, f); p = f.name
    r = subprocess.run([sys.executable, ORACLE, p, "--now", NOW], capture_output=True, text=True)
    os.unlink(p)
    content_fails = [l for l in r.stdout.splitlines() if l.strip().startswith("FAIL") and "P6" not in l]
    good = not content_fails
    print("%s  %-46s expected %-14s got %-14s" % ("[ok] " if good else "[!!] ", label,
          "no P1-P5 fail", "clean" if good else "%d content fail(s)" % len(content_fails)))
    for l in content_fails: print("    ", l.strip())
    return good

d = base(); d["stats"] = {}
results.append(predicates(d, "B4 genuinely empty stats (quiet day != outage)"))

# B5 — the last honest question: can a REAL beacon-stats run be replayed tomorrow, i.e. can a
#      fire re-commit yesterday's provably-real artifact and call it today's reading? P5.stale
#      is the only thing standing between the loop and that, so it is checked at the boundary.
d = base(); d["fetched_utc"] = "2026-08-08T20:29:00Z"      # 30.0h before NOW - just inside
results.append(run(d, "B5a 29.99h old (inside window, P5 must not fire)", "FAIL"))   # fails P6 only
d = base(); d["fetched_utc"] = "2026-08-08T20:00:00Z"      # 30.5h - just outside
import subprocess as _sp, tempfile as _tf
with _tf.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    json.dump(d, f); _p = f.name
_r = _sp.run([sys.executable, ORACLE, _p, "--now", NOW], capture_output=True, text=True); os.unlink(_p)
_hit = any("P5.stale" in l for l in _r.stdout.splitlines())
print("%s  %-46s expected %-14s got %-14s" % ("[ok] " if _hit else "[!!] ",
      "B5b 30.5h old (outside window, P5.stale must fire)", "P5.stale", "P5.stale" if _hit else "silent"))
results.append(_hit)

print()
ok = all(results)
print("PROBE RESULT: %s  (%d/%d)" % ("the oracle caught every break attempted" if ok else "THE ORACLE HAS A HOLE", sum(results), len(results)))
sys.exit(0 if ok else 1)
