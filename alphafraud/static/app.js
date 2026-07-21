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
  // Word-wrap a title to <= maxChars per line (plotly honours <br> in titles), so long titles
  // don't clip on narrow screens.
  function wrapTitle(text, maxChars) {
    var words = String(text).split(" "), lines = [], cur = "";
    for (var i = 0; i < words.length; i++) {
      var word = words[i];
      if (cur && (cur.length + 1 + word.length) > maxChars) { lines.push(cur); cur = word; }
      else { cur = cur ? cur + " " + word : word; }
    }
    if (cur) lines.push(cur);
    return lines.join("<br>");
  }

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

      var keepH = layout.meta && layout.meta.keepHeight && layout.height;
      if (mobile) {
        var hasL2 = !!layout.legend2, hasL = !!layout.legend, hasL3 = !!layout.legend3;
        var legRows = (hasL ? 1 : 0) + (hasL2 ? 1 : 0) + (hasL3 ? 1 : 0);
        // Vertically-stacked subplots (the histograms) declare their own height and separate-
        // domain y-axes (no `overlaying`); overlaying right-hand axes (the trend) are different.
        var stacked = !!(layout.yaxis2 && !layout.yaxis2.overlaying);
        var rightAxis = !!((layout.yaxis2 && layout.yaxis2.overlaying) ||
                           (layout.yaxis3 && layout.yaxis3.overlaying));
        // Index of MY stats box (a paper annotation with a bgcolor) — not make_subplots' titles.
        var annIdx = -1;
        (layout.annotations || []).forEach(function (a, i) {
          if (a && a.xref === "paper" && a.yref === "paper" && a.bgcolor) annIdx = i;
        });
        var trendLike = rightAxis && annIdx >= 0;   // the 3-axis trend with a stats box
        // Wrap a long title so it doesn't clip off the edges.
        var titleLines = 1;
        if (layout.title) {
          if (typeof layout.title === "string") layout.title = { text: layout.title };
          if (layout.title.text) {
            layout.title.text = wrapTitle(layout.title.text, 30);
            titleLines = layout.title.text.split("<br>").length;
          }
          layout.title.font = Object.assign({}, layout.title.font, { size: 12.5 });
          layout.title.x = 0.5; layout.title.xanchor = "center";
        }
        // Keep the tall server height for stacked subplots / ranked lists; otherwise size to width.
        if (!keepH && !stacked) layout.height = Math.max(360, Math.round(w * 0.98)) + legRows * 30;
        ["xaxis", "yaxis", "xaxis2", "yaxis2", "xaxis3", "yaxis3"].forEach(function (ax) {
          if (layout[ax] && layout[ax].title) {
            layout[ax].title.font = Object.assign({}, layout[ax].title.font, { size: 10 });
          }
        });

        if (trendLike) {
          // The two right-hand axis titles overlap on a phone; drop them — the legend names each
          // series and the black/red tick colours tie the numbers to the right axis.
          if (layout.yaxis2) layout.yaxis2.title = { text: "" };
          if (layout.yaxis3) layout.yaxis3.title = { text: "" };
          if (!keepH) layout.height = 520;
          layout.margin = { l: 52, r: 46, t: 34 + titleLines * 22, b: 184 };
          var ty = -98 / layout.height;   // clear the x-axis title with breathing room
          // 50:50 row below the plot — legend on the LEFT (vertical), stats box on the RIGHT.
          // Wrap the box narrow enough to fit its half so it can't overlap the legend.
          if (hasL) layout.legend = Object.assign({}, layout.legend,
            { orientation: "v", x: 0, xanchor: "left", y: ty, yanchor: "top", font: { size: 9 } });
          var ann = layout.annotations[annIdx];
          layout.annotations[annIdx] = Object.assign({}, ann,
            { x: 1, xanchor: "right", y: ty, yanchor: "top", align: "left",
              text: (ann.text || "").split("<br>").map(function (s) { return wrapTitle(s, 26); }).join("<br>"),
              font: Object.assign({}, ann.font, { size: 8.5 }) });
        } else {
          layout.margin = {
            l: keepH ? 122 : 56,
            r: rightAxis ? (layout.yaxis3 ? 58 : 46) : 22,
            t: 34 + titleLines * 22,
            b: (keepH ? 104 : 84) + legRows * 34,
          };
          // Legend below the plot — a PIXEL offset (not a fraction of the plot height, which
          // would drop it far below on tall ranked lists like the dumbbell) — with enough gap to
          // clear the x-axis title.
          var ly = -Math.min(0.30, 94 / layout.height);
          if (hasL) layout.legend = Object.assign({}, layout.legend,
            { orientation: "h", x: 0.5, xanchor: "center", y: ly, yanchor: "top", font: { size: 10 } });
          if (hasL2) layout.legend2 = Object.assign({}, layout.legend2,
            { orientation: "h", x: 0.5, xanchor: "center", y: ly - 44 / layout.height, yanchor: "top", font: { size: 10 } });
          if (hasL3) layout.legend3 = Object.assign({}, layout.legend3,
            { orientation: "h", x: 0.5, xanchor: "center", y: ly - 88 / layout.height, yanchor: "top", font: { size: 10 } });
          if (annIdx >= 0) {
            layout.annotations[annIdx] = Object.assign({}, layout.annotations[annIdx],
              { x: 0.0, xanchor: "left", y: ly - (legRows + 1) * 44 / layout.height, yanchor: "top",
                align: "left", font: Object.assign({}, layout.annotations[annIdx].font, { size: 9.5 }) });
            layout.margin.b += 52; if (!stacked && !keepH) layout.height += 44;
          }
        }
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
      var whole = function (x) { return Math.round(x == null ? 0 : x).toLocaleString(); };
      function pct(part, total) {                 // " (N%)" of total; "<1%" when it rounds to 0
        if (!total) return "";
        var p = 100 * (part || 0) / total;
        return " (" + (p > 0 && p < 0.5 ? "<1%" : Math.round(p) + "%") + ")";
      }
      set("stAnalysed", whole(s.analysed) + pct(s.analysed, s.total_processed));  // % of the real archive total
      set("stCW", whole(s.confidently_wrong) + pct(s.confidently_wrong, s.analysed));
      set("stNW", whole(s.novel_and_wrong) + pct(s.novel_and_wrong, s.analysed));
      set("stDb", (s.db_mb != null ? whole(s.db_mb) + " MB" : "—"));
      set("stVis", whole(s.unique_visitors));
    }).catch(function () {});
  }

  // ---- Grouped worst-offenders table: collapsible groups + filter ----
  function initLeaderboardGroups() {
    var table = document.getElementById("lbTable");
    if (!table) return;

    function membersOf(uni) {
      return table.querySelectorAll('tr.lb-member[data-parent="' + (window.CSS && CSS.escape ? CSS.escape(uni) : uni) + '"]');
    }
    function setOpen(group, open) {
      var uni = group.querySelector(".lb-uni") ? group.getAttribute("data-key") : null;
      group.setAttribute("aria-expanded", open ? "true" : "false");
      // members are the following sibling rows until the next .lb-group
      var tr = group.nextElementSibling;
      while (tr && !tr.classList.contains("lb-group")) {
        if (tr.classList.contains("lb-member")) { if (open) tr.removeAttribute("hidden"); else tr.setAttribute("hidden", ""); }
        tr = tr.nextElementSibling;
      }
    }
    table.querySelectorAll("tr.lb-group").forEach(function (g) {
      g.addEventListener("click", function () { setOpen(g, g.getAttribute("aria-expanded") !== "true"); });
      g.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(g, g.getAttribute("aria-expanded") !== "true"); }
      });
    });

    var expandAll = document.getElementById("lbExpandAll"), allOpen = false;
    if (expandAll) expandAll.addEventListener("click", function () {
      allOpen = !allOpen;
      table.querySelectorAll("tr.lb-group").forEach(function (g) { setOpen(g, allOpen); });
      expandAll.textContent = allOpen ? "Collapse all" : "Expand all";
    });

    var search = document.getElementById("lbSearch");
    if (search) search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase();
      table.querySelectorAll("tr.lb-group").forEach(function (g) {
        var hit = !q || (g.getAttribute("data-key") || "").indexOf(q) !== -1;
        g.style.display = hit ? "" : "none";
        var tr = g.nextElementSibling;
        while (tr && !tr.classList.contains("lb-group")) {
          if (tr.classList.contains("lb-member")) tr.style.display = hit ? "" : "none";
          tr = tr.nextElementSibling;
        }
      });
    });
  }

  function initExampleArchive() {
    var list = document.getElementById("arcList");
    if (!list) return;
    var search = document.getElementById("arcSearch"),
        empty = document.getElementById("arcEmpty"),
        toggle = document.getElementById("arcToggle"),
        rows = Array.prototype.slice.call(list.querySelectorAll(".arcrow")),
        N = parseInt(list.getAttribute("data-visible"), 10) || 6,
        expanded = false;

    function apply() {
      var q = search ? search.value.trim().toLowerCase() : "",
          searching = !!q, shown = 0;
      rows.forEach(function (r, i) {
        var match = !q || (r.getAttribute("data-key") || "").indexOf(q) !== -1;
        // While searching, matches override the collapse; otherwise show the first N (or all).
        var vis = searching ? match : (expanded || i < N);
        r.style.display = vis ? "block" : "none";
        if (vis) shown++;
      });
      if (empty) empty.hidden = !(searching && shown === 0);
      if (toggle) {
        toggle.style.display = searching ? "none" : "";   // during search, all matches already show
        toggle.textContent = expanded ? "Show fewer ▴" : ("Show all " + rows.length + " weeks ▾");
      }
    }

    if (toggle) toggle.addEventListener("click", function () {
      expanded = !expanded;
      apply();
      if (!expanded) toggle.scrollIntoView({ block: "nearest" });
    });
    if (search) search.addEventListener("input", apply);
    apply();
  }

  function initWeekTable() {
    var table = document.getElementById("archiveTable"),
        toggle = document.getElementById("wkToggle");
    if (!table || !toggle) return;
    var extra = table.querySelectorAll("tr.wk-extra"),
        label = toggle.textContent, expanded = false;
    toggle.addEventListener("click", function () {
      expanded = !expanded;
      extra.forEach(function (r) { r.hidden = !expanded; });
      toggle.textContent = expanded ? "Show fewer ▴" : label;
      if (!expanded) toggle.scrollIntoView({ block: "nearest" });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderPlots();
    document.querySelectorAll("table.sortable").forEach(initTable);
    initFilters();
    initLeaderboardGroups();
    initExampleArchive();
    initWeekTable();
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

/* ---- Enhanced multi-structure viewer for the Examples tab (style/colour/ghost/spin tools) ---- */
(function () {
  var loaded = false, loading = false;
  function devColor(b) {
    if (b < 0) return 0x9aa7b3;
    var d = Math.max(0, Math.min(b, 10));
    var s = [[0,[30,115,190]],[1,[74,159,212]],[2,[120,190,180]],[3,[252,185,0]],[6,[232,89,12]],[10,[200,30,30]]];
    for (var i = 0; i < s.length - 1; i++) { var a = s[i], c = s[i + 1];
      if (d <= c[0]) { var t = c[0] === a[0] ? 0 : (d - a[0]) / (c[0] - a[0]);
        return (Math.round(a[1][0]+(c[1][0]-a[1][0])*t)<<16)|(Math.round(a[1][1]+(c[1][1]-a[1][1])*t)<<8)|Math.round(a[1][2]+(c[1][2]-a[1][2])*t); } }
    return 0xc81e1e;
  }
  function load3Dmol(cb) {
    if (loaded && window.$3Dmol) { cb(); return; }
    if (loading) { setTimeout(function () { load3Dmol(cb); }, 150); return; }
    loading = true;
    var s = document.createElement("script"); s.src = "/static/3Dmol-min.js";
    s.onload = function () { loaded = true; cb(); }; document.head.appendChild(s);
  }
  function applySS(model, pdb) {
    var map = {};
    pdb.split("\n").forEach(function (line) {
      if (line.lastIndexOf("HELIX", 0) === 0) { for (var i = parseInt(line.substring(21,25),10); i <= parseInt(line.substring(33,37),10); i++) map[i] = "h"; }
      else if (line.lastIndexOf("SHEET", 0) === 0) { for (var j = parseInt(line.substring(22,26),10); j <= parseInt(line.substring(33,37),10); j++) map[j] = "s"; }
    });
    model.selectedAtoms({}).forEach(function (a) { a.ss = map[a.resi] || "c"; });
  }
  var GHOST = { cartoon: { color: 0x2563eb, style: "trace", thickness: 0.9 } };
  var STYLES = ["cartoon", "stick", "sphere", "surface"], COLORS = ["deviation", "spectrum", "chain", "sstruc"];
  var SLAB = { cartoon: "Cartoon", stick: "Sticks", sphere: "Spheres", surface: "Surface" };
  var CLAB = { deviation: "Cα deviation", spectrum: "Rainbow N→C", chain: "By chain", sstruc: "By 2° structure" };
  function colorSpec(c) {
    if (c === "deviation") return { colorfunc: devColor };
    if (c === "spectrum") return { color: "spectrum" };
    if (c === "chain") return { colorscheme: "chainHetatm" };
    return { colorscheme: "ssPyMOL" };
  }
  function applyStyle(v, model, si, ci) {
    v.removeAllSurfaces(); var cs = colorSpec(COLORS[ci]), st = STYLES[si];
    if (st === "cartoon") model.setStyle({}, { cartoon: Object.assign({ arrows: true }, cs) });
    else if (st === "stick") model.setStyle({}, { stick: Object.assign({ radius: 0.16 }, cs) });
    else if (st === "sphere") model.setStyle({}, { sphere: Object.assign({ scale: 0.28 }, cs) });
    else { model.setStyle({}, { cartoon: Object.assign({}, cs) }); try { v.addSurface($3Dmol.SurfaceType.VDW, Object.assign({ opacity: 0.65 }, cs), {}); } catch (e) {} }
    v.render();
  }
  function initViewer(root) {
    var canvas = root.querySelector(".exv-canvas"), img = root.querySelector(".exv-ribbon"),
        tools = root.querySelector(".exv-tools"), launch = root.querySelector(".exv-launch"),
        coordsUrl = root.getAttribute("data-coords"), ghostUrl = root.getAttribute("data-ghost");
    var viewer = null, model = null, ghost = null, ghostOn = false, spin = false, si = 0, ci = 0;
    function relabel() {
      var b1 = root.querySelector('[data-act="style"]'), b2 = root.querySelector('[data-act="color"]');
      if (b1) b1.textContent = "🎨 " + SLAB[STYLES[si]]; if (b2) b2.textContent = "🌈 " + CLAB[COLORS[ci]];
    }
    if (!coordsUrl) { if (launch) launch.style.display = "none"; return; }
    launch.addEventListener("click", function () {
      launch.textContent = "loading…";
      load3Dmol(function () {
        fetch(coordsUrl).then(function (r) { return r.text(); }).then(function (pdb) {
          if (img) img.style.display = "none"; canvas.style.display = "block"; tools.style.display = "flex"; launch.style.display = "none";
          viewer = $3Dmol.createViewer(canvas, { backgroundAlpha: 0 });
          model = viewer.addModel(pdb, "pdb"); applySS(model, pdb);
          applyStyle(viewer, model, si, ci); relabel(); viewer.zoomTo(); viewer.render();
        }).catch(function () { launch.textContent = "could not load coordinates"; });
      });
    });
    tools.addEventListener("click", function (e) {
      var btn = e.target.closest("button"); if (!btn || !viewer) return;
      var act = btn.getAttribute("data-act");
      if (act === "style") { si = (si + 1) % STYLES.length; applyStyle(viewer, model, si, ci); relabel(); }
      else if (act === "color") { ci = (ci + 1) % COLORS.length; applyStyle(viewer, model, si, ci); relabel(); }
      else if (act === "spin") { spin = !spin; viewer.spin(spin ? "y" : false, 0.6); btn.classList.toggle("on", spin); }
      else if (act === "reset") { viewer.zoomTo(); viewer.render(); }
      else if (act === "ghost") {
        if (ghost) { ghostOn = !ghostOn; ghost.setStyle({}, ghostOn ? GHOST : {}); viewer.render(); btn.classList.toggle("on", ghostOn); }
        else if (ghostUrl) { btn.textContent = "loading…"; fetch(ghostUrl).then(function (r) { return r.text(); }).then(function (g) {
          ghost = viewer.addModel(g, "pdb"); ghost.setStyle({}, GHOST); ghostOn = true; viewer.render(); btn.textContent = "👻 AF ghost"; btn.classList.add("on"); }); }
      }
    });
  }
  // Expose so dynamically-injected panels (the Calculate tab) can wire up their viewers.
  window.initExampleViewers = function (scope) {
    (scope || document).querySelectorAll(".exviewer").forEach(initViewer);
  };
  document.addEventListener("DOMContentLoaded", function () { document.querySelectorAll(".exviewer").forEach(initViewer); });
})();

/* ---- Calculate tab: autocomplete + on-demand compute ---- */
(function () {
  var input = document.getElementById("calcInput");
  if (!input) return;
  var go = document.getElementById("calcGo"),
      list = document.getElementById("calcSuggest"),
      msg = document.getElementById("calcMsg"),
      result = document.getElementById("calcResult"),
      items = [], active = -1, timer = null, poll = null;

  function show(text, kind) {
    msg.textContent = text;
    msg.className = "calc-msg" + (kind ? " " + kind : "");
    msg.hidden = !text;
  }
  function hideList() { list.hidden = true; list.innerHTML = ""; items = []; active = -1; }

  function render() {
    list.innerHTML = "";
    items.forEach(function (it, i) {
      var li = document.createElement("li");
      li.className = "calc-sug" + (i === active ? " on" : "");
      li.setAttribute("role", "option");
      li.innerHTML = '<b>' + it.entry_id + '</b> <span class="calc-sug-t">' +
        ((it.gene || "").replace("_HUMAN", "") + (it.title ? " · " + it.title : "")) + '</span>' +
        (it.post_cutoff ? '' : ' <span class="calc-sug-pre">pre-cutoff</span>');
      li.addEventListener("mousedown", function (e) { e.preventDefault(); choose(it); });
      list.appendChild(li);
    });
    list.hidden = items.length === 0;
  }
  function choose(it) { input.value = it.entry_id; hideList(); run(); }

  function fetchSuggest() {
    var q = input.value.trim();
    if (q.length < 1) { hideList(); return; }
    fetch("/api/calculate/suggest?q=" + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (rows) { items = rows || []; active = items.length ? 0 : -1; render(); })
      .catch(function () { hideList(); });
  }

  input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(fetchSuggest, 140); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown" && items.length) { e.preventDefault(); active = (active + 1) % items.length; render(); }
    else if (e.key === "ArrowUp" && items.length) { e.preventDefault(); active = (active - 1 + items.length) % items.length; render(); }
    else if (e.key === "Tab" && items.length && active >= 0) { e.preventDefault(); input.value = items[active].entry_id; hideList(); }
    else if (e.key === "Enter") { e.preventDefault(); if (!list.hidden && active >= 0) choose(items[active]); else run(); }
    else if (e.key === "Escape") { hideList(); }
  });
  document.addEventListener("click", function (e) { if (!list.contains(e.target) && e.target !== input) hideList(); });
  go.addEventListener("click", run);

  function run() {
    var pdb = input.value.trim();
    if (!pdb) return;
    hideList();
    if (poll) { clearInterval(poll); poll = null; }
    result.innerHTML = "";
    show("Checking " + pdb.toUpperCase() + " …", "info");
    fetch("/calculate/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pdb: pdb })
    }).then(function (r) { return r.json(); }).then(handle)
      .catch(function () { show("Something went wrong contacting the server.", "err"); });
  }

  function handle(res) {
    if (res.status === "error") { show(res.reason || "This entry does not meet the criteria.", "err"); return; }
    if (res.status === "busy") { show(res.reason, "warn"); return; }
    if (res.status === "ready") { loadPanel(res.entity_id); return; }
    if (res.status === "computing") {
      show("Computing " + res.entity_id + " — fetching the AlphaFold model, superposing and scoring. This can take up to a minute…", "info");
      startPoll(res.entity_id);
    }
  }
  function startPoll(eid) {
    var tries = 0;
    poll = setInterval(function () {
      tries++;
      fetch("/api/calculate/status/" + encodeURIComponent(eid))
        .then(function (r) { return r.json(); })
        .then(function (s) {
          if (s.status === "ready") { clearInterval(poll); poll = null; loadPanel(eid); }
          else if (s.status === "error") { clearInterval(poll); poll = null; show(s.reason || "Could not process this structure.", "err"); }
          else if (tries > 60) { clearInterval(poll); poll = null; show("Still working — this structure is taking unusually long. Try again shortly.", "warn"); }
        });
    }, 2000);
  }
  function loadPanel(eid) {
    show("", null);
    fetch("/calculate/panel/" + encodeURIComponent(eid))
      .then(function (r) { return r.text(); })
      .then(function (html) {
        result.innerHTML = html;
        if (window.initExampleViewers) window.initExampleViewers(result);
        result.scrollIntoView({ behavior: "smooth", block: "start" });
      })
      .catch(function () { show("Computed, but the panel failed to load. Refresh and try again.", "err"); });
  }
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

  // Points whose customdata[0] looks like "8G2V_1" carry an entity id we can act on.
  function eidOf(d) {
    var pt = d && d.points && d.points[0];
    if (!pt || !pt.customdata || !pt.customdata[0]) return null;
    var eid = String(pt.customdata[0]);
    return /^[0-9A-Za-z]{4}_/.test(eid) ? eid : null;
  }

  function isExamplePoint(d) {
    var p = d && d.points && d.points[0];
    return !!(p && p.data && p.data.meta && p.data.meta.example);
  }

  window.wireScatterPreview = function (el) {
    if (!el || el._ribbonHoverWired || !el.on) return;
    // Any plot whose points carry an entity_id in customdata[0] (fraud scatter, dumbbell).
    el._ribbonHoverWired = true;
    el.on("plotly_hover", function (d) {
      el._pulsePaused = true;                          // freeze the star pulse so its tooltip is stable
      var eid = eidOf(d);
      if (!eid) return;
      el.style.cursor = "pointer";                   // signal the point is clickable
      ensureBox();
      box._cap.textContent = eid + "  ·  Cα deviation";
      img.src = "/ribbon/" + encodeURIComponent(eid) + ".svg";
      var ev = d.event || window.event;
      var x = (ev.clientX || 0) + 16, y = (ev.clientY || 0) + 16;
      x = Math.min(x, window.innerWidth - 210);
      y = Math.min(y, window.innerHeight - 200);
      box.style.left = x + "px"; box.style.top = y + "px";
    });
    el.on("plotly_unhover", function () { el._pulsePaused = false; el.style.cursor = ""; hide(); });
    // Click a curated deep-dive example → jump to its Examples-tab panel; any other point → entry.
    // Route by entity id (built into el._exLinks) so it works no matter which trace resolves.
    el.on("plotly_click", function (d) {
      var eid = eidOf(d);
      if (eid && el._exLinks && el._exLinks[eid]) { window.location.href = el._exLinks[eid]; return; }
      if (isExamplePoint(d) && d.points[0].customdata && d.points[0].customdata[2]) {
        window.location.href = d.points[0].customdata[2]; return;
      }
      if (eid) window.location.href = "/entry/" + encodeURIComponent(eid);
    });
    startExamplePulse(el);
  };

  // Pulse + grow the deep-dive example markers so they catch the eye (all users, always).
  function startExamplePulse(el) {
    if (!window.Plotly || el._exPulse) return;
    var idx = -1;
    (el.data || []).forEach(function (t, i) { if (t.meta && t.meta.example) idx = i; });
    if (idx < 0) return;
    // Map entity id -> Examples-tab link so clicks route correctly regardless of trace hit.
    el._exLinks = {};
    ((el.data[idx] && el.data[idx].customdata) || []).forEach(function (row) {
      if (row && row[0] && row[2]) el._exLinks[row[0]] = row[2];
    });
    var t0 = Date.now();
    el._exPulse = setInterval(function () {
      if (!document.body.contains(el)) { clearInterval(el._exPulse); el._exPulse = null; return; }
      if (el._pulsePaused) return;                     // hold steady while the user hovers
      var s = 18 + 6 * Math.sin((Date.now() - t0) / 300);   // grows ~12..24 px
      try { Plotly.restyle(el, { "marker.size": s }, [idx]); } catch (e) { /* mid-react */ }
    }, 80);
  }
})();
