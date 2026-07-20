"""Curated 'Examples' deep-dives — four of the worst-offending protein families, each an
instructive AlphaFold failure. Prose was drafted by a Fable-5 research pass (structural biology
+ literature), then wired to live AlphaFraud metrics (see webapp._render_examples). Each example
renders as an identically-formatted annotated panel with an interactive 3D viewer.

Keep the prose here; the numbers come from the DB at render time so they never go stale.
"""

# The positive control — rendered on its own at the very top of the Examples page. A case where
# AlphaFold's blind prediction was almost perfect, to show the tool can be accurate AND that the
# AlphaFraud pipeline certifies good predictions (near-zero fraud), not just hunts for failures.
CONTROL = {
    "kind": "match",
    "section": "When AlphaFold gets it right — the control",
    "section_note": (
        "AlphaFraud exists to catch confident failures — so here is the opposite, on purpose. This is a "
        "genuine positive control: a protein AlphaFold had never seen, predicted almost perfectly. It "
        "proves two things at once — that AlphaFold can be brilliantly accurate, and that AlphaFraud's "
        "metrics certify a good prediction as good (near-zero fraud) rather than only finding bad ones."),
    "uniprot": "Q96SD1",
    "gene": "DCLRE1C",
    "name": "Protein Artemis",
    "entity_id": "6TT5_1",
    "entry": "6TT5",
    "chain": "AAA",
    "failure_mode": "Excellent match — AlphaFold nailed it",
    "badges": ["novel", "well-calibrated", "1.5 Å X-ray"],
    "headline": (
        "AlphaFold's blind prediction of a novel, disease-critical nuclease matched the 1.5 Å crystal "
        "structure to 0.45 Å RMSD — the positive control that shows the tool is genuinely accurate, and "
        "that AlphaFraud certifies good predictions, not just bad ones."),
    "structure": [
        "Artemis (gene DCLRE1C, UniProt Q96SD1) is a structure-specific endonuclease whose catalytic core "
        "belongs to the metallo-β-lactamase (MBL) fold, fused to a β-CASP domain. This MBL/β-CASP "
        "combination defines a nuclease superfamily shared with SNM1A, SNM1B/Apollo and CPSF73, in which "
        "the two domains pack together to build a single composite active site rather than acting as "
        "independent modules. The MBL domain contributes a shallow αβ/βα sandwich that cradles catalytic "
        "metal ions (Zn²⁺), while the β-CASP insertion supplies additional coordinating residues and "
        "closes over the metal centre to form a deep, substrate-binding cleft suited to nicking hairpin "
        "and branched DNA.",
        "PDB 6TT5 captures this catalytic domain (roughly the first 361 residues) at 1.5 Å resolution — a "
        "well-ordered, compact single-domain fold with no oligomeric assembly, no domain-swapping and no "
        "conformational ambiguity in the crystal. Full-length Artemis extends well beyond this core with a "
        "long C-terminal region that is intrinsically disordered and regulatory, phosphorylated by "
        "DNA-PKcs and ATM. That tail is not part of the crystallised, folded domain modelled here — and it "
        "is exactly the kind of flexible extension AlphaFold typically flags with low pLDDT rather than "
        "mis-predicting with false confidence.",
    ],
    "why_wrong": [
        "Every headline metric on this entry points the same way. Global superposition of AlphaFold's "
        "blind model against the 6TT5 experimental structure gives a TM-score of 0.996 and GDT_TS of 99.2 "
        "(GDT_HA 96.0), with a Cα-RMSD of just 0.45 Å across the full catalytic domain. Locally the "
        "agreement is equally tight: lDDT 0.985 and secondary-structure agreement Q3 92.5%, meaning "
        "essentially every strand, helix and loop is placed and oriented correctly — not just the domain's "
        "rough envelope. This was achieved on a sequence with only 29% identity to the closest structure "
        "in AlphaFold's pre-cutoff training set (6TT5 was deposited in 2019, after AlphaFold2's 2018-04-30 "
        "cutoff), so the model was not recalling a near-identical template — it was genuinely generalising "
        "from evolutionary and physical constraints.",
        "Confidence and correctness are also well matched here, which is the part AlphaFraud is built to "
        "check. Mean pLDDT was 95.2, and that confidence was earned: the pLDDT↔lDDT correlation is +0.56, "
        "the PAE-overconfident fraction is 0.00, and the confidently-wrong-residue fraction is 0.00 — "
        "nowhere did the model report high confidence in a region it actually got wrong. Structurally this "
        "is the regime AlphaFold is built for: a single, compact, evolutionarily well-conserved globular "
        "enzyme domain with a deep multiple-sequence alignment, one dominant native conformation, and none "
        "of the hinge motion, domain-swapping, assembly or amyloid ambiguity that trips it up elsewhere. "
        "AlphaFraud's composite score reflects that cleanly: FRAUD = 0.020, against a backdrop where the "
        "site's worst offenders score 0.8–0.95. The pipeline is not tuned to find fraud everywhere; here "
        "it correctly recognises that there is none.",
    ],
    "biology": [
        "Artemis sits at the centre of non-homologous end joining (NHEJ), the dominant pathway for "
        "repairing DNA double-strand breaks in mammalian cells. Recruited to DNA ends by DNA-PKcs and "
        "activated by DNA-PKcs-mediated phosphorylation, its endonuclease activity opens the covalently "
        "sealed hairpin intermediates generated during V(D)J recombination — the process that assembles "
        "diverse antigen-receptor genes in developing T and B lymphocytes. Beyond hairpin opening it also "
        "trims and resects DNA ends at double-strand breaks and during immunoglobulin class-switch "
        "recombination, making it essential both for adaptive-immune diversity and for genome stability "
        "after damage.",
        "Loss-of-function mutations in DCLRE1C cause radiosensitive severe combined immunodeficiency "
        "(RS-SCID), including the founder Athabascan SCID phenotype, and Omenn syndrome; hypomorphic "
        "alleles are linked to milder combined immunodeficiency, elevated lymphoma risk and clinical "
        "radiosensitivity. Because Artemis is required to repair a defined subset of radiation-induced "
        "breaks, and because tumour cells often rely on NHEJ to survive genotoxic therapy, it is actively "
        "pursued as a radiosensitiser and anti-cancer drug target; the structure reported alongside 6TT5 "
        "was explicitly generated to support structure-based strategies for its inhibition.",
    ],
    "key_facts": [
        "Fold: metallo-β-lactamase (MBL) domain fused to a β-CASP domain — a single composite Zn-dependent nuclease active site (MBL/β-CASP superfamily, with SNM1A/Apollo, CPSF73)",
        "Match to experiment: TM-score 0.996, GDT_TS 99.2, GDT_HA 96.0, Cα-RMSD 0.45 Å, lDDT 0.985, SS-Q3 92.5%",
        "Genuinely novel target: only 29% identity to the closest pre-cutoff PDB chain; 6TT5 deposited (2019) after AlphaFold2's training cutoff",
        "Calibration: mean pLDDT 95.2, pLDDT↔lDDT correlation +0.56, PAE-overconfident 0.00, confidently-wrong fraction 0.00",
        "AlphaFraud verdict: FRAUD score 0.020 (near-zero, not flagged) vs a worst-offender range of 0.8–0.95 — it certifies accuracy, not just failure",
        "Biology: NHEJ endonuclease; opens V(D)J hairpins with DNA-PKcs; loss of function causes RS-SCID/Omenn; pursued as a radiosensitiser drug target",
    ],
}


# Two curated sections: ordinary globular folds AlphaFold gets subtly wrong (the surprising
# cases — right fold, wrong conformation/assembly), then the dramatic whole-fold catastrophes.
EXAMPLES = [
    # ---- Section 1: ordinary single-chain globular folds ----
    {
        "section": "Ordinary folds AlphaFold still gets wrong",
        "section_note": (
            "AlphaFold is genuinely good at compact, single-chain globular folds — which is exactly "
            "why these four are so telling. Each is a regular folded protein, not an amyloid, a "
            "membrane protein, or a disordered chain. AlphaFold gets the fold essentially right, then "
            "commits — often at very high confidence — to the wrong conformation, curvature, or "
            "inter-domain pose. The failure is subtle, and its rarity is itself the finding."),
        "uniprot": "P30153",
        "gene": "PPP2R1A",
        "name": "PP2A scaffold subunit A (PR65)",
        "entity_id": "8UWB_3",
        "entry": "8UWB",
        "chain": "C",
        "failure_mode": "Right fold, wrong curvature (flexible α-solenoid)",
        "badges": ["globular", "flexible scaffold", "tumour suppressor"],
        "headline": (
            "AlphaFold assigns mean pLDDT 96.8 — near-maximal confidence — to a 15-repeat HEAT "
            "solenoid whose global curvature is wrong for 99% of its residues: a textbook case of high "
            "confidence in the wrong spring state."),
        "structure": [
            "The PP2A A/scaffold subunit (PR65) is built entirely from 15 tandem HEAT repeats, each an "
            "antiparallel pair of ~39-residue α-helices (a short 'A' helix and a longer 'B' helix) "
            "joined by a turn. Successive repeats stack side-by-side into a superhelical, horseshoe-"
            "shaped α-solenoid ~90 Å long, with no β-structure or globular core — architecturally "
            "distinct from most folds in the AlphaFraud set.",
            "Functionally it is a bipartite assembly platform: HEAT repeats 1–10 form the concave "
            "surface that recruits one of ~26 regulatory B-family subunits, while repeats 11–15 dock "
            "the catalytic C subunit, together forming the PP2A heterotrimer. Critically the solenoid "
            "is not a rigid ruler: inter-repeat hinge angles — concentrated around repeats 5–7 and the "
            "B/C-subunit interface — flex between 'open'/extended and 'clamped'/compact states "
            "depending on which subunits are bound. PR65 is a spring, not a fixed curve.",
        ],
        "why_wrong": [
            "This is a confidence paradox. Mean pLDDT 96.8 says AlphaFold is essentially certain of "
            "the local geometry of every HEAT-repeat helix pair — reasonable, because the repeat unit "
            "is a simple, well-constrained motif. Yet TM-score 0.293, Cα-RMSD 15.0 Å, lDDT 0.311 and a "
            "0.99 confidently-wrong-residue fraction show the assembled molecule is grossly wrong in "
            "overall shape against the deposited PR65 subunit of 8UWB.",
            "It is a curvature/hinge failure, not a fold failure: AlphaFold locks onto one static "
            "superhelical bend, but tiny per-repeat angular errors compound multiplicatively across 15 "
            "tandem repeats into tens of Ångströms of end-to-end displacement — exactly what a global "
            "metric like TM-score punishes while the more local lDDT (0.31, not near-zero) partially "
            "forgives. The near-zero pLDDT↔lDDT correlation (−0.13) confirms confidence carries no "
            "diagnostic signal. The source paper had to solve an experimental PP2A trimer to guide "
            "AlphaFold2-Multimer rather than trust single-sequence prediction of the assembly.",
        ],
        "biology": [
            "PP2A is one of the cell's two dominant serine/threonine phosphatases, an obligate A–B–C "
            "heterotrimer that dephosphorylates substrates across the cell cycle, Akt/PI3K and MYC "
            "signalling, apoptosis and the DNA-damage response — a major tumour suppressor. PPP2R1A is "
            "the sole scaffold onto which combinatorial exchange of B subunits builds an estimated "
            "~100 distinct holoenzymes with different specificities and localisations.",
            "PPP2R1A is recurrently mutated in endometrial and ovarian carcinomas, with hotspots "
            "(P179R, R183W/P, S256F, W257G/L/C, R258H) clustering in HEAT repeats 5–7 that disrupt "
            "B56-family binding without abolishing C-subunit docking — uncoupling substrate targeting "
            "from catalysis. Germline variants cause a neurodevelopmental disorder. PP2A reactivation "
            "by small-molecule activators (SMAPs) is an active oncology strategy exploiting exactly "
            "the scaffold flexibility this structure captures.",
        ],
        "key_facts": [
            "Fold: 15 tandem HEAT repeats (paired antiparallel α-helices) forming an elongated, flexible α-solenoid",
            "No single fixed curvature — inter-repeat hinges flex between open and clamped states",
            "Assembly platform of the PP2A heterotrimer: repeats 1–10 bind B subunits, 11–15 bind catalytic C",
            "AF failure: pLDDT 96.8 (near-maximal) yet lDDT 0.311, TM 0.293, RMSD 15.0 Å — 99% confidently wrong",
            "Root cause: hinge/curvature error compounding across 15 repeats, not a secondary-structure error",
            "Disease: master tumour-suppressor scaffold; cancer hotspots (P179R, R183, S256F, W257, R258H) in the B56-binding repeats",
        ],
    },
    {
        "uniprot": "Q13586",
        "gene": "STIM1",
        "name": "Stromal interaction molecule 1 (CC1)",
        "entity_id": "6YEL_1",
        "entry": "6YEL",
        "chain": "A",
        "failure_mode": "Bistable conformational switch — wrong conformer",
        "badges": ["globular", "conformational switch", "single chain"],
        "headline": (
            "A single folded three-helix coiled-coil switch that toggles between a clamped-shut resting "
            "bundle and an extended active state — AlphaFold committed to one conformer, and the "
            "deposited structure is the other."),
        "structure": [
            "STIM1 is a type-I single-pass ER membrane protein: an N-terminal luminal EF-hand/SAM "
            "domain senses ER Ca²⁺, followed by one transmembrane helix, and a cytosolic region of "
            "stacked coiled-coil segments — CC1, then the CC2–CC3 pair that folds into the CAD/SOAR "
            "module that ultimately traps and gates Orai1. CC1 (~238–343) is not a simple two-stranded "
            "coiled coil but a compact, antiparallel three-helix bundle held together by a hydrophobic "
            "interhelical seam.",
            "In the resting cell this bundle folds back on itself so that CC1α3 clamps CAD/SOAR "
            "intramolecularly, holding STIM1 'tight' and autoinhibited. Store depletion collapses the "
            "luminal Ca²⁺ signal, propagates across the membrane and releases the clamp, letting CC1 "
            "and the whole C-terminus adopt an 'extended' conformation that frees CAD/SOAR to engage "
            "Orai1. CC1 is a genuinely bistable folded module — two legitimate, functionally distinct "
            "tertiary arrangements of the same helical content.",
        ],
        "why_wrong": [
            "This is emphatically not disorder or amyloid: SS-Q3 of 69.6% confirms AlphaFold gets the "
            "local chemistry right — CC1 is helical, and the model largely agrees on where the helices "
            "are. What collapses is tertiary packing: lDDT 0.341, TM-score 0.389 and Cα-RMSD 35.8 Å — "
            "the signature of correct secondary structure wrapped around the wrong global arrangement.",
            "Consistent with AlphaFold's known bias toward continuous, extended coiled-coil geometry "
            "for heptad-rich sequences, it most likely predicted CC1 as a single elongated helix or "
            "open hairpin — the 'extended', CAD-releasing conformation — while 6YEL captures the "
            "compact, folded-back three-helix bundle of the autoinhibited state (or vice versa). A "
            "single-sequence predictor trained to output one static structure has no mechanism to "
            "represent a switch with two functionally required minima; it commits to one at pLDDT 78.9, "
            "leaving 84% of residues confidently wrong. The fold class is correct; the conformer is not.",
        ],
        "biology": [
            "STIM1 is the ER-resident Ca²⁺ sensor that initiates store-operated Ca²⁺ entry (SOCE). "
            "Ca²⁺ loss from the EF-SAM domain triggers luminal unfolding and oligomerisation, "
            "redistribution to ER–plasma-membrane junctions, and release of the CC1 clamp so that "
            "CAD/SOAR can capture and gate Orai1 CRAC channels — driving Ca²⁺ influx essential for "
            "T-cell and mast-cell activation, muscle excitation–contraction coupling and platelet "
            "function.",
            "The CC1α1–α2 contacts set the activation threshold. Gain-of-function mutations such as "
            "R304W disrupt these contacts, elongate the helix and destabilise the tight resting bundle, "
            "producing constitutive CAD exposure — underlying Stormorken syndrome and tubular aggregate "
            "myopathy. Loss-of-function STIM1 mutations abolish CRAC activity, causing "
            "CRAC-channelopathy immunodeficiency. CC1 is the structural fulcrum between healthy and "
            "diseased Ca²⁺ signalling.",
        ],
        "key_facts": [
            "Single-chain ER Ca²⁺ sensor; CC1 (~238–343) is a compact three-helix antiparallel bundle, not a simple coiled coil",
            "Genuine conformational switch: 'tight' autoinhibited bundle (resting) vs 'extended' CAD-releasing state (activated)",
            "AF failure: right fold class (helical, SS-Q3 69.6%) but wrong conformer/packing — lDDT 0.341, TM 0.389, RMSD 35.8 Å",
            "pLDDT 78.9 with 84% confidently-wrong residues — confident in one state of a two-state switch",
            "Function: gates release of CAD/SOAR to trap and open Orai1 CRAC channels (store-operated Ca²⁺ entry)",
            "Disease: gain-of-function CC1 mutations (R304W) → Stormorken / tubular aggregate myopathy; loss-of-function → CRAC-channelopathy",
        ],
    },
    {
        "uniprot": "O95433",
        "gene": "AHSA1",
        "name": "Activator of Hsp90 ATPase 1 (Aha1)",
        "entity_id": "7DME_1",
        "entry": "7DME",
        "chain": "A",
        "failure_mode": "Right domains, wrong inter-domain pose (flexible linker)",
        "badges": ["globular", "flexible linker", "co-chaperone"],
        "headline": (
            "Two well-folded domains on a flexible tether — AlphaFold committed to a single, plausible "
            "relative pose of a conformationally dynamic co-chaperone, and the deposited solution "
            "structure sampled a different one."),
        "structure": [
            "Human Aha1 (338 aa) is built from two compact globular domains: an N-terminal domain (NTD, "
            "~1–156, a Rossmann-like α/β fold) and a C-terminal domain (CTD, ~157–338, a curved "
            "β-sandwich), joined by a linker that is only partly ordered even when Aha1 is docked on "
            "its partner. Each domain individually folds robustly and is well characterised in "
            "isolation.",
            "In the extended, Hsp90-bound state the NTD engages the Hsp90 middle domain and the CTD "
            "packs against the N-terminal ATPase domains, stabilising the closed, hydrolysis-competent "
            "state in an asymmetric 1:2 stoichiometry. But this domain-bridging arrangement is an "
            "induced state: free Aha1 in solution is intrinsically dynamic, its NTD and CTD tumbling "
            "largely independently and sampling a broad distribution of inter-domain orientations. Aha1 "
            "behaves less like one rigid two-domain protein and more like two folded modules loosely "
            "constrained by a flexible hinge.",
        ],
        "why_wrong": [
            "The numbers tell an intra-domain-correct, inter-domain-wrong story. lDDT is a moderate "
            "0.748 and SS-Q3 is 74.3% — both domains fold essentially correctly, far better than "
            "genuinely misfolded targets. But TM-score collapses to 0.432 with a 23.4 Å Cα-RMSD, and "
            "85% of residues are confidently wrong despite mean pLDDT 83.3.",
            "AlphaFold has built two accurate local folds, then bolted them together at one specific, "
            "self-consistent NTD–CTD angle and buried the joint in a high-pLDDT interface — exactly the "
            "behaviour its confidence metric should flag but does not (pLDDT↔lDDT correlation only "
            "+0.33), because the network has no way to represent an ensemble. The NMR solution structure "
            "(7DME) instead reflects the flexible, loosely coupled reality: whichever discrete pose "
            "AlphaFold picked, the linker's real freedom put the deposited orientation far from it. A "
            "textbook flexible-linker failure — the pieces are right, the assembly instruction is wrong.",
        ],
        "biology": [
            "Aha1 is the strongest known stimulator of Hsp90's intrinsically slow ATPase, accelerating "
            "the conformational cycle required to mature a broad swath of Hsp90 clients — kinases, "
            "steroid hormone receptors and disease-relevant misfolded proteins. It binds Hsp90 "
            "asymmetrically (one Aha1 per dimer suffices), with its NTD engaging the Hsp90 middle "
            "domain and its CTD stabilising the closed N-domain interface, and also shows independent "
            "holdase-like chaperone activity toward stress-denatured proteins.",
            "The partnership has direct disease relevance: Aha1 drives maturation of ΔF508-CFTR, and "
            "reducing Aha1 improves ΔF508-CFTR trafficking — a strategy of interest in cystic fibrosis; "
            "Aha1 also promotes accumulation of pathological tau, implicating it in tauopathies. Given "
            "Hsp90's centrality to oncogenic client maturation, the Aha1–Hsp90 interface is an actively "
            "pursued target for allosteric modulation in cancer and proteostasis disease.",
        ],
        "key_facts": [
            "Hsp90 co-chaperone; the strongest known stimulator of the Hsp90 ATPase cycle",
            "Two independently well-folded globular domains (NTD, CTD) joined by a flexible linker — no single rigid pose in isolation",
            "AF failure: correct domain folds (lDDT 0.75, SS-Q3 74%) assembled at the wrong relative orientation (TM 0.43, RMSD 23.4 Å)",
            "Misleading confidence: mean pLDDT 83.3 but 85% confidently-wrong residues, pLDDT↔lDDT correlation only +0.33",
            "Binds Hsp90 asymmetrically (NTD→middle domain, CTD→N-domain interface); also an independent holdase",
            "Disease: drives ΔF508-CFTR maturation (cystic fibrosis target) and pathological tau accumulation; Hsp90 axis is a cancer target",
        ],
    },
    {
        "uniprot": "O00308",
        "gene": "WWP2",
        "name": "NEDD4-like E3 ubiquitin ligase WWP2 (WW module)",
        "entity_id": "6RSS_1",
        "entry": "6RSS",
        "chain": "A",
        "failure_mode": "Flexible inter-module geometry — honest low confidence",
        "badges": ["globular", "small fold", "E3 ligase"],
        "headline": (
            "Each WW module of WWP2 is a textbook three-stranded β-sheet AlphaFold folds correctly in "
            "isolation — but the deposited chain has no single fixed inter-module geometry, and "
            "AlphaFold guessed one anyway; tellingly, at only pLDDT 74.5, it was honestly unsure."),
        "structure": [
            "Full-length WWP2 (870 aa) has the canonical NEDD4-family layout: an N-terminal C2 domain, "
            "four WW domains (WW1–WW4) that read PPxY/LPxY motifs in substrates, and a C-terminal HECT "
            "domain that forms the E3~ubiquitin thioester. Each WW domain is one of the smallest "
            "autonomously folding units known — ~35–40 residues, a three-stranded antiparallel β-sheet "
            "stabilised by two invariant tryptophans packing its hydrophobic face.",
            "In the resting enzyme WWP2 is autoinhibited: the 2,3-linker wraps onto the HECT domain, "
            "occluding its allosteric ubiquitin site — relieved by ubiquitin binding, multivalent WW "
            "engagement by adaptors such as Ndfip1, or linker phosphorylation. Separately, "
            "isoform-specific pairing of WW3 and WW4 recognises PY-motif partners (e.g. Smad7) with an "
            "inter-domain geometry that is not fixed: it shifts with ligand identity and phosphorylation "
            "state.",
        ],
        "why_wrong": [
            "The chemistry is trivial: a two-Trp, three-strand β-sheet is exactly the small, "
            "high-contact-order motif AlphaFold nails routinely. Yet mean pLDDT here is only 74.5 — the "
            "model is honestly hedging — and everything downstream is bad: TM-score 0.46, lDDT 0.503, "
            "Cα-RMSD 21.9 Å, SS-Q3 63%, 73% of residues confidently wrong, and a pLDDT↔lDDT correlation "
            "of just +0.15.",
            "The 109-residue deposited chain pairs the native WW fold with a second, unrelated folded "
            "module (an NMR solubility-tag partner) via a short flexible tether — structurally the same "
            "problem as native WW3–WW4 tandems having no single relative orientation. Given one sequence "
            "and no knowledge of which pose (or which fusion) was actually captured, AlphaFold predicted "
            "a specific, wrong relative packing — a linker/inter-module geometry failure layered on top "
            "of individually correct small folds, not a misfolded core. Here the honest thing is that "
            "its confidence, uniquely low among these examples, half-admits the uncertainty.",
        ],
        "biology": [
            "WWP2 is a HECT-family E3 ubiquitin ligase of the NEDD4-like clan, using its WW domains as "
            "substrate-recognition modules that dock PY-motif partners for K48- or K63-linked "
            "ubiquitination. Validated substrates include SMAD7 and SMAD2/3 (TGF-β pathway), PTEN, TP53 "
            "and the pluripotency factor OCT4, alongside roles touching chromatin regulators and "
            "autophagy machinery.",
            "Because WWP2 arises as multiple splice isoforms with different WW-domain complements, the "
            "same locus produces enzymes with opposing substrate preferences — WWP2-C preferentially "
            "degrades the TGF-β inhibitor SMAD7 and promotes EMT/metastasis, while WWP2-N targets "
            "SMAD2/3. Autoinhibition via the 2,3-linker keeps basal activity low until relieved by "
            "ubiquitin binding or phosphorylation. WWP2 dysregulation and isoform-ratio shifts are "
            "implicated in cancers (SMAD/TGF-β and PTEN/p53 axes), osteoblast and cardiac remodelling, "
            "and stem-cell biology via OCT4 turnover.",
        ],
        "key_facts": [
            "NEDD4-family HECT E3 ubiquitin ligase: N-terminal C2 domain, four WW domains (WW1–WW4), C-terminal catalytic HECT",
            "WW domains are ~35–40-residue, two-Trp, three-stranded antiparallel β-sheets — among the smallest stable folds",
            "AF failure: uncertain/flexible relative orientation between small folded modules, not a misfolded core",
            "Substrates: SMAD7, SMAD2/3, PTEN, TP53, OCT4 — substrate choice is isoform- and WW-composition-dependent",
            "Autoinhibited by 2,3-linker–HECT packing; relieved by ubiquitin binding, multivalent WW engagement or phosphorylation",
            "Honest failure: mean pLDDT only 74.5 with pLDDT↔lDDT correlation +0.15 — the model is genuinely, correctly unsure",
        ],
    },
    # ---- Section 2: the dramatic whole-fold catastrophes ----
    {
        "section": "The dramatic failures — aggregation, disorder & context",
        "section_note": (
            "The headline catches: whole-fold catastrophes where AlphaFold's confident native "
            "prediction and the deposited coordinates are essentially unrelated — a novel membrane "
            "amyloid, a disordered monomer forced into a fibril, a folded tetramer that amyloids, and a "
            "multidomain zymogen captured in the wrong biological context."),
        "uniprot": "Q9NUM4",
        "gene": "TMEM106B",
        "name": "Transmembrane protein 106B",
        "entity_id": "7U14_1",
        "entry": "7U14",
        "chain": "A",
        "failure_mode": "Novel membrane-protein amyloid",
        "badges": ["amyloid", "novel", "membrane"],
        "headline": (
            "AlphaFold built TMEM106B a tidy, glycosylated FN3 β-sandwich at pLDDT 94 — the real "
            "deposited structure is a self-templating cross-β amyloid ladder that forms in "
            "essentially every aged human brain, and AlphaFold got every one of the ~135 ordered "
            "residues wrong."),
        "structure": [
            "TMEM106B is a type-II single-pass lysosomal membrane protein: a short, intrinsically "
            "disordered cytoplasmic N-terminus (~1–96), a single TM helix (~97–120), and a luminal "
            "C-terminal domain (CTD, ~118–274). The monomeric CTD's native fold, solved by X-ray "
            "crystallography (PDB 8B7D), is a canonical fibronectin type III (FN3) β-sandwich — a "
            "seven-stranded Ig-like fold crowned by a short α-helix and pinned by a disulfide.",
            "In disease and in aged brain the same CTD polymerises homotypically: residues ~120–254 "
            "form the ordered fibril core, adopting an entirely different five-layered cross-β "
            "architecture of 17–19 short β-strands per rung, stacked in-register at ~4.8 Å rise. "
            "Three N-glycans and a C214–C253 disulfide are built into the ordered core — unusual for "
            "amyloid. This is a polymer fold, not a monomer fold; AlphaFold predicts only the latter.",
        ],
        "why_wrong": [
            "AlphaFold returns the native monomeric FN3 fold at mean pLDDT 94.4 — high confidence, "
            "because the sequence has strong coevolutionary support for a folded globular domain. "
            "But the deposited structure (7U14 chain A) is the amyloid cross-β core, and the two "
            "topologies are essentially unrelated: TM-score 0.157 (near-random), Cα-RMSD 27.1 Å, "
            "GDT_TS 0.56, and even secondary-structure identity collapses to Q3 52.6%.",
            "The calibration failure is total: the pLDDT↔lDDT correlation is 0.03 (confidence carries "
            "no information about local accuracy), 72% of residues are over-confident by PAE, and "
            "100% are confidently wrong. The root cause is structural: amyloid is a non-native, "
            "self-templated fold stabilised by intermolecular stacking across thousands of copies — a "
            "cooperative polymer state that cannot be inferred from a single chain. The sequence is "
            "also 100% novel to AlphaFold's training cutoff, so no template steers it off its "
            "globular-fold prior.",
        ],
        "biology": [
            "TMEM106B is a broadly-expressed lysosomal membrane glycoprotein regulating lysosome "
            "size, pH, positioning and trafficking. It was the first GWAS risk/modifier locus for "
            "FTLD-TDP, acting most strongly in progranulin (GRN) mutation carriers, where the risk "
            "haplotype accelerates onset — largely via a linked coding variant, T185S, that changes "
            "glycosylation and turnover.",
            "The 2022 discovery (reported near-simultaneously in Cell, Nature and Acta "
            "Neuropathologica) that the CTD itself forms amyloid fibrils — independent of and "
            "distinct from TDP-43, tau and α-synuclein — reframed TMEM106B as an amyloidogenic "
            "species in its own right. These fibrils accumulate across a broad range of "
            "neurodegenerative diseases and, strikingly, in cognitively-normal aged brain in an "
            "age-dependent manner.",
        ],
        "key_facts": [
            "Fold: type-II TM lysosomal protein; native luminal CTD is a 7-stranded FN3 β-sandwich (PDB 8B7D)",
            "Length: 274 aa; fibril-forming CTD core ≈ residues 120–254",
            "Amyloid: five-layered cross-β 'golf-course' fold; glycans + a C214–C253 disulfide ordered within the core",
            "Disease: top GWAS hit for FTLD-TDP; modifies penetrance in GRN carriers (T185S)",
            "AF failure: confident native FN3 monomer (pLDDT 94) vs self-templated amyloid polymer",
            "Novelty: 100% — no pre-2018 fibril template existed; 21/22 depositions confidently wrong",
        ],
    },
    {
        "uniprot": "P37840",
        "gene": "SNCA",
        "name": "Alpha-synuclein",
        "entity_id": "9A1Q_1",
        "entry": "9A1Q",
        "chain": "A",
        "failure_mode": "Disordered monomer → amyloid fibril",
        "badges": ["amyloid", "disordered", "neurodegeneration"],
        "headline": (
            "AlphaFold confidently predicted a fold for a protein that, in reality, has no single "
            "fold to predict — and the 208 deposited structures that expose this are almost entirely "
            "amyloid fibrils, a self-templating cross-β architecture that only exists once thousands "
            "of copies stack together."),
        "structure": [
            "Alpha-synuclein is a 140-residue intrinsically disordered protein with no stable "
            "tertiary structure as a soluble monomer. It has three regions: an amphipathic "
            "N-terminus (1–60) of imperfect KTKEGV repeats that folds into a helix on membrane "
            "contact; the hydrophobic NAC domain (~61–95), the aggregation-nucleating core; and an "
            "acidic, unstructured C-terminus (96–140) that chaperones against aggregation.",
            "The deposited structures are full-length fibrils solved by cryo-EM: two protofilaments "
            "intertwined about a 2₁ screw axis, each a serpentine, Greek-key-like arrangement of "
            "β-strands packing a hydrophobic core over residues ~37–99. This cross-β fold is "
            "polymorphic — Parkinson's/DLB filaments differ from the multiple-system-atrophy "
            "polymorphs — and is templated by intermolecular stacking, not by the monomer's own "
            "energy landscape.",
        ],
        "why_wrong": [
            "On the worst case (9A1Q chain A): TM-score 0.138, Cα-RMSD 36.3 Å, lDDT 0.18, GDT_TS 1.6, "
            "SS-Q3 35% — essentially no fold correspondence. Expected, since AlphaFold has no cross-β "
            "amyloid mode in its training distribution, and nothing about the sequence alone "
            "specifies which disease-associated protofilament fold it will adopt.",
            "More diagnostically, mean pLDDT 75.2 with a pLDDT↔lDDT correlation of −0.29 shows "
            "AlphaFold's confidence is actively anti-correlated with accuracy — where the model is "
            "more confident it is measurably wrong more often, likely because it partially recognises "
            "local propensities (helical N-terminus, extended NAC) without any signal for "
            "polymorph-specific packing. This is the archetypal disordered-monomer-forced-into-amyloid "
            "failure: 206 of 208 depositions confidently wrong, the highest deposition count in the set.",
        ],
        "biology": [
            "Alpha-synuclein is a presynaptic protein that modulates SNARE-complex assembly, vesicle "
            "clustering and neurotransmitter release, binding curved acidic membranes via its "
            "N-terminal amphipathic helix. Its aggregation into fibrils in Lewy bodies defines the "
            "synucleinopathies: Parkinson's disease, dementia with Lewy bodies, and multiple system "
            "atrophy (where fibrils accumulate in oligodendrocytes).",
            "Familial PD mutations (A30P, E46K, H50Q, G51D, A53T) cluster in the N-terminal/NAC region "
            "and alter membrane binding and polymorph selection; SNCA locus multiplication causes "
            "disease by dosage. Pathology spreads by prion-like templated seeding, and distinct fibril "
            "'strains' correlate with distinct clinical syndromes — a proposed basis for "
            "seed-amplification biomarkers.",
        ],
        "key_facts": [
            "140 aa; intrinsically disordered as a free monomer — no single native fold to predict",
            "Regions: N-terminal KTKEGV lipid-binding repeats, NAC aggregation core (~61–95), acidic C-terminus",
            "Pathological form: cross-β amyloid fibril (Greek-key protofilament), an intermolecular assembly",
            "Disease: synucleinopathies (Parkinson's, DLB, MSA); mutations A30P/E46K/H50Q/G51D/A53T",
            "AF failure: disordered monomer + amyloid fibril, worsened by anti-correlated confidence (r=−0.29)",
            "Most-deposited confidently-wrong protein: 208 depositions, 206 confidently wrong",
        ],
    },
    {
        "uniprot": "P02766",
        "gene": "TTR",
        "name": "Transthyretin",
        "entity_id": "9BZS_1",
        "entry": "9BZS",
        "chain": "A",
        "failure_mode": "Folded tetramer → amyloid fibril",
        "badges": ["amyloid", "druggable", "assembly"],
        "headline": (
            "AlphaFold calls the native TTR fold at pLDDT 98 — statistically indistinguishable from "
            "certainty — while the deposited cardiac amyloid fibril scores TM 0.21 against that "
            "prediction, a 22.8 Å Cα-RMSD collapse that makes this one of the starkest confidently-"
            "wrong cases in the dataset."),
        "structure": [
            "The TTR monomer is a 127-residue subunit folded as an eight-stranded β-sandwich — two "
            "four-stranded antiparallel sheets in a Greek-key, immunoglobulin-like topology with a "
            "short α-helix between strands E and F. Monomers dimerise edge-to-edge and two dimers "
            "pack back-to-back into the physiological homotetramer, forming two funnel-shaped "
            "thyroxine-binding sites. This is exactly what AlphaFold predicts, at near-maximal "
            "confidence.",
            "The amyloid state is a different molecule. Tetramer dissociation and partial monomer "
            "unfolding precede assembly into cross-β fibrils: cryo-EM resolves a single protofilament "
            "built from an N-terminal segment (~Pro11–Lys35) and a C-terminal segment (~Gly57–Thr123) "
            "packed into a compact serpentine β-arch, connected by a disordered linker, stacking at "
            "~4.8 Å rise. Essentially none of the native sandwich topology survives.",
        ],
        "why_wrong": [
            "Every metric tells the same story. AlphaFold's mean pLDDT 98.0 reflects extreme confidence "
            "in the native β-sandwich — unsurprising, since TTR has 0% sequence novelty and sits "
            "squarely in the training set. But the deposited structure (9BZS chain A) is the amyloid "
            "fibril: TM-score 0.214, Cα-RMSD 22.8 Å, lDDT 0.49, GDT_TS 0.27, SS-Q3 56.5%. The "
            "confidently-wrong-residue fraction is 1.0, and 75% of errors fall in PAE-overconfident "
            "territory; FRAUD 0.95.",
            "The mechanistic point is the cleanest illustration of the whole thesis: pLDDT measures "
            "AlphaFold's confidence in the fold it knows — the evolutionarily-conserved native state — "
            "not whether a given deposited coordinate set represents that state. Amyloid is a "
            "non-native, kinetically-accessed aggregation product; nothing in the "
            "sequence-to-native-structure mapping AlphaFold learned encodes it. This is a wrong-STATE "
            "failure, not an unknown-sequence one.",
        ],
        "biology": [
            "TTR is a homotetrameric transport protein made mainly by the liver (plasma) and choroid "
            "plexus (CSF). It carries thyroxine (T4) in the tetramer channel and retinol indirectly, "
            "via retinol-binding protein 4. Amyloidogenesis is rate-limited by tetramer dissociation "
            "to monomer, which partially unfolds and reassembles into fibrils that deposit in nerve "
            "and cardiac tissue.",
            "Two diseases result: wild-type ATTR (age-related cardiac amyloidosis) and hereditary "
            "ATTRv from >130 destabilising mutations (classically V30M polyneuropathy). Uniquely among "
            "amyloid diseases, it is genuinely druggable — tetramer kinetic stabilisers (tafamidis, "
            "diflunisal, acoramidis) lock the tetramer at the T4 sites, and gene-silencing agents "
            "(patisiran, vutrisiran) suppress hepatic production. The 2024 cryo-EM work behind 9BZS "
            "found V30M fibrils from heart and nerve of the same patient are near-identical.",
        ],
        "key_facts": [
            "Native fold: 127-aa β-sandwich, Greek-key Ig-like; obligate homotetramer with two T4 sites",
            "Ligands: thyroxine (T4) and, via RBP4, retinol (vitamin A)",
            "Disease: ATTR amyloidosis — wild-type (cardiac) and hereditary ATTRv (e.g. V30M)",
            "AF failure: confident native tetramer (pLDDT 98, novelty 0%) vs amyloid fibril (TM 0.21)",
            "Mechanism: rate-limiting tetramer dissociation → monomer misfolding → cross-β fibril",
            "Druggable: tafamidis/diflunisal/acoramidis (stabilisers); patisiran/vutrisiran (knockdown)",
        ],
    },
    {
        "uniprot": "P00742",
        "gene": "F10",
        "name": "Coagulation factor X",
        "entity_id": "6Q9F_2",
        "entry": "6Q9F",
        "chain": "B",
        "failure_mode": "Wrong context — fragment / complex / PTM",
        "badges": ["not amyloid", "multidomain", "druggable"],
        "headline": (
            "AlphaFold nails the modular zymogen it was trained to see, but the worst-scoring "
            "deposition isn't Factor X folded at all — it's a 39-residue stretch of the EGF1 domain, "
            "unfolded and threaded through the active site of a partner hydroxylase: a failure of "
            "context, not of fold prediction."),
        "structure": [
            "Full-length Factor X is a vitamin-K-dependent zymogen built from an N-terminal Gla domain "
            "(11 γ-carboxyglutamates coordinating Ca²⁺ for membrane docking), two tandem EGF-like "
            "domains, and a C-terminal chymotrypsin-fold serine protease domain (catalytic triad "
            "His236–Asp282–Ser379). Light and heavy chains are disulfide-linked; a 52-residue "
            "activation peptide is excised on activation to factor Xa. AlphaFold predicts this compact "
            "multidomain architecture with high confidence.",
            "The deposited PDB corpus fragments that picture: isolated Gla domains, isolated protease "
            "domains, activated Xa, Xa in prothrombinase/tenase assemblies — and, in the worst case "
            "here (6Q9F chain B), a synthetic 39-mer peptide spanning the EGF1 β-hydroxylation site, "
            "captured extended through the active-site channel of aspartyl/asparaginyl β-hydroxylase "
            "(AspH), not folded as an EGF module at all.",
        ],
        "why_wrong": [
            "This is a wrong-context failure, not re-folding-into-amyloid, and the numbers say so. "
            "FRAUD 0.37 and Cα-RMSD 6.6 Å are moderate — nowhere near the ~25 Å amyloid catastrophes — "
            "and SS-Q3 70% shows partial secondary-structure agreement survives. Yet TM-score collapses "
            "to 0.127: a 39-residue linear fragment threaded through AspH's channel has no compact fold "
            "to superpose against AlphaFold's EGF1-in-context prediction.",
            "The pLDDT↔lDDT correlation of −0.59 is the tell: AlphaFold assigns high local confidence "
            "(mean pLDDT 93.5) to a folded domain context that isn't present in the crystal, so "
            "confidence and correctness move in opposite directions. AlphaFold models the isolated, "
            "intact, canonical protein; experiments capture it activated, cleaved, fragmented or bound "
            "— states that, given one sequence, it cannot know. It has no way to anticipate a residue "
            "will later be excised as substrate for another enzyme.",
        ],
        "biology": [
            "Factor X is a vitamin-K-dependent plasma zymogen made in the liver. It is activated by two "
            "convergent tenase complexes — the extrinsic tissue-factor/FVIIa and the intrinsic "
            "FIXa/FVIIIa (deficient in haemophilia B and A). Activated factor Xa, with cofactor Va, "
            "Ca²⁺ and phospholipid, forms prothrombinase, the complex that converts prothrombin to "
            "thrombin — the central amplification node of coagulation.",
            "That makes Xa one of the most validated anticoagulant targets: the direct oral inhibitors "
            "rivaroxaban, apixaban and edoxaban bind the protease S1/S4 pockets and are first-line for "
            "atrial fibrillation and venous thromboembolism. Separately, AspH hydroxylates a conserved "
            "Asp/Asn in Factor X's EGF1 domain using Fe(II)/2-oxoglutarate chemistry — an oncofetal "
            "antigen of interest in cancer immunotherapy, which motivated this exact structure series.",
        ],
        "key_facts": [
            "Modular zymogen: Gla – EGF1 – EGF2 – (activation peptide) – serine-protease domain",
            "Vitamin-K-dependent γ-carboxylation of the Gla domain enables Ca²⁺/membrane binding",
            "Xa + Va + Ca²⁺ + phospholipid = prothrombinase, the thrombin-generating complex",
            "Validated anticoagulant target: rivaroxaban, apixaban, edoxaban",
            "Worst case (6Q9F chain B): a 39-mer EGF1 peptide extended through AspH's active site — TM 0.127",
            "Non-amyloid contrast: AF's error is missing biological context (fragment/complex/PTM), not aggregation",
        ],
    },
]

EXAMPLES_BY_UNIPROT = {e["uniprot"]: e for e in EXAMPLES}
