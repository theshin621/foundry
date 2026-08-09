// src/worker.js — the foundry's Worker. Serves public/ as before, plus three beacon routes.
//
// BEFORE THIS FILE, wrangler.jsonc was assets-only (no `main`), so Cloudflare served
// public/ directly. Adding `main` means the Worker now fronts every request and must
// fall through to env.ASSETS for everything that is not a beacon route.
//
// TWO-STEP DEPLOY (adopted 2026-08-09 from the rebuild checker's finding 4 — the old
// comments here and in wrangler.jsonc contradicted each other on blast radius, and
// neither claim was verifiable from the sandbox):
//   STEP 1 — merge with NO kv binding. Proves the `main`-fronts-the-site change alone.
//            The Worker runs fine unbound: hits are accepted (204) but not counted
//            (env.BEACON absent), /_b/stats answers 503 {"error":"kv-unbound"}.
//   STEP 2 — one-line commit adding kv_namespaces (namespace foundry-beacon,
//            id 4849d5cb422843d49e27535fa796644d — provisioned by Theshin's hand,
//            decisions/2026-08-08-v4-adoption.md). If THIS deploy fails, revert is one
//            line and step 1 keeps serving.
// Per Cloudflare's documented behaviour a script-upload failure leaves the previous
// deployment serving (it does not take the site down) — stated as documentation, not
// as sandbox-verified fact; the two-step split exists so neither claim is load-bearing.

import { decide, COUNTABLE } from './beacon-core.js';

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

      // FIXED 2026-08-09 (rebuild checker finding 8): the old check was 512 UTF-16 code
      // units AFTER an unbounded read — a 2 MB POST was read in full, and 450 CJK chars
      // (1384 bytes) slipped under "512". Now: declared length is rejected before the
      // read, and the kept-body test is BYTES. A chunked body with no content-length is
      // still read then dropped by the byte test — bounded by the platform's own request
      // limits, cost-only, no key can be minted either way (the allowlist holds).
      const declared = parseInt(request.headers.get('content-length') || '0', 10);
      if (declared > 1024) return new Response(null, { status: 204, headers: { 'cache-control': 'no-store' } });
      let payload = null;
      try {
        const body = await request.text();
        if (new TextEncoder().encode(body).length <= 512) payload = JSON.parse(body);
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
      // REBUILT 2026-08-09 (rebuild checker finding 3): the list()-then-get design was
      // bounded in *pagination* and *concurrency* but not in TOTAL subrequests — the
      // keyspace grows one key per (path, day), so by elapsed time alone (~13 days on
      // the Free 50-subrequest ceiling) the endpoint would exceed the per-invocation
      // limit and take down the exact feed the kill-criteria read. Key insight: the key
      // shape v1:<date>:<path> is fully known, so NO list() is needed — generate the
      // day keys directly and hard-cap the total gets at 44 (< the Free ceiling of 50,
      // with margin). Coverage: ?days=N (default 10, enough for the trailing-7-day
      // stop-condition metric with margin) across all countable paths, or a deep
      // ?path=/one-ship/&days=30 single-path query for d30 reads. Both bounded.
      const HARD_CAP = 44;
      const one = url.searchParams.get('path');
      const paths = one ? (COUNTABLE.has(one) ? [one] : []) : [...COUNTABLE];
      if (one && paths.length === 0) {
        return new Response(JSON.stringify({ error: 'unknown-path' }), { status: 404, headers: JSON_HEADERS });
      }
      let days = Math.max(1, Math.min(parseInt(url.searchParams.get('days') || '10', 10) || 10, one ? 30 : 10));
      while (paths.length * days > HARD_CAP) days--;
      const now = Date.now();
      const dates = Array.from({ length: days }, (_, i) => new Date(now - i * 86400000).toISOString().slice(0, 10));
      const keys = [];
      for (const p of paths) for (const d of dates) keys.push({ p, d, k: `v1:${d}:${p}` });
      const vals = await Promise.all(keys.map(({ k }) => env.BEACON.get(k)));
      const out = {};
      keys.forEach(({ p, d }, i) => {
        const n = parseInt(vals[i] || '0', 10) || 0;
        if (n > 0) (out[p] ||= {})[d] = n;   // zero days omitted; absent path = zero visits
      });
      for (const p of paths) out[p] ||= {};
      return new Response(JSON.stringify({
        generated: new Date().toISOString(),
        window: { days, from: dates[dates.length - 1], to: dates[0] },
        paths: out,
      }, null, 1), { headers: JSON_HEADERS });
    }

    // ---- everything else: the static site, exactly as before.
    return env.ASSETS.fetch(request);
  },
};
