#!/usr/bin/env python3
"""Build: generates blog/posts.json (slugs sorted newest-first) and rss.xml."""

import json, os, re
from datetime import datetime, timezone
from email.utils import format_datetime

ROOT      = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(ROOT, 'blog', 'posts')
BASE_URL  = 'https://gomesgoncalo.github.io'

def parse_frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n?', text, re.DOTALL)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key, val = key.strip(), val.strip()
        if val.startswith('[') and val.endswith(']'):
            val = [t.strip().strip('\'"') for t in val[1:-1].split(',') if t.strip()]
        elif len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        meta[key] = val
    return meta, text[m.end():]

posts = []
for fname in os.listdir(POSTS_DIR):
    if not fname.endswith('.md'):
        continue
    slug = fname[:-3]
    with open(os.path.join(POSTS_DIR, fname), encoding='utf-8') as f:
        content = f.read()
    meta, body = parse_frontmatter(content)
    posts.append({
        'slug':        slug,
        'title':       meta.get('title', slug),
        'date':        meta.get('date', ''),
        'description': meta.get('description', ''),
        'tags':        meta.get('tags', []),
        'body':        body,
    })

posts = [p for p in posts if p.get('draft') == 'false']
posts.sort(key=lambda p: p['date'], reverse=True)

def reading_time(text):
    words = len(text.strip().split())
    return f"{max(1, (words + 199) // 200)} min read"

# posts.json — metadata objects, newest first
meta_fields = ['slug', 'title', 'date', 'description', 'tags']
out = [{**{k: p[k] for k in meta_fields}, 'read_time': reading_time(p['body'])} for p in posts]
with open(os.path.join(ROOT, 'blog', 'posts.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(f'posts.json: {len(posts)} post(s)')

# rss.xml
def xml(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

items = []
for p in posts:
    if not p['date']:
        continue
    try:
        dt = datetime.fromisoformat(p['date']).replace(tzinfo=timezone.utc)
        pub = format_datetime(dt)
    except ValueError:
        pub = p['date']
    link = f"{BASE_URL}/blog/post.html?slug={p['slug']}"
    items.append(f"""  <item>
    <title>{xml(p['title'])}</title>
    <link>{link}</link>
    <guid isPermaLink="true">{link}</guid>
    <description>{xml(p['description'])}</description>
    <pubDate>{pub}</pubDate>
  </item>""")

rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>Gonçalo Gomes — Blog</title>
  <link>{BASE_URL}/blog/</link>
  <description>Notes on systems, software, and the occasional rabbit hole.</description>
  <language>en-gb</language>
  <atom:link href="{BASE_URL}/rss.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
</channel>
</rss>"""

with open(os.path.join(ROOT, 'rss.xml'), 'w', encoding='utf-8') as f:
    f.write(rss)
print(f'rss.xml: {len(items)} item(s)')

# sitemap.xml
static_urls = [BASE_URL + path for path in ('/', '/blog/')]
post_urls   = [f'{BASE_URL}/blog/post.html?slug={p["slug"]}'
               + (f'<lastmod>{p["date"]}</lastmod>' if p['date'] else '')
               for p in posts]
sitemap_entries = [f'  <url><loc>{u}</loc></url>' for u in static_urls] + \
                  [f'  <url><loc>{BASE_URL}/blog/post.html?slug={p["slug"]}</loc>'
                   + (f'<lastmod>{p["date"]}</lastmod>' if p['date'] else '')
                   + '</url>' for p in posts]
sitemap = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + '\n'.join(sitemap_entries) + '\n'
    '</urlset>'
)
with open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
    f.write(sitemap)
print(f'sitemap.xml: {len(sitemap_entries)} URL(s)')
