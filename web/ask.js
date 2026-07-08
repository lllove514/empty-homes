/* Ask panel: grounded answers with verified citations.
   On the local install the Python server answers at api/ask. On the public
   demo (GitHub Pages, which can't run code) the same logic runs as a
   Cloudflare Worker; see worker/README.md. */
(function () {
  "use strict";
  var ENDPOINT = location.hostname.endsWith("github.io")
    ? "https://empty-homes-ask.jellybot.workers.dev"
    : "api/ask";
  var form = document.getElementById("askform");
  var input = document.getElementById("askq");
  var out = document.getElementById("askout");

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function linkify(text) {
    return esc(text)
      .replace(/^#{1,4}\s*/gm, "")                       /* strip markdown headers */
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")          /* **bold** -> bold */
      .replace(/^[-*]\s+/gm, "· ")                       /* list markers -> middots */
      .replace(/\[opa:(\d{9})\]/g,
        '<a href="parcel.html#$1">[parcel $1]</a>')
      .replace(/\[owner:(\d+)\]/g,
        '<a href="owners.html#owner/$1">[owner $1]</a>');
  }

  function show(html) {
    out.hidden = false;
    out.innerHTML = html;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q) return;
    show("thinking… (checking the database)");
    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          show('<span class="error">' + esc(data.error) + "</span>");
          return;
        }
        var cites = (data.citations || []).map(function (c) {
          return c.type === "opa"
            ? '<a href="parcel.html#' + esc(c.id) + '">parcel ' + esc(c.id) + "</a>"
            : '<a href="owners.html#owner/' + esc(c.id) + '">owner ' + esc(c.id) + "</a>";
        }).join(" · ");
        show(linkify(data.answer) +
          (cites ? '<div class="cites">verified records: ' + cites + "</div>" : ""));
      })
      .catch(function () {
        show("Couldn't reach the AI layer. The map, search, receipts, and " +
          "leaderboard all still work; try the question again in a minute, or " +
          '<a href="https://github.com/lllove514/empty-homes">run it locally</a>.');
      });
  });

  document.querySelectorAll(".ask-examples a").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      input.value = a.dataset.q;
      form.dispatchEvent(new Event("submit"));
    });
  });
})();
