// AlphaFraud front-end: theme toggle, Plotly rendering, client-side table sort/filter.
(function () {
  "use strict";

  // Theme follows the viewer's OS setting via CSS @media (prefers-color-scheme); there is
  // no manual switcher.

  // ---- Plotly ----
  // Set the width explicitly from the container. autosize/responsive proved unreliable on
  // narrow (mobile) widths -- Plotly kept a desktop width and overflowed the viewport -- so
  // we pin layout.width to the element's own width and re-render on resize.
  function renderPlots() {
    if (typeof Plotly === "undefined") return;
    document.querySelectorAll("script[data-target]").forEach(function (s) {
      var el = document.getElementById(s.getAttribute("data-target"));
      if (!el) return;
      var fig;
      try { fig = JSON.parse(s.textContent); } catch (e) { return; }
      var layout = fig.layout || {};
      // Cap width to the viewport (minus the wrap+card horizontal padding, ~72px). Once a
      // plot has overshot the viewport the page itself is over-wide, so el.clientWidth reads
      // too large -- the viewport is the only stable reference for the ceiling.
      var vw = document.documentElement.clientWidth || window.innerWidth || 360;
      var w = Math.min(el.clientWidth || vw, vw - 72);
      layout.width = w;
      layout.autosize = false;
      Plotly.react(el, fig.data, layout, { displayModeBar: false, responsive: false });
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

  document.addEventListener("DOMContentLoaded", function () {
    renderPlots();
    document.querySelectorAll("table.sortable").forEach(initTable);
    initFilters();
  });
})();
