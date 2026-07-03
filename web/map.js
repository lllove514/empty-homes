/* Empty Homes map. Vanilla JS + Leaflet (canvas renderer). */
(function () {
  "use strict";

  var KIND_COLOR = ["#8c1d1d", "#b3641c", "#5a6b7d", "#6b5a7d"];
  var KIND_NAME = ["public agency", "LLC / corporate", "individual", "other"];

  var PHILLY = L.latLngBounds([39.85, -75.33], [40.16, -74.92]);
  var map = L.map("map", {
    preferCanvas: true,
    minZoom: 11,
    maxZoom: 19,
    maxBounds: PHILLY.pad(0.05),
    maxBoundsViscosity: 1.0,
    zoomSnap: 0.5,
    wheelPxPerZoomLevel: 90
  }).setView([39.99, -75.13], 12);
  L.tileLayer("https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
  }).addTo(map);
  var renderer = L.canvas({ padding: 0.4 });

  fetch("data/meta.json").then(function (r) { return r.json(); }).then(function (meta) {
    document.getElementById("stats").textContent =
      meta.parcel_count.toLocaleString() + " likely-vacant properties · " +
      meta.delinquent_count.toLocaleString() + " tax-delinquent (June 2022) · data generated " + meta.generated;
  });

  fetch("data/points.json").then(function (r) { return r.json(); }).then(function (points) {
    var bounds = [];
    points.forEach(function (p) {
      var lon = p[0], lat = p[1], opa = p[2], score = p[3], kind = p[4];
      var marker = L.circleMarker([lat, lon], {
        renderer: renderer,
        radius: 4.5 + Math.min(score, 10) * 0.55,
        color: "#2b2b2b",
        weight: 0.8,
        fillColor: KIND_COLOR[kind],
        fillOpacity: 0.85
      }).addTo(map);
      marker.bindPopup(
        '<b><a href="parcel.html#' + opa + '">parcel ' + opa + "</a></b><br>" +
        KIND_NAME[kind] + " · accountability score " + score +
        '<br><a href="parcel.html#' + opa + '">full receipt →</a>');
      bounds.push([lat, lon]);
    });
    if (bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
  });

  /* search */
  var input = document.getElementById("q");
  var resultsEl = document.getElementById("results");
  var items = [], active = -1, timer = null;

  function render() {
    resultsEl.innerHTML = "";
    items.forEach(function (r, i) {
      var div = document.createElement("div");
      div.textContent = r.address + " — " + (r.owner || "owner unknown");
      if (i === active) div.className = "active";
      div.onmousedown = function () { choose(r); };
      resultsEl.appendChild(div);
    });
    resultsEl.hidden = items.length === 0;
  }

  function choose(r) {
    resultsEl.hidden = true;
    input.value = r.address;
    map.setView([r.lat, r.lon], 18);
    L.popup().setLatLng([r.lat, r.lon]).setContent(
      "<b>" + r.address + "</b><br>" + (r.owner || "owner unknown") +
      "<br>accountability score " + r.score +
      '<br><a href="parcel.html#' + r.opa_id + '">full receipt →</a>').openOn(map);
  }

  input.addEventListener("input", function () {
    clearTimeout(timer);
    var q = input.value.trim();
    if (q.length < 3) { items = []; render(); return; }
    timer = setTimeout(function () {
      fetch("/api/search?q=" + encodeURIComponent(q))
        .then(function (r) { return r.json(); })
        .then(function (data) { items = data.results; active = -1; render(); })
        .catch(function () { items = []; render(); });
    }, 150);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { active = Math.min(active + 1, items.length - 1); render(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { active = Math.max(active - 1, 0); render(); e.preventDefault(); }
    else if (e.key === "Enter" && active >= 0) { choose(items[active]); }
    else if (e.key === "Escape") { resultsEl.hidden = true; }
  });
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".searchbox")) resultsEl.hidden = true;
  });
})();
