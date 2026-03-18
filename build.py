#!/usr/bin/env python3
"""Build: generates static post HTML, posts.json, rss.xml, and sitemap.xml.

Usage:
  python3 build.py               # publish only (draft: false)
  python3 build.py --drafts      # include draft posts
"""

import argparse, json, os, re
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape as he
import markdown as mdlib

parser = argparse.ArgumentParser()
parser.add_argument('--drafts', action='store_true', help='include draft posts')
args = parser.parse_args()

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

def reading_time(text):
    words = len(text.strip().split())
    return f"{max(1, (words + 199) // 200)} min read"

def format_date(date_str):
    try:
        dt = datetime.fromisoformat(date_str)
        return f"{dt.day} {dt.strftime('%B %Y')}"
    except ValueError:
        return date_str

def render_post_html(p):
    slug        = p['slug']
    title       = p['title']
    description = p['description']
    tags        = p['tags']
    read_time   = reading_time(p['body'])
    post_url    = f"{BASE_URL}/blog/posts/{slug}.html"

    md = mdlib.Markdown(extensions=['extra'])
    body_html = md.convert(p['body'])

    formatted_date = format_date(p['date']) if p['date'] else ''
    tags_html = ''.join(f'<span class="tag">{he(t)}</span>' for t in tags)

    meta_parts = []
    if formatted_date:
        meta_parts.append(f'<span class="post-date">{he(formatted_date)}</span>')
    meta_parts.append(f'<span class="read-time">{he(read_time)}</span>')
    if tags_html:
        meta_parts.append(f'<div class="post-tags">{tags_html}</div>')
    meta_html = '\n          '.join(meta_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<title>{he(title)} — Gonçalo Gomes</title>
<meta name="description" content="{he(description)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{he(title)} — Gonçalo Gomes">
<meta property="og:description" content="{he(description)}">
<meta property="og:url" content="{post_url}">
<link rel="canonical" href="{post_url}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<script>if (localStorage.getItem('theme') === 'light') document.documentElement.classList.add('light');</script>
<link rel="stylesheet" href="../../shared.css">
<link rel="stylesheet" href="../post.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/base16/tomorrow-night.min.css">
<link rel="alternate" type="application/rss+xml" title="Gonçalo Gomes — Blog" href="/rss.xml">
</head>
<body>

<div id="reading-progress"></div>
<nav>
  <a href="../../index.html" class="nav-logo"><span>~/</span>gg</a>
  <ul class="nav-links" id="nav-links">
    <li><a href="../../index.html#skills" onclick="closeNav()">skills</a></li>
    <li><a href="../../index.html#cv" onclick="closeNav()">cv</a></li>
    <li><a href="../../index.html#projects" onclick="closeNav()">projects</a></li>
    <li><a href="../../index.html#passions" onclick="closeNav()">passions</a></li>
    <li><a href="../../index.html#contact" onclick="closeNav()">contact</a></li>
    <li><a href="../index.html" class="active" onclick="closeNav()">blog</a></li>
  </ul>
  <div class="nav-right">
    <button id="theme-toggle" class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle theme">◐</button>
    <button class="nav-burger" id="nav-burger" aria-label="Toggle menu" onclick="toggleNav()">
      <span></span><span></span><span></span>
    </button>
  </div>
</nav>

<main>
  <div class="container">
    <header class="post-header">
      <div class="terminal-line">
        <span class="prompt-sym">❯</span>
        <span class="prompt-path">~/blog/posts</span>
        <span class="prompt-cmd">cat {he(slug)}.md</span>
      </div>
      <h1 class="post-title">{he(title)}</h1>
      <div class="post-meta-bar">
        {meta_html}
      </div>
    </header>
    <article class="post-content" id="post-content">
{body_html}
    </article>
    <div class="post-nav">
      <a href="../index.html">← all posts</a>
      <a href="../../index.html">portfolio</a>
    </div>
  </div>
</main>

<footer>
  <div class="container">
    <a href="../index.html">← all posts</a>
  </div>
</footer>

<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="../post-utils.js"></script>
<script src="../../shared.js"></script>
<script>
  document.addEventListener('DOMContentLoaded', () => {{
    const contentEl = document.getElementById('post-content');
    hljs.highlightAll();
    buildToc(contentEl);
    addCopyButtons(contentEl);
    initProgressBar();
  }});
</script>
</body>
</html>"""

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
        'draft':       meta.get('draft', 'true'),
        'body':        body,
    })

if not args.drafts:
    posts = [p for p in posts if p.get('draft') == 'false']
posts.sort(key=lambda p: p['date'], reverse=True)

# Remove stale generated HTML files (slugs no longer in the build)
expected_html = {p['slug'] + '.html' for p in posts}
for fname in os.listdir(POSTS_DIR):
    if fname.endswith('.html') and fname not in expected_html:
        os.remove(os.path.join(POSTS_DIR, fname))
        print(f'removed stale: {fname}')

# Static post HTML
for p in posts:
    out_path = os.path.join(POSTS_DIR, p['slug'] + '.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(render_post_html(p))
print(f'posts/*.html: {len(posts)} file(s)')

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
    link = f"{BASE_URL}/blog/posts/{p['slug']}.html"
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
sitemap_entries = [
    f'  <url><loc>{BASE_URL}/</loc></url>',
    f'  <url><loc>{BASE_URL}/blog/</loc></url>',
] + [
    f'  <url><loc>{BASE_URL}/blog/posts/{p["slug"]}.html</loc>'
    + (f'<lastmod>{p["date"]}</lastmod>' if p['date'] else '')
    + '</url>'
    for p in posts
]
sitemap = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + '\n'.join(sitemap_entries) + '\n'
    '</urlset>'
)
with open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
    f.write(sitemap)
print(f'sitemap.xml: {len(sitemap_entries)} URL(s)')
