# foundry

One product a day, built and shipped by an AI agent under a human go/no-go gate.

Every morning at 04:00 SAST a fresh Claude (Fable) session scouts the last 24-72h of AI/agent-infrastructure news for a gap that can be built and deployed the same day, recommends exactly one, and waits. On "go" it builds, an independent adversarial checker verifies the running deployment before anything goes public, and the ship lands here — one folder per day under public/, one row in ledger.json, verdicts recorded verbatim including the failures.

Sundays nothing new ships: the loop reads real usage signal, kills the dead, and compounds the one thing that shows pull.

- `PLAYBOOK.md` — the full method, including the stop-condition and the loop's own binding self-kill clause (30 ships, zero signal, it proposes its own termination)
- `ledger.json` / `graveyard.md` — every ship and every kill, with reasons
- `research/` — the scout baselines this loop grew out of

Built in public. The checker's FAIL verdicts stay in the ledger on purpose.
