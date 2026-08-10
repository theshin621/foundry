#!/usr/bin/env python3
"""
lib/beacon_stats.py — the ONE way a fire reads its own instrument.
Reusable piece for BUILDER's "one reusable piece to lib/" rule.

The rule this enforces (PLAYBOOK §6): every ledger signal block is instrument-read,
never claimed, never hand-invented; if the instrument is unreachable, write
{"error": "<why>", "as_of": <ts>} rather than null.

Reading the relay artifact directly is the mistake this module exists to prevent:
public/beacon-stats.json is a plain file in a repo the loop can write to, so its mere
presence proves nothing. This module never returns numbers the oracle has not blessed.
It shells out to oracles/beacon-stats-relay/oracle.py and maps the verdict:

    PASS            -> {"as_of":…, "source":"…", "stats":{…}, "verdict":"PASS", …}
    FAIL            -> {"error": "<the oracle's own failing predicates>", "as_of":…}
    CANNOT-CERTIFY  -> {"error": "oracle could not establish ground truth: …", "as_of":…}
    missing file    -> {"error": "no relay artifact: …", "as_of":…}

An error block is a legitimate, honest ledger value. A number this module did not
verify is not.
"""
import datetime, json, os, subprocess, sys

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACT = os.path.join(ROOT, "public", "beacon-stats.json")
ORACLE   = os.path.join(ROOT, "oracles", "beacon-stats-relay", "oracle.py")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read(artifact=ARTIFACT, max_age_h=None):
    """Return a ledger-ready signal block. NEVER raises, NEVER returns None."""
    now = _now()
    if not os.path.exists(artifact):
        return {"error": "no relay artifact at %s — the beacon-stats workflow has not "
                         "committed a reading yet" % os.path.relpath(artifact, ROOT),
                "as_of": now}
    if not os.path.exists(ORACLE):
        return {"error": "oracle missing at %s — an unverified artifact is not a reading"
                         % os.path.relpath(ORACLE, ROOT), "as_of": now}

    cmd = [sys.executable, ORACLE, artifact]
    if max_age_h is not None:
        cmd += ["--max-age-h", str(max_age_h)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except Exception as e:
        return {"error": "oracle did not complete: %s: %s" % (type(e).__name__, e), "as_of": now}

    failing = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("FAIL")]

    if r.returncode == 1:
        return {"error": "relay artifact REJECTED by its oracle — " +
                         ("; ".join(failing) or "no detail"), "as_of": now}
    if r.returncode == 2:
        verdict = next((l for l in r.stdout.splitlines() if l.startswith("VERDICT")), "CANNOT-CERTIFY")
        return {"error": "oracle could not establish ground truth: " + verdict.strip(), "as_of": now}
    if r.returncode != 0:
        return {"error": "oracle exited %d unexpectedly" % r.returncode, "as_of": now}

    d = json.load(open(artifact))
    if not d.get("ok"):
        # A PASS on an ok:false artifact means the relay honestly recorded a failed read.
        # That is a real measurement of a real outage and is reported as an error block.
        return {"error": "beacon endpoint unreadable at %s: %s"
                         % (d.get("fetched_utc"), d.get("error")),
                "as_of": now, "http": d.get("http"),
                "provenance": d.get("provenance", {}).get("run_url")}

    return {
        "as_of": d["fetched_utc"],
        "read_at": now,
        "source": d["source_url"],
        "verdict": "PASS",
        "provenance": d.get("provenance", {}).get("run_url"),
        "stats": d.get("stats"),
    }


def qualified_visits(block, path=None, days=None):
    """Sum visits from a PASS block. Returns None if the block is an error block —
    a caller must not silently treat 'unmeasured' as zero."""
    if not isinstance(block, dict) or block.get("verdict") != "PASS":
        return None
    stats = block.get("stats")
    if not isinstance(stats, dict):
        return None
    total = 0
    for p, byday in stats.items():
        if path is not None and p != path:
            continue
        if not isinstance(byday, dict):
            continue
        for day, n in byday.items():
            if days is not None and day not in days:
                continue
            if isinstance(n, int):
                total += n
    return total


if __name__ == "__main__":
    print(json.dumps(read(), indent=1))
