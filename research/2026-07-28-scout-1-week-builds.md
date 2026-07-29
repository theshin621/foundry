# SCOUT — 5 ideas, one week each

**Run date:** 2026-07-28 · **Mode:** founders-board SCOUT · **Constraint:** shippable in ~1 week
**Verification:** 5 load-bearing "why now" claims re-checked by an independent adversarial pass. Two came back damaged — corrections are inline and the damage is shown, not hidden.

---

## The meta-finding that reordered everything

The distribution channels that produced 2024–25's indie success stories are structurally broken:

- Pew: **1% of users click links cited in AI Overviews**; organic CTR 8% with AIO vs 15% without.
- Google's **21 May 2026 core update** hit programmatic/directory sites at the *domain* level — one operator's six-site sample shows a clean dose-response: 70% programmatic pages → **−78% traffic**; editorial-only → +4%.
- **90% of consumer AI time** sits in ChatGPT + DeepSeek + Gemini (Sensor Tower, Q1 2026).
- AI subscription apps retain **~30% worse** than non-AI (RevenueCat, 115k apps): 12-month annual retention 21.1% vs 30.7%.
- The gap between winners and everyone else **doubled in two years** — top 5% now earn 400x the bottom 25%, up from 200x in 2024.
- **No indie monetisation layer exists** in the two biggest AI ecosystems: Anthropic's marketplace (7 Mar 2026) is enterprise-only, gated on committed API spend; OpenAI's Apps SDK explicitly permits **physical goods only** — "you cannot submit an app with monetization for any digital products/services."

So: anything requiring cold-start distribution is dead on arrival in mid-2026. **The only durable edge left is a buyer relationship or a hard regulatory clock.** Every candidate below is ranked on that basis, which is why three of five cluster around enterprise access rather than spreading prettily across lanes. That concentration is the honest answer, not a failure of imagination.

The realistic unit of work is the **£15–40k proof-of-concept over 2–4 weeks** (Winder.AI rate card, cross-referenced to Robert Half 2026 and G-Cloud 14). Not a SaaS. Not a template pack.

---

## 1. Agentic channel + claims-surge triage for SA short-term insurers

**Lens:** Collison — whose essential workflow do you quietly become. **Score: 24/30**

**Why now (four independent signals stacking inside eleven weeks):**

- **Santam went live on Guidewire cloud core, 9 June 2026** — verified at primary source. The release explicitly names *"Santam's longer-term plans to expand the use of AI and automation across areas such as underwriting, claims, and customer service."* Group CIO **Sam Nkosi** is the named owner. They have finished the expensive, painful part — a modern API-addressable core — and shipped nothing on top of it yet.
- **Naked became the world's first insurer to deliver a *binding* car quote inside ChatGPT, 13 May 2026** — verified as binding, not indicative (Daily Maverick: *"not an estimate or lead-generation teaser, but a final quote that can be accepted by the customer"*), and as a native app on OpenAI's platform, not a link-out. **No SA competitor has matched it in the 11 weeks since.** Every rival exec team has now been asked why not.
- **Two consecutive catastrophe quarters.** Santam booked ~R430m in weather and major claims in Q1 2026, then 4–12 May brought up to 600mm of rain across the Western/Eastern/Northern Cape, Garden Route and Winelands — 10+ deaths, 45 road closures. Claims ops is visibly under-water; "next budget cycle" no longer works as an objection.
- **ITWeb published the target map yesterday (28 July 2026)** — naming Naked, King Price and Discovery Life as having AI in production for fraud/claims, with named executive owners. More useful is who is *absent*: Santam, OUTsurance, Hollard, Bryte, Old Mutual Insure, Momentum.

Anchor number for the CFO conversation: **Nedbank publicly disclosed R186m in realised benefit from 30 AI use cases in 2025** (Evident AI Index for Banks – MEA, 5 June 2026), 312,000 hours saved. Third-party verified, rand-denominated, domestic peer. Baseline for the gap: the FSCA/PA joint study found **insurers at 8% AI adoption vs banks at 52%**, and most institutions with *no dedicated AI governance arrangements at all* — though that survey ran Oct–Dec 2024 and should be treated as a directional floor, not a current number.

**Week-1 build:** a working agentic quote flow against one insurer's *public* rating surface, plus a claims-triage prototype on synthetic FNOL documents — extraction, severity classification, routing, with a confidence gate. Ship it as a 90-second screen recording, not a deck.

**Cheapest first test:** send that recording unsolicited to three named execs from the ITWeb whitespace list. One day of work; the response rate tells you everything. Do not build the second thing until one replies.

**$1B:** yes-if the triage engine generalises into a vertical app on the Guidewire ecosystem (~600 insurer customers globally) rather than staying bespoke to SA / no-because services into a handful of SA insurers is a consultancy with a hard ceiling.

**Pros:** densest why-now in the entire sweep; four signals from independent sources; the edge (enterprise access + insurance domain) is precisely the thing indie builders cannot copy; PoC price band is under most CIOs' discretionary threshold.
**Cons (lead objection):** **the killer here is procurement cycle length, not build capability.** The graveyard is full of insurtech vendors who lost 18 months in SA enterprise procurement and died with a great product. Guidewire sells its own AI modules and Deloitte/EY are already in these accounts. The only survivable shape is a fixed-fee scoped pilot bought on a CIO's signature — the moment it needs a steering committee, walk.

---

## 2. NCC direct-marketing opt-out registry compliance — monthly, statutory, no incumbent

**Lens:** Levels — can v1 ship in a week and charge from day one. **Score: 22/30**

**Why now — and read the correction, the law is harsher than first reported:**

CPA Amendment Regulations gazetted **GN R7380 of 2026, effective 15 April 2026**, no transitional period. Creates a national pre-emptive block registry. Direct marketers must register with the NCC (Annexure P) and **cleanse their marketing databases against the registry monthly** (new Reg 4(7)–(11)).

- Registration commenced **1 July 2026**. Enforcement deadline **1 October 2026** — nine weeks out.
- Fees: **R2,574** initial, R1,930.50 renewal, **R0.12 per record** cleansed (rising R0.02/yr to R0.18 by 2029).
- Penalty: **10% of annual turnover OR R1,000,000, whichever is the *greater*.** That is a floor, not a cap — most published summaries get this backwards.
- Binds *any person who engages in direct marketing* — every SA business doing outbound email, SMS, WhatsApp or telemarketing, any size, any sector, regardless of industry-body membership. Unregistered marketers are barred from contacting consumers electronically.

The reason this is unclaimed: it is fifteen weeks old, the registry only opened for registration this month, and the previous analogue (DMASA's industry-body list) had weak adoption precisely because it lacked statutory teeth. That is the thing that changed.

**Week-1 build:** register as a direct marketer, **document the actual cleansing mechanism**, then build the diff service — ingest a CRM export, suppress against the registry, return a cleaned list plus a dated compliance certificate. Recurring by statute, forever. Front door: done-for-you NCC registration.

**Cheapest first test:** R2,574 and one afternoon — register and observe how cleansing actually works.

**Pros:** the compliance duty is *monthly and permanent*, so recurring revenue is designed in by the regulator rather than by you; no incumbent; nine-week deadline; local market you can reach by phone; stacks naturally with POPIA work; sell through marketing agencies and CRM resellers rather than direct.
**Cons (lead objection):** **the integration surface your product needs is undocumented, and the published sources contradict each other on which direction the data flows.** Michalsons and Bowmans imply marketers *query* the registry; GlobalBusiness states marketers must *submit their full database to the NCC* monthly. Those are opposite architectures with opposite POPIA exposure. Michalsons says outright that it cannot even resolve whether R0.12 is charged per record queried or per record cleaned. If the mechanism turns out to be a manual form, an automated product has no surface to integrate with. **Resolve this before writing a line of code** — and note that if nobody has published the answer, that document is itself the first sellable asset.

---

## 3. Read-mostly portal agent, priced per transaction

**Lens:** Andreessen — which cost curve just flipped. **Score: 20/30**

**Why now, with the correction applied:** Google shipped Gemini 3.6 Flash on **21 July 2026** at **$1.50 / $7.50 per 1M tokens** with **83.0% on OSWorld-Verified** — both figures confirmed on Google's own pricing page and launch blog. Gemini 3.5 Flash-Lite hits 74.0% at $0.30/$2.50. Eight weeks ago, computer use meant a standalone premium model at frontier prices. At Flash rates the per-task cost drops below the labour it replaces, which is what makes per-transaction pricing work at all.

The reason nobody automated SA broker portals, medical-aid claim submission or municipal billing sites is that per-portal engineering cost exceeded the value of a small market. That arithmetic just inverted.

**The correction that reshapes the idea:** Google's Computer Use documentation still marks the capability **Preview**, not GA — *"may contain errors and security vulnerabilities"* — and **3.6 Flash is not on the supported-model list** (3.5 Flash, 3 Flash Preview and 2.5 are). The launch blog and the docs disagree; build on the docs. Worse for the obvious version of this idea: the safety policy **blocks or confirmation-gates payments, retail checkout and regulated goods**, forbids solving CAPTCHAs, and forbids accepting Terms of Service. An unattended agent that transacts is directly contraindicated.

So the shippable form is **read-mostly**: extract, reconcile, monitor, summarise — statement retrieval, claims-status sweeps, document extraction, reconciliation against a system of record — with a human confirmation gate on every write.

**Week-1 build:** one portal, one read-only workflow, end to end, with a screenshot-diff verifier that fails loudly when the UI changes.

**Cheapest first test:** measure cost-per-task against the human minutes it replaces. If cost/task exceeds ~30% of the loaded labour cost, kill it — the margin will not survive maintenance.

**$1B:** yes-if one portal *category* has thousands of near-identical instances (every SA medical-aid scheme, every municipal billing portal) so a single integration serves many buyers / no-because bespoke per-portal work with UI-change maintenance is a services business wearing a product costume.

**Pros:** genuine, verified cost-curve flip; the workflows have no API and never will; sells into the same accounts as idea 1; per-transaction pricing means the buyer's ROI is arithmetic rather than faith.
**Cons (lead objection):** **the graveyard here is deep and recent.** Adept AI was acqui-hired by Amazon in 2024 after failing to commercialise general computer-use agents, and the 2024–25 wave of browser-agent startups died the same way — general agents were unreliable, and the ones still alive are narrow. Add Preview status and write-action gating, and the honest scope is one workflow with a verifier, not a platform.

---

## 4. AI-output assurance: the evidence file, not the model

**Lens:** Thiel — the secret nobody will say out loud. **Score: 19/30**

**Why now:** On **10 April 2026** South Africa gazetted its draft National AI Policy (Notice 3880). On **26 April 2026** the Minister withdrew it, after at least **6 of 67 academic citations were found to be AI hallucinations**. Every SA enterprise legal and risk team read that story. The failure mode was not a bad model — it was *unverified AI output shipped by a serious institution*.

Set that against the FSCA/PA finding that most SA financial institutions have **no dedicated AI governance arrangements at all**, and the regulators' stated intention to publish a discussion paper on AI supervision — still unpublished, meaning firms face a known-but-undated ask. Meanwhile the EU is pricing the same thing: **AI Act Article 4 AI-literacy** obligations become supervisable and penalisable on **2 August 2026** (broadest-scope duty in the Act — every provider and deployer, any sector, any size), and what the regulator wants is an *evidence file*: attendance register, competency matrix by role, dated attestation. Nobody sells the record-keeping artefact; everyone sells the course.

**The secret in one sentence:** in a regulated firm, the sellable AI product is not the output — it is the auditable proof that the output was independently checked before it shipped.

**Week-1 build:** a verification harness productised as a paid add-on — citation tracing to source, an adversarial re-derivation pass on a *different model* that hunts for the failure rather than confirming success, and a signed, dated evidence file as the deliverable. Attach it as a line item to any AI engagement in a regulated SA firm.

**Cheapest first test:** offer it as a priced add-on on the very next engagement. If a buyer will not pay a premium for the evidence file, the thesis is wrong and you have lost a day.

**$1B:** yes-if the evidence file becomes the standard format regulators expect to receive — a Collison-style infrastructure position / no-because if it stays consulting, or if the model vendors ship native citation-verification and absorb it as a feature.

**Pros:** rides a local, dated, embarrassing and extremely well-sourced event that your buyers already know about; differentiates every other engagement you sell rather than competing with them; the method already exists, so week 1 is packaging, not invention; regulated-firm buyers pay for defensibility in a way they never pay for capability.
**Cons (lead objection):** **"governance" is the most crowded pitch in enterprise AI** — OneTrust, TrustArc, Credo AI and every Big-4 practice sell into exactly this anxiety with brand and indemnity you cannot match. The only defensible wedge is being the person already inside the delivery, selling assurance as an attachment. Sold standalone and cold, it loses to a logo.

---

## 5. Africa remittance corridor price-dispersion tracker

**Lens:** Balaji — frontier arbitrage the incumbents structurally cannot publish. **Score: 17/30**

**Why now:** Sub-Saharan Africa remains the world's most expensive remittance destination — **8.78% to send $200** (World Bank Remittance Prices Worldwide, Q1 2025) against a global average of 6.49% and a UN SDG target of 3%. Total remittances to Africa were **$104bn in 2024**; Kenya alone receives ~$4bn/yr. On **27 July 2026** LemFi and BVNK moved the Kenya corridor onto stablecoin settlement at roughly half price: traditional MTOs ~6.5%, stablecoin-routed 2–3%. That is a **350–450bp structural spread**, and it is compliance and last-mile liquidity, not technology.

**IMF Working Paper 2026/056** (27 March 2026) gives the defensible framework: across 4 USD-pegged stablecoins and 27 currencies, a 1% exogenous increase in net stablecoin inflows raises parity deviations by 40bp and depreciates local currencies; halving cross-market frictions cuts the exchange-rate effect by ~a third. It is the only non-promotional quantitative source in the whole corridor story — every vendor number (Yellow Card, BVNK, LemFi, Thunes) quotes 2–3% as *achieved* rather than *advertised*.

Nobody publishes the net-of-cost spread as a time series. That is the gap.

**Week-1 build:** poll published rates for the top 10 Africa-inbound corridors across MTOs (Western Union, WorldRemit, Wise), stablecoin routes and local P2P; publish the live spread in basis points, net of fees and FX, as a dated series.

**Cheapest first test:** publish one week of the series and see whether anyone quotes it.

**$1B:** no-because a transparency dashboard is a credibility asset, not a business / yes-if it becomes the pricing reference that routes actual flow and takes a bp on volume — but that is a licensed payments business, not a week's build.

**Pros:** the underlying data is public and the anchor sources (World Bank, IMF) are genuinely independent, which is rare in this space; structurally unclaimed *because* everyone who holds the data has an incentive to suppress the denominator; cheap to run forever once built; it is the artefact that makes you the person cited.
**Cons (lead objection):** **be honest that this is a credibility asset, not revenue.** The distribution collapse in the meta-finding hits content sites hardest, so it earns nothing standalone — it only pays by making ideas 1–4 easier to sell. And the adjacent trade it looks like it implies is dead: the SA crypto arbitrage spread compressed from ~20% (2016) to roughly zero net of costs by early 2026, and every operator still selling "arbitrage as a service" quotes gross spread. Build the tracker; do not build the trade.

---

## Killed before ranking

- **MCP spec-migration land-grab.** The 2026-07-28 revision — stateless servers, MCP Apps, deprecations — is **still a release candidate**. modelcontextprotocol.io states the current protocol version is **2025-11-25**; `/specification/2026-07-28` returns 404; no final-release post exists. The RC was locked 21 May with final publication *scheduled* for today. Real opportunity, wrong week — and selling against a document that has not shipped is how you lose a client. Also note the 12-month deprecation window carries a 90-day expedited-removal exception where a security advisory exists. **Revisit trigger:** the final-release post appears on blog.modelcontextprotocol.io.
- **EU AI Act Article 50 template pack.** The date is the most solid claim in the sweep — **2 August 2026**, confirmed by the Commission itself, not deferred by the Digital Omnibus (Reg (EU) 2026/1744, in force 27 July 2026, which pushed Annex III high-risk to 2 Dec 2027). But it bites in five days: you would ship into a market that has already bought, from outside the EU, against entrenched incumbents. The residual play is the **2 December 2026** grace period on machine-readable marking for systems already on the market — a four-month runway rather than a five-day sprint. Folded into idea 4 rather than run standalone.
- **Smart-contract audit contests.** Code4rena announced wind-down on 13 May 2026. Live time-boxed contests on 27 July: **five, combined pool $127,000.** The headline bounties ($16m Usual, $15.5m Uniswap v4) are advertised ceilings that have essentially never paid; **Immunefi's median confirmed payout is ~$2,000.** Supply is falling and the median is the honest number.
- **AI red-teaming bounties.** Gray Swan Arena shows *"No ongoing challenges at the moment"* as of today. Last paid challenge (IPI Q1 2026, 25 Feb–11 Mar) had a $40,000 total pool split across two waves — a top-20 wave finish is worth roughly **$360**. Programmatic automation is explicitly prohibited. Skill acquisition, not income.
- **x402 / agent-payments integration.** 100m cumulative transactions generate **~$28,000/day of actual volume** at ~$0.20 average, and Artemis found **roughly half of observed transactions are artificial** — self-dealing and circular funding. There are no merchants to integrate with. Mastercard's Agent Pay for Machines (10 June 2026) is announced with named partners but unconfirmed developer availability.
- **Selling Claude skills / GPT-store apps.** Building for a store that does not exist — see the meta-finding.

---

## Sources

[Guidewire — Santam go-live](https://www.guidewire.com/about/press-center/press-releases/20260609/santam-goes-live-on-guidewire) · [Daily Maverick — Naked binding quotes in ChatGPT](https://www.dailymaverick.co.za/article/2026-05-20-naked-puts-car-insurance-quotes-inside-chatgpt-but-the-fine-print-still-matters/) · [TimesLIVE — Naked first](https://www.timeslive.co.za/news/sci-tech/2026-05-13-naked-becomes-first-sa-insurer-to-offer-binding-quotes-through-chatgpt/) · [ITWeb — insurers deploy AI against fraud](https://www.itweb.co.za/article/insurers-deploy-ai-to-tackle-fraud/dgp45qaBlYxvX9l8) · [FAnews — autumn flooding](https://www.fanews.co.za/article/non-life/15/general/1217/extensive-autumn-flooding/44058) · [Evident AI Index — SA banks](https://www.africaainews.com/p/south-african-banks-lead-africa-in) · [ENS — FSCA/PA AI study](https://www.ensafrica.com/news/detail/11119/fsca-and-prudential-authority-publish-landmar)

[GN R7380 of 2026 — CPA Amendment Regulations](https://lawlibrary.org.za/akn/za/act/gn/2026/r7380/eng@2026-04-15) · [NCC — regulations to curb spam calls](https://thencc.org.za/ncc-welcomes-regulations-to-curb-spam-calls/) · [ENS — CPA amendment newsflash](https://www.ensafrica.com/news/detail/11656/newsflash-consumer-protection-act-amendment-r) · [Michalsons — opt-out registry uncertainty](https://www.michalsons.com/blog/ncc-opt-out-registry-is-a-crisis-for-marketers/81895) · [Property Professional — 1 October deadline](https://propertyprofessional.co.za/2026/06/15/ncc-confirms-october-deadline-for-direct-marketing-compliance-what-agents-need-to-know-now/)

[Google — Gemini 3.6 Flash launch](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-6-flash-3-5-flash-lite-3-5-flash-cyber/) · [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) · [Gemini computer use docs (Preview)](https://ai.google.dev/gemini-api/docs/computer-use)

[Fasken — SA National AI Policy withdrawn](https://www.fasken.com/en/knowledge/2026/04/the-hallucinatory-irony-of-it-all-minister-withdraws-draft-national-ai-policy) · [DLA Piper — withdrawal analysis](https://www.dlapiper.com/en-us/insights/publications/2026/05/withdrawal-of-south-africa-draft-ai-policy) · [European Commission — AI Act framework](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) · [EUR-Lex — Regulation (EU) 2026/1744](https://eur-lex.europa.eu/eli/reg/2026/1744/oj) · [EC — Article 50 transparency FAQ](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act) · [Travers Smith — AI literacy](https://www.traverssmith.com/knowledge/knowledge-container/the-eu-ai-acts-ai-literacy-requirement-key-considerations/)

[IMF WP 2026/056 — stablecoin inflows and FX spillovers](https://www.imf.org/en/publications/wp/issues/2026/03/27/stablecoin-inflows-and-spillovers-to-fx-markets-575046) · [Rio Times — LemFi/BVNK Kenya corridor](https://www.riotimesonline.com/lemfi-bvnk-stablecoin-remittance-kenya-2026/) · [Nairametrics — Yellow Card/Mastercard](https://nairametrics.com/2026/05/19/yellow-card-mastercard-push-stablecoins-to-address-africas-costly-remittance-system/) · [The Open Letter — end of SA crypto arbitrage](https://theopenletter.io/p/end-of-crypto-arbitrage-sa)

[MCP — versioning (current: 2025-11-25)](https://modelcontextprotocol.io/specification/versioning) · [MCP — 2026-07-28 release candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) · [MCP — feature lifecycle policy](https://modelcontextprotocol.io/community/feature-lifecycle)

[RevenueCat — subscription benchmarks 2026](https://www.revenuecat.com/blog/growth/subscription-app-trends-benchmarks-2026/) · [TechCrunch — AI app retention](https://techcrunch.com/2026/03/10/ai-powered-apps-struggle-with-long-term-retention-new-report-shows) · [AdExchanger — AI search reckoning](https://www.adexchanger.com/publishers/the-ai-search-reckoning-is-dismantling-open-web-traffic-and-publishers-may-never-recover/) · [1ClickReport — May 2026 core update](https://www.1clickreport.com/blog/google-may-2026-core-update-programmatic-seo-dead) · [Sensor Tower — State of AI 2026](https://www.prnewswire.com/news-releases/sensor-tower-state-of-ai-2026-report-global-time-spent-on-generative-ai-apps-projected-to-more-than-double-year-over-year-302800844.html) · [Winder.AI — AI consulting rates 2026](https://winder.ai/ai-consulting-costs-2026-hourly-rates-poc-production/) · [OpenAI — Apps SDK monetization](https://developers.openai.com/apps-sdk/build/monetization) · [TNW — Anthropic enterprise marketplace](https://thenextweb.com/news/anthropic-marketplace-claude-enterprise-software)

[Crypto Times — Code4rena wind-down](https://www.cryptotimes.io/2026/05/13/code4rena-announces-wind-down-after-securing-billions-in-defi/) · [Gray Swan Arena](https://app.grayswan.ai/arena) · [CoinDesk — x402 demand assessment](https://www.coindesk.com/markets/2026/03/11/coinbase-backed-ai-payments-protocol-wants-to-fix-micropayment-but-demand-is-just-not-there-yet)

---

*Board personas are simulations of public frameworks, not the views of the named individuals. This brief proposes; it does not promote anything into the vault. Pick one and it goes through JUDGE before anything gets built.*
