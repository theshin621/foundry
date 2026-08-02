# lib/checks/ — the compounding verification library

The maker has `lib/`; the checker has this. **Every checker contributes its reusable
harness here, and every checker starts from what previous rounds accumulated.**

## Why this exists (2026-08-02)

Ship 002 went through four checker passes across two runs. Each pass independently
rebuilt the same rigs: the GitHub filter-pattern cheat-sheet oracle, an XSS payload
corpus, a ReDoS timing probe, a differential fuzz harness. That rebuild is the most
expensive stage of every day, thrown away and redone the next morning. It should
compound instead — ship #20's checker must cost half of ship #2's, the same way the
build library makes ship #20's build cost half of ship #1's.

## The rule (binding for the CHECKER stage)

1. **Reuse first.** Before writing a new harness, check here for one that fits.
2. **Contribute one piece back** per ship, generalised enough for the next checker:
   a payload corpus, an oracle, a timing probe, a differential driver.
3. **Corpora only grow.** A payload or example that ever caught a real defect is never
   removed — it is regression protection for every future ship.

## What's here now (seeded from ship 002's checkers)

- `xss-payloads.json` — HTML/JS-injection strings that reach an innerHTML sink. Includes
  the two shapes that actually bit ship 002: a value in a template, and a value inside a
  **thrown Error message** that is later rendered. Any ship that builds HTML from user
  input runs every payload and asserts zero script execution.
- `redos-probes.json` — pattern shapes that cause catastrophic backtracking in a naive
  glob→regex compiler, with the wall-clock ceiling a check should enforce. The lesson from
  ship 002: a *static complexity budget cannot bound this* — the only real fix is a
  non-backtracking (linear-time) matcher, so these probes exist to prove one.
- `gha-filter-oracle.json` — GitHub's own published filter-pattern cheat-sheet
  (pattern, value, expected) pairs. The ground-truth oracle for anything touching
  Actions globs; ship 002's rebuild must pass all of them.

Language-agnostic on purpose: JSON corpora, not JS, so a checker in any language loads them.
