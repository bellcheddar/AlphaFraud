"""Enrichment fetches for the Analysis tab: for a batch of already-compared entities, pull
the structural-classification, family, citation and assembly metadata that the pipeline did
not need for scoring but the deep-dive analysis does.

All from RCSB Data GraphQL (batched, polite via the shared retrying session). Nothing here
re-downloads coordinates -- everything needed comes from metadata queries, so it runs cheaply
over the compared subset (a few thousand), not the full 96k archive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import config
from .http import graphql

# Entity-level: sequence + family annotations (Pfam / InterPro / GO).
_ENTITY_ANN_QUERY = """
query($ids: [String!]!) {
  polymer_entities(entity_ids: $ids) {
    rcsb_id
    entity_poly { pdbx_seq_one_letter_code_can rcsb_sample_sequence_length }
    rcsb_polymer_entity_annotation { type annotation_id name }
  }
}
"""

# Chain-instance level: structural classification features (CATH / SCOP / SCOP2 / ECOD).
_INSTANCE_FOLD_QUERY = """
query($ids: [String!]!) {
  polymer_entity_instances(instance_ids: $ids) {
    rcsb_id
    rcsb_polymer_instance_feature {
      type name feature_id
      feature_positions { beg_seq_id end_seq_id }
    }
  }
}
"""

# Entry level: primary-citation DOI/PubMed + assembly / chain counts.
_ENTRY_CITE_QUERY = """
query($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    rcsb_primary_citation { pdbx_database_id_DOI title journal_abbrev year pdbx_database_id_PubMed }
    rcsb_entry_info { assembly_count deposited_polymer_entity_instance_count }
  }
}
"""

_FOLD_TYPES = {"CATH", "SCOP", "SCOP2B_SUPERFAMILY", "ECOD"}


@dataclass
class Annotation:
    entity_id: str
    sequence: str = ""
    seq_length: Optional[int] = None
    cath_code: Optional[str] = None            # e.g. "3.90.190.10"
    cath_name: Optional[str] = None
    cath_class: Optional[str] = None           # "3"
    cath_arch: Optional[str] = None            # "3.90"
    cath_topo: Optional[str] = None            # "3.90.190"
    scop2_sf: Optional[str] = None             # SCOP2 superfamily name (readable)
    ecod_family: Optional[str] = None
    pfam: list = field(default_factory=list)   # [{"id","name"}]
    go: list = field(default_factory=list)
    citation_doi: Optional[str] = None
    citation_title: Optional[str] = None
    citation_journal: Optional[str] = None
    citation_year: Optional[int] = None
    citation_pubmed: Optional[int] = None
    n_chains: Optional[int] = None             # deposited polymer instance count (assembly size proxy)
    assembly_count: Optional[int] = None


# CATH class numbers -> human names (top level only; enough for the class breakdown).
CATH_CLASS_NAMES = {
    "1": "Mainly Alpha", "2": "Mainly Beta", "3": "Alpha Beta",
    "4": "Few Secondary Structures", "6": "Special",
}


def fetch(entities: list[dict]) -> dict[str, Annotation]:
    """entities: rows with entity_id, entry_id, chain, uniprot. Returns entity_id -> Annotation."""
    out: dict[str, Annotation] = {e["entity_id"]: Annotation(entity_id=e["entity_id"]) for e in entities}
    ids = [e["entity_id"] for e in entities]
    instance_ids, id_by_instance = [], {}
    for e in entities:
        if e.get("chain"):
            iid = f"{e['entry_id'].upper()}.{e['chain']}"
            instance_ids.append(iid)
            id_by_instance[iid] = e["entity_id"]
    entry_ids = sorted({e["entry_id"] for e in entities})
    entry_to_entities: dict[str, list[str]] = {}
    for e in entities:
        entry_to_entities.setdefault(e["entry_id"], []).append(e["entity_id"])

    _fetch_entity_annotations(ids, out)
    _fetch_fold(instance_ids, id_by_instance, out)
    _fetch_citations(entry_ids, entry_to_entities, out)
    return out


def _batches(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _fetch_entity_annotations(ids, out):
    for batch in _batches(ids, 40):
        data = graphql(config.RCSB_GRAPHQL_URL, _ENTITY_ANN_QUERY, {"ids": batch})
        for ent in data.get("polymer_entities") or []:
            if not ent:
                continue
            ann = out.get(ent["rcsb_id"])
            if not ann:
                continue
            poly = ent.get("entity_poly") or {}
            ann.sequence = (poly.get("pdbx_seq_one_letter_code_can") or "").replace("\n", "")
            ann.seq_length = poly.get("rcsb_sample_sequence_length")
            for a in ent.get("rcsb_polymer_entity_annotation") or []:
                t = a.get("type")
                item = {"id": a.get("annotation_id"), "name": a.get("name")}
                if t == "Pfam":
                    ann.pfam.append(item)
                elif t == "GO":
                    ann.go.append(item)


def _fetch_fold(instance_ids, id_by_instance, out):
    for batch in _batches(instance_ids, 40):
        data = graphql(config.RCSB_GRAPHQL_URL, _INSTANCE_FOLD_QUERY, {"ids": batch})
        for inst in data.get("polymer_entity_instances") or []:
            if not inst:
                continue
            ann = out.get(id_by_instance.get(inst["rcsb_id"]))
            if not ann:
                continue
            # Pick the CATH domain covering the most residues as the "primary" class.
            best_cath = None
            best_span = -1
            for f in inst.get("rcsb_polymer_instance_feature") or []:
                t = f.get("type")
                if t not in _FOLD_TYPES:
                    continue
                if t == "CATH":
                    span = _span(f)
                    if span > best_span:
                        best_span, best_cath = span, f
                elif t == "SCOP2B_SUPERFAMILY" and not ann.scop2_sf:
                    ann.scop2_sf = f.get("name")
                elif t == "ECOD" and not ann.ecod_family:
                    ann.ecod_family = f.get("name")
            if best_cath:
                code = best_cath.get("feature_id") or ""
                ann.cath_code = code
                ann.cath_name = best_cath.get("name")
                parts = code.split(".")
                if len(parts) >= 1:
                    ann.cath_class = parts[0]
                if len(parts) >= 2:
                    ann.cath_arch = ".".join(parts[:2])
                if len(parts) >= 3:
                    ann.cath_topo = ".".join(parts[:3])


def _fetch_citations(entry_ids, entry_to_entities, out):
    for batch in _batches(entry_ids, 80):
        data = graphql(config.RCSB_GRAPHQL_URL, _ENTRY_CITE_QUERY, {"ids": batch})
        for entry in data.get("entries") or []:
            if not entry:
                continue
            cite = entry.get("rcsb_primary_citation") or {}
            info = entry.get("rcsb_entry_info") or {}
            for eid in entry_to_entities.get(entry["rcsb_id"], []):
                ann = out.get(eid)
                if not ann:
                    continue
                ann.citation_doi = cite.get("pdbx_database_id_DOI")
                ann.citation_title = cite.get("title")
                ann.citation_journal = cite.get("journal_abbrev")
                ann.citation_year = cite.get("year")
                ann.citation_pubmed = cite.get("pdbx_database_id_PubMed")
                ann.n_chains = info.get("deposited_polymer_entity_instance_count")
                ann.assembly_count = info.get("assembly_count")


def _span(feature) -> int:
    total = 0
    for pos in feature.get("feature_positions") or []:
        b, e = pos.get("beg_seq_id"), pos.get("end_seq_id")
        if b is not None and e is not None:
            total += int(e) - int(b) + 1
    return total
