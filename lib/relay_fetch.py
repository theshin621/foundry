#!/usr/bin/env python3
"""
lib/relay_fetch.py — the fan-out reader for /_b/stats. Ship 013, 2026-08-12.
Oracle: oracles/013-stats-window-floor/oracle.mjs (predicate P8).

WHY THIS FILE EXISTS
--------------------
`.github/workflows/beacon-stats.yml` used to make ONE all-paths call to
https://tailorfarms.com/_b/stats and commit whatever came back. That worked while the
fleet was small and stopped working silently as it grew: the endpoint's budget is 44 KV
reads per invocation, so `paths x days` has to give somewhere. Ship 013 made the day
dimension inviolable (a 7-day floor, because MOD-2's threshold is defined on a
trailing-7 window) and made the PATH dimension absorb growth instead — declared, never
silent. That fixes the endpoint's honesty but not the relay's completeness: a single
all-paths call now returns a truthful answer about SIX paths and says so.

This module makes the committed artifact complete again. It reads the all-paths call,
and for every path the endpoint declares it omitted, it issues one bounded single-path
call (`?path=…&days=…`, 30 reads maximum) and merges the result. Each call is its own
Worker invocation with its own subrequest budget, so total coverage is independent of
fleet size. The endpoint stays bounded; the artifact stays whole.

WHAT IT WILL NOT DO
-------------------
It never writes a number it did not read. A path whose fan-out call fails is left OUT of
`stats.paths` and named in `stats.truncated.paths_omitted` with the reason — it is not
recorded as zero. "Unreadable" and "measured no visits" are different facts and the whole
instrument is worthless if they collapse into each other (lib/beacon_stats.py enforces
the same distinction on the reading side).

USAGE
    python3 lib/relay_fetch.py --source https://tailorfarms.com/_b/stats \
                               --out public/beacon-stats.json
    python3 lib/relay_fetch.py --source http://127.0.0.1:PORT/_b/stats --stdout

Provenance fields are read from the GitHub Actions environment exactly as the inline
script used to build them, so `oracles/beacon-stats-relay/oracle.py` keeps working
unchanged: the artifact shape is identical apart from the added `stats.fanout` block.
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "foundry-beacon-stats-relay"
TIMEOUT = 25
MAX_FANOUT = 60          # a hard stop; a fleet past this needs a paged relay, not a bigger loop
FLOOR_DAYS = 7           # MOD-2's trailing-7 window — the artifact must never be shorter


def as_dict(x):
    """x if it is a dict, else None.

    FIX CYCLE, checker round 1 finding 2 [medium]. The first draft guarded the top-level
    `paths` field with an isinstance check but reached `.get()` on `window`, `truncated`
    and the per-path payloads through `x or {}`, which only defends against None/falsy —
    a list, int, string or bool sails through and raises AttributeError. The module's own
    docstring promises it never raises, and a crash here is worse than a wrong number:
    the workflow step dies, the commit step is skipped, and the STALE artifact is left in
    place with nobody told. Fixed as a class rather than at the one site the checker
    named — every untrusted mapping now goes through this one door.
    """
    return x if isinstance(x, dict) else None


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def provenance():
    """Identical fields to the ones the inline workflow script wrote. Recorded even on a
    failed read — a failed reading must be as attributable as a good one."""
    return {
        "run_id": int(os.environ.get("GITHUB_RUN_ID", 0) or 0),
        "run_url": "%s/%s/actions/runs/%s" % (
            os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_RUN_ID", "")),
        "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", 1) or 1),
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "workflow_path": ".github/workflows/beacon-stats.yml",
        "head_sha": os.environ.get("GITHUB_SHA", ""),
        "head_branch": os.environ.get("GITHUB_REF_NAME", ""),
        "runner": "ubuntu-latest",
    }


def get_json(url):
    """(status, parsed_or_None, error_or_None). Never raises.

    A 200 carrying an HTML shell is NOT a reading, and `json.loads` succeeds on 'null',
    '42' and '"hi"' — both traps were found by the round-1 checker on the original relay
    and both are kept here rather than re-learned."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(2_000_000).decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        try:
            body = e.read(2_000_000).decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, None, "HTTP %s from the beacon endpoint" % e.code
    except Exception as e:
        return 0, None, "%s: %s" % (type(e).__name__, e)

    try:
        parsed = json.loads(body)
    except ValueError:
        return status, None, "body is not JSON (first 200 bytes: %r)" % body[:200]
    if not isinstance(parsed, (dict, list)):
        return status, None, ("body parsed as JSON but is %s, not an object/array"
                              % type(parsed).__name__)
    if status != 200:
        return status, None, "non-200 with a JSON body: HTTP %s" % status
    return status, parsed, None


def with_query(source, **params):
    parts = urllib.parse.urlsplit(source)
    q = dict(urllib.parse.parse_qsl(parts.query))
    q.update({k: str(v) for k, v in params.items()})
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path,
                                    urllib.parse.urlencode(q), parts.fragment))


def read(source):
    """Return the artifact dict the workflow commits."""
    out = {"fetched_utc": now_utc(), "source_url": source, "provenance": provenance()}

    status, base, err = get_json(source)
    out["http"] = status
    if err is not None:
        out["ok"] = False
        out["error"] = err
        return out

    if not isinstance(base, dict) or not isinstance(base.get("paths"), dict):
        out["ok"] = False
        out["error"] = ("all-paths read is not a stats payload (no `paths` object); got keys %s"
                        % sorted(base.keys())[:8] if isinstance(base, dict) else "not an object")
        return out

    window = as_dict(base.get("window"))
    if window is None:
        out["ok"] = False
        out["error"] = "endpoint returned a non-object `window`: %r" % (base.get("window"),)
        out["stats"] = None
        return out
    days = window.get("days")
    if not isinstance(days, int) or days < 1:
        out["ok"] = False
        out["error"] = "endpoint returned a malformed window: %r" % (window,)
        return out
    if days < FLOOR_DAYS:
        # The endpoint is contractually forbidden from doing this since ship 013. If it
        # happens the endpoint has regressed, and committing the short reading as if it
        # were fine is exactly the silent-degradation failure this ship removed.
        out["ok"] = False
        out["error"] = ("endpoint returned a %d-day window, below the %d-day floor the "
                        "trailing-7 metric is defined on" % (days, FLOOR_DAYS))
        out["stats"] = None
        return out

    truncated = as_dict(base.get("truncated")) or {}
    raw_omitted = truncated.get("paths_omitted")
    omitted = [p for p in raw_omitted if isinstance(p, str)] if isinstance(raw_omitted, list) else []

    fanout = {"requests": 0, "omitted_by_endpoint": list(omitted),
              "recovered": [], "unreadable": []}

    if len(omitted) > MAX_FANOUT:
        fanout["capped_at"] = MAX_FANOUT
        fanout["not_attempted"] = omitted[MAX_FANOUT:]
        omitted = omitted[:MAX_FANOUT]

    for path in omitted:
        url = with_query(source, path=path, days=days)
        st, one, e = get_json(url)
        fanout["requests"] += 1
        one_paths = as_dict(as_dict(one) and one.get("paths"))
        if e is not None or one_paths is None or not isinstance(one_paths.get(path), dict):
            fanout["unreadable"].append({"path": path,
                                         "error": e or "response did not contain a usable row for the path",
                                         "http": st})
            continue
        one_days = (as_dict(one.get("window")) or {}).get("days")
        if one_days != days:
            # Merging a different window would produce an artifact whose declared window
            # is a lie for some of its paths. Refuse the row rather than blend windows.
            fanout["unreadable"].append({"path": path, "http": st,
                                         "error": "window mismatch: single-path read returned %r days, "
                                                  "all-paths window is %d" % (one_days, days)})
            continue
        base["paths"][path] = one_paths[path]
        fanout["recovered"].append(path)

    still_missing = [d["path"] for d in fanout["unreadable"]] + fanout.get("not_attempted", [])
    if still_missing:
        base["truncated"] = {
            "paths_omitted": still_missing,
            "reason": "fanout-incomplete",
            "detail": "the endpoint omitted these and the per-path retry did not return them; "
                      "they are ABSENT, not zero",
        }
    else:
        base.pop("truncated", None)

    base["fanout"] = fanout
    out["stats"] = base
    out["ok"] = True
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=os.environ.get("SOURCE_URL",
                                                       "https://tailorfarms.com/_b/stats"))
    ap.add_argument("--out", default=None, help="write the artifact here")
    ap.add_argument("--stdout", action="store_true", help="print the artifact to stdout")
    a = ap.parse_args()

    doc = read(a.source)
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w") as f:
            json.dump(doc, f, indent=1, sort_keys=True)
    if a.stdout or not a.out:
        json.dump(doc, sys.stdout, indent=1, sort_keys=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
