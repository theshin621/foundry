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
| `sshconfig.js` | ship 007 | OpenSSH client-config parser + first-obtained-wins resolver, pattern matching executed on `nfa.js`. Every semantic rule in it was measured against the real `ssh -G`, never read off the man page |
| `checks/ssh-fuzz.js` | ship 007 | **the differential harness** — generates ssh_config files and diffs `sshconfig.js` against the real `ssh` binary, by REPLAY (see below) |

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


## The REPLAY diff — the strongest form of borrow-the-oracle (ship 007, 2026-08-08)

2026-08-07 established the rule: *where a real implementation exists, install it and diff against
it.* Ship 007 found the shape that makes the rule bite hardest, and it is worth stealing for every
future ship whose reference implementation is a program rather than a library.

A per-keyword diff — "for each option I claim, does the real tool agree?" — only tests what the
maker thought to look at. It cannot see an option you dropped, because you never asked about it.
Ship 006 died of exactly that class.

**Replay closes it.** Take your answer, write it back out as a minimal input to the reference
implementation, run the reference implementation on it, and require that its FULL output is
identical to its output on the user's original input:

```
ssh -G -F <the user's config>  <host>        ==       ssh -G -F <our resolved answer>  <host>
```

If the resolver dropped a directive, invented one, or picked the wrong winner, the two outputs
diverge somewhere across all ~80 options ssh prints — including options the maker never enumerated.
It also gets the reference implementation's *internal side-effects* right for free: OpenSSH derives
`ServerAliveInterval 300` from `BatchMode yes`, and a naive baseline diff flags that as a defect,
while the replay reproduces it on both sides and stays silent. Hand-maintaining a table of those
side-effects would have been a maker's-own-oracle wearing a disguise.

Preconditions: the reference implementation must accept its own output as input (or you must be
able to synthesise input from your answer), and the harness must NOT normalise away real
differences — normalise only what the reference demonstrably rewrites on the way out (`ssh -G`
prints `no` as `false`, `QUIET` as `SILENT`, and re-quotes string options), and record each such
rewrite in a comment so the next reader can tell a cosmetic rule from a convenient one.

**Result on ship 007:** 5,493 generated configs across four seeds, zero mismatches. Four real
defects were found and fixed by the harness before any checker saw the page — a command-line user
outranking every `User` line, five accumulators de-duplicating identical values, `ProxyCommand` and
friends taking the rest of the line raw, and `Match user` evaluated against the wrong subject. Not
one of them was reachable by reading the documentation.
