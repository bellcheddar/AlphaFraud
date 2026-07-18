# Worst-Offending Proteins — Accuracy Spectrum

Captured 2026-07-18 from the completed full-archive backfill. Foundation data for a planned
**family-spectrum analysis tab** (see the README To Do). Aggregated over the 15,482 fully-compared
entities, grouped by UniProt (2,963 distinct proteins; 1,371 with ≥3 depositions).

## The finding that motivates this

AlphaFold DB holds **one blind model per UniProt sequence**, so every experimental deposition of the
same protein is compared against the *same* prediction. Proteins are deposited many times over
(transthyretin ×47, calmodulin ×163, TMEM106B ×22 …), so per-structure views repeat the same
prediction dozens of times. All summaries therefore **deduplicate by protein** — the confidently-wrong
dumbbell collapses to one row per protein (worst deposition, badged `×N`) and the leaderboard carries a
`×N` "Structures" column.

A protein with many depositions that *all* disagree with the one confident model is stronger evidence,
not weaker — e.g. 22 independent TMEM106B structures all at TM ≈ 0.18.

## Important distinction: confidently wrong vs. honest failure

Ranking purely by low TM mixes two very different cases. The tab must separate them:

- **Confidently wrong** (high pLDDT, low TM): AlphaFold was sure and missed. This is the headline "fraud".
- **Honest failure** (low TM *and* low pLDDT): AlphaFold flagged its own uncertainty; a low-confidence
  miss is not a fraud. (e.g. Alpha-inhibin `P04279` median TM 0.16 but pLDDT 30; EPAS1 `Q99814` TM 0.21
  at pLDDT 49 — `confidently_wrong` fraction 0.)

## Tier 1 — Confidently wrong (high pLDDT, low TM) — the headline catches

| UniProt | ×N | median TM | mean pLDDT | CW frac | Protein |
|---|---:|---:|---:|---:|---|
| Q14571 | 6 | 0.08 | 90 | 1.00 | Inositol 1,4,5-trisphosphate receptor (fragment) |
| O14960 | 7 | 0.17 | **97** | 1.00 | Leukocyte cell-derived chemotaxin-2 |
| P02489 | 5 | 0.17 | 86 | 1.00 | Alpha-crystallin A chain |
| P63261 | 4 | 0.18 | 96 | 1.00 | Actin, cytoplasmic 2 |
| Q9NUM4 | 22 | 0.18 | 93 | 0.95 | Transmembrane protein 106B (TMEM106B, amyloid) |
| P00742 | 29 | 0.21 | 91 | 0.86 | Coagulation factor X |
| P20382 | 6 | 0.21 | 71 | 0.83 | Melanin-concentrating hormone |

## Tier 2 — Intermediate / conformational disagreement (median TM ~0.5–0.7)

Often flexible or multidomain proteins where AlphaFold gets the fold but not the deposited conformation.

| UniProt | ×N | median TM | min TM | mean pLDDT | Protein |
|---|---:|---:|---:|---:|---|
| P49917 | 19 | 0.50 | 0.35 | 88 | DNA ligase 4 |
| P04049 | 14 | 0.50 | 0.26 | 71 | RAF proto-oncogene Ser/Thr kinase |
| Q7Z7F7 | 43 | 0.51 | 0.27 | 89 | 39S ribosomal protein L55, mitochondrial |
| P0DP23 | 163 | 0.51 | 0.39 | 87 | Calmodulin-1 (canonical flexible dumbbell) |
| P27694 | 5 | 0.51 | 0.44 | 90 | Replication protein A 70 kDa subunit |

## Tier 3 — Well-predicted (median TM ~1.0) — the control set

Classic well-folded enzymes AlphaFold nails; useful as the "AlphaFold works here" contrast.

| UniProt | ×N | median TM | mean pLDDT | Protein |
|---|---:|---:|---:|---|
| O43570 | 8 | 1.00 | 98 | Carbonic anhydrase 12 |
| P12821 | 4 | 1.00 | 95 | Angiotensin-converting enzyme |
| P50579 | 6 | 1.00 | 98 | Methionine aminopeptidase 2 |
| P08473 | 5 | 1.00 | 98 | Neprilysin |
| P18858 | 7 | 1.00 | 94 | DNA ligase 1 (contrast with ligase 4 above) |
| P15121 | 9 | 1.00 | 98 | Aldo-keto reductase family 1 member B1 |

## Notes for building the tab

- Filter to families with ≥3 depositions so a "family verdict" is well-sampled (1,371 qualify).
- Rank Tier 1 by `confidently_wrong` fraction × (1 − median TM), not TM alone, to exclude honest failures.
- The DNA ligase 1 (well-predicted) vs DNA ligase 4 (intermediate) pairing is a nice within-family contrast.
- Consider grouping by structural/functional family (Pfam / CATH — the Analysis tab already computes CATH
  enrichment) so the spectrum reads as families, not just individual proteins.
