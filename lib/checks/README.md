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

## Added by ship 003 (codeowners, 2026-08-04)

- `codeowners-oracle.json` — three independent grounds of truth for CODEOWNERS /
  gitignore-style path matching: the reference implementation's own 153-pair test corpus,
  13 cases lifted from **GitHub's documented example block** with the documentation's own
  expectation quoted (the only PUBLISHED ground truth), and the set of malformed lines
  GitHub silently skips. It also carries a **differential recipe**: Go is installed in the
  build sandbox and `hmarr/codeowners`' root package builds with no network, so a checker
  can re-answer any (pattern, path) pair with the real Go implementation instead of arguing
  about it. Ship 003 ran 100,000 generated pairs through it.
- **A trap the recipe records so no future checker rediscovers it:** `hmarr/codeowners`
  *panics* (`index out of range [-1]`, `match.go:47`) on the pattern `/`. A driver without a
  per-pair `recover()` dies mid-run and looks like a harness bug.
- Ship 003's checker round then broke the ship twice, and both findings are now permanent
  regression material inside `codeowners-oracle.json` (`regression_notes` + 18 added pairs):
  a **single-occurrence byte matcher** in a byte-stepping port of a rune-based engine (`?`
  matched one byte, not one rune — invisible to every ASCII test), and **unmetered
  parse/compile** (a ~1 MiB pattern froze the tab 3.9 s before any budgeted work began).
  The second one carries a general lesson worth more than the fix: **step throughput is
  shape-dependent** — ~32M/s, ~20M/s and ~4-5M/s measured for three different workloads —
  so a step counter is not a time bound, and only a wall-clock deadline is honest enough
  for a UI to quote.

## `door-limits.json` (ship 003 rebuild, 2026-08-05)

Input-dimension probes for any ship with a pasted text box: chars, lines, line length, **field
length** (the one that gets missed), and output size. Plus the stale-answer probe — a page that
computes synchronously never paints its own `clear()`, so the last painted frame during a long run
is the previous answer. Reading the DOM does not catch that; screenshot mid-run or assert a state
attribute flips before compute begins.
