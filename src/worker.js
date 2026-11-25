// ddfcgi.com Worker (Cloudflare, WWM account, Worker "ddfcgi").
//
// Two jobs:
//   1. The "Request a free consultation" form posts here from every copy of the site:
//        POST /api/consultation   fname, lname, email, phone, company (all required)
//      Each entry goes to a Zapier catch hook (secret CONSULTATION_WEBHOOK_URL, set in the Cloudflare
//      dashboard, never in this public repo). Zapier sends the "New Website Request" email.
//      A filled-in hidden "website" field marks a bot: it gets a normal success answer but nothing is sent.
//   2. It serves public/ as the test link (ddfcgi.wwm-031.workers.dev) and branch preview links.
//      The real site (www.ddfcgi.com) is the same public/ folder on GitHub Pages; its form posts here.
//
// Only /api/* runs code (run_worker_first in wrangler.jsonc); everything else is a static file, and unknown
// addresses get public/404.html with a 404 status.

const ENDPOINT = "/api/consultation";
const WEBHOOK_SECRET = "CONSULTATION_WEBHOOK_URL";
const LIVE_SITE = "https://www.ddfcgi.com";
const REQUIRED = ["fname", "lname", "email", "phone", "company"];
const LIMITS = { fname: 100, lname: 100, email: 254, phone: 50, company: 200 };
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Pages that may post to the form: the live site, the GitHub Pages address, and this Worker's own
// test and preview links.
function allowedOrigin(origin) {
  if (!origin) return null;
  try {
    const host = new URL(origin).host;
    if (host === "www.ddfcgi.com" || host === "ddfcgi.com" || host === "ddfcgi.github.io") return origin;
    if (host === "ddfcgi.wwm-031.workers.dev" || host.endsWith("-ddfcgi.wwm-031.workers.dev")) return origin;
  } catch {
    return null;
  }
  return null;
}

function corsHeaders(request) {
  const origin = allowedOrigin(request.headers.get("Origin"));
  return origin ? { "Access-Control-Allow-Origin": origin, Vary: "Origin" } : {};
}

function wantsJson(request) {
  return (request.headers.get("Accept") || "").includes("application/json");
}

function reply(request, ok, status = 200) {
  if (wantsJson(request)) {
    return new Response(JSON.stringify({ ok }), {
      status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...corsHeaders(request) },
    });
  }
  // No JavaScript: send the visitor back to the site they came from.
  const from = allowedOrigin(request.headers.get("Origin")) ||
    allowedOrigin(safeOrigin(request.headers.get("Referer"))) || LIVE_SITE;
  const to = ok ? `${from}/message-sent` : `${from}/free-analysis`;
  return new Response(null, { status: 303, headers: { Location: to, "Cache-Control": "no-store" } });
}

function safeOrigin(url) {
  try {
    return url ? new URL(url).origin : null;
  } catch {
    return null;
  }
}

function easternTime(date) {
  // e.g. "11/24/2026 19:05:09"
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
    }).formatToParts(date).map((p) => [p.type, p.value]),
  );
  return `${parts.month}/${parts.day}/${parts.year} ${Number(parts.hour)}:${parts.minute}:${parts.second}`;
}

async function handleForm(request, env) {
  let data;
  try {
    data = await request.formData();
  } catch {
    return reply(request, false, 400);
  }
  const get = (k) => String(data.get(k) || "").trim().slice(0, LIMITS[k] || 500);

  if (get("website")) return reply(request, true); // honeypot: quietly drop bots

  const fields = {};
  for (const k of REQUIRED) fields[k] = get(k);
  for (const k of REQUIRED) {
    if (!fields[k]) return reply(request, false, 422);
  }
  if (!EMAIL_RE.test(fields.email)) return reply(request, false, 422);

  const url = env[WEBHOOK_SECRET];
  if (!url) {
    console.error(`missing secret ${WEBHOOK_SECRET}`);
    return reply(request, false, 503);
  }

  const now = new Date();
  const payload = {
    form: "free_consultation",
    page: "Request a free consultation",
    name: `${fields.fname} ${fields.lname}`.trim(),
    first_name: fields.fname,
    last_name: fields.lname,
    email: fields.email,
    phone: fields.phone,
    company: fields.company,
    submitted_at: now.toISOString(),
    submitted_on: easternTime(now),
    site: safeOrigin(request.headers.get("Origin")) || safeOrigin(request.headers.get("Referer")) || "",
  };

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`webhook answered ${res.status}`);
  } catch (err) {
    console.error(`consultation webhook failed: ${err.message}`);
    return reply(request, false, 502);
  }
  return reply(request, true);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/$/, "");
    if (path === ENDPOINT) {
      if (request.method === "OPTIONS") {
        return new Response(null, {
          status: 204,
          headers: {
            ...corsHeaders(request),
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Accept, Content-Type",
            "Access-Control-Max-Age": "86400",
          },
        });
      }
      if (request.method !== "POST") {
        return new Response("Method Not Allowed", { status: 405, headers: { Allow: "POST" } });
      }
      return handleForm(request, env);
    }
    if (path.startsWith("/api")) {
      const page = await env.ASSETS.fetch(new Request(new URL("/404", url), request));
      return new Response(page.body, { status: 404, headers: page.headers });
    }
    return env.ASSETS.fetch(request);
  },
};
