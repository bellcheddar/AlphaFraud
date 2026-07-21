"""RCSB PDB access: discover new human protein entities deposited after AlphaFold's
training cutoff, and pull the metadata needed to match them to an AlphaFold model.

Two APIs:
  * Search API  (POST /rcsbsearch/v2/query) -- returns the polymer_entity ids to process.
  * Data GraphQL (/graphql)                 -- entity sequence, UniProt accession, and the
                                               entity<->UniProt residue alignment (so we
                                               compare only the resolved/aligned span and
                                               can flag mutants/constructs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from pathlib import Path

from . import config
from .http import download, graphql, post_json

RCSB_FILE_URL = "https://files.rcsb.org/download/{entry_id}.{fmt}"


@dataclass
class AlignedRegion:
    """One contiguous entity<->UniProt correspondence (1-based, inclusive)."""
    entity_beg: int
    ref_beg: int
    length: int


@dataclass
class EntityMeta:
    entity_id: str                       # e.g. "7XYZ_1"
    entry_id: str                        # e.g. "7XYZ"
    sequence: str                        # one-letter (canonical) entity sequence
    auth_asym_ids: list[str]             # author chain ids for this entity
    uniprot_accession: Optional[str]
    uniprot_name: Optional[str]
    aligned_regions: list[AlignedRegion] = field(default_factory=list)
    deposit_date: Optional[str] = None
    release_date: Optional[str] = None
    resolution: Optional[float] = None
    method: Optional[str] = None
    description: Optional[str] = None

    @property
    def has_single_uniprot(self) -> bool:
        return bool(self.uniprot_accession)

    @property
    def first_chain(self) -> Optional[str]:
        return self.auth_asym_ids[0] if self.auth_asym_ids else None


# --------------------------------------------------------------------------------------
# Discovery (Search API)
# --------------------------------------------------------------------------------------
def _search_query(since: date, until: date, enforce_cutoff: bool = True) -> dict:
    # The weekly watch floors at the AlphaFold cutoff; the Calculate index sweep (enforce_cutoff=
    # False) needs the pre-cutoff human structures too.
    floor = max(since, config.AF_TRAINING_CUTOFF) if enforce_cutoff else since
    return {
        "query": {
            "type": "group",
            "logical_operator": "and",
            "nodes": [
                {
                    # taxonomy_lineage.id is the searchable form (ncbi_taxonomy_id itself
                    # is not search-enabled) and expects the id as a string.
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "rcsb_entity_source_organism.taxonomy_lineage.id",
                        "operator": "exact_match",
                        "value": str(config.HUMAN_TAXONOMY_ID),
                    },
                },
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "rcsb_accession_info.deposit_date",
                        "operator": "range",
                        "value": {
                            "from": f"{floor.isoformat()}T00:00:00Z",
                            "to": f"{until.isoformat()}T23:59:59Z",
                            "include_lower": True,
                            "include_upper": True,
                        },
                    },
                },
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "entity_poly.rcsb_entity_polymer_type",
                        "operator": "exact_match",
                        "value": "Protein",
                    },
                },
            ],
        },
        "return_type": "polymer_entity",
        "request_options": {"paginate": {"start": 0, "rows": 100}, "results_content_type": ["experimental"]},
    }


def search_new_human_entities(since: date, until: date, limit: Optional[int] = None,
                              enforce_cutoff: bool = True) -> list[str]:
    """Return polymer_entity ids (e.g. '7XYZ_1') for human protein entities deposited in the window.
    With enforce_cutoff (default) the lower bound is floored at the AlphaFold cutoff (the weekly
    watch); with enforce_cutoff=False the raw `since` is used (the Calculate index's pre-cutoff
    sweep). Paginates the Search API in blocks of 100."""
    payload = _search_query(since, until, enforce_cutoff=enforce_cutoff)
    rows = payload["request_options"]["paginate"]["rows"]
    start = 0
    ids: list[str] = []
    while True:
        payload["request_options"]["paginate"]["start"] = start
        resp = post_json(config.RCSB_SEARCH_URL, payload)
        if resp.status_code == 204:            # no (more) results
            break
        resp.raise_for_status()
        result_set = resp.json().get("result_set", [])
        if not result_set:
            break
        ids.extend(item["identifier"] for item in result_set)
        if limit and len(ids) >= limit:
            return ids[:limit]
        if len(result_set) < rows:
            break
        start += rows
    return ids


def human_entities_of_entry(entry_id: str) -> list[str]:
    """The human protein polymer_entity ids of one PDB entry (any deposit date). Empty if the entry
    doesn't exist, isn't human, or has no protein entity — used by the Calculate tab to resolve a
    bare 4-char id and to give a precise 'not a human structure' reason."""
    payload = {
        "query": {"type": "group", "logical_operator": "and", "nodes": [
            {"type": "terminal", "service": "text", "parameters": {
                "attribute": "rcsb_entry_container_identifiers.entry_id",
                "operator": "exact_match", "value": entry_id.upper()}},
            {"type": "terminal", "service": "text", "parameters": {
                "attribute": "rcsb_entity_source_organism.taxonomy_lineage.id",
                "operator": "exact_match", "value": str(config.HUMAN_TAXONOMY_ID)}},
            {"type": "terminal", "service": "text", "parameters": {
                "attribute": "entity_poly.rcsb_entity_polymer_type",
                "operator": "exact_match", "value": "Protein"}},
        ]},
        "return_type": "polymer_entity",
        "request_options": {"paginate": {"start": 0, "rows": 50}, "results_content_type": ["experimental"]},
    }
    resp = post_json(config.RCSB_SEARCH_URL, payload)
    if resp.status_code == 204:
        return []
    resp.raise_for_status()
    return [item["identifier"] for item in resp.json().get("result_set", [])]


# --------------------------------------------------------------------------------------
# Metadata (Data GraphQL)
# --------------------------------------------------------------------------------------
_ENTITY_QUERY = """
query($ids: [String!]!) {
  polymer_entities(entity_ids: $ids) {
    rcsb_id
    entity_poly { pdbx_seq_one_letter_code_can rcsb_entity_polymer_type }
    rcsb_polymer_entity { pdbx_description }
    rcsb_polymer_entity_container_identifiers {
      entry_id
      auth_asym_ids
      reference_sequence_identifiers { database_accession database_name }
    }
    rcsb_polymer_entity_align {
      reference_database_accession
      reference_database_name
      aligned_regions { entity_beg_seq_id ref_beg_seq_id length }
    }
  }
}
"""

_ENTRY_QUERY = """
query($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    rcsb_accession_info { deposit_date initial_release_date }
    rcsb_entry_info { resolution_combined experimental_method }
  }
}
"""


def _pick_uniprot(entity: dict) -> tuple[Optional[str], Optional[str], list[AlignedRegion]]:
    """Choose the single UniProt accession for an entity and its aligned regions.

    Entities with zero or multiple distinct UniProt references (antibodies, chimeras,
    fusion constructs) return (None, None, []) and are flagged/skipped downstream.
    """
    refs = (entity.get("rcsb_polymer_entity_container_identifiers") or {}).get(
        "reference_sequence_identifiers"
    ) or []
    accs = {r["database_accession"] for r in refs if r.get("database_name") == "UniProt"}
    if len(accs) != 1:
        return None, None, []
    acc = next(iter(accs))

    regions: list[AlignedRegion] = []
    name = None
    for align in entity.get("rcsb_polymer_entity_align") or []:
        if align.get("reference_database_name") != "UniProt":
            continue
        if align.get("reference_database_accession") != acc:
            continue
        for reg in align.get("aligned_regions") or []:
            regions.append(
                AlignedRegion(
                    entity_beg=int(reg["entity_beg_seq_id"]),
                    ref_beg=int(reg["ref_beg_seq_id"]),
                    length=int(reg["length"]),
                )
            )
    return acc, name, regions


def download_structure(entry_id: str, prefer_cif: bool = False, force: bool = False) -> Optional[Path]:
    """Download the experimental coordinates. Tries PDB format, falls back to mmCIF for
    entries too large for the legacy PDB format (large cryo-EM assemblies).

    `prefer_cif` requests mmCIF first -- the canonical, complete format. Large assemblies
    (>62 chains / >99,999 atoms) have no valid legacy .pdb at all, so a plain .pdb fetch can
    save a truncated/error file that later fails to parse; the retry path uses this to fetch
    the format that actually exists. `force` re-downloads even if a (possibly bad) cached
    file is present."""
    entry_id = entry_id.lower()
    pdb_dest = config.STRUCT_CACHE / f"{entry_id}.pdb"
    cif_dest = config.STRUCT_CACHE / f"{entry_id}.cif"
    if force:                                   # drop stale/corrupt cached files first
        pdb_dest.unlink(missing_ok=True)
        cif_dest.unlink(missing_ok=True)
    order = [("cif", cif_dest), ("pdb", pdb_dest)] if prefer_cif else [("pdb", pdb_dest), ("cif", cif_dest)]
    for fmt, dest in order:
        got = download(RCSB_FILE_URL.format(entry_id=entry_id, fmt=fmt), dest, skip_if_exists=not force)
        if got:
            return got
    return None


def fetch_entity_metadata(entity_ids: list[str]) -> dict[str, EntityMeta]:
    """Resolve a batch of polymer_entity ids to EntityMeta (sequence, UniProt, alignment,
    plus entry-level deposit/release/resolution/method)."""
    out: dict[str, EntityMeta] = {}
    # GraphQL handles large id lists, but keep batches modest to stay well under limits.
    for i in range(0, len(entity_ids), 50):
        batch = entity_ids[i : i + 50]
        data = graphql(config.RCSB_GRAPHQL_URL, _ENTITY_QUERY, {"ids": batch})
        for entity in data.get("polymer_entities") or []:
            if not entity:
                continue
            ident = entity["rcsb_id"]
            cont = entity.get("rcsb_polymer_entity_container_identifiers") or {}
            poly = entity.get("entity_poly") or {}
            acc, name, regions = _pick_uniprot(entity)
            out[ident] = EntityMeta(
                entity_id=ident,
                entry_id=cont.get("entry_id", ident.split("_")[0]),
                sequence=(poly.get("pdbx_seq_one_letter_code_can") or "").replace("\n", ""),
                auth_asym_ids=cont.get("auth_asym_ids") or [],
                uniprot_accession=acc,
                uniprot_name=name,
                aligned_regions=regions,
                description=(entity.get("rcsb_polymer_entity") or {}).get("pdbx_description"),
            )
    _attach_entry_info(out)
    return out


def _attach_entry_info(metas: dict[str, EntityMeta]) -> None:
    entry_ids = sorted({m.entry_id for m in metas.values()})
    info: dict[str, dict] = {}
    for i in range(0, len(entry_ids), 100):
        batch = entry_ids[i : i + 100]
        data = graphql(config.RCSB_GRAPHQL_URL, _ENTRY_QUERY, {"ids": batch})
        for entry in data.get("entries") or []:
            if entry:
                info[entry["rcsb_id"]] = entry
    for meta in metas.values():
        entry = info.get(meta.entry_id)
        if not entry:
            continue
        acc = entry.get("rcsb_accession_info") or {}
        einfo = entry.get("rcsb_entry_info") or {}
        meta.deposit_date = acc.get("deposit_date")
        meta.release_date = acc.get("initial_release_date")
        res = einfo.get("resolution_combined")
        meta.resolution = float(res[0]) if res else None
        methods = einfo.get("experimental_method")
        meta.method = methods if isinstance(methods, str) else (methods[0] if methods else None)
