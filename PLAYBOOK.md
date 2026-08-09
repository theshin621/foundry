# FABLE FOUNDRY — the daily scout→build→ship loop

**Designed:** 2026-07-28 · **Status:** PROPOSED — wires on Theshin's "wire it" (loop-mode gate)
**One sentence:** every morning a fresh Fable session scouts the newest gap, recommends ONE day-buildable product, waits for Theshin's "go", then builds, adversarially verifies, deploys, distributes, and ledgers it — six new ships a week, Sunday kills the dead and compounds the winner.

This file is canonical. A copy lives at the repo root as `PLAYBOOK.md`; every fresh session reads it before acting. The vault holds only a pointer note — the loop's state lives in the repo, per the "unconstrained by the vault" directive (2026-07-28, Theshin).

---

## 0. Confirmed decisions (2026-07-28, per Theshin)

| Decision | Choice |
|---|---|
| Autonomy | **AMENDED 2026-07-31 (see Amendments):** scout → build → checker all run autonomously to a STAGED preview; Theshin's "go" = PUBLISH (merge). Nothing public without approval — the gate moved from build-time to publish-time. |
| Fire time | 04:00 SAST daily (`0 2 * * *` UTC) |
| Stack | GitHub monorepo + Cloudflare Pages/Workers (deploy-on-push) |
| Rhythm | Mon–Sat new ships · Sunday triage (kill/keep/iterate — same approval gate) |
| Revenue | Free + analytics first 30 days; payment rails added only to Sunday-triage winners |
| Brand | New neutral brand, one domain, every ship under it (candidates in §8) |
| Distribution | MCP-registry submission where applicable + portfolio-hub entry + DRAFTED X post in Theshin's voice (never auto-posted) |
| Budget | No cap — the approval gate is the cost control |

---

### Amendments — 2026-07-31 (per Theshin, after two zero-output runs)

The 2026-07-30 manual fire and the 2026-07-31 04:08 scheduled fire both died before pushing anything — no brief, no candidates, no heartbeat reached the repo (cause: quota exhaustion mid-run; the full parallel scout burned ~300k+ tokens before any durable output). The go-gate was never reached, so throughput was never a gate problem. Six binding changes, none of which relax verification:

1. **Gate moved to publish-time.** Mon–Sat runs now build AND checker-verify to a **staged preview** (unmerged branch) autonomously every day. Theshin's "go" / "go N" **merges to production** — batchable ("go 2+4"), any time. Nothing is ever publicly deployed without approval; the checker still gates staging. A staged ship unreleased after **7 days** flips to `parked` in the ledger (branch kept).
2. **Three scout lanes, same gates on all:** ORIGINAL (news-driven gap, dated why-now ≤14d — the original lane) · **CLONE** (a tool with corroborated, current revenue elsewhere — founders-board CREATE evidence rules; "I made $X" posts are marketing until corroborated). **AMENDED 2026-08-02:** the edge must be STRUCTURAL, not inferential — free vs paid, no signup, whole-site vs one-item, API/MCP-first, or handling the case the incumbent gets wrong. There is no LLM API key by design, so any clone whose advantage is runtime inference is not buildable, however good. Ship 002 was exactly this shape and needed no key. · **EVERGREEN** (boring schlep utilities with permanent demand — no news hook required; the why-now requirement is waived for this lane only, the occupant hunt is not). Every candidate still passes the adversarial screen, the day-build gate, and carries a kill-criterion.
3. **Lean daily / deep Sunday scout.** Weekdays: single-pass differential scan (~100–150k tokens — changelogs, MCP registry/blog, one sweep, ≤2 subagents and only to verify the ONE recommendation). Sunday: the deep parallel scan runs alongside triage.
4. **Heartbeat + push-early (survivability).** First action of every run after clone: append a run-start line to today's brief file and PUSH it. Push again the moment the brief is drafted, again after the checker verdict, again after staging. A run that dies mid-flight must still leave dated evidence in the repo at the last completed stage.
5. **Dashboard refresh step.** Each run updates the content of `tools/foundry-dashboard.html`, then runs `python3 tools/stamp.py` and commits BOTH files it touches — the script (never the hand) stamps the data-as-of timestamp and mirrors the page to `public/dashboard/index.html`, which the push auto-deploys to `/dashboard/`. Desktop-artifact sync is an interactive-session job, not a fire's job — see the 2026-08-05 amendment.
6. **Ledger statuses** now: `staged` (built, verified, awaiting go) · `live` · `parked` (staged >7d unreleased) · `killed`.

Clauses elsewhere in this file that say "no build without approval" are superseded by (1): the binding invariant is **no PUBLIC exposure without approval**, and the maker still never self-verdicts.

---

### Amendment — 2026-08-02b (deployment quality — more ships reach staged, and you see them before you merge)

After ship 002 failed four checker passes over two runs, the bottleneck is visibly in *build strategy and deploy verification*, not in candidates or approvals. Five binding changes, none of which relax the gate:

1. **A GitHub Actions sidecar closes the sandbox's two blind spots.** The build sandbox cannot reach `*.workers.dev` or the GitHub REST API, but a workflow running *in the repo* can, for free, with the built-in `GITHUB_TOKEN` — no new secret. `.github/workflows/ship-preview.yml` opens a **draft PR** for every `ship/**` push (Cloudflare then attaches a preview deployment, so Theshin looks at the real page before merging — this is the "PRs get preview URLs" line finally made real). `.github/workflows/health-check.yml` probes the live site after every `main` deploy and commits `public/health.json`; the next run **reads that file and knows** whether the site renders, turning "live-URL unverified (egress)" from a permanent caveat into a verified fact inside the loop.
2. **Borrow-don't-build at pick time.** Ship 002 died three times on one hand-rolled glob engine when a correct, tested reference implementation (nektos/act's `pkg/workflowpattern`, MIT) existed the whole time. **If a ship's risky core — parser, matcher, sanitiser, crypto — has a reference implementation, port it with attribution; hand-rolling one is a reason to prefer a different candidate.** Day-buildable must also mean day-verifiable.
3. **A rebuild lane for architectural FAILs.** A checker-FAIL whose fix is structural (not a one-liner) re-enters the *next* morning's pick as a rebuild candidate carrying the checker's constraint as its build order — failed work becomes the cheapest next ship instead of sunk cost. (Ship 002 → Monday's rebuild: linear-time non-backtracking matcher, verified against `lib/checks/gha-filter-oracle.json`.)
4. **`lib/checks/` compounds verification the way `lib/` compounds building.** The checker reuses the accumulated payload corpora / oracles / timing probes and contributes one piece back per ship. The `esc()` boundary helper is now `lib/esc.js` — both of ship 002's security findings were unescaped input reaching `innerHTML`, so every ship routes HTML-from-input through it and the checker greps for raw `innerHTML=` that bypasses it.
5. **Kill-criteria must be measurable by the beacon.** Cloudflare's free Web Analytics is **pageview-only** (no custom events), so a criterion like "<25 tool runs" is unmeasurable and quietly makes Sunday triage ceremonial. Every kill-criterion is phrased in **per-path visits** (which the beacon does provide) or it is not a valid criterion.

---

### Amendment — 2026-08-03 (the workflow blocker, measured — and routed around)

Theshin, 2026-08-03: *"its been 3 days now and nothing shipped. I need the foundry to work
end to end."* Three findings, the first of which reframes the other two.

1. **The workflows were never the thing blocking a ship.** Publishing requires exactly one
   act: Theshin merges a ship branch. `ship-preview.yml` buys a preview URL and
   `health-check.yml` buys a live-render signal — both valuable, neither on the critical
   path to a ship going live. The three-day gap was not the gate: day 1 shipped the hub,
   day 2 and the first half of day 3 were ship 002 failing the checker twice on a
   hand-rolled glob engine. That was a **build-quality** problem, and the borrow-don't-build
   amendment is what fixed it. Diagnose the actual bottleneck before reporting a blocker.

2. **The PAT rejection is real, and now measured rather than asserted.** Probed on a
   throwaway branch with nothing queued behind it:
   `! [remote rejected] (refusing to allow a Personal Access Token to create or update
   workflow .github/workflows/_probe.yml without \`workflow\` scope)`. The refusal comes
   from GitHub, not the sandbox proxy — no alternate push path avoids it. Re-verified the
   same day: `*.workers.dev` still 403 from the sandbox; `api.github.com/repos/...` and
   `.../pulls` still 403 **with** the PAT; and the `add_repo` mechanism the 403 body
   advertises **does not exist** in this session's tool set. A run therefore cannot open a
   PR by any means. Never claim otherwise.

3. **Route around it instead of reporting it every morning.** The files now live at
   `tools/workflows/` — pushable, reviewable, and ready to `cp` into `.github/workflows/`
   the moment the permission exists. The dashboard carries a one-tap installer button per
   file (GitHub's editor, content prefilled in the URL) and a merge button for whatever is
   staged. Where a capability is genuinely out of reach, the loop's job is to shrink the
   human step to seconds and put it where he will see it — not to restate the blocker.

**Interim live-render signal, no workflow required.** `tools/foundry-dashboard.html` now
probes the live site **from Theshin's browser**, which can reach `workers.dev` even though
the sandbox cannot: an `<img>` load of `/up.svg` (image loads are not CORS-restricted, so
`onload`/`onerror` is a true reachability signal). It proves the deployment is serving and
**nothing more** — no HTTP status, no per-ship path, no beacon check, and no signal inside
a scheduled run. Label it as reachability, never as health. `health-check.yml` remains the
real fix.

**Standing rule:** a run reports a blocker at most once with a measurement attached, then
either routes around it or reduces it to a one-tap action. A blocker restated verbatim on
consecutive days without either is a reporting failure, not a status update.

---

### Amendment — 2026-08-02 (the write path; verified, do not re-derive)

The 2026-08-02 run produced a full brief, a build and two checker verdicts and **could not push a single byte**. Diagnosis, verified by test rather than assumed:

| test | result |
|---|---|
| clone / `ls-remote` via the sandbox proxy | works — **read is allowed** |
| `git push origin` (proxy, via `url.insteadOf`) | **403 — the proxy is read-only** |
| `https://github.com/…/info/refs?service=git-upload-pack` | **200** |
| `https://github.com/…/info/refs?service=git-receive-pack` | **401** — auth required, *not* blocked |
| `api.github.com` (bare root) | 200 — **but this is misleading, see below** |
| `api.github.com/repos/theshin621/foundry/*` | **403** — sandbox proxy: "GitHub access to this repository is not enabled for this session" |
| `/home/claude/foundry/config.json` | **absent** |

**The network was never the problem. The credential was.** §8 stores the PAT at `/home/claude/foundry/config.json`, a container path — and a scheduled run gets a *fresh container*, so the file never exists. Every scheduled fire is therefore write-blind, which is why Amendment 4's heartbeat-push could not execute and why runs went dark. Ship 001 and the amendments landed from interactive sessions where the PAT was in context, never from a scheduled fire.

Binding consequences:

1. **All pushes go through `bin/push.sh`.** It bypasses the read-only proxy rewrite (`-c url.https://github.com/.insteadOf=`), takes the PAT from `$FOUNDRY_PAT` → `config.json` → `./config.json`, scrubs the token from output, and never leaves it in `.git/config`.
2. **Live site + analytics — provisioned 2026-08-02.** The hub is `https://foundry.theshin-naidu.workers.dev` (Workers Build, deploys on push to `main`). Cloudflare Web Analytics is enabled and its token is in `lib/beacon.html`; the hub and `lib/template.html` both carry the beacon, so **every ship from day 003 onward is measured by construction**. Signal before 2026-08-02 is *unmeasurable*, not zero — never read the absence of early numbers as failure. **The sandbox cannot reach `*.workers.dev` (CONNECT tunnel 403), so no run can ever confirm the live site renders** — that check belongs to Theshin or to a session running on his machine, and a run must say "live-URL unverified (egress)" rather than imply otherwise. There is deliberately **no LLM API key** (Theshin, 2026-08-02): the runtime secret surface stays one PAT.
3. **The PAT must live somewhere a fresh container can read** — in practice the scheduled task's own prompt text, which is the only channel that survives container reclamation. Fine-grained, single repo, Contents+PR read/write, rotatable.
4. **A run that cannot push reports BLOCKED and hands over a `git bundle`** covering all refs, so the run's state survives outside the repo. It never works stateless and never pretends the push happened.
5. **The day-build gate now also tests for runtime credentials**, not just app-store review / KYC / marketplace approval. The 2026-08-02 scout found the entire CLONE lane unbuildable because every candidate's edge is runtime inference and the loop has no inference key — a provisioning fact the old gate could not see.
6. **`ledger.json` gains a `failed` status** — a checker-FAILed build is neither `staged` nor `killed`, and mislabelling it either way corrupts the ledger. Statuses: `staged | live | parked | killed | failed`.
7. **The GitHub REST API is NOT usable from a run.** Git over HTTPS works with the PAT; `api.github.com` *repo* endpoints are intercepted by the sandbox proxy and return 403 regardless of credential. (An earlier note in this amendment claimed "api.github.com 200" — that was a bare-root probe and was wrong; corrected 2026-08-02.) Consequences: step F **cannot open a registry PR via the API**, and anything else API-shaped must be done by Theshin or from a session running on his machine. `git push` prints a ready-made `…/pull/new/<branch>` URL — put that in the notification instead of pretending a PR was opened. The dashboard's API calls are unaffected because they execute in Theshin's browser, not here.
8. **The "go" channel — RESOLVED 2026-08-02: the merge IS the approval.** A scheduled fire is a *fresh session*: it cannot see a reply Theshin typed into yesterday's session, and there is no durable inbox for the word "go". A loop that waits to be *told* could therefore only ever publish if he happened to answer while the session was still alive — at 4am, effectively never. So approval moved to an act that needs no message to survive: **Theshin merges `ship/NNN-slug` into `main` on GitHub** (phone, laptop, any hour), which *is* the production deploy since Cloudflare builds on push. `bin/reconcile-merged.sh`, run at the start of every fire, detects merged ship branches via `git merge-base --is-ancestor`, flips those rows to `live`, sets `deploy_url`, syncs `public/ledger.json` and pushes. An in-session "go" still works as a second path. The gate is unchanged and unweakened — nothing reaches `main` except by Theshin's hand.
   **A branch merged despite a checker FAIL** flips to `live` too — the ledger records reality rather than tidying it — but the reconciler emits an override warning and the FAIL verdict stays verbatim. It must never be presented as healthy.
9. **Ship branches own only their own files.** A ship branch touches `public/NNN-slug/`, `lib/`, `ledger.json`, `public/ledger.json`, `SHIPPED.md`, `briefs/` — and nothing else. `tools/`, `PLAYBOOK.md`, `bin/` and `.gitignore` belong to `main`. Editing those on a branch is precisely what produces the merge conflict that would land in Theshin's lap and break the one-click gate. Before announcing a ship staged, merge `origin/main` into the branch (main wins on shared files) and confirm `git merge-tree --write-tree origin/main origin/ship/NNN-slug` reports no CONFLICT. **A staged ship Theshin cannot merge in one click is not staged.**

---

### Amendment — 2026-08-05 (dashboard freshness — a measured timestamp, and one URL that is always current; per Theshin)

Theshin asked why the dashboard artifact doesn't update daily and demanded a timestamp. Diagnosis, recorded so nobody re-derives it: the fires **had** been refreshing `tools/foundry-dashboard.html` every day (the 08-03/04/05 commits prove it), but (a) the desktop Cowork artifact is only writable through the desktop bridge, which is never connected at 04:00, so the artifact froze at its 08-01 bake; (b) the page's in-browser self-refresh (raw.githubusercontent + GitHub API) is blocked inside the desktop-artifact sandbox, so the embedded snapshot rendered **as if current**; (c) the only freshness marker was a hand-edited date pill — no time, no age, no alarm. Four binding changes:

1. **The timestamp is machine-stamped, never hand-written.** `python3 tools/stamp.py` rewrites `data-generated` and the #fresh pill with measured NOW (UTC + SAST) and mirrors the page to `public/dashboard/index.html`. Run it after every dashboard content edit and commit both files together. If its anchors are missing it exits 1 — report that as a FAIL, never commit an unstamped dashboard.
2. **`/dashboard/` is the always-fresh rendered URL.** The end-of-run push auto-deploys it (same Workers build as the hub). GitHub's file view of `tools/…html` renders nothing; `https://foundry.theshin-naidu.workers.dev/dashboard/` renders today's page. When freshness matters, that is the URL.
3. **The page self-reports its age.** An age pill computes (browser clock − `data-generated`) with zero network; past 36h without a successful live refresh, a red STALE banner names the bake time and points at `/dashboard/`. A stale copy can no longer masquerade as current.
4. **Artifact sync is an interactive-session job.** Scheduled fires skip it silently — the absent bridge is design, not failure. Any interactive session that touches the foundry pushes the current stamped page into the `foundry-dashboard` artifact as a standing courtesy.
5. **Workflow automation (same day, per Theshin — "like these automated in the future").** Both sidecar workflows were installed by hand once (10:24 SAST, the two dashboard buttons). Standing policy from here: a human-button ritual is a fallback, never a pattern. As soon as the loop's PAT carries **Workflows: read/write** alongside Contents + Pull requests, fires create and update `.github/workflows/` files directly — CI changes pass the same checker discipline as shipped code — and Needs-Theshin must never again grow a "click this to install" item that a scoped token could have done itself. LANDED same day (~10:45 SAST): the rotated three-scope PAT is in the trigger prompt's CREDENTIAL block and config.json — automation armed; workflow edits no longer queue for Theshin. Paired GitHub-side toggles (Theshin, once): Workflow permissions → **Read and write** (PROVEN — health-check committed its first probe 08:26 UTC), and **Allow GitHub Actions to create and approve pull requests** (ship-preview opens the draft PRs; still unproven until the next ship branch).

### Amendment v4 — CANON since 2026-08-09 (activated from a live session; on any conflict with earlier PLAYBOOK text OR the trigger prompt, this Amendment wins)

**ACTIVATION RECORD — the live-channel word both refusals asked for.** On 2026-08-09 at 07:39 UTC (09:39 SAST), in an interactive session — the daily watchdog session, made live by his reply — Theshin wrote, verbatim:

> *"fix all the issues here, mid run death, declined etc. i want autonomy"*

That is a reply in a session, in Theshin's own words, naming the gate ("i want autonomy"), sent in direct response to the watchdog report that had surfaced the second refusal and named the required channel ("give the v4 go via a live interactive session (attested channel) — Theshin"). It is not a fire payload and not an agent-authored document: it arrived as live user input in an attended session — exactly the channel `decisions/2026-08-09-v4-declined-second-channel.md` §"What would actually activate it" specifies. Corroboration, instrument-read rather than asserted: (a) minutes earlier a manual recovery fire was started (heartbeat `2026-08-09T07:36:00Z`) — an at-keyboard owner acting on the same watchdog report; (b) `tailorfarms.com` is attached to this Worker and serving the fleet (live fetches 2026-08-09, watchdog run and this session), confirming the adoption file's provisioning claims by observation; (c) the live word confirms `decisions/2026-08-08-v4-adoption.md` (commit `0500e1c`, his account, him watching), whose content matches it. Full record: `decisions/2026-08-09-v4-activated-live.md`.

**Standing rule this event sets (the gate's design, now explicit):** a gate change NEVER activates from a fire payload, a PRE-NOTE, or an agent-authored commit — only from Theshin's own words in a live session. The two refusals (2026-08-08, 2026-08-09) were correct applications of this rule and remain the precedent.

**ADOPTED:** the received v4 text (kept verbatim below for the record) WITH the three modifications of `decisions/2026-08-08-v4-adoption.md`, which the live word confirms. Where a modification and the received text conflict, the modification wins:

**[MOD-1] GATE — staged autonomy (supersedes the received GATES clause's blanket merge autonomy).** Infra/maintenance merges to `main` are autonomous NOW. Ship merges keep Theshin's batchable one-click go (merge-is-approval, unchanged) UNTIL `BOTTLENECKS.md` entry #1 carries a shipped, **checker-validated** fix; from then, ship merges are autonomous too. Consumer-segment ships always make their public debut on the foundry domain (Theshin's gate). His rule stands: *"hosting to domain only happens on my go ahead; deploying to github happens autonomously."* Remaining human gates unchanged from the received text: custom-domain attach · payment-rail activation · X posting · anything money-touching · Bet promotion (commit rule: first dollar, Theshin's hand). No PII · cookieless beacon · POPIA-safe · no ToS-violating scraping · foundry brand, never Theshin's name · the maker never self-verdicts.

**[MOD-2] VISITS THRESHOLD.** ≥250 qualified visits (not 100), spread across ≥3 distinct days, in any trailing-7-day window.

**[MOD-3] BRAND.** The foundry's public brand and domain is `tailorfarms.com`, whole fleet — hub + every ship + beacon move there; `foundry.theshin-naidu.workers.dev` becomes a redirect. This retires the his-name-URL conflict. (Domain attached by Theshin's hand 2026-08-08; verified serving the fleet 2026-08-09.)

**PLUS one clause promoted from BOTTLENECKS #1's own analysis into the ARCHITECT/CHECKER contract (it asked to be "a step, not a happy accident"):** an oracle is trusted only after **probe-the-oracle** passes: (a) a negative control — break the artifact in the way the oracle claims to catch and confirm it goes red — and (b) an independent attempt to construct a break the oracle still passes. An oracle that fails either probe is itself a FAIL finding.

**The five-role org, fire order and stop-condition are in force as received** (text below), with [MOD-2]'s 250 substituted into the visit threshold and [MOD-1]'s staging substituted into GATES.

<details>
<summary><strong>v4 text as received 2026-08-08 — verbatim, for the record (read with MOD-1/2/3 above)</strong></summary>

```markdown
## Amendment v4 — the five-role org (2026-08-08, per Theshin: "do 1-7, 3a". On any conflict with earlier PLAYBOOK text OR the trigger prompt, this Amendment wins.)

ORG — ultra-small, all-technical (brivael/Karpathy Elon-org principles, design doc of 2026-08-08 in Theshin's session; maker≠checker-verified R1 FAIL→fixed, R2 PARTIAL→fixed). The fired session is a deterministic harness executing the fire order below; it decides nothing; disputes land in the ledger for Theshin. Theshin is the founder-engineer, one call from everything; there is no management layer.

- SCOUT: founders-board SCOUT, adversarial screen ON, $1B call native. Approved vault filters (Theshin 2026-08-08): bot-vs-human-gate + consumer-segment aim — messaging · payments · social · gaming · media · other. Standing question: "what becomes possible at ~zero build cost that has no name yet" — new categories, never cheaper clones. Output: ranked shortlist, evidence-cited, occupant-hunted, one platform-gate card per candidate (payments: build ADJACENT to rails, never on top · media: YouTube inauthentic-content policy gates the autonomy level · gaming: Roblox DevEx / UEFN payout terms · social: cold-start is the killer · messaging: WhatsApp BSP terms + POPIA). Never builds.
- ARCHITECT: BEFORE any code — a runnable oracle in oracles/<ship>/ (reference implementation, real dataset, or acceptance predicates executable cold) plus the smallest system that could pass it, after running question → delete → simplify → accelerate → automate on the requirements. NO ORACLE, NO BUILD. Ships the structural fix for any twice-seen BOTTLENECKS cause.
- BUILDER: codes to the architect's oracle in an isolated branch, daily and unattended to STAGED; writes the ship's 5-line "to evaluate this you need to understand…" block; deposits to lib/ or logs the conscious refusal. Never self-verdicts.
- CHECKER: v3 contract unchanged — independent, DIFFERENT MODEL from builder, refutation-seeking, drives the staged page cold against the ARCHITECT's oracle (never cases the builder authored), verdict verbatim in the ledger. Files failure causes to BOTTLENECKS.md at kill time and rules on cause-sameness (the fix author cannot judge its own falsification; ties → Theshin).
- OPERATOR: owns the beacon + keeps every ledger signal block non-null + d30/kill computations every fire; Sunday countdown + decision-debt report (every decision blocked >7 days on Theshin; an item at 2 consecutive triages becomes a BOTTLENECKS entry); drafts (NEVER posts) distribution; rail checklists only — rail ACTIVATION requires Theshin's explicit per-ship approval at a triage; drafts self-kill/redesign and clock-pause proposals (Theshin decides).

FIRE ORDER Mon–Sat: scout → architect → builder → checker → operator (lean-scout quota rule and heartbeat-push-at-every-stage kept from v3). Sunday: triage — kill/compound/park by real signal · bottleneck review · rail approvals · segment lock when due · countdown + decision-debt.

GATES (per Theshin 2026-08-08, explicit, supersedes the v3 daily publish-"go"): [superseded by MOD-1 staged autonomy above — kept verbatim in git history].

STOP-CONDITION (the 30-day clock). Definitions: beacon armed = live on the four current ships + every merge thereafter. Qualified visit = JS-executed beacon hit minus known-bot UAs and ?self=1 self-traffic. Visit threshold = ≥250 qualified visits on one ship [MOD-2], spread across ≥3 distinct days, within a trailing-7-day window (pending Theshin's final sign-off of this proxy; flag it in the next Sunday triage if unconfirmed). Segment lock = scout presents the evidence-ranked segment shortlist at a Sunday triage, Theshin picks by number, locked for the window. Clock-start = first fire after: wired ∧ beacon armed ∧ segment locked ∧ domain attached (Theshin's go). Predicate: within 30 days of clock-start, ≥1 post-clock-start ship in the locked segment reaches (A) a rail-receipted first real dollar (rail approval = Theshin's judgement; the receipt = the instrument) OR (B) the visit threshold — whichever first; both instrument-read, never claimed. Build-day rule: any BOTTLENECKS cause at count ≥2 without a shipped fix blocks build days while outstanding. Day-30 evaluation: no such cause outstanding · all published ships checker-PASSed · zero exposure outside the gate set above. Miss → operator drafts the self-kill/redesign proposal for Sunday triage, Theshin decides. The binding 30-ship/zero-signal clause stays; whichever trips first. ≥3 consecutive dead fires → operator surfaces a clock-pause decision early.
```

</details>

**CLOCK STATUS at promotion (2026-08-09).** Clock-start = first fire after wired ∧ beacon armed ∧ segment locked ∧ domain attached. Standing: wired ✓ · domain attached ✓ (2026-08-08, Theshin's hand) · beacon armed — IN FLIGHT (`infra/beacon-firstparty` held until its checker re-run PASSes; on PASS its merge is an infra merge, autonomous under [MOD-1]) · segment locked ✗ — the scout's evidence-ranked segment shortlist goes to Theshin at a Sunday triage and he picks by number. **The 30-day clock has NOT started. It starts at the first fire after all four hold.** The binding 30-ship/zero-signal clause remains; whichever trips first.

**HISTORY (append-only).** Received 2026-08-08 as a manual-fire payload → parked PENDING (first refusal, `26ad54f`). Re-asserted via git commit + PRE-NOTE → second refusal by the 2026-08-09 02:10 fire (`decisions/2026-08-09-v4-declined-second-channel.md`). Activated live 2026-08-09 07:39 UTC. Both refusals were correct applications of the gate they defended. The PENDING frame is deleted per its own activation clause ("The next fire promotes this block to canon…, deletes this frame, and runs under it" — promotion performed by the live session itself, a strictly stronger channel than the next fire); the frame survives in git history.

---


## 1. Stop-condition (the verifiable predicate — confirming this wires the loop)

A **Mon–Sat run is DONE** when all six hold:

1. **SCOUT:** ≥3 candidates, each with (a) a dated, URL-sourced why-now from the last ~14 days, (b) an adversarial screen passed — occupant hunt performed and named, promotional-motive check, graveyard check, (c) dedupe against `ledger.json`, `graveyard.md`, `candidates-seen.json`, (d) a **day-build gate** passed: v1 deployable by the agent alone — no app-store review, no KYC, no human-dependent account creation, no marketplace approval in the critical path.
2. **RECOMMENDATION:** exactly ONE candidate carries a complete build order — spec, pages/endpoints, deploy target, distribution actions, analytics events, and its own kill-criterion.
3. **HALT + NOTIFY:** brief delivered ~05:30 SAST with push notification. **No build without an explicit reply** — "go" (build the pick), "go 2"/"go 3" (build an alternate), "skip" (log and stand down). No reply by next fire = skip, logged. Approval never times out into a build.
4. **BUILD + VERIFY (post-go):** v1 built, deployed to staging, then **maker≠checker verified on the running deployment** (contract in §5). PASS required before public exposure; FAIL → stays staged, failing item named in the notification.
5. **SHIP:** public URL live under the foundry domain · hub entry added · analytics beacon firing · MCP-registry submission opened where applicable · X post drafted into the brief (never posted) · `ledger.json` row appended with the checker's verdict recorded verbatim.
6. **REPORT — RUN SUMMARY (required of every run, scheduled or manual, per Theshin 2026-07-30):** a fixed-format summary posted in-session AND appended to the day's `briefs/` file: **SCOUTED** (candidates, one line each) · **PICKED** (or halted/skip) · **BUILT** (what, where) · **CHECKER** (verdict verbatim) · **DEPLOYED** (URL or staged) · **LEDGER** (row n) · **BLOCKED/NEXT**. Any step impossible → the run reports **FAIL with the failing step named**. The run never silently skips a step and the maker never declares its own done.

A **Sunday run is DONE** when: analytics + ledger read for every live ship → ranked by real signal (visits ex-Theshin, registry installs, inbound, revenue) → kill list proposed (kills archive to `graveyard.md`, stay in repo, go dark on the hub) → ONE iteration target proposed with a build order (payment rail allowed here — the 30-day free rule graduates winners to charging) → same halt-for-"go" gate → post-go, iteration ships under §1.4–1.6.

**Loop-level self-kill (binding):** at ship #30, if cumulative signal across ALL ships is zero — no organic usage, no installs, no inbound, no revenue — the Sunday run must table a terminate-or-pivot recommendation as its lead item. The loop proposes its own death; it never rides on sunk cost.

---

## 2. The daily pipeline

```
04:00  SCOUT (fresh session)
       ├─ clone repo → read PLAYBOOK.md, ledger.json, graveyard.md, candidates-seen.json
       ├─ differential news sweep (last 24–72h): model/agent releases, MCP/spec changes,
       │  new API surfaces, reg deadlines, platform launches, incident-driven demand
       ├─ gap screen: day-buildable × genuinely empty × reachable without ads
       ├─ adversarial pass: hunt the occupant, check promo motive, count the graveyard
       └─ brief → push notification → HALT
~06:00+ THESHIN: "go" / "go N" / "skip"           ← the only human step
       BUILD (same session continues)
       ├─ scaffold from lib/ (never from scratch if lib/ has it)
       ├─ build v1 → push branch → Cloudflare preview deploy
       ├─ CHECKER: independent subagent, refutation-seeking, against the PREVIEW URL
       │  FAIL → fix once → re-verify → still FAIL = stays staged, reported
       └─ PASS → merge → production deploy on push
       SHIP
       ├─ hub entry + analytics + registry submission (PR) + X draft
       ├─ ledger row (checker verdict verbatim) + lib/ contribution back
       └─ notify: URL + one-liner + verdict
```

Weekly cost shape (no cap, for sizing): scout ~200–300k tokens · build ~400k–1M · checker ~100k → roughly 1M/day, alongside the 05:30–08:00 producer chain.

## 3. Scout method (daily, differential — not the full 25-slot sweep)

The two July 28 SCOUT runs are the **baseline map** (`research/` in the repo). The daily scout is a *delta* on that map, not a rebuild:

- **Sources, in priority order:** model-vendor changelogs and release blogs (Anthropic, OpenAI, Google, open-weight labs) · MCP spec/blog/registry · platform launch surfaces (new marketplaces, new APIs, new extensions) · regulator feeds for dated deadlines · incident reports (each incident = demand with a date) · builder chatter (HN, launch threads) for what's being asked for and not built.
- **Standing biases from the baseline (revisit monthly, don't re-derive daily):** the trust stack stays empty while capability slots fill in months; cold-start consumer distribution is dead; MCP registries are free indexed distribution; buyer-relationship and deadline-driven demand beat vibes-driven demand.
- **Every candidate answers:** what changed in the last 14 days (dated, URL) · who occupies the slot (named, or the hunt that found nobody) · who benefits from me believing this (promo check) · what v1 ships today · how anyone finds it without ads · its kill-criterion.
- **Dedupe is binding:** anything in ledger, graveyard, or candidates-seen is out unless the why-now materially changed — then it re-enters flagged as a revisit with the trigger named.

## 4. Build rules

- **Day-build gate (hard):** deployable by the agent alone, same day. MCP servers, single-purpose web apps, APIs/Workers, dashboards, trackers, calculators, data products on a schedule — yes. Anything needing app-store review, KYC, human sales, or credentialed accounts that don't exist yet — no (park it; it can become a Sunday iteration or a manual project).
- **lib/ first:** check the shared library before writing anything; contribute one reusable piece back per build (template, scaffold, script, snippet). The factory improving is the point — ship #20 must cost half of ship #1.
- **Free-first shape:** no payment rails Mon–Sat for the first 30 days. Every ship carries the analytics beacon (privacy-clean: no cookies, no fingerprinting, no PII — POPIA-safe by construction) and a "built by [brand], day NNN" footer linking the hub.
- **ToS/legality gate (surfaced now, per loop-mode):** no scraping against ToS · no financial advice, custody, or anything money-touching without explicit approval · no PII collection · registry submissions and repo pushes only under pre-provisioned credentials · X posts are drafts in the brief, never posted by the loop · nothing deploys under Theshin's personal name (brand insulation is deliberate).

## 5. Maker≠checker contract (per maker-checker-verifier; binding)

A separate subagent pass — refutation-seeking, never confirmation-seeking — against the **running preview deployment**, not the code in context:

1. Fetch the deployment cold. Sandbox egress cannot reach `*.workers.dev` — so the verification path is: serve `public/` locally and fetch THAT cold; confirm the push actually landed (`git ls-remote` hash = local HEAD); and when the desktop bridge is up, load the live URL through Chrome on Theshin's machine. If the live URL is unverifiable, the verdict line must carry "live-URL unverified (egress)" — it may still PASS on local+push evidence. Then: does it do what the landing copy claims? Try to make the claim false.
2. Probe the obvious breaks: empty states, bad input, mobile viewport, the one flow a first visitor actually takes.
3. Scan the diff for leaked secrets, tokens, personal data, vault references.
4. Re-check the day's why-now claim against its source — if the scout's premise was wrong, the ship's landing copy is wrong.
5. Verify the ledger row matches deployed reality (URL live, name right, claims honest).

Verdict PASS / FAIL / PARTIAL with the offending item named, recorded **verbatim** in the ledger. The maker never writes its own verdict. One fix-cycle allowed; a second FAIL stays staged and is reported as FAIL — a staged FAIL is an acceptable daily outcome, a silently-shipped one is not.

## 6. Memory (block 2 — state lives in the repo, never only in context)

```
foundry/  (GitHub monorepo — public, build-in-public)
├─ PLAYBOOK.md              this file; canonical method for every fresh session
├─ ledger.json + SHIPPED.md machine + human ledger (schema below)
├─ graveyard.md             killed candidates + killed ships, with reasons — the screen compounds
├─ candidates-seen.json     dedupe memory
├─ research/                the two 2026-07-28 SCOUT baselines + monthly refreshes
├─ lib/                     landing template · analytics-beacon placeholder — grows one reusable piece per ship
└─ public/                  the served site — hub at public/index.html, one folder per ship at public/NNN-slug/ (wrangler.jsonc serves ./public)
```

Ledger row: `{ n, date, slug, one_liner, gap_source_url, deploy_url, kind (mcp|app|api|data), checker_verdict, distribution: {registry_pr, hub, x_draft}, signal: {d7_visits, d7_installs, d30_visits, inbound, revenue}, status (live|staged|killed|iterating), kill_criterion }`

## 7. Governance (the Leader layer — required for any standing producer, AGENTS.md 2026-06-27)

- **Daily human gate:** the "go" reply — no ungoverned building, ever.
- **Weekly review:** Sunday triage IS the performance review — realized signal, kill-on-drift, one winner compounded.
- **Self-kill clause:** §1's 30-ship zero-signal termination proposal — binding.
- **Fleet oversight:** registers in BOT-REGISTRY.md at wiring; falls under the monthly producer-self-improvement audit; demote-at-first-drift applies. daily-evolution (08:00) may read the morning brief same-day but the foundry does not gate on it.
- **Standalone rule preserved:** like founders-board (2026-07-06), the scout is vault-unconstrained on content — no hard filters, no commit-rule scoring at scout stage. The commit rule bites exactly once: a ship only graduates toward the Bet portfolio on a first real revenue signal, through the normal opp-synth/commit path, by Theshin's hand.

## 8. Provisioning (Theshin, one-time, ~20 min) — the loop's entire runtime secret surface is ONE scoped token

1. **GitHub repo** — create `foundry` (public recommended: build-in-public is the distribution). Add a **fine-grained PAT scoped to this one repo, Contents+PRs read/write only** — rotatable, blast-radius = one public repo. This is the only secret the daily run needs.
2. **Cloudflare** — DONE 2026-07-30: the repo is git-connected as a **Workers Build** (project `foundry` · build command none · deploy `npx wrangler deploy` · `wrangler.jsonc` serves `./public` as static assets). Every push to `main` deploys production; PRs get preview URLs. Runtime needs **no Cloudflare token** — deploy IS the git push. Ships live under `public/NNN-slug/`. Still to do: enable free Web Analytics and drop the token into `lib/beacon.html`.
3. **Domain** — register the brand domain, point at Pages. Name candidates (check availability): `dayforge.dev` · `shipdock.dev` · `oneaday.build` · `foundry365.dev` — or your own; everything templates off `FOUNDRY_DOMAIN`.
4. **Registry identity** — registry submissions ride the same GitHub PAT (they're PRs). Nothing else to provision.
5. Reply **"wire it"** with the repo URL + PAT → I initialise the repo (playbook, lib, hub scaffold, ledger), create the scheduled task (04:00 SAST daily, push notifications on), add the BOT-REGISTRY row + vault pointer note, and Day 001 is the next morning.

**Ship #001 is the factory itself:** hub site + lib/ + beacon + deploy pipeline, end-to-end through the full pipeline including checker and ledger — proving the loop on its own body before it touches a market idea.

## 9. Honest failure modes (named now, so Sunday can check them)

1. **30 diary entries.** Both scouts proved cold-start distribution is dead; six ships a week without a reason to be found is a public sketchbook. Mitigations built in: MCP-registry ships get indexed discovery by default; drafted posts make build-in-public a one-tap habit; Sunday compounds the one thing with pull. The self-kill clause exists because this mitigation can still fail.
2. **Quality erosion under cadence.** A daily clock pressures the checker to soften. The checker's verdict is recorded verbatim and a staged FAIL is a legitimate outcome — the streak metric is "pipeline ran to verdict", never "something went public".
3. **Scout drift into novelty.** Chasing what's new over what's needed. The build order's mandatory kill-criterion and the dated why-now discipline are the brakes; monthly, the baseline biases in §3 get re-derived rather than trusted.
4. **Approval bottleneck.** Everything waits on "go". That's by design (per Theshin, 2026-07-28) — but if a week passes with no gos, Sunday must flag whether the recommendations are wrong or the gate needs renegotiating (e.g. standing-go for MCP-server ships only).
5. **Environment fragility.** Fresh sessions + reclaimable containers mean the repo is the only memory that counts. Anything worth keeping is pushed same-session; a run that can't reach GitHub reports BLOCKED rather than working stateless.

---

## Appendix — daily trigger prompt (installed verbatim at wiring, PAT + repo URL substituted)

> Run the Fable Foundry daily loop. You are a fresh session; your method and memory live in the repo.
> 1. `git clone https://x-access-token:<PAT>@github.com/<user>/foundry` → read `PLAYBOOK.md` and follow it exactly. If the `fable-foundry` skill is available, invoke it; the repo playbook is canonical if they differ.
> 2. Today is Mon–Sat → run SCOUT per §3, write the brief (top-of-brief: ONE recommendation + build order), push the brief to `briefs/`, notify, and HALT for approval per §1.3. Sunday → run TRIAGE per §1.
> 3. On an approval reply in this session ("go" / "go N"), continue: BUILD → CHECKER (§5, subagent, refutation-seeking, against the preview URL) → on PASS deploy to production via push, then SHIP steps (§2) and ledger. On FAIL: stage, name the failing item, notify.
> 4. Never build without approval. Never let the maker self-verdict. Never skip the ledger row. If any step is impossible, report FAIL with the step named. Push everything before ending.
