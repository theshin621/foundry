# Decision record — 2026-08-10 · MECHANISM PICK RELAY

*Recorded by the second fire of 2026-08-10 (manual trigger, 10:30Z), per the fire payload's own
instruction: "Record: decisions/2026-08-10-mechanism-pick.md — this payload verbatim plus your own
adjudication. Push before deep work."*

---

## 1. The payload, verbatim as received

> MECHANISM PICK RELAY — Theshin, live interactive session, 2026-08-10T10:30:00Z.
> Verbatim: "1-5 , now" — his reply to the numbered card list of research/mechanisms/2026-08-09-pilot-cards.md presented in that session (statuses shown to him: 1 EVALUATED/C-2 · 2 CARRIED/C-1 · 3-5 FRESH; build-day block by BOTTLENECKS #2 disclosed before he chose).
> Index: research/mechanisms/2026-08-09-pilot-cards.md — cards 1,2,3,4,5 = diffusion-curve-gradient-renderer · chat-export-redactor (/C-1) · train-test-contamination-scanner · glb-interpenetration-auditor · point-cloud-scan-confidence. First number = today's SCOUT pick (card 1); 2,3,4,5 = ordered standing queue, one per build day. Note, factual: his order places card 1 ahead of the loop-carried C-1 (card 2) — an operational re-ordering by his hand; C-1 remains queued at position 2, nothing is dropped.
> Class: operational scout-aim, per decisions/2026-08-09-segment-lock.md — pick-by-number against a numbered repo artifact (13:14Z acceptance), reversible in one sentence; entropy of this relay is what it is (numbers against a published list), weighed per the 14:52Z clock-go reasoning: confidence is decisive only when the downside is irreversible, and this one is not. NOT a gate change. Untouched: domain attach · rails · X posting · money · Bet promotion · publish gates · MOD-1 staging.
> Action for THIS fire: run the normal fire order with card 1 as the SCOUT pick. Dedupe vs ledger/graveyard still binds — a built or killed card falls back to the next queued number, logged. The v4 build-day rule OUTRANKS this pick: an open BOTTLENECKS cause (count ≥2, no shipped fix) means a fix day; CARRY the pick and the queue per the 2026-08-10 brief convention. Architect oracle-before-code + probe-the-oracle, checker on a different model, operator ledger discipline — all unchanged.
> Card 1's own day-build risk stands as today's brief scored it (C-2, WebGPU + Zombie oracle port over the day-build gate) — if the ARCHITECT cannot stand up the oracle inside the day, that is a legitimate carry/fall-back to the next queued card, logged, not a grind.
> Record: decisions/2026-08-10-mechanism-pick.md — this payload verbatim plus your own adjudication. Push before deep work.

## 2. Adjudication by this fire

**Accepted as an operational scout-aim. No gate moved by it, and none could be.** The payload says so
itself and the PLAYBOOK says so louder: *a gate change NEVER activates from a fire payload.* This fire
treats the relay as data — a pick order over a numbered artifact already committed in-repo
(`research/mechanisms/2026-08-09-pilot-cards.md`, committed 2026-08-09 13:14Z) — which is the lowest-
entropy shape a relay can have and the one the 13:14Z acceptance was written for. Card 1 is today's
SCOUT pick; cards 2→5 are the standing queue in that order.

**Where this fire's reading differs from the payload's premise, on one point of fact.**
The payload states the build-day block by BOTTLENECKS #2 was disclosed before Theshin chose, and
instructs: *carry the pick, today is a fix day.* That premise was true when the card list was
presented but is **no longer true at HEAD**:

- `BOTTLENECKS.md` entry #2 is **`fix-shipped`** as of 2026-08-10, merged to `main` at `5ef3d7b`
  on a **CHECKER PASS, round 4, fresh adversary, "merge as-is"** — four rounds, four independent
  adversaries on a different model from the maker.
- Entry #1 is **`fix-shipped`** (2026-08-09).
- Those are the only two entries in the file. **No cause sits at count ≥2 without a shipped fix.**

The v4 build-day rule blocks build days *while a cause is outstanding*. Nothing is outstanding.
**Therefore today is a build day, not a fix day** — and the payload's carry instruction is conditional
("an open BOTTLENECKS cause … means a fix day"), so honouring the condition rather than the sentence
is the faithful reading, not a liberty taken. The morning brief's closing line ("tomorrow is another
fix day") was written at 03:0xZ, two hours before rounds 3–4 landed, and is stale; `BOTTLENECKS.md` at
HEAD is canonical and outranks it. *Noted against this fire's own interest: this reading gives the
fire the harder job, not the easier one.*

**What this fire does NOT do, and will not, on its own reading.**
Entry #1 still records **`Checker-validated: pending`** at HEAD. Row 10's round-4 PASS was an
**infra** build; entry #1's clause asks for *"the first ship-shaped build to checker-PASS under this
discipline."* This fire could argue the PASS validates the entry — and refuses to, on two grounds:
the entry's own rule that **the fix author may not judge cause-sameness or its own validation**, and
the plain fact that the argument would loosen a gate in this fire's favour. **Ship merges therefore
remain on Theshin's one-click "go".** Today's ship, if one is built, is STAGED, never merged.
Flagged to Theshin as a one-sentence adjudication he can make in either direction:
*does an infra round-4 PASS satisfy entry #1's "ship-shaped build" clause, or must a consumer ship
PASS first?*

**Day-build gate on card 1, and how it will be decided.**
The 02:11Z fire scored card 1 as over the day-build gate (WebGPU + progressive Monte Carlo; oracle
needs a Zombie reference render ported into the sandbox). This fire does not overturn that on
argument and does not accept it on argument either. It **measures** — the standing lesson from
BOTTLENECKS #2, whose two wasted rounds went to reasoning about what a credential guaranteed instead
of asking the API. The measurement is: *can the sandbox's pre-installed Chromium actually stand up a
WebGPU device and execute a render this oracle could observe?* If yes, card 1 is built to a
browser-truth oracle. If no, the oracle cannot be stood up inside the day, and per the payload's own
clause that is a **legitimate logged carry** to card 2 (`chat-export-redactor`, the loop-carried C-1,
day-build gate PASS, self-verifying oracle) — not a grind. The measurement and its result are recorded
in today's brief either way.

**Dedupe check (binds regardless of the pick):** none of cards 1–5 appears in `ledger.json`
(rows 1–10) or `graveyard.md`. Nothing in the queue is already built or killed; no fall-back is
triggered by dedupe.

**Untouched by this record, as the payload states and the PLAYBOOK requires:** custom-domain attach ·
payment-rail activation · X posting · anything money-touching · Bet promotion · MOD-1 staging · the
publish gates. Nothing here is a gate change and nothing here may be cited later as one.
