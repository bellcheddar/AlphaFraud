"""The weekly pipeline: discover new human post-cutoff depositions, match each to its
blind AlphaFold model, score novelty, run the metric suite, and persist. Designed to be
robust per-entity -- one bad structure logs an error row and the run continues.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from . import afdb, banner, cath, compare, config, db, novelty, pdb, structio


def _ref_span(meta: pdb.EntityMeta) -> tuple[int, int]:
    """UniProt residue span the experimental entity covers (from the alignment regions)."""
    begs = [r.ref_beg for r in meta.aligned_regions]
    ends = [r.ref_beg + r.length - 1 for r in meta.aligned_regions]
    return (min(begs), max(ends)) if begs else (1, len(meta.sequence))


def _skip(entity_id: str, meta: Optional[pdb.EntityMeta], run_id: int, reason: str) -> None:
    db.upsert_entity({
        "entity_id": entity_id,
        "entry_id": (meta.entry_id if meta else entity_id.split("_")[0]),
        "chain": (meta.first_chain if meta else None),
        "uniprot": (meta.uniprot_accession if meta else None),
        "description": (meta.description if meta else None),
        "deposit_date": (meta.deposit_date if meta else None),
        "release_date": (meta.release_date if meta else None),
        "resolution": (meta.resolution if meta else None),
        "method": (meta.method if meta else None),
        "status": "skipped",
        "skip_reason": reason,
        "run_id": run_id,
    })


def process_entity(entity_id: str, meta: pdb.EntityMeta, run_id: int) -> str:
    """Process one entity. Returns 'compared' | 'skipped' | 'error'."""
    if not meta.has_single_uniprot:
        _skip(entity_id, meta, run_id, "no single UniProt mapping (antibody/chimera/construct?)")
        return "skipped"
    if not meta.first_chain:
        _skip(entity_id, meta, run_id, "no author chain id")
        return "skipped"

    ref_beg, ref_end = _ref_span(meta)
    preds = afdb.fetch_predictions(meta.uniprot_accession)
    frag = afdb.best_fragment(preds, ref_beg, ref_end)
    if frag is None or frag.covers(ref_beg, ref_end) < 10:
        _skip(entity_id, meta, run_id, f"no AlphaFold model covering UniProt {ref_beg}-{ref_end}")
        return "skipped"

    exp_path = pdb.download_structure(meta.entry_id)
    af_path = afdb.download_model(frag)
    if not exp_path or not af_path:
        _skip(entity_id, meta, run_id, "structure download failed")
        return "skipped"
    pae_path = afdb.download_pae(frag)

    nov = novelty.score(meta.sequence)
    exp_chain = structio.load_chain(exp_path, meta.first_chain)
    af_chain = structio.load_chain(af_path, is_af=True)
    pae = compare.load_pae(pae_path, len(af_chain.residues))
    cath_domains = cath.domains_for_chain(meta.entry_id, meta.first_chain)

    comparison = compare.compare(exp_chain, af_chain, pae=pae, cath_domains=cath_domains)

    db.upsert_entity({
        "entity_id": entity_id,
        "entry_id": meta.entry_id,
        "chain": meta.first_chain,
        "uniprot": meta.uniprot_accession,
        "uniprot_name": meta.uniprot_name,
        "description": meta.description,
        "deposit_date": meta.deposit_date,
        "release_date": meta.release_date,
        "resolution": meta.resolution,
        "method": meta.method,
        "novelty_identity": nov.max_identity,
        "is_novel": nov.is_novel,
        "closest_pre_cutoff": nov.closest_pre_cutoff,
        "af_entry_id": frag.entry_id,
        "af_model_version": frag.model_version,
        "metrics": comparison.metrics,
        "per_residue": comparison.per_residue,
        "domains": comparison.domains,
        "heatmaps": comparison.heatmaps,
        "status": "compared",
        "run_id": run_id,
    })
    return "compared"


def run(since: date, until: date, limit: Optional[int] = None, dry_run: bool = False) -> dict:
    """Execute one pipeline run over depositions in (since, until]."""
    db.init_schema()
    config.ensure_dirs()
    limit = limit or config.RUN_LIMIT
    label = until.isoformat()

    banner.step(f"Discovering human protein entities deposited {since} … {until}")
    ids = pdb.search_new_human_entities(since, until, limit=limit)
    banner.info(f"{len(ids)} entities returned by RCSB")

    fresh = [i for i in ids if not db.entity_exists(i)]
    banner.info(f"{len(fresh)} new (not already in the database)")
    if not fresh:
        banner.ok("Nothing new to process.")
        return {"discovered": len(ids), "compared": 0, "skipped": 0}

    if dry_run:
        metas = pdb.fetch_entity_metadata(fresh[: (limit or 25)])
        for eid, m in metas.items():
            tag = "map✓" if m.has_single_uniprot else "no-uniprot"
            banner.step(f"{eid}  {m.uniprot_accession or '-':7} {tag:11} {m.description or ''}")
        banner.ok(f"Dry run: {len(metas)} entities inspected, nothing written.")
        return {"discovered": len(ids), "compared": 0, "skipped": 0}

    run_id = db.start_run(label, since.isoformat(), until.isoformat())
    metas = pdb.fetch_entity_metadata(fresh)
    compared = skipped = errored = 0
    for eid in fresh:
        meta = metas.get(eid)
        if meta is None:
            _skip(eid, None, run_id, "metadata lookup failed")
            skipped += 1
            continue
        try:
            outcome = process_entity(eid, meta, run_id)
        except Exception as exc:  # keep the run alive; record the failure
            db.upsert_entity({
                "entity_id": eid, "entry_id": meta.entry_id, "uniprot": meta.uniprot_accession,
                "status": "error", "skip_reason": f"{type(exc).__name__}: {exc}", "run_id": run_id,
            })
            banner.err(f"{eid}: {type(exc).__name__}: {exc}")
            errored += 1
            continue
        if outcome == "compared":
            compared += 1
            e = db.get_entity(eid)
            flag = " ⚠ CONFIDENTLY WRONG" if e and e.get("confidently_wrong") else ""
            banner.ok(f"{eid}  TM={e.get('tm_by_experiment')}  lDDT={e.get('lddt')}  "
                      f"pLDDT={e.get('mean_plddt')}  novelty={e.get('novelty_identity')}%{flag}")
        else:
            skipped += 1

    db.finish_run(run_id, len(ids), compared, skipped + errored)
    banner.ok(f"Run {label}: {compared} compared, {skipped} skipped, {errored} errored.")
    return {"discovered": len(ids), "compared": compared, "skipped": skipped + errored}


def default_since() -> date:
    """Start of the next window for a scheduled `run`: resume from the most recent
    processed run. With an empty database, default to a one-week lookback -- NOT the 2018
    cutoff -- so the weekly timer never tries to backfill the entire post-cutoff archive.
    Use `backfill --from ... --to ...` explicitly to seed history."""
    label = db.latest_run_label()
    if label:
        try:
            return datetime.fromisoformat(label).date()
        except ValueError:
            pass
    return date.today() - timedelta(days=7)
