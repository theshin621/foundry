#!/usr/bin/env bash
# bin/reconcile-merged.sh — THE APPROVAL DETECTOR. Added 2026-08-02.
#
# WHY THIS EXISTS:
#   Every scheduled fire is a NEW session. It cannot see a reply Theshin typed into
#   yesterday's session, and there is no durable inbox for the word "go". So a loop
#   that waits to be *told* "go" can only ever publish if Theshin happens to answer
#   while the session is still alive — at 4am, that is approximately never.
#
#   Fix: make the MERGE itself the approval. Theshin merges ship/NNN-slug into main
#   from GitHub (phone, laptop, anywhere, any time). Merging to main IS the production
#   deploy — Cloudflare builds on push. This script is how the next run notices.
#   No message has to survive. The gate is unchanged: nothing reaches main without him.
#
# Usage:  bin/reconcile-merged.sh [--dry-run]
# Exit:   0 = ran (changes may or may not have been made), 1 = error.
set -uo pipefail
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1

git fetch -q origin 2>/dev/null || { echo "reconcile: fetch failed" >&2; exit 1; }

branches=$(git ls-remote --heads origin 'refs/heads/ship/*' 2>/dev/null | awk '{print $2}' | sed 's#refs/heads/##')
[ -n "$branches" ] || { echo "reconcile: no ship/* branches"; exit 0; }

merged=""
for b in $branches; do
  if git merge-base --is-ancestor "origin/$b" origin/main 2>/dev/null; then
    merged="$merged $b"
    echo "reconcile: MERGED -> $b  (Theshin approved; this is the 'go')"
  else
    echo "reconcile: awaiting  -> $b"
  fi
done
[ -n "${merged// /}" ] || { echo "reconcile: nothing newly merged"; exit 0; }

export RECONCILE_MERGED="$merged"
python3 - "$DRY" <<'PY'
import json, os, re, sys
dry = sys.argv[1] == "1"
merged = os.environ.get("RECONCILE_MERGED", "").split()
ns = set()
for b in merged:
    m = re.search(r'ship/(\d+)-', b)
    if m: ns.add(int(m.group(1)))

try:
    led = json.load(open('ledger.json'))
except Exception as e:
    print("reconcile: cannot read ledger.json:", e); sys.exit(1)

changed, warn = [], []
for s in led.get('ships', []):
    if s.get('n') not in ns:
        continue
    st = s.get('status')
    if st == 'live':
        continue
    if st == 'failed':
        # Theshin merged a branch the checker FAILED. That is his call to make, and the
        # ledger must reflect reality rather than tidy it away -- but it must never look
        # like the checker passed. Status goes live; the FAIL verdict stays verbatim.
        warn.append(s)
    s['status'] = 'live'
    slug = s.get('slug', '')
    if not str(s.get('deploy_url', '')).startswith('http'):
        s['deploy_url'] = '/%03d-%s/' % (s['n'], slug)
    changed.append(s)

if not changed:
    print("reconcile: merged branches already reconciled"); sys.exit(0)

for s in changed:
    print("reconcile: ledger n=%s %s -> live" % (s['n'], s.get('slug')))
for s in warn:
    print("reconcile: *** WARNING n=%s %s was merged with checker verdict FAIL. It is now "
          "PUBLIC. The verdict is preserved verbatim in the ledger; surface this in the run "
          "summary and the notification, do NOT quietly mark it healthy." % (s['n'], s.get('slug')))

if dry:
    print("reconcile: --dry-run, no files written"); sys.exit(0)

json.dump(led, open('ledger.json', 'w'), indent=2)
json.dump(led, open('public/ledger.json', 'w'), indent=2)
print("reconcile: wrote ledger.json + public/ledger.json")
PY
rc=$?
[ $DRY -eq 1 ] && exit $rc
[ $rc -eq 0 ] || exit $rc

if ! git diff --quiet -- ledger.json public/ledger.json 2>/dev/null; then
  git add ledger.json public/ledger.json
  git commit -q -m "reconcile: merged ship branch(es) detected -> ledger live (merge = Theshin's go)"
  bin/push.sh main
fi
exit 0
