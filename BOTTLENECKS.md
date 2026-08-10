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
- **count:** 5 confirmed, **+1 unadjudicated** (see incident #9 below — the fix author may not judge whether it is this cause, so it is logged and left for Theshin)
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
  approving that prompt requires a human in the session and a scheduled fire has none. It is not
  transient and it does not retry its way out. Consequence: **every signal the loop is supposed to
  steer by is unreadable by the loop.** Kill-criteria in `ledger.json` are denominated in beacon
  visits; MOD-2 Branch B of the 30-day stop-condition is `>=250 qualified visits, >=3 distinct days,
  trailing 7d`; both are served only at `https://tailorfarms.com/_b/stats`. A loop that cannot read
  its own instrument cannot kill, cannot iterate on evidence, and cannot know whether it has won.
- **count:** 3
- **incidents:**
  - **2026-08-09T13:14Z relay fire** — `decisions/2026-08-09-segment-lock.md` precondition table
    records beacon armed as *"✓ **carried, not re-read this run**"*. The fire asserted the
    precondition it could not measure.
  - **2026-08-09T14:52Z clock-go fire** — same file, verbatim: *"this fire could **not**
    independently re-read `https://tailorfarms.com/_b/stats`. The fetch tool returned
    `PROVENANCE_REQUIRED` … an unattended session has nobody to approve the prompt."* It correctly
    declined to overwrite good measured data with an `{"error":…}` stub, and correctly named the
    limitation — but the clock started on a precondition nobody had checked that day.
  - **2026-08-10T02:2xZ daily fire** — same failure, measured again on clock day 1. Filed this
    entry.
- **why it was not caught sooner:** the cause was already written down, in this repo, in prose —
  `.github/workflows/health-check.yml`'s header states it in general form: *"The build sandbox
  cannot reach the live origin (WebFetch is provenance-gated in unattended runs) … so no scheduled
  run can confirm by itself that the live site renders."* The remedy invented there (a
  GitHub-hosted runner, outside the sandbox, committing what it saw) was applied to **render
  checks** and never extended to **the instrument**. Ship 008 then built `/_b/stats` explicitly so
  "a scheduled fire can READ its own instrument" (ledger row 8) and stopped one step short of the
  reader. The gap survived because each artifact was correct about its own scope.
- **fix:** `.github/workflows/beacon-stats.yml` — the health-check path pointed at one more
  endpoint. A GitHub-hosted runner reads `/_b/stats` at 01:35 UTC (~25 min before the daily fire),
  records the body **with Actions provenance** (`run_id`, `run_url`, `run_attempt`, `repo`,
  `workflow_path`, `head_sha`), and commits it to `public/beacon-stats.json`. The next fire reads
  its instrument out of git.
  **The provenance is the load-bearing part, not the convenience.** `public/beacon-stats.json` is a
  file in a repo the loop can write to, so its existence proves nothing — a fire could fabricate
  numbers into it and the ledger would look measured. `oracles/beacon-stats-relay/oracle.py`
  therefore does not inspect the numbers at all; it asks **api.github.com** whether the run behind
  them exists, is *this* workflow, and sits at *this* `head_sha`. A sandbox fire can write any JSON
  it likes; it cannot manufacture an Actions run. That API call is this oracle's equivalent of
  entry #1's "execute it in a real browser" — observe the real system rather than predict it.
  `lib/beacon_stats.py` is the only permitted reader and returns numbers **only** on an oracle
  PASS; on anything else it returns an honest `{"error":…, "as_of":…}` block, and it keeps
  *measured-zero* and *unmeasured* as different values (`0` vs `None`) so a quiet day can never be
  laundered into an outage or vice versa.
<<<<<<< HEAD
- **status:** **`open`.** The fix above was built, and it does not merge. Two independent
  adversaries on a different model from the maker, two rounds, **zero PASS** — the anti-grind clause
  binds and `infra/beacon-stats-relay` stays unmerged. Full verdicts verbatim in `ledger.json` row 10.
  **What actually failed is worth stating precisely, because the two halves came apart:**
  - **The RELAY works.** Actions runs `31349720900`, `31349820402`, `31350293968`, `31350511164`
    each reached `tailorfarms.com/_b/stats` from outside the sandbox and committed what they saw.
    The loop read its own instrument today, four times, for the first time in its history. Neither
    checker disputed this; round 2 explicitly confirmed every relay-side guard holds.
  - **The PROOF that the numbers are the runner's does not work.** Round 1 killed the first version
    ("a fire cannot manufacture an Actions run" — true, and irrelevant: a run's provenance block is
    public and re-quotable, so editing `stats` and keeping provenance byte-identical passed). The one
    permitted fix cycle moved the unforgeable thing from the run to the commit — the reading is now
    written through GitHub's Contents API, which GPG-signs it. Round 2 falsified **the premise of
    that fix**: GitHub signs *every* Contents-API commit regardless of caller, so the loop's own PAT
    (which has `push:true, admin:true`, and which the oracle itself reads) can produce a
    `verified:true` commit carrying any bytes it likes. *"This is not a sibling of one round-1 fix —
    it is the same finding #1 reopened by the very mechanism chosen to fix it."*
- **why this entry stays open rather than being downgraded:** the honest reading is that BOTTLENECKS
  #1's pattern reproduced here in one day, and the loop should say so rather than argue itself into a
  merge. But the trajectory data belongs on the record too: round 1 found 4 severe; the fix cycle
  held on 6 of 8 findings under adversarial re-test (round 2 re-verified them by *neutering each
  predicate individually*, which is stronger evidence than round 1 asked for); and round 2's three
  severe findings are one root, not three — **the oracle authenticates the CHANNEL and never the
  ACTOR.** Every bypass, in both rounds, is the same sentence: nothing checks *who wrote the bytes*.
- **the fix that is NOT attempted here, deliberately:** round 2 handed over the shape of the real
  answer — check identity, not just signature. `commit.author.login` is `github-actions[bot]` for a
  runner commit and Theshin's account for a PAT commit; that distinction is visible in the same API
  response P7 already fetches. It is one predicate. **It is not written, because the one permitted
  fix cycle is spent and this fire is now the fix author twice over.** Writing a third version and
  grading it is exactly the self-certification loop this file exists to stop. It is the next fire's
  first task, against a fresh adversary.
- **the clean way out, and it is Theshin's hand:** the strongest binding is not identity at all, it
  is the runner's own log — GitHub writes it, no caller can. The oracle was built to use it and
  could not: `GET /actions/runs/{id}/logs` returns **403** with the current fine-grained PAT, which
  carries Contents + Pull requests + Workflows but **not `Actions: read`**. Adding that one scope to
  the existing token closes finding #1 outright, with no cleverness: the oracle downloads the log
  GitHub wrote, and asserts the committed numbers appear in it. **Decision-debt opened 2026-08-10,
  owner Theshin, one-line action: add `Actions: read` to the foundry PAT.**
=======
- **status:** `fix-shipped` pending this run's CHECKER verdict — INFRA, so it merges autonomously on
  PASS under v4 MOD-1. `closed` still requires >=2 subsequent fires reading the instrument without
  recurrence.
>>>>>>> infra/beacon-stats-relay
- **first evidence the fix works:** run `31349720900` produced a reading the oracle certified cold
  at 02:24:49Z — the first time in this loop's history that a fire has read its own instrument.
  What it says is in `briefs/2026-08-10.md` §5 and it is not good news.

<<<<<<< HEAD
- **incident #4 (the fix attempt itself, 2026-08-10):** `infra/beacon-stats-relay`, 2 rounds,
  2 independent verdicts, 0 PASS, branch unmerged. Logged here because a failed fix for a cause is
  evidence about the cause. **This fire authored the fix and therefore does not score whether it is
  the same cause as entry #1** — that adjudication is Theshin's or a later fire's, per this file's
  standing rule. The case for "same cause as #1" is round 2's own sentence about the reopened
  finding; the case against is that #1 is about defect *count* regenerating while here a single root
  (channel-not-actor) was mis-modelled twice, which is arguably one mistake made twice rather than a
  generator of new ones.

=======
>>>>>>> infra/beacon-stats-relay
*Opened 2026-08-10 by the daily fire, which is also the fix author. Per this file's standing rule
the fix author may not judge cause-sameness for later failures; a recurrence is adjudicated by
Theshin or by a fire that did not write this entry.*
