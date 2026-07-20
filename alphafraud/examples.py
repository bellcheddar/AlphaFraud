"""Curated 'Examples' deep-dives — four of the worst-offending protein families, each an
instructive AlphaFold failure. Prose was drafted by a Fable-5 research pass (structural biology
+ literature), then wired to live AlphaFraud metrics (see webapp._render_examples). Each example
renders as an identically-formatted annotated panel with an interactive 3D viewer.

Keep the prose here; the numbers come from the DB at render time so they never go stale.
"""

# Ordered worst-first-ish, but curated for a spread of failure modes.
EXAMPLES = [
    {
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
