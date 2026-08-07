# lib/ — the compounding build library

Every build checks here FIRST and contributes one reusable piece back. Ship #001 populates: landing template + analytics-beacon placeholder (token pending). MCP server scaffold and other pieces get added by the first ship that needs them — every build contributes one piece back. Ship #20 must cost half of ship #1 — this folder is why.

## Ship mechanics (every build follows these)
1. Build into `public/NNN-slug/index.html` starting from `lib/template.html`.
2. Append the ship's row to root `ledger.json`, then `cp ledger.json public/ledger.json` — the hub reads the public copy client-side.
3. Include `lib/beacon.html` contents only once it holds a real token (it is a placeholder until Cloudflare Web Analytics is enabled).
4. Checker runs BEFORE merge: serve `public/` locally (`python3 -m http.server`) and verify there — sandbox egress cannot reach workers.dev, so local render + push-hash + (when the desktop is reachable) Chrome on the live URL is the verification path.
5. Merge to `main` = production deploy (Cloudflare Workers Build, `wrangler.jsonc` → `./public`).

## What's in lib/ now

| file | contributed by | what it is |
|---|---|---|
| `template.html` | ship 001 | ship-page skeleton (beacon + footer) |
| `beacon.html` | ship 001 | the live cookieless Cloudflare Web Analytics snippet |
| `esc.js` | ship 002 | the ONE HTML-escape helper; every HTML-from-input sink routes through it |
| `mini-yaml.js` | ship 002 | bounded YAML subset parser |
| `gha-glob.js` | ship 002 | GitHub Actions filter-pattern matcher (act semantics, Pike VM) |
| `nfa.js` | ship 003 | **the linear-time matcher core, extracted** — Thompson NFA + Pike VM over bytes, with a work budget. Build a pattern language on top of it and it cannot backtrack. |
| `codeowners.js` | ship 003 | CODEOWNERS parser + matcher (hmarr/codeowners semantics, executed on `nfa.js`) |
| `inline.js` | ship 003 | assembles a self-contained ship page from a source file plus lib/ modules, so the inlined copy can be **proven** identical to lib/ instead of drifting silently |
| `gitignore.js` | ship 006 | **gitignore-syntax pattern sets** — parse + match, no regex and no NFA. Two bottom-up DPs (segment, then path), four exact necessary-condition short-circuits, and an optional `nocase` mode that folds at compile time. `compileOne`/`testRule` for one-pattern-many-paths. Reusable by anything with gitignore-shaped rules: npm, `.dockerignore`, `.eslintignore`. |
| `npmpack.js` | ship 006 | npm's publish-set resolution on top of `gitignore.js` — the always-in / always-out / hard-core tables, `.npmignore`-replaces-`.gitignore`, the `files[]` allow-list, ancestor-directory pruning, and the *reason* for every file. |

`gha-glob.js` still carries its own copy of the VM rather than importing `nfa.js`: it is live
in production with three independent checker verdicts against its exact bytes, and re-pointing
it at a new dependency would invalidate that evidence for no user-visible gain. Migrating it is
a job for a run that can afford its own checker round.

## A rule added the hard way (2026-08-04)

**Never write a person's name into code, a comment, or a commit message.** Ship 003 put an
attribution note in a `lib/` comment; `lib/` is inlined into every ship page, so it shipped to
a served file, and because git history is additive, fixing the tip did not remove it — a
checker fetched it back over HTTP from an ancestor commit and proved the exposure was live.
The branch had to be squashed and force-pushed. Attribute decisions to a date and a reason;
the ledger is where the loop's memory belongs, and the ledger is not inlined into a page.

## `door.js` — validate every dimension at the door (ship 003 rebuild, 2026-08-05)

One forward pass over a pasted box that measures **total chars, line count, line length and
whitespace-delimited field length** without splitting, slicing or allocating, and bails at the
first violation. Call it **before** any split/trim/parse/compile.

Why it exists: bounding aggregate input proves nothing. `** @` + 100,000 `a` is 100 KB — inside
every aggregate cap — and cost ship 003 attempt 1 twenty-three seconds, because one absurd owner
token was re-drawn once per matching row. The rebuild refuses it in 0.007 ms.

**Two line caps, not one (added 2026-08-06).** `maxLines` bounds NON-BLANK lines — the ones that
are downstream work. `maxSegments` bounds TOTAL segments — what `String.split` actually produces.
You need both, and the reason is not obvious until it bites: counting only non-blank lines is
correct for the *answer* and useless for the *preprocessing*, because the split allocates one
string per line, blanks included, before anything metered runs. 1 MiB of newlines is **0** non-blank
lines and **1,048,576** segments, and it walked straight through a 20,000-line cap. Binding rule:
**the door must bound every quantity any loop between the door and the budget will iterate over,
and no raw split may be taken over a quantity the door has not bounded.** `kind:'segments'` bails
the instant the cap is passed, so `length` is `limit+1` with `exact:false` — phrase that refusal as
"more than N", never "N+1".

Also exports `buffer(maxChars)` (bounds *output* by construction, the other half of the same
lesson) and `clip(s, max)` (a second belt on any single drawn value).

`lineTerminators` must match whatever the caller later splits on — `'lf'` for `lib/codeowners.js`,
`'any'` for a list split with `/\r\n|\r|\n/`. Verified equal to both consumers across 931 cases.

## Choosing a matcher (ship 006, 2026-08-07) — nfa.js is not always the answer

`lib/nfa.js` is the repo's proven linear-time matcher and the reflex is to reach for it.
Ship 006 deliberately did not, and the reasoning generalises: **pick the matcher from the
SHAPE of the workload, not from what is already proven.**

* `nfa.js` wins when a few patterns run against many long strings — compile once, then
  `O(len(input) x len(program))` per test, no backtracking.
* A publish-set resolution is the mirror image: **many patterns x many short paths**
  (300 x 3,000 = 9e5 tests at ship 006's door limits), and nearly every test dies on its
  first segment. Under the Pike VM each of those pays the full program width; under a
  segment walk it pays one compare.

Both are backtracking-free, so this is a constant-factor argument, not a safety one — but
the constant was ~3 orders of magnitude, which is the difference between a click and a
frozen tab. What is NOT negotiable is the third option: the textbook RECURSIVE glob
matcher is exponential and is the same defect class as a backtracking regex. Neither of
`gitignore.js`'s DPs can recurse or backtrack by construction.

**The short-circuit discipline that came with it.** Four exact necessary conditions
(whole-segment literal · min length, or EXACT length when the segment has no `*` · leading
literal run · trailing literal run) cut the worst door-legal input ship 006 accepts from
**1,658 ms to 133 ms**. Each can only reject what the DP would also reject — and the
23-case oracle in `lib/checks/npm-publish-oracle.json` was re-run after every one of them,
because "it got faster" and "it still answers correctly" are two different claims and only
the second one matters.

## A refusal must not claim a measurement it never took (ship 006, 2026-08-07)

`door.js` BAILS at the first violation, so for `kind:'lines'`, `kind:'segments'` and a
mid-run `kind:'field'` the reported `length` is `limit+1` — a box of 600 lines and a box
of 60,000 both report 301. Phrase all three as **"more than N"**. Ship 006 shipped the
`segments` message correctly and its `lines` sibling wrongly, in the same function, and
only found it by driving the real page. That is the sibling-sweep rule (2026-08-06) failing
at authoring time rather than at fix time — apply it to code you are WRITING, not only to
code you are patching.

## Two rules from ship 006's checker round 1 (2026-08-07) — both cost a FAIL

**1. A maker's own oracle proves only that the code agrees with the maker.** Ship 006
shipped 23 hand-written reference cases and passed all 23. An independent checker then
installed **real npm** and diffed the page against `npm pack --dry-run`, and found that
npm's walker matches **case-insensitively** (`ignore-walk`, `nocase: true`, unconditional)
while the page was case-sensitive throughout — so on any repo containing a `Dist/` or a
`DEBUG.LOG` the core answer was simply wrong. Four more disagreements came out of the same
method (a backslash in a filename being rewritten to a separator and then *cited* as a
directory that did not exist; `files[]` entries not anchored to the package root; `files`
as a string, which npm iterates character by character; the `browser` field, which npm
force-includes like `main`). **Where a real implementation exists, diff against it.** The
oracle now carries the npm version it was verified against, case by case.

**2. A metered function must charge for the work it does on the way to the meter.** The
old `matchOne()` parsed its pattern before it ticked the budget, and a `files[]` entry of
8,180 spaces is stripped to `''` by the trailing-whitespace rule and returns early — so
48,000 calls burned 2,941 ms of main thread with `budget.left` still at exactly 60,000,000.
That is ship 003's cause of death recurring one call site over: **a loop between the door
and the budget that the budget cannot see.** Two fixes, both required — tick before parse,
and give callers `compileOne`/`testRule` so a pattern matched against many paths is parsed
once and the parse leaves the inner loop entirely.

**Corollary for `door.buffer()`:** do not assemble an output whose honesty depends on text
appended LAST. Ship 006's truncation notice could not be written because the buffer that
truncated the table was already full, so a cut-off answer rendered as a confident one. Build
independently bounded parts and concatenate — banners that describe the table must not live
in the same buffer as the table.
