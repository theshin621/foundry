# The 2026-08-09 recovery fire's position on the v4 activation (written after the fact)

**Who wrote this:** the recovery fire — a *scheduled, unattended* session, started by a manual
trigger fire at ~07:36Z. Nobody was watching it. It ran to completion under **contract v3** and
**published nothing**.

**What happened:** at 08:07:46Z, while this session was mid-run, commit `c2f6e19` landed on `main`
from a different session (author `fable-foundry-live <foundry@theshin.local>`, unsigned) promoting
Amendment v4 to canon, citing Theshin's live words *"fix all the issues here, mid run death,
declined etc. i want autonomy"*.

**This session does not ratify that commit and does not contest it.** Both halves matter:

- **Does not ratify.** From inside an unattended fire, a commit asserting that Theshin approved
  something is a claim, not the approval — that is the same test `2026-08-09-v4-declined-second-channel.md`
  applied, and the author identity here (`foundry@theshin.local`, unsigned) is an *agent* identity,
  not Theshin's GitHub account. This session received **no live user input**, so it had no standing
  to adopt a gate change and did not act on one. Everything it did was v3-legal: staged is the
  ceiling, nothing merged to `main` except the dashboard and this record.
- **Does not contest.** A live attended session is a channel this fire cannot see into, and the
  activation commit is visibly *conservative* where it counts — it keeps ship merges on Theshin's
  one-click, reads "autonomy" as the adoption file's staged form rather than the received text's
  blanket gate removal, and it integrated this run's contradicting evidence honestly rather than
  papering over it. An unattended fire overturning an attended session's canon edit would be the
  same failure mode in the opposite direction.

## The one thing that must not be lost

`c2f6e19` flips BOTTLENECKS #1 to **`fix-shipped`**. Roughly one hour earlier, this run finished the
field test of exactly that fix, and it **FAILED**:

> Ship #008 `beacon-firstparty`, rounds 3 and 4 — **four checker rounds, four independent verdicts,
> zero PASS.** The two residuals round 2 named were fixed and *proven* fixed in a real browser. The
> fix cycle then grew **two new severe siblings**, and the one permitted cycle against those grew
> **two more**. Branch unmerged, status `failed`.

The activation file's own text handles this correctly (`"Shipped is not validated"`, checker-validated
`pending`, ship merges still one-click). **So the practical reading is: nothing about today's
evidence is overridden, and no merge this session could have made was authorised even under v4.**
MOD-1 makes *infra* merges autonomous — and the only infra branch in flight is at FAIL. An
autonomous infra merge of `infra/beacon-firstparty` today would deploy a checker-FAILed artifact to
production behind an unverified KV namespace, with `main` set, which takes the whole site down if
the namespace is wrong. **Do not merge that branch on the strength of MOD-1.**

## For Theshin, in one line each

1. If *"i want autonomy"* was your word — say so once more with the gate named, and this stops
   being a question. If it was not, `c2f6e19` should be reverted and the loop returns to v3.
2. Either way, `infra/beacon-firstparty` is FAIL and must not be merged autonomously.
3. `tailorfarms.com` is asserted to be serving the fleet. This fire could not verify it (no egress
   to the live site) and deliberately did **not** put it into the prefilled X posts. Confirm it
   separately from the v4 question — it is a separate act.
