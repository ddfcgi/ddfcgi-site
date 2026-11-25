# ddfcgi-site

The website for DDF Consulting Group, **www.ddfcgi.com**. It moved off Squarespace in November 2026 with the
same look, words and page addresses, and is maintained by Working Web Media.

## How it works

- **The site** is plain HTML and CSS in `public/`. Every time `public/` changes on `main`,
  `.github/workflows/pages.yml` copies it to the `gh-pages` branch, which GitHub Pages serves. Don't edit
  `gh-pages` by hand; each run replaces it.
- **The free consultation form** (`/free-analysis`) posts to a small Cloudflare Worker (`src/worker.js`,
  Worker "ddfcgi" in WWM's Cloudflare account), which passes each request to a Zapier workflow that emails it on.
  The Zapier address is a Worker secret (`CONSULTATION_WEBHOOK_URL`), never stored in this repo.
- **Test link:** the same Worker serves `public/` at https://ddfcgi.wwm-031.workers.dev, and every branch gets its
  own preview link. These are marked noindex. Keep the workers.dev address on: the form needs it.
- **Domain:** registered at GoDaddy, DNS on GoDaddy. Only the website records point here; email (Google Workspace)
  and everything else is untouched. See `docs/2026-11-24-dns-cutover.md` for the records and the rollback.
- **Analytics:** GA4 `G-VPYXSN3NXZ`, loaded only on ddfcgi.com (not on the test or preview links).

## Making changes

| What | Where |
|---|---|
| Home, Testimonials, Contact, Free Consultation and 404 pages | `content/*.html` |
| Header, menu, page wrapper, Resources pages | `tools/build_site.py` |
| Styles | `public/assets/css/styles.css` |
| Phone menu, form, Resources paging, search | `public/assets/js/site.js` |
| Form handling | `src/worker.js` |

After editing `content/` or `tools/build_site.py`, rebuild and commit `public/`:

```sh
pip install beautifulsoup4
python3 tools/build_site.py          # rewrites the pages in public/
python3 tools/render.py index.html   # optional: screenshots in _shots/ (needs Playwright)
```

`tools/build_images.py` copies images and fonts into `public/` (run `npm install` first for the fonts);
it only needs running again if the images change.

## Where the content came from

`capture/` is a one-time copy of the Squarespace site (Nov 24, 2026), made by
`.github/workflows/capture-squarespace.yml`. The 34 Resources posts are built from it. Old post images that had
gone missing were recovered from the Wayback Machine (`tools/wayback_images.py`); two could not be found and are
left as they were. `capture/screens/` holds full-page screenshots of the Squarespace pages for comparison.

Fonts: Poppins and Rubik, self-hosted under the SIL Open Font License (`public/assets/fonts/`).
