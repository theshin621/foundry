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
print("=== (c) P7/P8 CONTROLS ON THE REAL TRACKED ARTIFACT ===")
print("    ROUND 2 finding 3: every fixture above is a tempfile, so P7/P8 were skipped and the")
print("    probe reported 15/15 while never exercising the round's headline fix. These controls")
print("    mutate the tracked artifact, assert the oracle goes red, and restore it byte-for-byte.")

import shutil
REAL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "public", "beacon-stats.json")

def on_real(mutate, label, target):
    if not os.path.exists(REAL):
        print("[--]   %-46s skipped — no tracked artifact present" % label); return True
    backup = REAL + ".probe-backup"
    shutil.copy2(REAL, backup)
    try:
        doc = json.load(open(REAL))
        mutate(doc)
        json.dump(doc, open(REAL, "w"), indent=1, sort_keys=True)
        r = subprocess.run([sys.executable, ORACLE, REAL], capture_output=True, text=True)
        failed = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("FAIL")]
        hit = any(target in l for l in failed)
        print("%s  %-46s expected FAIL    got %-8s isolates %s"
              % ("[ok] " if hit else "[!!] ", label,
                 {0: "PASS", 1: "FAIL", 2: "CANNOT"}.get(r.returncode, "?"), target))
        if not hit:
            print("     ---- oracle said ----"); print("     " + r.stdout.replace("\n", "\n     "))
        return hit
    finally:
        shutil.move(backup, REAL)

def _bump(d): d["stats"].setdefault("paths", {})["/"] = {"2026-08-09": 999999}
results.append(on_real(_bump, "C1 numbers edited in the tracked artifact", "P7.bytes"))

def _wipe(d): d["stats"] = {"paths": {}}
results.append(on_real(_wipe, "C2 payload emptied in the tracked artifact", "P7.bytes"))

# C3 proves P8 is load-bearing and not merely present: with the bytes intact, P7 passes and
# only the runner's stamp can disagree, so we assert the oracle is currently satisfied.
if os.path.exists(REAL):
    r = subprocess.run([sys.executable, ORACLE, REAL], capture_output=True, text=True)
    p8 = [l for l in r.stdout.splitlines() if "P8." in l]
    good = r.returncode == 0 and any("ok" in l for l in p8) and len(p8) >= 3
    print("%s  %-46s expected PASS    got %-8s P8 predicates: %d"
          % ("[ok] " if good else "[!!] ", "C3 untouched artifact still certifies (P8 live)",
             {0: "PASS", 1: "FAIL", 2: "CANNOT"}.get(r.returncode, "?"), len(p8)))
    if not good: print("     " + r.stdout.replace("\n", "\n     "))
    results.append(good)

print()
print("=== (d) API-SIDE CONTROLS — the ten predicates ROUND 3 found untested ===")
print("    P6.branch and every P7/P8 predicate take their input from GitHub, not from the file,")
print("    so no file fixture can make them fire. probe.py used to report 18/18 while ten of the")
print("    round's headline checks had zero coverage. These drive them through the oracle's fenced")
print("    fake-API seam, which can never return exit 0.")

def _live():
    """Build a canned API bundle that mirrors the truth, so each mutation isolates one predicate."""
    import urllib.request
    for k in ("https_proxy","HTTPS_PROXY","http_proxy","HTTP_PROXY","all_proxy","ALL_PROXY","GLOBAL_AGENT_HTTPS_PROXY"):
        os.environ.pop(k, None)
    tok = json.load(open("/home/claude/foundry/config.json"))["github_pat"]
    def g(pth):
        r = urllib.request.urlopen(urllib.request.Request(
            "https://api.github.com" + pth,
            headers={"User-Agent": "probe", "Accept": "application/vnd.github+json",
                     "Authorization": "Bearer " + tok}), timeout=30)
        return json.load(r)
    art = json.load(open(REAL))
    prov = art["provenance"]
    run = g("/repos/theshin621/foundry/actions/runs/%s" % prov["run_id"])
    commits = g("/repos/theshin621/foundry/commits?path=public/beacon-stats.json&sha=%s&per_page=20"
                % run["head_branch"])
    blob = subprocess.run(["git", "hash-object", REAL], capture_output=True, text=True,
                          cwd=os.path.dirname(os.path.dirname(HERE))).stdout.strip()
    # find the commit carrying these bytes, same rule the oracle uses
    target_sha = None
    for cand in commits[:20]:
        c = g("/repos/theshin621/foundry/contents/public/beacon-stats.json?ref=%s" % cand["sha"])
        if c.get("sha") == blob:
            target_sha = cand["sha"]; break
    crs = g("/repos/theshin621/foundry/commits/%s/check-runs" % target_sha) if target_sha else {"check_runs": []}
    return {"run": run, "commits": commits, "contents": {"sha": blob}, "checkruns": crs}

try:
    BASE = _live()
except Exception as e:
    BASE = None
    print("[--]   section (d) skipped — could not build the live bundle: %s: %s" % (type(e).__name__, e))

def api_control(mutate, label, target):
    import copy, tempfile as _t
    bundle = copy.deepcopy(BASE)
    mutate(bundle)
    with _t.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(bundle, f); fp = f.name
    env = dict(os.environ, FOUNDRY_ORACLE_FAKE_API=fp)
    r = subprocess.run([sys.executable, ORACLE, REAL], capture_output=True, text=True, env=env)
    os.unlink(fp)
    failed = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("FAIL")]
    hit = any(target in l for l in failed)
    print("%s  %-46s expected FAIL    isolates %s" % ("[ok] " if hit else "[!!] ", label, target))
    if not hit:
        print("     fired on: %s" % ([l.split()[1] for l in failed] or ["nothing"]))
        print("     " + r.stdout.splitlines()[-1] if r.stdout else "")
    return hit

if BASE:
    # sanity: an unmutated bundle must reach SIMULATED-PASS (exit 3), never 0
    with __import__("tempfile").NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(BASE, f); _bp = f.name
    _r = subprocess.run([sys.executable, ORACLE, REAL], capture_output=True, text=True,
                        env=dict(os.environ, FOUNDRY_ORACLE_FAKE_API=_bp))
    os.unlink(_bp)
    _fenced = _r.returncode == 3 and "SIMULATED" in _r.stdout
    print("%s  %-46s expected exit 3, got %d  (the seam can never certify)"
          % ("[ok] " if _fenced else "[!!] ", "D0 fake mode is fenced", _r.returncode))
    results.append(_fenced)

    def m(fn):
        return fn
    CONTROLS = [
        ("D1  run belongs to another repo",        lambda b: b["run"]["repository"].__setitem__("full_name", "someone/else"), "P6.repo"),
        ("D2  run is a different workflow",        lambda b: b["run"].__setitem__("path", ".github/workflows/health-check.yml"), "P6.workflow"),
        ("D3  run head_sha mismatched",            lambda b: b["run"].__setitem__("head_sha", "0"*40), "P6.sha"),
        ("D4  run did not conclude success",       lambda b: b["run"].__setitem__("conclusion", "failure"), "P6.concl"),
        ("D5  run is still in progress",           lambda b: b["run"].__setitem__("conclusion", None), "P6.concl"),
        ("D6  run branch != artifact branch",      lambda b: b["run"].__setitem__("head_branch", "some-other-branch"), "P6.branch"),
        ("D7  reading outside the run's window",   lambda b: b["run"].__setitem__("created_at", "2026-01-01T00:00:00Z") or b["run"].__setitem__("updated_at", "2026-01-01T00:01:00Z"), "P7.window"),
        ("D8  no commit touches the artifact",     lambda b: b.__setitem__("commits", []), "P7.commit"),
        ("D9  no commit carries these bytes",      lambda b: b.__setitem__("contents", {"sha": "f"*40}), "P7.bytes"),
        ("D10 commit is not GitHub-signed",        lambda b: b["commits"][0]["commit"]["verification"].update({"verified": False, "reason": "unsigned"}), "P7.signed"),
        ("D11 signature reason not valid",         lambda b: b["commits"][0]["commit"]["verification"].__setitem__("reason", "unknown_key"), "P7.reason"),
        ("D12 wrong commit message",               lambda b: b["commits"][0]["commit"].__setitem__("message", "chore: something else"), "P7.msg"),
        ("D13 no runner attestation",              lambda b: b["checkruns"].__setitem__("check_runs", []), "P8.exists"),
        ("D14 attestation from another app",       lambda b: [c for c in b["checkruns"]["check_runs"] if c["name"]=="beacon-stats-attestation"][0]["app"].__setitem__("slug", "some-other-app"), "P8.app"),
        ("D15 attestation did not succeed",        lambda b: [c for c in b["checkruns"]["check_runs"] if c["name"]=="beacon-stats-attestation"][0].__setitem__("conclusion", "failure"), "P8.concl"),
        ("D16 attested digest is a different file",lambda b: [c for c in b["checkruns"]["check_runs"] if c["name"]=="beacon-stats-attestation"][0]["output"].update({"title":"sha256=%s"%("a"*64),"summary":"sha256=%s"%("a"*64)}), "P8.digest"),
        ("D17 two attestations, order undefined",  lambda b: b["checkruns"]["check_runs"].append(dict([c for c in b["checkruns"]["check_runs"] if c["name"]=="beacon-stats-attestation"][0])), "P8.unique"),
    ]
    for label, mut, tgt in CONTROLS:
        results.append(api_control(mut, label, tgt))

print()
ok = all(results)
print("PROBE RESULT: %s  (%d/%d)" % ("the oracle caught every break attempted" if ok else "THE ORACLE HAS A HOLE", sum(results), len(results)))
sys.exit(0 if ok else 1)
