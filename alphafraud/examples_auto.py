"""Deterministic 'example of the week' generator — NO LLM.

Every weekly PDB release, the pipeline picks that week's most instructive confidently-wrong
catch and turns it into an annotated example panel whose prose is assembled purely from the
AlphaFraud database (headline metrics, calibration, CATH annotation, citation). Unlike the
curated deep-dives in `examples.py`, this auto class deliberately omits a 'Biology & disease'
section: the biology is the one part a template can't honestly write, so we don't fake it.

`build(row)` takes a joined entity+annotation row (see db.weekly_example_source_rows) and
returns the same dict shape the Examples template consumes, minus `biology`.
"""

import json

# The hand-curated deep-dives already own these proteins — never auto-pick them, so the
# weekly panel always surfaces something new rather than duplicating a featured family.
CURATED_UNIPROTS = {
    "P30153", "Q13586", "O95433", "O00308", "Q9NUM4", "P37840", "P02766", "P00742",
}


def _f2(v):
    return "—" if v is None else f"{v:.2f}"


def _f1(v):
    return "—" if v is None else f"{v:.1f}"


def _classify(r, m):
    """(failure-mode label, one-sentence mechanism) from metrics + structural flags."""
    lddt = r["lddt"] or 0
    ssq3 = m.get("ss_agreement_q3") or 0            # stored 0–100 (a percent)
    plddt = r["mean_plddt"] or 0
    if r["is_amyloid"]:
        return ("Native fold → amyloid",
                "the deposited coordinates are a self-templating cross-β amyloid assembly — a "
                "non-native polymer state AlphaFold's single-chain model has no way to represent")
    if plddt >= 80 and lddt >= 0.55 and ssq3 >= 60:
        return ("Right fold, wrong conformation/assembly",
                "the local fold is largely correct but the global arrangement is not — the "
                "hallmark of a conformational-state or inter-domain-geometry error rather than a misfold")
    if r["is_assembly"] or (r["n_chains"] or 1) > 1:
        return ("Wrong biological context",
                "the experiment captured a complex or assembly state that a single-chain monomer "
                "prediction cannot anticipate")
    if r["is_idr"] or r["is_coiledcoil"]:
        return ("Disorder / coiled-coil ambiguity",
                "the sequence lacks a single well-defined fold, so AlphaFold's one static answer "
                "cannot match the deposited state")
    return ("Whole-fold mismatch",
            "secondary structure and tertiary packing both diverge from the prediction — "
            "AlphaFold committed to the wrong fold")


def build(r) -> dict:
    """Generate the templated example dict for a joined entity row `r` (dict-like)."""
    m = json.loads(r["metrics_json"] or "{}")
    ssq3 = m.get("ss_agreement_q3")               # percent 0–100
    pearson = m.get("plddt_lddt_pearson")
    cwf = m.get("confidently_wrong_frac")         # fraction 0–1
    nov = r["novelty_identity"]
    mode, mech = _classify(r, m)
    fold = r["cath_name"] or r["scop2_sf"] or None
    name = r["description"] or r["uniprot"]
    gene = (r["uniprot_name"] or "").replace("_HUMAN", "")
    novtxt = (f"{round(100 - (nov or 0))}% novel to AlphaFold's training cutoff"
              if r["is_novel"] else "within AlphaFold's training distribution")

    headline = (
        f"AlphaFold modelled {r['entry_id']}_{r['chain']} at mean pLDDT {_f1(r['mean_plddt'])}, "
        f"but the deposited structure scores TM-score {_f2(r['tm_by_experiment'])} against that prediction"
        + (f" — {round(cwf * 100)}% of residues confidently wrong" if cwf is not None else "")
        + f". A {mode.lower()}.")

    structure = [
        (f"{name} is "
         + (f"a {r['seq_length']}-residue chain" if r["seq_length"] else "a protein chain")
         + (f" annotated as {fold}" if fold else "")
         + (f" ({r['cath_class']})" if r["cath_class"] else "")
         + (f"; the deposition resolves {r['n_chains']} chains" if (r["n_chains"] or 1) > 1 else "")
         + ". This is the fold AlphaFold predicts, and it does so with high confidence."),
        ("In the viewer, residues are coloured by their Cα deviation from the AlphaFold model — "
         "red marks where the deposited coordinates moved furthest from the prediction; toggle the "
         "AlphaFold “ghost” to overlay what it predicted."),
    ]
    conf_word = ("near-maximal confidence" if (r["mean_plddt"] or 0) >= 90
                 else "high confidence" if (r["mean_plddt"] or 0) >= 75 else "moderate confidence")
    why_wrong = [
        (f"AlphaFold's mean pLDDT of {_f1(r['mean_plddt'])} signals {conf_word}, yet the accuracy "
         f"metrics disagree: TM-score {_f2(r['tm_by_experiment'])}, Cα-RMSD "
         + (f"{r['ca_rmsd']:.1f} Å" if r["ca_rmsd"] is not None else "—")
         + f", lDDT {_f2(r['lddt'])}"
         + (f", secondary-structure agreement Q3 {round(ssq3)}%" if ssq3 is not None else "")
         + "."),
        ("Confidence is "
         + ("mis-calibrated here" if (pearson is not None and pearson < 0.3) else "only weakly informative")
         + (f" — the pLDDT↔lDDT correlation is {pearson:+.2f}" if pearson is not None else "")
         + f". Mechanistically, {mech}. The sequence is {novtxt}."),
    ]
    key_facts = [
        f"UniProt {r['uniprot']}" + (f"; {r['seq_length']} aa" if r["seq_length"] else "")
        + (f"; {r['n_chains']} chains" if (r["n_chains"] or 1) > 1 else ""),
        (f"Fold: {fold}" + (f" ({r['cath_class']})" if r["cath_class"] else "")) if fold else "Fold: not annotated",
        f"AF failure: pLDDT {_f1(r['mean_plddt'])} vs TM {_f2(r['tm_by_experiment'])}, lDDT {_f2(r['lddt'])}"
        + (f", {round(cwf * 100)}% residues confidently wrong" if cwf is not None else ""),
        f"Failure mode: {mode}",
        (f"Novelty: {round(100 - (nov or 0))}%" if r["is_novel"] else "Within training distribution"),
    ]
    badges = [b for b in [
        "novel" if r["is_novel"] else None,
        "amyloid" if r["is_amyloid"] else None,
        "assembly" if r["is_assembly"] else None,
        "auto",
    ] if b]
    citation = ({"doi": r["citation_doi"], "title": r["citation_title"], "year": r["citation_year"]}
                if r["citation_doi"] else None)

    return {
        "uniprot": r["uniprot"], "gene": gene, "name": name,
        "entity_id": r["entity_id"], "entry": r["entry_id"], "chain": r["chain"],
        "failure_mode": mode, "badges": badges, "headline": headline,
        "structure": structure, "why_wrong": why_wrong, "key_facts": key_facts,
        "citation": citation, "source": "auto",
    }
