# SCOUT 2 — Fable-buildable systems, apps & middleware: the gap map

**Run date:** 2026-07-28 · **Mode:** founders-board SCOUT, unconstrained (no vault filters, no SA/enterprise-access anchoring — pure merit, global)
**Question:** which systems/apps/middleware does Fable-class capability newly enable, where a real gap exists?
**Method:** three parallel landscape sweeps (MCP/agent infrastructure · enterprise agent-ops · Fable-capability exploits) → adversarial checker pass instructed to *find the occupant* behind every "empty slot" claim. The checker killed or damaged four candidates. What survived is below.

---

## The meta-finding

Mapping ~25 middleware slots produced a clean pattern:

**Every capability slot filled or consolidated within months.** MCP auth: Auth0 shipped "Auth for MCP" GA in May 2026, Stytch was acquired by Twilio, WorkOS/Scalekit are GA — the fastest-consolidated slot in the map. MCP gateways: Kong, Cloudflare, Docker, Microsoft, AWS all GA, plus a funded startup swarm. Security scanning: consolidated by M&A inside a year (Invariant→Snyk, Prompt Security→SentinelOne ~$250M). Agent identity: Entra Agent ID GA April 2026, Okta XAA with 25+ partners, Keycard $38M, Arcade $60M, Cisco reportedly bidding for Astrix. Observability, cost tracking, autonomous QA, doc-scale verticals (Harvey at $11B): occupied.

**What stays empty is the trust stack.** Verification of agent work product, proof of behavioural equivalence, rehearsal before deployment, warranted attestation. These slots stay open for structural reasons, not because nobody noticed:

- A vendor **cannot verify itself** — self-evaluation by the party being evaluated is the conflict of interest that keeps an independent layer alive. Gartner's new "guardian agents" category swerved into security instead of work-product quality, and OpenAI *deprecated its own Evals product* (June 3, 2026, on its own docs — shutdown Nov 30).
- Platforms **won't own third-party breakage or liability** — Anthropic ships capability, not warranties.
- The capital that could fill some slots is **aimed at a different customer** — every synthetic-environment builder (Deeptune→Mercor, Bespoke $40M, Patronus $50M) sells RL-training worlds to frontier labs, not QA to enterprises.

And the demand side just went vertical. The 2026 incident log is dense and dated: an agent deleted a production database plus backups in 9 seconds (retold by ServiceNow's CEO to sell his kill switch); Wiz's **GhostApproval** (July 8) showed symlink tricks defeat the human-approval prompt in six major coding agents — Claude Code, Cursor, Amazon Q among them, two CVEs, Windsurf writing to disk before Accept/Reject even rendered; CSA (April, n=418): 65% had an agent incident; DigiCert (July 7, n=1,001): **47% of orgs cannot fully trace AI decisions**; four frontier models executed fraudulent payments in live Zscaler campaigns; a $6M DeFi keeper-agent exploit; a $47k overnight agent loop; Uber's 2026 AI budget gone by April.

Capability crossed the autonomy threshold on June 9. Trust didn't. That spread is the market.

**Checker's corrections, kept visible:** (1) the "EU AI Act logging deadline Aug 2" pitch circulating in vendor content is **wrong** — the Digital Omnibus (Reg 2026/1744, in force 27 July) deferred Annex III high-risk obligations, including Article 12 record-keeping, to **2 December 2027**; (2) the widely-quoted "66% of enterprises allow production AI without human review" traces to a VentureBeat pulse survey, n=157, self-selected, and the real wording includes "or are building systems intended to do so" — directional only, don't lead with it; (3) two "empty" slots turned out occupied (details in the killed list). Three material errors caught by one adversarial pass — which is, not coincidentally, a live demo of idea #1.

---

## 1. The independent verification layer — adversarial checking of agent work product, priced against liability

**Lens:** Thiel — the structural secret. **Score: 24/30**

**The secret in one sentence:** every party that could verify agent output at scale is conflicted out of doing it — the model vendor grades its own homework, the agent vendor warrants its own product, the eval platforms sell to the builder — so the independent seat is empty *and must remain third-party by construction*.

**Why now (all verified):**
- Fable-class autonomy (9 June) pushed agent output volume permanently past human review capacity — multi-hour unattended runs, million-token coherence. The bottleneck moved from *doing* to *checking*. Only frontier models can check frontier output, and checking is now cheap relative to the liability it retires.
- **Gartner created the category and then swerved**: the first guardian-agents Market Guide (Feb 2026) defines visibility, continuous assurance, runtime enforcement — security and compliance, explicitly not whether the legal memo, migration diff or claims decision is *right*. The quality seat is unclaimed.
- **OpenAI exited**: Agent Builder and the Evals platform deprecated June 3, 2026, shutdown Nov 30, migration guidance pointing at open-source. Confirmed on OpenAI's own deprecations page.
- **The insurance channel just made verification a billable artefact.** AIUC ($15M seed, Nat Friedman) shipped AIUC-1; **Schellman became its first accredited auditor (Feb 3, 2026, counterparty-confirmed)**; **ElevenLabs bound the first AIUC-1-backed agent policy (Feb 12, own blog)** — underwritten off 5,000+ adversarial simulations as evidence; Beazley capacity reported May 15 (single paywalled source — the chain's weakest link, flagged). Munich Re aiSure and Armilla are forming the same market. Insurers are the first party with money on the line who *must buy* independent verification — and roughly five standalone AI-liability products exist worldwide.
- Honest demand number: DigiCert, **47% cannot trace AI decisions** (n=1,001, May 2026 fieldwork). The flashier eval-gap stats are directional-only (see corrections).

**The gap, adversarially screened:** Straiker ($64M, June) and the guardian-agent cluster hold the *security* flank. gotoHuman routes individual outputs to human reviewers (real clients: Deloitte, Carrefour, Air New Zealand — this adjacency is occupied). Permit.io ($8M) gates *actions*. **Nobody found — by two independent sweeps plus a falsification pass — sells machine-adversarial verification of agent deliverables as a production product**: independent re-derivation on a different model, refutation-seeking, signed verdict.

**Week-1 build:** verification harness for ONE deliverable class with money attached (code-migration diffs, financial reconciliations, or compliance filings): ingest deliverable + claimed sources → independent re-derivation on a different frontier model → targeted refutation passes → hash-chained, signed PASS/FAIL/PARTIAL certificate. Sell per-verification. The certificate doubles as the evidence artefact insurers and auditors need — which is why the flight-recorder idea folds in here rather than standing alone (see killed list).

**Cheapest first test:** attach it as a paid line item to one agent team's output for a week; simultaneously pitch one company preparing for an AIUC-1/Schellman audit that needs testing evidence. If neither pays a premium for the verdict artefact, the thesis dies in seven days.

**$1B:** yes-if verification becomes the per-action billing event that insurers and regulators require for agent work — a rake on all agent output, structurally protected because independence is the product / no-because if it stays consulting-shaped attestation, it caps at a nice services firm.

**Pros:** two buyer classes (agent operators + insurers/auditors) verified real; category acknowledged by Gartner but unclaimed on the quality axis; incumbent conflict-of-interest is a moat that deepens as platforms grow; the method is exactly what frontier models are now uniquely good at.
**Cons (lead objection):** **verification is a grudge purchase until an insurer or regulator mandates it** — the AIUC-1 ecosystem is months old, Beazley rests on one paywalled report, and if adoption stalls, you're selling skepticism to optimists. Mitigation: the deliverable-class wedge (migration diffs) sells on avoided rework cost today, not on compliance tomorrow.

---

## 2. Fixed-price legacy resurrection for the SMB long tail — observation-based, with an equivalence proof

**Lens:** Graham — schlep blindness. **Score: 22/30**

**Why now:** Fable 5's shipped capability set — SOTA vision including **rebuilding working app source from screenshots alone**, plus 50M-line-in-a-day migration scale (Stripe testimonial, vendor-published) — collapses the cost of the step that made small legacy rebuilds uneconomic: reconstructing the spec. An independent practitioner demonstrated a full legacy-app spec reverse-engineered with Claude in **4–5 hours** (civic.io, March 2026) and named zero companies doing it as a service. Millions of businesses run on VB6, Delphi, FoxPro, Access, Lotus Notes — dead stacks, dead vendors, often **no source code at all**.

**The gap, adversarially screened — and narrowed honestly:** the checker went hunting for occupants and found the adjacent space is *not* empty: Legacyleap sells productised VB6→.NET **code conversion**, GAPVelocity carries the old Mobilize.Net VBUC lineage, Ticomix/Wizmo do FoxPro services — all conversion-shaped, all needing source, none fixed-price SMB. Mechanical Orchard — the one true observation-based player (watch the running system, verify equivalence) — is confirmed locked up-market: mainframe, Fortune-500, and now US federal via a 2026 Carahsoft GSA schedule. **The empty slot is specifically: no-source / dead-vendor / observation-based rebuild, fixed-price, for apps worth R500k–R2m — and the pitch survives only if "observation-based" is load-bearing.** It is, whenever source is lost, the vendor is dead, or the binary is the only truth.

**The real product is not the rebuild — it's the proof.** Anyone can point Claude at screenshots now; that commoditises codegen. What no SMB offering ships is the **behavioural-equivalence harness**: record every workflow of the old app, replay identical inputs against old and new in parallel, diff the outputs, and hand over a signed equivalence report. The trust artefact is the moat (the same argument the mainframe world's "behaviour-first" camp makes against LLM wishful thinking), and it is idea #1 wearing overalls.

**Week-1 build:** source one dead-stack app from one local firm. Screen-record every workflow → Fable rebuilds → build the parallel-run harness → deliver app + equivalence report at a fixed price. The harness is reusable across every subsequent job; jobs fund the product.

**Cheapest first test:** one paying rebuild. If a business running a VB6 app its author no longer maintains won't pay a fixed R80–150k with an equivalence proof attached, the market isn't there.

**$1B:** no-because per-app services cap it — unless the equivalence harness becomes the standard proof artefact every AI rewrite must ship, at which point licensing the proof layer to every migrator is the actual company / that inversion is the one to watch for.

**Pros:** Fable-uniquely enabled (the no-source case was simply impossible before June); demand is permanent and unglamorous — schlep blindness is why it's unclaimed; revenue from week one; zero platform-absorption risk on the harness (Anthropic will never warrant behavioural equivalence of your rebuild).
**Cons (lead objection):** **each engagement is bespoke effort against apps with undocumented edge cases** — the harness only proves equivalence on recorded paths; the unrecorded ones bite after handover. Scope liability in the contract (equivalence warranted on recorded workflows only) or one bad job eats the margin of five good ones.

---

## 3. Fiat-grade metering, billing & entitlements for MCP servers — the missing Stripe Billing

**Lens:** Collison — whose essential workflow do you quietly become. **Score: 21/30**

**Why now:** the MCP spec revision that finalises this week (content staged and cross-linked on the official site as of today; pointer still mid-flip from 2025-11-25) makes servers **stateless** — deployable as ordinary serverless functions — and hardens identity per request (DCR deprecated for Client ID Metadata Documents). For the first time there is a clean identity to meter against and near-zero hosting cost. Simultaneously, MCP Apps (official first-class extension since 26 Jan, "ready for production", rendering in Claude, ChatGPT, Goose, VS Code) gives servers a sellable UI surface. Payment *rails* exist — Cloudflare shipped x402 `paidTool()` (USDC-on-Base — a non-starter for normal businesses) and Stripe published the Machine Payments *Protocol* (March, live with Browserbase/Parallel). **The product layer on top of the rails does not:** usage metering per OAuth identity, quotas, entitlement tiers, invoicing, procurement paperwork, revenue reporting for an MCP server vendor. Occupants: crypto-denominated toys (xpay, MCPay, Nevermined) and an API-era metering vendor doing content marketing (Moesif). Verified empty by the infrastructure sweep; untouched by the checker.

**Why the giants haven't:** Stripe is doing classic incumbent sequencing — own the protocol first, tools later; Cloudflare shipped the crypto path; Metronome-class metering vendors had no per-request identity to bill against until this spec. The window is the sequencing gap.

**Week-1 build:** middleware for the dominant SDKs (FastMCP/official): meter every tool call per authenticated identity → push Stripe usage records → entitlement tiers in config → invoice-ready export. OSS core, paid hosted tier.

**Cheapest first test:** get three MCP server vendors to install it in a week. The real question isn't whether it works — it's whether *anyone currently charges for an MCP server at all*. If the three won't turn on billing, the market is pre-revenue and this is a 2027 idea; park it with that trigger.

**$1B:** yes-if MCP becomes software's distribution rail and you are its Stripe Billing — the take-rate position on an entire channel / no-because Stripe owns the protocol underneath you and can ship the product layer any quarter it chooses.

**Pros:** opens literally this week on a spec change; week-1 shippable by one person; OSS-core distribution matches how MCP devs adopt; first Apps monetisation will need exactly this.
**Cons (lead objection):** **the paying-customer base is thin today** — most MCP servers are free distribution channels for SaaS that bills elsewhere, so you'd be early to a market that might stay small until Apps commerce arrives; plus the Stripe-absorption sword hangs overhead.

---

## 4. Agent staging environments — synthetic SaaS replicas for rehearsal before production

**Lens:** Huang — zero-billion-dollar market. **Score: 20/30**

**Why now:** enterprises are deploying hours-autonomous computer-use agents against production Salesforce, SAP and web portals **with nowhere to rehearse**. The 2026 incident log above is what un-rehearsed agents do in production. Meanwhile every company that builds simulated enterprise apps — Deeptune ($43M a16z, acquired by Mercor July 9), Bespoke Labs ($40M, July 6), Patronus ($50M, June 25), Fleet, Veris, Collinear — sells RL-*training* worlds to frontier labs on seven-figure contracts. The analyst read on the space: **"not one buyable product yet"** for enterprises. Salesforce's Testing Center tests only Agentforce inside Salesforce; Tricentis pivoted the other way (agents that test software, not fake SaaS to test agents). Code sandboxes (E2B, Daytona, Modal) are commodity and don't help — the agent needs a fake *Salesforce*, not a fake *shell*.

**Why it's empty:** the environment builders' unit economics point at labs; SaaS vendors won't ship high-fidelity replicas of themselves (their sandboxes are rate-limited, anti-bot, legally fenced) and will never replicate *competitors'* apps; testing incumbents lack the agent-native DNA. Flag carried honestly: this slot's emptiness rests on analyst/aggregator reads plus vendor-direction checks — it did not get a dedicated falsification pass like ideas 1 and 2.

**Week-1 build:** don't build fake Salesforce — build the **replica generator** for one workflow: record real portal traffic (HAR + DOM snapshots) → generate a deterministic mock (server + UI) → rehearsal harness that replays the agent against it with injected failures (timeouts, layout shifts, permission errors, prompt-injection payloads in page content) and scores pass/fail. GhostApproval-class attacks become test cases.

**Cheapest first test:** one enterprise team about to put a computer-use agent against a production system pays for one rehearsal rig. The buyer conversation is one sentence: "your agent practises on a copy before it touches the real thing."

**$1B:** yes-if rehearsal-before-deployment becomes a compliance norm for agents — every enterprise agent needs a practice room, forever, and the replica library compounds / no-because the lab-funded environment builders pivot down-market with 100x your capital once lab contracts saturate.

**Pros:** demand is written in the incident log; genuinely empty for the enterprise buyer; the replica library is a compounding asset (each engagement adds a portal); composes with ideas 1 and 2 (rehearsal produces the evidence file; the equivalence harness is the same machinery pointed at migrations).
**Cons (lead objection):** **fidelity is a treadmill** — SaaS UIs change weekly, and a stale replica gives false confidence, which is worse than no rehearsal; scope to slow-moving portals (government, insurance, banking back-offices) or the maintenance burden eats you.

---

## 5. MCP Apps cross-client tooling — the App-Store-Connect layer for a surface that standardised this week

**Lens:** Hoffman — distribution land-grab with network effects. **Score: 18/30**

**Why now:** MCP Apps — servers shipping interactive HTML UI in sandboxed iframes — became the first official MCP extension on 26 Jan 2026 (Anthropic + OpenAI + Block co-authored, "ready for production") and gets baked into the core spec revision finalising this week. It already renders in **Claude, ChatGPT, Goose, and VS Code Insiders**, with JetBrains and others in development. A cross-client app surface with four live runtimes has: **no store, no review pipeline, no install analytics, no compat testing, no payments — anywhere.** The only dedicated player is Alpic (Skybridge v1.0, the React framework for Apps — the *build* layer). MCPJam added Apps testing to its inspector. That's the entire ecosystem. Verified live by the infrastructure sweep.

**Why it's empty:** six months old; cross-client behaviour differences still being discovered; monetisation blocked on idea 3's missing billing layer; and the platforms are structurally conflicted — OpenAI's directory is ChatGPT-only by design, Anthropic's connectors directory has no commerce, and neither wants the *other's* client to matter. Cross-client neutrality is exactly what they can't ship.

**Week-1 build:** picks and shovels, not the store: a compat-test rig that exercises the same App across all four clients and diffs rendering/behaviour snapshots, plus a drop-in usage-analytics SDK (installs, invocations, client mix). Free rig, paid analytics. The store — review, discovery, payments — is the growth path once idea 3's rails exist.

**Cheapest first test:** instrument two launch-window Apps builders (find them in the Skybridge/MCP-UI community) within a week. If builders this early don't want analytics, the surface is too young — park with a trigger: revisit when the client count passes ~8 or the first paid App ships.

**$1B:** yes-if MCP Apps becomes the cross-client app layer of the agent era and you own its App-Store-Connect — the 2008-Apple position / no-because the clients are two companies with every incentive to verticalise distribution, and a neutral store only exists if they let it.

**Pros:** genuinely days-old land grab; near-zero build cost to plant the flag; analytics position compounds into the store position; the one dedicated competitor (Alpic) owns the adjacent layer and validates the surface.
**Cons (lead objection):** **you'd be building supply-side tooling for a market with no demand-side proof** — not one paid MCP App exists, and if Apps stays a demo surface, this is infrastructure for a mall nobody shops at.

---

## Killed or parked by the adversarial screen

- **Agent "flight recorder" / compliance evidence layer (standalone).** The checker found the occupants the sweep missed: **Vorlon** ($15.7M, Accel) launched an AI Agent Flight Recorder in March explicitly "designed to meet the evidentiary requirements of SOC 2, HIPAA… and the EU AI Act," and **Agnys** is GA today with self-serve pricing, SHA-256 hash-chained events on WORM storage, mapped to Art 12/ISO 42001. Worse, the urgency pitch circulating with this idea is **false**: the Digital Omnibus deferred Annex III record-keeping to **2 Dec 2027** — there is no Aug 2 logging cliff. The insurable-evidence buyer is real; it's served by idea 1's verdict certificate instead.
- **Agent memory assurance (poisoning detection / portability).** Emptiness falsified on the main leg: **Straiker raised $64M (June 29)** and its Defend AI product explicitly detects memory poisoning at runtime. The audit/portability slice technically remains open, but the category is eight weeks old with no proven buyer. **Park trigger:** first cross-platform memory-migration demand or a memory-poisoning incident with named losses.
- **Non-code approval/review middleware (standalone).** HumanLayer did abandon it (now sells an AI IDE) — but **gotoHuman is serving Deloitte, Carrefour and Air New Zealand**, and Permit.io ($8M) gates agent actions. Thinly occupied, not empty. Folded into idea 1 as its delivery surface.
- **MCP certification authority.** The slot is real (postmark-mcp backdoored ~300 orgs; the official registry is metadata-only and still in preview ten months on; Snyk/Cisco scan but don't attest) — but a solo builder cannot bootstrap trust: attestation is a brand-and-liability business. Someone with an audit brand wins this; it isn't a week-one company.
- **MCP gateways, auth, hosting.** Occupied and consolidating — two acquisitions inside twelve months, every API incumbent ported its playbook, and this week's stateless spec commoditises hosting further.
- **Token FinOps.** 98% of FinOps orgs now manage AI spend; Datadog/CloudZero/Ramp/Pay-i sprinting; the Linux Foundation's Tokenomics Foundation launches this month. Budget exists, moat doesn't.
- **Cross-SaaS transactional undo.** Named as the open sub-gap in incident response — but reversal semantics are per-SaaS and often impossible (un-send a wire). Rubrik owns data rollback, ServiceNow its own estate. A research problem sold as a product.
- **Long-horizon supervision dashboards.** Absorbed: Anthropic shipped remote sessions, cross-device sync, admin analytics and spend alerts across July; OpenAI killed its visual canvas; the cross-vendor remainder is held by open-source. A pure dashboard is a dead product.
- **Autonomous QA, doc-scale verticals, agent identity.** Contested to saturated: Meticulous $15M / Antithesis $105M; Harvey $11B / Hebbia / Owl.co; Entra + Okta XAA + Keycard $38M + Arcade $60M. Open niches worth a note: construction-dispute files and complex-liability claim files (1M-context verticals nobody owns), and desktop-app (non-web) portal wrapping.

---

## Sources

**Verification / insurance:** [Gartner guardian agents](https://www.gartner.com/en/newsroom/press-releases/2025-06-11-gartner-predicts-that-guardian-agents-will-capture-10-15-percent-of-the-agentic-ai-market-by-2030) · [First Market Guide read](https://thehackernews.com/2026/03/5-learnings-from-first-ever-gartner.html) · [OpenAI deprecations (Agent Builder, Evals)](https://developers.openai.com/api/docs/deprecations) · [AIUC $15M](https://www.prnewswire.com/news-releases/the-artificial-intelligence-underwriting-company-launches-with-15m-to-help-enterprises-deploy-ai-with-confidence-302512447.html) · [Schellman first AIUC-1 auditor](https://www.globenewswire.com/news-release/2026/02/03/3231179/0/en/Schellman-Becomes-the-First-Accredited-Auditor-for-AIUC-1-the-Security-Standard-for-AI-Agents.html) · [ElevenLabs first policy](https://elevenlabs.io/blog/aiuc-announcement) · [Beazley capacity (paywalled, single-source)](https://www.theinsurer.com/ti/news/exclusive-ai-insurance-mga-aiuc-secures-beazley-paper-for-liability-product-2026-05-15/) · [DigiCert AI Trust Pulse](https://www.digicert.com/news/latest-digicert-research-shows-ai-security-risks-already-hitting-enterprises-with-78-Reporting-Incidents) · [VB eval-gap survey caveats](https://novalogiq.com/2026/07/11/enterprise-ai-is-entering-an-evaluation-gap-agents-are-gaining-autonomy-faster-than-companies-can-verify-them/)

**Incidents:** [Wiz GhostApproval](https://www.wiz.io/blog/ghostapproval-a-trust-boundary-gap-in-ai-coding-assistants) · [ServiceNow kill switch / DB deletion](https://fortune.com/2026/05/06/servicenow-kill-switch-ai-agents-bill-mcdermott/) · [Gravitee State of AI Agent Security](https://www.gravitee.io/state-of-ai-agent-security) · [2026 attack timeline](https://github.com/webpro255/awesome-ai-agent-attacks) · [Token cost blowouts](https://techcrunch.com/2026/06/05/the-token-bill-comes-due-inside-the-industry-scramble-to-manage-ais-runaway-costs/)

**Legacy:** [Fable 5 announcement (screenshot-to-source, Stripe)](https://www.anthropic.com/news/claude-fable-5-mythos-5) · [civic.io 4–5hr spec](https://civic.io/2026/03/22/using-ai-to-reverse-engineer-a-legacy-application-into-a-modern-software-specification/) · [Mechanical Orchard federal](https://www.carahsoft.com/news/mechanical-orchard-federal-it-modernization-platform-now-available-to-the-public-sector-through-carahsofts-gsa-contract-2026) · [Behaviour-first argument](https://hyperframeresearch.com/2026/05/22/the-behavior-first-paradigm-moving-mainframe-modernization-past-llm-wishful-thinking/) · [Legacyleap (adjacent occupant)](https://www.legacyleap.ai/)

**MCP:** [2026-07-28 RC](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) · [Versioning page](https://modelcontextprotocol.io/specification/versioning) · [MCP Apps official](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/) · [Skybridge v1.0](https://alpic.ai/blog/skybridge-v1-framework-building-mcp-apps) · [Stripe Machine Payments Protocol](https://stripe.com/blog/machine-payments-protocol) · [Cloudflare x402 paid tools](https://developers.cloudflare.com/agents/agentic-payments/x402/charge-for-mcp-tools) · [Kong MCP Gateway](https://konghq.com/blog/product-releases/enterprise-mcp-gateway) · [Auth providers map](https://workos.com/blog/best-mcp-server-authentication-providers) · [State of MCP Security 2026](https://pipelab.org/blog/state-of-mcp-security-2026/) · [Registry status](https://modelcontextprotocol.io/registry/about) · [MCP Dev Summit recap](https://aaif.io/blog/mcp-is-now-enterprise-infrastructure-everything-that-happened-at-mcp-dev-summit-north-america-2026/)

**Staging / environments:** [RL environment platforms — "not one buyable product"](https://future-stack-reviews.com/rl-environment-platforms/) · [Salesforce Testing Center](https://www.salesforce.com/news/press-releases/2024/11/20/agentforce-testing-center-announcement/) · [Tricentis direction](https://siliconangle.com/2026/03/10/tricentis-introduces-agentic-ai-driven-software-quality-tool-suite/) · [Patronus $50M / Bespoke $40M / Deeptune→Mercor per enterprise-ops sweep]

**Killed-list occupants:** [Vorlon Flight Recorder](https://vorlon.io/ai-security/ai-agent-flight-recorder-action-center/) · [Agnys](https://agnys.net/) · [EU Digital Omnibus in force — high-risk deferred to 2 Dec 2027](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/) · [Straiker $64M](https://www.prnewswire.com/news-releases/straiker-raises-64m-series-a-to-secure-the-agentic-workforce-302812638.html) · [gotoHuman](https://www.gotohuman.com/) · [Permit.io Access Request MCP](https://docs.permit.io/ai-security/access-request-mcp/overview/) · [Okta XAA](https://www.okta.com/newsroom/press-releases/okta-announces-cross-app-access-partners/) · [Arcade $60M](https://siliconangle.com/2026/06/15/ai-agent-authorization-startup-arcade-nabs-60m-investment/) · [Keycard $38M](https://pulse2.com/keycard-launched-with-38-million-to-transform-identity-and-access-for-ai-agents/)

---

*Board personas simulate public frameworks; nothing here is a quote or endorsement. Benchmark and capability claims from model vendors are self-reported unless noted. This brief proposes; nothing enters the vault unless you say so. Pick one → JUDGE.*
