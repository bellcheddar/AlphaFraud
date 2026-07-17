// AlphaFraud front-end: theme toggle, Plotly rendering, client-side table sort/filter.
(function () {
  "use strict";

  // Theme follows the viewer's OS setting via CSS @media (prefers-color-scheme); there is
  // no manual switcher.

  // ---- Plotly ----
  // Set the width explicitly from the container. autosize/responsive proved unreliable on
  // We pin layout.width to the plot element's own width (autosize/responsive proved
  // unreliable on narrow widths). On mobile we also fix the aspect ratio and shrink/stack
  // the title, legends and axis fonts so nothing clips or overlaps.
  function renderPlots() {
    if (typeof Plotly === "undefined") return;
    var vw = document.documentElement.clientWidth || window.innerWidth || 360;
    var mobile = vw < 620;
    document.querySelectorAll("script[data-target]").forEach(function (s) {
      var el = document.getElementById(s.getAttribute("data-target"));
      if (!el) return;
      var fig;
      try { fig = JSON.parse(s.textContent); } catch (e) { return; }   // fresh clone each call
      var layout = fig.layout || {};
      var w = el.clientWidth || (vw - 32);
      layout.width = w;
      layout.autosize = false;

      if (mobile) {
        // Squarer aspect so bubbles aren't vertically squished on a narrow screen.
        layout.height = Math.max(320, Math.round(w * 0.95));
        var hasL2 = !!layout.legend2, hasL = !!layout.legend;
        layout.margin = { l: 46, r: 14, t: hasL2 ? 120 : (hasL ? 92 : 54), b: 58 };
        if (layout.title) {
          layout.title.font = Object.assign({}, layout.title.font, { size: 13 });
          layout.title.x = 0.5; layout.title.xanchor = "center"; layout.title.y = 0.985;
        }
        // Stack the two legends (colour above size) instead of side by side.
        if (hasL) layout.legend = Object.assign({}, layout.legend,
          { x: 0, xanchor: "left", y: hasL2 ? 1.19 : 1.12, font: { size: 10 } });
        if (hasL2) layout.legend2 = Object.assign({}, layout.legend2,
          { x: 0, xanchor: "left", y: 1.09, font: { size: 10 } });
        ["xaxis", "yaxis", "xaxis2", "yaxis2"].forEach(function (ax) {
          if (layout[ax] && layout[ax].title) {
            layout[ax].title.font = Object.assign({}, layout[ax].title.font, { size: 11 });
          }
        });
      } else if (!layout.height) {
        layout.height = 440;
      }
      Plotly.react(el, fig.data, layout, { displayModeBar: false, responsive: false });
      if (window.wireScatterPreview) window.wireScatterPreview(el);
    });
  }

  var _rt;
  window.addEventListener("resize", function () {
    clearTimeout(_rt);
    _rt = setTimeout(renderPlots, 150);
  });

  // ---- Tables: sort + filter ----
  function cellValue(row, idx) {
    var td = row.children[idx];
    var v = td.getAttribute("data-sort");
    if (v === null) v = td.textContent.trim();
    var n = parseFloat(v);
    return isNaN(n) ? v.toLowerCase() : n;
  }

  function initTable(table) {
    var tbody = table.tBodies[0];
    if (!tbody) return;
    Array.prototype.forEach.call(table.tHead.rows[0].cells, function (th, idx) {
      th.addEventListener("click", function () {
        var asc = !th.classList.contains("sorted-asc");
        Array.prototype.forEach.call(table.tHead.rows[0].cells, function (h) {
          h.classList.remove("sorted-asc", "sorted-desc");
        });
        th.classList.add(asc ? "sorted-asc" : "sorted-desc");
        var rows = Array.prototype.slice.call(tbody.rows);
        rows.sort(function (a, b) {
          var va = cellValue(a, idx), vb = cellValue(b, idx);
          if (va < vb) return asc ? -1 : 1;
          if (va > vb) return asc ? 1 : -1;
          return 0;
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      });
    });
  }

  function initFilters() {
    var search = document.getElementById("tableSearch");
    var wrongOnly = document.getElementById("wrongOnly");
    var novelOnly = document.getElementById("novelOnly");
    var table = document.getElementById("dataTable");
    if (!table) return;
    function apply() {
      var q = (search && search.value || "").toLowerCase();
      var w = wrongOnly && wrongOnly.checked;
      var n = novelOnly && novelOnly.checked;
      Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
        var text = row.textContent.toLowerCase();
        var ok = (!q || text.indexOf(q) !== -1) &&
                 (!w || row.getAttribute("data-wrong") === "1") &&
                 (!n || row.getAttribute("data-novel") === "1");
        row.style.display = ok ? "" : "none";
      });
    }
    [search, wrongOnly, novelOnly].forEach(function (el) {
      if (el) el.addEventListener("input", apply);
    });
  }

  // ---- CSV export ----
  function csvEscape(v) {
    v = (v == null ? "" : String(v));
    return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  }
  function triggerCsv(rows, filename) {
    var csv = rows.map(function (r) { return r.map(csvEscape).join(","); }).join("\n");
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = filename || "alphafraud.csv";
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(a.href);
  }
  window.downloadTableCsv = function (tableId, filename) {
    var t = document.getElementById(tableId);
    if (!t || !t.tHead || !t.tBodies[0]) return;
    var rows = [[]];
    Array.prototype.forEach.call(t.tHead.rows[0].cells, function (c) { rows[0].push(c.textContent.trim()); });
    Array.prototype.forEach.call(t.tBodies[0].rows, function (tr) {
      if (tr.style.display === "none") return;   // respect the active filter
      var row = [];
      Array.prototype.forEach.call(tr.cells, function (c) { row.push(c.textContent.trim()); });
      rows.push(row);
    });
    triggerCsv(rows, filename);
  };
  window.downloadPlotCsv = function (plotId, filename) {
    var el = document.getElementById(plotId);
    if (!el || !el.data) return;
    var data = el.data, rows = [];
    if (data.some(function (t) { return t.z; })) {            // heatmap -> dump the z matrix
      data.filter(function (t) { return t.z; })[0].z.forEach(function (r) { rows.push(r.slice()); });
    } else {
      var hasCd = data.some(function (t) { return t.customdata; });
      rows.push(hasCd ? ["trace", "x", "y", "label"] : ["trace", "x", "y"]);
      data.forEach(function (t) {
        var x = t.x || [], y = t.y || [], cd = t.customdata || [], n = Math.max(x.length, y.length);
        for (var i = 0; i < n; i++) {
          if (x[i] == null && y[i] == null) continue;         // skips the empty size-legend traces
          var row = [t.name || "", x[i], y[i]];
          if (hasCd) row.push(cd[i] ? cd[i][0] : "");
          rows.push(row);
        }
      });
    }
    triggerCsv(rows, filename);
  };

  // ---- Header live-stats panel ----
  function loadStats() {
    if (!document.getElementById("statsPanel")) return;
    fetch("/api/stats").then(function (r) { return r.json(); }).then(function (s) {
      function set(id, v) { var el = document.getElementById(id); if (el) el.textContent = v; }
      var n = function (x) { return (x == null ? 0 : x).toLocaleString(); };
      set("stAnalysed", n(s.analysed));
      set("stCW", n(s.confidently_wrong));
      set("stArch", (s.archive_pct != null ? s.archive_pct + "%" : "—"));
      set("stDb", (s.db_mb != null ? s.db_mb + " MB" : "—"));
      set("stMem", (s.memory_mb != null ? s.memory_mb + " MB" : "—"));
      set("stVis", n(s.unique_visitors));
    }).catch(function () {});
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderPlots();
    document.querySelectorAll("table.sortable").forEach(initTable);
    initFilters();
    loadStats();
    setInterval(loadStats, 60000);
  });
})();

/* ---- Interactive 3D ribbon viewer (3Dmol.js, vendored, lazy-loaded) ---- */
(function () {
  var loaded = false, loading = false, viewer = null, on = false;

  function devColor(b) {                       // deviation (Å in B-factor) -> hex int
    if (b < 0) return 0x9aa7b3;                // unmatched residue = grey
    var d = Math.max(0, Math.min(b, 10));
    var s = [[0,[30,115,190]],[1,[74,159,212]],[2,[120,190,180]],
             [3,[252,185,0]],[6,[232,89,12]],[10,[200,30,30]]];
    for (var i = 0; i < s.length - 1; i++) {
      var a = s[i], c = s[i + 1];
      if (d <= c[0]) {
        var t = c[0] === a[0] ? 0 : (d - a[0]) / (c[0] - a[0]);
        var r = Math.round(a[1][0] + (c[1][0] - a[1][0]) * t);
        var g = Math.round(a[1][1] + (c[1][1] - a[1][1]) * t);
        var bl = Math.round(a[1][2] + (c[1][2] - a[1][2]) * t);
        return (r << 16) | (g << 8) | bl;
      }
    }
    return 0xc81e1e;
  }

  function load3Dmol(cb) {
    if (loaded && window.$3Dmol) { cb(); return; }
    if (loading) { setTimeout(function () { load3Dmol(cb); }, 150); return; }
    loading = true;
    var s = document.createElement("script");
    s.src = "/static/3Dmol-min.js";
    s.onload = function () { loaded = true; cb(); };
    s.onerror = function () { var h = document.getElementById("viewer3dHint"); if (h) h.textContent = "3D viewer failed to load."; };
    document.head.appendChild(s);
  }

  // This 3Dmol build doesn't set atom.ss from HELIX/SHEET records, so we parse those records
  // (which the server writes) ourselves and set atom.ss -> a real cartoon, not a tube.
  function ssMapFromPdb(pdb) {
    var map = {};
    pdb.split("\n").forEach(function (line) {
      if (line.lastIndexOf("HELIX", 0) === 0) {
        var s = parseInt(line.substring(21, 25), 10), e = parseInt(line.substring(33, 37), 10);
        for (var i = s; i <= e; i++) map[i] = "h";
      } else if (line.lastIndexOf("SHEET", 0) === 0) {
        var s2 = parseInt(line.substring(22, 26), 10), e2 = parseInt(line.substring(33, 37), 10);
        for (var j = s2; j <= e2; j++) map[j] = "s";
      }
    });
    return map;
  }
  function applySS(model, pdb) {
    var map = ssMapFromPdb(pdb);
    model.selectedAtoms({}).forEach(function (a) { a.ss = map[a.resi] || "c"; });
  }

  var ghostModel = null, ghostOn = false, ghostUrlSaved = "", expModel = null;
  // The AlphaFold model as a solid, crisp blue backbone trace: a thin opaque tube so it reads
  // clearly over the (undimmed, full-colour) experiment without fogging it.
  var GHOST_STYLE = { cartoon: { color: 0x2563eb, style: "trace", thickness: 0.8 } };

  window.toggleGhost = function () {
    if (!viewer || !ghostUrlSaved) return;
    var gbtn = document.getElementById("btnGhost");
    if (ghostModel) {                          // already loaded -> just toggle visibility
      ghostOn = !ghostOn;
      ghostModel.setStyle({}, ghostOn ? GHOST_STYLE : {});
      viewer.render();
      gbtn.textContent = ghostOn ? "👻 Hide AlphaFold ghost" : "👻 AlphaFold ghost";
      return;
    }
    gbtn.textContent = "loading…";
    fetch(ghostUrlSaved).then(function (r) { return r.text(); }).then(function (pdb) {
      ghostModel = viewer.addModel(pdb, "pdb");
      ghostModel.setStyle({}, GHOST_STYLE);
      ghostOn = true;
      viewer.render();
      gbtn.textContent = "👻 Hide AlphaFold ghost";
    }).catch(function () { gbtn.textContent = "👻 AlphaFold ghost"; });
  };

  window.toggleRibbon3D = function (eid, coordsUrl, ghostUrl) {
    var img = document.getElementById("ribbonImg"),
        div = document.getElementById("viewer3d"),
        btn = document.getElementById("btn3d"),
        gbtn = document.getElementById("btnGhost"),
        hint = document.getElementById("viewer3dHint");
    if (on) {                                  // back to the static ribbon
      if (viewer) viewer.spin(false);
      div.style.display = "none"; img.style.display = "";
      if (gbtn) gbtn.style.display = "none";
      btn.textContent = "🔄 Interactive 3D"; hint.textContent = ""; on = false;
      return;
    }
    hint.textContent = "loading…";
    ghostUrlSaved = ghostUrl || "";
    load3Dmol(function () {
      fetch(coordsUrl).then(function (r) { return r.text(); }).then(function (pdb) {
        img.style.display = "none"; div.style.display = "block";
        if (!viewer) viewer = $3Dmol.createViewer(div, { backgroundAlpha: 0 });
        else viewer.clear();
        ghostModel = null; ghostOn = false;
        expModel = viewer.addModel(pdb, "pdb");
        applySS(expModel, pdb);
        expModel.setStyle({}, { cartoon: { colorfunc: devColor, arrows: true } });
        viewer.zoomTo();
        viewer.spin("y", 0.5);
        viewer.render();
        btn.textContent = "⏸ Show flat ribbon";
        hint.textContent = "drag to rotate · scroll to zoom";
        if (gbtn && ghostUrlSaved) { gbtn.style.display = ""; gbtn.textContent = "👻 AlphaFold ghost"; }
        on = true;
      }).catch(function () { hint.textContent = "could not load coordinates."; });
    });
  };
})();

/* ---- Ribbon hover-preview on the fraud-quadrant scatter ---- */
(function () {
  var box = null, img = null;
  function ensureBox() {
    if (box) return;
    box = document.createElement("div");
    box.className = "ribbon-preview";
    img = document.createElement("img");
    var cap = document.createElement("div");
    cap.className = "ribbon-preview-cap";
    box.appendChild(img); box.appendChild(cap);
    img.onerror = function () { hide(); };          // no ribbon for this entity -> don't show
    img.onload = function () { box.style.display = "block"; };
    document.body.appendChild(box);
    box._cap = cap;
  }
  function hide() { if (box) box.style.display = "none"; }

  window.wireScatterPreview = function (el) {
    if (!el || el._ribbonHoverWired || !el.on) return;
    // Only plots whose points carry an entity_id in customdata[0] (the fraud scatter).
    el._ribbonHoverWired = true;
    el.on("plotly_hover", function (d) {
      var pt = d.points && d.points[0];
      if (!pt || !pt.customdata || !pt.customdata[0]) return;
      var eid = String(pt.customdata[0]);
      if (!/^[0-9A-Za-z]{4}_/.test(eid)) return;     // looks like an entity id
      ensureBox();
      box._cap.textContent = eid + "  ·  Cα deviation";
      img.src = "/ribbon/" + encodeURIComponent(eid) + ".svg";
      var ev = d.event || window.event;
      var x = (ev.clientX || 0) + 16, y = (ev.clientY || 0) + 16;
      x = Math.min(x, window.innerWidth - 210);
      y = Math.min(y, window.innerHeight - 200);
      box.style.left = x + "px"; box.style.top = y + "px";
    });
    el.on("plotly_unhover", hide);
  };
})();
