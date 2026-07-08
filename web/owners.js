/* Leaderboard and owner detail. Hash routes: #  |  #owner/<id> */
(function () {
  "use strict";
  var main = document.getElementById("main");
  var FILTERS = [["", "all owners"], ["public", "public only"], ["llc", "LLCs only"], ["individual", "individuals only"]];

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }
  function dollars(n) {
    return n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
  }
  function pill(kind) {
    var label = kind === "public" ? "public agency" : kind;
    return '<span class="pill ' + esc(kind) + '">' + esc(label) + "</span>";
  }

  function route() {
    var m = (location.hash || "").match(/^#owner\/(\d+)/);
    if (m) renderOwner(m[1]);
    else renderBoard((location.hash || "").replace("#", ""));
  }

  function renderBoard(kind) {
    if (FILTERS.every(function (f) { return f[0] !== kind; })) kind = "";
    fetch("api/owners" + (kind ? "?kind=" + kind : ""))
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .catch(function () {
        /* static-demo fallback */
        return fetch("data/owners_top.json")
          .then(function (r) { return r.json(); })
          .then(function (top) { return { owners: top[kind || "all"] }; });
      })
      .then(function (data) {
        var owners = data.owners;
        var top = owners[0];
        var headline = top
          ? "<div class='headline'><b>" + esc(top.canonical_name) + "</b> holds <b>" +
            top.parcel_count + "</b> likely-vacant properties in this dataset" +
            (top.total_due ? ", owing " + dollars(top.total_due) + " in back taxes as of June 2022" : "") + "."
          : "<div class='headline'>No owners match this filter.";
        headline += "</div>";

        var buttons = "<div class='filters'>" + FILTERS.map(function (f) {
          return "<button class='" + (f[0] === kind ? "" : "off") + "' data-k='" + f[0] + "'>" + f[1] + "</button>";
        }).join("") + "</div>";

        var rows = owners.map(function (o, i) {
          return "<tr>" +
            "<td class='num'>" + (i + 1) + "</td>" +
            "<td><a href='#owner/" + o.id + "'>" + esc(o.canonical_name) + "</a>" + pill(o.kind) +
            (o.cluster_id != null ? " <small>(linked network)</small>" : "") + "</td>" +
            "<td class='num'>" + o.parcel_count + "</td>" +
            "<td class='num'>" + dollars(o.total_due) + "</td>" +
            "<td class='num'>" + (o.avg_years_owed == null ? "—" : o.avg_years_owed) + "</td></tr>";
        }).join("");

        main.innerHTML = "<h2>Who owns the most empty homes</h2>" + headline + buttons +
          "<table class='board'><tr><th class='num'>#</th><th>owner</th>" +
          "<th class='num'>likely-vacant properties</th><th class='num'>back taxes due (June 2022)</th>" +
          "<th class='num'>avg years owed</th></tr>" + rows + "</table>" +
          "<p class='footnote'>Owner names are grouped by normalizing the raw strings on the public record " +
          "and by a hand-curated alias list for public agencies. “Linked network” means the owner " +
          "shares a mailing address with other entities on this board, a fact, not a claim of common control.</p>";

        main.querySelectorAll(".filters button").forEach(function (b) {
          b.onclick = function () { location.hash = b.dataset.k; };
        });
      });
  }

  function renderOwner(id) {
    fetch("api/owner/" + id)
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .catch(function () {
        /* static-demo fallback: exported for owners on the board */
        return fetch("data/owners/" + id + ".json")
          .then(function (r) { if (!r.ok) throw new Error(); return r.json(); });
      })
      .then(function (o) {
        var clusterHtml = "";
        if (o.cluster && o.cluster.length) {
          clusterHtml = "<div class='cluster-note'><b>Shares a mailing address" +
            (o.shared_mailing_addr ? " (" + esc(o.shared_mailing_addr) + ")" : "") + " with:</b> " +
            o.cluster.map(function (c) {
              return "<a href='#owner/" + c.id + "'>" + esc(c.canonical_name) + "</a> (" + c.parcel_count + ")";
            }).join(" · ") +
            "<br><small>A shared mailing address is a documented fact. It is not, by itself, proof of common ownership.</small></div>";
        }
        var aliasHtml = o.aliases.length > 1
          ? "<p class='sub'>appears in the record as: " + o.aliases.map(esc).join(" / ") + "</p>" : "";

        var rows = o.parcels.map(function (p) {
          return "<tr><td><a href='parcel.html#" + p.opa_id + "'>" + esc(p.address) + "</a></td>" +
            "<td>" + esc(p.zip || "—") + "</td>" +
            "<td>" + (p.delinquent ? esc(p.years_owed + " yr, " + dollars(p.total_due)) : "—") + "</td>" +
            "<td>" + (p.open_violations || "—") + "</td>" +
            "<td>" + p.score + "</td></tr>";
        }).join("");

        main.innerHTML = "<p><a href='owners.html'>&larr; back to the board</a></p>" +
          "<h2>" + esc(o.canonical_name) + pill(o.kind) + "</h2>" + aliasHtml +
          "<div class='sub'>" + o.parcel_count + " likely-vacant properties · " +
          dollars(o.total_due) + " back taxes due (June 2022)</div>" + clusterHtml +
          "<div class='owner-detail'><table><tr><th>address</th><th>zip</th>" +
          "<th>delinquency (June 2022)</th><th>open violations</th><th>score</th></tr>" +
          rows + "</table></div>";
        window.scrollTo(0, 0);
      })
      .catch(function () {
        main.innerHTML = "<p class='error'>This owner's page is not in the static demo " +
          "(only owners on the board are exported). Run the project locally for every owner. " +
          "<a href='owners.html'>Back to the board.</a></p>";
      });
  }

  window.addEventListener("hashchange", route);
  route();
})();
