"""The metric suite: given an experimental chain and its AlphaFold model, quantify how
much the prediction disagrees with the experiment.

Residue correspondence is established by a global sequence alignment of the two chains
(they are the *same* protein, so this is the right frame -- it naturally handles missing
loops as gaps, engineered point mutations as mismatches, tags, and >2700 aa fragments).
Everything downstream operates on the matched residue pairs.

Metric families (all pure-numpy except TM-score via tmtools):
  * global superposition  -- TM-score (4 normalizations), RMSD (CA/backbone/all-atom/core),
                             GDT_TS, GDT_HA, MaxSub, structural-overlap
  * local, superposition-free -- lDDT (+per-residue), contact-map overlap, distance-matrix
                             difference, CAD-score (contact-area difference, approx)
  * backbone              -- secondary-structure agreement (Q3), phi/psi differences
  * domains               -- per-CATH-domain and per-PAE-cluster-domain TM/RMSD, Rg
  * calibration           -- pLDDT vs actual-lDDT correlation, PAE honesty
  * composite             -- FRAUD score, confidently_wrong
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from biotite.sequence import ProteinSequence
from biotite.sequence.align import SubstitutionMatrix, align_optimal
from scipy.sparse.csgraph import connected_components
from scipy.stats import pearsonr, spearmanr

from . import config
from .structio import Chain

_STD_AA = set("ACDEFGHIKLMNPQRSTVWY")
_BLOSUM = SubstitutionMatrix.std_protein_matrix()

# tmtools wraps the TM-align C code, which uses static/global buffers and is NOT
# thread-safe -- concurrent calls from the backfill's worker threads deadlock. TM-align
# runs in milliseconds, so serialising just this call costs nothing while the real
# bottleneck (per-entity downloads) still runs fully in parallel.
_TMALIGN_LOCK = threading.Lock()


# --------------------------------------------------------------------------------------
# Result container
# --------------------------------------------------------------------------------------
@dataclass
class Comparison:
    metrics: dict = field(default_factory=dict)          # scalar metrics (JSON-friendly)
    per_residue: dict = field(default_factory=dict)      # arrays keyed by name
    domains: list = field(default_factory=list)          # per-domain metric dicts
    heatmaps: dict = field(default_factory=dict)         # downsampled 2D data for the report


# --------------------------------------------------------------------------------------
# Residue matching + superposition
# --------------------------------------------------------------------------------------
def _sanitize(seq: str) -> str:
    return "".join(c if c in _STD_AA else "X" for c in seq)


def match_residues(exp: Chain, af: Chain) -> tuple[np.ndarray, np.ndarray]:
    """Indices into exp.residues and af.residues for aligned (non-gap) positions."""
    s1 = ProteinSequence(_sanitize(exp.sequence))
    s2 = ProteinSequence(_sanitize(af.sequence))
    aln = align_optimal(s1, s2, _BLOSUM, gap_penalty=(-10, -1), terminal_penalty=False)[0]
    trace = aln.trace
    keep = (trace[:, 0] >= 0) & (trace[:, 1] >= 0)
    return trace[keep, 0], trace[keep, 1]


def _kabsch(mobile: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rotate+translate `mobile` onto `target` (least-squares). Returns (aligned, R)."""
    mc, tc = mobile.mean(0), target.mean(0)
    M, T = mobile - mc, target - tc
    U, _s, Vt = np.linalg.svd(M.T @ T)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    return (M @ R.T) + tc, R


def _d0(length: int) -> float:
    if length <= 15:
        return 0.5
    return 1.24 * (length - 15) ** (1.0 / 3.0) - 1.8


# --------------------------------------------------------------------------------------
# Global metrics
# --------------------------------------------------------------------------------------
def _tm_scores(exp: Chain, af: Chain) -> dict:
    import tmtools

    with _TMALIGN_LOCK:
        res = tmtools.tm_align(exp.ca_coords, af.ca_coords, _sanitize(exp.sequence), _sanitize(af.sequence))
    by_exp = float(res.tm_norm_chain1)
    by_af = float(res.tm_norm_chain2)
    return {
        "tm_by_experiment": round(by_exp, 4),
        "tm_by_model": round(by_af, 4),
        "tm_by_shorter": round(max(by_exp, by_af), 4),
        "tm_by_longer": round(min(by_exp, by_af), 4),
        "tmalign_rmsd": round(float(res.rmsd), 3),
    }


def screen(exp: Chain, af: Chain, mean_plddt: Optional[float]) -> dict:
    """Tier-1 screen: TM-score only (one TM-align), plus a cheap proxy FRAUD and the
    confidently-wrong flag from mean pLDDT alone. No PAE, novelty, domains or O(n^2)
    metrics -- fast enough to run across the whole archive. Tier 2 recomputes the true
    FRAUD (per-residue, confidence-weighted) only for the disagreements this surfaces."""
    tm = _tm_scores(exp, af)
    tm_exp = tm["tm_by_experiment"]
    proxy_fraud = round((mean_plddt / 100.0) * (1.0 - tm_exp), 4) if mean_plddt is not None else None
    confidently_wrong = bool(
        mean_plddt is not None and mean_plddt > config.CONFIDENT_PLDDT and tm_exp < config.WRONG_TM
    )
    return {**tm, "mean_plddt": mean_plddt, "fraud_score": proxy_fraud,
            "confidently_wrong": confidently_wrong}


def _gdt(dev: np.ndarray, thresholds) -> float:
    return float(np.mean([np.mean(dev <= t) for t in thresholds]) * 100.0)


def _self_tm(dev: np.ndarray, length: int) -> float:
    d0 = _d0(length)
    return float(np.mean(1.0 / (1.0 + (dev / d0) ** 2)))


def _core_rmsd(P: np.ndarray, Q: np.ndarray, iterations: int = 5) -> tuple[float, np.ndarray]:
    """RMSD after iteratively rejecting the worst-fitting residues (well-modeled core)."""
    idx = np.arange(len(P))
    dev = None
    for _ in range(iterations):
        aligned, _R = _kabsch(Q[idx], P[idx])
        d = np.linalg.norm(P[idx] - aligned, axis=1)
        cutoff = max(2.0, np.percentile(d, 75))
        keep = d <= cutoff
        if keep.sum() < max(10, 0.3 * len(P)) or keep.all():
            idx = idx[keep]
            break
        idx = idx[keep]
    aligned_full, _R = _kabsch(Q[idx], P[idx])
    dev = np.linalg.norm(P[idx] - aligned_full, axis=1)
    return float(np.sqrt((dev ** 2).mean())), idx


# --------------------------------------------------------------------------------------
# Local, superposition-free metrics
# --------------------------------------------------------------------------------------
def _lddt(P: np.ndarray, Q: np.ndarray) -> tuple[float, np.ndarray]:
    """CA-based lDDT (global + per-residue). P=target(exp), Q=model(af), matched order."""
    n = len(P)
    Dt = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=-1)
    Dm = np.linalg.norm(Q[:, None, :] - Q[None, :, :], axis=-1)
    mask = (Dt < config.LDDT_INCLUSION_RADIUS) & (~np.eye(n, dtype=bool))
    diff = np.abs(Dt - Dm)
    preserved = np.zeros((n, n))
    for t in config.LDDT_THRESHOLDS:
        preserved += (diff < t)
    preserved /= len(config.LDDT_THRESHOLDS)
    per_res = np.array([
        preserved[i, mask[i]].mean() if mask[i].any() else np.nan for i in range(n)
    ])
    global_lddt = float(np.nanmean(per_res))
    return global_lddt, per_res


def _contacts(coords: np.ndarray, cutoff=8.0, seq_sep=6) -> np.ndarray:
    n = len(coords)
    D = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=-1)
    sep = np.abs(np.arange(n)[:, None] - np.arange(n)[None, :]) >= seq_sep
    return (D < cutoff) & sep


def _contact_overlap(P: np.ndarray, Q: np.ndarray) -> dict:
    cp, cq = _contacts(P), _contacts(Q)
    iu = np.triu_indices(len(P), k=1)
    a, b = cp[iu], cq[iu]
    inter = np.sum(a & b)
    union = np.sum(a | b)
    tp = inter
    return {
        "contact_jaccard": round(float(inter / union) if union else 1.0, 4),
        "contact_precision": round(float(tp / b.sum()) if b.sum() else 0.0, 4),
        "contact_recall": round(float(tp / a.sum()) if a.sum() else 0.0, 4),
    }


def _distance_matrix_diff(P: np.ndarray, Q: np.ndarray) -> tuple[float, np.ndarray]:
    Dt = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=-1)
    Dm = np.linalg.norm(Q[:, None, :] - Q[None, :, :], axis=-1)
    diff = np.abs(Dt - Dm)
    mean_diff = float(diff[np.triu_indices(len(P), k=1)].mean())
    return mean_diff, diff


def _cad_score(exp: Chain, af: Chain, ei: np.ndarray, ai: np.ndarray) -> float:
    """Contact-area-difference score (approx): residue-residue 'contact area' estimated by
    the count of inter-residue atom pairs within 4.5 A. CAD = sum|min(M,T)-T|/sum T over
    contacting pairs; score = 1-CAD, clamped to [0,1]. A pragmatic stand-in for Voronoi CAD.
    """
    cutoff = 4.5
    exp_atoms = [np.array(list(exp.residues[i].atoms.values())) for i in ei]
    af_atoms = [np.array(list(af.residues[j].atoms.values())) for j in ai]

    def areas(atoms_list):
        n = len(atoms_list)
        A = np.zeros((n, n))
        cen = np.array([a.mean(0) for a in atoms_list])
        near = np.linalg.norm(cen[:, None] - cen[None, :], axis=-1) < 15.0
        for i in range(n):
            for j in range(i + 1, n):
                if not near[i, j]:
                    continue
                d = np.linalg.norm(atoms_list[i][:, None, :] - atoms_list[j][None, :, :], axis=-1)
                c = int(np.sum(d < cutoff))
                if c:
                    A[i, j] = A[j, i] = c
        return A

    T = areas(exp_atoms)
    M = areas(af_atoms)
    iu = np.triu_indices(len(ei), k=1)
    t, m = T[iu], M[iu]
    contact = t > 0
    if not contact.any():
        return 1.0
    cad = np.sum(np.abs(np.minimum(m[contact], t[contact]) - t[contact])) / np.sum(t[contact])
    return round(float(max(0.0, 1.0 - cad)), 4)


# --------------------------------------------------------------------------------------
# Backbone metrics
# --------------------------------------------------------------------------------------
def _ss_agreement(exp: Chain, af: Chain, ei, ai) -> float:
    same = [exp.residues[i].sse == af.residues[j].sse for i, j in zip(ei, ai)]
    return round(float(np.mean(same) * 100.0), 2)


def _torsion_diffs(exp: Chain, af: Chain, ei, ai) -> tuple[dict, np.ndarray]:
    def circ(a, b):
        d = np.abs(a - b) % (2 * math.pi)
        return np.minimum(d, 2 * math.pi - d)

    dphi, dpsi = [], []
    per_res = []
    for i, j in zip(ei, ai):
        p1, p2 = exp.residues[i].phi, af.residues[j].phi
        s1, s2 = exp.residues[i].psi, af.residues[j].psi
        dp = circ(p1, p2) if not (math.isnan(p1) or math.isnan(p2)) else np.nan
        ds = circ(s1, s2) if not (math.isnan(s1) or math.isnan(s2)) else np.nan
        dphi.append(dp)
        dpsi.append(ds)
        per_res.append(np.nanmean([dp, ds]))
    dphi, dpsi = np.array(dphi), np.array(dpsi)
    tol = math.radians(30)
    within = np.mean((dphi < tol) & (dpsi < tol))
    return (
        {
            "mean_phi_diff_deg": round(float(np.degrees(np.nanmean(dphi))), 1),
            "mean_psi_diff_deg": round(float(np.degrees(np.nanmean(dpsi))), 1),
            "torsion_within_30deg_frac": round(float(within), 4),
        },
        np.degrees(np.array(per_res, dtype=float)),
    )


# --------------------------------------------------------------------------------------
# Domain decomposition
# --------------------------------------------------------------------------------------
def pae_domains(pae: np.ndarray, cutoff: float = 10.0, min_size: int = 25) -> list[tuple[int, int]]:
    """Split residues into domains by PAE connectivity (symmetrized PAE < cutoff), returned
    as contiguous (start,end) UniProt/model ranges. Needs no external annotation."""
    n = pae.shape[0]
    sym = np.minimum(pae, pae.T)
    adj = sym < cutoff
    ncomp, labels = connected_components(adj, directed=False)
    ranges = []
    for c in range(ncomp):
        idx = np.where(labels == c)[0]
        if len(idx) < min_size:
            continue
        ranges.append((int(idx.min()) + 1, int(idx.max()) + 1))   # 1-based, model numbering
    return sorted(ranges)


def _domain_metrics(label, beg, end, ei, ai, af_resid, P, Q) -> Optional[dict]:
    """TM/RMSD restricted to matched residues whose AF residue number is in [beg,end]."""
    sel = [k for k in range(len(ai)) if beg <= af_resid[ai[k]] <= end]
    if len(sel) < 10:
        return None
    Ps, Qs = P[sel], Q[sel]
    aligned, _R = _kabsch(Qs, Ps)
    dev = np.linalg.norm(Ps - aligned, axis=1)
    rmsd = float(np.sqrt((dev ** 2).mean()))
    return {
        "label": label,
        "range": f"{beg}-{end}",
        "n_residues": len(sel),
        "rmsd": round(rmsd, 3),
        "tm": round(_self_tm(dev, len(sel)), 4),
        "mean_ca_dev": round(float(dev.mean()), 3),
    }


# --------------------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------------------
def _calibration(plddt: np.ndarray, per_res_lddt: np.ndarray) -> dict:
    m = ~np.isnan(plddt) & ~np.isnan(per_res_lddt)
    if m.sum() < 5:
        return {"plddt_lddt_pearson": None, "plddt_lddt_spearman": None}
    return {
        "plddt_lddt_pearson": round(float(pearsonr(plddt[m], per_res_lddt[m] * 100)[0]), 4),
        "plddt_lddt_spearman": round(float(spearmanr(plddt[m], per_res_lddt[m])[0]), 4),
    }


def _pae_honesty(pae: np.ndarray, ai, P, Q) -> tuple[dict, dict]:
    """Compare AlphaFold's self-reported PAE to the frame-invariant observed error
    (|distance_exp - distance_af|) over matched residue pairs. Low correlation / many
    pairs where observed >> PAE = overconfident = 'dishonest'."""
    sub = np.array([ai[k] for k in range(len(ai))])
    pae_sub = pae[np.ix_(sub, sub)]
    Dt = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=-1)
    Dm = np.linalg.norm(Q[:, None, :] - Q[None, :, :], axis=-1)
    observed = np.abs(Dt - Dm)
    iu = np.triu_indices(len(sub), k=1)
    pv, ov = pae_sub[iu], observed[iu]
    corr = float(pearsonr(pv, ov)[0]) if len(pv) > 5 and pv.std() > 0 else None
    overconf = float(np.mean(ov > (pae_sub[iu] + 2.0)))   # observed exceeds PAE by >2 A
    metrics = {
        "pae_observed_pearson": round(corr, 4) if corr is not None else None,
        "pae_overconfident_frac": round(overconf, 4),
        "mean_pae": round(float(pae_sub.mean()), 3),
        "mean_observed_error": round(float(observed.mean()), 3),
    }
    heat = {"pae": _downsample(pae_sub), "observed": _downsample(observed)}
    return metrics, heat


# --------------------------------------------------------------------------------------
# Helpers for the report
# --------------------------------------------------------------------------------------
def _downsample(mat: np.ndarray, cap: int = 200) -> list:
    n = mat.shape[0]
    if n <= cap:
        return np.round(mat, 2).tolist()
    idx = np.linspace(0, n - 1, cap).astype(int)
    return np.round(mat[np.ix_(idx, idx)], 2).tolist()


def load_pae(path: Optional[Path], n_model: int) -> Optional[np.ndarray]:
    if not path or not Path(path).exists():
        return None
    data = json.loads(Path(path).read_text())
    entry = data[0] if isinstance(data, list) else data
    key = "predicted_aligned_error" if "predicted_aligned_error" in entry else "pae"
    pae = np.array(entry.get(key, []), dtype=float)
    return pae if pae.ndim == 2 and pae.shape[0] == pae.shape[1] else None


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------
def compare(exp: Chain, af: Chain, pae: Optional[np.ndarray] = None,
            cath_domains=None) -> Comparison:
    """Run the full metric suite on one experimental chain vs its AlphaFold model."""
    ei, ai = match_residues(exp, af)
    if len(ei) < 10:
        raise ValueError(f"only {len(ei)} residues aligned -- refusing to compare")

    P = exp.ca_coords[ei]
    Q = af.ca_coords[ai]
    af_resid = np.array([r.res_id for r in af.residues])
    plddt = np.array([af.residues[j].plddt if af.residues[j].plddt is not None else np.nan for j in ai])

    aligned, _R = _kabsch(Q, P)
    dev = np.linalg.norm(P - aligned, axis=1)

    m: dict = {}
    m.update(_tm_scores(exp, af))
    m["ca_rmsd"] = round(float(np.sqrt((dev ** 2).mean())), 3)
    m["backbone_rmsd"] = round(_multi_atom_rmsd(exp, af, ei, ai, ("N", "CA", "C", "O")), 3)
    m["all_atom_rmsd"] = round(_multi_atom_rmsd(exp, af, ei, ai, None), 3)
    core_rmsd, core_idx = _core_rmsd(P, Q)
    m["core_rmsd"] = round(core_rmsd, 3)
    m["core_fraction"] = round(len(core_idx) / len(P), 3)
    m["gdt_ts"] = round(_gdt(dev, (1, 2, 4, 8)), 2)
    m["gdt_ha"] = round(_gdt(dev, (0.5, 1, 2, 4)), 2)
    m["maxsub"] = round(_self_tm(dev[dev <= 3.5], len(P)) if np.any(dev <= 3.5) else 0.0, 4)
    m["structural_overlap_3_5"] = round(float(np.mean(dev <= 3.5)), 4)

    global_lddt, per_res_lddt = _lddt(P, Q)
    m["lddt"] = round(global_lddt, 4)
    m.update(_contact_overlap(P, Q))
    dm_mean, dm = _distance_matrix_diff(P, Q)
    m["distance_matrix_mean_diff"] = round(dm_mean, 3)
    m["cad_score"] = _cad_score(exp, af, ei, ai)

    m["ss_agreement_q3"] = _ss_agreement(exp, af, ei, ai)
    tor, per_res_tor = _torsion_diffs(exp, af, ei, ai)
    m.update(tor)

    m["radius_of_gyration_exp"] = round(_rg(P), 2)
    m["radius_of_gyration_model"] = round(_rg(Q), 2)
    m["radius_of_gyration_diff"] = round(abs(_rg(P) - _rg(Q)), 2)

    m["coverage_of_model"] = round(len(ai) / len(af.residues), 4)
    m["coverage_of_experiment"] = round(len(ei) / len(exp.residues), 4)
    m["sequence_identity_aligned"] = round(
        float(np.mean([exp.residues[i].letter == af.residues[j].letter for i, j in zip(ei, ai)])) * 100, 2
    )
    valid_plddt = plddt[~np.isnan(plddt)]
    m["mean_plddt"] = round(float(valid_plddt.mean()), 2) if valid_plddt.size else None

    m.update(_calibration(plddt, per_res_lddt))

    heatmaps: dict = {"distance_diff": _downsample(dm)}
    if pae is not None:
        pae_metrics, pae_heat = _pae_honesty(pae, ai, P, Q)
        m.update(pae_metrics)
        heatmaps.update(pae_heat)

    # Composite headline metrics.
    dev_c = np.clip(dev, 0, 15) / 15.0
    plddt_w = np.where(np.isnan(plddt), 0.0, plddt / 100.0)
    m["fraud_score"] = round(float(np.mean(plddt_w * dev_c)), 4)
    m["confidently_wrong_frac"] = round(
        float(np.mean((plddt > 70) & (dev > 4)) if valid_plddt.size else 0.0), 4
    )
    m["confidently_wrong"] = bool(
        (m["mean_plddt"] or 0) > config.CONFIDENT_PLDDT and m["tm_by_experiment"] < config.WRONG_TM
    )

    # Domains: PAE clusters (always) + CATH (when annotated).
    domains = []
    if pae is not None:
        for beg, end in pae_domains(pae):
            d = _domain_metrics(f"PAE:{beg}-{end}", beg, end, ei, ai, af_resid, P, Q)
            if d:
                d["source"] = "PAE"
                domains.append(d)
    for dom in cath_domains or []:
        # CATH ranges are in entity numbering; map to model residues via matched pairs.
        d = _domain_metrics(dom.domain_id, dom.beg, dom.end, ei, ai, af_resid, P, Q)
        if d:
            d["source"] = "CATH"
            d["name"] = dom.name
            domains.append(d)

    per_residue = {
        "af_res_id": [int(af_resid[j]) for j in ai],
        "ca_deviation": np.round(dev, 3).tolist(),
        "lddt": np.round(np.nan_to_num(per_res_lddt, nan=0.0), 4).tolist(),
        "plddt": [None if np.isnan(x) else round(float(x), 1) for x in plddt],
        "torsion_diff_deg": np.round(np.nan_to_num(per_res_tor, nan=0.0), 1).tolist(),
        "mutation": [exp.residues[i].letter != af.residues[j].letter for i, j in zip(ei, ai)],
    }
    return Comparison(metrics=m, per_residue=per_residue, domains=domains, heatmaps=heatmaps)


def _multi_atom_rmsd(exp: Chain, af: Chain, ei, ai, atom_names) -> float:
    """RMSD over shared atoms of matched residues, in the CA-superposed frame."""
    P_ca = exp.ca_coords[ei]
    Q_ca = af.ca_coords[ai]
    _aligned, R = _kabsch(Q_ca, P_ca)
    mc, tc = Q_ca.mean(0), P_ca.mean(0)
    p_list, q_list = [], []
    for i, j in zip(ei, ai):
        ea, aa = exp.residues[i].atoms, af.residues[j].atoms
        names = (atom_names if atom_names else set(ea) & set(aa))
        for name in names:
            if name in ea and name in aa:
                p_list.append(ea[name])
                q_list.append((aa[name] - mc) @ R.T + tc)
    if not p_list:
        return float("nan")
    P = np.array(p_list)
    Q = np.array(q_list)
    return float(np.sqrt(((P - Q) ** 2).sum(axis=1).mean()))


def _rg(coords: np.ndarray) -> float:
    c = coords - coords.mean(0)
    return float(np.sqrt((c ** 2).sum(axis=1).mean()))
