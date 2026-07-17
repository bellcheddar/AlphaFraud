"""The Analysis deep-dive engine: enrich the compared set with structural classification,
family and citation metadata, then aggregate it into a single cached snapshot the web app
renders (fold-class enrichment with statistics, sequence-similarity clustering, failure-mode
embedding, theme flags, correlates, conformational-heterogeneity, per-superfamily scorecards,
and the weekly highlight). All compute lives here; the web app just reads the snapshot.

Run via `AlphaFraud.py analyze` (enrich + rebuild snapshot); wired to run after each pipeline
run. Nothing here re-downloads coordinates.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from . import annotate, banner, config, db

# --------------------------------------------------------------------------------------
# Theme flags (from stored metrics + fetched annotation + text)
# --------------------------------------------------------------------------------------
_AMYLOID_RE = re.compile(
    r"amyloid|fibril|prion|transthyretin|superoxide dismutase|\bsod1\b|"
    r"beta-2-microglobulin|microglobulin|islet amyloid|\biapp\b|synuclein|serum amyloid|"
    r"\btau\b|huntingtin|polyglutamine|gelsolin|\bhet-s\b", re.I)
_COIL_RE = re.compile(r"coiled.?coil|tropomyosin|spectrin|intermediate filament|\bSNARE\b", re.I)
_ENG_RE = re.compile(r"de novo|designed|engineered|nanobody|scaffold|minibinder|chimera|fusion protein", re.I)
_IDR_RE = re.compile(r"intrinsically disordered|\bidr\b|disorder", re.I)


def compute_flags(entity: dict, ann: dict) -> dict:
    m = json.loads(entity.get("metrics_json") or "{}")
    text = " ".join(filter(None, [entity.get("description"), entity.get("uniprot_name"),
                                  ann.get("citation_title")]))
    rg_diff = m.get("radius_of_gyration_diff") or 0
    ss_q3 = m.get("ss_agreement_q3")
    core_frac = m.get("core_fraction")
    n_chains = ann.get("n_chains") or 1
    is_amyloid = bool(_AMYLOID_RE.search(text)) or (rg_diff > 6 and ss_q3 is not None and ss_q3 < 45)
    is_coiled = bool(_COIL_RE.search(text)) or ("coiled" in (ann.get("ecod_family") or "").lower())
    is_engineered = bool(_ENG_RE.search(text)) or (bool(entity.get("is_novel")) and not entity.get("closest_pre_cutoff"))
    is_idr = bool(_IDR_RE.search(text)) or (core_frac is not None and core_frac < 0.45 and not is_amyloid)
    return {
        "is_amyloid": int(is_amyloid),
        "is_assembly": int((n_chains or 1) >= 4),
        "is_coiledcoil": int(is_coiled),
        "is_engineered": int(is_engineered),
        "is_idr": int(is_idr),
    }


# --------------------------------------------------------------------------------------
# Enrichment (fetch + flag + store)
# --------------------------------------------------------------------------------------
def enrich(limit: Optional[int] = None, batch: int = 200) -> int:
    """Fetch + store annotations for compared entities that lack them. Returns count enriched."""
    todo = db.compared_needing_annotation(limit=limit)
    if not todo:
        return 0
    banner.info(f"[analyze] enriching {len(todo)} compared entities…")
    done = 0
    for i in range(0, len(todo), batch):
        chunk = todo[i : i + batch]
        anns = annotate.fetch(chunk)
        by_id = {e["entity_id"]: e for e in chunk}
        for eid, a in anns.items():
            ad = {
                "sequence": a.sequence, "seq_length": a.seq_length,
                "cath_code": a.cath_code, "cath_class": a.cath_class, "cath_arch": a.cath_arch,
                "cath_topo": a.cath_topo, "cath_name": a.cath_name, "scop2_sf": a.scop2_sf,
                "ecod_family": a.ecod_family, "citation_doi": a.citation_doi,
                "citation_title": a.citation_title, "citation_journal": a.citation_journal,
                "citation_year": a.citation_year, "citation_pubmed": a.citation_pubmed,
                "n_chains": a.n_chains, "assembly_count": a.assembly_count,
            }
            flags = compute_flags(by_id[eid], {"n_chains": a.n_chains, "ecod_family": a.ecod_family,
                                               "citation_title": a.citation_title})
            db.upsert_annotation({
                "entity_id": eid, **ad, **flags,
                "pfam_json": json.dumps([p["id"] for p in a.pfam]),
                "go_json": json.dumps([g["id"] for g in a.go]),
            })
            done += 1
        banner.step(f"[analyze] enriched {min(i + batch, len(todo))}/{len(todo)}")
    return done


# --------------------------------------------------------------------------------------
# Statistics helpers
# --------------------------------------------------------------------------------------
def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Point estimate + Wilson 95% CI for a proportion k/n (returns fractions)."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def _fisher_p(a: int, b: int, c: int, d: int) -> Optional[float]:
    """One-sided (greater) Fisher exact p for the 2x2 [[a,b],[c,d]]."""
    try:
        from scipy.stats import fisher_exact
        return float(fisher_exact([[a, b], [c, d]], alternative="greater")[1])
    except Exception:
        return None


# --------------------------------------------------------------------------------------
# Aggregations
# --------------------------------------------------------------------------------------
THEMES = [("is_amyloid", "amyloid"), ("is_assembly", "large assembly"), ("is_idr", "disordered"),
          ("is_coiledcoil", "coiled-coil"), ("is_engineered", "engineered")]


def _enrichment(rows: list[dict], key: str, name_key: Optional[str] = None, min_n: int = 3) -> list[dict]:
    """CW-enrichment per category value of `key`. Returns rows sorted by lower-CI of CW-rate."""
    bg_total = len(rows)
    cw_total = sum(1 for r in rows if r["confidently_wrong"])
    by_val_bg, by_val_cw, label = Counter(), Counter(), {}
    for r in rows:
        v = r.get(key)
        if v in (None, ""):
            v = "unclassified"
        by_val_bg[v] += 1
        if r["confidently_wrong"]:
            by_val_cw[v] += 1
        if name_key and r.get(name_key):
            label.setdefault(v, r[name_key])
    out = []
    for v, n_bg in by_val_bg.items():
        if n_bg < min_n:
            continue
        n_cw = by_val_cw[v]
        rate, lo, hi = _wilson(n_cw, n_bg)
        base = cw_total / bg_total if bg_total else 0
        enr = (rate / base) if base else 0
        p = _fisher_p(n_cw, n_bg - n_cw, cw_total - n_cw, (bg_total - n_bg) - (cw_total - n_cw))
        out.append({
            "value": v, "label": label.get(v, v), "n_bg": n_bg, "n_cw": n_cw,
            "cw_rate": round(rate * 100, 1), "ci_lo": round(lo * 100, 1), "ci_hi": round(hi * 100, 1),
            "enrichment": round(enr, 2), "p": p,
        })
    out.sort(key=lambda d: (d["ci_lo"], d["n_cw"]), reverse=True)
    return out


def _cath_folds(rows: list[dict], cap: int = 12) -> dict:
    """Confidently-wrong structures grouped by CATH architecture.

    The overwhelming finding is that most confident failures have *no* CATH fold at all
    (amyloids, peptides, disordered regions), so we surface that as a headline stat and plot
    only the classified minority -- ranked, named, coloured by CATH class -- which is far more
    legible than a treemap dominated by one giant 'unclassified' tile of cryptic codes.
    """
    cw = [r for r in rows if r["confidently_wrong"]]
    total = len(cw)
    n_unclassified = sum(1 for r in cw if not r.get("cath_arch"))
    n_classified = total - n_unclassified

    by_arch = defaultdict(lambda: {"count": 0, "class": None, "topos": Counter()})
    for r in cw:
        arch = r.get("cath_arch")
        if not arch:
            continue
        b = by_arch[arch]
        b["count"] += 1
        b["class"] = r.get("cath_class")
        if r.get("cath_topo"):
            b["topos"][r["cath_topo"]] += 1

    bars = []
    for arch, b in by_arch.items():
        cls = b["class"]
        top_topo = b["topos"].most_common(1)[0][0] if b["topos"] else None
        bars.append({
            "code": arch,
            "label": annotate.cath_arch_label(arch),
            "class_code": cls,
            "class_name": annotate.CATH_CLASS_NAMES.get(cls, "unclassified"),
            "count": b["count"],
            "top_topo": top_topo,
        })
    bars.sort(key=lambda x: x["count"], reverse=True)
    return {
        "total_cw": total,
        "n_unclassified": n_unclassified,
        "pct_unclassified": round(100 * n_unclassified / total, 0) if total else 0,
        "n_classified": n_classified,
        "n_architectures": len(bars),
        "bars": bars[:cap],
    }


def _themes(rows: list[dict]) -> dict:
    cw = [r for r in rows if r["confidently_wrong"]]
    return {
        "cw_total": len(cw),
        "counts": [{"theme": name, "n": sum(1 for r in cw if r.get(col))} for col, name in THEMES],
    }


def _correlates(rows: list[dict]) -> dict:
    """CW-rate by method, resolution bin, length bin, novelty bin."""
    def rate_by(bucket_fn):
        bg, cw = Counter(), Counter()
        for r in rows:
            b = bucket_fn(r)
            if b is None:
                continue
            bg[b] += 1
            if r["confidently_wrong"]:
                cw[b] += 1
        return [{"bucket": b, "n": bg[b], "cw_rate": round(100 * cw[b] / bg[b], 1)} for b in bg]

    def res_bin(r):
        v = r.get("resolution")
        if v is None:
            return None
        for hi, lbl in [(1.5, "<1.5"), (2.0, "1.5-2"), (2.5, "2-2.5"), (3.0, "2.5-3"), (4.0, "3-4")]:
            if v < hi:
                return lbl
        return ">4"

    def len_bin(r):
        m = json.loads(r.get("metrics_json") or "{}")
        n = r.get("seq_length")
        if not n:
            return None
        for hi, lbl in [(100, "<100"), (200, "100-200"), (400, "200-400"), (800, "400-800")]:
            if n < hi:
                return lbl
        return ">800"

    def nov_bin(r):
        v = r.get("novelty_identity")
        if v is None:
            return None
        # bin on identity but label as novelty (= 100 - identity), high = novel
        for hi, lbl in [(30, "novel >70%"), (60, "40-70%"), (90, "10-40%")]:
            if v < hi:
                return lbl
        return "<10%"

    method_order = None
    return {
        "method": rate_by(lambda r: (r.get("method") or None)),
        "resolution": rate_by(res_bin),
        "length": rate_by(len_bin),
        "novelty": rate_by(nov_bin),
    }


def _heterogeneity(rows: list[dict], min_spread: float = 0.3) -> list[dict]:
    """Bold idea 2: proteins whose multiple experimental structures disagree with AlphaFold to
    very different degrees -> AlphaFold predicts one rigid state for a multi-state protein.
    Uses the spread of TM-to-AF across structures of the same UniProt (no coordinates needed)."""
    by_uni = defaultdict(list)
    for r in rows:
        if r.get("uniprot") and r.get("tm_by_experiment") is not None:
            by_uni[r["uniprot"]].append(r)
    out = []
    for uni, group in by_uni.items():
        if len(group) < 2:
            continue
        tms = [g["tm_by_experiment"] for g in group]
        spread = max(tms) - min(tms)
        if spread < min_spread:
            continue
        group_sorted = sorted(group, key=lambda g: g["tm_by_experiment"])
        out.append({
            "uniprot": uni,
            "name": group[0].get("uniprot_name") or group[0].get("description") or uni,
            "n": len(group), "tm_min": round(min(tms), 3), "tm_max": round(max(tms), 3),
            "spread": round(spread, 3),
            "worst": f"{group_sorted[0]['entry_id']}_{group_sorted[0]['chain']}",
            "best": f"{group_sorted[-1]['entry_id']}_{group_sorted[-1]['chain']}",
        })
    out.sort(key=lambda d: d["spread"], reverse=True)
    return out[:40]


def _scorecards(rows: list[dict], enr_scop2: list[dict], top: int = 12) -> list[dict]:
    """Bold idea 1: per-superfamily AlphaFold blind-spot scorecards (top enriched SCOP2 SFs)."""
    by_sf = defaultdict(list)
    for r in rows:
        sf = r.get("scop2_sf")
        if sf:
            by_sf[sf].append(r)
    cards = []
    for e in enr_scop2[:top]:
        sf = e["value"]
        members = by_sf.get(sf, [])
        cw_members = sorted([m for m in members if m["confidently_wrong"]],
                            key=lambda m: (m.get("fraud_score") or 0), reverse=True)
        theme_counts = Counter()
        for m in cw_members:
            for col, name in THEMES:
                if m.get(col):
                    theme_counts[name] += 1
        cards.append({
            "superfamily": sf, "n": e["n_bg"], "n_cw": e["n_cw"], "cw_rate": e["cw_rate"],
            "ci_lo": e["ci_lo"], "ci_hi": e["ci_hi"], "enrichment": e["enrichment"],
            "dominant_theme": (theme_counts.most_common(1)[0][0] if theme_counts else "—"),
            "examples": [_offender_row(m) for m in cw_members[:5]],
        })
    return cards


def _sequence_clusters(rows: list[dict], cap: int = 90) -> dict:
    """All-vs-all %identity of the top offenders, hierarchical clustering + dendrogram order."""
    from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
    from scipy.spatial.distance import squareform
    from . import compare

    pool = [r for r in rows if (r.get("confidently_wrong") or (r.get("tm_by_experiment") or 1) < 0.5)
            and r.get("sequence") and len(r["sequence"]) >= 20]
    pool.sort(key=lambda r: (r.get("fraud_score") or 0), reverse=True)
    pool = pool[:cap]
    n = len(pool)
    if n < 4:
        return {"n": n}
    from biotite.sequence import ProteinSequence
    from biotite.sequence.align import align_optimal
    seqs = [ProteinSequence(compare._sanitize(r["sequence"])) for r in pool]
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            aln = align_optimal(seqs[i], seqs[j], compare._BLOSUM, gap_penalty=(-10, -1),
                                terminal_penalty=False)[0]
            tr = aln.trace
            matched = tr[(tr[:, 0] >= 0) & (tr[:, 1] >= 0)]
            same = sum(1 for a, b in matched if str(seqs[i][a]) == str(seqs[j][b]))
            ident = same / max(1, len(matched))
            D[i, j] = D[j, i] = 1.0 - ident
    Z = linkage(squareform(D, checks=False), method="average")
    order = dendrogram(Z, no_plot=True)["leaves"]
    clusters = fcluster(Z, t=0.7, criterion="distance").tolist()
    ident_pct = np.round((1.0 - D) * 100, 1)
    labels = [f"{pool[k]['entry_id']}_{pool[k]['chain']}" for k in order]
    ordered_cluster = [int(clusters[k]) for k in order]
    ordered_desc = [(pool[k].get("description") or pool[k].get("uniprot_name") or "") for k in order]

    # Contiguous cluster blocks (the dendrogram order groups clusters), each labelled by the
    # most common significant word across its members -> "the transthyretin block", etc.
    blocks, i = [], 0
    while i < n:
        j = i
        while j + 1 < n and ordered_cluster[j + 1] == ordered_cluster[i]:
            j += 1
        if j - i + 1 >= 2:
            blocks.append({"start": i, "end": j, "size": j - i + 1,
                           "label": _dominant_word(ordered_desc[i : j + 1])})
        i = j + 1
    return {
        "n": n,
        "order_labels": labels,
        "matrix": ident_pct[np.ix_(order, order)].tolist(),
        "clusters": ordered_cluster,
        "blocks": blocks,
        "n_clusters": len(set(clusters)),
    }


_STOPWORDS = {"protein", "chain", "human", "domain", "family", "type", "subunit", "factor",
              "complex", "the", "and", "receptor", "binding", "like", "containing", "isoform",
              "beta", "alpha", "putative", "uncharacterized", "member", "region", "terminal"}


def _dominant_word(descs: list) -> str:
    words = Counter()
    for d in descs:
        for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", d or ""):
            wl = w.lower()
            if wl not in _STOPWORDS:
                words[wl] += 1
    if not words:
        return "mixed"
    top, n = words.most_common(1)[0]
    return top if n >= 2 else "mixed"


def _failure_embedding(rows: list[dict], cap: int = 800) -> dict:
    """2-D PCA (numpy SVD) of a per-structure metric fingerprint, coloured by CATH class."""
    feats, meta = [], []
    for r in rows:
        m = json.loads(r.get("metrics_json") or "{}")
        vec = [
            r.get("tm_by_experiment") or 0, r.get("lddt") or 0, (r.get("gdt_ts") or 0) / 100,
            min(r.get("ca_rmsd") or 0, 20) / 20, min(m.get("radius_of_gyration_diff") or 0, 20) / 20,
            (m.get("ss_agreement_q3") or 0) / 100, m.get("contact_jaccard") or 0,
            m.get("pae_overconfident_frac") or 0, r.get("coverage_of_experiment") or 0,
        ]
        if any(v is None for v in vec):
            continue
        feats.append(vec)
        meta.append(r)
    if len(feats) < 5:
        return {"n": len(feats)}
    if len(feats) > cap:
        idx = sorted(range(len(feats)), key=lambda k: (meta[k].get("fraud_score") or 0), reverse=True)[:cap]
        feats = [feats[k] for k in idx]
        meta = [meta[k] for k in idx]
    X = np.array(feats, dtype=float)
    X = (X - X.mean(0)) / (X.std(0) + 1e-9)
    U, S, Vt = np.linalg.svd(X - X.mean(0), full_matrices=False)
    coords = (U[:, :2] * S[:2])
    return {
        "n": len(meta),
        "x": np.round(coords[:, 0], 3).tolist(),
        "y": np.round(coords[:, 1], 3).tolist(),
        "cath_class": [annotate.CATH_CLASS_NAMES.get(r.get("cath_class"), "unclassified") for r in meta],
        "fraud": [r.get("fraud_score") or 0 for r in meta],
        "cw": [int(bool(r.get("confidently_wrong"))) for r in meta],
        "label": [f"{r['entry_id']}_{r['chain']}" for r in meta],
    }


def _offender_row(r: dict) -> dict:
    return {
        "entity_id": r["entity_id"], "entry_id": r["entry_id"], "chain": r["chain"],
        "uniprot": r.get("uniprot"), "description": (r.get("description") or "")[:60],
        "tm": r.get("tm_by_experiment"), "plddt": r.get("mean_plddt"), "fraud": r.get("fraud_score"),
        "cath_class": annotate.CATH_CLASS_NAMES.get(r.get("cath_class")) if r.get("cath_class") else None,
        "scop2_sf": r.get("scop2_sf"), "week": r.get("week"),
        "themes": [name for col, name in THEMES if r.get(col)],
        "doi": r.get("citation_doi"), "pubmed": r.get("citation_pubmed"),
        "journal": r.get("citation_journal"), "year": r.get("citation_year"),
        "novelty": r.get("novelty_identity"), "is_novel": r.get("is_novel"),
    }


def _weekly_highlight(rows: list[dict]) -> dict:
    """This week's new confidently-wrong offenders + first-time fold/theme flags."""
    weeks = sorted({r["week"] for r in rows if r.get("week")})
    if not weeks:
        return {}
    latest = weeks[-1]
    this = [r for r in rows if r.get("week") == latest]
    prior = [r for r in rows if r.get("week") and r["week"] != latest]
    this_cw = sorted([r for r in this if r["confidently_wrong"]],
                     key=lambda r: (r.get("fraud_score") or 0), reverse=True)
    prior_sf = {r.get("scop2_sf") for r in prior if r["confidently_wrong"] and r.get("scop2_sf")}
    prior_class = {r.get("cath_class") for r in prior if r["confidently_wrong"] and r.get("cath_class")}
    first_sf = sorted({r.get("scop2_sf") for r in this_cw
                       if r.get("scop2_sf") and r.get("scop2_sf") not in prior_sf})
    return {
        "week": latest,
        "n_new_cw": len(this_cw),
        "n_new_analysed": len(this),
        "first_time_superfamilies": first_sf[:8],
        "worst": [_offender_row(r) for r in this_cw[:8]],
    }


# --------------------------------------------------------------------------------------
# Snapshot build
# --------------------------------------------------------------------------------------
def rebuild_snapshot() -> dict:
    rows = db.compared_with_annotations()
    banner.info(f"[analyze] aggregating {len(rows)} annotated compared entities…")
    enr_class = _enrichment(rows, "cath_class", name_key=None, min_n=3)
    for e in enr_class:
        e["label"] = annotate.CATH_CLASS_NAMES.get(e["value"], e["value"])
    enr_scop2 = _enrichment(rows, "scop2_sf", name_key="scop2_sf", min_n=3)
    snap = {
        "n_analysed": len(rows),
        "n_cw": sum(1 for r in rows if r["confidently_wrong"]),
        "enrichment_cath_class": enr_class,
        "enrichment_scop2": enr_scop2[:30],
        "cath_folds": _cath_folds(rows),
        "themes": _themes(rows),
        "correlates": _correlates(rows),
        "heterogeneity": _heterogeneity(rows),
        "scorecards": _scorecards(rows, enr_scop2),
        "clusters": _sequence_clusters(rows),
        "embedding": _failure_embedding(rows),
        "weekly": _weekly_highlight(rows),
        "offenders": [_offender_row(r) for r in sorted(
            rows, key=lambda r: (r.get("fraud_score") or 0), reverse=True)[:400]],
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    db.save_snapshot("cumulative", snap)
    return snap


def analyze(limit: Optional[int] = None) -> dict:
    """Full analysis pass: enrich un-annotated compared entities, then rebuild the snapshot."""
    db.init_schema()
    n = enrich(limit=limit)
    banner.ok(f"[analyze] enriched {n} new entities")
    snap = rebuild_snapshot()
    banner.ok(f"[analyze] snapshot rebuilt: {snap['n_analysed']} analysed, {snap['n_cw']} confidently wrong")
    return snap
