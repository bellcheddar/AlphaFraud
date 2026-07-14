"""AlphaFold Protein Structure Database access.

The prediction endpoint returns one JSON object per model fragment for a UniProt
accession (proteins >2700 aa are split into overlapping F1..Fn fragments). We keep the
returned download URLs verbatim rather than reconstructing them, so we stay correct across
model-version bumps (v4 today, the API already advertises v6 for some entries).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config
from .http import download, get_json


@dataclass
class AFPrediction:
    accession: str
    entry_id: str                 # AFDB entry id, e.g. AF-P18031-F1
    fragment: int                 # 1-based fragment number (F<n>)
    uniprot_start: int            # UniProt residue range this fragment covers (1-based, inclusive)
    uniprot_end: int
    mean_plddt: Optional[float]   # globalMetricValue
    model_version: Optional[int]
    sequence: str
    pdb_url: str
    cif_url: str
    pae_url: Optional[str]        # paeDocUrl (per-residue-pair PAE matrix, JSON)
    pae_image_url: Optional[str]

    def covers(self, ref_beg: int, ref_end: int) -> int:
        """Number of UniProt residues of [ref_beg, ref_end] this fragment contains."""
        lo = max(self.uniprot_start, ref_beg)
        hi = min(self.uniprot_end, ref_end)
        return max(0, hi - lo + 1)


def fetch_predictions(accession: str) -> list[AFPrediction]:
    """All AlphaFold DB fragments for a UniProt accession. Empty list if absent (404)."""
    data = get_json(config.AFDB_PREDICTION_URL.format(accession=accession))
    if not data:
        return []
    preds: list[AFPrediction] = []
    for e in data:
        preds.append(
            AFPrediction(
                accession=accession,
                entry_id=e.get("entryId", f"AF-{accession}-F1"),
                fragment=_fragment_number(e.get("entryId", "")),
                uniprot_start=int(e.get("uniprotStart", 1)),
                uniprot_end=int(e.get("uniprotEnd", len(e.get("uniprotSequence", "")) or 1)),
                mean_plddt=_as_float(e.get("globalMetricValue")),
                model_version=e.get("latestVersion"),
                sequence=e.get("sequence") or e.get("uniprotSequence") or "",
                pdb_url=e.get("pdbUrl", ""),
                cif_url=e.get("cifUrl", ""),
                pae_url=e.get("paeDocUrl"),
                pae_image_url=e.get("paeImageUrl"),
            )
        )
    return preds


def best_fragment(preds: list[AFPrediction], ref_beg: int, ref_end: int) -> Optional[AFPrediction]:
    """Fragment covering the most of the experimental UniProt span (handles >2700 aa splits)."""
    if not preds:
        return None
    return max(preds, key=lambda p: p.covers(ref_beg, ref_end))


def download_model(pred: AFPrediction) -> Optional[Path]:
    """Download the fragment's PDB file to the structure cache. Returns the path or None."""
    if not pred.pdb_url:
        return None
    dest = config.STRUCT_CACHE / f"{pred.entry_id}.pdb"
    return download(pred.pdb_url, dest)


def download_pae(pred: AFPrediction) -> Optional[Path]:
    """Download the fragment's PAE matrix JSON, or None if unavailable."""
    if not pred.pae_url:
        return None
    dest = config.STRUCT_CACHE / f"{pred.entry_id}-pae.json"
    return download(pred.pae_url, dest)


def _fragment_number(entry_id: str) -> int:
    # AF-<acc>-F<n>-model_v<k>  or  AF-<acc>-F<n>
    for tok in entry_id.split("-"):
        if tok.startswith("F") and tok[1:].isdigit():
            return int(tok[1:])
    return 1


def _as_float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
