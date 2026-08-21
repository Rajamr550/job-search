"""SQLite tracker for jobs, applications, and status history."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

STATUSES = (
    "found",
    "queued",
    "applied",
    "failed",
    "skipped",
    "manual",
    "viewed",
    "interview",
    "rejected",
    "offer",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Tracker:
    def __init__(self, db_path: str | Path = "db/jobs.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portal TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT,
                    company TEXT,
                    location TEXT,
                    remote_type TEXT,
                    url TEXT,
                    description TEXT,
                    fit_score REAL,
                    discovered_at TEXT,
                    UNIQUE(portal, external_id)
                );

                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL REFERENCES jobs(id),
                    status TEXT NOT NULL,
                    resume_version TEXT,
                    error_message TEXT,
                    updated_at TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL REFERENCES applications(id),
                    status TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS portal_health (
                    portal TEXT PRIMARY KEY,
                    needs_reauth INTEGER DEFAULT 0,
                    last_error TEXT,
                    updated_at TEXT
                );
                """
            )

    def upsert_job(
        self,
        *,
        portal: str,
        external_id: str,
        title: str,
        company: str,
        location: str,
        remote_type: str,
        url: str,
        description: str,
        fit_score: float,
    ) -> int:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO jobs (portal, external_id, title, company, location, remote_type, url, description, fit_score, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(portal, external_id) DO UPDATE SET
                    title=excluded.title,
                    company=excluded.company,
                    location=excluded.location,
                    remote_type=excluded.remote_type,
                    url=excluded.url,
                    description=excluded.description,
                    fit_score=excluded.fit_score
                """,
                (
                    portal,
                    external_id,
                    title,
                    company,
                    location,
                    remote_type,
                    url,
                    description,
                    fit_score,
                    _utc_now(),
                ),
            )
            row = conn.execute(
                "SELECT id FROM jobs WHERE portal=? AND external_id=?",
                (portal, external_id),
            ).fetchone()
            return int(row["id"])

    def has_application(self, job_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM applications WHERE job_id=? LIMIT 1", (job_id,)
            ).fetchone()
            return row is not None

    def create_application(
        self,
        job_id: int,
        status: str = "found",
        resume_version: str = "",
        error_message: str = "",
    ) -> int:
        now = _utc_now()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO applications (job_id, status, resume_version, error_message, updated_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, status, resume_version, error_message, now, now),
            )
            app_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO status_history (application_id, status, note, created_at) VALUES (?, ?, ?, ?)",
                (app_id, status, "", now),
            )
            return app_id

    def update_status(self, application_id: int, status: str, note: str = "") -> None:
        now = _utc_now()
        with self._conn() as conn:
            conn.execute(
                "UPDATE applications SET status=?, error_message=?, updated_at=? WHERE id=?",
                (status, note, now, application_id),
            )
            conn.execute(
                "INSERT INTO status_history (application_id, status, note, created_at) VALUES (?, ?, ?, ?)",
                (application_id, status, note, now),
            )

    def set_portal_health(self, portal: str, needs_reauth: bool, last_error: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO portal_health (portal, needs_reauth, last_error, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(portal) DO UPDATE SET
                    needs_reauth=excluded.needs_reauth,
                    last_error=excluded.last_error,
                    updated_at=excluded.updated_at
                """,
                (portal, 1 if needs_reauth else 0, last_error, _utc_now()),
            )

    def funnel_counts(self) -> dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM applications GROUP BY status"
            ).fetchall()
        return {r["status"]: r["c"] for r in rows}

    def recent_applications(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT a.id AS application_id, a.status, a.updated_at, a.error_message,
                       j.title, j.company, j.portal, j.url, j.fit_score, j.location, j.remote_type
                FROM applications a
                JOIN jobs j ON j.id = a.job_id
                ORDER BY a.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def portal_health(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM portal_health ORDER BY portal").fetchall()
        return [dict(r) for r in rows]

    def applications_by_status(self) -> list[dict[str, Any]]:
        return self.recent_applications(limit=500)

    def get_application_id_for_job(self, job_id: int) -> Optional[int]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM applications WHERE job_id=? ORDER BY id DESC LIMIT 1",
                (job_id,),
            ).fetchone()
        return int(row["id"]) if row else None
