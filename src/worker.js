// src/worker.js — the foundry's Worker. Serves public/ as before, plus three beacon routes.
//
// BEFORE THIS FILE, wrangler.jsonc was assets-only (no `main`), so Cloudflare served
// public/ directly. Adding `main` means the Worker now fronts every request and must
// fall through to env.ASSETS for everything that is not a beacon route. Get that wrong
// and the whole site 404s — which is one reason this branch is unmerged and unverified.
//
// PROVISIONING REQUIRED BEFORE THIS CAN DEPLOY (Theshin, Cloudflare dashboard — the loop
// holds no Cloudflare credential by design, PLAYBOOK Amendment 2026-08-02 §2):
//   1. Workers & Pages → KV → Create namespace, name it `foundry-beacon`
//   2. copy its ID into wrangler.jsonc → kv_namespaces[0].id (currently a placeholder)
//   3. merge this branch
// Until (1) and (2) are done a deploy of this branch FAILS on the unknown namespace ID.
// That failure is contained to the branch preview; main is untouched.

import { decide } from './beacon-core.js';

const JSON_HEADERS = {
  'content-type': 'application/json; charset=utf-8',
  'cache-control': 'no-store',
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // ---- POST /_b — record one hit. Returns 204 always; never leaks whether it counted.
    if (url.pathname === '/_b') {
      if (request.method !== 'POST') return new Response(null, { status: 405 });
      // Same-origin only. No CORS headers are ever returned, so a cross-origin page
      // cannot read the response, and this check stops it writing either.
      // FIXED 2026-08-08 (checker finding 2): `Origin: null` is browser-legal — sandboxed
      // iframes and some redirected/private-mode requests send it — and `new URL('null')`
      // throws, which turned the documented "always 204" into an uncaught 500.
      const origin = request.headers.get('origin');
      if (origin) {
        let sameOrigin = false;
        try { sameOrigin = new URL(origin).host === url.host; } catch { sameOrigin = false; }
        if (!sameOrigin) return new Response(null, { status: 204, headers: { 'cache-control': 'no-store' } });
      }

      let payload = null;
      try {
        const body = await request.text();
        if (body.length <= 512) payload = JSON.parse(body);
      } catch { /* malformed body is a drop, not an error the client learns about */ }

      const verdict = decide({
        payload,
        userAgent: request.headers.get('user-agent') || '',
        nowMs: Date.now(),
      });

      if (verdict.count && env.BEACON) {
        // KV has no atomic increment. Read-modify-write can lose a hit when two land
        // in the same instant on different edge nodes. MEASURED CONSEQUENCE, stated
        // rather than hidden: counts are a LOWER BOUND. That is acceptable for a
        // threshold that must be exceeded (>=100) and unacceptable for anything that
        // must be exact — if the stop-condition ever needs exactness, move this to a
        // Durable Object counter, which is the correct primitive.
        ctx.waitUntil((async () => {
          const cur = parseInt((await env.BEACON.get(verdict.key)) || '0', 10) || 0;
          // 400-day TTL: long enough for any trailing-window question, short enough
          // that the namespace never grows without bound.
          await env.BEACON.put(verdict.key, String(cur + 1), { expirationTtl: 400 * 86400 });
        })());
      }
      return new Response(null, { status: 204, headers: { 'cache-control': 'no-store' } });
    }

    // ---- GET /_b/stats — per-path daily counts, so a fire can read its own instrument.
    // Public and read-only: it exposes integers the ledger publishes anyway.
    if (url.pathname === '/_b/stats') {
      if (!env.BEACON) return new Response(JSON.stringify({ error: 'kv-unbound' }), { status: 503, headers: JSON_HEADERS });
      // FIXED 2026-08-08 (checker finding 4): both loops were uncapped. With the
      // allowlist in beacon-core the keyspace is now bounded by |COUNTABLE| x days,
      // but "bounded by an invariant elsewhere" is not a limit — Workers has a hard
      // subrequest ceiling and an unbounded Promise.all walks straight into it. So:
      // an explicit page cap, and gets issued in fixed-size batches.
      const MAX_PAGES = 20, BATCH = 40;
      const out = {};
      const names = [];
      let cursor, pages = 0, truncated = false;
      do {
        const page = await env.BEACON.list({ prefix: 'v1:', cursor, limit: 1000 });
        for (const k of page.keys) names.push(k.name);
        cursor = page.list_complete ? undefined : page.cursor;
        if (++pages >= MAX_PAGES && cursor) { truncated = true; cursor = undefined; }
      } while (cursor);

      for (let i = 0; i < names.length; i += BATCH) {
        const slice = names.slice(i, i + BATCH);
        const vals = await Promise.all(slice.map((n) => env.BEACON.get(n)));
        slice.forEach((n, j) => {
          const [, date, ...rest] = n.split(':');
          const path = rest.join(':');
          (out[path] ||= {})[date] = parseInt(vals[j] || '0', 10) || 0;
        });
      }
      if (truncated) out['_truncated'] = { note: `stopped after ${MAX_PAGES} list pages` };
      return new Response(JSON.stringify({ generated: new Date().toISOString(), paths: out }, null, 1), { headers: JSON_HEADERS });
    }

    // ---- everything else: the static site, exactly as before.
    return env.ASSETS.fetch(request);
  },
};
