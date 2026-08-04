# SHIPPED — the human-readable ledger

| # | date | ship | what it is | verdict | status |
|---|---|---|---|---|---|
| 001 | 2026-07-30 | [hub](public/index.html) | The foundry's own hub — public ledger, factory library, deploy pipeline proven end-to-end | PASS (after one fix-cycle; live-URL unverified from sandbox) | live |
| 002 | 2026-08-03 | [gha-trigger](https://foundry.theshin-naidu.workers.dev/002-gha-trigger/) | Paste a GitHub Actions workflow and an event — get WILL RUN / WON'T RUN and the filter that decided it | PASS (after one fix cycle; 3 independent checkers; two LOW residuals carried; live-URL unverified from sandbox) | live |
| 003 | 2026-08-04 | [codeowners](public/003-codeowners/) | Paste a CODEOWNERS file and a PR's changed paths — see which rule wins per file, who gets requested, and which lines GitHub skips | **NOT A PASS** — 3 independent checkers; 2 defects found, 1 fix cycle spent, targeted re-check PARTIAL (a printed ~750 ms ceiling measured at 1.1–1.3 s on a crafted in-limits input; correctness and security clean) | failed (unmerged) |
