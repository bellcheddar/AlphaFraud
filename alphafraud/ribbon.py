"""Deviation-coloured Cα ribbon SVGs for worst offenders.

A pure-numpy schematic cartoon: the experimental Cα trace (kept in the pipeline's
superposition frame) projected to 2D and drawn as a smooth, SSE-aware ribbon coloured
per-residue by its Cα deviation from the AlphaFold model (blue = agrees … red = diverges,
anchored to *absolute* Ångströms). No external renderer, no CDN, no WebGL -- just SVG text,
so it scales from a table thumbnail to a full-page hero and works offline.

The SVG is transparent and text-free (the legend is HTML, rendered once per page), so the
same file serves every surface. Stored on disk at config.RIBBON_DIR/<entity_id>.svg; the
web app serves it and the pipeline writes it. Colours are theme-independent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from . import compare, config

# Deviation colour scale, anchored to ABSOLUTE Ångströms (never per-entity min/max, so a
# 0.8 Å miss never looks as red as a 15 Å one). Brand palette: blue -> light blue -> amber -> red.
_STOPS = [(0.0, (30, 115, 190)), (1.0, (74, 159, 212)), (2.0, (120, 190, 180)),
          (3.0, (252, 185, 0)), (6.0, (232, 89, 12)), (10.0, (200, 30, 30))]
_CLAMP = 10.0
MIN_RESIDUES = 10          # below this a ribbon is meaningless (short peptides)


def dev_color(d: float) -> tuple[int, int, int]:
    d = max(0.0, min(float(d), _CLAMP))
    for (a, ca), (b, cb) in zip(_STOPS, _STOPS[1:]):
        if d <= b:
            t = 0.0 if b == a else (d - a) / (b - a)
            return tuple(round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
    return _STOPS[-1][1]


def ribbon_path(entity_id: str) -> Path:
    return config.RIBBON_DIR / f"{entity_id}.svg"


def has_ribbon(entity_id: str) -> bool:
    return ribbon_path(entity_id).exists()


def _catmull_rom(pts: np.ndarray, samples: int = 8):
    """Smooth polyline through pts; returns densified points and the fractional residue index
    of each so colour/width can be looked up per sub-segment."""
    pts = np.asarray(pts, float)
    n = len(pts)
    if n < 3:
        return pts, np.arange(n, dtype=float)
    out, par = [], []
    ext = np.vstack([pts[0], pts, pts[-1]])
    for i in range(n - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            pt = 0.5 * ((2 * p1) + (-p0 + p2) * t
                        + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                        + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(pt)
            par.append(i + t)
    out.append(pts[-1])
    par.append(float(n - 1))
    return np.array(out), np.array(par)


def build_svg(P: np.ndarray, dev, sse, width: int = 520, height: int = 440,
              samples: int = 3, af_ca=None) -> str:
    """Transparent, text-free ribbon SVG from aligned experimental Cα coords `P` (N,3),
    per-residue deviation `dev` and secondary structure `sse` ('a'/'b'/'c'). Kept compact
    (integer coords, modest smoothing) so it is small enough to store per-entity and serve
    many-per-page: a few hundred coloured segments, ~15-30 KB, gzips to a few KB."""
    P = np.asarray(P, float)
    dev = np.asarray(dev, float)
    n = len(P)
    # PCA -> best-spread 2D view; keep the 3rd component for depth cueing.
    mean = P.mean(0)
    C = P - mean
    _u, _s, Vt = np.linalg.svd(C, full_matrices=False)
    proj = C @ Vt.T
    xy, z = proj[:, :2], proj[:, 2]

    # The superposed AlphaFold Cα trace, projected onto the SAME axes so it overlays the exp.
    af_xy = None
    if af_ca is not None and len(af_ca):
        af_xy = ((np.asarray(af_ca, float) - mean) @ Vt.T)[:, :2]

    pad = 26
    fit_pts = xy if af_xy is None else np.vstack([xy, af_xy])   # fit view to both so neither clips
    mn, mx = fit_pts.min(0), fit_pts.max(0)
    span = mx - mn
    span[span == 0] = 1.0
    sc = min((width - 2 * pad) / span[0], (height - 2 * pad) / span[1])
    off = np.array([pad + (width - 2 * pad - span[0] * sc) / 2 - mn[0] * sc,
                    pad + (height - 2 * pad - span[1] * sc) / 2 - mn[1] * sc])
    Q2 = xy * sc + off
    Q2[:, 1] = height - Q2[:, 1]                 # flip y to screen space
    zmin, zmax = z.min(), z.max()
    zr = (zmax - zmin) or 1.0

    # Faint AlphaFold ghost trace (drawn first, behind the coloured experimental ribbon).
    ghost = ""
    if af_xy is not None:
        A2 = af_xy * sc + off
        A2[:, 1] = height - A2[:, 1]
        dense_a, _pa = _catmull_rom(A2, samples=samples)
        d = "M" + "L".join(f"{p[0]:.0f} {p[1]:.0f}" for p in dense_a)
        ghost = (f'<path d="{d}" stroke="#2563eb" stroke-width="1.8" stroke-linecap="round" '
                 f'stroke-linejoin="round" opacity="0.5" stroke-dasharray="1 5"/>')

    dense, par = _catmull_rom(Q2, samples=samples)
    seg = []
    for k in range(len(dense) - 1):
        ri = min(int(round(par[k])), n - 1)
        ss = sse[ri] if ri < len(sse) else "c"
        base_w = 6.6 if ss in ("a", "b") else 3.4     # SSE-aware: helix/strand fatter, coil thin
        zf = (z[ri] - zmin) / zr                       # 0 back .. 1 front
        seg.append((z[ri], dense[k], dense[k + 1], dev_color(dev[ri]),
                    round(base_w * (0.72 + 0.36 * zf), 1), round(0.5 + 0.5 * zf, 2)))
    seg.sort(key=lambda s: s[0])                        # paint back-to-front
    # Group by (colour,width,opacity) into <path> elements -- far fewer, smaller elements than
    # one <line> per segment. Integer coords keep it compact.
    from collections import defaultdict
    groups = defaultdict(list)
    for _z, a, b, col, w, op in seg:
        groups[(col, w, op)].append((a, b))
    parts = []
    for (col, w, op), segs in sorted(groups.items(), key=lambda kv: kv[0][2]):  # low opacity (back) first
        d = "".join(f"M{a[0]:.0f} {a[1]:.0f}L{b[0]:.0f} {b[1]:.0f}" for a, b in segs)
        parts.append(f'<path d="{d}" stroke="rgb{col}" stroke-width="{w}" '
                     f'stroke-linecap="round" opacity="{op}"/>')
    nt, ct = Q2[0], Q2[-1]
    termini = (f'<circle cx="{nt[0]:.0f}" cy="{nt[1]:.0f}" r="4" fill="none" stroke="#5b6b7a" stroke-width="1.5"/>'
               f'<circle cx="{ct[0]:.0f}" cy="{ct[1]:.0f}" r="4" fill="#5b6b7a"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'preserveAspectRatio="xMidYMid meet" role="img" fill="none" '
            f'aria-label="Experimental Cα ribbon coloured by deviation from the AlphaFold model, '
            f'with the superposed AlphaFold backbone as a faint dashed trace">'
            f'{ghost}{"".join(parts)}{termini}</svg>')


def render_for_chains(exp_chain, af_chain) -> Optional[str]:
    """Compute the aligned frame + per-residue deviation from two loaded chains (mirrors the
    pipeline superposition) and return a ribbon SVG, or None if too few residues align."""
    ei, ai = compare.match_residues(exp_chain, af_chain)
    if len(ei) < MIN_RESIDUES:
        return None
    P = exp_chain.ca_coords[ei]
    Q = af_chain.ca_coords[ai]
    aligned, _R = compare._kabsch(Q, P)          # AF matched Cα superposed into the exp frame
    dev = np.linalg.norm(P - aligned, axis=1)
    sse = [exp_chain.residues[i].sse for i in ei]
    return build_svg(P, dev, sse, af_ca=aligned)


_ONE_TO_THREE = {
    "A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN", "E": "GLU",
    "G": "GLY", "H": "HIS", "I": "ILE", "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE",
    "P": "PRO", "S": "SER", "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL",
}
_BACKBONE = ("N", "CA", "C", "O")


def _atom_lines(residues, dev_by_idx, start_serial=1):
    """Backbone ATOM records: B-factor = Cα deviation (clamped; -1 sentinel if none). Exact PDB
    columns so 3Dmol parses residues/chain cleanly. Secondary structure travels in the
    HELIX/SHEET records (parsed client-side to set atom.ss for the cartoon)."""
    lines, serial = [], start_serial
    for idx, res in enumerate(residues):
        b = min(dev_by_idx.get(idx, -1.0), _CLAMP)
        resn = _ONE_TO_THREE.get(res.letter, "UNK")
        for atom in _BACKBONE:
            xyz = res.atoms.get(atom)
            if xyz is None:
                continue
            name = f" {atom:<3s}"
            lines.append(
                "ATOM  %5d %4s%1s%3s %1s%4d%1s   %8.3f%8.3f%8.3f%6.2f%6.2f          %2s" % (
                    serial, name, " ", resn, "A", res.res_id, " ",
                    xyz[0], xyz[1], xyz[2], 1.00, b, atom[0]))
            serial += 1
    return lines


def coords_path(entity_id: str) -> Path:
    return config.RIBBON_DIR / f"{entity_id}.pdb"


def has_coords(entity_id: str) -> bool:
    return coords_path(entity_id).exists()


def ghost_path(entity_id: str) -> Path:
    return config.RIBBON_DIR / f"{entity_id}.af.pdb"


def has_ghost(entity_id: str) -> bool:
    return ghost_path(entity_id).exists()


def _ss_runs(residues, code: str):
    """Contiguous (start_res, end_res) runs of a given SSE code within a residue list."""
    runs, start = [], None
    for i, r in enumerate(residues):
        if r.sse == code and start is None:
            start = i
        elif r.sse != code and start is not None:
            runs.append((residues[start], residues[i - 1]))
            start = None
    if start is not None:
        runs.append((residues[start], residues[-1]))
    return runs


def _ss_records(residues) -> list:
    """HELIX/SHEET records (exact PDB columns) from the per-residue SSE. Kept as a standard
    fallback; the viewer primarily uses the occupancy-encoded SSE (see _atom_lines)."""
    lines = []
    for n, (a, b) in enumerate(_ss_runs(residues, "a"), 1):
        ra, rb = _ONE_TO_THREE.get(a.letter, "UNK"), _ONE_TO_THREE.get(b.letter, "UNK")
        lines.append("HELIX  %3d %3d %3s %1s %4d  %3s %1s %4d  1" % (n, n, ra, "A", a.res_id, rb, "A", b.res_id))
    for n, (a, b) in enumerate(_ss_runs(residues, "b"), 1):
        ra, rb = _ONE_TO_THREE.get(a.letter, "UNK"), _ONE_TO_THREE.get(b.letter, "UNK")
        lines.append("SHEET  %3d %3s%2d %3s %1s%4d  %3s %1s%4d  0" % (n, "A", 1, ra, "A", a.res_id, rb, "A", b.res_id))
    return lines


def build_coords_pdb(exp_chain, af_chain) -> Optional[str]:
    """A minimal backbone PDB of the experimental chain with the per-residue Cα deviation
    written into the B-factor column (clamped to _CLAMP Å). The interactive 3Dmol viewer loads
    this and colours the cartoon by B-factor with the same scale as the static ribbon. Only the
    residues matched to the AlphaFold model carry a deviation; the rest get a negative sentinel."""
    ei, ai = compare.match_residues(exp_chain, af_chain)
    if len(ei) < MIN_RESIDUES:
        return None
    P = exp_chain.ca_coords[ei]
    Q = af_chain.ca_coords[ai]
    aligned, _R = compare._kabsch(Q, P)
    dev = np.linalg.norm(P - aligned, axis=1)
    dev_by_idx = {int(i): float(d) for i, d in zip(ei, dev)}
    lines = _ss_records(exp_chain.residues) + _atom_lines(exp_chain.residues, dev_by_idx)
    lines.append("END")
    return "\n".join(lines) + "\n"


def build_af_ghost_pdb(exp_chain, af_chain) -> Optional[str]:
    """The AlphaFold model backbone, transformed into the experiment's superposition frame
    (using the same matched-Cα Kabsch fit), as a plain grey ghost for the paired 3D view.
    No deviation colouring; occupancy still carries the model's SSE for cartoon rendering."""
    ei, ai = compare.match_residues(exp_chain, af_chain)
    if len(ei) < MIN_RESIDUES:
        return None
    P = exp_chain.ca_coords[ei]
    Q = af_chain.ca_coords[ai]
    _aligned, R = compare._kabsch(Q, P)
    qc, pc = Q.mean(0), P.mean(0)

    # Apply the fitted transform to every AF backbone atom, in place, then emit.
    import copy
    moved = []
    for res in af_chain.residues:
        r2 = copy.copy(res)
        r2.atoms = {name: ((xyz - qc) @ R.T) + pc for name, xyz in res.atoms.items()}
        moved.append(r2)
    lines = _ss_records(moved) + _atom_lines(moved, {})   # no deviation -> all sentinel
    lines.append("END")
    return "\n".join(lines) + "\n"


def write_ribbon(entity_id: str, svg: str) -> Path:
    config.RIBBON_DIR.mkdir(parents=True, exist_ok=True)
    p = ribbon_path(entity_id)
    p.write_text(svg, encoding="utf-8")
    return p


def render_and_store_all(entity_id: str, exp_chain, af_chain) -> bool:
    """Render + persist BOTH the static ribbon SVG and the interactive-viewer backbone PDB.
    Never raises. Returns True if at least the SVG was written."""
    ok = render_and_store(entity_id, exp_chain, af_chain)
    try:
        pdb_str = build_coords_pdb(exp_chain, af_chain)
        if pdb_str:
            coords_path(entity_id).write_text(pdb_str, encoding="utf-8")
    except Exception:
        pass
    try:
        ghost = build_af_ghost_pdb(exp_chain, af_chain)
        if ghost:
            ghost_path(entity_id).write_text(ghost, encoding="utf-8")
    except Exception:
        pass
    return ok


def render_and_store(entity_id: str, exp_chain, af_chain) -> bool:
    """Render + persist a ribbon for one entity. Returns True on success. Never raises --
    a missing ribbon must never fail a comparison."""
    try:
        svg = render_for_chains(exp_chain, af_chain)
        if not svg:
            return False
        write_ribbon(entity_id, svg)
        return True
    except Exception:
        return False
