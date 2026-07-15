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

import json
import os
from datetime import date

from flask import Flask, abort, jsonify, render_template, url_for

from . import __version__, banner, db, report

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
    db.init_schema()

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
        return {"asset": asset}

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
        rows = db.leaderboard(limit=200)
        return render_template("leaderboard.html", banner=banner.BANNER_ART,
                               entities=rows, stats=db.overall_stats(), version=__version__)

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


def _render_all():
    """The default landing page: cumulative view across every processed week."""
    rows = db.all_entities_scalar()          # all analysed entities, worst-FRAUD first
    weekly = db.weekly_aggregates()
    figures = {
        "scatter": report.fraud_scatter(rows),
        "histograms": report.metric_histograms(rows),
        "trend": report.trend_figure(weekly) if len(weekly) > 1 else None,
    }
    return render_template(
        "week.html",
        banner=banner.BANNER_ART,
        label="All",
        is_all=True,
        today=date.today().isoformat(),
        total_count=len(rows),
        table_cap=TABLE_CAP,
        entities=rows[:TABLE_CAP],
        kpis=report.kpis(rows),
        figures=figures,
        weeks=db.list_weeks(),
        version=__version__,
    )


def _render_week(label):
    entities = db.entities_for_week(label)
    weeks = db.list_weeks()
    if not any(w["label"] == label for w in weeks):
        abort(404)
    weekly = db.weekly_aggregates()
    figures = {
        "scatter": report.fraud_scatter(entities),
        "histograms": report.metric_histograms(entities),
        "trend": report.trend_figure(weekly) if len(weekly) > 1 else None,
    }
    return render_template(
        "week.html",
        banner=banner.BANNER_ART,
        label=label,
        is_all=False,
        entities=entities,
        kpis=report.kpis(entities),
        figures=figures,
        weeks=weeks,
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
