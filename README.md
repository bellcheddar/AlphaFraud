# 🧬 AlphaFraud

> **Catch AlphaFold where the fold is wrong: weekly, automatically, on freshly deposited human structures.**

[![live](https://img.shields.io/badge/live-alphafraud.mdeller.com-00d084)](https://alphafraud.mdeller.com) ![python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white) ![flask](https://img.shields.io/badge/web-Flask%20%2B%20gunicorn-000000?logo=flask&logoColor=white) ![data](https://img.shields.io/badge/data-RCSB%20PDB%20%2B%20AlphaFold%20DB-1e73be) ![status](https://img.shields.io/badge/status-in%20development-fcb900) [![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21808182-1C244B?logo=doi&logoColor=white)](https://doi.org/10.5281/zenodo.21808182) ![code](https://img.shields.io/badge/code-MIT-9b51e0) ![author](https://img.shields.io/badge/author-Marc%20C.%20Deller%2C%20D.Phil.-1C244B)

<table>
<tr>
<td>🌐 <b>Website</b></td><td><a href="https://alphafraud.mdeller.com" target="_blank" rel="noopener noreferrer">alphafraud.mdeller.com</a></td>
<td>✉️ <b>Contact</b></td><td><a href="mailto:marc@marcdeller.com">marc@marcdeller.com</a></td>
<td>🐙 <b>GitHub</b></td><td><a href="https://github.com/bellcheddar/AlphaFraud" target="_blank" rel="noopener noreferrer">bellcheddar/AlphaFraud</a></td>
</tr>
</table>

---

AlphaFraud watches the RCSB PDB for newly deposited human protein structures, matches each one to its blind AlphaFold prediction from the AlphaFold Structure Database (EBI), superposes them, and quantifies exactly where the prediction disagrees with the experiment. AlphaFold2 was trained only on PDB chains released before 2018-04-30, so any human structure deposited after that date is something the model predicted without ever seeing its coordinates: the ideal test set.

**Why it matters:** the claim that "AlphaFold has solved protein folding" is only testable on structures the model never trained on, and those arrive continuously as the PDB grows. AlphaFraud turns that stream into a standing experiment: every week it surfaces the structures AlphaFold got most wrong, and ranks the "confidently wrong" cases (high pLDDT, low agreement) where the model was sure and still missed. It is useful for: structural biologists auditing AlphaFold reliability, method developers looking for hard cases, and anyone testing whether predicted models are safe to build on.

**A live instance runs at [alphafraud.mdeller.com](https://alphafraud.mdeller.com)**, having backfilled the entire post-cutoff archive (96,827 human protein entities, 82,796 analysed) and updating every week. The landing page is a cumulative dashboard across every processed week; the worst offenders so far are a roster of amyloid-forming proteins (transthyretin, β2-microglobulin, islet amyloid polypeptide) that AlphaFold predicts as confidently folded but which crystallise or cryo-EM in a completely different aggregated form.

## ✨ Features

| Capability | What it does |
|---|---|
| Automated PDB watch | Weekly systemd timer fires after the PDB's Wednesday 00:00 UTC release; resumes from the last processed run |
| Human, post-cutoff filter | RCSB Search for taxonomy 9606 protein entities deposited after AlphaFold's 2018-04-30 training cutoff |
| Blind-model matching | Maps each entity to its UniProt accession and AlphaFold DB model, handling fragments, mutants and missing loops via sequence alignment |
| Sequence-novelty score | Max percent identity to any pre-cutoff PDB chain, so genuinely unseen sequences are flagged (not just easy homologs) |
| Full metric suite | Global, local, backbone, per-domain and confidence-calibration metrics (see below) |
| Confidence audit | pLDDT vs actual lDDT calibration, and a PAE-honesty check comparing AlphaFold's self-reported error to the observed error |
| Two-tier archive backfill | A fast TM-score screen across every structure, running the full metric suite only on the disagreements; makes the whole ~96k-entity archive tractable |
| Structural imagery | Every worst offender is drawn as a deviation-coloured Cα ribbon (the experimental structure, coloured residue-by-residue by its distance from the AlphaFold model, on an absolute-Ångström scale) on the leaderboard, entry page and weekly highlights; an interactive 3Dmol.js viewer with an optional translucent AlphaFold "ghost" overlay; hover-preview thumbnails on the scatter; and a "divergence" ribbon banner in the header |
| On-demand Calculate tab | Type any human PDB ID and the full pipeline runs on demand (fetch AlphaFold model, superpose, score, render) to return the auto-example panel, with strict autocomplete (exists + human + has an AlphaFold model) and no LLM |
| Home & live Statistics | A Home navigation page outlining every tab, and an exhaustive Statistics page grouping all KPIs, coverage, runs, server (CPU/memory/uptime), storage/database and API stats into themed panels |
| Cumulative dashboard | Default landing page aggregating every processed week: the "fraud quadrant" scatter, metric histograms, a weekly trend, and a browsable per-week / per-structure archive |
| Branded, mobile-responsive report | Flask app with the signature scatter, heatmaps, per-domain tables and an all-time leaderboard; every plot has a CSV export and a plain-language explanatory panel that defines each metric twice over (a lay sentence and the underlying equation), and every table exports to CSV |
| One-command deploy | Provisioning, deploy and one-shot release scripts for a DigitalOcean droplet (gunicorn, nginx, certbot TLS) |

## 🏗️ Architecture and workflow

One controller (`AlphaFraud.py`, subcommands) drives a small Python package; a Flask app serves the results. Two runtimes share one SQLite file: a **systemd timer** runs the weekly pipeline (writes the database and the ribbon/coords assets), and an always-on **gunicorn** process serves the site by reading that same database live.

| Module | Responsibility |
|---|---|
| `pdb.py` | RCSB Search (new human protein entities) + Data GraphQL (UniProt mapping, dates, method) |
| `afdb.py` | AlphaFold DB fetch: the blind model + PAE, choosing the fragment covering the entity's span |
| `novelty.py` | max % identity to any pre-cutoff chain (so genuinely unseen sequences are flagged) |
| `compare.py` | the full metric suite on the aligned span (TM, lDDT, GDT, RMSD, per-residue deviation, PAE honesty) |
| `ribbon.py` | Cα-deviation SVG + 3D-viewer coords + the AlphaFold "ghost" (vendored, offline) |
| `annotate.py` / `analysis.py` | CATH / SCOP / citation enrichment and the `/analysis` snapshot (enrichment, clustering, PCA) |
| `examples_auto.py` | the deterministic, no-LLM panel builder (match **or** failure framing) |
| `calc_index.py` / `calculate.py` | the Calculate tab's strict autocomplete index + on-demand single-entity compute |
| `db.py` / `report.py` / `webapp.py` | SQLite persistence, Plotly figure JSON, and the Flask routes |

**The weekly pipeline** (`AlphaFraud.py run`, one entity at a time):

```text
for entity in RCSB.search(human, protein, deposited_after = 2018-04-30):
    if entity in db: continue
    meta = RCSB.graphql(entity)                       # UniProt, dates, method, chains
    if not meta.single_uniprot: skip("antibody / fusion / chimera"); continue
    af = AlphaFoldDB.model(meta.uniprot)              # the blind prediction (fragment covering the span)
    if af is None:               skip("no AlphaFold model"); continue
    exp, model = download(entity), download(af)
    m        = compare(exp, model)                    # TM, lDDT, GDT, RMSD, per-residue dev, PAE honesty
    novelty  = max_identity_to_pre_cutoff(meta.sequence)
    fraud    = mean_i( pLDDT_i/100 * clamp(dev_i, 0, 15Å) / 15 )   # confidence-weighted error
    confidently_wrong = (mean_pLDDT > 70) and (TM < 0.5)          # sure, and still wrong
    ribbon.render(exp, model)                         # deviation SVG + coords + AF ghost
    db.store(entity, m, novelty, fraud, confidently_wrong)

analysis.rebuild()            # /analysis enrichment snapshot
rebuild_weekly_examples()     # auto 'example of the week' + weekly archive
calc_index.refresh(metas)     # keep the Calculate autocomplete index current
```

**The always-on web app** (gunicorn) reads the same SQLite and renders cached Plotly JSON:

```text
GET /            -> cumulative "fraud quadrant" dashboard (figures cached, short TTL)
GET /entry/<id>  -> per-structure heatmaps, calibration, per-domain metrics
GET /examples    -> positive control + auto example-of-the-week + curated deep-dives
GET /calculate   -> type a human PDB id  ->  (reuse if known | compute on demand)  ->  panel
```

**The Calculate tab** reuses the very same `process_entity()` as the pipeline, run in an isolated subprocess so a heavy computation never blocks a web worker, and stored apart so it never pollutes the science:

```text
POST /calculate/run { pdb }:
    entity = resolve_human_entity(pdb)                # strict index, else a live RCSB check
    if not qualifies:  return reason                 # not human / no single UniProt / no AF model
    if entity already computed:  return "ready"      # cached -> instant
    mark(entity, "computing"); spawn AlphaFraud.py calculate <entity>   # same pipeline, subprocess
    return "computing"                               # the browser polls, then injects the panel
```

## 🎯 Metric suite

Every matched structure is scored on the aligned residue span (all pure-Python except CATH, which is a lookup):

| Family | Metrics |
|---|---|
| Global fold agreement | TM-score (4 normalisations), Cα / backbone / all-atom / core RMSD, GDT_TS, GDT_HA, MaxSub, structural overlap |
| Local, superposition-free | lDDT (global and per-residue), contact-map Jaccard / precision / recall, distance-matrix difference, CAD-score |
| Backbone and secondary structure | Q3 secondary-structure agreement, mean Δφ / Δψ, radius-of-gyration difference |
| Domains | Per-CATH-domain and per-PAE-cluster-domain TM and RMSD (exposes inter-domain hinge errors a global fit hides) |
| Confidence calibration | pLDDT vs lDDT correlation, PAE vs observed-error correlation, overconfident-pair fraction |
| Composite | FRAUD score (confidence-weighted error) and a confidently-wrong flag (mean pLDDT > 70 yet TM-score < 0.5) |

## 📋 Requirements

- Python 3.11 or newer
- The packages in `requirements.txt` (requests, tenacity, biotite, tmtools, numpy, scipy, pandas, plotly, flask, gunicorn, python-dotenv), all pip-installable with no compiled toolchain
- Outbound HTTPS to `search.rcsb.org`, `data.rcsb.org`, `files.rcsb.org` and `alphafoldebi.ac.uk`
- For deployment: a Linux droplet with root/SSH access, a domain, and DNS pointed at it

## 🔧 Installation

```bash
git clone https://github.com/bellcheddar/AlphaFraud.git
cd AlphaFraud
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 AlphaFraud.py init          # create dirs, DB schema, vendor plotly.min.js
```

## 🚀 Usage

```bash
# Preview discovery for a window without writing anything
python3 AlphaFraud.py run --since 2024-01-01 --until 2024-01-10 --limit 6 --dry-run

# Process a window for real (omit --since to resume from the last run)
python3 AlphaFraud.py run --since 2024-01-01 --limit 50

# Backfill a historical range (full metrics on everything)
python3 AlphaFraud.py backfill --from 2023-01-01 --to 2023-12-31

# Two-tier backfill: fast TM-score screen on everything, full metrics only on the
# disagreements (TM below --tm-threshold). Far cheaper on time, disk and API load.
python3 AlphaFraud.py backfill --from 2023-01-01 --to 2023-12-31 --two-tier --tm-threshold 0.7

# Two-tier backfill of the ENTIRE post-cutoff archive (~96k entities, monthly chunks,
# resumable). Screens all, fully analyses only the tail AlphaFold got wrong.
python3 AlphaFraud.py backfill --all --two-tier

# --workers N adds a download thread pool (network-bound work parallelises well). Single-
# threaded is the reliable default for long unattended runs; workers give a partial speedup
# but are more sensitive to the droplet's core count.
python3 AlphaFraud.py backfill --all --two-tier --workers 6

# Database summary + worst-offenders leaderboard
python3 AlphaFraud.py status

# Local dev web server (production uses gunicorn)
python3 AlphaFraud.py serve --port 8000
```

| Command | Purpose |
|---|---|
| `init` | Create directories, the SQLite schema, and vendor `plotly.min.js` |
| `run` | Discover, match, score and store one deposit window (`--since`, `--until`, `--limit`, `--dry-run`) |
| `backfill` | Process a historical window (`--from`, `--to`); `--two-tier` screens by TM-score and fully analyses only disagreements below `--tm-threshold`; `--all` covers the entire post-cutoff archive in resumable monthly chunks |
| `status` | Print a database summary and the current leaderboard |
| `serve` | Run the Flask app locally (`--port`, `--debug`) |

## 📊 Output

The web app serves live from SQLite. Every plot carries a plain-language explanatory panel (what the axes mean, the cutoffs, a take-home summary, and a per-metric breakdown giving both a lay explanation and the equation, e.g. `TM = (1/L) Σᵢ 1/(1 + (dᵢ/d₀)²)`) plus a CSV export; every table exports to CSV too.

The site is live at **[alphafraud.mdeller.com](https://alphafraud.mdeller.com/)**.

| Route | Shows |
|---|---|
| [`/`](https://alphafraud.mdeller.com/) | Home — a concise navigation page: the project's purpose, headline KPIs, and a colour-coded card per tab with a "what you'll learn" line |
| [`/all`](https://alphafraud.mdeller.com/all) | Cumulative "All structures" dashboard across every processed week: KPIs, the pLDDT-vs-TM fraud-quadrant scatter, metric histograms, the weekly trend, and a top-ranked table. A pulldown jumps to any single week |
| `/week/<label>` | One release week, same layout scoped to that batch |
| `/entry/<id>` | Per-structure detail: per-residue error tracks, calibration scatter, distance-matrix and PAE-vs-observed heatmaps, per-domain breakdown, and every metric |
| [`/leaderboard`](https://alphafraud.mdeller.com/leaderboard) | The all-time worst AlphaFold failures across every processed week |
| [`/analysis`](https://alphafraud.mdeller.com/analysis) | Structural deep dive over the worst offenders: fold/family enrichment (Wilson-CI + Fisher), sequence-similarity clustering, failure-mode PCA, theme flags, per-superfamily blind-spot scorecards, conformational-heterogeneity detection, a "new this week" ribbon, and RCSB + DOI links on every structure |
| [`/examples`](https://alphafraud.mdeller.com/examples) | Curated storytelling layer: a positive control (an excellent AlphaFold match), an auto-generated "example of the week" plus a full weekly-release archive, and hand-authored deep-dive panels with interactive viewers (see below) |
| [`/calculate`](https://alphafraud.mdeller.com/calculate) | Type any human PDB ID and get the same panel computed on demand: strict autocomplete (exists + human + has an AlphaFold model), full pipeline in an isolated subprocess, no LLM (see below) |
| [`/archive`](https://alphafraud.mdeller.com/archive) | Every PDB release week since the 2018 cutoff, at weekly granularity, each linking to that week's structures and confidently-wrong count |
| [`/stats`](https://alphafraud.mdeller.com/stats) | An exhaustive live Statistics page: themed panels for catch/quality, coverage & schedule, runs & compute, server (CPU/memory/uptime), storage & database, data sources & APIs, and traffic |
| `/api/week/<label>`, `/api/leaderboard`, `/api/entry/<id>` | JSON for external tools |

## 🔬 Examples

The **[Examples](https://alphafraud.mdeller.com/examples)** tab turns raw catches into readable stories and deliberately shows both sides of AlphaFold's record, not just the failures:

- **A positive control.** The page opens with the one thing the rest of the site does not: an *excellent* match. Human **[Artemis (DCLRE1C)](https://alphafraud.mdeller.com/examples#ex-6TT5_1)**, a genuinely novel post-cutoff nuclease (only 29% identity to anything AlphaFold trained on), was predicted blind to TM-score 0.996, lDDT 0.985 and 0.45 Å Cα-RMSD at a justified mean pLDDT of 95, and AlphaFraud scores it FRAUD 0.02. It is the proof that the pipeline certifies good predictions, not just hunts for bad ones.
- **An auto ["example of the week"](https://alphafraud.mdeller.com/examples).** After every weekly run the pipeline picks that release's most instructive confidently-wrong catch and writes its panel deterministically from the database (no LLM), badged and dated.
- **A [complete weekly archive](https://alphafraud.mdeller.com/examples).** Every PDB release week since the 2018 cutoff is listed: weeks with a catch expand to a full panel with its Cα-deviation ribbon, and the quiet weeks (where AlphaFold was never overconfident) are recorded too, collapsed to the most recent by default.
- **Curated deep-dives.** Hand-authored panels across the failure spectrum: ordinary single-chain globular folds AlphaFold gets *subtly* wrong (right fold, wrong conformation or assembly — the [PP2A scaffold](https://alphafraud.mdeller.com/examples#ex-8UWB_3), [STIM1](https://alphafraud.mdeller.com/examples#ex-6YEL_1), [Aha1](https://alphafraud.mdeller.com/examples#ex-7DME_1), [WWP2](https://alphafraud.mdeller.com/examples#ex-6RSS_1)) and the dramatic whole-fold catastrophes ([TMEM106B](https://alphafraud.mdeller.com/examples#ex-7U14_1), [alpha-synuclein](https://alphafraud.mdeller.com/examples#ex-9A1Q_1), [transthyretin](https://alphafraud.mdeller.com/examples#ex-9BZS_1), [factor X](https://alphafraud.mdeller.com/examples#ex-6Q9F_2)). Each panel carries live metrics, an interactive 3Dmol.js viewer (deviation colouring plus the AlphaFold "ghost") and a structure / mechanism / disease write-up.
- **Linked from the scatter.** The curated examples are overlaid on the [home fraud-quadrant plot](https://alphafraud.mdeller.com/) as pulsing red (failure) and green (accurate) markers, each labelled with its protein name and clickable straight through to its panel.

Each panel is summarised below — click any title to open its live, interactive version. Metrics: **TM-score** and **lDDT** (1.0 = identical), **Cα-RMSD** (0 Å = identical), **pLDDT** (AlphaFold's own confidence, 0–100), **FRAUD** (confidence-weighted error, higher = worse), **novelty** (100% = wholly unseen before AlphaFold's cutoff).

### 🟢 Protein Artemis (DCLRE1C) · [`6TT5_1`](https://alphafraud.mdeller.com/examples#ex-6TT5_1)

| Field | Detail |
|---|---|
| **Take-home** | A novel post-cutoff nuclease AlphaFold predicted blind almost perfectly — the control proving AlphaFraud certifies good predictions, not only failures |
| **AlphaFold vs experimental** | <a href="https://alphafraud.mdeller.com/examples#ex-6TT5_1"><img src="https://alphafraud.mdeller.com/ribbon/6TT5_1.svg" alt="Experimental structure of 6TT5_1 coloured by Cα deviation from AlphaFold" width="380"></a><br><sub>Experimental structure coloured by Cα deviation from AlphaFold (blue = agree, red = diverges) — click for the interactive 3D viewer with the AlphaFold "ghost" overlay</sub> |
| **Link to live example** | **[Open the interactive panel →](https://alphafraud.mdeller.com/examples#ex-6TT5_1)** |
| **KPIs** | TM **0.996** · lDDT 0.985 · pLDDT 95.2 · Cα-RMSD 0.45 Å · FRAUD **0.02** · novelty 71% |
| **Stats** | 11 depositions, **0** confidently wrong · SS-Q3 92.5% · pLDDT↔lDDT +0.56 (calibrated) |
| **Structure** | Metallo-β-lactamase + β-CASP nuclease domain with a Zn active site; the disordered regulatory C-terminus sits (correctly) outside the crystallised fold |
| **Why AlphaFold gets it right** | A single, conserved globular domain with a deep MSA and one native conformation — AlphaFold's ideal regime; confidence is earned (PAE-overconfident 0.00) |
| **Biology & disease** | NHEJ endonuclease that opens V(D)J hairpins with DNA-PKcs; loss of function causes radiosensitive SCID / Omenn; pursued as a radiosensitiser drug target |
| **Key fact** | 29% identity to anything pre-cutoff yet GDT_TS 99.2 — genuine generalisation, not memorisation |

### 🔴 PP2A scaffold subunit A / PR65 (PPP2R1A) · [`8UWB_3`](https://alphafraud.mdeller.com/examples#ex-8UWB_3)

| Field | Detail |
|---|---|
| **Take-home** | Near-maximal confidence (pLDDT 97) on a flexible 15-HEAT solenoid whose curvature is wrong for 99% of residues |
| **AlphaFold vs experimental** | <a href="https://alphafraud.mdeller.com/examples#ex-8UWB_3"><img src="https://alphafraud.mdeller.com/ribbon/8UWB_3.svg" alt="Experimental structure of 8UWB_3 coloured by Cα deviation from AlphaFold" width="380"></a><br><sub>Experimental structure coloured by Cα deviation from AlphaFold (blue = agree, red = diverges) — click for the interactive 3D viewer with the AlphaFold "ghost" overlay</sub> |
| **Link to live example** | **[Open the interactive panel →](https://alphafraud.mdeller.com/examples#ex-8UWB_3)** |
| **KPIs** | TM 0.293 · lDDT 0.311 · pLDDT 96.8 · Cα-RMSD 15.0 Å · FRAUD 0.77 · novelty 0% |
| **Stats** | 26 depositions, 1 confidently wrong (this one) · pLDDT↔lDDT −0.13 (confidence carries no signal) |
| **Structure** | 15 tandem HEAT repeats forming a horseshoe α-solenoid — a spring, not a fixed ruler |
| **Why AlphaFold gets it wrong** | Local helices are right, but tiny per-repeat hinge errors compound across 15 repeats into a grossly wrong global shape — a curvature failure, not a fold failure |
| **Biology & disease** | Sole scaffold of the PP2A tumour-suppressor phosphatase; cancer hotspots (P179R, R183, S256F…) cluster in the B56-binding repeats |
| **Key fact** | The source paper needed an experimental trimer structure to guide the prediction |

### 🔴 Stromal interaction molecule 1 / CC1 (STIM1) · [`6YEL_1`](https://alphafraud.mdeller.com/examples#ex-6YEL_1)

| Field | Detail |
|---|---|
| **Take-home** | A bistable three-helix Ca²⁺ switch; AlphaFold committed to one conformer, the structure is the other |
| **AlphaFold vs experimental** | <a href="https://alphafraud.mdeller.com/examples#ex-6YEL_1"><img src="https://alphafraud.mdeller.com/ribbon/6YEL_1.svg" alt="Experimental structure of 6YEL_1 coloured by Cα deviation from AlphaFold" width="380"></a><br><sub>Experimental structure coloured by Cα deviation from AlphaFold (blue = agree, red = diverges) — click for the interactive 3D viewer with the AlphaFold "ghost" overlay</sub> |
| **Link to live example** | **[Open the interactive panel →](https://alphafraud.mdeller.com/examples#ex-6YEL_1)** |
| **KPIs** | TM 0.389 · lDDT 0.341 · pLDDT 78.9 · Cα-RMSD 35.8 Å · FRAUD 0.75 · novelty 2% |
| **Stats** | 1 deposition, confidently wrong · SS-Q3 69.6% (secondary structure right, packing wrong) |
| **Structure** | CC1 is a compact antiparallel three-helix bundle that toggles between clamped (resting) and extended (active) states |
| **Why AlphaFold gets it wrong** | Right fold class, wrong tertiary packing — a single-answer predictor cannot represent a two-state switch |
| **Biology & disease** | Gates store-operated Ca²⁺ entry via Orai1; gain-of-function → Stormorken / tubular aggregate myopathy; loss → CRAC-channelopathy |
| **Key fact** | 35.8 Å RMSD with correct secondary structure = a conformer error, not a misfold |

### 🔴 Activator of Hsp90 ATPase 1 / Aha1 (AHSA1) · [`7DME_1`](https://alphafraud.mdeller.com/examples#ex-7DME_1)

| Field | Detail |
|---|---|
| **Take-home** | Two well-folded domains bolted together at the wrong angle — a flexible-linker ensemble collapsed to one guess |
| **AlphaFold vs experimental** | <a href="https://alphafraud.mdeller.com/examples#ex-7DME_1"><img src="https://alphafraud.mdeller.com/ribbon/7DME_1.svg" alt="Experimental structure of 7DME_1 coloured by Cα deviation from AlphaFold" width="380"></a><br><sub>Experimental structure coloured by Cα deviation from AlphaFold (blue = agree, red = diverges) — click for the interactive 3D viewer with the AlphaFold "ghost" overlay</sub> |
| **Link to live example** | **[Open the interactive panel →](https://alphafraud.mdeller.com/examples#ex-7DME_1)** |
| **KPIs** | TM 0.432 · lDDT 0.748 · pLDDT 83.3 · Cα-RMSD 23.4 Å · FRAUD 0.82 · novelty 0% |
| **Stats** | 4 depositions, 1 confidently wrong · pLDDT↔lDDT +0.33 (high confidence hides the joint) |
| **Structure** | N- and C-terminal domains on a partly-ordered linker; each folds correctly in isolation |
| **Why AlphaFold gets it wrong** | Domains are right (lDDT 0.75) but their relative orientation is wrong (TM 0.43) — a conformational-ensemble failure, not a misfold |
| **Biology & disease** | Strongest stimulator of the Hsp90 ATPase; drives ΔF508-CFTR maturation (cystic-fibrosis target) and pathological tau |
| **Key fact** | The pieces are right; only the assembly instruction is wrong |

### 🔴 NEDD4-like E3 ligase WWP2 / WW module (WWP2) · [`6RSS_1`](https://alphafraud.mdeller.com/examples#ex-6RSS_1)

| Field | Detail |
|---|---|
| **Take-home** | A tiny two-Trp β-sheet AlphaFold folds fine, but the deposited chain's inter-module geometry is flexible — and, tellingly, the model was honestly unsure |
| **AlphaFold vs experimental** | <a href="https://alphafraud.mdeller.com/examples#ex-6RSS_1"><img src="https://alphafraud.mdeller.com/ribbon/6RSS_1.svg" alt="Experimental structure of 6RSS_1 coloured by Cα deviation from AlphaFold" width="380"></a><br><sub>Experimental structure coloured by Cα deviation from AlphaFold (blue = agree, red = diverges) — click for the interactive 3D viewer with the AlphaFold "ghost" overlay</sub> |
| **Link to live example** | **[Open the interactive panel →](https://alphafraud.mdeller.com/examples#ex-6RSS_1)** |
| **KPIs** | TM 0.46 · lDDT 0.503 · pLDDT 74.5 · Cα-RMSD 21.9 Å · FRAUD 0.71 · novelty 8% |
| **Stats** | 7 depositions, 1 confidently wrong · pLDDT↔lDDT +0.15 (lowest confidence of the set) |
| **Structure** | NEDD4-family HECT E3 ligase; the WW domain is a ~38-residue three-stranded antiparallel β-sheet that reads PPxY motifs |
| **Why AlphaFold gets it wrong** | Uncertain relative orientation between small folded modules — and its low pLDDT half-admits the uncertainty |
| **Biology & disease** | Ubiquitinates SMAD7, PTEN, TP53, OCT4; isoform balance shifts drive EMT and metastasis |
| **Key fact** | The "honest" failure of the set — low confidence tracking real uncertainty |

### 🔴 Transmembrane protein 106B (TMEM106B) · [`7U14_1`](https://alphafraud.mdeller.com/examples#ex-7U14_1)

| Field | Detail |
|---|---|
| **Take-home** | AlphaFold built a tidy globular β-sandwich at pLDDT 94; the real structure is a novel brain amyloid — every ordered residue wrong |
| **AlphaFold vs experimental** | <a href="https://alphafraud.mdeller.com/examples#ex-7U14_1"><img src="https://alphafraud.mdeller.com/ribbon/7U14_1.svg" alt="Experimental structure of 7U14_1 coloured by Cα deviation from AlphaFold" width="380"></a><br><sub>Experimental structure coloured by Cα deviation from AlphaFold (blue = agree, red = diverges) — click for the interactive 3D viewer with the AlphaFold "ghost" overlay</sub> |
| **Link to live example** | **[Open the interactive panel →](https://alphafraud.mdeller.com/examples#ex-7U14_1)** |
| **KPIs** | TM 0.157 · lDDT 0.536 · pLDDT 94.4 · Cα-RMSD 27.1 Å · FRAUD 0.87 · novelty **100%** |
| **Stats** | 29 depositions, **27** confidently wrong · pLDDT↔lDDT 0.03 (confidence uninformative) |
| **Structure** | Native luminal domain is a fibronectin-III β-sandwich; the deposited form is a five-layered cross-β amyloid core |
| **Why AlphaFold gets it wrong** | Amyloid is a self-templating polymer state absent from training, and the sequence is 100% novel — nothing steers it off its globular prior |
| **Biology & disease** | Lysosomal protein; top GWAS hit for FTLD-TDP; its C-terminal domain forms fibrils across ageing and neurodegeneration |
| **Key fact** | 100% sequence-novel — no pre-2018 fibril template existed |

### 🔴 Alpha-synuclein (SNCA) · [`9A1Q_1`](https://alphafraud.mdeller.com/examples#ex-9A1Q_1)

| Field | Detail |
|---|---|
| **Take-home** | A protein with no single fold; AlphaFold's confidence is actively *anti*-correlated with accuracy |
| **AlphaFold vs experimental** | <a href="https://alphafraud.mdeller.com/examples#ex-9A1Q_1"><img src="https://alphafraud.mdeller.com/ribbon/9A1Q_1.svg" alt="Experimental structure of 9A1Q_1 coloured by Cα deviation from AlphaFold" width="380"></a><br><sub>Experimental structure coloured by Cα deviation from AlphaFold (blue = agree, red = diverges) — click for the interactive 3D viewer with the AlphaFold "ghost" overlay</sub> |
| **Link to live example** | **[Open the interactive panel →](https://alphafraud.mdeller.com/examples#ex-9A1Q_1)** |
| **KPIs** | TM 0.138 · lDDT 0.177 · pLDDT 75.2 · Cα-RMSD 36.3 Å · FRAUD 0.71 · novelty 0% |
| **Stats** | **210** depositions, **206** confidently wrong — the archive's most-repeated failure · pLDDT↔lDDT −0.29 |
| **Structure** | 140-residue intrinsically disordered monomer; the deposited forms are cryo-EM cross-β fibrils |
| **Why AlphaFold gets it wrong** | No native fold to predict, and polymorph-specific packing is not in the sequence — where it is more confident it is measurably more wrong |
| **Biology & disease** | Presynaptic protein; fibrils define Parkinson's, DLB and multiple system atrophy; PD mutations A30P/E46K/H50Q/G51D/A53T |
| **Key fact** | 210 depositions, 206 confidently wrong — the most-deposited catch on the site |

### 🔴 Transthyretin (TTR) · [`9BZS_1`](https://alphafraud.mdeller.com/examples#ex-9BZS_1)

| Field | Detail |
|---|---|
| **Take-home** | pLDDT 98 on the native tetramer fold; the deposited cardiac amyloid fibril scores TM 0.21 — one of the starkest confidently-wrong cases |
| **AlphaFold vs experimental** | <a href="https://alphafraud.mdeller.com/examples#ex-9BZS_1"><img src="https://alphafraud.mdeller.com/ribbon/9BZS_1.svg" alt="Experimental structure of 9BZS_1 coloured by Cα deviation from AlphaFold" width="380"></a><br><sub>Experimental structure coloured by Cα deviation from AlphaFold (blue = agree, red = diverges) — click for the interactive 3D viewer with the AlphaFold "ghost" overlay</sub> |
| **Link to live example** | **[Open the interactive panel →](https://alphafraud.mdeller.com/examples#ex-9BZS_1)** |
| **KPIs** | TM 0.214 · lDDT 0.489 · pLDDT 98.0 · Cα-RMSD 22.8 Å · FRAUD **0.95** · novelty 0% |
| **Stats** | 160 depositions, 34 confidently wrong · pLDDT↔lDDT −0.16 |
| **Structure** | Native 127-aa β-sandwich homotetramer with thyroxine sites; the amyloid form is a cross-β fibril from cleaved segments |
| **Why AlphaFold gets it wrong** | A wrong-*state* failure: pLDDT measures confidence in the known native fold, not whether a deposition *is* that state; TTR is 0% novel, squarely in training |
| **Biology & disease** | Thyroxine/retinol transporter; ATTR amyloidosis (wild-type cardiac + hereditary V30M); uniquely druggable (tafamidis, patisiran) |
| **Key fact** | FRAUD 0.95 — near the very top of the whole site |

### 🔴 Coagulation factor X (F10) · [`6Q9F_2`](https://alphafraud.mdeller.com/examples#ex-6Q9F_2)

| Field | Detail |
|---|---|
| **Take-home** | Not a refold but a wrong-*context* capture — a 39-residue EGF1 fragment threaded through a partner enzyme's active site |
| **AlphaFold vs experimental** | <a href="https://alphafraud.mdeller.com/examples#ex-6Q9F_2"><img src="https://alphafraud.mdeller.com/ribbon/6Q9F_2.svg" alt="Experimental structure of 6Q9F_2 coloured by Cα deviation from AlphaFold" width="380"></a><br><sub>Experimental structure coloured by Cα deviation from AlphaFold (blue = agree, red = diverges) — click for the interactive 3D viewer with the AlphaFold "ghost" overlay</sub> |
| **Link to live example** | **[Open the interactive panel →](https://alphafraud.mdeller.com/examples#ex-6Q9F_2)** |
| **KPIs** | TM 0.127 · lDDT 0.468 · pLDDT 93.5 · Cα-RMSD 6.6 Å · FRAUD 0.37 · novelty 0% |
| **Stats** | 47 depositions, 26 confidently wrong · pLDDT↔lDDT −0.59 |
| **Structure** | Modular zymogen (Gla–EGF1–EGF2–protease); the worst deposition is a linear EGF1 peptide in AspH's channel, not a folded module |
| **Why AlphaFold gets it wrong** | A context failure, not aggregation — the RMSD is modest (6.6 Å) but TM collapses because a linear fragment has no compact fold to superpose |
| **Biology & disease** | Central coagulation zymogen; activated factor Xa is the target of rivaroxaban, apixaban and edoxaban |
| **Key fact** | The non-amyloid contrast — the error is missing biological context (fragment / complex / PTM), not misfolding |

## 🧪 Calculate

The **[Calculate](https://alphafraud.mdeller.com/calculate)** tab runs the whole pipeline on demand for any human PDB ID you type and returns the same panel format as the auto examples — KPIs, the Cα-deviation ribbon, the interactive 3D viewer and a deterministic write-up — with **no AI-generated text**.

- **Strict autocomplete.** The input only completes to entries that (1) exist, (2) are human, and (3) have an AlphaFold model. That comes from a precomputed index — seeded for free from the corpus (the ~83k entities already carrying a confirmed AlphaFold model), back-filled with a one-off pre-cutoff human sweep, and refreshed automatically by every weekly run. Press Tab to complete.
- **Any human structure, blind or not.** Post-cutoff entries are genuine blind tests; pre-cutoff entries compute too, with a note that AlphaFold may have seen them in training (so it is not a blind prediction).
- **Clear reasons on rejection.** If an entry doesn't qualify you are told exactly why: not a human protein structure, no single UniProt mapping (antibody / fusion / chimera / synthetic), or no AlphaFold model for the sequence.
- **Right or wrong, honestly.** A good prediction renders the green "AlphaFold gets it right" panel (like the positive control); a confidently-wrong one renders the failure panel — the same deterministic builder (`examples_auto.build`) decides which from the metrics.
- **Isolated and cached.** On-demand results are stored under a separate run and status, so they never enter the leaderboard, stats, analysis or archive; the heavy compute runs in an isolated subprocess; and a repeat request for the same structure is instant.

## 🧮 Coverage and skipped entities

Not every deposited entity can be compared. AlphaFold DB holds a single model per human UniProt sequence (monomers only), so anything that does not map cleanly to one accession, has no model covering its resolved range, or is too small or too large to compare is recorded as *skipped* rather than forced through.

The completed full-archive backfill (finished 2026-07-18) processed **96,827** post-cutoff human entities: **82,796 analysed** (85.5%; 67,314 fast-screened plus 15,482 fully compared), **1,941 confidently wrong** (2.3% of analysed, 431 of them sequence-novel), **13,908 skipped** (14.4%), and **123 unrecoverable errors** (0.1%, broken coordinate-less files). The skips break down as:

| Count | Share | Reason | Nature |
|---:|---:|---|---|
| **11,875** | 85% | **No single UniProt mapping** — antibodies, chimeras, engineered constructs, fusion proteins, synthetics | Structural fact: no single AlphaFold model exists to compare against |
| **1,186** | 9% | **No AlphaFold model covering the residue range** — mostly giant multi-domain proteins (titin-scale) whose resolved fragment falls outside AlphaFold DB's fragmented coverage, plus isoforms it lacks | Coverage gap in AlphaFold DB |
| **464** | 3% | **Too few residues aligned (<10)** — tiny peptides or mostly-unresolved chains | Nothing meaningful to compare |
| **381** | 3% | **Structure too large (>40 MB)** — the out-of-memory guard for the 3.8 GB droplet | Resource limit (our cap) |
| **2** | — | Sequence too short (<3 residues) | Degenerate |

The 85% is exactly what the design intends: because AlphaFold DB is monomer-and-single-sequence only, anything that does not map to one human UniProt accession (an antibody Fab, a designed fusion, a chimera) has no counterpart model, so it is flagged and skipped rather than mis-compared.

Skipped entities are terminal by design: `retry-errors` only re-runs `status='error'`, and the resumable weekly and backfill runs skip anything already recorded. Four of the five buckets are permanent structural properties, so re-running would simply re-skip them. The two worth revisiting are the **381 oversized structures** (a memory limit of the small droplet, not a true incomparability, recoverable by raising `MAX_STRUCT_BYTES` or upsizing the box) and the multi-domain subset of the **1,186 missing-model** bucket (recoverable with better fragment selection for AlphaFold models above 2,700 residues).

## 🛠️ Web deployment

**Live at [alphafraud.mdeller.com](https://alphafraud.mdeller.com).** The report is served by a Flask app (gunicorn behind nginx with a Let's Encrypt certificate) and the weekly pipeline runs from a systemd timer on the same droplet.

```bash
# 1. From your Mac: copy .env.example to .env and fill in DROPLET_SSH / DROPLET_PATH / SERVER_NAME
cp .env.example .env

# 2. Push the code to the droplet
bash deploy/deploy.sh

# 3. On the droplet as root: one-time provisioning (packages, user, venv, services, nginx, TLS)
sudo SERVER_NAME=alphafraud.mdeller.com bash /opt/alphafraud/deploy/provision.sh

# 4. (optional) trigger the first pipeline run immediately
sudo systemctl start alphafraud-run.service
```

After that, `deploy/deploy.sh` pushes code updates and restarts the web service, and `deploy/release.sh "message"` does the whole loop in one step (commit, push to GitHub, then deploy). Deploys are safe to run while a backfill is in progress: the web app is a read-only reader, WAL is set once, and DB writes are retry-wrapped, so restarting the web service never disturbs the running pipeline. The weekly timer fires every Wednesday 00:30 UTC.

| File | Role |
|---|---|
| `deploy/provision.sh` | One-time root setup: system packages, service user, venv, systemd units, nginx site, certbot. Also patches HTTP/2 onto certbot's TLS listener afterward (nginx doesn't enable it by default) — idempotent, so it self-heals on a re-run |
| `deploy/deploy.sh` | Push code from your Mac (rsync over SSH) and restart the web service |
| `deploy/release.sh` | One-shot: commit, push to GitHub, then deploy to the droplet |
| `deploy/alphafraud-web.service` | gunicorn web app (always on) |
| `deploy/alphafraud-run.service` + `.timer` | Weekly pipeline and its Wednesday 00:30 UTC schedule |
| `deploy/alphafraud-backfill.service` | Supervised one-time full-archive backfill; auto-restarts on crash, survives reboot (`systemctl enable --now alphafraud-backfill`) |
| `deploy/nginx-alphafraud.conf` | nginx reverse-proxy site (templated with the server name) |

## 🧱 Stack

Python, biotite and tmtools for structure handling and superposition, numpy and scipy for the metrics, Flask and gunicorn for serving, Plotly for the figures, and SQLite for state. No compiled toolchain, no external database.

## 🧭 Caveats

- "Deposited after the cutoff" plus a novelty score is a strong proxy, not proof AlphaFold never saw a homolog: the novelty column makes this explicit so you can filter to the defensible subset.
- AlphaFold DB models are monomers, so complex and interface accuracy are not tested in this version.
- Engineered constructs, antibodies and fusion proteins that do not map to a single UniProt accession are flagged and skipped, not compared.

## ✅ To Do

Roadmap for AlphaFraud, newest ideas at the top. Suggestions welcome.

- [x] **Published as a citable software release.** Zenodo, MIT, concept DOI [10.5281/zenodo.21808182](https://doi.org/10.5281/zenodo.21808182), which always resolves to the latest version. Source only: `data/` is 5.2 GB of API-cached structures and generated ribbons, all regenerable, and the results database is not deposited. The description's figures were read from the live database rather than from this README, which had drifted by a week's worth of runs
- [x] **Home page and `/api/stats` no longer scan the whole `entities` table.** `overall_stats()` filtered on `status`, which nothing indexed, so the planner had only `SCAN entities`: ~97k rows over 63 MB of pages, dragging in 23 of the table's 28 columns that the aggregate never reads. That was 62 ms on every page load and made AlphaFraud the slowest app on the droplet by an order of magnitude (68 ms against 1-2 ms for its neighbours). A covering index on `(status, confidently_wrong, is_novel, tm_by_experiment, lddt)` lets SQLite answer the whole query from a 2.8 MB index without touching the table, taking it to 4.9 ms, and the result is now cached in `analysis_snapshots` alongside the analysis payload, refreshed by the weekly run. Warm requests are ~6 ms; the launcher's health check went from 193 ms to 52 ms.

- [x] **Statistics page** — an exhaustive live `/stats` page grouping everything the app tracks into themed, equal-height panels (consistent with the rest of the site): catch & quality KPIs, coverage & schedule (date ranges, release weeks, last/next update), runs & compute, server metrics (CPU, load, memory, uptime), storage & database (file sizes, per-table row counts, disk), data sources & APIs (linked), and traffic — with a "Full statistics →" link from the header panel
- [x] **Home landing page** — a concise navigation page at `/` outlining the project and each tab as a colour-coded card with a "what you'll learn" line and headline KPIs; the cumulative dashboard moved to `/all` ("All structures"). Nav tabs now carry their panel accent colour to tie the site together
- [x] **Calculate tab** — type any human PDB ID and AlphaFraud runs the full pipeline on demand (resolve the entity, fetch its AlphaFold model, superpose, score, render the ribbon) and returns the same panel as the auto examples, with **no LLM**. A strict autocomplete index (exists + human + has an AlphaFold model), seeded from the corpus and auto-refreshed each week, guarantees only qualifying entries; rejections are explained (not human / antibody-fusion / no AlphaFold model); good predictions render the green "gets it right" panel and confidently-wrong ones the failure panel; the heavy compute runs in an isolated subprocess and on-demand results stay out of every aggregate
- [x] **Examples tab** — a curated storytelling layer that shows both sides of AlphaFold's record. It opens with a **positive control** (human Artemis, a novel post-cutoff nuclease predicted blind to 0.45 Å Cα-RMSD and scored FRAUD 0.02) proving the pipeline certifies good predictions as well as bad; an auto-generated, LLM-free **"example of the week"** plus a **complete weekly-release archive** (catches and quiet weeks alike); hand-authored deep-dive panels across the failure spectrum, each with live metrics and an interactive 3D viewer; and clickable red/green example markers overlaid on the home fraud-quadrant scatter
- [x] **Page and figure caching** — the cumulative dashboard's heavy whole-archive figures (scatter / dumbbell / histograms over ~80k rows) are precomputed once and cached in an `analysis_snapshots` row with a short TTL, and every static asset (vendored Plotly / 3Dmol, ribbons, CSS/JS) is served with long immutable cache headers, so repeat loads are near-instant
- [x] **Weekly-release archive at full granularity** — the Archive tab now lists every PDB release week since the 2018 cutoff (derived from each structure's release date), each linking to that week's structures and confidently-wrong count, instead of only the recent ongoing-watch runs
- [x] **Fix slow page loads after the full backfill** — once the archive backfill filled the `entities` table with ~470 KB `heatmaps_json` per compared row (≈ 6.5 GB), every list/sort query (home, leaderboard, week pages) dragged all that JSON through memory and took 20–60 s (the leaderboard 504'd at the 60 s gunicorn timeout). Fixed by moving the big per-residue and heatmap payloads into an `entity_blobs` sidecar table read only by the per-structure entry page, so the hot table stays small and list queries return in well under a second
- [x] **Structural imagery throughout** — every worst offender is rendered as a deviation-coloured Cα ribbon (experiment coloured by distance from the AlphaFold model, on an absolute-Ångström scale), shown on the leaderboard, entry page and weekly highlights; the entry page adds an interactive 3Dmol.js viewer with a proper secondary-structure cartoon and an optional translucent AlphaFold "ghost" overlay in the shared superposition frame; a "divergence" ribbon banner sits in the header. All server-rendered as vendored, offline SVG/PDB (no CDN)
- [x] **Percentages on the KPI tiles** — each headline count also shows its share of the batch (e.g. confidently wrong: 1,941 = 2.3%), on the dashboard, week and leaderboard views
- [x] **Worst-offenders structural deep dive** — the **Analysis** tab characterises the confidently-wrong set by CATH / SCOP2 fold and family class (Wilson-CI + Fisher-exact enrichment), clusters it by sequence similarity, flags shared themes (amyloid / assembly / disordered / coiled-coil / engineered), maps failure modes by PCA, detects conformational heterogeneity, gives per-superfamily blind-spot scorecards, and links every offender to its RCSB entry and DOI-verified manuscript; refreshed hourly and after each weekly run
- [x] **Hover-to-preview structures** — hovering a point on the "fraud quadrant" scatter pops a floating deviation-coloured ribbon thumbnail of that structure; the entry page carries the full interactive 3D viewer
- [x] **Header "Stats" panel** — a live panel in the top-right of the header tracking app health: worker memory, SQLite DB size, unique visitors, structures analysed, confidently-wrong count and archive %; refreshes every minute from `/api/stats`
- [x] **Supervised backfill service** — the archive backfill runs as a systemd unit (`alphafraud-backfill.service`) that auto-restarts on crash and survives reboots, replacing the detached `nohup` process
- [ ] **Family-spectrum analysis tab** — a new tab presenting worst-offending proteins across the accuracy spectrum with a clear worked example per tier: confidently wrong (high pLDDT, low TM), intermediate / conformational disagreement, and well-predicted; plus a distinct "honest failure" category (low TM but AlphaFold flagged its own low confidence). Deduplicated by UniProt, since AlphaFold DB holds one blind model per sequence, so repeat depositions of a protein share an identical prediction (already reflected in the confidently-wrong dumbbell's per-protein collapse and the leaderboard `×N` column, and documented in [FAMILY_SPECTRUM.md](FAMILY_SPECTRUM.md)). Seed examples: leukocyte cell-derived chemotaxin-2 (`O14960`, ×7, median TM 0.17 at pLDDT 97), TMEM106B (`Q9NUM4`, ×22, 0.18), coagulation factor X (`P00742`, ×29, 0.21) at the bad end; calmodulin (`P0DP23`, ×163, 0.51) and DNA ligase 4 (`P49917`, 0.50) mid; carbonic anhydrase 12 (`O43570`), ACE (`P12821`), aldo-keto reductase 1B1 (`P15121`) at ~1.0
- [ ] **Multi-chain / complex accuracy** — compare assemblies with QS-score and interface lDDT (AlphaFold DB models are monomer-only today, so interfaces are untested)
- [ ] **Accuracy by method and resolution** — break results down by X-ray / cryo-EM / NMR and by resolution to see where AlphaFold struggles most
- [ ] **Map multi-domain and engineered chains** — compare antibodies, fusions and constructs per-domain instead of skipping chains without a single UniProt accession
- [ ] **Process-based parallel backfill** — a `ProcessPoolExecutor` path to beat the single-thread ceiling without the C-extension thread-safety issues that forced single-threaded mode
- [ ] **Predictor and model-version tracking** — record the AlphaFold DB model version, flag entries updated since the first prediction, and add other predictors (AlphaFold3, ESMFold) for comparison
- [ ] **Catch alerts** — optional email / Slack notification when a new confidently-wrong or novel-and-wrong structure is found
- [ ] **Robust large-assembly parsing** — handle the CIF-only and oversized structures that currently log a parse error and are skipped
- [ ] **Tests and CI** — a regression set pinned on known catches (transthyretin, SOD1, β2-microglobulin) plus continuous integration

## 📦 Citation

AlphaFraud is deposited on Zenodo as a citable software release under the MIT Licence: the
pipeline, the metric suite, the ribbon renderer and the Flask application as released. The
cached structures and generated imagery are not included — they are regenerable from the
public APIs — and neither is the results database.

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21808182-1C244B?logo=doi&logoColor=white)](https://doi.org/10.5281/zenodo.21808182)

| | |
|---|---|
| Concept DOI (always latest) | [10.5281/zenodo.21808182](https://doi.org/10.5281/zenodo.21808182) |
| This version (v0.1.0) | [10.5281/zenodo.21808183](https://doi.org/10.5281/zenodo.21808183) |

Every figure in the deposit's description was **read from the live instance's database**
on 2026-08-05 rather than copied from this README, which was carrying counts from an
earlier week (96,827 entities and 82,796 analysed, against an actual 96,928 and 82,895).
On a sibling project six figures reached a Zenodo description by being copied from prose,
and a DOI would have made them permanent.

**Cite as:** Deller, M. C. (2026). *AlphaFraud: a weekly, automated audit of AlphaFold
accuracy on freshly deposited human structures*. Version 0.1.0. Zenodo.
https://doi.org/10.5281/zenodo.21808182

## 📝 Licence

Released under the MIT Licence (see [LICENSE](LICENSE)).

Attributing AlphaFraud does not discharge the obligation to the sources it derives from:
the [Protein Data Bank](https://www.rcsb.org) (CC0) and the
[AlphaFold Protein Structure Database](https://alphafold.ebi.ac.uk) (CC BY 4.0).

---

## 👤 Author

**Marc C. Deller, D.Phil.**  
Structural biologist & drug discovery scientist  

<table>
<tr>
<td>🌐</td><td><a href="https://marcdeller.com" target="_blank" rel="noopener noreferrer">marcdeller.com</a></td>
<td>✉️</td><td><a href="mailto:marc@marcdeller.com">marc@marcdeller.com</a></td>
<td>🐙</td><td><a href="https://github.com/bellcheddar/AlphaFraud" target="_blank" rel="noopener noreferrer">github.com/bellcheddar/AlphaFraud</a></td>
</tr>
</table>
