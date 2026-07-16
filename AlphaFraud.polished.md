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

**A live instance runs at [alphafraud.mdeller.com](https://alphafraud.mdeller.com)**, backfilling the entire post-cutoff archive (~96,000 human protein entities) and updating every week. The landing page is a cumulative dashboard across every processed week; the worst offenders so far are a roster of amyloid-forming proteins (transthyretin, β2-microglobulin, islet amyloid polypeptide) that AlphaFold predicts as confidently folded but which crystallise or cryo-EM in a completely different aggregated form.

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
| `/archive` | An index of all processed weeks |
| `/api/week/<label>`, `/api/leaderboard`, `/api/entry/<id>` | JSON for external tools |

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

- [x] **Percentages on the KPI tiles** — each headline count also shows its share of the batch (e.g. confidently wrong: 586 = 1.6%), on the dashboard, week and leaderboard views
- [x] **Worst-offenders structural deep dive** — the **Analysis** tab characterises the confidently-wrong set by CATH / SCOP2 fold and family class (Wilson-CI + Fisher-exact enrichment), clusters it by sequence similarity, flags shared themes (amyloid / assembly / disordered / coiled-coil / engineered), maps failure modes by PCA, detects conformational heterogeneity, gives per-superfamily blind-spot scorecards, and links every offender to its RCSB entry and DOI-verified manuscript; refreshed hourly and after each weekly run
- [ ] **Hover-to-preview structures** — a live 3D preview (experimental vs AlphaFold) on hover over a scatter point or a table row
- [ ] **Header "Stats" panel** — a small live panel in the top-right of the header tracking app health: memory usage, SQLite DB size, unique visitors, and other key stats
- [x] **Supervised backfill service** — the archive backfill runs as a systemd unit (`alphafraud-backfill.service`) that auto-restarts on crash and survives reboots, replacing the detached `nohup` process
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
