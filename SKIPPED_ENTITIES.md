# Skipped Entities — Breakdown

Final figures from the completed full-archive backfill (finished 2026-07-18). Of **96,827**
post-cutoff human entities processed, **13,908 were skipped** (14.4%) across five buckets. These are
terminal by design — they are *not* reprocessed by `retry-errors` (which only targets `status='error'`)
nor by resumable weekly/backfill runs.

For context, the completed run analysed **82,796** entities (67,314 fast-screened + 15,482 fully
compared), flagged **1,941 confidently wrong** (2.3% of analysed, 431 of them sequence-novel), and left
**123 unrecoverable errors** (0.1%, broken coordinate-less files).

## Why they're skipped

| Count | Share | Reason | Nature |
|---:|---:|---|---|
| **11,875** | 85% | **No single UniProt mapping** — antibodies, chimeras, engineered constructs, fusion proteins, synthetics | Structural fact: no single AlphaFold model exists to compare against |
| **1,186** | 9% | **No AlphaFold model covering the residue range** — mostly giant multi-domain proteins (titin-scale) whose resolved fragment falls outside AlphaFold DB's fragmented coverage, plus isoforms it lacks | Coverage gap in AlphaFold DB |
| **464** | 3% | **Too few residues aligned (<10)** — tiny peptides or mostly-unresolved chains | Nothing meaningful to compare |
| **381** | 3% | **Structure too large (>40 MB)** — the out-of-memory guard for the 3.8 GB droplet | Resource limit (our cap) |
| **2** | — | Sequence too short (<3 residues) | Degenerate |

The 85% is exactly what the design intended: AlphaFold DB is monomer-and-single-sequence only, so anything
that doesn't map cleanly to one human UniProt accession (an antibody Fab, a designed fusion, a chimera)
has no counterpart model — it's flagged and skipped, not a bug.

## Will they be reprocessed?

**No** — and that's correct for four of the five buckets:

- **`retry-errors` only touches `status='error'`** (`db.py`: `SELECT entity_id FROM entities WHERE status='error'`), *not* `status='skipped'`.
- **Weekly/backfill runs are resumable** — they skip anything already recorded, so a skipped entity stays skipped.

No-UniProt, too-few-aligned, and too-short are **permanent structural properties** — re-running would just re-skip them.

### Worth revisiting

- **The 381 "too large"** are not fundamentally incomparable — they're a memory limitation of the small
  droplet. If `MAX_STRUCT_BYTES` is raised (or the box is upsized), those 381 could be re-attempted.
- **The 1,186 "no AlphaFold model covering range"** are *mostly* permanent, but a subset (giant multi-domain
  proteins) could become comparable with improved fragment-selection for >2,700 aa AlphaFold models
  (noted as future work).
