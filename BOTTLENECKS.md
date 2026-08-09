# BOTTLENECKS — causes, not incidents

A bottleneck entry is a **cause** that has killed or blocked work more than once. One incident is
bad luck; the second occurrence is a fact about the factory. Entries are opened by the checker at
kill time, and the fix author may not judge whether a later failure is the same cause — ties go to
Theshin.

**Fields:** `cause` · `count` (distinct incidents) · `incidents` · `fix` · `status`.

**Statuses:** `open` (no fix) · `fix-proposed` (a fix exists on paper / pending approval) ·
`fix-shipped` (the fix is in force in `main`) · `closed` (fix in force AND ≥2 subsequent builds of
the same shape passed without the cause recurring).

**Build-day rule (proposed with Amendment v4, not yet in force):** any cause at `count ≥ 2` with no
*shipped* fix blocks build days while outstanding. Recorded here so it is ready if v4 is adopted.

---

## Entry #1 — the fix cycle regenerates defects

- **cause:** the same generator produces new defects at the rate they are closed. A checker names
  N defects, the one permitted fix cycle closes all N, and the re-check finds fresh siblings of the
  fixes — usually one line away from what was just repaired. The loop cannot currently tell a
  *converging* ship from a *grinding* one, so the anti-grind clause kills both.
- **count:** 5
- **incidents:**
  - **#003 codeowners** (2026-08-06) — 3 builds, 7 independent verdicts, 0 PASS. Killed →
    `graveyard.md`.
  - **#006 npm-publish-preflight** (2026-08-07) — 2 rounds, 4 verdicts, 0 PASS. 7 findings fixed in
    the permitted cycle; 6 new ones found, **2 of them siblings of the fixes**. Status `failed`,
    branch unmerged.
  - **#007 ssh-config-resolver** (2026-08-08) — 2 rounds, 4 verdicts, 0 PASS. Round 1: 7 defects
    with one root (the page answered confidently for files OpenSSH refuses outright). Fix cycle
    closed all 7; round 2 found 4 new defects, **every one a sibling of the refusal fix**. Status
    `failed`, branch unmerged, `lib/` deliberately not merged so the shared library stays clean.
  - **#008 beacon-firstparty** (2026-08-08, same day, the wiring fire) — 2 independent checkers.
    Round 1 FAIL, 6 findings, the severe one being that the inlined beacon was **inert on all five
    pages** while every page still returned HTTP 200 and the module-level oracle still read 53/53
    green. The one permitted fix cycle killed 5 of 6 outright. Round 2 PARTIAL — and named **a new
    severe sibling of the fix**: the hardened oracle's hand-rolled `<script>` boundary walker is
    itself defeatable by a stray unclosed `<script>` earlier in the page, reproducing the exact
    original failure (inert beacon, oracle green, 93/93). Status `failed`, branch unmerged.

    **This incident is different in kind from the other three and is the reason the count moved.**
    The first three were the pattern in *ships*. This one is the pattern **inside the verification
    layer** — the fix for "the oracle couldn't see the artifact" grew a sibling in the artifact
    checker itself. A loop whose checker can go green on a broken deliverable has a worse problem
    than a loop that ships bugs, because every other verdict in the ledger inherits the doubt. The
    specific lesson is narrow and actionable: **do not hand-roll a parser for a language that has a
    spec-defined tokenizer.** The round-2 checker falsified the walker in minutes using Python's
    stdlib `html.parser`. That is the fix — parse with a real tokenizer, never with regexes and
    index arithmetic — and it is the same borrow-don't-build rule from Amendment 2026-08-02b,
    applied for the first time to *verification* code rather than to product code.
- **fix:** Amendment v4's **oracle-before-code** rule — the architect writes a runnable oracle in
  `oracles/<ship>/` (reference implementation, real dataset, or cold-executable acceptance
  predicates) *before* any code exists, and the checker drives the staged page against **that**
  oracle rather than against cases the builder authored. The theory of the defect: when scope is
  drawn around a reference implementation with a long tail of rules, and the only spec is the
  builder's own reading of it, each fix reveals the next rule. An oracle fixes the target set before
  the first line is written, so the defect count can actually converge — and convergence becomes
  measurable instead of being guessed at by the anti-grind clause.
  - **#008 beacon-firstparty, rounds 3-4** (2026-08-09, the recovery fire) — **the same
    incident, two more rounds, and the reason the count moved to 5.** The maker fixed exactly the
    two residuals round 2 named, with negative controls proving each fixed vector now goes red.
    Round 3 (independent checker, different model) FAILed with **two new severe defects, each a
    direct sibling of one of those two fixes**: the replacement byte-equality contract was
    defeated by wrapping the *byte-identical* snippet in `<template>`/`<noscript>` (oracle
    95/95 green, beacon provably inert in Chromium); and `lib/inline.js`'s new output
    post-condition called the checker **with no expectation argument**, so "verified" meant only
    "parseable" and a merged, never-executing module passed. The one permitted fix cycle closed
    both — re-confirmed dead in a real browser — and round 4 then found **two more severe
    siblings of those fixes**: the inert-ancestor stack is desynchronised by a `</template>`
    inside an open `<noscript>` (raw text to a browser, a real end tag to `html.parser`), and
    `verify_bodies` matches each expected body independently, so N directives can be satisfied by
    one surviving live element. Four rounds, four independent verdicts, **zero PASS**. Branch
    unmerged, status `failed`.

    **This is the entry's most important evidence to date, and it points the opposite way to what
    was hoped.** The 2026-08-09 fire was instructed to record the oracle-first fix as
    *field-validated* if the beacon passed. It did not pass. What was actually field-tested was
    the round-2 lesson — *"do not hand-roll a parser for a language that has a spec-defined
    tokenizer"* — and that lesson **held**: the tokenizer-based checker caught every vector the
    hand-rolled walker missed. What failed is the layer above it. Both round-4 siblings live in
    the thin band of hand-written logic wrapped *around* the borrowed tokenizer — an ancestor
    stack and a matching rule the maker still had to author. The generalisation is narrower and
    more useful than "use an oracle": **borrowing a correct primitive does not make the code that
    calls it correct, and the caller is where the defects now are.** Every fix in this incident
    has been one layer up from the last.

- **status:** **fix-proposed** — *not* `fix-shipped`. Amendment v4 arrived 2026-08-08 as a manual
  fire payload into an unattended session and is parked **PENDING** in `PLAYBOOK.md` until Theshin
  confirms it from a live session. The fix is written down; it is not in force. Until it is, this
  cause is `count 5, unfixed`.

  **And #008 is evidence the proposed fix is necessary but not sufficient.** #008 *had* an oracle
  before the code — the v4 rule was followed voluntarily — and the pattern recurred anyway, one
  layer up. An oracle fixes the target set; it does not make the oracle itself correct. The rule
  needs a second clause: **the oracle's own coverage must be adversarially probed before it is
  trusted** — concretely, a negative control (break the artifact in the way the oracle claims to
  catch, confirm it goes red) plus an independent attempt to construct a break the oracle still
  passes. The round-2 checker did exactly that unprompted, in minutes, and found the hole. That
  should be a step, not a happy accident.

  **Build-day rule status:** if v4 is adopted as written, this cause at `count 5` with no *shipped*
  fix would **block build days** until the fix lands. That is the correct outcome and worth stating
  plainly before it bites: the loop has produced four consecutive non-shipping builds, and the
  honest reading is that it should stop starting new ships until this is fixed, not keep starting
  them faster.

  **A third open question, added 2026-08-09 after #008 rounds 3-4.** Is the anti-grind clause
  measuring the wrong thing? On this artifact the defect *count* per round is flat (2 severe, then
  2 severe) — which the clause reads as grinding — but the defects are strictly **narrower and
  deeper** each round: a hand-rolled walker, then a content-model gap, then a parser-fidelity
  edge case that needs `<noscript>` inside `<template>` to trigger. Round 4's severities are real
  but their *reachability* is not: nothing in this repo, and no plausible future ship page, emits
  `<template><noscript>…</template>…</noscript>`. A rule that counts findings cannot tell
  "still broken for real users" from "an adversary with repo write access can still construct a
  page that fools it". **Proposal for Theshin, not adopted here: score findings by reachability
  from the loop's own build path, and let a round of unreachable-only findings count as
  convergence rather than grinding.** The risk of adopting it is obvious and should be stated —
  it is a rule that makes it easier to declare victory, authored by the party that benefits.

**Two open questions the fix does not answer** (carry into Sunday triage, per the 2026-08-08 brief):

1. Is one fix cycle simply too few for this *shape* of ship? 7→4 defects across rounds on #007 is
   arguably convergence, and a clause that cannot distinguish convergence from grinding will kill
   converging ships forever. A defect-count-must-shrink rule is a cheaper fix than an oracle and is
   worth testing alongside it, not instead of it.
2. Is the real cause upstream, at **pick** time? All three incidents are "port a long-tailed
   reference implementation's semantics into a browser page". The borrow-don't-build amendment
   (2026-08-02b) says port rather than hand-roll — but #006 and #007 both *had* references and still
   died. That suggests the candidate shape itself, not the build method, is the thing to screen out.
   An oracle makes that shape *survivable*; avoiding the shape makes it *unnecessary*.

---

*Opened 2026-08-08 by the wiring fire, on the cause the 2026-08-08 daily brief had independently
nominated as Sunday's lead triage item.*
