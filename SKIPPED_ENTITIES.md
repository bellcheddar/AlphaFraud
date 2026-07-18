# Skipped Entities — Breakdown

Snapshot from the live droplet DB during the full-archive backfill (2026-07-18, ~99.8% processed).
**13,650 entities skipped** across five buckets. These are terminal by design — they are *not*
reprocessed by `retry-errors` (which only targets `status='error'`) nor by resumable weekly/backfill runs.

## Why they're skipped

| Count | % | Reason | Nature |
|---:|---:|---|---|
| **11,769** | 86% | **No single UniProt mapping** — antibodies, chimeras, engineered constructs, fusion proteins, synthetics | Structural fact — no single AF model exists to compare against |
| **~1,184** | 9% | **No AlphaFold model covering that residue range** — mostly giant multidomain proteins (titin-scale) whose resolved fragment falls outside AF DB's fragmented coverage, plus isoforms AF DB lacks | Coverage gap in AF DB |
| **364** | 3% | **Structure too large (>40 MB)** — the OOM guard for the 3.8 GB droplet | Resource limit (our cap) |
| **~332** | 2% | **Too few residues aligned (<10)** — tiny peptides / mostly-unresolved chains | Nothing meaningful to compare |
| **1** | — | Sequence too short (<3 residues) | Degenerate |

The 86% is exactly what the design intended: AF DB is monomer-and-single-sequence only, so anything
that doesn't map cleanly to one human UniProt accession (an antibody Fab, a designed fusion, a chimera)
has no counterpart model — it's flagged and skipped, not a bug.

## Will they be reprocessed?

**No** — and that's correct for four of the five buckets:

- **`retry-errors` only touches `status='error'`** (`db.py`: `SELECT entity_id FROM entities WHERE status='error'`), *not* `status='skipped'`.
- **Weekly/backfill runs are resumable** — they skip anything already recorded, so a skipped entity stays skipped.

No-UniProt, too-few-aligned, and too-short are **permanent structural properties** — re-running would just re-skip them.

### Worth revisiting

- **The 364 "too large"** are not fundamentally incomparable — they're a memory limitation of the small
  droplet. If `MAX_STRUCT_BYTES` is raised (or the box is upsized), those 364 could be re-attempted.
- **The ~1,184 "no AF model covering range"** are *mostly* permanent, but a subset (giant multidomain
  proteins) could become comparable with improved fragment-selection for >2,700 aa AF models
  (noted as future work).
