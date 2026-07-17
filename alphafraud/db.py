"""SQLite persistence -- shared by the pipeline (writer) and the Flask app (reader).

One row per processed polymer entity. The full metric dict, per-residue arrays, domain
list and heatmap data are stored as JSON; the handful of columns used for sorting,
filtering and the leaderboard are promoted to real columns. Runs group entities into the
weekly batch that produced them (`label` = the release Wednesday the run covers).
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT NOT NULL,          -- release date this run covers (YYYY-MM-DD)
    since        TEXT,
    until        TEXT,
    started_at   TEXT,
    finished_at  TEXT,
    n_discovered INTEGER DEFAULT 0,
    n_compared   INTEGER DEFAULT 0,
    n_skipped    INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id          TEXT PRIMARY KEY,   -- e.g. 7XYZ_1
    entry_id           TEXT,
    chain              TEXT,
    uniprot            TEXT,
    uniprot_name       TEXT,
    description        TEXT,
    deposit_date       TEXT,
    release_date       TEXT,
    resolution         REAL,
    method             TEXT,
    -- novelty
    novelty_identity   REAL,               -- % identity to closest pre-cutoff chain
    is_novel           INTEGER,
    closest_pre_cutoff TEXT,
    -- alphafold
    af_entry_id        TEXT,
    af_model_version   INTEGER,
    mean_plddt         REAL,
    -- promoted headline metrics (for sort/leaderboard)
    tm_by_experiment   REAL,
    lddt               REAL,
    gdt_ts             REAL,
    ca_rmsd            REAL,
    fraud_score        REAL,
    confidently_wrong  INTEGER,
    -- full payloads
    metrics_json       TEXT,
    per_residue_json   TEXT,
    domains_json       TEXT,
    heatmaps_json      TEXT,
    -- provenance
    status             TEXT,               -- compared | skipped | error
    skip_reason        TEXT,
    run_id             INTEGER,
    processed_at       TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_entities_run     ON entities(run_id);
CREATE INDEX IF NOT EXISTS idx_entities_fraud   ON entities(fraud_score);
CREATE INDEX IF NOT EXISTS idx_entities_deposit ON entities(deposit_date);

-- Enrichment metadata for the Analysis tab (fetched lazily over the compared subset).
CREATE TABLE IF NOT EXISTS entity_annotations (
    entity_id        TEXT PRIMARY KEY,
    sequence         TEXT,
    seq_length       INTEGER,
    cath_code        TEXT,
    cath_class       TEXT,
    cath_arch        TEXT,
    cath_topo        TEXT,
    cath_name        TEXT,
    scop2_sf         TEXT,
    ecod_family      TEXT,
    pfam_json        TEXT,
    go_json          TEXT,
    citation_doi     TEXT,
    citation_title   TEXT,
    citation_journal TEXT,
    citation_year    INTEGER,
    citation_pubmed  INTEGER,
    n_chains         INTEGER,
    assembly_count   INTEGER,
    is_amyloid       INTEGER,
    is_idr           INTEGER,
    is_assembly      INTEGER,
    is_coiledcoil    INTEGER,
    is_engineered    INTEGER,
    enriched_at      TEXT,
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
);

-- Cached, precomputed analysis payload (one 'cumulative' row rebuilt after each run).
CREATE TABLE IF NOT EXISTS analysis_snapshots (
    kind        TEXT PRIMARY KEY,
    data_json   TEXT,
    updated_at  TEXT
);

-- Lightweight visitor counter for the header stats panel (IPs are hashed, never stored raw).
CREATE TABLE IF NOT EXISTS visits (
    ip_hash     TEXT PRIMARY KEY,
    first_seen  TEXT,
    last_seen   TEXT,
    hits        INTEGER DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL is a PERSISTENT property of the database file -- set once in init_schema(), never
    # here. Running `PRAGMA journal_mode=WAL` on every connection needs a brief write lock,
    # and when a deploy restarts the web service (which also opens the DB) that collided
    # with the backfill's writes and surfaced as "attempt to write a readonly database".
    # busy_timeout is per-connection and harmless -- wait for a writer rather than erroring.
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema() -> None:
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")   # persisted in the DB header; set once
        conn.executescript(SCHEMA)


def _retry_write(action, attempts: int = 6, base_delay: float = 0.4):
    """Retry a DB write through a transient OperationalError (a locked/readonly window, e.g.
    a concurrent web-service restart) instead of letting a multi-day backfill crash."""
    import time
    for i in range(attempts):
        try:
            return action()
        except sqlite3.OperationalError:
            if i == attempts - 1:
                raise
            time.sleep(base_delay * (i + 1))


# --------------------------------------------------------------------------------------
# Runs
# --------------------------------------------------------------------------------------
def start_run(label: str, since: str, until: str) -> int:
    def _do():
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO runs(label, since, until, started_at, status) VALUES (?,?,?,?, 'running')",
                (label, since, until, _now()),
            )
            return int(cur.lastrowid)
    return _retry_write(_do)


def finish_run(run_id: int, n_discovered: int, n_compared: int, n_skipped: int) -> None:
    def _do():
        with connect() as conn:
            conn.execute(
                "UPDATE runs SET finished_at=?, n_discovered=?, n_compared=?, n_skipped=?, status='done' WHERE id=?",
                (_now(), n_discovered, n_compared, n_skipped, run_id),
            )
    _retry_write(_do)


def entity_exists(entity_id: str) -> bool:
    with connect() as conn:
        return conn.execute("SELECT 1 FROM entities WHERE entity_id=?", (entity_id,)).fetchone() is not None


# Error rows whose skip_reason is one of these are not real failures: the pipeline
# *correctly* refused to compare (too few residues aligned to the AF model, or a peptide
# too short to superpose). They belong under 'skipped' (not-comparable), like constructs.
_NONCOMPARABLE_ERROR_PATTERNS = ("refusing to compare", "too short")


def _noncomparable_where(col: str = "skip_reason") -> str:
    return " OR ".join(f"{col} LIKE '%{p}%'" for p in _NONCOMPARABLE_ERROR_PATTERNS)


def reclassify_noncomparable_errors() -> int:
    """Move guard-rejection error rows to 'skipped' (they are not real failures). Returns the
    number of rows reclassified. Idempotent."""
    def _do():
        with connect() as conn:
            cur = conn.execute(
                f"UPDATE entities SET status='skipped' "
                f"WHERE status='error' AND ({_noncomparable_where()})"
            )
            return cur.rowcount
    return _retry_write(_do)


def error_entity_ids(exclude_noncomparable: bool = True) -> list[str]:
    """Entity ids currently in 'error' status. By default excludes the guard rejections
    (which a retry cannot fix); the remainder are the retryable I/O/format/model failures."""
    sql = "SELECT entity_id FROM entities WHERE status='error'"
    if exclude_noncomparable:
        sql += f" AND NOT ({_noncomparable_where()})"
    sql += " ORDER BY entity_id"
    with connect() as conn:
        return [r["entity_id"] for r in conn.execute(sql).fetchall()]


# --------------------------------------------------------------------------------------
# Entities
# --------------------------------------------------------------------------------------
def upsert_entity(rec: dict) -> None:
    """Insert or replace one entity row. `rec` carries scalar columns plus the four JSON
    blobs already serialized to dicts/lists (this function serializes them)."""
    m = rec.get("metrics") or {}
    row = {
        "entity_id": rec["entity_id"],
        "entry_id": rec.get("entry_id"),
        "chain": rec.get("chain"),
        "uniprot": rec.get("uniprot"),
        "uniprot_name": rec.get("uniprot_name"),
        "description": rec.get("description"),
        "deposit_date": rec.get("deposit_date"),
        "release_date": rec.get("release_date"),
        "resolution": rec.get("resolution"),
        "method": rec.get("method"),
        "novelty_identity": rec.get("novelty_identity"),
        "is_novel": _as_int(rec.get("is_novel")),
        "closest_pre_cutoff": rec.get("closest_pre_cutoff"),
        "af_entry_id": rec.get("af_entry_id"),
        "af_model_version": rec.get("af_model_version"),
        "mean_plddt": m.get("mean_plddt"),
        "tm_by_experiment": m.get("tm_by_experiment"),
        "lddt": m.get("lddt"),
        "gdt_ts": m.get("gdt_ts"),
        "ca_rmsd": m.get("ca_rmsd"),
        "fraud_score": m.get("fraud_score"),
        "confidently_wrong": _as_int(m.get("confidently_wrong")),
        "metrics_json": json.dumps(m),
        "per_residue_json": json.dumps(rec.get("per_residue") or {}),
        "domains_json": json.dumps(rec.get("domains") or []),
        "heatmaps_json": json.dumps(rec.get("heatmaps") or {}),
        "status": rec.get("status", "compared"),
        "skip_reason": rec.get("skip_reason"),
        "run_id": rec.get("run_id"),
        "processed_at": _now(),
    }
    cols = ", ".join(row)
    placeholders = ", ".join(f":{c}" for c in row)

    def _do():
        with connect() as conn:
            conn.execute(f"INSERT OR REPLACE INTO entities ({cols}) VALUES ({placeholders})", row)
    _retry_write(_do)


def _as_int(v) -> Optional[int]:
    if v is None:
        return None
    return int(bool(v))


# --------------------------------------------------------------------------------------
# Queries (used by the web app)
# --------------------------------------------------------------------------------------
def latest_run_label() -> Optional[str]:
    with connect() as conn:
        row = conn.execute(
            "SELECT label FROM runs WHERE status='done' ORDER BY finished_at DESC LIMIT 1"
        ).fetchone()
        return row["label"] if row else None


def list_weeks() -> list[dict]:
    # Aggregate by label so a chunk that was interrupted and resumed (two run rows for the
    # same month) shows once, with summed counts.
    with connect() as conn:
        rows = conn.execute(
            """SELECT label,
                      SUM(n_discovered) n_discovered,
                      SUM(n_compared)   n_compared,
                      SUM(n_skipped)    n_skipped,
                      MAX(finished_at)  finished_at
               FROM runs WHERE status='done' GROUP BY label ORDER BY label DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


# Both tiers count as "analysed": 'screened' (TM-only) and 'compared' (full metrics).
ANALYSED = "status IN ('screened','compared')"


def entities_for_week(label: str) -> list[dict]:
    q = (f"SELECT * FROM entities WHERE run_id IN (SELECT id FROM runs WHERE label=?) "
         f"AND {ANALYSED} ORDER BY fraud_score DESC")
    with connect() as conn:
        return [dict(r) for r in conn.execute(q, (label,)).fetchall()]


# Scalar columns only (no JSON blobs) -- cheap to pull for every analysed entity, which
# the cumulative "All" view needs for its scatter, histograms, KPIs and top-N table.
_SCALAR_COLS = (
    "entity_id, entry_id, chain, uniprot, description, deposit_date, resolution, method, "
    "novelty_identity, is_novel, mean_plddt, tm_by_experiment, lddt, gdt_ts, ca_rmsd, "
    "fraud_score, confidently_wrong, status"
)


def all_entities_scalar() -> list[dict]:
    """Every analysed entity (both tiers), scalar columns only, worst-FRAUD first."""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT {_SCALAR_COLS} FROM entities WHERE {ANALYSED} ORDER BY fraud_score DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def uniprots_before_label(label: str) -> set:
    """UniProt accessions seen in weeks released before `label` (for the 'first seen' flag).
    Week labels are ISO dates, so a string comparison orders them correctly."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT e.uniprot FROM entities e JOIN runs r ON e.run_id = r.id "
            "WHERE r.label < ? AND e.uniprot IS NOT NULL",
            (label,),
        ).fetchall()
        return {r["uniprot"] for r in rows}


def get_entity(entity_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM entities WHERE entity_id=?", (entity_id,)).fetchone()
        return dict(row) if row else None


def leaderboard(limit: int = 100, novel_only: bool = False) -> list[dict]:
    q = f"SELECT * FROM entities WHERE {ANALYSED}"
    if novel_only:
        q += " AND is_novel=1"
    # Worst first: confidently wrong, then high fraud score, then low TM.
    q += " ORDER BY confidently_wrong DESC, fraud_score DESC, tm_by_experiment ASC LIMIT ?"
    with connect() as conn:
        return [dict(r) for r in conn.execute(q, (limit,)).fetchall()]


def weekly_aggregates() -> list[dict]:
    """Per-week means for the trend figure, oldest -> newest."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT r.label AS label,
                      AVG(e.tm_by_experiment) AS mean_tm,
                      SUM(e.confidently_wrong) AS confidently_wrong,
                      COUNT(*) AS n_compared
               FROM entities e JOIN runs r ON e.run_id = r.id
               WHERE e.status IN ('screened','compared')
               GROUP BY r.label ORDER BY r.label ASC"""
        ).fetchall()
        return [dict(r) for r in rows]


# --------------------------------------------------------------------------------------
# Analysis-tab support: enrichment annotations + cached snapshot
# --------------------------------------------------------------------------------------
def compared_needing_annotation(limit: Optional[int] = None) -> list[dict]:
    """Fully-analysed entities that have no enrichment annotation row yet."""
    q = ("SELECT e.entity_id, e.entry_id, e.chain, e.uniprot, e.description, e.uniprot_name, "
         "e.is_novel, e.closest_pre_cutoff, e.metrics_json "
         "FROM entities e LEFT JOIN entity_annotations a ON a.entity_id = e.entity_id "
         "WHERE e.status='compared' AND a.entity_id IS NULL ORDER BY e.fraud_score DESC")
    if limit:
        q += f" LIMIT {int(limit)}"
    with connect() as conn:
        return [dict(r) for r in conn.execute(q).fetchall()]


def upsert_annotation(row: dict) -> None:
    row = {**row, "enriched_at": _now()}
    cols = ", ".join(row)
    placeholders = ", ".join(f":{c}" for c in row)

    def _do():
        with connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO entity_annotations ({cols}) VALUES ({placeholders})", row
            )
    _retry_write(_do)


def compared_with_annotations() -> list[dict]:
    """All fully-analysed entities joined to their enrichment annotations (for aggregation).
    Includes metrics_json for feature extraction; excludes the big heatmap/per-residue blobs."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT e.entity_id, e.entry_id, e.chain, e.uniprot, e.uniprot_name, e.description,
                      e.deposit_date, e.release_date, e.resolution, e.method, e.novelty_identity,
                      e.is_novel, e.closest_pre_cutoff, e.mean_plddt, e.tm_by_experiment, e.lddt,
                      e.gdt_ts, e.ca_rmsd, e.fraud_score, e.confidently_wrong, e.metrics_json, e.run_id,
                      r.label AS week,
                      a.sequence, a.seq_length, a.cath_code, a.cath_class, a.cath_arch, a.cath_topo,
                      a.cath_name, a.scop2_sf, a.ecod_family, a.pfam_json,
                      a.citation_doi, a.citation_title, a.citation_journal, a.citation_year,
                      a.citation_pubmed, a.n_chains, a.assembly_count,
                      a.is_amyloid, a.is_idr, a.is_assembly, a.is_coiledcoil, a.is_engineered
               FROM entities e
               JOIN entity_annotations a ON a.entity_id = e.entity_id
               LEFT JOIN runs r ON e.run_id = r.id
               WHERE e.status='compared'"""
        ).fetchall()
        return [dict(r) for r in rows]


def annotation_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) n FROM entity_annotations").fetchone()["n"]


def save_snapshot(kind: str, data: dict) -> None:
    import json as _json

    def _do():
        with connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO analysis_snapshots(kind, data_json, updated_at) VALUES (?,?,?)",
                (kind, _json.dumps(data), _now()),
            )
    _retry_write(_do)


def load_snapshot(kind: str = "cumulative") -> Optional[dict]:
    import json as _json

    with connect() as conn:
        row = conn.execute(
            "SELECT data_json, updated_at FROM analysis_snapshots WHERE kind=?", (kind,)
        ).fetchone()
        if not row:
            return None
        data = _json.loads(row["data_json"])
        data["_updated_at"] = row["updated_at"]
        return data


def record_visit(ip_hash: str) -> None:
    def _do():
        with connect() as conn:
            conn.execute(
                "INSERT INTO visits(ip_hash, first_seen, last_seen, hits) VALUES (?,?,?,1) "
                "ON CONFLICT(ip_hash) DO UPDATE SET last_seen=excluded.last_seen, hits=hits+1",
                (ip_hash, _now(), _now()),
            )
    _retry_write(_do)


def visitor_stats() -> dict:
    try:
        with connect() as conn:
            r = conn.execute("SELECT COUNT(*) uniq, COALESCE(SUM(hits),0) hits FROM visits").fetchone()
            today = _now()[:10]
            t = conn.execute("SELECT COUNT(*) n FROM visits WHERE substr(last_seen,1,10)=?", (today,)).fetchone()
            return {"unique": r["uniq"], "hits": r["hits"], "today": t["n"]}
    except sqlite3.OperationalError:      # visits table not created yet (fresh deploy)
        return {"unique": 0, "hits": 0, "today": 0}


def db_size_bytes() -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        p = str(config.DB_PATH) + suffix
        if os.path.exists(p):
            total += os.path.getsize(p)
    return total


def overall_stats() -> dict:
    with connect() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) n, SUM(confidently_wrong) cw, SUM(is_novel) novel,
                       SUM(CASE WHEN is_novel=1 AND confidently_wrong=1 THEN 1 ELSE 0 END) novel_wrong,
                       AVG(tm_by_experiment) avg_tm, AVG(lddt) avg_lddt,
                       SUM(status='compared') fully
                FROM entities WHERE {ANALYSED}"""
        ).fetchone()
        return dict(row) if row else {}
