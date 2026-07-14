# 🧬 AlphaFraud

> **Catch AlphaFold where the fold is wrong: weekly, automatically, on freshly deposited human structures.**

![python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white) ![flask](https://img.shields.io/badge/web-Flask%20%2B%20gunicorn-000000?logo=flask&logoColor=white) ![data](https://img.shields.io/badge/data-RCSB%20PDB%20%2B%20AlphaFold%20DB-1e73be) ![status](https://img.shields.io/badge/status-in%20development-fcb900) ![author](https://img.shields.io/badge/author-Marc%20C.%20Deller%2C%20D.Phil.-1C244B)

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

## ✨ Features

| Capability | What it does |
|---|---|
| Automated PDB watch | Weekly systemd timer fires after the PDB's Wednesday 00:00 UTC release; resumes from the last processed run |
| Human, post-cutoff filter | RCSB Search for taxonomy 9606 protein entities deposited after AlphaFold's 2018-04-30 training cutoff |
| Blind-model matching | Maps each entity to its UniProt accession and AlphaFold DB model, handling fragments, mutants and missing loops via sequence alignment |
| Sequence-novelty score | Max percent identity to any pre-cutoff PDB chain, so genuinely unseen sequences are flagged (not just easy homologs) |
| Full metric suite | Global, local, backbone, per-domain and confidence-calibration metrics (see below) |
| Confidence audit | pLDDT vs actual lDDT calibration, and a PAE-honesty check comparing AlphaFold's self-reported error to the observed error |
| Branded web report | Flask app with the signature "fraud quadrant" scatter, heatmaps, per-domain tables and an all-time leaderboard |
| One-command deploy | Provisioning and deploy scripts for a DigitalOcean droplet (gunicorn, nginx, certbot TLS) |

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

# Backfill a historical range
python3 AlphaFraud.py backfill --from 2023-01-01 --to 2023-12-31

# Database summary + worst-offenders leaderboard
python3 AlphaFraud.py status

# Local dev web server (production uses gunicorn)
python3 AlphaFraud.py serve --port 8000
```

| Command | Purpose |
|---|---|
| `init` | Create directories, the SQLite schema, and vendor `plotly.min.js` |
| `run` | Discover, match, score and store one deposit window (`--since`, `--until`, `--limit`, `--dry-run`) |
| `backfill` | Process a historical window (`--from`, `--to`) |
| `status` | Print a database summary and the current leaderboard |
| `serve` | Run the Flask app locally (`--port`, `--debug`) |

## 📊 Output

The web app serves live from SQLite:

| Route | Shows |
|---|---|
| `/` | The latest release week: KPIs, the pLDDT-vs-TM fraud-quadrant scatter, metric histograms, and a sortable table of every matched structure |
| `/entry/<id>` | Per-structure detail: per-residue error tracks, calibration scatter, distance-matrix and PAE-vs-observed heatmaps, per-domain breakdown, and every metric |
| `/leaderboard` | The all-time worst AlphaFold failures across every processed week |
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

After that, `deploy/deploy.sh` alone pushes updates and restarts the web service. The weekly timer fires every Wednesday 00:30 UTC.

| File | Role |
|---|---|
| `deploy/provision.sh` | One-time root setup: system packages, service user, venv, systemd units, nginx site, certbot |
| `deploy/deploy.sh` | Push code from your Mac (rsync over SSH) and restart the web service |
| `deploy/alphafraud-web.service` | gunicorn web app (always on) |
| `deploy/alphafraud-run.service` + `.timer` | Weekly pipeline and its Wednesday 00:30 UTC schedule |
| `deploy/nginx-alphafraud.conf` | nginx reverse-proxy site (templated with the server name) |

## 🧱 Stack

Python, biotite and tmtools for structure handling and superposition, numpy and scipy for the metrics, Flask and gunicorn for serving, Plotly for the figures, and SQLite for state. No compiled toolchain, no external database.

## 🧭 Caveats

- "Deposited after the cutoff" plus a novelty score is a strong proxy, not proof AlphaFold never saw a homolog: the novelty column makes this explicit so you can filter to the defensible subset.
- AlphaFold DB models are monomers, so complex and interface accuracy are not tested in this version.
- Engineered constructs, antibodies and fusion proteins that do not map to a single UniProt accession are flagged and skipped, not compared.

## 📝 Licence

Add your licence here.

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
