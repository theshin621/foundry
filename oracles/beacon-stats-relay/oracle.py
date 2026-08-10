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
REQUIRED_PROV = {"run_id", "run_url", "run_attempt", "repo", "workflow_path", "head_sha"}

fails, notes = [], []
def check(cond, pid, msg):
    if cond: notes.append("  ok   %s" % pid)
    else:    fails.append("  FAIL %s — %s" % (pid, msg))
    return cond

def iso(s):
    try: return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except Exception: return None

def gh(path, token):
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
        if "head_branch" in prov:
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
    real_path = os.path.relpath(os.path.abspath(path), ROOT)
    if real_path != ARTIFACT_PATH:
        notes.append("  --   P7 skipped — %s is a fixture, not the tracked artifact" % real_path)
    else:
        try:
            _, commits = gh("/repos/%s/commits?path=%s&sha=%s&per_page=1"
                            % (REPO, ARTIFACT_PATH, run.get("head_branch") or "main"), tok)
        except Exception as e:
            print("\n".join(notes + fails))
            print("VERDICT: CANNOT-CERTIFY — could not read the artifact's commit history (%s)." % type(e).__name__)
            return 2
        if not commits:
            fails.append("  FAIL P7.commit — GitHub has no commit touching %s on this branch" % ARTIFACT_PATH)
        else:
            c = commits[0]
            ver = c.get("commit", {}).get("verification", {})
            # THE control. A `git push` with the loop's PAT produces verified=false.
            check(ver.get("verified") is True, "P7.signed",
                  "the commit carrying these numbers is NOT GitHub-signed (reason %r) — it was "
                  "pushed by a token, not created through the Contents API, so the bytes are unattested"
                  % ver.get("reason"))
            check(ver.get("reason") == "valid", "P7.reason", "signature reason is %r" % ver.get("reason"))
            check((c.get("commit", {}).get("message") or "").startswith("beacon: instrument reading"),
                  "P7.msg", "commit message is %r" % (c.get("commit", {}).get("message") or "")[:60])
            # The bytes on disk must BE the bytes in that signed commit.
            try:
                import subprocess
                local_blob = subprocess.run(["git", "hash-object", path], capture_output=True,
                                            text=True, cwd=ROOT).stdout.strip()
                _, cont = gh("/repos/%s/contents/%s?ref=%s" % (REPO, ARTIFACT_PATH, c["sha"]), tok)
                check(cont.get("sha") == local_blob, "P7.bytes",
                      "local artifact blob %s != signed-commit blob %s — the working copy has been "
                      "edited since GitHub signed it" % (local_blob[:10], str(cont.get("sha"))[:10]))
            except Exception as e:
                fails.append("  FAIL P7.bytes — could not compare blobs: %s: %s" % (type(e).__name__, e))

    print("\n".join(notes + fails))
    if fails:
        print("VERDICT: FAIL (%d predicate(s))" % len(fails)); return 1
    print("VERDICT: PASS — artifact is fresh, internally consistent, produced by Actions run %s of "
          "%s at %s, and its exact bytes arrived in a commit GitHub itself signed."
          % (prov.get("run_id"), WORKFLOW_PATH, (prov.get("head_sha") or "")[:7]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
