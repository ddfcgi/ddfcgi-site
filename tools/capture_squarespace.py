#!/usr/bin/env python3
"""One-time copy of the live ddfcgi.com Squarespace site into capture/squarespace/.

Runs in GitHub Actions (see .github/workflows/capture-squarespace.yml) because the build
workspace can't reach outside websites. Read-only: it only downloads public pages.

Saves, for every address in the sitemap (plus the Resources list pages behind "Older" and a 404):
  pages/<slug>.html   the page as served
  pages/<slug>.json   Squarespace's ?format=json for the same address (words, blog post fields)
Also the site's stylesheets, sitemap, robots.txt, favicon, every image the pages use, and the files under /s/.

Images that no longer load are listed in broken.json; tools/wayback_images.py then looks for them in
the Wayback Machine (web.archive.org).
"""
import hashlib
import json
import mimetypes
import pathlib
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://www.ddfcgi.com"
EXTRA = ["/", "/free-analysis", "/testimonials", "/resources", "/this-page-does-not-exist-404-check"]
OUT = pathlib.Path("capture/squarespace")
PAGES = OUT / "pages"
IMG = OUT / "images"
FILES = OUT / "files"
CSS = OUT / "css"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

IMG_EXT = r"\.(?:jpe?g|png|gif|webp|svg|ico|bmp)"
CDN_RE = re.compile(r"https?://images\.squarespace-cdn\.com/content/[^\"'\s<>)\\?]+")
STATIC_RE = re.compile(r"https?://static1\.squarespace\.com/static/[^\"'\s<>)\\?]+" + IMG_EXT, re.I)
ATTR_RE = re.compile(r"""(?:src|data-src|data-image|href|srcset)\s*=\s*["']([^"']+)["']""", re.I)
FILE_RE = re.compile(r"(?:https?://(?:www\.)?ddfcgi\.com)?(/s/[^\"'\s<>)\\?]+)")
CSS_RE = re.compile(r"""<link[^>]+rel=["']stylesheet["'][^>]*href=["']([^"']+)["']""", re.I)
SKIP_HOSTS = ("assets.squarespace.com", "use.typekit.net", "p.typekit.net", "www.google-analytics.com",
              "www.googletagmanager.com", "definitions.sqspcdn.com")


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(), r.headers.get("Content-Type", ""), r.status
        except urllib.error.HTTPError as e:
            if e.code in (404, 410, 403):
                return e.read(), e.headers.get("Content-Type", ""), e.code
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        print(f"retry {url}: {last}")
        time.sleep(2 * (i + 1))
    raise last


def slug_for(p):
    path, _, query = p.partition("?")
    path = urllib.parse.unquote_plus(path).strip("/") or "home"
    s = path + ("__" + urllib.parse.unquote_plus(query) if query else "")
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s[:180]


def img_name(url):
    u = urllib.parse.urlparse(url)
    parts = [p for p in u.path.split("/") if p]
    tail = parts[-2:] if len(parts) >= 2 else parts
    base = "__".join(urllib.parse.unquote_plus(p) for p in tail)
    if "squarespace" not in u.netloc:
        base = u.netloc + "__" + base
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-")
    h = hashlib.sha1(url.encode()).hexdigest()[:6]
    return f"{base[:150]}-{h}"


def main():
    if OUT.exists():
        shutil.rmtree(OUT)  # start clean so no stale copy survives a re-run
    for d in (OUT, PAGES, IMG, FILES, CSS):
        d.mkdir(parents=True, exist_ok=True)

    sitemap, _, _ = get(f"{SITE}/sitemap.xml")
    (OUT / "sitemap.xml").write_bytes(sitemap)
    robots, _, _ = get(f"{SITE}/robots.txt")
    (OUT / "robots.txt").write_bytes(robots)
    try:
        fav, ctype, status = get(f"{SITE}/favicon.ico")
        if status == 200:
            (OUT / "favicon.ico").write_bytes(fav)
    except Exception as e:  # noqa: BLE001
        print("favicon", e)

    paths = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", sitemap.decode("utf-8", "replace")):
        p = loc.replace("&amp;", "&")
        p = re.sub(r"^https?://(?:www\.)?ddfcgi\.com", "", p) or "/"
        paths.append(p)
    for p in EXTRA:
        if p not in paths:
            paths.append(p)

    index = {}
    texts = []  # (page url, html text) for finding images
    queue = list(paths)
    seen = set()
    while queue:
        p = queue.pop(0)
        if p in seen:
            continue
        seen.add(p)
        url = SITE + urllib.parse.quote(p, safe="/?=&%+:")
        slug = slug_for(p)
        html, ctype, status = get(url)
        (PAGES / f"{slug}.html").write_bytes(html)
        text = html.decode("utf-8", "replace")
        texts.append((url, text))
        entry = {"path": p, "status": status, "html": f"pages/{slug}.html"}
        if status == 200:
            sep = "&" if "?" in url else "?"
            try:
                js, _, jstatus = get(url + sep + "format=json")
                if jstatus == 200:
                    data = json.loads(js)
                    (PAGES / f"{slug}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
                    entry["json"] = f"pages/{slug}.json"
                    blob = json.dumps(data, ensure_ascii=False)
                    texts.append((url, blob.replace("\\/", "/")))
                    # Blog list pages: follow "Older" (pagination) so every list page is captured.
                    pag = data.get("pagination") or {}
                    nxt = pag.get("nextPageUrl")
                    if nxt:
                        nxt = re.sub(r"^https?://(?:www\.)?ddfcgi\.com", "", nxt)
                        if nxt not in seen:
                            queue.append(nxt)
                    # Blog posts and list items: make sure every item URL is captured too.
                    for item in data.get("items") or []:
                        fu = item.get("fullUrl")
                        if fu and fu not in seen and fu not in queue:
                            queue.append(fu)
                    item = data.get("item")
                    if item and item.get("body"):
                        texts.append((url, item["body"]))
            except Exception as e:  # noqa: BLE001
                print("json failed", p, e)
        index[p] = entry
        print("page", status, p, len(html))

    (OUT / "pages.json").write_text(json.dumps(index, indent=1))

    # Stylesheets
    css_urls = set()
    for _, t in texts:
        for href in CSS_RE.findall(t):
            css_urls.add(urllib.parse.urljoin(SITE + "/", href.replace("&amp;", "&")))
    css_manifest = {}
    for cu in sorted(css_urls):
        if any(h in cu for h in ("typekit",)):
            continue
        try:
            body, _, status = get(cu)
        except Exception as e:  # noqa: BLE001
            print("css failed", cu, e)
            continue
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", urllib.parse.urlparse(cu).path.strip("/"))[-120:] or "site.css"
        if not name.endswith(".css"):
            name += ".css"
        (CSS / name).write_bytes(body)
        css_manifest[cu] = {"file": f"css/{name}", "status": status, "bytes": len(body)}
        print("css", status, name, len(body))

    # Images: anything the pages or post bodies point at that looks like an image
    found = {}
    for page_url, t in texts:
        t = t.replace("&amp;", "&")
        for m in CDN_RE.findall(t) + STATIC_RE.findall(t):
            found.setdefault(m, page_url)
        for raw in ATTR_RE.findall(t):
            for piece in raw.split(","):
                cand = piece.strip().split(" ")[0]
                if not cand or cand.startswith(("data:", "#", "mailto:", "tel:", "javascript:")):
                    continue
                absu = urllib.parse.urljoin(page_url, cand)
                bare = absu.split("?")[0]
                host = urllib.parse.urlparse(absu).netloc
                if host in SKIP_HOSTS:
                    continue
                if re.search(IMG_EXT + r"$", bare, re.I) or "images.squarespace-cdn.com" in host:
                    found.setdefault(bare, page_url)

    manifest = {"images": {}, "files": {}, "css": css_manifest}
    broken = {}
    for url, page_url in sorted(found.items()):
        name = img_name(url)
        fetch = url + ("?format=2500w" if "images.squarespace-cdn.com" in url else "")
        body, ctype, status, source = None, "", 0, "live"
        try:
            body, ctype, status = get(fetch)
        except Exception as e:  # noqa: BLE001
            print("img error", url, e)
        if status != 200 or not ctype.startswith("image/"):
            # Missing today. tools/wayback_images.py looks for these in the Wayback Machine next.
            broken[url] = {"page": page_url, "status": status}
            manifest["images"][url] = {"error": f"status {status}", "page": page_url}
            print("BROKEN", url, "on", page_url)
            continue
        ext = mimetypes.guess_extension(ctype.split(";")[0].strip()) or ""
        if ext == ".jpe":
            ext = ".jpg"
        if not re.search(IMG_EXT + "$", name, re.I):
            name += ext
        (IMG / name).write_bytes(body)
        manifest["images"][url] = {"file": f"images/{name}", "type": ctype, "bytes": len(body),
                                   "page": page_url, "source": source}
        print("img", source if source == "live" else "wayback", name, len(body))

    # Files under /s/ (PDFs and other downloads)
    files = set()
    for _, t in texts:
        files.update(FILE_RE.findall(t))
    for path in sorted(files):
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", urllib.parse.unquote(path.split("/s/", 1)[1]))
        try:
            body, ctype, status = get(SITE + path)
        except Exception as e:  # noqa: BLE001
            manifest["files"][path] = {"error": str(e)}
            continue
        if status != 200:
            manifest["files"][path] = {"error": f"status {status}"}
            continue
        (FILES / name).write_bytes(body)
        manifest["files"][path] = {"file": f"files/{name}", "type": ctype, "bytes": len(body)}
        print("file", name, len(body))

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (OUT / "broken.json").write_text(json.dumps(broken, indent=1))
    print("pages:", len(index), "images:", len(manifest["images"]), "broken:", len(broken),
          "files:", len(manifest["files"]))


if __name__ == "__main__":
    main()
