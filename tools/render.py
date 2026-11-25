"""Render pages with headless Chrome for visual checks.

    python3 tools/render.py [page.html,...] [widths]     e.g. python3 tools/render.py index.html,contact.html 1440,390
Screenshots go to _shots/ (not committed). Serves public/ locally and maps clean URLs (/contact -> contact.html).
"""
import http.server
import os
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

PAGES = sys.argv[1].split(",") if len(sys.argv) > 1 else ["index.html"]
WIDTHS = [int(w) for w in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["1440", "390"])]
OUT = "_shots"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory="public", **k)

    def translate_path(self, path):
        p = super().translate_path(path)
        if os.path.exists(p.rstrip("/") + ".html") and (not os.path.exists(p) or os.path.isdir(p)):
            return p.rstrip("/") + ".html"
        return p

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 8765), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for page_name in PAGES:
        for w in WIDTHS:
            page = browser.new_page(viewport={"width": w, "height": 900}, device_scale_factor=1)
            # Outside tags (Google Analytics) can't load from here; skip them so the render isn't held up.
            page.route("**/*", lambda r: r.abort() if not r.request.url.startswith("http://127.0.0.1") else r.continue_())
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
            page.goto(f"http://127.0.0.1:8765/{page_name}", wait_until="load")
            page.evaluate("document.fonts.ready")
            page.evaluate("() => { document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager'); }")
            page.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }")
            page.wait_for_timeout(1200)
            sw = page.evaluate("document.documentElement.scrollWidth")
            h = page.evaluate("document.documentElement.scrollHeight")
            name = page_name.replace(".html", "").replace("/", "_").replace("?", "_").replace("=", "-").replace("&", "_") or "index"
            page.screenshot(path=f"{OUT}/{name}-{w}.png", full_page=True)
            broken = page.evaluate("[...document.images].filter(i => i.getAttribute('src') && i.complete && i.naturalWidth === 0).map(i => i.src)")
            print(f"{name} {w}px: height={h} overflow={sw > w} broken_images={len(broken)} errors={errors[:3]}")
            page.close()
    browser.close()
srv.shutdown()
