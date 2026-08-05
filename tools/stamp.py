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
import re, sys, shutil, datetime, pathlib

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

src.write_text(html)
out = root / 'public' / 'dashboard' / 'index.html'
out.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(src, out)
print('stamped %s UTC -> tools/foundry-dashboard.html + public/dashboard/index.html' % disp)
