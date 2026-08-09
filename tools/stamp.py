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

# Bake the Scouted cards + Graveyard rows + candidates tile from repo data, so a
# fetch-blocked copy (the desktop artifact) shows the full candidate history
# instead of an ancient empty-state. Mirrors the page's own JS renderers, which
# simply overwrite these nodes when a live refresh works. (Added 2026-08-06
# after Theshin found the artifact's Scouted panel still showing day 001.)
import html as _h
import re as _re
def _bake_panels(html):
    try:
        c = json.loads((root / 'candidates-seen.json').read_text())
        seen = c.get('seen', c) if isinstance(c, dict) else c
    except Exception:
        seen = []
    def esc(s): return _h.escape(str('' if s is None else s), quote=True)
    def picked(o):
        o = str(o or '').lower()
        return bool(_re.search(r'pick|built|live|staged|rebuild picked', o)) and not _re.search(r'runner-up|first pick for', o)
    cards = []
    for cand in reversed(seen):
        if isinstance(cand, str):
            cards.append('<div class="cand rejected"><div class="cand-h"><span class="name">%s</span><span class="st rejected">dropped</span></div></div>' % esc(cand))
            continue
        outcome = cand.get('outcome') or cand.get('note') or ''
        is_p = picked(outcome)
        st_word = (_re.split(r'[—\-(]', str(outcome))[0] or '').strip() or ('picked' if is_p else 'seen')
        st_word = st_word[:22]
        plain = cand.get('plain') or {}
        rows = ''
        def row(lbl, val, cls=''):
            return ('<div class="lbl">%s</div><div class="val%s">%s</div>' % (lbl, cls, esc(val))) if val else ''
        if plain.get('what') or plain.get('solves') or plain.get('money'):
            rows = row('what', plain.get('what')) + row('problem', plain.get('solves')) + row('money', plain.get('money'), ' money')
        else:
            rows = row('note', cand.get('note') or cand.get('one_liner'))
        cards.append(
            '<div class="cand %s"><div class="cand-h"><span class="name">%s</span>%s<span class="st %s">%s</span>%s</div>%s</div>' % (
                'picked' if is_p else 'rejected',
                esc(cand.get('slug') or cand.get('name') or '?'),
                ('<span class="lane">%s</span>' % esc(cand['lane'])) if cand.get('lane') else '',
                'picked' if is_p else 'rejected', esc(st_word),
                ('<span class="date">%s</span>' % esc(cand['date'])) if cand.get('date') else '',
                ('<div class="cand-r">%s</div>' % rows) if rows else ''))
    scouted = '<div id="scouted-body">%s</div>' % ''.join(cards) if cards else '<div id="scouted-body" class="empty">No scouted candidates recorded yet.</div>'
    grave = '<div id="grave-body"></div>'
    try:
        glines = [l for l in (root / 'graveyard.md').read_text().split('\n')
                  if l.startswith('|') and '---' not in l and not l.startswith('| date')]
        if glines:
            trs = []
            for l in list(reversed(glines))[:5]:
                cells = [x.strip() for x in l.split('|')]
                trs.append('<tr><td class="mono">%s</td><td class="mono">%s</td><td class="one">%s</td></tr>' % (
                    esc(cells[1] if len(cells) > 1 else ''), esc(cells[2] if len(cells) > 2 else ''), esc(cells[3] if len(cells) > 3 else '')))
            grave = ('<div id="grave-body"><h2 style="margin-top:16px">Graveyard · %d</h2><table><thead><tr><th>date</th><th>what</th><th>why killed</th></tr></thead><tbody>%s</tbody></table></div>' % (len(glines), ''.join(trs)))
    except Exception:
        pass
    html, s1 = re.subn(r'<!--BAKE:SCOUTED-->.*?<!--/BAKE:SCOUTED-->', '<!--BAKE:SCOUTED-->%s<!--/BAKE:SCOUTED-->' % scouted, html, count=1, flags=re.S)
    html, s2 = re.subn(r'<!--BAKE:GRAVE-->.*?<!--/BAKE:GRAVE-->', '<!--BAKE:GRAVE-->%s<!--/BAKE:GRAVE-->' % grave, html, count=1, flags=re.S)
    html, s3 = re.subn(r'(<b id="t-scouted">)[^<]*(</b>)', r'\g<1>%d\g<2>' % len(seen), html, count=1)
    print('panels baked: scouted=%d cards (markers %d), graveyard rows (markers %d), tile (%d)' % (len(cards), s1, s2, s3))
    return html

html = _bake_panels(html)

# Best-effort: point the "Latest ship" button + URL row at the newest LIVE ship
# from ledger.json, so even a fetch-blocked copy opens the right page.
led = root / 'ledger.json'
try:
    ships = json.loads(led.read_text()).get('ships', [])
    # kind:infra rows (e.g. 008 beacon) have no public/NNN-slug/ page — linking one
    # 404s. The "latest ship" button only ever points at a page a visitor can open.
    live = sorted([s for s in ships if str(s.get('status', '')).startswith('live')
                   and s.get('kind') != 'infra'],
                  key=lambda s: s.get('n', 0))
    base = 'https://tailorfarms.com'  # MOD-3 (v4 canon 2026-08-09): the fleet's public domain
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
