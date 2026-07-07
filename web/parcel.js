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
            var d = v.date ? String(v.date).slice(0, 10) : "date unknown";
            return esc(d + " · " + v.title);
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
        row("Last sale", p.sale_date ? esc(String(p.sale_date).slice(0, 10)) + (p.sale_price != null ? " for " + esc(dollars(p.sale_price)) : "") : null,
            "OPA assessment") +
        row("Owner mailing address", esc(p.mailing_addr), "OPA / Revenue records") +
        "</table>" +
        "<h2 style='margin-top:22px'>Accountability score: " + p.score + "</h2>" +
        scoreRows +
        '<p style="margin-top:18px">' +
        '<button id="copy">copy link to this parcel</button> ' +
        '<button id="card" class="secondary">download share card</button> ' +
        '<a class="btn secondary" href="index.html">back to map</a></p>' +
        "<h2 style='margin-top:22px'>Take action</h2>" +
        "<p class='sub'>Drafts are filled from this parcel's public record, nothing else. " +
        "Review every fact, add your name, and send it yourself.</p>" +
        "<p>" +
        '<button class="draft-btn" data-type="foia">records request (right-to-know)</button> ' +
        '<button class="draft-btn" data-type="council">letter to the council office</button> ' +
        '<button class="draft-btn" data-type="testimony">testimony paragraph</button>' +
        "</p>" +
        '<div id="draftout" hidden>' +
        '<div class="notice" id="draftnotice"></div>' +
        '<textarea id="drafttext" style="width:100%;height:340px;font-family:monospace;font-size:13px;"></textarea>' +
        '<p><button id="draftcopy" class="secondary">copy draft</button></p></div>' +
        '<p class="footnote">"Likely vacant" is the city\'s model-based indicator, not a field inspection. ' +
        "The score formula is fixed and public: min(years delinquent, 10) + min(open violations, 5) " +
        "+ 3 if publicly owned + 2 if flagged for sheriff sale.</p>";

      document.getElementById("copy").onclick = function () {
        navigator.clipboard.writeText(location.href).then(function () {
          document.getElementById("copy").textContent = "link copied";
        });
      };

      document.getElementById("card").onclick = function () {
        var facts = [];
        if (p.vacant_flag) facts.push("flagged likely vacant by the city (" + p.vacant_flag.toLowerCase() + ")");
        if (p.delinquent) facts.push(p.years_owed + " year(s) tax-delinquent, " +
          (dollars(p.total_due) || "") + " due, as of June 2022");
        if (p.open_violations) facts.push(p.open_violations + " open L&I violation(s)");
        facts.push("owned by " + (p.owner_name || p.owner_raw || "unknown"));
        window.renderShareCard({
          title: p.address,
          subtitle: "OPA account " + p.opa_id + " · accountability score " + p.score,
          facts: facts,
          permalink: location.host + "/parcel.html%23" + p.opa_id
        }, "empty-homes-" + p.opa_id + ".png");
      };

      document.querySelectorAll(".draft-btn").forEach(function (b) {
        b.onclick = function () {
          b.textContent = "drafting…";
          fetch("/api/draft", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: b.dataset.type, opa_id: p.opa_id })
          })
            .then(function (r) { return r.json(); })
            .then(function (d) {
              b.textContent = b.dataset.type === "foia" ? "records request (right-to-know)"
                : b.dataset.type === "council" ? "letter to the council office" : "testimony paragraph";
              var box = document.getElementById("draftout");
              if (d.error) {
                box.hidden = false;
                document.getElementById("draftnotice").textContent = d.error;
                return;
              }
              box.hidden = false;
              document.getElementById("draftnotice").textContent = "DRAFT. " + d.review_notice;
              document.getElementById("drafttext").value = d.draft;
              box.scrollIntoView({ behavior: "smooth" });
            });
        };
      });
      document.getElementById("draftcopy").onclick = function () {
        navigator.clipboard.writeText(document.getElementById("drafttext").value)
          .then(function () { document.getElementById("draftcopy").textContent = "copied"; });
      };
    })
    .catch(function () {
      main.innerHTML = '<p class="error">No record for parcel ' + esc(opa) +
        '. It may not be in the current build. <a href="index.html">Back to the map.</a></p>';
    });
})();
