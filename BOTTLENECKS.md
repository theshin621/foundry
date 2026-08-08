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
- **count:** 3
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
- **fix:** Amendment v4's **oracle-before-code** rule — the architect writes a runnable oracle in
  `oracles/<ship>/` (reference implementation, real dataset, or cold-executable acceptance
  predicates) *before* any code exists, and the checker drives the staged page against **that**
  oracle rather than against cases the builder authored. The theory of the defect: when scope is
  drawn around a reference implementation with a long tail of rules, and the only spec is the
  builder's own reading of it, each fix reveals the next rule. An oracle fixes the target set before
  the first line is written, so the defect count can actually converge — and convergence becomes
  measurable instead of being guessed at by the anti-grind clause.
- **status:** **fix-proposed** — *not* `fix-shipped`. Amendment v4 arrived 2026-08-08 as a manual
  fire payload into an unattended session and is parked **PENDING** in `PLAYBOOK.md` until Theshin
  confirms it from a live session. The fix is written down; it is not in force. Until it is, this
  cause is `count 3, unfixed`.

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
