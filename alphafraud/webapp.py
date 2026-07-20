"""Flask app: serves the AlphaFraud results live from SQLite. Production runs under
gunicorn (see wsgi.py + deploy/); `AlphaFraud.py serve` runs the same app for local dev.

Routes:
    /                     latest week
    /week/<label>         a specific release week
    /archive              index of all weeks
    /entry/<entity_id>    per-structure detail (heatmaps, domains, all metrics)
    /leaderboard          all-time worst AlphaFold failures
    /api/week/<label>     JSON
    /api/leaderboard      JSON
    /api/entry/<id>       JSON
    /healthz              liveness probe for systemd/nginx
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, timedelta

from flask import Flask, abort, jsonify, render_template, request, send_from_directory, url_for

from . import __version__, banner, config, db, report, ribbon

# User-agents we do NOT count as human visitors (crawlers, scanners, HTTP libraries, headless).
_BOT_UA = re.compile(
    r"bot|crawl|spider|slurp|scan|http-client|python-requests|curl|wget|libredtail|websiphon|"
    r"semrush|ahrefs|bytespider|facebookexternalhit|headless|okhttp|dataprovider|censys|masscan|"
    r"zgrab|nuclei|petalbot|amazonbot|go-http|infrawat|cyberconvoy|internet-?measurement|libwww|"
    r"aiohttp|perl|paloalto|palo alto|cortex|visionheight|flowiq|genomecrawler|nokia|"
    r"claude-user|claude-code|python/|\(cow\)", re.I)

# Metric groups drive the tidy tables on the entry page (label -> metric keys).
METRIC_GROUPS = [
    ("Global fold agreement", [
        ("tm_by_experiment", "TM-score (norm. experiment)"),
        ("tm_by_model", "TM-score (norm. model)"),
        ("tm_by_shorter", "TM-score (norm. shorter)"),
        ("tm_by_longer", "TM-score (norm. longer)"),
        ("ca_rmsd", "Cα-RMSD (Å)"),
        ("backbone_rmsd", "backbone-RMSD (Å)"),
        ("all_atom_rmsd", "all-atom-RMSD (Å)"),
        ("core_rmsd", "core-RMSD (Å)"),
        ("core_fraction", "core fraction"),
        ("gdt_ts", "GDT_TS"),
        ("gdt_ha", "GDT_HA"),
        ("maxsub", "MaxSub"),
        ("structural_overlap_3_5", "structural overlap (3.5 Å)"),
    ]),
    ("Local, superposition-free", [
        ("lddt", "lDDT"),
        ("contact_jaccard", "contact-map Jaccard"),
        ("contact_precision", "contact precision"),
        ("contact_recall", "contact recall"),
        ("distance_matrix_mean_diff", "distance-matrix mean Δ (Å)"),
        ("cad_score", "CAD-score (approx)"),
    ]),
    ("Backbone & secondary structure", [
        ("ss_agreement_q3", "SS agreement Q3 (%)"),
        ("mean_phi_diff_deg", "mean Δφ (°)"),
        ("mean_psi_diff_deg", "mean Δψ (°)"),
        ("torsion_within_30deg_frac", "torsion within 30° (frac)"),
        ("radius_of_gyration_exp", "Rg experiment (Å)"),
        ("radius_of_gyration_model", "Rg model (Å)"),
        ("radius_of_gyration_diff", "ΔRg (Å)"),
    ]),
    ("Confidence calibration", [
        ("mean_plddt", "mean pLDDT"),
        ("plddt_lddt_pearson", "pLDDT↔lDDT Pearson"),
        ("plddt_lddt_spearman", "pLDDT↔lDDT Spearman"),
        ("pae_observed_pearson", "PAE↔observed Pearson"),
        ("pae_overconfident_frac", "PAE overconfident frac"),
        ("mean_pae", "mean PAE (Å)"),
        ("mean_observed_error", "mean observed error (Å)"),
    ]),
    ("Context & headline", [
        ("coverage_of_model", "coverage of model"),
        ("coverage_of_experiment", "coverage of experiment"),
        ("sequence_identity_aligned", "seq identity aligned (%)"),
        ("confidently_wrong_frac", "confidently-wrong residue frac"),
        ("fraud_score", "FRAUD score"),
    ]),
]


def create_app() -> Flask:
    app = Flask(__name__)
    # The web app is a pure reader -- it does NOT init the schema (that would be a write on
    # every gunicorn restart, contending with a running backfill). The schema is created by
    # `AlphaFraud.py init` (provisioning) and by every pipeline run.

    def _human_visitor_id():
        # A hashed client IP, but ONLY for requests that look human. A public server is hammered
        # by crawlers and vulnerability scanners (Amazonbot alone: >1300 hits/day), many of which
        # either use an unfamiliar UA or spoof a real browser hitting `/` once -- indistinguishable
        # from a person by user-agent alone. So the real filter is applied at the CALL SITE: we only
        # record a visitor from /api/stats, which the page's JavaScript fetches on load. Blind
        # scanners GET a page and leave without executing JS, so they never reach it. This is a
        # proof-of-JS-execution gate; the UA blocklist below just strips the JS-capable bots.
        ua = request.headers.get("User-Agent", "")
        if not ua or _BOT_UA.search(ua):
            return None
        ip = (request.headers.get("X-Real-IP")
              or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
              or request.remote_addr or "")
        if not ip:
            return None
        return hashlib.sha256(("af:" + ip).encode()).hexdigest()[:16]

    @app.route("/api/stats")
    def api_stats():
        # Recording the visit here (not on the page route) is the human gate -- see _human_visitor_id.
        vid = _human_visitor_id()
        if vid:
            try:
                db.record_visit(vid)
            except Exception:
                pass
        rss_mb = None
        try:                                   # this worker's resident memory (Linux)
            with open("/proc/self/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        rss_mb = round(int(line.split()[1]) / 1024, 1)
                        break
        except Exception:
            pass
        vs = db.visitor_stats()
        st = db.overall_stats()
        analysed = st.get("n") or 0
        total = db.total_entity_count()      # real archive size, now the backfill is complete
        return jsonify({
            "memory_mb": rss_mb,
            "db_mb": round(db.db_size_bytes() / 1048576, 1),
            "analysed": analysed,
            "total_processed": total,
            "confidently_wrong": st.get("cw") or 0,
            "novel_and_wrong": st.get("novel_wrong") or 0,
            "archive_pct": round(100 * analysed / total, 1) if total else 0,
            "unique_visitors": vs["unique"],
            "page_views": vs["hits"],
            "visitors_today": vs["today"],
        })

    @app.context_processor
    def _asset_helper():
        # Append the file's mtime as ?v= so a redeploy busts the browser cache even though
        # nginx serves /static/ with a 7-day expiry (query string changes -> fresh fetch).
        def asset(filename):
            try:
                v = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
            except OSError:
                v = 0
            return url_for("static", filename=filename, v=v)

        def ribbon_url(entity_id):
            # URL of the deviation-coloured Cα ribbon SVG, or None if not yet rendered. The
            # ?v=mtime busts the browser cache whenever the SVG is regenerated (the file changes
            # but its path doesn't), so redeploys/re-renders show up immediately.
            if not ribbon.has_ribbon(entity_id):
                return None
            try:
                v = int(ribbon.ribbon_path(entity_id).stat().st_mtime)
            except OSError:
                v = 0
            return url_for("ribbon_svg", entity_id=entity_id, v=v)

        def coords_url(entity_id):
            # URL of the backbone PDB for the interactive 3D viewer, or None if absent.
            return url_for("ribbon_coords", entity_id=entity_id) if ribbon.has_coords(entity_id) else None

        def ghost_url(entity_id):
            # URL of the AlphaFold-model ghost PDB (superposed frame), or None if absent.
            return url_for("ribbon_ghost", entity_id=entity_id) if ribbon.has_ghost(entity_id) else None

        def nov(identity):
            # Displayed "novelty" = 100 - (max % identity to any pre-cutoff chain), so 100% = a
            # sequence unlike anything AlphaFold saw, 0% = an identical training sequence. The
            # stored value stays as raw identity; this flips it for display only.
            return None if identity is None else round(100 - identity, 1)

        # The next weekly PDB release the app will process: the PDB updates Wednesday 00:00 UTC
        # (our run fires shortly after), so this is the next upcoming Wednesday.
        today = date.today()
        days = (2 - today.weekday()) % 7 or 7          # Wednesday == 2; if today is Wed, next week
        next_update = (today + timedelta(days=days)).strftime("%a %d %b")

        return {"asset": asset, "ribbon_url": ribbon_url, "coords_url": coords_url,
                "ghost_url": ghost_url, "nov": nov, "next_pdb_update": next_update}

    @app.route("/ribbon/<entity_id>.svg")
    def ribbon_svg(entity_id):
        if not ribbon.has_ribbon(entity_id):
            abort(404)
        resp = send_from_directory(config.RIBBON_DIR, f"{entity_id}.svg",
                                   mimetype="image/svg+xml")
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    @app.route("/coords/<entity_id>.pdb")
    def ribbon_coords(entity_id):
        if not ribbon.has_coords(entity_id):
            abort(404)
        resp = send_from_directory(config.RIBBON_DIR, f"{entity_id}.pdb",
                                   mimetype="chemical/x-pdb")
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    @app.route("/ghost/<entity_id>.pdb")
    def ribbon_ghost(entity_id):
        if not ribbon.has_ghost(entity_id):
            abort(404)
        resp = send_from_directory(config.RIBBON_DIR, f"{entity_id}.af.pdb",
                                   mimetype="chemical/x-pdb")
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    @app.after_request
    def _page_cache(resp):
        # Asset routes (ribbon/coords/ghost) set their own long immutable headers; /static is
        # cached by nginx. For the dynamic HTML pages add a short public cache so repeat
        # navigation is instant — the underlying data only changes on a weekly run. Never cache
        # the live JSON/health endpoints (stats panel polls /api/stats).
        if (request.method == "GET" and resp.status_code == 200
                and resp.cache_control.max_age is None
                and not request.path.startswith("/api/") and request.path != "/healthz"):
            resp.headers["Cache-Control"] = "public, max-age=120"
        return resp

    @app.route("/")
    def index():
        if not db.latest_run_label():
            return render_template("empty.html", banner=banner.BANNER_ART, version=__version__)
        return _render_all()

    @app.route("/week/<label>")
    def week(label):
        return _render_week(label)

    @app.route("/archive")
    def archive():
        return render_template("archive.html", banner=banner.BANNER_ART,
                               weeks=db.list_weeks(), version=__version__)

    @app.route("/leaderboard")
    def leaderboard():
        groups = db.leaderboard_grouped(max_proteins=80)
        stats = db.overall_stats()
        stats["median_tm"] = db.median_tm()      # match the home-page KPI (median, not mean)
        return render_template("leaderboard.html", banner=banner.BANNER_ART,
                               groups=groups, stats=stats, version=__version__)

    @app.route("/analysis")
    def analysis():
        snap = db.load_snapshot("cumulative")
        figures = {}
        if snap:
            figures = {
                "enrich_class": report.analysis_enrichment(
                    snap.get("enrichment_cath_class") or [], "AlphaFold blind spots by CATH class"),
                "enrich_scop2": report.analysis_enrichment(
                    snap.get("enrichment_scop2") or [], "AlphaFold blind spots by SCOP2 superfamily"),
                "cath_folds": report.analysis_cath_folds(snap.get("cath_folds") or {}),
                "themes": report.analysis_themes(snap.get("themes") or {}),
                "clusters": report.analysis_cluster_heatmap(snap.get("clusters") or {}),
                "embedding": report.analysis_embedding(snap.get("embedding") or {}),
                "correlates": report.analysis_correlates(snap.get("correlates") or {}),
            }
        return render_template("analysis.html", banner=banner.BANNER_ART, snap=snap,
                               figures=figures, version=__version__)

    @app.route("/api/analysis")
    def api_analysis():
        return jsonify(db.load_snapshot("cumulative") or {})

    @app.route("/entry/<entity_id>")
    def entry(entity_id):
        e = db.get_entity(entity_id)
        if not e:
            abort(404)
        return _render_entry(e)

    # ---- JSON API ----
    @app.route("/api/week/<label>")
    def api_week(label):
        return jsonify(db.entities_for_week(label))

    @app.route("/api/leaderboard")
    def api_leaderboard():
        return jsonify(db.leaderboard(limit=500))

    @app.route("/api/entry/<entity_id>")
    def api_entry(entity_id):
        e = db.get_entity(entity_id)
        return (jsonify(e), 200) if e else ("", 404)

    @app.route("/healthz")
    def healthz():
        return {"status": "ok", "version": __version__, "latest_week": db.latest_run_label()}

    return app


TABLE_CAP = 500   # rows shown in the cumulative "All" table (the rest live in weeks/leaderboard)


HOME_CACHE_TTL = 1800   # seconds; the cumulative view recomputes at most this often


def _snapshot_fresh(updated_at: Optional[str], ttl: int) -> bool:
    if not updated_at:
        return False
    try:
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(updated_at)).total_seconds()
        return 0 <= age < ttl
    except Exception:
        return False


def _render_all():
    """The default landing page: cumulative view across every processed week.

    Building the whole-archive figures (scatter/dumbbell/histograms over ~80k rows) is the one
    slow step, so the assembled payload is cached in analysis_snapshots and reused for up to
    HOME_CACHE_TTL. The underlying data only changes on a weekly run / backfill, so a stale
    window of minutes is harmless and one visitor per interval absorbs the recompute."""
    payload = db.load_snapshot("home")
    if not (payload and _snapshot_fresh(payload.get("_updated_at"), HOME_CACHE_TTL)):
        rows = db.all_entities_scalar()      # all analysed entities, worst-FRAUD first
        weekly = db.deposit_month_trend()
        payload = {
            "figures": {
                "scatter": report.fraud_scatter(rows),
                "scatter_zoom": report.fraud_scatter(rows, zoom=True),
                "dumbbell": report.fraud_dumbbell(rows),
                "histograms": report.metric_histograms(rows),
                "trend": report.trend_figure(weekly, cw_trend=db.cw_rate_trend()) if len(weekly) > 1 else None,
            },
            "kpis": report.kpis(rows),
            "scatter_note": report.sampling_note(rows),
            "total_count": len(rows),
            "entities": rows[:TABLE_CAP],
        }
        db.save_snapshot("home", payload)
    return render_template(
        "week.html",
        banner=banner.BANNER_ART,
        label="All",
        is_all=True,
        today=date.today().isoformat(),
        total_count=payload["total_count"],
        table_cap=TABLE_CAP,
        entities=payload["entities"],
        kpis=payload["kpis"],
        figures=payload["figures"],
        scatter_note=payload["scatter_note"],
        weeks=db.dropdown_weeks(8),
        backfill_months=db.list_backfill_months(),
        version=__version__,
    )


def _render_week(label):
    entities = db.entities_for_week(label)
    if not db.week_exists(label):        # any real run (weekly or backfill); 404 only if unknown
        abort(404)
    is_backfill = db.run_kind(label) == "backfill"   # title "Release month" vs "Release week"
    weeks = db.dropdown_weeks(8)         # latest weekly releases, for the "jump to" dropdown
    weekly = db.deposit_month_trend()
    figures = {
        "scatter": report.fraud_scatter(entities),
        "scatter_zoom": report.fraud_scatter(entities, zoom=True),
        "dumbbell": report.fraud_dumbbell(entities),
        "histograms": report.metric_histograms(entities),
        "trend": report.trend_figure(weekly, cw_trend=db.cw_rate_trend()) if len(weekly) > 1 else None,
    }
    highlights = report.week_highlights(entities, seen_uniprots=db.uniprots_before_label(label))
    return render_template(
        "week.html",
        banner=banner.BANNER_ART,
        label=label,
        is_all=False,
        is_backfill=is_backfill,
        entities=entities,
        kpis=report.kpis(entities),
        highlights=highlights,
        figures=figures,
        scatter_note=report.sampling_note(entities),
        weeks=weeks,
        backfill_months=db.list_backfill_months(),
        version=__version__,
    )


def _render_entry(e):
    metrics = json.loads(e["metrics_json"] or "{}")
    per_res = json.loads(e["per_residue_json"] or "{}")
    domains = json.loads(e["domains_json"] or "[]")
    heatmaps = json.loads(e["heatmaps_json"] or "{}")
    figures = {
        "tracks": report.per_residue_tracks(per_res) if per_res.get("ca_deviation") else None,
        "calibration": report.calibration_scatter(per_res) if per_res.get("plddt") else None,
        "distance": report.heatmap(heatmaps["distance_diff"], "Distance-matrix difference |Δ| (Å)")
        if heatmaps.get("distance_diff") else None,
        "pae": report.pae_honesty_pair(heatmaps["pae"], heatmaps["observed"])
        if heatmaps.get("pae") and heatmaps.get("observed") else None,
    }
    return render_template(
        "entry.html",
        banner=banner.BANNER_ART,
        e=e,
        metrics=metrics,
        domains=domains,
        figures=figures,
        metric_groups=METRIC_GROUPS,
        version=__version__,
    )
