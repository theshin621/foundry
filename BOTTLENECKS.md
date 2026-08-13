# BOTTLENECKS — causes, not incidents

A bottleneck entry is a **cause** that has killed or blocked work more than once. One incident is
bad luck; the second occurrence is a fact about the factory. Entries are opened by the checker at
kill time, and the fix author may not judge whether a later failure is the same cause — ties go to
Theshin.

**Fields:** `cause` · `count` (distinct incidents) · `incidents` · `fix` · `status`.

**Statuses:** `open` (no fix) · `fix-proposed` (a fix exists on paper / pending approval) ·
`fix-shipped` (the fix is in force in `main`) · `closed` (fix in force AND ≥2 subsequent builds of
the same shape passed without the cause recurring).

**Build-day rule (IN FORCE since 2026-08-09 — v4 canon):** any cause at `count ≥ 2` with no
*shipped* fix blocks build days while outstanding.

---

## Entry #1 — the fix cycle regenerates defects

- **cause:** the same generator produces new defects at the rate they are closed. A checker names
  N defects, the one permitted fix cycle closes all N, and the re-check finds fresh siblings of the
  fixes — usually one line away from what was just repaired. The loop cannot currently tell a
  *converging* ship from a *grinding* one, so the anti-grind clause kills both.
- **count:** 5 confirmed, **+5 unadjudicated** (#009, #011, #012, #013, #014 below — each logged by the very fire that wrote the fix, and therefore scored by none of them. The bookkeeping is a fact; the adjudication is Theshin's.)
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

- **status:** **fix-shipped** (2026-08-09, live activation — `decisions/2026-08-09-v4-activated-live.md`):
  oracle-before-code AND **probe-the-oracle** (negative control + an independent attempt to break
  the oracle — this entry's own second clause, now a mandatory step) are canon in `main`.
  **Shipped is not validated, and rounds 3-4 above are the honest correction:** the oracle-first
  rule was followed on #008 and the cause recurred anyway, twice, in the hand-written band *around*
  the borrowed tokenizer. The shipped fix therefore carries a third clause, applied first to #008's
  rebuild (2026-08-09, the live session): **for liveness-of-markup claims the oracle executes the
  page in a real browser (Chromium) and observes the behaviour itself — the hand-written
  parse-and-match band is deleted, not repaired.** A static walker cannot be trusted to prove a
  beacon fires; a browser observing the fire is the spec-defined tokenizer for the *whole* problem
  — borrow-don't-build taken to its endpoint. **Checker-validated: pending** — the first
  ship-shaped build to checker-PASS under this discipline validates the entry (the #008 rebuild is
  the candidate); until then MOD-1 keeps ship merges on Theshin's one-click go. `closed` still
  requires ≥2 subsequent same-shape builds passing without recurrence.

  **Validation trajectory (2026-08-09, the #008 rebuild under the shipped discipline):**
  rebuild checker round: PARTIAL, 9 findings, 0 severe (its words: the browser-truth oracle
  "genuinely survives independent attack… I defeated the static band again and it caught me").
  One fix cycle. Fresh targeted re-check: PARTIAL — **all 8 fixes HOLD**, exactly 1 new sibling,
  MEDIUM, fleet-growth reachability only, recorded in the ledger and queued as its own
  checker-gated commit. Compare the entry's four prior incidents: fixes closed N, re-checks found
  ~N new SEVERE siblings. This round: 9 → 1, severity falling, reachability receding — **the first
  converging trajectory in this entry's history.** Checker-validated therefore remains PENDING (the
  clause needs a clean PASS): the queued /_b/stats window fix is the next validation candidate.
  Until a PASS lands, MOD-1 keeps ship merges on Theshin's one-click go — staged autonomy working
  as designed, not a failure of it.

  **Unadjudicated incident — #014 beacon-liveness-oracle (2026-08-13, the 02:11Z scheduled fire).**
  Logged and deliberately NOT counted by its own author, for the fifth time and the same reason.
  The facts, so Theshin can:

  Round 1 (independent, different model): **FAIL, 4 findings, 2 SEVERE.** One fix cycle, applied
  structurally rather than case-by-case, and one of the two fixes was a *deletion*: the checker
  showed that three of the oracle's predicates were **decoration** — neutering any of them changed
  no verdict, because they were not independent (nothing parses unless it arrived, nothing arrives
  unless it was sent), while the commit message asserted "23/23, every predicate has a control that
  flips it". They were collapsed into one predicate, and `probe.py` was rewritten to **neuter every
  predicate in turn and fail if any changes no verdict**, converting that claim from a sentence into
  a machine-checked property. Round 2 (**FRESH adversary**, independent of round 1): the two named
  defects **hold closed for the shapes tested**, clause (c)'s 27/27 · 7/7 reproduces cold, and the
  `neuter` seam is confirmed unreachable from the CLI — **and 4 new findings, ALL FOUR SEVERE, every
  one classified by the adversary as a sibling of a fix.**

  **The trajectory is the worst this entry has recorded and this fire says so against its own work.**
  #011 fell 4 → 2 with severity to zero. #012 fell 6 → 3 with one SEVERE surviving. #013 ROSE 2 → 3
  with severe 1 → 2. Here the count holds at 4 → 4 while the severe count RISES **2 → 4**, and the
  sibling attribution is no longer arguable — the adversary named the parent fix for each finding
  unprompted. Two rounds, two independent adversaries, **zero PASS.** Branch
  `infra/014-beacon-liveness-oracle` unmerged, ledger row 14 `failed`, both verdicts verbatim.
  MOD-1's autonomous-infra-merge did not fire, because a FAIL is not a PASS.

  **What this incident adds, and it is the sharpest evidence in the entry to date.** #013's headline
  was that a predicate added to close an oracle gap grew its own sibling inside the same cycle — the
  pattern reaching the instrument. This incident is one turn further in: **the fix whose entire
  purpose was to eliminate decorative verification shipped a decorative control of its own.** Round 1
  killed three predicates for having no control that isolates them. The fix cycle added a machine
  check for exactly that failure — and also added `b2-popup`, a positive control whose fixture
  evaluates `location` in the *opener's* frame rather than the popup's, so it passes without ever
  exercising the claim it exists to prove, and the popup fix it was supposed to validate **was never
  actually made**: the request listener the fix moved to context level populates a field `judge()`
  never reads, while the binding predicate still keys off the opener's URL. Clause (c) could not
  catch this, because a decorative *fixture* still flips a verdict — it just flips it for the wrong
  reason. The generalisation this entry has been building toward gets one more layer: **borrowing a
  correct primitive does not make the caller correct; making the caller's verification machine-checked
  does not make the fixtures honest.** Every fix in this entry's history has been one layer up from
  the last, and the layer is now the fixture that feeds the machine check.

  **A second, narrower fact worth keeping.** The same `wire()` change introduced two regressions in
  code that previously could not fail at all: an uncaught error in an *unrelated* popup now fails an
  otherwise-live page, and a popup that never settles hangs `ctx.close()` indefinitely (reproduced
  past 90 seconds, twice). Before the fix, popups were invisible, so neither was reachable. **A fix
  that widens what an instrument observes widens what can wedge it**, and this one would have hung a
  GitHub Actions step with no message and no CANNOT-CERTIFY until the job's multi-hour ceiling.

  **Adjudication question for Theshin, stated plainly and unchanged from #013.** If this counts,
  entry #1 moves to 6 and reverts to `open`, which under the build-day rule **blocks build days until
  a fix ships**. #013's fire believed that was the correct reading. This fire believes it more
  strongly, because here the sibling attribution was made by an adversary rather than inferred by the
  author, and because the artifact that regenerated defects was itself the anti-decoration fix. It
  notes against itself, as its predecessors did, both that this is the least flattering reading of its
  own work and that it has no standing to make the call.

  **Unadjudicated incident — #013 stats-window-floor (2026-08-12, the 02:11Z scheduled fire).**
  Logged and deliberately NOT counted by its own author, for the fourth time and the same reason.
  The facts, so Theshin can:

  Round 1 (independent, different model): **FAIL, 2 findings, 1 SEVERE + 1 MEDIUM.** One fix
  cycle, applied structurally rather than case-by-case — the SEVERE (a 7-day floor enforced only
  inside the growth branch, so `?days=1` on an all-paths read returned a silent 1-day window) was
  closed by moving the floor onto the *ask* and by making `window` always carry `requested` and
  `floor`, so a day-dimension adjustment is self-declaring rather than relying on a `truncated`
  block that only ever described paths; the MEDIUM (an `AttributeError` on a non-dict `window`)
  was closed with an `as_dict()` gate placed on every untrusted mapping rather than on the one
  site named. Round 2 (**FRESH adversary**, independent of round 1): **both fixes HOLD**, verified
  against inputs the adversary wrote itself (fleet sizes 1–80, `?days=1..15`, non-dict values of
  every plain type) — and **3 new findings, 2 SEVERE, all three explicitly siblings of the two
  places the fix touched.**

  **The trajectory points the wrong way and this fire says so against its own work.** #011 fell
  4 → 2 with severity dropping to zero and argued convergence; #012 fell 6 → 3 with one SEVERE
  surviving. Here the count RISES 2 → 3 and the severe count RISES 1 → 2. Two rounds, two
  independent adversaries, **zero PASS**. Branch `infra/013-stats-window-floor` unmerged, ledger
  row 13 `failed`, both verdicts verbatim. MOD-1's autonomous-infra-merge did not fire, because a
  FAIL is not a PASS.

  **What this incident adds that the others do not, and it is the sharpest evidence in the entry.**
  Round 2's severest finding is not in the product at all — **it is in the oracle, and it is a
  sibling of the fix that was made to the oracle.** Round 1 found that the oracle never sent
  `?days=` without also sending `?path=`; the fix added predicate P10 to close exactly that gap;
  round 2 then showed that P10 inspects only the `window` object and never `body.paths`, so a
  worker that silently deletes every path but one **whenever the caller types `?days=`** passes
  P1–P10 and the oracle exits 0. The 2026-08-09 rebuild had already found one such hole
  (probe-the-oracle clause (b), a worker that returned one path and *declared* the rest omitted);
  this one is strictly worse because it declares nothing, and it was introduced **by the repair of
  the first one.** The entry's own generalisation — *"every fix has been one layer up from the
  last"* — now has an instance where the layer is the instrument, the fix was written in response
  to a checker, and the sibling appeared inside the same file in the same cycle.

  **The concrete proposal this incident makes, offered by the party it constrains.** #012 proposed
  that *the checker's first act should be to write fixtures, not to run the oracle.* This run is
  evidence for that proposal and evidence that it is not sufficient on its own: both adversaries
  DID write their own cases first, and both found real defects the oracle could not see — but the
  oracle they were auditing had been amended by the maker in between, and nobody re-audited the
  amendment. The narrower rule that would have caught round 2's severe finding is mechanical:
  **a predicate added during a fix cycle is maker-authored verification and must be probed by the
  same probe-the-oracle discipline as the original oracle** — negative control plus an independent
  attempt to pass it while being wrong. P10 received neither. That is a rule change to the
  ARCHITECT/CHECKER contract and is therefore proposed, not adopted.

  **Adjudication question for Theshin, stated plainly.** If this counts, entry #1 moves to 6 and
  reverts to `open`, which under the build-day rule **blocks build days until a fix ships** — the
  loop would spend its next fires on the cause rather than on ships. This fire believes that is
  the correct reading and notes against itself both that this is the least flattering reading of
  its own work and that it has no standing to make the call.

  **Unadjudicated incident — #012 chat-export-redactor (2026-08-11, the 02:10Z scheduled fire).**
  Logged and deliberately NOT counted by its own author, for the third time and the same reason:
  this fire wrote the fixes and may not score whether the later failure is this cause. The facts,
  so Theshin can:

  Round 1 (independent, different model): **FAIL, 6 findings, 3 SEVERE.** One fix cycle, applied
  structurally rather than case-by-case — the two SEVEREs shared one root cause (the identifier set
  was collected only from author fields) and were closed with a system-line grammar and a *recursive
  key-allowlist walk*, not with two patches. Round 2 (**FRESH adversary**): **all six fixes HOLD**,
  verified against inputs the adversary wrote itself — and **3 new findings, 1 SEVERE, all three
  explicitly siblings of the three places the fix touched.** The SEVERE is one line
  (`msg.trim()`): the system-line patterns are `$`-anchored and the borrowed parser leaves a
  trailing newline on the final record, so a person named only in a *terminal* system line is still
  leaked.

  **The question for Theshin is the same one #011 posed, with the evidence pointing the other way
  this time.** #011's siblings fell 4 -> 2 with severity dropping to zero, and that fire argued it
  was convergence. Here the count falls 6 -> 3 but **a SEVERE survives into round 2**, and it is a
  cleartext identity leak on a privacy tool — the worst possible residual for this artifact. This
  fire believes that is a recurrence and that the count should move to 6, which would revert entry
  #1 to `open` and block build days. **It has no standing to say so, and it notes against itself
  that this is the reading least favourable to its own work — which is not the same as it being
  right.**

  **What this incident adds that the others do not.** The oracle-first rule was followed to the
  letter, probe-the-oracle passed 10/10, and the oracle still went 40/40 green on a page with three
  SEVERE defects in it. The round-1 checker diagnosed exactly why, and the sentence is worth
  keeping: *the oracle compares residual identifiers case-insensitively, so one differently-cased
  fixture would have caught SEVERE 3 on the first run — none of the five existed.* **An oracle
  fixes the target set to what its author already knew how to handle.** Probe-the-oracle checks
  that the oracle can go RED; it does not check that the oracle is looking in the right places.
  Concrete proposal for Theshin, offered by the party it constrains: **the checker's first act
  should be to write fixtures, not to run the oracle** — the adversary's cases enter the instrument
  before the verdict is taken, rather than living only in a review nobody re-runs. Two of this
  ship's three rounds were spent discovering cases an adversary could have contributed in ten
  minutes, and both times the fix was cheap and the discovery was not.

  Fourth consecutive artifact where **every** defect lived in the hand-written band around a
  borrowed primitive; the borrowed primitive itself (`whatsapp-chat-parser@4.0.2`, verified
  byte-identical to upstream by the checker) drew zero findings.

  **Unadjudicated incident — #011 diffusion-curves (2026-08-10, the 10:30Z manual fire).** Logged,
  deliberately NOT counted by its own author, for the same reason as #009: this fire wrote the fix
  and cannot score whether the later failure is this cause. The facts, so Theshin can:
  round 1 (independent, different model) FAILed with 4 findings, 1 severe — a mid-render scene swap
  kept averaging new boundary data into the old accumulator and the page reported "done" over a
  blend of two boundary-value problems. That severe finding is itself arguably a sibling: the `gen`
  token had already been added during the build to stop two render loops racing, and the swap
  handlers were the code path that fix did not cover. The one permitted fix cycle closed all 4.
  Round 2 (FRESH adversary) confirmed **all four hold** and found 2 new, **0 severe** — and its
  MEDIUM is explicitly the sibling of the *guard* added after the fix cycle (`setScene()` was
  guarded against a null GL context; the banner-erasure and the unhandled rejection on that same
  path were not). **The question for Theshin is whether "a fix grew a sibling one layer up, but the
  siblings are now MEDIUM rather than SEVERE and are falling in count (4 → 2)" counts as this cause
  recurring, or as the converging trajectory the entry has been waiting for.** This fire believes it
  is the latter and has no standing to say so.

  **Unadjudicated incident — #009 html-structure-oracle (2026-08-09, the 02:10Z scheduled fire).**
  Logged, deliberately NOT counted by its own author. This entry's rule says *the fix author may
  not judge whether a later failure is the same cause — ties go to Theshin*, and this fire both
  wrote the artifact and would be scoring it, so it scores nothing.

  What happened: the fire picked incident #4's named lesson ("do not hand-roll a parser for a
  language that has a spec-defined tokenizer") as its Sunday iteration target and rebuilt the
  `<script>` boundary check on Python's stdlib `html.parser` in `lib/checks/html_structure.py`,
  adding a third verdict `CANNOT-CERTIFY` so an oracle can decline to bless a page it cannot read.
  Round 1: **FAIL**, 2 severe — the module counted `<script type="application/json">` and scripts
  inside `<template>`/`<noscript>` as executing, i.e. it reproduced #008's own failure shape
  (markup present, browser inert, oracle green) through a mechanism the tokenizer question cannot
  see. One fix cycle closed all of it (checker-confirmed; self-test 17→36). Round 2: **FAIL**, and
  the two new defects were **siblings of that fix, one line away** — `str.strip()` strips Unicode
  whitespace where HTML strips only ASCII, and `dict(attrs)` is last-wins where the spec is
  first-wins. Both one-liners. Neither was fixed; the anti-grind clause binds. Branch unmerged,
  ledger row 9 `failed`, two verdicts verbatim.

  **Why it may not belong to this entry at all, and why that matters.** This artifact was designed
  before the third clause above landed, and it is precisely the thing that clause deletes: a
  hand-written parse-and-match band asserting a liveness-of-markup claim. Every defect across both
  rounds was static analysis predicting browser behaviour and getting it wrong, and the checker's
  standing residual in *both* rounds was that it had no browser to ground-truth against. So this is
  arguably not a fresh instance of the cause but **independent confirmation of the shipped fix,
  arrived at from the opposite direction** — someone rebuilt the static approach carefully, with a
  real tokenizer and an honest CANNOT-CERTIFY verdict, and it still regenerated siblings inside one
  cycle. That reading is also the less flattering one for the artifact's author, which is part of
  why the author should not be the one to choose it.

  It is offered as a counterweight to the converging-trajectory note above: that note reads one
  artifact's improvement (9→1) as the entry turning a corner. This incident is a *different*
  artifact, built the same day against the same entry, that did not converge. Two data points
  pointing opposite ways is a reason to keep `checker-validated: pending` rather than to relax it.
  Salvage: the 36-case corpus (9 of them present-but-inert pages with known expected liveness) is
  reusable as *input* to the browser-truth oracle, and Chromium is available in the sandbox.

  **And #008 is evidence the proposed fix is necessary but not sufficient.** #008 *had* an oracle
  before the code — the v4 rule was followed voluntarily — and the pattern recurred anyway, one
  layer up. An oracle fixes the target set; it does not make the oracle itself correct. The rule
  needs a second clause: **the oracle's own coverage must be adversarially probed before it is
  trusted** — concretely, a negative control (break the artifact in the way the oracle claims to
  catch, confirm it goes red) plus an independent attempt to construct a break the oracle still
  passes. The round-2 checker did exactly that unprompted, in minutes, and found the hole. That
  should be a step, not a happy accident.

  **Build-day rule status (updated 2026-08-09):** the rule is in force (v4 canon) and the fix is
  *shipped*, so build days are NOT blocked by this cause. Five incidents across four artifacts
  remain the reason the rule exists; a recurrence under the shipped fix moves the count to 6,
  reverts the status to `open`, and blocks build days until a better fix ships.

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

---

## Entry #2 — the loop cannot read its own instrument

- **cause:** an unattended scheduled fire cannot fetch a live URL. `WebFetch` answers
  `PROVENANCE_REQUIRED — "the permission request for this URL was not answered in time"`, because
  approving that prompt needs a human in the session and a scheduled fire has none. Consequence:
  every signal the loop steers by was unreadable by the loop. Kill-criteria are denominated in
  beacon visits; MOD-2 Branch B is `>=250 qualified visits, >=3 distinct days, trailing 7d`; both
  are served only at `https://tailorfarms.com/_b/stats`.
- **count:** 3 (2026-08-09 13:14Z fire · 2026-08-09 14:52Z fire · 2026-08-10 02:2xZ fire)
- **fix:** `.github/workflows/beacon-stats.yml`. A GitHub-hosted runner reads `/_b/stats` at
  01:35 UTC, ~25 min before the daily fire, and commits the reading to `public/beacon-stats.json`.
  The next fire reads its instrument out of git. `oracles/beacon-stats-relay/oracle.py` re-derives
  the whole chain from `api.github.com` and `lib/beacon_stats.py` is the only permitted reader —
  it returns numbers on an oracle PASS and an honest `{"error", "as_of"}` block on anything else,
  and keeps *measured-zero* and *unmeasured* as different values.
- **status:** **`fix-shipped`** (2026-08-10, merged to `main` on a CHECKER PASS). **Four rounds,
  four independent adversaries on a different model from the maker, three FAILs then a PASS.**
- **what took four rounds, because the record is the useful part:** every FAIL was one root wearing
  a new coat — *the oracle authenticated the CHANNEL and never the ACTOR.*
  - **Round 1:** the oracle proved an Actions run *existed* but never bound the *bytes* to it. A
    run's provenance block is public and re-quotable, so editing `stats` and keeping provenance
    byte-identical passed.
  - **Round 2:** the fix bound the bytes to a GitHub GPG signature — and the premise was false.
    GitHub signs *every* Contents-API commit whoever calls it, so the loop's own PAT could produce
    a `verified:true` commit carrying anything.
  - **Round 3:** the actor proof was finally real, but the commit lookup took the *newest* commit
    touching the artifact rather than *this artifact's*, so a valid reading failed the moment the
    next relay run landed. And ten of the new predicates had **no negative control at all** — the
    probe reported 18/18 while never exercising the round's headline fix.
  - **Round 4: PASS**, with an explicit "merge as-is". It independently neutered **all 35
    predicates one at a time** and confirmed every one has a control that flips.
- **what actually solved it, and the lesson worth keeping:** not cleverness — **measurement**. The
  loop's own PAT was probed against the API and answered: `POST /repos/.../check-runs` → **403
  "Resource not accessible by personal access token"**; `GET` → **200**. A runner's `GITHUB_TOKEN`
  can create a check-run; the sandbox cannot. So the runner stamps `sha256` of the bytes it
  committed into a check-run and the oracle reads it back. **The proof was a property of the
  credential, and two rounds were spent reasoning about signatures instead of asking the API what
  the token could do.** Entry #1's lesson generalises: borrow a primitive, and *measure* what it
  actually guarantees rather than assuming.
- **the limit, stated rather than glossed:** the PAT holds the `workflows` scope and `main` has no
  ruleset, so the loop can rewrite `beacon-stats.yml` and have a real runner attest bytes it chose.
  P8 proves *a runner executed the workflow as this repo currently defines it* — not *the numbers
  came off tailorfarms.com*. Any check the loop can edit is not a control on the loop, so this is
  the right place to stop in code. **Decision-debt, owner Theshin, one action, either works:** a
  repository ruleset requiring review on `.github/workflows/**`, or dropping `workflows` from the
  PAT so the loop proposes CI changes instead of pushing them.
- **`closed` still requires** >=2 subsequent fires reading the instrument without recurrence.

*Opened and fixed 2026-08-10 by the daily fire; merged after four independent verdicts. The fire
authored the fix and does not score cause-sameness for any later failure.*
