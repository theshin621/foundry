# Graveyard

Killed candidates and killed ships, with reasons. The adversarial screen compounds here — nothing in this file gets re-proposed unless its why-now materially changes.

| date | slug/candidate | reason killed | revisit trigger |
|---|---|---|---|
| 2026-08-06 | **codeowners** (ship 003, branch `ship/003-codeowners`, never public) | Three days, three builds, **seven independent checker verdicts, zero PASS**. Killed by the anti-grind clause written into `briefs/2026-08-06.md` *before* the build, not by a judgement made after seeing the verdict. Not killed for being wrong: the matcher is correct and heavily proven (190/190 reference cases against the live page, verified by an independent adversary against a `budget=null` Node reference), and the page is secure, private, output-bounded, off-by-one exact at every limit, deadlock-free, and mobile-clean. It died on a pattern: **every fix cycle closed one defect and revealed a sibling of it.** Attempt 1 froze on an unbounded field; attempt 2 bounded the field and left the segment count open; attempt 3 bounded the segments, metered the hit-rate loop and fixed the path clip — and the re-check found the *same* clip bug at a sibling sink one line away. The residual at death is genuinely one line (`page.src.html:562` calls `cell()` where it needs a 4096-char clip), which is exactly why a fourth day was tempting and exactly why the clause existed. | **None.** Do not re-propose. The engineering was kept and merged to `main` (`lib/door.js` two-cap rule, `lib/nfa.js`, `lib/codeowners.js`, `lib/inline.js`, `lib/checks/codeowners-oracle.json` 171 pairs, `lib/checks/door-limits.json` 11 probes) — a future ship inherits all of it. The branch stays in the repo, dark and unmerged, as the record. Only Theshin can overturn this. |
| 2026-08-06 | mcp-stateless-request-lint | Rejected twice on occupancy, second time on stronger evidence. Why-now is real (2026-07-28 MCP spec; HN front page 2026-08-05, 374 pts) but the tool layer is held by `Roee-Tsur/mcp-spec-check` (npx black-box probe + a published scan of all 7,850 registry servers) and the guide layer went from one site to at least five inside nine days. The only half this loop could build — paste-and-lint — is both the weak half and the occupied half, because the useful form probes a live server URL and a static page cannot make that cross-origin call. | None. |
| 2026-08-05 | cron-expression-generator | Eight live free tools on the first page of one search (crongenerator.dev, appsmith, fasttool, foundthetool, devtoollab, rjl.io, CrontabRobot, elmah.io). The CLONE lane needs corroborated current revenue *plus* a structural edge; the incumbents are already free, already no-signup and already numerous, so there is neither revenue to clone nor an edge left to hold. | None. |

## 015 · `password-csv-remapper` — killed 2026-08-14, at checker, before publication

**What it was.** A single in-browser page converting a Chrome / Bitwarden / LastPass /
1Password 8 password export into Bitwarden's import CSV. Never published; branch
`ship/015-password-csv-remapper` kept and unmerged.

**Why it died — the binding reason is the second one.**

1. **Checker FAIL, 2 SEVERE.** A real NordPass export (`name,password,username,url,note,folder`)
   satisfies the `chrome` detector's `needs`/`forbids`, so the page reported
   `state=ok, format=chrome` and silently dropped the `folder` column. That falsifies the
   page's **own name-checked claim** — *"If your file is a KeePass, Dashlane, NordPass or
   Enpass export, this page tells you so and converts nothing."* It named NordPass and got
   NordPass wrong. Padlock and BitwardenOrg exports collide the same way.

2. **The scout premise was false, and this is what makes it a kill rather than a fix.**
   The checker found [tembrica.com/en/bitwarden-converter](https://tembrica.com/en/bitwarden-converter)
   — free, no signup, **in-browser**, covering all four of ship 015's formats *plus* Bitwarden
   JSON, KeePass 2.x and Firefox, bidirectionally — **ranking page 1** on the exact query this
   ship's only non-ads discovery path depended on. The operator independently corroborated it
   on a second search, which returned the same tool on a second domain
   ([timbrica.com](https://timbrica.com/en/bitwarden-converter)).

**Why the permitted fix cycle was NOT used.** Finding 1 is fixable in an hour. It was not
fixed, on purpose. A fixed ship 015 is a strictly worse duplicate of a page-1 incumbent, and
its kill criterion (<10 visits by 2026-09-13) would then be satisfied by construction. The
anti-grind clause exists for exactly this: **spending the fix cycle would have bought a
better version of a thing that should never have been built.** Killing beats grinding.

**What survives, and what deliberately does not.** `lib/pwcsv-remap.js` and
`lib/csv-parse.vendor.js` stay on the dead branch and are **not** promoted to `lib/` on
`main` — the shared library does not inherit a detector known to misdetect NordPass, the same
call ship 007 made. What *does* survive is `oracles/015-password-csv-remapper/`: the loop's
first differential oracle (`pass_import` on both ends), whose probe found **seven defects
pre-build**, and whose own residual hole — finding 2, a `group`/`otpauth` swap passing
106/106 because every fixture leaves those columns empty — is filed as real and unfixed.

**The honest lesson, and it is about the factory, not the ship.** The occupant hunt ran, was
written up at length, named three occupant classes, and **missed the incumbent that ranks on
the user's actual search query** — because it searched the *problem description*
("convert password manager CSV export format to import another free browser tool") instead of
**what a user would type**. Sixteen negative controls, a differential oracle and a
browser-truth harness cannot save a candidate that should have died at scout. See
`BOTTLENECKS.md`.
