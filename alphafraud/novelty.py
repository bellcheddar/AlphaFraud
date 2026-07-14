"""Sequence-novelty scoring.

"Deposited after the cutoff" is a proxy: AlphaFold can still nail a post-2018 structure
if a close homolog was in its training set. To sharpen the hypothesis test we ask, for
each entity sequence, "what is the highest %identity to ANY PDB chain released BEFORE the
training cutoff?" -- i.e. how much did AlphaFold have to go on. A low value means genuinely
unseen. We use the RCSB Search `sequence` service (MMseqs2) restricted to pre-cutoff
release dates, and read the top hit's sequence identity from verbose match context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import config
from .http import post_json


@dataclass
class Novelty:
    max_identity: Optional[float]     # % identity to closest pre-cutoff PDB chain (None = lookup failed)
    closest_pre_cutoff: Optional[str] # that chain's entity id, for provenance
    is_novel: bool                    # max_identity < threshold (unknown -> False, conservative)


def _query(sequence: str) -> dict:
    cutoff = config.AF_TRAINING_CUTOFF.isoformat()
    return {
        "query": {
            "type": "group",
            "logical_operator": "and",
            "nodes": [
                {
                    "type": "terminal",
                    "service": "sequence",
                    "parameters": {
                        "evalue_cutoff": 1,
                        "identity_cutoff": 0,        # keep even remote homologs so "max identity" is honest
                        "sequence_type": "protein",
                        "value": sequence,
                    },
                },
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "rcsb_accession_info.initial_release_date",
                        "operator": "less",
                        "value": f"{cutoff}T00:00:00Z",
                    },
                },
            ],
        },
        "return_type": "polymer_entity",
        "request_options": {
            "scoring_strategy": "sequence",
            "results_verbosity": "verbose",
            "paginate": {"start": 0, "rows": 1},
        },
    }


def score(sequence: str) -> Novelty:
    """Max %identity of `sequence` to any pre-cutoff PDB chain (0 if none; None on error)."""
    sequence = (sequence or "").strip().replace("\n", "")
    # The sequence service needs a meaningful query length; very short peptides are skipped.
    if len(sequence) < 20:
        return Novelty(max_identity=None, closest_pre_cutoff=None, is_novel=False)
    try:
        resp = post_json(config.RCSB_SEARCH_URL, _query(sequence))
    except Exception:
        return Novelty(max_identity=None, closest_pre_cutoff=None, is_novel=False)

    if resp.status_code == 204:
        # No pre-cutoff hit at all -> nothing remotely similar existed at training time.
        return Novelty(max_identity=0.0, closest_pre_cutoff=None, is_novel=True)
    if resp.status_code != 200:
        return Novelty(max_identity=None, closest_pre_cutoff=None, is_novel=False)

    result_set = resp.json().get("result_set") or []
    if not result_set:
        return Novelty(max_identity=0.0, closest_pre_cutoff=None, is_novel=True)

    top = result_set[0]
    ident = _extract_identity(top)
    if ident is None:
        return Novelty(max_identity=None, closest_pre_cutoff=top.get("identifier"), is_novel=False)
    pct = round(ident * 100, 1)
    return Novelty(
        max_identity=pct,
        closest_pre_cutoff=top.get("identifier"),
        is_novel=pct < config.NOVELTY_IDENTITY_THRESHOLD,
    )


def _extract_identity(result: dict) -> Optional[float]:
    for svc in result.get("services", []):
        if svc.get("service_type") != "sequence":
            continue
        best = None
        for node in svc.get("nodes", []):
            for ctx in node.get("match_context", []):
                si = ctx.get("sequence_identity")
                if si is not None:
                    best = si if best is None else max(best, si)
        return best
    return None
