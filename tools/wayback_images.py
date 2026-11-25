#!/usr/bin/env python3
"""Look for the Resources posts' missing images in the Wayback Machine.

Runs in GitHub Actions after tools/capture_squarespace.py (this workspace can't reach outside sites).
The old posts point at images on the blog's former WordPress host, which is gone. For each host the
images may once have lived on, this asks the Wayback Machine's index (CDX) for every archived file under
/wp-content/uploads/, matches the missing images by file name, and downloads the archived copy.

Reads capture/squarespace/broken.json. Writes:
  capture/squarespace/images/<name>    each image found
  capture/squarespace/wayback.json     missing URL -> {file, snapshot, match}
  capture/squarespace/still-broken.json  the ones the archive doesn't have (they stay broken on the site)
"""
import json
import mimetypes
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from capture_squarespace import IMG_EXT, img_name  # noqa: E402

OUT = pathlib.Path("capture/squarespace")
IMG = OUT / "images"
UA = "Mozilla/5.0 (compatible; ddfcgi-site capture; +https://www.ddfcgi.com)"
HOSTS = ["sp2018tnj6dwj.wpengine.com", "ddfcgi.com", "www.ddfcgi.com", "ddfcgi.wpengine.com"]


def get(url, tries=3, timeout=45):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", ""), r.status
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                return b"", "", e.code
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        print(f"retry {url}: {last}")
        time.sleep(3 * (i + 1))
    print("gave up", url, last)
    return b"", "", 0


def base(name):
    return urllib.parse.unquote(name.rsplit("/", 1)[-1]).lower()


def main():
    broken = json.loads((OUT / "broken.json").read_text())
    wanted = {u: v for u, v in broken.items() if "/wp-content/uploads/" in u}
    print("missing images to look for:", len(wanted))

    # Every archived file under /wp-content/uploads/ on each candidate host, by file name.
    index = {}
    for host in HOSTS:
        q = urllib.parse.urlencode({
            "url": f"{host}/wp-content/uploads/",
            "matchType": "prefix",
            "output": "json",
            "fl": "original,timestamp,statuscode,mimetype",
            "filter": "statuscode:200",
            "collapse": "urlkey",
            "limit": "20000",
        })
        body, _, status = get(f"https://web.archive.org/cdx/search/cdx?{q}", timeout=120)
        rows = json.loads(body)[1:] if status == 200 and body.strip() else []
        print(host, "archived uploads:", len(rows))
        for original, ts, _, mime in rows:
            if not mime.startswith("image/"):
                continue
            index.setdefault(base(original), []).append((original, ts))
        time.sleep(2)

    found, still = {}, {}
    for url, info in sorted(wanted.items()):
        name = base(url)
        match, hits = "exact", index.get(name)
        if not hits:
            # Windows Live Writer posted "_thumb" copies; the full-size original is the same picture.
            alt = re.sub(r"_thumb(\d*)(\.\w+)$", r"\1\2", name)
            if alt != name:
                hits, match = index.get(alt), "full-size"
        if not hits:
            still[url] = info
            print("not archived:", name)
            continue
        hits.sort(key=lambda h: h[1])  # oldest first: closest to when the post was written
        saved = None
        for original, ts in hits[:3]:
            snap = f"https://web.archive.org/web/{ts}id_/{original}"
            body, ctype, status = get(snap)
            if status == 200 and ctype.startswith("image/") and len(body) > 200:
                fname = img_name(url)
                ext = mimetypes.guess_extension(ctype.split(";")[0].strip()) or ""
                if ext == ".jpe":
                    ext = ".jpg"
                if not re.search(IMG_EXT + "$", fname, re.I):
                    fname += ext
                (IMG / fname).write_bytes(body)
                saved = {"file": f"images/{fname}", "snapshot": snap, "match": match, "bytes": len(body),
                         "type": ctype, "page": info.get("page")}
                break
            time.sleep(1)
        if saved:
            found[url] = saved
            print("found", match, name, saved["bytes"])
        else:
            still[url] = info
            print("archive copy failed:", name)
        time.sleep(1)

    # Anything outside /wp-content/uploads/ stays as captured.
    for url, info in broken.items():
        if url not in wanted:
            still[url] = info

    (OUT / "wayback.json").write_text(json.dumps(found, indent=1))
    (OUT / "still-broken.json").write_text(json.dumps(still, indent=1))
    print("found in the Wayback Machine:", len(found), "still missing:", len(still))


if __name__ == "__main__":
    main()
