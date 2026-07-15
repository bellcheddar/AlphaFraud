"""SQLite persistence -- shared by the pipeline (writer) and the Flask app (reader).

One row per processed polymer entity. The full metric dict, per-residue arrays, domain
list and heatmap data are stored as JSON; the handful of columns used for sorting,
filtering and the leaderboard are promoted to real columns. Runs group entities into the
weekly batch that produced them (`label` = the release Wednesday the run covers).
"""

from __future__ import annotations

import json
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


def overall_stats() -> dict:
    with connect() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) n, SUM(confidently_wrong) cw, SUM(is_novel) novel,
                       AVG(tm_by_experiment) avg_tm, AVG(lddt) avg_lddt,
                       SUM(status='compared') fully
                FROM entities WHERE {ANALYSED}"""
        ).fetchone()
        return dict(row) if row else {}
