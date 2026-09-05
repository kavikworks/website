"""Check the public offer, navigation, metadata and intake failure contract."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
errors = []

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.ld = [], set(), []
        self.h1 = 0
        self.in_ld = False
        self.ld_text = ''
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h1': self.h1 += 1
        if 'id' in attrs:
            if attrs['id'] in self.ids: errors.append('Duplicate ID: ' + attrs['id'])
            self.ids.add(attrs['id'])
        if tag == 'a' and 'href' in attrs: self.links.append(attrs['href'])
        if tag in ('script', 'img') and 'src' in attrs: self.links.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') == 'stylesheet': self.links.append(attrs['href'])
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.in_ld = True
            self.ld_text = ''
    def handle_data(self, data):
        if self.in_ld: self.ld_text += data
    def handle_endtag(self, tag):
        if tag == 'script' and self.in_ld:
            self.ld.append(json.loads(self.ld_text))
            self.in_ld = False

def target(path, base):
    p = ROOT / path.lstrip('/') if path.startswith('/') else base.parent / path
    if p.is_dir(): return p / 'index.html'
    if p.exists(): return p
    return p.with_suffix('.html') if not p.suffix else p

pages = [*ROOT.glob('*.html'), *ROOT.glob('*/index.html'), *ROOT.glob('build-concepts/*.html'), *ROOT.glob('guides/*.html')]
pages = sorted(set(pages))
for path in pages:
    parsed = Page()
    text = path.read_text()
    try: parsed.feed(text)
    except Exception as exc: errors.append(f'{path.relative_to(ROOT)}: {exc}')
    if parsed.h1 != 1: errors.append(f'{path.name}: expected one h1')
    for link in parsed.links:
        parts = urlsplit(link)
        if parts.scheme or parts.netloc: continue
        dest = target(unquote(parts.path), path) if parts.path else path
        if not dest.exists(): errors.append(f'{path.relative_to(ROOT)}: missing {link}')
        elif parts.fragment and dest.suffix == '.html':
            dest_page = Page(); dest_page.feed(dest.read_text())
            if parts.fragment not in dest_page.ids: errors.append(f'{path.name}: missing anchor {link}')

for node in ET.parse(ROOT/'sitemap.xml').iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
    url = node.text
    path = target(urlsplit(url).path, ROOT/'index.html')
    if not path.exists(): errors.append('Sitemap destination missing: ' + url)
    elif 'noindex' in path.read_text(): errors.append('Noindex page in sitemap: ' + url)

intake = (ROOT/'intake.html').read_text()
js = (ROOT/'workflow-check.js').read_text()
for prohibited in ('script.google.com', 'scripts.google.com', 'no-cors', 'We got it'):
    if prohibited in intake or prohibited in js: errors.append('False/unverified intake path: ' + prohibited)
for prohibited in ('fetch(', 'XMLHttpRequest', 'localStorage', 'innerHTML'):
    if prohibited in js: errors.append('Unexpected submission/storage/HTML sink: ' + prohibited)
if 'Opening a draft does not send your request.' not in intake:
    errors.append('Email handoff must state that sending is still required')
for file in ('index.html','llms.txt','terms.html','privacy.html','refunds.html'):
    text = (ROOT/file).read_text()
    if 'Paddle' in text: errors.append('Unverified payment claim in ' + file)
for file in ('index.html','llms.txt'):
    if '$149' not in (ROOT/file).read_text(): errors.append('Offer price missing in ' + file)

if errors:
    raise SystemExit('\n'.join(sorted(set(errors))))
print(f'PASS: {len(pages)} public HTML pages; local links, anchors, JSON-LD, sitemap, offer, and intake contract.')
