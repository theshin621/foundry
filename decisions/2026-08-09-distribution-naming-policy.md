# Distribution & naming policy — 2026-08-09 (relay fire, 14:56Z)

**Source.** A fire payload relaying Theshin, verbatim, from a live session the same evening:

> "i dont like the fact that my full name is exposed in the github url and tweets… I would like the
> tweet to reflect the published cloudflare url of the working solutions. when something is pushed
> to github we shouldnt tweet then."

**Classification — why this was applied without a live-word attestation.** The v4 standing rule is
that *a gate change never activates from a fire payload*. This is not a gate change and the diff
proves it: nothing in THE GATES was touched, no autonomy was widened, and every clause is a
**restriction** on what the loop may write into public-facing text. X posting remains what it always
was — drafted, never posted, the Post tap always Theshin's. A payload may tighten the loop's own
output discipline; it may not loosen a gate. Had this asked for the opposite (permission to post, a
new autonomous surface), it would have been refused pending his own words, exactly as 2026-08-08 and
2026-08-09 were refused.

---

## 1. X-DRAFT POLICY (in force)

1. **Trigger.** A draft is authored or refreshed **only when a ship is PUBLISHED** — live on
   `tailorfarms.com`. Never at push time, never at stage time. A push to GitHub is not a publication
   event and produces no draft. (This is the half of his sentence that is easy to miss: the
   objection was not only to the link, it was to *tweeting at the wrong moment in the pipeline*.)
2. **Link.** Every draft links **only** the ship's `tailorfarms.com` URL. No GitHub links, no
   `workers.dev` URLs, no personal-name strings — in any draft, or in any public-facing text, ever.

**Applied and verified this run.** All four live-ship drafts rewritten; a programmatic scan of the
four `x.com/intent` payloads decoded from the *stamped* dashboard returns **0 violations** across
`github` · `workers.dev` · `theshin`.

## 2. NAME SCRUB (public surfaces)

Swept `public/`, the hub, the dashboard, `SHIPPED.md`, and both ledger copies.

- `foundry.theshin-naidu.workers.dev` → `tailorfarms.com` everywhere it was *surfaced*.
- Personal-name prose in `ledger.json` / `public/ledger.json` → "the founder". Both copies parse and
  are byte-identical; semantics preserved (`directed_by: "the founder 2026-08-06"`).
- `public/005-maccleaner/maccleaner.sh` build comment de-named. No published checksum, so no
  artifact contract was broken.
- Hub footer no longer advertises the repo path; its ledger fallback now points at `/ledger.json`.
- 005's "Read the source" button now serves the script off `tailorfarms.com` — **more** functional
  than before, not less.

**Two things were deliberately NOT scrubbed, and saying so is the point:**

- **`public/health.json`.** It is instrument output. The blanket sweep rewrote its `base` field and
  that edit was **reverted within the same run**: the file recorded a probe that ran against
  `workers.dev`, and relabelling it `tailorfarms.com` would have been a hand-written measurement —
  the exact sin the ledger's non-null rule exists to prevent. It will say `tailorfarms.com` when a
  probe has actually run there, and not one minute earlier.
- **Operator links on the dashboard** (`PLAYBOOK.md`, `graveyard.md`, `SHIPPED.md`, "the public
  repo"). GitHub is the only host for those files. The blanket sweep turned them into
  `tailorfarms.com/blob/...` — **five dead links**, caught and repaired in-run. They are back on
  GitHub, functional, with labels that no longer print the path. This is the honest residual: the
  repo path is reachable from the dashboard, and only the org transfer (§3) removes it.

## 3. GITHUB IDENTITY — decision-debt, owner Theshin, opened 2026-08-09

**Not attempted by the loop, by instruction.** Recorded so it cannot quietly rot:

| | |
|---|---|
| **Decision** | Transfer `theshin621/foundry` to a neutral org (e.g. `github.com/tailorfarms`) |
| **Owner** | Theshin (only he can transfer; only he can reissue the PAT) |
| **Why** | The repo URL is the last public surface carrying his handle |
| **Cost of waiting** | Low and bounded — the repo stays public, build-in-public continues, nothing public advertises the path any more |
| **Steps** | 1. Create/claim the org · 2. Settings → Danger Zone → Transfer ownership (old URLs auto-redirect, so nothing breaks) · 3. Reissue the fine-grained PAT against the new owner, same three scopes · 4. Paste it into the trigger's CREDENTIAL block · 5. A fire updates `REPO_SLUG` and the dashboard's `RAWBASE`/`API` constants |
| **Escalation** | 2 consecutive Sunday triages unresolved → becomes a `BOTTLENECKS.md` entry |

## 4. The workers.dev toggle — armed, NOT recommended

His account action, one toggle: **Workers & Pages → foundry → Domains → Production `workers.dev`
→ OFF.** On the dashboard as Needs-Theshin #4, with that exact click path.

**This run does not recommend tapping it, and that is a finding rather than a caveat.** The
instruction was "verify tailorfarms.com serves every live path before recommending the toggle." This
session **could not verify it**: `WebFetch` returned `PROVENANCE_REQUIRED` on all eight paths — the
tool wants a human to approve the fetch, and unattended fires have no human. Fetching around it with
`curl` was available and was **not** used; routing around a permission gate to manufacture the
evidence a gate exists to withhold is not verification.

So the run armed the instrument instead: `.github/workflows/health-check.yml` now probes
`BASE: https://tailorfarms.com`, and it runs on this push. The next `public/health.json` is the
proof — all-green with `base: https://tailorfarms.com` is the gate on the toggle. Nothing public
points at `workers.dev` any more; leaving it answering costs nothing and breaks nothing.

**Known open item the probe will also surface** (pre-existing, not caused here): the last
`workers.dev` probe showed `/008-beacon-firstparty/` returning **404** while its ledger row reads
`live`, and `has_beacon: false` on ships 004 and 005. That is a ledger-vs-reality gap for a build
day to own, not this relay.
