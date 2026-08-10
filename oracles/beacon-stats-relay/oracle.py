#!/usr/bin/env python3
"""
ORACLE — beacon-stats-relay  (written BEFORE the artifact, per v4 oracle-before-code)

THE CLAIM UNDER TEST
    "A scheduled, unattended fire can read the LIVE numbers from
     https://tailorfarms.com/_b/stats out of this repository."

WHY THIS ORACLE EXISTS IN THIS SHAPE
    BOTTLENECKS.md #1's terminal lesson: for a liveness claim, do not hand-write a band
    of logic that PREDICTS what the real system did — observe the real system. For markup
    that meant executing the page in Chromium. Here the claim is not about markup, it is
    about PROVENANCE: did a machine outside this sandbox actually reach the live origin,
    or did a fire in this sandbox write plausible numbers into a file?

    Those two are byte-indistinguishable in the artifact. So the oracle does not inspect
    the numbers at all. It asks GITHUB whether the run that produced them exists
    (api.github.com, authenticated), and whether that run was THIS workflow at THIS commit.
    ROUND 1 (checker FAIL, 2026-08-10) proved the first version of that argument answered the
    wrong question. Manufacturing a run is unnecessary: a run's provenance block is PUBLIC and
    re-quotable, so editing `stats` while keeping provenance byte-identical passed cleanly. The
    oracle proved a run EXISTED; it never bound the BYTES to it.

    P7 is the fix, and it moves the unforgeable thing from the run to the commit. The relay now
    writes the reading through GitHub's Contents API, which makes GitHub GPG-sign the commit
    (`verification.verified == true`, web-flow key). The loop's PAT pushes UNVERIFIED commits and
    cannot produce that signature -- GitHub holds the key, not the caller. So P7 asks GitHub
    whether IT signed the commit these exact bytes arrived in. A hand-edited artifact answers no.
    That is this oracle's equivalent of "execute it in a real browser": observe the real system,
    do not predict it.

VERDICTS
    PASS            every predicate held
    FAIL            a predicate was violated  (the artifact is not trustworthy)
    CANNOT-CERTIFY  the oracle could not reach its own ground truth (no token / API down).
                    Borrowed from lib/checks/html_structure.py: an oracle that cannot see
                    must decline to bless, not default to green.

USAGE
    python3 oracles/beacon-stats-relay/oracle.py <artifact.json> [--now ISO8601] [--max-age-h N]
    exit 0 = PASS · 1 = FAIL · 2 = CANNOT-CERTIFY
"""
import json, os, re, sys, datetime, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO          = "theshin621/foundry"
WORKFLOW_PATH = ".github/workflows/beacon-stats.yml"
SOURCE_URL    = "https://tailorfarms.com/_b/stats"
MAX_AGE_H     = 30          # the fire is daily; >30h means a run was skipped or is failing

REQUIRED_TOP  = {"fetched_utc", "source_url", "http", "ok", "provenance"}
ARTIFACT_PATH = "public/beacon-stats.json"
REQUIRED_PROV = {"run_id", "run_url", "run_attempt", "repo", "workflow_path", "head_sha", "head_branch"}

fails, notes = [], []
def check(cond, pid, msg):
    if cond: notes.append("  ok   %s" % pid)
    else:    fails.append("  FAIL %s — %s" % (pid, msg))
    return cond

def iso(s):
    try: return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except Exception: return None

# ---------------------------------------------------------------------------
# TEST SEAM. ROUND 3 finding 3: ten predicates (P6.branch, all of P7 and P8) had no
# negative control, because their inputs come from GitHub rather than from the file.
# probe.py can now feed canned API responses through this seam and prove each one
# fires. The seam is fenced so it can never be a bypass: in fake mode the oracle
# NEVER returns 0. A clean run returns 3 and prints SIMULATED, and lib/beacon_stats.py
# treats any non-zero exit as "no numbers".
# ---------------------------------------------------------------------------
FAKE = os.environ.get("FOUNDRY_ORACLE_FAKE_API")


def gh(path, token):
    if FAKE:
        canned = json.load(open(FAKE))
        # Fidelity limit, named so nobody mistakes D-series coverage for walk coverage:
        # the canned /contents/ responder IGNORES ?ref and returns one fixed blob, so the
        # seam cannot exercise "skip a wrong newer candidate to reach the right older one".
        # That behaviour is covered against real historical commits instead.
        if "/check-runs" in path:      return 200, canned.get("checkruns", {"check_runs": []})
        if "/commits?" in path:        return 200, canned.get("commits", [])
        if "/contents/" in path:       return 200, canned.get("contents", {})
        return 200, canned.get("run", {})
    return _gh_real(path, token)


def _gh_real(path, token):
    for k in ("https_proxy","HTTPS_PROXY","http_proxy","HTTP_PROXY","all_proxy","ALL_PROXY","GLOBAL_AGENT_HTTPS_PROXY"):
        os.environ.pop(k, None)
    req = urllib.request.Request("https://api.github.com" + path, headers={
        "User-Agent": "foundry-oracle", "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, json.load(r)

def token():
    t = os.environ.get("FOUNDRY_PAT")
    if t: return t
    for p in ("/home/claude/foundry/config.json", "./config.json"):
        try:
            v = json.load(open(p)).get("github_pat", "")
            if v and not v.startswith("<"): return v
        except Exception: pass
    return None

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    now_s = None; max_age = MAX_AGE_H
    for i, a in enumerate(sys.argv):
        if a == "--now":       now_s   = sys.argv[i+1]
        if a == "--max-age-h": max_age = float(sys.argv[i+1])
    if not args:
        print("usage: oracle.py <artifact.json> [--now ISO] [--max-age-h N]"); return 2
    path = args[0]
    now = iso(now_s) if now_s else datetime.datetime.now(datetime.timezone.utc)

    # P0 — the artifact exists and is JSON at all.
    try:
        raw = open(path, "rb").read().decode("utf-8", "replace")
        d = json.loads(raw)
    except FileNotFoundError:
        print("FAIL P0 — artifact missing: %s" % path); return 1
    except Exception as e:
        print("FAIL P0 — artifact is not valid JSON: %s" % e); return 1
    check(isinstance(d, dict), "P0.type", "top level is not an object")
    if not isinstance(d, dict):
        print("\n".join(fails)); print("VERDICT: FAIL"); return 1

    # P1 — schema.
    check(REQUIRED_TOP <= set(d), "P1.keys", "missing top-level keys: %s" % sorted(REQUIRED_TOP - set(d)))
    prov = d.get("provenance") if isinstance(d.get("provenance"), dict) else {}
    check(REQUIRED_PROV <= set(prov), "P1.prov", "missing provenance keys: %s" % sorted(REQUIRED_PROV - set(prov)))

    # P2 — no half-truths. A success must carry data; a failure must carry a reason.
    #      This is the predicate that stops "ok:true" from meaning "the file exists".
    ok = d.get("ok")
    check(isinstance(ok, bool), "P2.bool", "ok is not a boolean: %r" % (ok,))
    if ok is True:
        check("stats" in d and d["stats"] is not None, "P2.data", "ok:true but no stats payload")
        check("error" not in d or not d.get("error"), "P2.clean", "ok:true but an error is also recorded")
    elif ok is False:
        check(isinstance(d.get("error"), str) and d["error"].strip(), "P2.why", "ok:false with no error string")
        check("stats" not in d or d.get("stats") is None, "P2.nodata", "ok:false but stats present — a failed read must not carry numbers")

    # P3 — the read was of the right thing.
    check(d.get("source_url") == SOURCE_URL, "P3.url", "source_url is %r, expected %r" % (d.get("source_url"), SOURCE_URL))
    check(isinstance(d.get("http"), int), "P3.http", "http status is not an integer: %r" % (d.get("http"),))
    if ok is True:
        check(d.get("http") == 200, "P3.200", "ok:true with http %r" % (d.get("http"),))

    # P4 — the payload is data, not a served error page. Guards the shape where the origin
    #      answers 200 with an HTML shell and the relay stores it as if it were the instrument.
    st = d.get("stats")
    if ok is True:
        check(isinstance(st, (dict, list)), "P4.json", "stats is not a JSON object/array (type %s) — an HTML body or a string is not the instrument" % type(st).__name__)
        blob = json.dumps(st)[:4000] if st is not None else ""
        check(not re.search(r"<\s*(html|head|body|!doctype)", blob, re.I), "P4.nothtml", "stats payload contains HTML markup")

    # P5 — freshness. A stale artifact read as current is the silent failure this whole
    #      relay exists to prevent: the loop would report last week's numbers as today's.
    ts = iso(d.get("fetched_utc", ""))
    check(ts is not None, "P5.parse", "fetched_utc unparseable: %r" % (d.get("fetched_utc"),))
    if ts:
        age_h = (now - ts).total_seconds() / 3600.0
        check(age_h >= -0.25, "P5.future", "fetched_utc is %.1fh in the future" % (-age_h))
        check(age_h <= max_age, "P5.stale", "artifact is %.1fh old, limit %.1fh" % (age_h, max_age))

    # P6 — GROUND TRUTH. The predicate the other five cannot substitute for.
    tok = token()
    if not tok:
        print("\n".join(notes + fails))
        print("VERDICT: CANNOT-CERTIFY — no token, so the run behind this artifact cannot be confirmed to exist.")
        return 2
    try:
        status, run = gh("/repos/%s/actions/runs/%s" % (REPO, prov.get("run_id")), tok)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            fails.append("  FAIL P6.exists — GitHub has no run %r. The numbers in this artifact were not produced by an Actions run." % (prov.get("run_id"),))
            status, run = None, {}
        else:
            print("\n".join(notes + fails))
            print("VERDICT: CANNOT-CERTIFY — GitHub API returned HTTP %s; ground truth unreachable." % e.code)
            return 2
    except Exception as e:
        print("\n".join(notes + fails))
        print("VERDICT: CANNOT-CERTIFY — GitHub API unreachable (%s); ground truth not established." % type(e).__name__)
        return 2

    if run:
        check(run.get("repository", {}).get("full_name") == REPO, "P6.repo", "run belongs to %r" % run.get("repository", {}).get("full_name"))
        # The break this oracle was built to survive: quoting a REAL run id from a DIFFERENT
        # workflow. Without this line, any health-check run id would launder invented numbers.
        check(run.get("path") == WORKFLOW_PATH, "P6.workflow", "run %s is workflow %r, not %r" % (prov.get("run_id"), run.get("path"), WORKFLOW_PATH))
        check(run.get("head_sha") == prov.get("head_sha"), "P6.sha", "run head_sha %r != artifact head_sha %r" % (run.get("head_sha"), prov.get("head_sha")))
        check(str(prov.get("run_id")) in str(prov.get("run_url", "")), "P6.url", "run_url does not contain run_id")
        # ROUND 1 finding 2: `None` means the run has not finished, so it cannot yet have
        # produced a committed reading. Accepting it let an in-progress run launder numbers.
        concl = run.get("conclusion")
        check(concl == "success", "P6.concl", "the producing run concluded %r (only 'success' is ground truth)" % concl)
        # ROUND 1 finding 6: the artifact's self-reported workflow_path was required to exist
        # but its VALUE was never checked, making it decorative. Check it.
        check(prov.get("workflow_path") == WORKFLOW_PATH, "P6.selfpath",
              "artifact self-reports workflow_path %r" % prov.get("workflow_path"))
        # ROUND 1 finding 7: the run's branch was never read, so the PASS line claimed more
        # than it checked. Record it and require the artifact to agree if it states one.
        branch = run.get("head_branch")
        # ROUND 2 finding 7: this was conditional on a key the workflow never wrote, so it was
        # dead code. The workflow now writes head_branch and the check is unconditional.
        check(prov.get("head_branch") == branch, "P6.branch",
              "artifact says branch %r, run says %r" % (prov.get("head_branch"), branch))
        # ROUND 1 finding 1 (temporal half): the reading must fall inside the run's own
        # execution window. Combined with P5.stale this means a forger must quote a run from
        # the last 30h AND land inside its ~1-minute window.
        c_at, u_at = iso((run.get("created_at") or "").replace("+00:00", "Z")), iso((run.get("updated_at") or "").replace("+00:00", "Z"))
        if ts and c_at and u_at:
            check(c_at - datetime.timedelta(minutes=2) <= ts <= u_at + datetime.timedelta(minutes=2),
                  "P7.window", "fetched_utc %s is outside run window %s..%s" % (d.get("fetched_utc"), run.get("created_at"), run.get("updated_at")))

    # ---------------------------------------------------------------------------
    # P7 — CONTENT BINDING. The predicate round 1 did not have, and the one that makes
    # the numbers themselves unforgeable rather than merely well-attributed.
    # ---------------------------------------------------------------------------
    # ROUND 2 finding 2: this used to SKIP P7 for any path other than the tracked one, which
    # reproduced round 1's original break verbatim on a copy. It now fails CLOSED: a fixture
    # cannot be blessed, it can only be declined.
    real_path = os.path.relpath(os.path.abspath(os.path.realpath(path)), ROOT)
    if real_path != ARTIFACT_PATH:
        print("\n".join(notes + fails))
        # A failure already found is still a failure; only a clean fixture is "cannot certify".
        if fails:
            print("VERDICT: FAIL (%d predicate(s)) — and P7/P8 could not run on a fixture." % len(fails))
            return 1
        print("VERDICT: CANNOT-CERTIFY — %s is not the tracked artifact (%s), so its bytes cannot "
              "be bound to a runner. Content predicates above are informational only."
              % (real_path, ARTIFACT_PATH))
        return 2
    else:
        # ROUND 3 finding 1: this used to take the MOST RECENT commit touching the path.
        # Every relay run writes a new one (fetched_utc differs each time), so a perfectly
        # good reading started FAILing the moment the next run landed — the oracle rejected
        # its own valid output on the loop's normal path. Fix: find the commit whose blob IS
        # these bytes, not the commit that happens to be newest.
        try:
            _, commits = gh("/repos/%s/commits?path=%s&sha=%s&per_page=20"
                            % (REPO, ARTIFACT_PATH, run.get("head_branch") or "main"), tok)
        except Exception as e:
            print("\n".join(notes + fails))
            print("VERDICT: CANNOT-CERTIFY — could not read the artifact's commit history (%s)." % type(e).__name__)
            return 2
        import subprocess
        local_blob = subprocess.run(["git", "hash-object", path], capture_output=True,
                                    text=True, cwd=ROOT).stdout.strip()
        # ROUND 4 finding 1: a bare `except: continue` here made a transient API error
        # indistinguishable from "these bytes don't match", so one 5xx on the candidate that
        # would have matched reported FAIL P7.bytes — an infrastructure blip dressed up as
        # tampering. Errors are now collected and reported as CANNOT-CERTIFY, never as FAIL.
        c = None
        walk_errors = []
        for cand in (commits or [])[:20]:
            try:
                _, cont = gh("/repos/%s/contents/%s?ref=%s" % (REPO, ARTIFACT_PATH, cand["sha"]), tok)
                if not isinstance(cont, dict):
                    walk_errors.append("%s: contents response was %s, not an object"
                                       % (cand["sha"][:8], type(cont).__name__))
                    continue
                cand_blob = cont.get("sha")
            except Exception as e:
                walk_errors.append("%s: %s: %s" % (cand["sha"][:8], type(e).__name__, e))
                continue
            if cand_blob == local_blob:
                c = cand
                break
        if c is None and walk_errors:
            print("\n".join(notes + fails))
            print("VERDICT: CANNOT-CERTIFY — the commit walk hit errors and no candidate matched, "
                  "so absence of a match is not evidence of tampering: %s" % "; ".join(walk_errors[:3]))
            return 2
        if not commits:
            fails.append("  FAIL P7.commit — GitHub has no commit touching %s on this branch" % ARTIFACT_PATH)
        elif c is None:
            fails.append("  FAIL P7.bytes — no commit on this branch carries these exact bytes (local blob %s). "
                         "The working copy was edited after GitHub last saw it." % local_blob[:10])
        else:
            ver = c.get("commit", {}).get("verification", {})
            # THE control. A `git push` with the loop's PAT produces verified=false.
            check(ver.get("verified") is True, "P7.signed",
                  "the commit carrying these numbers is NOT GitHub-signed (reason %r) — it was "
                  "pushed by a token, not created through the Contents API, so the bytes are unattested"
                  % ver.get("reason"))
            check(ver.get("reason") == "valid", "P7.reason", "signature reason is %r" % ver.get("reason"))
            check((c.get("commit", {}).get("message") or "").startswith("beacon: instrument reading"),
                  "P7.msg", "commit message is %r" % (c.get("commit", {}).get("message") or "")[:60])
            # P7.bytes is established by construction above: c is the commit whose blob
            # equals the local file. Recorded explicitly so the predicate appears in output.
            check(True, "P7.bytes", "")

            # -------------------------------------------------------------------
            # P8 — ACTOR PROOF. Round 2's severe finding, and the one both earlier
            # versions were missing: a GitHub signature proves the CHANNEL, never the
            # ACTOR, because GitHub signs every Contents-API commit whoever calls it.
            #
            # Measured in this repo with the loop's own fine-grained PAT:
            #     POST /repos/.../check-runs -> 403 "Resource not accessible by
            #                                   personal access token"
            #     GET  /repos/.../check-runs -> 200
            # The runner's GITHUB_TOKEN can create a check-run; the sandbox cannot.
            # So the runner stamps sha256(bytes) into a check-run and this predicate
            # reads it back. Forging it needs a credential the loop does not hold.
            # -------------------------------------------------------------------
            import hashlib
            want = hashlib.sha256(open(path, "rb").read()).hexdigest()
            try:
                _, cr = gh("/repos/%s/commits/%s/check-runs" % (REPO, c["sha"]), tok)
            except Exception as e:
                print("\n".join(notes + fails))
                print("VERDICT: CANNOT-CERTIFY — check-runs unreadable (%s)." % type(e).__name__)
                return 2
            att = [r for r in cr.get("check_runs", []) if r.get("name") == "beacon-stats-attestation"]
            if not att:
                fails.append("  FAIL P8.exists — no beacon-stats-attestation check-run on %s. The "
                             "bytes carry no runner stamp, so nothing proves a runner wrote them." % c["sha"][:8])
            else:
                check(len(att) == 1, "P8.unique",
                      "%d check-runs named beacon-stats-attestation on this commit; ordering is "
                      "undocumented so the right one cannot be chosen" % len(att))
                a = att[0]
                check(a.get("app", {}).get("slug") == "github-actions", "P8.app",
                      "attestation was created by app %r, not github-actions" % a.get("app", {}).get("slug"))
                check(a.get("conclusion") == "success", "P8.concl", "attestation concluded %r" % a.get("conclusion"))
                blob = "%s %s" % (a.get("output", {}).get("title") or "", a.get("output", {}).get("summary") or "")
                check(want in blob, "P8.digest",
                      "the runner attested a different sha256 than the bytes on disk (want %s)" % want[:16])

    print("\n".join(notes + fails))
    if fails:
        print("VERDICT: FAIL (%d predicate(s))" % len(fails)); return 1
    if FAKE:
        print("VERDICT: SIMULATED-PASS — fake API responses were in use; this is never a real "
              "certification and never exits 0.")
        return 3
    print("VERDICT: PASS — artifact is fresh, internally consistent, produced by Actions run %s of "
          "%s at %s, arrived in a commit GitHub signed, and carry a runner-only check-run stamp of their own sha256."
          % (prov.get("run_id"), WORKFLOW_PATH, (prov.get("head_sha") or "")[:7]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
