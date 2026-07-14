"""Thin structure-IO layer over biotite: load a single protein chain as an ordered list
of residues (one-letter code, CA coord, per-atom coords, and pLDDT for AlphaFold models).

Kept separate from compare.py so the metric code deals in clean numpy arrays and never
touches biotite parsing details (altlocs, model stacks, non-standard residues).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import biotite.structure as struc
import biotite.structure.io as strucio
from biotite.sequence import ProteinSequence

_THREE_TO_ONE = {}  # cached lazily via ProteinSequence


@dataclass
class Residue:
    res_id: int                       # author residue number (AF model: UniProt position)
    letter: str                       # one-letter code ('X' for non-standard)
    ca: Optional[np.ndarray]          # (3,) CA coordinate, or None if unresolved
    atoms: dict[str, np.ndarray] = field(default_factory=dict)   # atom_name -> (3,)
    plddt: Optional[float] = None     # AF per-residue confidence (CA B-factor), else None
    sse: str = "c"                    # secondary structure: 'a' helix, 'b' strand, 'c' coil
    phi: float = float("nan")         # backbone torsion (radians)
    psi: float = float("nan")


@dataclass
class Chain:
    residues: list[Residue]

    @property
    def sequence(self) -> str:
        return "".join(r.letter for r in self.residues)

    @property
    def ca_coords(self) -> np.ndarray:
        return np.array([r.ca for r in self.residues], dtype=float)


def _one_letter(res_name: str) -> str:
    try:
        return ProteinSequence.convert_letter_3to1(res_name)
    except KeyError:
        return "X"


def _load_atomarray(path: Path) -> struc.AtomArray:
    """Load first model, standard amino acids only, highest-occupancy altloc."""
    # b_factor carries AlphaFold per-residue pLDDT; occupancy drives altloc filtering.
    obj = strucio.load_structure(str(path), extra_fields=["b_factor", "occupancy"])
    if isinstance(obj, struc.AtomArrayStack):   # NMR / multi-model -> first model
        obj = obj[0]
    obj = obj[struc.filter_amino_acids(obj)]
    try:
        obj = obj[struc.filter_highest_occupancy_altloc(obj)]
    except Exception:
        pass
    return obj


def load_chain(path, chain_id: Optional[str] = None, is_af: bool = False) -> Chain:
    """Load one chain as an ordered Residue list. For AF models chain_id may be None
    (single chain 'A'); pLDDT is read from the CA B-factor."""
    atoms = _load_atomarray(Path(path))
    if chain_id is not None:
        atoms = atoms[atoms.chain_id == chain_id]
    elif len(np.unique(atoms.chain_id)) > 1:
        first = atoms.chain_id[0]
        atoms = atoms[atoms.chain_id == first]

    spans = _residue_spans(atoms)
    sse = _safe_sse(atoms, len(spans))
    phi, psi = _safe_torsions(atoms, len(spans))

    residues: list[Residue] = []
    for idx, (start, stop) in enumerate(spans):
        res_atoms = atoms[start:stop]
        names = res_atoms.atom_name
        coords = res_atoms.coord
        atom_map = {n: coords[i] for i, n in enumerate(names)}
        ca = atom_map.get("CA")
        plddt = None
        if is_af and ca is not None:
            ca_idx = int(np.where(names == "CA")[0][0])
            plddt = float(res_atoms.b_factor[ca_idx])
        residues.append(
            Residue(
                res_id=int(res_atoms.res_id[0]),
                letter=_one_letter(res_atoms.res_name[0]),
                ca=np.asarray(ca, dtype=float) if ca is not None else None,
                atoms={n: np.asarray(c, dtype=float) for n, c in atom_map.items()},
                plddt=plddt,
                sse=sse[idx],
                phi=float(phi[idx]),
                psi=float(psi[idx]),
            )
        )
    # Drop residues with no CA -- they cannot participate in any structural comparison.
    residues = [r for r in residues if r.ca is not None]
    return Chain(residues=residues)


def _safe_sse(atoms: struc.AtomArray, n: int):
    """Per-residue secondary structure ('a'/'b'/'c'); falls back to all-coil on failure."""
    try:
        codes = struc.annotate_sse(atoms)
        if len(codes) == n:
            return [str(c) for c in codes]
    except Exception:
        pass
    return ["c"] * n


def _safe_torsions(atoms: struc.AtomArray, n: int):
    try:
        phi, psi, _omega = struc.dihedral_backbone(atoms)
        if len(phi) == n:
            return phi, psi
    except Exception:
        pass
    nan = np.full(n, np.nan)
    return nan, nan


def _residue_spans(atoms: struc.AtomArray):
    starts = struc.get_residue_starts(atoms).tolist()
    starts.append(len(atoms))
    return list(zip(starts[:-1], starts[1:]))
