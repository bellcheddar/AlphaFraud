"""On-demand single-entity computation for the Calculate tab — no LLM.

Reuses the full pipeline (pipeline.process_entity) to validate, superpose, score and render the
ribbon for one user-chosen human entity, stores it as status='calculated' (kept out of every
aggregate), and enriches its annotation so the panel carries CATH / citation fields. The panel
prose is the deterministic template in examples_auto.build.
"""

import json

from . import annotate, banner, config, db, pdb, pipeline


def validate(raw: str) -> dict:
    """Resolve a user-entered PDB id / entity id to a computable human entity, or explain why it
    can't be. Returns {'entity_id', 'in_index', 'post_cutoff', 'others'} on success, else {'error'}.
    Does at most a couple of fast API calls (never the heavy compute)."""
    raw = (raw or "").strip().upper()
    entry = raw.split("_")[0]
    want = raw if "_" in raw else None
    if len(entry) != 4 or not entry.isalnum():
        return {"error": "Enter a 4-character PDB ID (optionally with an entity number, e.g. 7U14 or 7U14_1)."}

    idx = db.index_entities_for_entry(entry)          # index = already-qualifying (human + AF model)
    if idx:
        row = next((r for r in idx if r["entity_id"] == want), None) or idx[0]
        return {"entity_id": row["entity_id"], "in_index": True, "post_cutoff": row["post_cutoff"],
                "others": [r["entity_id"] for r in idx]}

    ents = pdb.human_entities_of_entry(entry)         # not indexed -> live checks for a precise reason
    if not ents:
        return {"error": f"{entry} isn't a human protein structure in the PDB (no human protein "
                         "entity, or the entry doesn't exist)."}
    if want and want not in ents:
        return {"error": f"{want} is not a human protein entity of {entry}."}
    eid = want or ents[0]
    meta = pdb.fetch_entity_metadata([eid]).get(eid)
    if meta is None:
        return {"error": f"Couldn't read metadata for {eid} from the PDB."}
    if not meta.has_single_uniprot:
        return {"error": f"{eid} maps to no single UniProt (antibody / fusion / chimera / synthetic); "
                         "AlphaFraud can't pick one AlphaFold model to compare against."}
    from . import calc_index
    if not calc_index.af_has_model(meta.uniprot_accession):
        return {"error": f"No AlphaFold model exists for UniProt {meta.uniprot_accession}, so there is "
                         "nothing to compare this structure against."}
    dep = (meta.deposit_date or "")[:10]
    return {"entity_id": eid, "in_index": False,
            "post_cutoff": 1 if dep and dep >= config.AF_TRAINING_CUTOFF.isoformat() else 0,
            "others": ents}


def _store_annotation(entity: dict) -> None:
    """Fetch + store CATH / SCOP / citation for one entity (the /analysis 'enrich' loop, for a
    single 'calculated' row that the batch enricher — which only scans 'compared' — would skip)."""
    from . import analysis   # lazy: analysis pulls scipy
    anns = annotate.fetch([entity])
    a = anns.get(entity["entity_id"])
    if not a:
        return
    ad = {
        "sequence": a.sequence, "seq_length": a.seq_length, "cath_code": a.cath_code,
        "cath_class": a.cath_class, "cath_arch": a.cath_arch, "cath_topo": a.cath_topo,
        "cath_name": a.cath_name, "scop2_sf": a.scop2_sf, "ecod_family": a.ecod_family,
        "citation_doi": a.citation_doi, "citation_title": a.citation_title,
        "citation_journal": a.citation_journal, "citation_year": a.citation_year,
        "citation_pubmed": a.citation_pubmed, "n_chains": a.n_chains, "assembly_count": a.assembly_count,
    }
    flags = analysis.compute_flags(entity, {"n_chains": a.n_chains, "ecod_family": a.ecod_family,
                                            "citation_title": a.citation_title})
    db.upsert_annotation({
        "entity_id": entity["entity_id"], **ad, **flags,
        "pfam_json": json.dumps([p["id"] for p in a.pfam]),
        "go_json": json.dumps([g["id"] for g in a.go]),
    })


def compute(entity_id: str) -> dict:
    """Fully process one entity on demand and store it as 'calculated'. Returns {status, reason?}.
    status is 'ready' on success or 'error' with a human reason. Called by the `calculate`
    subcommand (spawned as a subprocess by the web route) or from the CLI."""
    entity_id = entity_id.strip().upper()
    run_id = db.calculate_run_id()
    metas = pdb.fetch_entity_metadata([entity_id])
    meta = metas.get(entity_id)
    if meta is None:
        db.upsert_entity({"entity_id": entity_id, "status": "error", "run_id": run_id,
                          "skip_reason": "metadata lookup failed (no such PDB entity?)"})
        return {"status": "error", "reason": "metadata lookup failed (no such PDB entity?)"}

    try:
        outcome = pipeline.process_entity(entity_id, meta, run_id, cleanup=True, status="calculated")
    except Exception as exc:
        db.upsert_entity({"entity_id": entity_id, "entry_id": meta.entry_id,
                          "uniprot": meta.uniprot_accession, "status": "error", "run_id": run_id,
                          "skip_reason": f"{type(exc).__name__}: {exc}"})
        banner.err(f"[calculate] {entity_id}: {type(exc).__name__}: {exc}")
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}

    if outcome == "compared":
        try:
            _store_annotation(dict(db.get_entity(entity_id)))
        except Exception as exc:                    # annotation is a nice-to-have, not fatal
            banner.warn(f"[calculate] annotation failed for {entity_id}: {exc}")
        banner.ok(f"[calculate] {entity_id} ready")
        return {"status": "ready"}

    row = db.calc_status(entity_id) or {}           # process_entity stored status='skipped' + reason
    return {"status": "error", "reason": row.get("skip_reason") or "could not process this entity"}
