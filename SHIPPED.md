# SHIPPED — the human-readable ledger

| # | date | ship | what it is | verdict | status |
|---|---|---|---|---|---|
| 001 | 2026-07-30 | [hub](public/index.html) | The foundry's own hub — public ledger, factory library, deploy pipeline proven end-to-end | PASS (after one fix-cycle; live-URL unverified from sandbox) | live |
| 002 | 2026-08-03 | [gha-trigger](https://foundry.theshin-naidu.workers.dev/002-gha-trigger/) | Paste a GitHub Actions workflow and an event — get WILL RUN / WON'T RUN and the filter that decided it | PASS (after one fix cycle; 3 independent checkers; two LOW residuals carried; live-URL unverified from sandbox) | live |
| 003 | 2026-08-06 | codeowners | Paste a CODEOWNERS file and a PR's changed paths — which rule wins per file and who gets requested | FAIL (3 builds, 7 independent verdicts, 0 PASS; killed by the anti-grind clause written before the build) | killed → [graveyard](graveyard.md) |
