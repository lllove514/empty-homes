/* Parcel receipt page. Reads the opa id from the URL hash. */
(function () {
  "use strict";
  var main = document.getElementById("main");

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }
  function dollars(n) {
    return n == null ? null : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2 });
  }
  function row(label, value, source) {
    return "<tr><th>" + esc(label) + (source ? '<span class="src">' + esc(source) + "</span>" : "") +
           "</th><td>" + (value == null || value === "" ? "—" : value) + "</td></tr>";
  }

  var opa = (location.hash || "").replace("#", "").trim();
  if (!/^\d{9}$/.test(opa)) {
    main.innerHTML = '<p class="error">No parcel selected. Open a parcel from the <a href="index.html">map</a>.</p>';
    return;
  }

  fetch("/api/parcel/" + opa)
    .then(function (r) { if (!r.ok) throw new Error("not found"); return r.json(); })
    .then(function (p) {
      document.title = p.address + " · Empty Homes";
      var kind = p.owner_kind || "other";
      var ownerHtml = p.owner_name
        ? '<a href="owners.html#owner/' + p.oid + '">' + esc(p.owner_name) + "</a>" +
          '<span class="pill ' + kind + '">' + esc(kind === "public" ? "public agency" : kind) + "</span>"
        : esc(p.owner_raw);

      var delinq;
      if (p.delinquent) {
        delinq = esc(p.years_owed + " year(s) owed") +
          (p.oldest_year_owed ? esc(", oldest unpaid year " + p.oldest_year_owed) : "") +
          (p.total_due != null ? ", " + esc(dollars(p.total_due)) + " due" : "") +
          " <b>(as of June 2022)</b>";
      } else {
        delinq = "not in the June 2022 delinquency snapshot";
      }

      var vio = p.violations.length
        ? p.violations.map(function (v) {
            return esc((v.date || "date unknown") + " · " + v.title);
          }).join("<br>")
        : "none open";

      var scoreRows = p.score_components.map(function (c) {
        return '<div class="score-line"><span>' + esc(c.reason) + "</span><b>+" + c.points + "</b></div>";
      }).join("") || '<div class="score-line"><span>no accountability signals on record</span><b>0</b></div>';

      main.innerHTML =
        "<h2>" + esc(p.address) + "</h2>" +
        '<div class="sub">OPA account ' + esc(p.opa_id) + " · ZIP " + esc(p.zip || "—") +
        " · council district " + esc(p.council_district || "—") + "</div>" +
        '<table class="receipt">' +
        row("Owner", ownerHtml, "OPA property assessment") +
        row("Likely vacant", esc(p.vacant_flag ? p.vacant_flag + " (city vacancy rank " + p.vacant_rank + ")" : null),
            "L&I Vacant Property Indicators") +
        row("Tax delinquency", delinq, "Dept. of Revenue, June 2022 snapshot") +
        row("Open violations", vio, "L&I violations (live dataset)") +
        row("Market value", esc(dollars(p.market_value)), "OPA assessment") +
        row("Last sale", p.sale_date ? esc(p.sale_date) + (p.sale_price != null ? " for " + esc(dollars(p.sale_price)) : "") : null,
            "OPA assessment") +
        row("Owner mailing address", esc(p.mailing_addr), "OPA / Revenue records") +
        "</table>" +
        "<h2 style='margin-top:22px'>Accountability score: " + p.score + "</h2>" +
        scoreRows +
        '<p style="margin-top:18px">' +
        '<button id="copy">copy link to this parcel</button> ' +
        '<a class="btn secondary" href="index.html">back to map</a></p>' +
        '<p class="footnote">"Likely vacant" is the city\'s model-based indicator, not a field inspection. ' +
        "The score formula is fixed and public: min(years delinquent, 10) + min(open violations, 5) " +
        "+ 3 if publicly owned + 2 if flagged for sheriff sale.</p>";

      document.getElementById("copy").onclick = function () {
        navigator.clipboard.writeText(location.href).then(function () {
          document.getElementById("copy").textContent = "link copied";
        });
      };
    })
    .catch(function () {
      main.innerHTML = '<p class="error">No record for parcel ' + esc(opa) +
        '. It may not be in the current build. <a href="index.html">Back to the map.</a></p>';
    });
})();
