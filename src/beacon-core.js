// src/beacon-core.js — the beacon's decision logic, with ZERO Workers APIs touched.
//
// Everything here is a pure function so it can be executed cold by an oracle
// (oracles/beacon/run.mjs) on a machine with no Cloudflare account, no network and
// no deployed Worker. The Worker in src/worker.js is a thin shell around these.
//
// POPIA / privacy contract, binding (PLAYBOOK §4):
//   * no cookies, no localStorage, no fingerprinting
//   * the IP address is READ (to derive nothing but a bot verdict input) and NEVER stored,
//     never hashed into a key, never logged
//   * the only thing persisted is an integer per (date, path)
//   * no user-agent string is persisted — only the boolean verdict derived from it

// Paths the beacon will count. Anything else is dropped rather than stored, so a
// crafted POST cannot create unbounded keys in KV. Ships are NNN-slug; the hub is "/".
const SHIP_PATH = /^\/(\d{3}-[a-z0-9][a-z0-9-]{0,60})\/$/;

/**
 * Normalise a client-supplied path to a countable key, or null to drop the hit.
 * Query strings and fragments are stripped before matching — the ?self=1 marker is
 * read separately by isSelfTraffic() and never reaches the key.
 */
export function normalisePath(raw) {
  if (typeof raw !== 'string' || raw.length === 0 || raw.length > 256) return null;
  // Reject anything that is not a same-origin absolute path.
  if (raw[0] !== '/' || raw.startsWith('//')) return null;
  let p = raw.split('#')[0].split('?')[0];
  if (p.includes('..') || p.includes('\\') || /[\x00-\x1f]/.test(p)) return null;
  // index.html and a bare directory are the same page.
  p = p.replace(/index\.html$/, '');
  if (p === '/') return '/';
  if (!p.endsWith('/')) p += '/';
  if (p === '/dashboard/') return '/dashboard/';
  return SHIP_PATH.test(p) ? p : null;
}

// Substrings that appear in the UA of the crawlers that actually hit a small static
// site. Deliberately conservative: a false positive silently deletes a real visit,
// which is worse for a threshold-based stop-condition than a false negative.
const BOT_UA = [
  'bot', 'crawler', 'spider', 'crawling', 'slurp',
  'googlebot', 'bingbot', 'yandex', 'duckduckbot', 'baiduspider', 'applebot',
  'ahrefs', 'semrush', 'mj12bot', 'dotbot', 'petalbot', 'bytespider',
  'facebookexternalhit', 'twitterbot', 'linkedinbot', 'slackbot', 'discordbot',
  'telegrambot', 'whatsapp', 'embedly', 'quora link preview', 'redditbot',
  'gptbot', 'ccbot', 'claudebot', 'claude-web', 'perplexitybot', 'anthropic-ai',
  'chatgpt-user', 'oai-searchbot', 'amazonbot', 'google-extended',
  'headlesschrome', 'phantomjs', 'puppeteer', 'playwright', 'selenium',
  'python-requests', 'curl/', 'wget/', 'go-http-client', 'node-fetch', 'axios',
  'okhttp', 'java/', 'libwww-perl', 'lighthouse', 'pingdom', 'uptimerobot',
  'monitoring', 'statuscake', 'datadog', 'newrelic', 'better uptime',
];

/** True if the user-agent looks automated. The UA itself is never persisted. */
export function isBotUA(ua) {
  if (typeof ua !== 'string' || ua.length === 0) return true; // no UA at all = not a browser
  const s = ua.toLowerCase();
  return BOT_UA.some((frag) => s.includes(frag));
}

/**
 * Theshin's own traffic. Two independent markers, either one is enough:
 *   * the page URL carried ?self=1 (he clicks his own links from the dashboard)
 *   * the beacon payload carries self:true (set by the snippet once ?self=1 is seen)
 * Self-traffic is dropped, not counted separately — a qualified visit must be a stranger.
 */
export function isSelfTraffic(payload, rawPath) {
  if (payload && payload.self === true) return true;
  if (typeof rawPath === 'string') {
    const q = rawPath.split('?')[1];
    if (q && /(^|&)self=1(&|$)/.test(q.split('#')[0])) return true;
  }
  return false;
}

/** KV key for one path on one UTC day. Contains no user-derived data beyond the path. */
export function dayKey(isoDate, path) {
  return `v1:${isoDate}:${path}`;
}

/** YYYY-MM-DD in UTC from an epoch-ms instant. Passed in, never read from a clock here. */
export function utcDate(nowMs) {
  return new Date(nowMs).toISOString().slice(0, 10);
}

/**
 * The whole decision, in one place: given a request's inputs, either a key to
 * increment or a reason it was dropped. The Worker does the IO; this decides.
 */
export function decide({ payload, userAgent, nowMs }) {
  const rawPath = payload && typeof payload.path === 'string' ? payload.path : null;
  if (rawPath === null) return { count: false, reason: 'no-path' };
  if (isSelfTraffic(payload, rawPath)) return { count: false, reason: 'self' };
  if (isBotUA(userAgent)) return { count: false, reason: 'bot' };
  const path = normalisePath(rawPath);
  if (path === null) return { count: false, reason: 'unknown-path' };
  return { count: true, key: dayKey(utcDate(nowMs), path), path };
}
