"""Find text that only fits on phones by breaking a word in the middle.

    python3 tools/check_word_breaks.py [widths]     e.g. python3 tools/check_word_breaks.py 320,360,390,414
Serves public/ locally, opens the main page types at each width, and lists every element whose longest word is
wider than the element (so the browser has to split it). Prints nothing but the summary when all is well.
"""
import http.server
import os
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

WIDTHS = [int(w) for w in (sys.argv[1].split(",") if len(sys.argv) > 1 else ["320", "360", "375", "390", "414"])]
PAGES = [
    "/", "/resources", "/resources/keyboard-shortcuts-in-sage-100-erp", "/resources/category/Demos",
    "/testimonials", "/contact", "/free-analysis", "/message-sent", "/search", "/404.html",
]

CHECK = """() => {
  const out = [];
  const ctx = document.createElement('canvas').getContext('2d');
  const els = document.querySelectorAll('h1,h2,h3,h4,p,a,li,label,legend,button,.post__title,.blog-card__title');
  for (const el of els) {
    if (!el.offsetParent || !el.textContent.trim()) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'inline' || cs.position === 'absolute') continue;
    const room = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    if (room < 20) continue;
    ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    ctx.letterSpacing = cs.letterSpacing === 'normal' ? '0px' : cs.letterSpacing;
    let text = el.innerText;
    if (cs.textTransform === 'uppercase') text = text.toUpperCase();
    let widest = '', widestW = 0;
    for (const word of text.split(/\\s+/)) {
      const w = ctx.measureText(word).width;
      if (w > widestW) { widestW = w; widest = word; }
    }
    if (widestW > room + 1) {
      out.push({tag: el.tagName.toLowerCase(), cls: String(el.className), size: cs.fontSize,
                over: Math.round(widestW - room), text: widest});
    }
  }
  return out;
}"""


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
srv = socketserver.TCPServer(("127.0.0.1", 8766), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()

problems = 0
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for w in WIDTHS:
        page = browser.new_page(viewport={"width": w, "height": 800}, device_scale_factor=1)
        for path in PAGES:
            page.goto(f"http://127.0.0.1:8766{path}", wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            for hit in page.evaluate(CHECK):
                problems += 1
                print(f"{w}px {path}: <{hit['tag']} class='{hit['cls']}'> {hit['size']} over by {hit['over']}px: {hit['text']}")
        page.close()
    browser.close()
srv.shutdown()
print(f"{problems} word break problem(s) across {len(PAGES)} pages at {WIDTHS}")
