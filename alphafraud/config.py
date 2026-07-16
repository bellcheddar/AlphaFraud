"""Central configuration for AlphaFraud.

All paths are anchored to the repository root (the parent of this package) so the code
runs identically from a laptop checkout and from /opt/alphafraud on the droplet. Secrets
and the deploy target come from a gitignored .env (see .env.example); everything else has
a sensible default here.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is optional at import time (e.g. bare python3 running `init`)
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent
DATA_DIR = ROOT_DIR / "data"                 # cached PDB + AFDB structure/PAE files
STRUCT_CACHE = DATA_DIR / "structures"
RIBBON_DIR = DATA_DIR / "ribbons"            # per-entity deviation-coloured Cα ribbon SVGs
DB_PATH = ROOT_DIR / "alphafraud.db"
STATIC_DIR = PACKAGE_DIR / "static"
VENDOR_PLOTLY = STATIC_DIR / "plotly.min.js"

load_dotenv(ROOT_DIR / ".env")

# --------------------------------------------------------------------------------------
# Scientific constants
# --------------------------------------------------------------------------------------
# AlphaFold2 was trained on PDB chains RELEASED before this date (DeepMind technical note).
# Structures DEPOSITED after it are the population AlphaFold predicted blind -> our target.
AF_TRAINING_CUTOFF = date(2018, 4, 30)

# Homo sapiens.
HUMAN_TAXONOMY_ID = 9606

# A sequence whose best match to any pre-cutoff PDB chain is below this %identity is
# treated as "novel" -- something AlphaFold had no close homolog for at training time.
NOVELTY_IDENTITY_THRESHOLD = float(os.environ.get("NOVELTY_IDENTITY_THRESHOLD", "30"))

# "Confidently wrong": AlphaFold was confident (mean pLDDT above this) yet the fold is
# wrong (TM-score below the other threshold). These two define the FRAUD headline.
CONFIDENT_PLDDT = 70.0
WRONG_TM = 0.50

# lDDT inclusion radius and the four distance-difference tolerances (CASP standard).
LDDT_INCLUSION_RADIUS = 15.0
LDDT_THRESHOLDS = (0.5, 1.0, 2.0, 4.0)

# --------------------------------------------------------------------------------------
# External API endpoints
# --------------------------------------------------------------------------------------
RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_GRAPHQL_URL = "https://data.rcsb.org/graphql"
AFDB_PREDICTION_URL = "https://alphafold.ebi.ac.uk/api/prediction/{accession}"
HTTP_TIMEOUT = 60          # seconds per request
HTTP_MAX_RETRIES = 5

# --------------------------------------------------------------------------------------
# Deploy / serving (from .env)
# --------------------------------------------------------------------------------------
DROPLET_SSH = os.environ.get("DROPLET_SSH", "")
DROPLET_PATH = os.environ.get("DROPLET_PATH", "/opt/alphafraud")
SERVER_NAME = os.environ.get("SERVER_NAME", "alphafraud.mdeller.com")
BIND_ADDR = os.environ.get("BIND_ADDR", "127.0.0.1:8000")

# Optional cap on entities processed per run (blank/0 = no cap). Handy for smoke tests.
_run_limit = os.environ.get("RUN_LIMIT", "").strip()
RUN_LIMIT = int(_run_limit) if _run_limit.isdigit() and int(_run_limit) > 0 else None


def ensure_dirs() -> None:
    """Create the runtime directory tree if missing. Safe to call repeatedly."""
    for d in (DATA_DIR, STRUCT_CACHE, RIBBON_DIR, STATIC_DIR):
        d.mkdir(parents=True, exist_ok=True)
