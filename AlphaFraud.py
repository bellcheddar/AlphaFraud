#!/usr/bin/env python3
"""AlphaFraud -- watch the PDB for structures AlphaFold predicted blind, and measure where
the prediction disagrees with the experiment.

Usage:
    python3 AlphaFraud.py init                         # dirs, DB schema, vendored plotly.js
    python3 AlphaFraud.py run [--since D] [--until D] [--limit N] [--dry-run]
    python3 AlphaFraud.py backfill --from D --to D     # process a historical window
    python3 AlphaFraud.py status                       # database summary
    python3 AlphaFraud.py serve [--port 8000]          # local dev web server

The weekly production run is driven by a systemd timer on the droplet (see deploy/); the
Flask app (gunicorn) serves the results live from SQLite. `run` with no --since resumes
from the last processed run.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from alphafraud import banner, config


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def cmd_init(_args) -> int:
    from alphafraud import db

    config.ensure_dirs()
    db.init_schema()
    banner.ok(f"Directories ready under {config.ROOT_DIR}")
    banner.ok(f"SQLite schema ready at {config.DB_PATH}")
    _vendor_plotly()
    banner.info("Next: `python3 AlphaFraud.py run --dry-run` to preview discovery.")
    return 0


def _vendor_plotly() -> None:
    if config.VENDOR_PLOTLY.exists() and config.VENDOR_PLOTLY.stat().st_size > 0:
        banner.ok(f"plotly.min.js already vendored ({config.VENDOR_PLOTLY})")
        return
    # Prefer the copy shipped inside the installed plotly package (offline, version-matched).
    try:
        from plotly import offline as _off  # noqa: F401
        import plotly
        from pathlib import Path

        pkg_js = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
        if pkg_js.exists():
            config.STATIC_DIR.mkdir(parents=True, exist_ok=True)
            config.VENDOR_PLOTLY.write_bytes(pkg_js.read_bytes())
            banner.ok(f"Vendored plotly.min.js from the plotly package ({config.VENDOR_PLOTLY})")
            return
    except Exception:
        pass
    # Fallback: download a pinned build.
    from alphafraud.http import download

    url = "https://cdn.plot.ly/plotly-2.35.2.min.js"
    got = download(url, config.VENDOR_PLOTLY)
    if got:
        banner.ok(f"Downloaded plotly.min.js -> {config.VENDOR_PLOTLY}")
    else:
        banner.warn("Could not vendor plotly.min.js; charts will not render until it is present.")


def cmd_run(args) -> int:
    from alphafraud import pipeline

    since = _parse_date(args.since) if args.since else pipeline.default_since()
    until = _parse_date(args.until) if args.until else date.today()
    pipeline.run(since, until, limit=args.limit, dry_run=args.dry_run)
    return 0


def cmd_backfill(args) -> int:
    from alphafraud import pipeline

    if args.all:
        pipeline.backfill_all(tm_threshold=args.tm_threshold, limit_per_chunk=args.limit,
                              workers=args.workers)
        return 0
    if not getattr(args, "from") or not args.to:
        banner.err("backfill needs --from and --to (or --all).")
        return 1
    since, until = _parse_date(getattr(args, "from")), _parse_date(args.to)
    if args.two_tier:
        pipeline.backfill_two_tier(since, until, tm_threshold=args.tm_threshold,
                                   limit=args.limit, workers=args.workers)
    else:
        pipeline.run(since, until, limit=args.limit)
    return 0


def cmd_retry_errors(args) -> int:
    from alphafraud import pipeline

    pipeline.retry_errors(tm_threshold=args.tm_threshold, limit=args.limit)
    return 0


def cmd_render_ribbons(args) -> int:
    from alphafraud import pipeline

    pipeline.render_ribbons(limit=args.limit, min_fraud=args.min_fraud, overwrite=args.overwrite)
    return 0


def cmd_status(_args) -> int:
    from alphafraud import db

    db.init_schema()
    stats = db.overall_stats()
    weeks = db.list_weeks()
    banner.info(f"Weeks processed: {len(weeks)}")
    banner.info(f"Entities compared: {stats.get('n') or 0}")
    banner.info(f"Confidently wrong: {stats.get('cw') or 0}")
    banner.info(f"Novel sequences: {stats.get('novel') or 0}")
    if stats.get("avg_tm") is not None:
        banner.info(f"Mean TM-score: {stats['avg_tm']:.3f}   Mean lDDT: {stats.get('avg_lddt') or 0:.3f}")
    banner.step("Worst offenders:")
    for e in db.leaderboard(limit=10):
        flag = "⚠" if e.get("confidently_wrong") else " "
        print(f"  {flag} {e['entity_id']:9} {e.get('uniprot') or '-':7} "
              f"TM={e.get('tm_by_experiment')}  FRAUD={e.get('fraud_score')}  "
              f"novelty={e.get('novelty_identity')}%  {e.get('description') or ''}")
    return 0


def cmd_analyze(args) -> int:
    from alphafraud import analysis

    analysis.analyze(limit=args.limit)
    return 0


def cmd_weekly_examples(_args) -> int:
    from alphafraud import db

    db.init_schema()
    c = db.rebuild_weekly_examples()
    banner.ok(f"Rebuilt {c['weeks']} release weeks ({c['catches']} confidently-wrong catches).")
    feat = db.latest_weekly_example()
    if feat:
        banner.info(f"Featured (latest catch): {feat['week']}  {feat['entity_id']}  {feat['uniprot']}")
    return 0


def cmd_serve(args) -> int:
    from alphafraud.webapp import create_app

    app = create_app()
    banner.info(f"Serving dev server on http://127.0.0.1:{args.port}  (production uses gunicorn)")
    app.run(host="127.0.0.1", port=args.port, debug=args.debug)
    return 0


def main(argv=None) -> int:
    banner.print_banner()
    parser = argparse.ArgumentParser(prog="AlphaFraud", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="create dirs, DB schema, vendor plotly.js").set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="run the pipeline for a deposit window")
    p_run.add_argument("--since", help="YYYY-MM-DD (default: resume from last run)")
    p_run.add_argument("--until", help="YYYY-MM-DD (default: today)")
    p_run.add_argument("--limit", type=int, help="max entities to process")
    p_run.add_argument("--dry-run", action="store_true", help="discover + map only, write nothing")
    p_run.set_defaults(func=cmd_run)

    p_bf = sub.add_parser("backfill", help="process a historical window")
    p_bf.add_argument("--from", help="YYYY-MM-DD (start of window)")
    p_bf.add_argument("--to", help="YYYY-MM-DD (end of window)")
    p_bf.add_argument("--all", action="store_true",
                      help="two-tier backfill of the entire post-cutoff archive (monthly chunks)")
    p_bf.add_argument("--two-tier", action="store_true",
                      help="TM-score screen everything, full metrics only below --tm-threshold")
    p_bf.add_argument("--tm-threshold", type=float, default=0.7,
                      help="TM-score below which an entity gets the full metric suite (default 0.7)")
    p_bf.add_argument("--limit", type=int, help="max entities (per chunk when --all)")
    p_bf.add_argument("--workers", type=int, default=1,
                      help="parallel download/analysis workers (default 1; try 6 for backfill)")
    p_bf.set_defaults(func=cmd_backfill)

    p_re = sub.add_parser("retry-errors",
                          help="reclassify guard errors → skipped, then re-attempt the real "
                               "failures (fresh mmCIF + model=1). Run only when no backfill is active.")
    p_re.add_argument("--tm-threshold", type=float, default=0.7,
                      help="promote a recovered entity to full metrics below this TM (default 0.7)")
    p_re.add_argument("--limit", type=int, help="max error entities to retry this pass")
    p_re.set_defaults(func=cmd_retry_errors)

    p_rb = sub.add_parser("render-ribbons",
                          help="retro-generate deviation-coloured Cα ribbon SVGs for compared "
                               "entities (worst offenders first). Reads DB, writes only files.")
    p_rb.add_argument("--limit", type=int, help="max ribbons to render this pass")
    p_rb.add_argument("--min-fraud", type=float, default=0.0, help="only entities at/above this FRAUD score")
    p_rb.add_argument("--overwrite", action="store_true", help="re-render even if a ribbon already exists")
    p_rb.set_defaults(func=cmd_render_ribbons)

    sub.add_parser("status", help="database summary + leaderboard").set_defaults(func=cmd_status)

    p_an = sub.add_parser("analyze", help="enrich the compared set + rebuild the Analysis snapshot")
    p_an.add_argument("--limit", type=int, help="max entities to enrich this pass")
    p_an.set_defaults(func=cmd_analyze)

    sub.add_parser("weekly-examples",
                   help="regenerate the auto 'example of the week' + archive (deterministic, no LLM)"
                   ).set_defaults(func=cmd_weekly_examples)

    p_serve = sub.add_parser("serve", help="local dev web server")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--debug", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
