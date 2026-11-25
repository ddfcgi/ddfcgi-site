#!/usr/bin/env python3
"""Copy the images and fonts the site uses into public/.

Images come from the one-time Squarespace capture (capture/squarespace/), including the old Resources
post images recovered from the Wayback Machine (capture/squarespace/wayback.json). They are small and
already web-sized, so they are copied as they are. Writes tools/images.json: original URL -> site path,
which tools/build_site.py uses to point every <img> at the local copy.

Fonts: Poppins and Rubik (SIL Open Font License), the two fonts the Squarespace site used, from the
@fontsource packages on npm. Run `npm install` first so node_modules/@fontsource is there.

Run from the repo root:  python3 tools/build_images.py
"""
import json
import pathlib
import re
import shutil
import urllib.parse

CAP = pathlib.Path("capture/squarespace")
PUB = pathlib.Path("public")
IMG = PUB / "assets/img"
POST_IMG = PUB / "assets/posts"
FONTS = PUB / "assets/fonts"
OUT = pathlib.Path("tools/images.json")

# Squarespace asset id -> file name on the new site (site-wide and page images)
SITE_IMAGES = {
    "1658432448195-K49QQ57LQRIJZVXDMLAR": "ddf-consulting-logo.png",
    "1658432425667-Z345771AFBE6DNY9FGSE": "ddf-consulting-logo-footer.png",
    "1658432439713-MS3BKPX4DR41GZNTF0UX": "home-banner-background.png",
    "1658432439731-1BOE0M0BEW3IQE0GDRN6": "home-banner-image.png",
    "1658432429524-7XX59G98M9056D8U60F2": "home-software-makes-a-difference.png",
    "1658432436805-XSFDPLL5S0GY9F8VLK5U": "home-testimonial-background.png",
    "1658432432736-IMSB82VR86UGCO28LOUV": "home-stop-wondering-start-moving.png",
    "1658432425632-6FEZJTMN7ON2HN1ZJ0HR": "home-footer-background.png",
    "1658432446109-IQWO4GRNV56UE1AKL3EA": "contact-ddf-consulting-sage-100.jpg",
    "1658432434129-BJFDAN54DPUSLPGZYSCN": "silver-springs.png",
    "1658432434140-7IFHYIFNV5O053RMIW5Y": "sheriff.png",
    "1658432434148-B9Q2ZERVC6CL1P4ZA6Y1": "florida-food-service.png",
    "1658432434157-2TJ1812X2UAF807Q2R8T": "culinary-source.jpg",
    "1658432443188-SHPP8T0WPWQXLOXORVO1": "sage-100-webinar-year-end-2015.png",
    "1658432443409-HVYAR555Y1IJRT2DA53G": "2014-year-end-sage-100-erp-video.png",
    "1658432443335-6UKKJ06T1PTR537SVCT5": "dsd-enhancements.png",
}
FONT_FILES = [
    ("poppins", "poppins-latin-300-normal.woff2"), ("poppins", "poppins-latin-300-italic.woff2"),
    ("poppins", "poppins-latin-400-normal.woff2"), ("poppins", "poppins-latin-400-italic.woff2"),
    ("poppins", "poppins-latin-700-normal.woff2"), ("poppins", "poppins-latin-700-italic.woff2"),
    ("rubik", "rubik-latin-300-normal.woff2"), ("rubik", "rubik-latin-400-normal.woff2"),
]


def bare(url):
    url = url.split("?")[0]
    if url.startswith("//"):
        url = "https:" + url
    return url


def main():
    for d in (IMG, POST_IMG, FONTS):
        d.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((CAP / "manifest.json").read_text())["images"]
    wayback = json.loads((CAP / "wayback.json").read_text())
    mapping = {}

    # Site and page images, by Squarespace asset id (every size/variant of the same asset maps to one file)
    for url, info in manifest.items():
        if "file" not in info:
            continue
        for asset_id, name in SITE_IMAGES.items():
            if asset_id in url:
                if not (IMG / name).exists():
                    shutil.copyfile(CAP / info["file"], IMG / name)
                mapping[bare(url)] = f"/assets/img/{name}"

    # Favicon
    for url, info in manifest.items():
        if "favicon" in url and "file" in info:
            shutil.copyfile(CAP / info["file"], PUB / "favicon.ico")

    # Other images used inside posts (Squarespace-hosted)
    for url, info in manifest.items():
        u = bare(url)
        if "file" not in info or u in mapping:
            continue
        if "/resources/" not in (info.get("page") or ""):
            continue
        name = urllib.parse.unquote_plus(u.rstrip("/").rsplit("/", 1)[-1])
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-").lower() or "image.png"
        stem, dot, ext = name.rpartition(".")
        if not dot:
            stem, ext = name, "png"
        target = POST_IMG / f"{stem}.{ext}"
        n = 2
        while target.exists() and target.read_bytes() != (CAP / info["file"]).read_bytes():
            target = POST_IMG / f"{stem}-{n}.{ext}"
            n += 1
        shutil.copyfile(CAP / info["file"], target)
        mapping[u] = f"/assets/posts/{target.name}"

    # Old WordPress images recovered from the Wayback Machine
    for url, info in wayback.items():
        src = CAP / info["file"]
        name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
        shutil.copyfile(src, POST_IMG / name)
        mapping[url] = f"/assets/posts/{name}"

    for pkg, f in FONT_FILES:
        src = pathlib.Path(f"node_modules/@fontsource/{pkg}/files/{f}")
        shutil.copyfile(src, FONTS / f)
    lic = pathlib.Path("node_modules/@fontsource/poppins/LICENSE")
    if lic.exists():
        shutil.copyfile(lic, FONTS / "OFL-poppins.txt")
    lic = pathlib.Path("node_modules/@fontsource/rubik/LICENSE")
    if lic.exists():
        shutil.copyfile(lic, FONTS / "OFL-rubik.txt")

    OUT.write_text(json.dumps(dict(sorted(mapping.items())), indent=1))
    print("images mapped:", len(mapping), "post images:", len(list(POST_IMG.iterdir())))


if __name__ == "__main__":
    main()
