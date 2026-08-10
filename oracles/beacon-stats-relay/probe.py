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
NOW    = "2026-08-10T02:50:00Z"

# ROUND 1 findings 3 & 4 — THE PROBE ITSELF WAS THE DEFECT, and this is the correction.
# Every N-control was built on a fixture carrying run_id 1, which does not exist, so P6.exists
# fired on all of them regardless of whether the predicate the control claimed to isolate was
# even present. Four controls (N2/N4/N7/N8) would have reported [ok] with their target
# predicates DELETED from the oracle. A probe that goes red for the wrong reason is worse than
# no probe: it manufactures confidence. Two changes fix it:
#   1. base() now quotes a REAL, successful beacon-stats.yml run, so P6 is satisfied and each
#      control fails on -- and only on -- the predicate it targets.
#   2. run() now asserts the TARGET PREDICATE ID appears in the oracle's failure list, not
#      merely that the exit code was non-zero.

# A REAL health-check.yml run (wrong workflow) — the laundering fixture.
REAL_BUT_WRONG_WORKFLOW = {
    "run_id": 31349144686,
    "run_url": "https://github.com/theshin621/foundry/actions/runs/31349144686",
    "head_sha": "12a99fb2fdd338fe418a91e198c09b1ca4ecb0e4",
}
# A REAL beacon-stats.yml run, conclusion success, branch infra/beacon-stats-relay,
# window 02:24:43Z..02:24:54Z. This is the fixture the N-controls now build on so that
# P6 is genuinely satisfied and cannot mask the predicate under test.
REAL_RIGHT_WORKFLOW = {
    "run_id": 31349720900,
    "run_url": "https://github.com/theshin621/foundry/actions/runs/31349720900",
    "head_sha": "e6a0681868b6e801edc39c486a9d5f650f667266",
    "head_branch": "infra/beacon-stats-relay",
}

def base():
    return {
        "fetched_utc": "2026-08-10T02:24:49Z",
        "source_url": "https://tailorfarms.com/_b/stats",
        "http": 200, "ok": True,
        "stats": {"/": {"2026-08-09": 4}, "/005-maccleaner/": {"2026-08-09": 2}},
        "provenance": dict(REAL_RIGHT_WORKFLOW, run_attempt=1, repo="theshin621/foundry",
                           workflow_path=".github/workflows/beacon-stats.yml",
                           runner="ubuntu-latest"),
    }

def run(doc, label, expect, target=None):
    """expect: the verdict. target: the predicate id this control claims to isolate.

    If `target` is given, the control only counts when that predicate is among the FAILING
    ones. Without this, a control can pass for a reason it was never testing — round 1
    finding 3, which is why this argument exists.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(doc, f); p = f.name
    r = subprocess.run([sys.executable, ORACLE, p, "--now", NOW], capture_output=True, text=True)
    os.unlink(p)
    got = {0: "PASS", 1: "FAIL", 2: "CANNOT-CERTIFY"}.get(r.returncode, "?%d" % r.returncode)
    failed = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("FAIL")]
    hit = (target is None) or any(target in l for l in failed)
    good = (got == expect) and hit
    why = "" if hit else "  <-- fired on %s, NOT on %s" % ([l.split()[1] for l in failed] or ["nothing"], target)
    print("%s  %-46s expected %-8s got %-8s isolates %-12s%s"
          % ("[ok] " if good else "[!!] ", label, expect, got, target or "-", why))
    if not good:
        print("     ---- oracle said ----"); print("     " + r.stdout.replace("\n", "\n     "))
    return good

results = []

print("=== (a) NEGATIVE CONTROLS — each breaks the artifact the way the oracle claims to catch ===")

d = base(); d["provenance"]["run_id"] = 999999999999
d["provenance"]["run_url"] = "https://github.com/theshin621/foundry/actions/runs/999999999999"
results.append(run(d, "N1 invented run id", "FAIL", "P6.exists"))

d = base(); d["fetched_utc"] = "2026-08-05T02:24:49Z"
results.append(run(d, "N2 stale artifact (5 days old)", "FAIL", "P5.stale"))

d = base(); del d["stats"]
results.append(run(d, "N3 ok:true with no numbers", "FAIL", "P2.data"))

d = base(); d["ok"] = False; d["error"] = "timeout"
results.append(run(d, "N4 ok:false still carrying numbers", "FAIL", "P2.nodata"))

d = base(); d["stats"] = "<!doctype html><html><body>404 Not Found</body></html>"
results.append(run(d, "N5 served error page stored as the instrument", "FAIL", "P4.json"))

d = base(); d["ok"] = False; d["stats"] = None; d["error"] = ""
results.append(run(d, "N6 failure with no stated reason", "FAIL", "P2.why"))

d = base(); d["source_url"] = "https://tailorfarms.com/"
results.append(run(d, "N7 read the wrong endpoint", "FAIL", "P3.url"))

d = base(); d["fetched_utc"] = "2026-08-11T09:00:00Z"   # also outside the run window; P5.future is the claim
results.append(run(d, "N8 timestamp in the future", "FAIL", "P5.future"))

d = base(); del d["provenance"]["head_sha"]
results.append(run(d, "N9 provenance missing head_sha", "FAIL", "P1.prov"))

print()
print("=== (b) INDEPENDENT BREAK ATTEMPTS — trying to get invented numbers PAST the oracle ===")

# B1 — LAUNDERING. The realistic attack, and the one that shaped the oracle.
d = base()
d["stats"] = {"/": {"2026-08-09": 412}, "/005-maccleaner/": {"2026-08-09": 388}}   # numbers nobody measured
d["provenance"].update(REAL_BUT_WRONG_WORKFLOW)
results.append(run(d, "B1 real run id, wrong workflow (laundering)", "FAIL", "P6.workflow"))

# B2 — laundering with the workflow_path field corrected to lie about which workflow it was.
d = base()
d["stats"] = {"/": {"2026-08-09": 412}}
d["provenance"].update(REAL_BUT_WRONG_WORKFLOW)
d["provenance"]["workflow_path"] = ".github/workflows/health-check.yml"
results.append(run(d, "B2 laundering + self-consistent wrong workflow", "FAIL", "P6.workflow"))

# B3 — ROUND 1 FINDING 4: this fixture used to quote the WRONG workflow, so P6.workflow
# stopped it and P6.sha — named in this file's own header as load-bearing — had zero
# independent coverage. It now quotes the REAL beacon-stats run with only head_sha swapped,
# which is the only way to actually exercise P6.sha.
d = base()
d["provenance"]["head_sha"] = "da781f2000000000000000000000000000000000"
results.append(run(d, "B3 real run id with mismatched head_sha", "FAIL", "P6.sha"))

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
