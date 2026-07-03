/* Empty Homes map. Vanilla JS + Leaflet.
   All parcels are drawn on a single canvas layer with zoom-scaled radii,
   instead of one Leaflet marker per parcel. At 36k+ points, per-marker
   layers are unusably slow and render as overlapping blobs. */
(function () {
  "use strict";

  var KIND_COLOR = ["#8c1d1d", "#b3641c", "#5a6b7d", "#6b5a7d"];
  var KIND_NAME = ["public agency", "LLC / corporate", "individual", "other"];
  var PHILLY = L.latLngBounds([39.85, -75.33], [40.16, -74.92]);

  var map = L.map("map", {
    minZoom: 11,
    maxZoom: 19,
    maxBounds: PHILLY.pad(0.05),
    maxBoundsViscosity: 1.0
  }).setView([39.99, -75.13], 12);

  L.tileLayer("https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
  }).addTo(map);

  /* points: [lon, lat, opa, score, kind], sorted so public draws on top */
  var points = [];

  function radiusFor(z, score) {
    var base = z <= 12 ? 1.7 : z === 13 ? 2.4 : z === 14 ? 3.2
             : z === 15 ? 4.4 : z === 16 ? 5.8 : 7.2;
    if (z >= 15) base += Math.min(score, 10) * 0.22;
    return base;
  }

  var PointsLayer = L.Layer.extend({
    onAdd: function (m) {
      this._map = m;
      this._canvas = L.DomUtil.create("canvas", "leaflet-layer");
      this._canvas.style.pointerEvents = "none";
      m.getPanes().overlayPane.appendChild(this._canvas);
      m.on("moveend viewreset resize", this._reset, this);
      m.on("zoomanim", this._animateZoom, this);
      this._reset();
    },
    _animateZoom: function (e) {
      var scale = this._map.getZoomScale(e.zoom);
      var offset = this._map._latLngBoundsToNewLayerBounds(
        this._map.getBounds(), e.zoom, e.center).min;
      L.DomUtil.setTransform(this._canvas, offset, scale);
    },
    _reset: function () {
      var m = this._map;
      var size = m.getSize();
      var topLeft = m.containerPointToLayerPoint([0, 0]);
      L.DomUtil.setPosition(this._canvas, topLeft);
      var dpr = window.devicePixelRatio || 1;
      this._canvas.width = size.x * dpr;
      this._canvas.height = size.y * dpr;
      this._canvas.style.width = size.x + "px";
      this._canvas.style.height = size.y + "px";

      var ctx = this._canvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size.x, size.y);

      var z = m.getZoom();
      var stroke = z >= 14;
      ctx.globalAlpha = z <= 12 ? 0.7 : 0.85;
      ctx.strokeStyle = "rgba(40,40,40,0.55)";
      ctx.lineWidth = 0.7;

      var pad = 12;
      for (var i = 0; i < points.length; i++) {
        var pt = points[i];
        var cp = m.latLngToContainerPoint([pt[1], pt[0]]);
        if (cp.x < -pad || cp.y < -pad || cp.x > size.x + pad || cp.y > size.y + pad) continue;
        ctx.beginPath();
        ctx.arc(cp.x, cp.y, radiusFor(z, pt[3]), 0, 6.2832);
        ctx.fillStyle = KIND_COLOR[pt[4]];
        ctx.fill();
        if (stroke) ctx.stroke();
      }
    }
  });
  var layer = new PointsLayer();

  /* click: nearest point within tap distance */
  map.on("click", function (e) {
    if (!points.length) return;
    var z = map.getZoom();
    var click = map.latLngToContainerPoint(e.latlng);
    var best = null, bestD = 1e9;
    for (var i = 0; i < points.length; i++) {
      var cp = map.latLngToContainerPoint([points[i][1], points[i][0]]);
      var dx = cp.x - click.x, dy = cp.y - click.y;
      var d = dx * dx + dy * dy;
      if (d < bestD) { bestD = d; best = points[i]; }
    }
    var hitRadius = radiusFor(z, best ? best[3] : 0) + 6;
    if (best && bestD <= hitRadius * hitRadius) {
      L.popup().setLatLng([best[1], best[0]]).setContent(
        "<b>" + KIND_NAME[best[4]] + "</b> · accountability score " + best[3] +
        '<br><a href="parcel.html#' + best[2] + '">full receipt for parcel ' + best[2] + " →</a>"
      ).openOn(map);
    }
  });

  fetch("data/meta.json").then(function (r) { return r.json(); }).then(function (meta) {
    document.getElementById("stats").textContent =
      meta.parcel_count.toLocaleString() + " likely-vacant properties · " +
      meta.delinquent_count.toLocaleString() + " tax-delinquent (June 2022) · data generated " + meta.generated;
  });

  fetch("data/points.json").then(function (r) { return r.json(); }).then(function (data) {
    /* draw public owners last so they sit on top */
    points = data.sort(function (a, b) { return b[4] - a[4]; });
    layer.addTo(map);
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
