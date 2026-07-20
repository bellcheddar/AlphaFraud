# 🧬 AlphaFraud

> **Catch AlphaFold where the fold is wrong: weekly, automatically, on freshly deposited human structures.**

[![live](https://img.shields.io/badge/live-alphafraud.mdeller.com-00d084)](https://alphafraud.mdeller.com) ![python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white) ![flask](https://img.shields.io/badge/web-Flask%20%2B%20gunicorn-000000?logo=flask&logoColor=white) ![data](https://img.shields.io/badge/data-RCSB%20PDB%20%2B%20AlphaFold%20DB-1e73be) ![status](https://img.shields.io/badge/status-in%20development-fcb900) ![author](https://img.shields.io/badge/author-Marc%20C.%20Deller%2C%20D.Phil.-1C244B)

<table>
<tr>
<td>🌐 <b>Website</b></td><td><a href="https://marcdeller.com" target="_blank" rel="noopener noreferrer">marcdeller.com</a></td>
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
| Cumulative dashboard | Default landing page aggregating every processed week: the "fraud quadrant" scatter, metric histograms, a weekly trend, and a browsable per-week / per-structure archive |
| Branded, mobile-responsive report | Flask app with the signature scatter, heatmaps, per-domain tables and an all-time leaderboard; every plot has a CSV export and a plain-language explanatory panel that defines each metric twice over (a lay sentence and the underlying equation), and every table exports to CSV |
| One-command deploy | Provisioning, deploy and one-shot release scripts for a DigitalOcean droplet (gunicorn, nginx, certbot TLS) |

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

| Route | Shows |
|---|---|
| `/` | Cumulative dashboard across every processed week: KPIs, the pLDDT-vs-TM fraud-quadrant scatter, metric histograms, the weekly trend, and a top-ranked table. A pulldown jumps to any single week |
| `/week/<label>` | One release week, same layout scoped to that batch |
| `/entry/<id>` | Per-structure detail: per-residue error tracks, calibration scatter, distance-matrix and PAE-vs-observed heatmaps, per-domain breakdown, and every metric |
| `/leaderboard` | The all-time worst AlphaFold failures across every processed week |
| `/analysis` | Structural deep dive over the worst offenders: fold/family enrichment (Wilson-CI + Fisher), sequence-similarity clustering, failure-mode PCA, theme flags, per-superfamily blind-spot scorecards, conformational-heterogeneity detection, a "new this week" ribbon, and RCSB + DOI links on every structure |
| `/examples` | Curated storytelling layer: a positive control (an excellent AlphaFold match), an auto-generated "example of the week" plus a full weekly-release archive, and hand-authored deep-dive panels with interactive viewers (see below) |
| `/archive` | Every PDB release week since the 2018 cutoff, at weekly granularity, each linking to that week's structures and confidently-wrong count |
| `/api/week/<label>`, `/api/leaderboard`, `/api/entry/<id>` | JSON for external tools |

## 🔬 Examples

The **Examples** tab turns raw catches into readable stories and deliberately shows both sides of AlphaFold's record, not just the failures:

- **A positive control.** The page opens with the one thing the rest of the site does not: an *excellent* match. Human Artemis (DCLRE1C), a genuinely novel post-cutoff nuclease (only 29% identity to anything AlphaFold trained on), was predicted blind to TM-score 0.996, lDDT 0.985 and 0.45 Å Cα-RMSD at a justified mean pLDDT of 95, and AlphaFraud scores it FRAUD 0.02. It is the proof that the pipeline certifies good predictions, not just hunts for bad ones.
- **An auto "example of the week".** After every weekly run the pipeline picks that release's most instructive confidently-wrong catch and writes its panel deterministically from the database (no LLM), badged and dated.
- **A complete weekly archive.** Every PDB release week since the 2018 cutoff is listed: weeks with a catch expand to a full panel with its Cα-deviation ribbon, and the quiet weeks (where AlphaFold was never overconfident) are recorded too, collapsed to the most recent by default.
- **Curated deep-dives.** Hand-authored panels across the failure spectrum: ordinary single-chain globular folds AlphaFold gets *subtly* wrong (right fold, wrong conformation or assembly — the PP2A scaffold, STIM1, Aha1, WWP2) and the dramatic whole-fold catastrophes (TMEM106B, alpha-synuclein, transthyretin, factor X). Each panel carries live metrics, an interactive 3Dmol.js viewer (deviation colouring plus the AlphaFold "ghost") and a structure / mechanism / disease write-up.
- **Linked from the scatter.** The curated examples are overlaid on the home fraud-quadrant plot as pulsing red (failure) and green (accurate) markers, each labelled with its protein name and clickable straight through to its panel.

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

## 🛠️ Deployment

The report is served by a Flask app (gunicorn behind nginx with a Let's Encrypt certificate) and the weekly pipeline runs from a systemd timer on the same droplet.

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
| `deploy/provision.sh` | One-time root setup: system packages, service user, venv, systemd units, nginx site, certbot |
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

## 📝 Licence

Released under the MIT Licence (see [LICENSE](LICENSE)).

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
