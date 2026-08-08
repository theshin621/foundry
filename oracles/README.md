# oracles/ — the target set, fixed before the first line of code

**Rule (Amendment v4, PENDING — not yet in force):** NO ORACLE, NO BUILD.

An oracle is a *cold-executable* statement of what "correct" means for one ship, written by the
architect **before** the builder starts, and used by the checker **instead of** cases the builder
authored. It is one of:

- a **reference implementation** the ship's output can be diffed against (e.g. `ssh -G`, `npm pack
  --dry-run`, `nektos/act`'s `pkg/workflowpattern`), or
- a **real dataset** of recorded input→output pairs captured from that reference, or
- **acceptance predicates** that run cold with no human in the loop.

Layout: `oracles/<NNN-slug>/` — `README.md` (what correct means, and the exact command that
produced the reference output), the corpus, and a runner that exits non-zero on divergence.

Relationship to `lib/checks/`: `lib/checks/` accumulates *checker* material — payload corpora,
timing probes, fuzz harnesses — and grows one piece per ship. `oracles/` holds the *architect's*
pre-build spec for a specific ship. They overlap deliberately; when an oracle proves reusable it
graduates into `lib/checks/`.

Why this directory exists: see `BOTTLENECKS.md` entry #1.

---

## Approved salvage plan — the 43-case npm-publish oracle (plan 5a)

Ship **#006 npm-publish-preflight** died `failed` on branch `ship/006-npm-publish-preflight`, and
ship **#007 ssh-config-resolver** died `failed` on `ship/007-ssh-config-resolver`. Both branches
carry real oracle material built against real references — for #006, a **43-case corpus** diffed
against actual `npm publish` behaviour, of which **33/43 are currently verified**; for #007, 37
recorded probes with real `ssh -G` output in `lib/checks/ssh-config-oracle.json`.

That material is the most valuable thing on two dead branches. It is worth salvaging, and it is
**not** ground truth yet.

**Binding, so nobody shortcuts it:**

1. The salvage happens in a **later, dedicated fire** — explicitly *not* the 2026-08-08 wiring fire,
   which created this directory and nothing else in it.
2. Before any of it counts as ground truth it needs (a) a **defect pass** over the corpus itself —
   these cases were authored alongside code that failed 4 independent verdicts, so the corpus
   inherits the suspicion, and (b) **per-case verification** of all 43, not just re-confirmation of
   the 33 already marked verified. The 10 unverified cases are the interesting ones: a case that
   resisted verification is either wrong or is exactly the long-tail rule the ship kept tripping on.
3. Until both are done, **no ship may be checked against this corpus** and no verdict may cite it.
   An unverified oracle is worse than no oracle — it launders the builder's assumptions into the
   checker's evidence, which is entry #1's failure mode wearing a different hat.
4. The defect pass must be run by someone other than the corpus's author, on a different model, per
   the standing maker≠checker contract. The corpus is an artefact like any other.

Status: **planned, not started.** Nothing in this directory is ground truth as of 2026-08-08.
