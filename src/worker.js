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
      const origin = request.headers.get('origin');
      if (origin && new URL(origin).host !== url.host) return new Response(null, { status: 204 });

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
      const out = {};
      let cursor;
      do {
        const page = await env.BEACON.list({ prefix: 'v1:', cursor, limit: 1000 });
        for (const k of page.keys) {
          const [, date, ...rest] = k.name.split(':');
          const path = rest.join(':');
          (out[path] ||= {})[date] = 0;
        }
        cursor = page.list_complete ? undefined : page.cursor;
      } while (cursor);
      // Second pass for values (list() does not return them).
      await Promise.all(Object.entries(out).flatMap(([path, days]) =>
        Object.keys(days).map(async (date) => {
          days[date] = parseInt((await env.BEACON.get(`v1:${date}:${path}`)) || '0', 10) || 0;
        })));
      return new Response(JSON.stringify({ generated: new Date().toISOString(), paths: out }, null, 1), { headers: JSON_HEADERS });
    }

    // ---- everything else: the static site, exactly as before.
    return env.ASSETS.fetch(request);
  },
};
