# lib/ — the compounding build library

Every build checks here FIRST and contributes one reusable piece back. Ship #001 populates: landing template + analytics-beacon placeholder (token pending). MCP server scaffold and other pieces get added by the first ship that needs them — every build contributes one piece back. Ship #20 must cost half of ship #1 — this folder is why.

## Ship mechanics (every build follows these)
1. Build into `public/NNN-slug/index.html` starting from `lib/template.html`.
2. Append the ship's row to root `ledger.json`, then `cp ledger.json public/ledger.json` — the hub reads the public copy client-side.
3. Include `lib/beacon.html` contents only once it holds a real token (it is a placeholder until Cloudflare Web Analytics is enabled).
4. Checker runs BEFORE merge: serve `public/` locally (`python3 -m http.server`) and verify there — sandbox egress cannot reach workers.dev, so local render + push-hash + (when the desktop is reachable) Chrome on the live URL is the verification path.
5. Merge to `main` = production deploy (Cloudflare Workers Build, `wrangler.jsonc` → `./public`).
