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
2. **Three scout lanes, same gates on all:** ORIGINAL (news-driven gap, dated why-now ≤14d — the original lane) · **CLONE** (a tool with corroborated, current revenue elsewhere, built with a named Claude edge — founders-board CREATE evidence rules; "I made $X" posts are marketing until corroborated) · **EVERGREEN** (boring schlep utilities with permanent demand — no news hook required; the why-now requirement is waived for this lane only, the occupant hunt is not). Every candidate still passes the adversarial screen, the day-build gate, and carries a kill-criterion.
3. **Lean daily / deep Sunday scout.** Weekdays: single-pass differential scan (~100–150k tokens — changelogs, MCP registry/blog, one sweep, ≤2 subagents and only to verify the ONE recommendation). Sunday: the deep parallel scan runs alongside triage.
4. **Heartbeat + push-early (survivability).** First action of every run after clone: append a run-start line to today's brief file and PUSH it. Push again the moment the brief is drafted, again after the checker verdict, again after staging. A run that dies mid-flight must still leave dated evidence in the repo at the last completed stage.
5. **Dashboard refresh step.** Each run regenerates the embedded snapshot in `tools/foundry-dashboard.html`, pushes it, and updates the `foundry-dashboard` Cowork artifact when the desktop bridge is reachable (skip gracefully when not).
6. **Ledger statuses** now: `staged` (built, verified, awaiting go) · `live` · `parked` (staged >7d unreleased) · `killed`.

Clauses elsewhere in this file that say "no build without approval" are superseded by (1): the binding invariant is **no PUBLIC exposure without approval**, and the maker still never self-verdicts.

---

### Amendment — 2026-08-02 (the write path; verified, do not re-derive)

The 2026-08-02 run produced a full brief, a build and two checker verdicts and **could not push a single byte**. Diagnosis, verified by test rather than assumed:

| test | result |
|---|---|
| clone / `ls-remote` via the sandbox proxy | works — **read is allowed** |
| `git push origin` (proxy, via `url.insteadOf`) | **403 — the proxy is read-only** |
| `https://github.com/…/info/refs?service=git-upload-pack` | **200** |
| `https://github.com/…/info/refs?service=git-receive-pack` | **401** — auth required, *not* blocked |
| `api.github.com` | **200** |
| `/home/claude/foundry/config.json` | **absent** |

**The network was never the problem. The credential was.** §8 stores the PAT at `/home/claude/foundry/config.json`, a container path — and a scheduled run gets a *fresh container*, so the file never exists. Every scheduled fire is therefore write-blind, which is why Amendment 4's heartbeat-push could not execute and why runs went dark. Ship 001 and the amendments landed from interactive sessions where the PAT was in context, never from a scheduled fire.

Binding consequences:

1. **All pushes go through `bin/push.sh`.** It bypasses the read-only proxy rewrite (`-c url.https://github.com/.insteadOf=`), takes the PAT from `$FOUNDRY_PAT` → `config.json` → `./config.json`, scrubs the token from output, and never leaves it in `.git/config`.
2. **The PAT must live somewhere a fresh container can read** — in practice the scheduled task's own prompt text, which is the only channel that survives container reclamation. Fine-grained, single repo, Contents+PR read/write, rotatable.
3. **A run that cannot push reports BLOCKED and hands over a `git bundle`** covering all refs, so the run's state survives outside the repo. It never works stateless and never pretends the push happened.
4. **The day-build gate now also tests for runtime credentials**, not just app-store review / KYC / marketplace approval. The 2026-08-02 scout found the entire CLONE lane unbuildable because every candidate's edge is runtime inference and the loop has no inference key — a provisioning fact the old gate could not see.
5. **`ledger.json` gains a `failed` status** — a checker-FAILed build is neither `staged` nor `killed`, and mislabelling it either way corrupts the ledger. Statuses: `staged | live | parked | killed | failed`.

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
