// ddfcgi.com: phone menu, the free consultation form, Resources list pages (?offset, ?category, ?tag)
// and site search. Everything works without JavaScript too, except search and the extra list pages.
(function () {
  "use strict";

  // ---------- Phone menu ----------
  var menu = document.getElementById("mobile-menu");
  document.querySelectorAll("[data-menu-open]").forEach(function (b) {
    b.addEventListener("click", function () { menu.classList.add("is-open"); menu.querySelector("a").focus(); });
  });
  document.querySelectorAll("[data-menu-close]").forEach(function (b) {
    b.addEventListener("click", function () { menu.classList.remove("is-open"); });
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && menu) menu.classList.remove("is-open"); });

  // ---------- Free consultation form ----------
  var form = document.getElementById("consultation-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var error = form.querySelector(".form__error");
      var button = form.querySelector(".form__submit");
      if (!form.checkValidity()) { form.reportValidity(); return; }
      button.disabled = true;
      error.hidden = true;
      fetch(form.action, { method: "POST", body: new FormData(form), headers: { Accept: "application/json" } })
        .then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
        .then(function (res) {
          if (!res.ok) throw new Error("not ok");
          var done = document.getElementById("form-message");
          form.hidden = true;
          done.hidden = false;
          done.focus();
        })
        .catch(function () {
          error.textContent = "Sorry, something went wrong. Please try again, or call us at (888) 289-2075.";
          error.hidden = false;
          button.disabled = false;
        });
    });
  }

  // ---------- Resources list pages ----------
  var list = document.getElementById("blog-list");
  var PER_PAGE = 6;
  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function enc(s) { return encodeURIComponent(s).replace(/%20/g, "+"); }
  function card(p) {
    var img = p.thumb ? '<a class="blog-card__image" href="' + p.url + '"><img src="' + p.thumb + '" alt="" loading="lazy"></a>' : "";
    var ex = p.excerpt ? '<div class="blog-card__excerpt">' + p.excerpt + ' <a class="blog-card__readmore" href="' + p.url + '">Read More &nbsp;→</a></div>' : "";
    return '<article class="blog-card">' + img + '<h2 class="blog-card__title"><a href="' + p.url + '">' + esc(p.title) +
      "</a></h2>" + ex + '<div class="meta"><time datetime="' + p.iso + '">' + esc(p.date) + "</time></div></article>";
  }
  if (list && location.search) {
    var q = new URLSearchParams(location.search);
    var category = q.get("category"), tag = q.get("tag");
    var offset = q.get("offset") ? Number(q.get("offset")) : null;
    var reverse = q.get("reversePaginate") === "true";
    if (category || tag || offset) {
      fetch("/assets/data/posts.json").then(function (r) { return r.json(); }).then(function (posts) {
        var pool = posts.filter(function (p) {
          return (!category || p.categories.indexOf(category) > -1) && (!tag || p.tags.indexOf(tag) > -1);
        });
        var page;
        if (offset && reverse) {
          var newer = pool.filter(function (p) { return p.ts > offset; });
          page = newer.slice(Math.max(0, newer.length - PER_PAGE));
        } else if (offset) {
          page = pool.filter(function (p) { return p.ts < offset; }).slice(0, PER_PAGE);
        } else {
          page = pool.slice(0, PER_PAGE);
        }
        var filter = document.getElementById("blog-filter");
        if (category) { filter.textContent = "Posts in " + category; filter.hidden = false; }
        if (tag) { filter.textContent = "Posts tagged " + tag; filter.hidden = false; }
        list.innerHTML = page.map(card).join("");
        var extra = (category ? "&category=" + enc(category) : "") + (tag ? "&tag=" + enc(tag) : "");
        var nav = document.getElementById("blog-pagination");
        var html = "";
        if (page.length && pool[0].url !== page[0].url) {
          html += '<a class="newer" href="/resources?offset=' + page[0].ts + "&reversePaginate=true" + extra + '">Newer</a>';
        }
        if (page.length && pool[pool.length - 1].url !== page[page.length - 1].url) {
          html += '<a class="older" href="/resources?offset=' + page[page.length - 1].ts + extra + '">Older</a>';
        }
        nav.innerHTML = html;
        nav.className = "blog-pagination" + (html.indexOf("newer") > -1 && html.indexOf("older") > -1 ? "" : " blog-pagination--single");
      });
    }
  }

  // ---------- Search ----------
  var results = document.getElementById("search-results");
  if (results) {
    var input = document.getElementById("search-q");
    var term = new URLSearchParams(location.search).get("q") || "";
    input.value = term;
    if (term.trim()) {
      fetch("/assets/data/search.json").then(function (r) { return r.json(); }).then(function (pages) {
        var words = term.toLowerCase().split(/\s+/).filter(Boolean);
        var hits = pages.filter(function (p) {
          var hay = (p.title + " " + p.text).toLowerCase();
          return words.every(function (w) { return hay.indexOf(w) > -1; });
        });
        document.getElementById("search-count").textContent =
          hits.length ? hits.length + (hits.length === 1 ? " result" : " results") + " for “" + term + "”" : "No results for “" + term + "”";
        results.innerHTML = hits.map(function (p) {
          return '<li><a href="' + p.url + '">' + esc(p.title) + "</a><p>" + esc(p.text.slice(0, 180)) + "…</p></li>";
        }).join("");
      });
    }
  }
})();
