---
name: fable-foundry
description: The daily scout→build→ship loop. Fires 04:00 SAST from a scheduled task — scouts the last 24–72h for Fable-buildable gaps (vault-unconstrained), recommends ONE day-buildable product with a full build order, HALTS for Theshin's "go", then builds, maker≠checker-verifies against the running deployment, ships to the foundry domain, distributes (registry PR + hub + drafted X post, never auto-posted), and appends the ledger. Sundays run triage instead — kill the dead, compound the winner. Trigger on the scheduled morning run, "run the foundry", "foundry scout", or "foundry triage". State lives in the foundry GitHub repo, never in context.
---

# fable-foundry — daily scout → build → ship

**Contract:** proposed 2026-07-28, wired on Theshin's "wire it". Six new ships Mon–Sat, Sunday triage. The repo's `PLAYBOOK.md` is canonical — read it first every run; if this skill and the playbook differ, the playbook wins.

## Every run, first

1. Clone/pull the foundry repo (PAT in the trigger prompt). Read `PLAYBOOK.md`, `ledger.json`, `graveyard.md`, `candidates-seen.json`.
2. Determine day-of-week in SAST. Mon–Sat → DAILY. Sunday → TRIAGE.
3. If the repo is unreachable: report BLOCKED and stop. Never run stateless.

## DAILY — phase 1: SCOUT (autonomous)

Differential scan of the last 24–72h, not a full landscape rebuild (the baselines live in `research/`):

- Sweep, in order: model-vendor changelogs/release blogs · MCP spec + blog + registry · new platform surfaces (marketplaces, APIs, extensions) · regulator feeds (dated deadlines only) · incident reports (an incident is demand with a date) · builder chatter (HN, launch threads).
- Standing biases (re-derive monthly, not daily): trust-stack slots stay empty while capability slots fill; cold-start consumer distribution is dead; MCP registries = free indexed discovery; deadline-driven and buyer-adjacent demand beat vibes.
- Candidate gate — every candidate must carry: dated why-now (URL, ≤14 days) · named occupant or the documented hunt that found none · promo-motive check on the source · **day-build gate**: v1 deployable by the agent alone today (no app-store review, KYC, human accounts, marketplace approval in the critical path) · a discovery path that isn't ads · a kill-criterion.
- Dedupe binding: ledger/graveyard/candidates-seen items are out unless the why-now materially changed (re-enter flagged "revisit", trigger named).
- Output: brief with ≥3 candidates, ONE recommendation on top with a complete build order (spec, pages/endpoints, deploy target, distribution actions, analytics events, kill-criterion). Push brief to `briefs/YYYY-MM-DD.md`. Update `candidates-seen.json`.

**Then HALT.** Notify (push) with the one-line recommendation. Build only on an explicit reply: `go` (the pick) · `go N` (alternate N) · `skip` (log, stand down). No reply = no build, logged next run. Approval never times out into a build.

## DAILY — phase 2: BUILD + VERIFY (after "go", fully autonomous)

1. Scaffold from `lib/` — never from scratch when lib has the piece. Build v1 in `sites/NNN-slug/`.
2. Free-first: no payment rails on Mon–Sat ships in the first 30 days. Every ship gets the analytics beacon (no cookies, no fingerprinting, no PII) and the "built by [brand] · day NNN" hub-linked footer.
3. Push branch → Cloudflare preview deploy → **CHECKER** (mandatory, subagent, refutation-seeking, against the PREVIEW URL — not the code):
   - Fetch cold: does it do what the landing copy claims? Try to falsify the claim.
   - Probe: empty states, bad input, mobile, the first-visitor flow.
   - Scan the diff: secrets, tokens, PII, vault references.
   - Re-verify today's why-now against its source — wrong premise = wrong landing copy = FAIL.
   - Confirm the pending ledger row matches deployed reality.
   - Verdict PASS/FAIL/PARTIAL, offending item named. Maker never writes its own verdict.
4. One fix-cycle on FAIL, then re-verify. Second FAIL → stays staged; report FAIL with the item named. A staged FAIL is a legitimate daily outcome; a soft-passed ship is not.

## DAILY — phase 3: SHIP (on PASS)

Merge → production deploys on push. Then, all of: hub entry · registry-submission PR where the ship is an MCP server · X build-in-public post DRAFTED into the brief in Theshin's voice (my-writing-style if available; never posted by the loop) · ledger row appended with the checker verdict **verbatim** (schema in PLAYBOOK §6) · one reusable piece contributed back to `lib/` · everything pushed · ship notification: URL + one-liner + verdict.

## SUNDAY — TRIAGE

1. Pull analytics + ledger for every live ship. Rank by real signal: visits-ex-Theshin, registry installs, inbound, revenue. No vanity ordering.
2. Propose: kill list (ships with zero signal past their kill-criterion → `graveyard.md` with reasons, dark on hub, folder stays in repo) + ONE iteration target with a build order. Winners may graduate to a payment rail here — Sunday is where the 30-day free rule ends for a proven ship.
3. **Same halt-for-"go" gate.** On go: iterate → checker → ship, identical to daily phases 2–3.
4. **Self-kill clause (binding):** at ship #30 with zero cumulative signal across all ships, the triage brief's LEAD item is a terminate-or-pivot recommendation for the loop itself.

## Hard rules (never loosened by cadence pressure)

- No build without explicit approval. No maker self-verdicts. No skipped ledger rows. No silent step-skips — impossible steps are reported FAIL with the step named.
- No scraping against ToS · nothing money-touching or financial-advice without explicit approval · no PII · no posting to X · nothing under Theshin's personal name · secrets stay out of code and ledger.
- Push before ending, every run. The repo is the only memory that survives.
