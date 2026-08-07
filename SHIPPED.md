# SHIPPED — the human-readable ledger

| # | date | ship | what it is | verdict | status |
|---|---|---|---|---|---|
| 001 | 2026-07-30 | [hub](public/index.html) | The foundry's own hub — public ledger, factory library, deploy pipeline proven end-to-end | PASS (after one fix-cycle; live-URL unverified from sandbox) | live |
| 002 | 2026-08-03 | [gha-trigger](https://foundry.theshin-naidu.workers.dev/002-gha-trigger/) | Paste a GitHub Actions workflow and an event — get WILL RUN / WON'T RUN and the filter that decided it | PASS (after one fix cycle; 3 independent checkers; two LOW residuals carried; live-URL unverified from sandbox) | live |
| 003 | 2026-08-06 | codeowners | Paste a CODEOWNERS file and a PR's changed paths — which rule wins per file and who gets requested | FAIL (3 builds, 7 independent verdicts, 0 PASS; killed by the anti-grind clause written before the build) | killed → [graveyard](graveyard.md) |
| 004 | 2026-08-06 | [khanya-school-tutor](https://foundry.theshin-naidu.workers.dev/004-khanya-school-tutor/) | Gamified CAPS/IEB tutor for Gr 3-12 — Socratic chat, knowledge maps, Snap & Solve, tests, spaced repetition; BYO key or demo mode | PASS (directed ship; family API key stripped pre-checker) | live |
| 005 | 2026-08-06 | [maccleaner](https://foundry.theshin-naidu.workers.dev/005-maccleaner/) | Safe auditable macOS cleanup — AppCleaner-style orphans + dev caches, quarantine not delete, full undo | PARTIAL -> fix (v1.1.4 symlink-ancestor gate) -> RECHECK PASS | live |
| 006 | 2026-08-07 | npm-publish-preflight | Paste your package.json, .npmignore/.gitignore and file list — the exact set npm publish would upload, and the one rule that decided each file | **FAIL** (2 rounds, 4 independent verdicts, 0 PASS; 7 findings fixed in the one permitted cycle, 6 new ones found incl. 2 siblings of those fixes; anti-grind clause fired) | failed → branch `ship/006-npm-publish-preflight`, unmerged, nothing public |
