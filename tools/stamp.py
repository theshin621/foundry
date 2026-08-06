#!/usr/bin/env python3
"""Machine-stamp the dashboard's data-as-of timestamp and publish the served copy.

Run AFTER editing tools/foundry-dashboard.html content, BEFORE committing:

    python3 tools/stamp.py

What it does, in order:
  1. rewrites <html data-generated="..."> with NOW (UTC, ISO)
  2. rewrites the #fresh pill text with the same instant (UTC + SAST)
  3. copies the file to public/dashboard/index.html, so the git-connected
     Workers build serves it at /dashboard/ on the next push

The timestamp is MEASURED, never hand-written — hand-edited dates rot silently
(the desktop artifact sat 4 days stale with no way to tell; 2026-08-05).
Exits 1 if an anchor is missing: a run must report that as a FAIL, not skip it.
"""
import re, sys, json, shutil, datetime, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
src = root / 'tools' / 'foundry-dashboard.html'
html = src.read_text()

now = datetime.datetime.now(datetime.timezone.utc)
iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')
disp = now.strftime('%Y-%m-%d %H:%M')
sast = (now + datetime.timedelta(hours=2)).strftime('%H:%M')

html, n1 = re.subn(r'data-generated="[^"]*"', 'data-generated="%s"' % iso, html, count=1)
html, n2 = re.subn(r'(<span class="pill mut" id="fresh">)[^<]*(</span>)',
                   r'\g<1>SNAPSHOT · baked %s UTC (%s SAST)\g<2>' % (disp, sast),
                   html, count=1)
if n1 != 1 or n2 != 1:
    sys.exit('stamp.py FAIL: anchor missing (data-generated=%d, fresh pill=%d) — do not commit an unstamped dashboard' % (n1, n2))

# Best-effort: bake the last GitHub Actions live-site verdict into the health
# pill, so a copy viewed with fetch blocked (the desktop artifact) shows the
# last KNOWN state instead of a false "UNREACHABLE". A live in-browser probe
# still overrides this whenever it can actually run.
hp = root / 'public' / 'health.json'
if hp.exists():
    try:
        hj = json.loads(hp.read_text())
        ok = bool(hj.get('hub', {}).get('ok'))
        when = str(hj.get('checked_utc', ''))[:16].replace('T', ' ')
        txt = ('LIVE SITE OK · Actions %s UTC' if ok else 'LIVE SITE DOWN · Actions %s UTC') % when
        cls = 'pos' if ok else 'neg'
        span = ('<span class="pill %s" id="health" data-baked="%s" data-baked-class="%s" '
                'title="last GitHub Actions live-site probe, baked at stamp time; a live probe from your browser overrides this when it can run">%s</span>'
                ) % (cls, txt, cls, txt)
        html2, n3 = re.subn(r'<span class="pill [a-z]+" id="health"[^>]*>[^<]*</span>', span, html, count=1)
        if n3 == 1:
            html = html2
    except Exception:
        pass  # never let the health bake break the stamp itself

# Best-effort: point the "Latest ship" button + URL row at the newest LIVE ship
# from ledger.json, so even a fetch-blocked copy opens the right page.
led = root / 'ledger.json'
try:
    ships = json.loads(led.read_text()).get('ships', [])
    live = sorted([s for s in ships if str(s.get('status', '')).startswith('live')],
                  key=lambda s: s.get('n', 0))
    base = 'https://foundry.theshin-naidu.workers.dev'
    if live:
        s = live[-1]
        path = '/' if (s.get('slug') == 'hub' or s.get('n') == 1) else '/%03d-%s/' % (s['n'], s['slug'])
        url, label = base + path, ('hub' if path == '/' else '%03d · %s' % (s['n'], s['slug']))
    else:
        url, label = base + '/', 'hub'
    html, a = re.subn(r'(<a class="btn" id="latest-btn" href=")[^"]*(")', r'\g<1>%s\g<2>' % url, html, count=1)
    html, b = re.subn(r'(<span id="latest-btn-label">)[^<]*(</span>)', r'\g<1>%s\g<2>' % label, html, count=1)
    html, c = re.subn(r'(<a id="latest-url" style="word-break:break-all" href=")[^"]*(">)[^<]*(</a>)',
                      r'\g<1>%s\g<2>%s\g<3>' % (url, url.replace('https://', '')), html, count=1)
    print('latest-ship baked (%d/%d/%d anchors): %s' % (a, b, c, url))
except Exception as e:
    print('latest-ship bake SKIPPED:', e)

src.write_text(html)
out = root / 'public' / 'dashboard' / 'index.html'
out.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(src, out)
print('stamped %s UTC -> tools/foundry-dashboard.html + public/dashboard/index.html' % disp)
