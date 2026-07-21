"""Strict autocomplete index for the Calculate tab.

An entity qualifies when it (1) exists in the PDB, (2) is a human protein, and (3) maps to a single
UniProt that has an AlphaFold model. The exact "the model covers the resolved residues" check is
deferred to submit time (pipeline._resolve_fragment), because confirming it here would mean
downloading every AlphaFold model.

The index is seeded for free from the corpus (entities already carrying a UniProt + AF model),
back-filled once with a pre-cutoff human sweep, and kept current by the weekly run (refresh_weekly).
"""

from datetime import date

from . import afdb, banner, config, db, pdb

_SWEEP_FLOOR = date(1976, 1, 1)   # first PDB depositions; the pre-cutoff sweep starts here


def af_has_model(uniprot: str) -> bool:
    """Does AlphaFold DB have a model for this accession? Cached per UniProt (one API call each)."""
    cached = db.af_cache_get(uniprot)
    if cached is not None:
        return cached
    has = bool(afdb.fetch_predictions(uniprot))
    db.af_cache_set(uniprot, has)
    return has


def _qualify(entity_id: str, meta) -> dict | None:
    """An index row for a qualifying entity, or None."""
    if not meta or not meta.has_single_uniprot or not meta.uniprot_accession:
        return None
    if not af_has_model(meta.uniprot_accession):
        return None
    dep = (meta.deposit_date or "")[:10]
    return {
        "entity_id": entity_id, "entry_id": meta.entry_id, "uniprot": meta.uniprot_accession,
        "gene": meta.uniprot_name, "title": meta.description, "deposit_date": meta.deposit_date,
        "post_cutoff": 1 if dep and dep >= config.AF_TRAINING_CUTOFF.isoformat() else 0,
    }


def refresh_weekly(metas: dict) -> int:
    """Upsert the qualifying entities among a batch of freshly-resolved metadata (the weekly run
    already fetched these, so this is nearly free)."""
    rows = [r for eid, m in (metas or {}).items() if (r := _qualify(eid, m))]
    return db.index_upsert(rows)


def sweep_pre_cutoff(limit: int | None = None, batch: int = 100) -> int:
    """One-off back-fill: human protein entities deposited before the AlphaFold cutoff (the corpus
    only holds post-cutoff entities). Metadata is fetched in batches; AF availability is cached."""
    ids = pdb.search_new_human_entities(_SWEEP_FLOOR, config.AF_TRAINING_CUTOFF,
                                        limit=limit, enforce_cutoff=False)
    banner.info(f"[calc-index] pre-cutoff sweep: {len(ids)} human protein entities to inspect")
    total = 0
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        metas = pdb.fetch_entity_metadata(chunk)
        rows = [r for eid, m in metas.items() if (r := _qualify(eid, m))]
        total += db.index_upsert(rows)
        if (i // batch) % 10 == 0:
            banner.info(f"[calc-index]   {min(i + batch, len(ids))}/{len(ids)} inspected, "
                        f"{total} indexed so far")
    return total


def seed_from_entities() -> int:
    """Seed the index from corpus entities that already have a UniProt + AlphaFold model."""
    return db.seed_index_from_entities()


def rebuild(pre_cutoff: bool = True, limit: int | None = None) -> dict:
    """Full (re)build: seed from the corpus, then optionally sweep the pre-cutoff human set."""
    seeded = seed_from_entities()
    banner.ok(f"[calc-index] seeded {seeded} entities from the corpus")
    swept = sweep_pre_cutoff(limit=limit) if pre_cutoff else 0
    total = db.index_count()
    banner.ok(f"[calc-index] rebuild done: seeded={seeded} swept={swept} total={total}")
    return {"seeded": seeded, "swept": swept, "total": total}
