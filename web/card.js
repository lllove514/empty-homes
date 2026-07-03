/* Share card renderer: 1200x630 PNG drawn on an offscreen canvas. */
(function () {
  "use strict";

  function wrap(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
    var words = String(text).split(" "), line = "", lines = 0;
    for (var i = 0; i < words.length; i++) {
      var test = line ? line + " " + words[i] : words[i];
      if (ctx.measureText(test).width > maxWidth && line) {
        ctx.fillText(line, x, y);
        y += lineHeight;
        line = words[i];
        if (++lines >= maxLines - 1) {
          ctx.fillText(line + "…", x, y);
          return y + lineHeight;
        }
      } else {
        line = test;
      }
    }
    ctx.fillText(line, x, y);
    return y + lineHeight;
  }

  /* opts: { title, subtitle, facts: [..], permalink } */
  window.renderShareCard = function (opts, filename) {
    var c = document.createElement("canvas");
    c.width = 1200; c.height = 630;
    var ctx = c.getContext("2d");

    ctx.fillStyle = "#1f1f1f";
    ctx.fillRect(0, 0, 1200, 630);
    ctx.fillStyle = "#8c1d1d";
    ctx.fillRect(0, 0, 1200, 14);

    ctx.fillStyle = "#c9c4b8";
    ctx.font = "26px Georgia, serif";
    ctx.fillText("EMPTY HOMES · PHILADELPHIA", 60, 78);

    ctx.fillStyle = "#f2efe8";
    ctx.font = "bold 56px Georgia, serif";
    var y = wrap(ctx, opts.title, 60, 160, 1080, 64, 2);

    if (opts.subtitle) {
      ctx.fillStyle = "#c9c4b8";
      ctx.font = "30px Georgia, serif";
      y = wrap(ctx, opts.subtitle, 60, y + 10, 1080, 40, 2);
    }

    ctx.font = "34px Georgia, serif";
    y += 26;
    (opts.facts || []).slice(0, 4).forEach(function (fact) {
      ctx.fillStyle = "#8c5a1d";
      ctx.fillText("■", 60, y);
      ctx.fillStyle = "#f2efe8";
      y = wrap(ctx, fact, 100, y, 1040, 44, 2) + 8;
    });

    ctx.fillStyle = "#9a927e";
    ctx.font = "24px Georgia, serif";
    ctx.fillText("every fact from public city records · " + (opts.permalink || ""), 60, 585);

    var a = document.createElement("a");
    a.download = filename || "empty-homes-card.png";
    a.href = c.toDataURL("image/png");
    a.click();
  };
})();
