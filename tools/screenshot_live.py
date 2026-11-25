#!/usr/bin/env python3
"""Full-page screenshots of the live Squarespace site, for side-by-side checks of the copy.

Runs in GitHub Actions (see .github/workflows/screenshot-live.yml) because this workspace can't reach
outside sites. Writes capture/screens/<page>-<width>.png and capture/screens/styles.json (computed
fonts, sizes and colors of the main elements on each page). Read-only.
"""
import json
import pathlib
import re

from playwright.sync_api import sync_playwright

SITE = "https://www.ddfcgi.com"
PAGES = [
    "/", "/testimonials", "/free-analysis", "/contact", "/resources",
    "/resources?offset=1396313580389",
    "/resources/keyboard-shortcuts-in-sage-100-erp",
    "/resources/ap-paperless-remittance",
    "/resources/sage-100-webinar-year-end-2015",
    "/resources/category/Demos",
    "/resources/tag/AP",
    "/this-page-does-not-exist-404-check",
]
WIDTHS = [1440, 390]
OUT = pathlib.Path("capture/screens")

STYLE_JS = """
() => {
  const out = [];
  const seen = new Set();
  const sels = ['header', 'header a', 'header img', 'h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'a',
    '.sqs-block-button-element', 'input', 'label', 'button', 'footer', 'footer p', 'footer h3', 'footer a',
    '.blog-item-title, .entry-title', '.blog-meta-item, .entry-meta, time', '.blog-excerpt, .entry-excerpt'];
  for (const sel of sels) {
    for (const e of [...document.querySelectorAll(sel)].slice(0, 3)) {
      const s = getComputedStyle(e);
      const r = e.getBoundingClientRect();
      const key = sel + '|' + s.fontFamily + s.fontSize + s.fontWeight + s.color;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({sel, text: (e.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 40),
        font: s.fontFamily, size: s.fontSize, weight: s.fontWeight, style: s.fontStyle, lh: s.lineHeight,
        ls: s.letterSpacing, tt: s.textTransform, color: s.color, bg: s.backgroundColor,
        pad: s.padding, margin: s.margin, border: s.border, radius: s.borderRadius,
        x: Math.round(r.x), y: Math.round(r.y + window.scrollY), w: Math.round(r.width), h: Math.round(r.height)});
    }
  }
  return out;
}
"""


def name_for(path):
    s = path.strip("/") or "home"
    return re.sub(r"[^A-Za-z0-9]+", "_", s)[:80]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    styles = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for path in PAGES:
            for w in WIDTHS:
                page = browser.new_page(viewport={"width": w, "height": 900})
                page.goto(SITE + path, wait_until="networkidle", timeout=90000)
                page.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 500) "
                              "{ window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } "
                              "window.scrollTo(0, 0); }")
                page.wait_for_timeout(1500)
                page.screenshot(path=str(OUT / f"{name_for(path)}-{w}.png"), full_page=True)
                if w == 1440:
                    styles[path] = page.evaluate(STYLE_JS)
                print("shot", path, w)
                page.close()
        browser.close()
    (OUT / "styles.json").write_text(json.dumps(styles, indent=1))


if __name__ == "__main__":
    main()
