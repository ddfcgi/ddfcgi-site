#!/usr/bin/env python3
"""Build public/ (every page of ddfcgi.com) from content/ and the Squarespace capture.

    python3 tools/build_images.py   # once, or when images change (copies images and fonts)
    python3 tools/build_site.py     # rebuild the pages

Main pages: the words and layout of each page live in content/<page>.html; this script wraps them in the
shared <head>, header and phone menu. Resources: the 34 posts, the list, and the category and tag pages
are made from the capture's ?format=json copies (capture/squarespace/pages/), at their old addresses.
Images in posts point at local copies (tools/images.json, written by build_images.py).

Also writes /assets/data/posts.json (Resources list pages after "Older", ?category= and ?tag=),
/assets/data/search.json (site search), sitemap.xml, robots.txt and the old-address redirects.
"""
import datetime
import html
import json
import pathlib
import re
import urllib.parse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

ROOT = pathlib.Path(".")
CAP = ROOT / "capture/squarespace"
PUB = ROOT / "public"
CONTENT = ROOT / "content"
SITE = "https://www.ddfcgi.com"
SITE_NAME = "DDF Consulting"
AUTHOR = "Robert Wood"  # Greg (Nov 24, 2026): posts are credited to Robert Wood
FORM_ENDPOINT = "https://ddfcgi.wwm-031.workers.dev/api/consultation"
GA_ID = "G-VPYXSN3NXZ"  # GA4 (Greg, Nov 25, 2026). The old UA-9808568-42 tag stopped working in 2023.
PER_PAGE = 6
ET = ZoneInfo("America/New_York")
IMAGES = json.loads((ROOT / "tools/images.json").read_text())
SUPPORT_URL = "https://fastsupport.gotoassist.com"
LOGO = "/assets/img/ddf-consulting-logo.png"
SHARE_IMAGE = SITE + LOGO

NAV = [
    ("/", "Home", "home"),
    ("/resources", "Resources", "resources"),
    ("/testimonials", "Testimonials", "testimonials"),
    (SUPPORT_URL, "Support", None),
    ("tel:+18882892075", "(888) 289-2075", None),
    ("mailto:info@ddfcgi.com", "info@ddfcgi.com", None),
]


def esc(s):
    return html.escape(s or "", quote=True)


# ---------------------------------------------------------------- shared parts

ICON_SEARCH = ('<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="6.5"/>'
               '<line x1="13.2" y1="13.2" x2="19" y2="19"/></svg>')
ICON_MENU = ('<svg viewBox="0 0 22 22" aria-hidden="true"><line x1="0" y1="5" x2="22" y2="5"/>'
             '<line x1="0" y1="11" x2="22" y2="11"/><line x1="0" y1="17" x2="22" y2="17"/></svg>')
ICON_CLOSE = ('<svg viewBox="0 0 22 22" aria-hidden="true"><line x1="2" y1="2" x2="20" y2="20"/>'
              '<line x1="20" y1="2" x2="2" y2="20"/></svg>')


def nav_links(active, cls=""):
    out = []
    for href, label, key in NAV:
        ext = ' target="_blank" rel="noopener"' if href.startswith("http") else ""
        state = ' class="is-active" aria-current="page"' if key and key == active else ""
        out.append(f'<a href="{esc(href)}"{state}{ext}>{esc(label)}</a>')
    out.append('<a class="site-nav__button" href="/free-analysis">Free Consultation</a>')
    return "\n        ".join(out)


def header(active, overlay=False):
    cls = "site-header site-header--overlay" if overlay else "site-header"
    if overlay and active != "home":
        cls += " site-header--plain-active"
    return f"""<header class="{cls}">
  <div class="site-header__inner">
    <a class="site-header__logo" href="/"><img src="{LOGO}" alt="DDF Consulting" width="196" height="82"></a>
    <nav class="site-nav" aria-label="Main">
        {nav_links(active)}
    </nav>
  </div>
  <div class="mobile-bar">
    <a class="mobile-bar__logo" href="/"><img src="{LOGO}" alt="DDF Consulting" width="196" height="82"></a>
    <div class="mobile-bar__actions">
      <a href="/search" aria-label="Search">{ICON_SEARCH}</a>
      <button type="button" data-menu-open aria-label="Open menu" aria-controls="mobile-menu">{ICON_MENU}</button>
    </div>
  </div>
</header>
<div class="mobile-menu" id="mobile-menu" role="dialog" aria-label="Menu">
  <button class="mobile-menu__close" type="button" data-menu-close aria-label="Close menu">{ICON_CLOSE}</button>
  <nav aria-label="Main">
        {nav_links(active)}
  </nav>
</div>"""


def ga_tag():
    """Google Analytics (GA4). Loads only on the real domain, so visits to the test and preview links
    on workers.dev don't count."""
    if not GA_ID:
        return ""
    return ("<script>if (/^(www\\.)?ddfcgi\\.com$/.test(location.hostname)) {"
            "window.dataLayer = window.dataLayer || []; window.gtag = function () { dataLayer.push(arguments); };"
            f"gtag('js', new Date()); gtag('config', '{GA_ID}');"
            "var s = document.createElement('script'); s.async = true;"
            f"s.src = 'https://www.googletagmanager.com/gtag/js?id={GA_ID}'; document.head.appendChild(s); }}</script>")


def page(path_url, title, body, active=None, overlay=False, description="", og_type="website",
         extra_head="", canonical=True, noindex=False):
    url = SITE + path_url
    desc = f'<meta name="description" content="{esc(description)}">\n' if description else ""
    can = f'<link rel="canonical" href="{esc(url)}">\n' if canonical else ""
    robots = '<meta name="robots" content="noindex">\n' if noindex else ""
    return f"""<!DOCTYPE html>
<html lang="en-US">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
{desc}{can}{robots}<link rel="icon" href="/favicon.ico">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:type" content="{og_type}">
<meta property="og:image" content="{SHARE_IMAGE}">
<meta name="twitter:card" content="summary">
<link rel="preload" href="/assets/fonts/poppins-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/assets/fonts/poppins-latin-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/styles.css">
{extra_head}{ga_tag()}
</head>
<body>
{header(active, overlay)}
<main id="main">
{body}
</main>
<script src="/assets/js/site.js" defer></script>
</body>
</html>
"""


def write(rel, text):
    out = PUB / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)


# ---------------------------------------------------------------- posts

def local_img(url):
    if not url:
        return url
    u = url.split("?")[0]
    if u.startswith("//"):
        u = "https:" + u
    return IMAGES.get(u, url)


def yt_id(block):
    raw = html.unescape(block.select_one("[data-html]")["data-html"]) if block.select_one("[data-html]") else ""
    raw = urllib.parse.unquote(raw)
    m = re.search(r"youtube\.com/(?:embed/|watch\?v=)([A-Za-z0-9_-]{11})", raw)
    return m.group(1) if m else None


def clean_fragment(node):
    """Point images and links at local copies and drop Squarespace-only leftovers."""
    for st in node.select("style.transform-overrides-vars"):
        st.decompose()
    for img in node.find_all("img"):
        src = img.get("data-src") or img.get("src")
        img["src"] = local_img(src)
        for a in ("data-src", "data-image", "data-image-dimensions", "data-image-focal-point", "data-load",
                  "data-image-id", "data-type", "srcset", "sizes", "data-sqsp-image-block-image-container"):
            if img.has_attr(a):
                del img[a]
        img["loading"] = "lazy"
    for a in node.find_all("a"):
        href = a.get("href")
        if href and href.split("?")[0] in IMAGES:
            a["href"] = IMAGES[href.split("?")[0]]
        elif href and href.startswith(SITE):
            a["href"] = href[len(SITE):] or "/"
    return node


def convert_body(body_html):
    soup = BeautifulSoup(body_html, "html.parser")
    parts = []
    for block in soup.select(".sqs-block"):
        classes = block.get("class", [])
        if "spacer-block" in classes:
            continue
        if "html-block" in classes:
            inner = block.select_one(".sqs-html-content") or block.select_one(".sqs-block-content")
            parts.append(clean_fragment(inner).decode_contents().strip())
        elif "code-block" in classes:
            inner = block.select_one(".sqs-code-container") or block.select_one(".sqs-block-content")
            parts.append(f'<div class="code-block">{clean_fragment(inner).decode_contents().strip()}</div>')
        elif "video-block" in classes:
            vid = yt_id(block)
            if vid:
                parts.append(f'<div class="video-block"><div class="video"><iframe src="https://www.youtube-nocookie.com/embed/{vid}" '
                             'title="YouTube video" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
                             'gyroscope; picture-in-picture" allowfullscreen></iframe></div></div>')
        elif "image-block" in classes:
            img = block.select_one("img")
            if img:
                src = local_img(img.get("data-src") or img.get("src"))
                fig = block.select_one("figure")
                mw = ""
                if fig and fig.get("style") and "max-width" in fig["style"]:
                    mw = f' style="{esc(fig["style"])}"'
                parts.append(f'<figure class="image-block"{mw}><img src="{esc(src)}" alt="{esc(img.get("alt", ""))}" loading="lazy"></figure>')
        elif "horizontalrule-block" in classes:
            parts.append("<hr>")
        else:
            inner = block.select_one(".sqs-block-content")
            if inner:
                parts.append(clean_fragment(inner).decode_contents().strip())
    return "\n".join(p for p in parts if p)


def text_of(fragment):
    return re.sub(r"\s+", " ", BeautifulSoup(fragment or "", "html.parser").get_text(" ")).strip()


def load_posts():
    posts = []
    for f in sorted((CAP / "pages").glob("resources_*.json")):
        name = f.name
        if "_category_" in name or "_tag_" in name or "__" in name:
            continue
        item = json.loads(f.read_text()).get("item")
        if not item:
            continue
        ts = int(item["publishOn"])
        when = datetime.datetime.fromtimestamp(ts / 1000, ET)
        modified = datetime.datetime.fromtimestamp(int(item.get("updatedOn") or ts) / 1000, ET)
        posts.append({
            "title": item["title"], "slug": item["urlId"], "url": item["fullUrl"], "ts": ts,
            "date": f"{when:%B} {when.day}, {when.year}", "iso": when.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "modified": modified.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "categories": item.get("categories") or [], "tags": item.get("tags") or [],
            "excerpt_html": (item.get("excerpt") or "").strip(),
            "body": convert_body(item.get("body") or ""), "raw": item,
        })
    posts.sort(key=lambda p: p["ts"], reverse=True)

    # Thumbnails exactly as the live list shows them (only three posts have one)
    list_html = (CAP / "pages/resources.html").read_text()
    soup = BeautifulSoup(list_html, "html.parser")
    thumbs = {}
    for art in soup.select("article.BlogList-item"):
        a = art.select_one("a[href]")
        img = art.select_one("img")
        if a and img:
            thumbs[a["href"]] = local_img(img.get("data-src") or img.get("src"))
    for p in posts:
        p["thumb"] = thumbs.get(p["url"])
        # The list shows the excerpt as plain inline text
        ex = BeautifulSoup(p["excerpt_html"], "html.parser")
        p["excerpt"] = "".join(str(x) for x in (ex.p.contents if ex.p else ex.contents)).strip() if p["excerpt_html"] else ""
        p["description"] = text_of(p["excerpt_html"]) or text_of(p["body"])[:160]
    return posts


def card(p):
    img = (f'<a class="blog-card__image" href="{p["url"]}"><img src="{esc(p["thumb"])}" alt="" loading="lazy"></a>'
           if p["thumb"] else "")
    ex = (f'<div class="blog-card__excerpt">{p["excerpt"]} <a class="blog-card__readmore" href="{p["url"]}">Read More &nbsp;→</a></div>'
          if p["excerpt"] else "")
    return (f'<article class="blog-card">{img}<h2 class="blog-card__title"><a href="{p["url"]}">{esc(p["title"])}</a></h2>'
            f'{ex}<div class="meta"><time datetime="{p["iso"]}">{esc(p["date"])}</time></div></article>')


def plus(s):
    return urllib.parse.quote(s, safe="").replace("%20", "+")


def blog_list_page(posts, filter_label="", older_extra=""):
    first = posts[:PER_PAGE]
    nav = ""
    if len(posts) > PER_PAGE:
        nav = f'<a class="older" href="/resources?offset={first[-1]["ts"]}{older_extra}">Older</a>'
    filt = (f'<header class="blog-filter" id="blog-filter">{esc(filter_label)}</header>' if filter_label
            else '<header class="blog-filter" id="blog-filter" hidden></header>')
    return f"""<section class="page page--blog">
  <div class="blog-intro">
    <h2>Sage 100 resources for our customers</h2>
    <p>Over the years, we’ve learned a few things. We’ve shared the most important Sage 100 things we’ve learned here — for you — our customer.</p>
  </div>
  {filt}
  <div class="blog-list" id="blog-list">
    {"".join(card(p) for p in first)}
  </div>
  <nav class="blog-pagination blog-pagination--single" id="blog-pagination" aria-label="More resources">{nav}</nav>
</section>"""


SHARE_ICONS = {
    "Facebook": ("https://www.facebook.com/sharer/sharer.php?u={u}",
                 '<path d="M9 4.5V3c0-.7.2-1.1 1.2-1.1H12V0H9.3C6.6 0 5.7 1.2 5.7 3.4v1.1H4v2.6h1.7V16H9V7.1h2.3l.3-2.6z"/>'),
    "X": ("https://twitter.com/intent/tweet?url={u}&text={t}",
          '<path d="M12.2 1h2.3l-5 5.7L15.4 15h-4.6L7.2 10.3 3.1 15H.8l5.4-6.1L.5 1h4.7l3.3 4.3zm-.8 12.6h1.3L4.6 2.3H3.3z"/>'),
    "LinkedIn": ("https://www.linkedin.com/sharing/share-offsite/?url={u}",
                 '<path d="M3.6 16H.3V5.3h3.3zM1.9 3.9C.9 3.9 0 3 0 2s.9-2 1.9-2 2 .9 2 1.9-.9 2-2 2zM16 16h-3.3v-5.2c0-1.2 0-2.8-1.7-2.8s-2 1.3-2 2.7V16H5.7V5.3h3.2v1.5c.4-.8 1.5-1.7 3.1-1.7 3.3 0 4 2.2 4 5.1z"/>'),
    "Reddit": ("https://www.reddit.com/submit?url={u}&title={t}",
               '<path d="M16 8a1.8 1.8 0 0 0-3-1.3 8.8 8.8 0 0 0-4.7-1.5l.8-3.7 2.6.6a1.3 1.3 0 1 0 .1-.7L8.9.8a.4.4 0 0 0-.4.3l-.9 4.1A8.8 8.8 0 0 0 2.9 6.7 1.8 1.8 0 1 0 .9 9.6a3.5 3.5 0 0 0 0 .5c0 2.7 3.1 4.8 7 4.8s7-2.1 7-4.8a3.5 3.5 0 0 0 0-.5A1.8 1.8 0 0 0 16 8zM4 9.3a1.3 1.3 0 1 1 1.3 1.3A1.3 1.3 0 0 1 4 9.3zm7.1 3.4a4.6 4.6 0 0 1-3.1 1 4.6 4.6 0 0 1-3.1-1 .3.3 0 0 1 .5-.5 3.9 3.9 0 0 0 2.6.8 3.9 3.9 0 0 0 2.6-.8.3.3 0 1 1 .5.5zm-.4-2.1A1.3 1.3 0 1 1 12 9.3a1.3 1.3 0 0 1-1.3 1.3z"/>'),
}


def post_page(p, newer, older):
    u = urllib.parse.quote(SITE + p["url"], safe="")
    t = urllib.parse.quote(p["title"], safe="")
    share = "".join(
        f'<a href="{esc(link.format(u=u, t=t))}" target="_blank" rel="noopener" aria-label="Share on {name}">'
        f'<svg viewBox="0 0 16 16" aria-hidden="true">{icon}</svg></a>'
        for name, (link, icon) in SHARE_ICONS.items())

    def nav_link(q, label, cls):
        if not q:
            return ""
        return (f'<a class="post-nav__link post-nav__link--{cls}" href="{q["url"]}"><span class="post-nav__label">{label}</span>'
                f'<span class="post-nav__title">{esc(q["title"])}</span>'
                f'<span class="meta">{esc(", ".join(q["categories"]))}</span></a>')

    ld = {
        "@context": "http://schema.org", "@type": "BlogPosting",
        "name": f'{p["title"]} — {SITE_NAME}', "headline": p["title"], "url": SITE + p["url"],
        "datePublished": p["iso"], "dateModified": p["modified"], "author": {"@type": "Person", "name": AUTHOR},
        "publisher": {"@type": "Organization", "name": SITE_NAME, "logo": {"@type": "ImageObject", "url": SHARE_IMAGE}},
    }
    head = (f'<meta property="og:description" content="{esc(p["description"])}">\n'
            f'<meta name="author" content="{AUTHOR}">\n'
            f'<meta property="article:published_time" content="{p["iso"]}">\n'
            f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n')
    body = f"""<article class="post">
  <header class="post__header">
    <span class="meta"><time datetime="{p["iso"]}">{esc(p["date"])}</time><span class="sr-only"> by {AUTHOR}</span></span>
    <h1 class="post__title">{esc(p["title"])}</h1>
  </header>
  <div class="post__body">
{p["body"]}
  </div>
  <div class="post__share">{share}</div>
  <nav class="post-nav" aria-label="More resources">
    {nav_link(newer, "Previous", "prev")}
    {nav_link(older, "Next", "next")}
  </nav>
</article>"""
    return page(p["url"], f'{p["title"]} — {SITE_NAME}', body, active="resources", og_type="article",
                description=p["description"], extra_head=head)


def collection_names(kind):
    """Category or tag names and their old addresses, from the sitemap (exact Squarespace spelling)."""
    sm = (CAP / "sitemap.xml").read_text()
    out = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", sm):
        m = re.match(rf"https://www\.ddfcgi\.com(/resources/{kind}/(.+))$", loc.replace("&amp;", "&"))
        if m:
            name = urllib.parse.unquote_plus(m.group(2))
            out.append((name, m.group(1)))
    return out


def file_paths_for(url_path):
    """Where a static host will look for an old address. Hosts decode %2F to a slash, so a name with a slash
    becomes a folder; '+' stays a literal '+'."""
    decoded = urllib.parse.unquote(url_path).lstrip("/")
    return [f"{decoded}.html"]


# ---------------------------------------------------------------- main

def main():
    pages = {}
    search = []

    def add(rel, path_url, title, html_text, words=""):
        write(rel, html_text)
        if path_url:
            pages[path_url] = title
        if words:
            search.append({"url": path_url, "title": title.replace(f" — {SITE_NAME}", ""), "text": words})

    home = (CONTENT / "home.html").read_text()
    add("index.html", "/", "Sage 100 Software Consulting in Florida — DDF Consulting",
        page("/", "Sage 100 Software Consulting in Florida — DDF Consulting", home, active="home", overlay=True),
        text_of(home))
    t = (CONTENT / "testimonials.html").read_text()
    add("testimonials.html", "/testimonials", "Customer Testimonials for Sage 100 Consulting — DDF Consulting",
        page("/testimonials", "Customer Testimonials for Sage 100 Consulting — DDF Consulting", t, active="testimonials"),
        text_of(t))
    c = (CONTENT / "contact.html").read_text()
    add("contact.html", "/contact", "Get in Touch with DDF Consulting for Sage 100 — DDF Consulting",
        page("/contact", "Get in Touch with DDF Consulting for Sage 100 — DDF Consulting", c, active="contact", overlay=True),
        text_of(c))
    fa = (CONTENT / "free-analysis.html").read_text().replace("[[form-endpoint]]", FORM_ENDPOINT)
    add("free-analysis.html", "/free-analysis", "Free Analysis and Consultation for Sage 100 — DDF Consulting",
        page("/free-analysis", "Free Analysis and Consultation for Sage 100 — DDF Consulting", fa),
        text_of(re.sub(r"<form.*?</form>", "", fa, flags=re.S)))
    nf = (CONTENT / "404.html").read_text()
    write("404.html", page("/404", "DDF Consulting", nf, canonical=False, noindex=True))
    sent = ('<section class="page page--narrow"><div class="page__inner form-message">'
            "<p>Thank you! Someone from DDF Consulting will reach out soon.</p>"
            '<p><a href="/">Return to the home page</a></p></div></section>')
    write("message-sent.html", page("/message-sent", "Thank You — DDF Consulting", sent, canonical=False, noindex=True))
    srch = """<section class="page">
  <form class="search-form" action="/search" method="get" role="search">
    <label class="sr-only" for="search-q">Search</label>
    <input type="search" id="search-q" name="q" placeholder="Search">
    <button class="button" type="submit">Search</button>
  </form>
  <p class="text-center" id="search-count" aria-live="polite"></p>
  <ul class="search-results" id="search-results"></ul>
</section>"""
    write("search.html", page("/search", "Search — DDF Consulting", srch, canonical=False, noindex=True))
    # /home was the old home page address; send it to /
    write("home.html", '<!DOCTYPE html><html lang="en-US"><head><meta charset="utf-8"><title>DDF Consulting</title>'
          f'<link rel="canonical" href="{SITE}/"><meta http-equiv="refresh" content="0; url=/"></head>'
          '<body><a href="/">DDF Consulting</a></body></html>\n')

    # Resources
    posts = load_posts()
    resources_html = page("/resources", "Software Articles and Resources for Sage 100 — DDF Consulting",
                          blog_list_page(posts), active="resources",
                          description="We make accounting software run efficiently.")
    add("resources.html", "/resources", "Software Articles and Resources for Sage 100 — DDF Consulting", resources_html)
    # resources/ is also a folder (the posts), so some hosts look for resources/index.html instead
    write("resources/index.html", resources_html)
    for i, p in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        add(p["url"].lstrip("/") + ".html", p["url"], f'{p["title"]} — {SITE_NAME}', post_page(p, newer, older),
            text_of(p["body"]))

    for kind, label, param in (("category", "Posts in", "category"), ("tag", "Posts tagged", "tag")):
        for name, url_path in collection_names(kind):
            subset = [p for p in posts if name in p[{"category": "categories", "tag": "tags"}[kind]]]
            title = f"{name} — Software Articles and Resources for Sage 100 — DDF Consulting"
            body = blog_list_page(subset, f"{label} {name}", f"&{param}={plus(name)}")
            html_text = page(url_path, title, body, active="resources")
            for rel in file_paths_for(url_path):
                write(rel, html_text)
            pages[url_path] = title

    # Data for the list pages after "Older" and for search
    data = [{k: p[k] for k in ("title", "url", "ts", "date", "iso", "categories", "tags", "thumb", "excerpt")} for p in posts]
    write("assets/data/posts.json", json.dumps(data, ensure_ascii=False))
    write("assets/data/search.json", json.dumps(search, ensure_ascii=False))

    # Sitemap: the same addresses Squarespace listed
    urls = ["/", "/resources", "/testimonials", "/contact", "/free-analysis"] + [p["url"] for p in posts]
    urls += [u for u in pages if u.startswith(("/resources/category/", "/resources/tag/"))]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"  <url><loc>{esc(SITE + u)}</loc></url>")
    sm.append("</urlset>")
    write("sitemap.xml", "\n".join(sm) + "\n")
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    print(f"built {len(pages)} addresses, {len(posts)} posts")


if __name__ == "__main__":
    main()
