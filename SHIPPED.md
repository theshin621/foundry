# SHIPPED — the human-readable ledger

| # | date | ship | what it is | verdict | status |
|---|---|---|---|---|---|
| 001 | 2026-07-30 | [hub](public/index.html) | The foundry's own hub — public ledger, factory library, deploy pipeline proven end-to-end | PASS (after one fix-cycle; live-URL unverified from sandbox) | live |
| 002 | 2026-08-02 | [gha-trigger](public/002-gha-trigger/index.html) | Will my GitHub Actions workflow run? Simulates event filters and names the one that decided it | **FAIL** (XSS fixed and confirmed dead under ~440 payloads from two independent adversaries; 56/56 vs GitHub's cheat sheet, 0 inverted verdicts in ~67M differential comparisons — fails on a glob-engine ReDoS that a static complexity budget could not bound, and on a safety claim the checker falsified) | failed — unmerged |
