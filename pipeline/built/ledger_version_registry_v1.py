"""Plan step 8: version registry for contract tables — publish only with a matching approval, restore by pointer.

A candidate is registered with the SHA-256 of its SQLite and of its quality-gate report. Publishing needs an
approval record whose version, file hash, gate hash and verdict match, a waiver for every warning, and the
expected registry revision. A blocked verdict is never publishable. Pointer, revision and event change in one
transaction; any failure leaves the active version as it was. Restore moves the pointer back after checking
the target file hash. Revoking the approval of the active version restores the previous published version.

The registry never writes a product table; product switch is a separate approval outside this module.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS version (
    version_id TEXT PRIMARY KEY, path TEXT NOT NULL, db_sha256 TEXT NOT NULL, gate_sha256 TEXT NOT NULL,
    verdict TEXT NOT NULL, state TEXT NOT NULL CHECK (state IN ('candidate','published','rejected','revoked')),
    registered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pointer (id INTEGER PRIMARY KEY CHECK (id = 1), active TEXT, revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS event (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, action TEXT NOT NULL, version_id TEXT,
    revision INTEGER, detail TEXT
);
INSERT OR IGNORE INTO pointer VALUES (1, NULL, 0);
"""


class Refused(Exception):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Registry:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "registry.sqlite"
        with self._db() as db:
            db.executescript(DDL)

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, isolation_level=None)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def status(self) -> dict:
        with self._db() as db:
            active, rev = db.execute("SELECT active, revision FROM pointer WHERE id = 1").fetchone()
            sha = db.execute("SELECT db_sha256 FROM version WHERE version_id = ?", (active,)).fetchone() if active else None
        return {"active": active, "revision": rev, "active_db_sha256": sha[0] if sha else None}

    def register(self, version_id: str, db_path: Path, gate_path: Path) -> dict:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        row = (version_id, str(db_path), sha256(db_path), sha256(gate_path), gate["verdict"],
               "rejected" if gate["verdict"] == "blocked" else "candidate", now())
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO version VALUES (?,?,?,?,?,?,?)", row)
            db.execute("INSERT INTO event (at, action, version_id, detail) VALUES (?,?,?,?)",
                       (now(), "register", version_id, gate["verdict"]))
            db.execute("COMMIT")
        return {"version_id": version_id, "verdict": gate["verdict"], "state": row[5]}

    def _version(self, db: sqlite3.Connection, version_id: str) -> dict:
        r = db.execute("SELECT version_id, path, db_sha256, gate_sha256, verdict, state FROM version WHERE version_id = ?",
                       (version_id,)).fetchone()
        if not r:
            raise Refused(f"unknown version {version_id}")
        return dict(zip(("version_id", "path", "db_sha256", "gate_sha256", "verdict", "state"), r))

    def _check_files(self, v: dict) -> None:
        if not Path(v["path"]).exists() or sha256(Path(v["path"])) != v["db_sha256"]:
            raise Refused("version file missing or changed since registration")

    def publish(self, version_id: str, approval_path: Path, expected_revision: int, fail_at: str | None = None) -> dict:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        with self._db() as db:
            v = self._version(db, version_id)
            if v["verdict"] == "blocked" or v["state"] in ("rejected", "revoked"):
                raise Refused(f"version state {v['state']} / verdict {v['verdict']} cannot be published")
            if approval.get("version") != version_id or approval.get("version_db_sha256") != v["db_sha256"] \
                    or approval.get("gate_report_sha256") != v["gate_sha256"] or approval.get("verdict") != v["verdict"]:
                raise Refused("approval record does not match this version, its file or its gate report")
            if approval.get("scope_of_approval") != "shadow_only":
                raise Refused("only shadow_only approvals are accepted here; product switch is a separate decision")
            if not approval.get("approved_by") or not approval.get("approved_on"):
                raise Refused("approval record has no approver or date")
            gate = json.loads(Path(v["path"]).with_name(Path(v["path"]).stem + "_gate.json").read_text(encoding="utf-8"))
            warns = {c["check"] for c in gate["checks"] if c["status"] == "warn"}
            waived = {w.get("check") for w in approval.get("waivers", []) if w.get("reason")}
            if warns - waived:
                raise Refused(f"warnings without a waiver: {sorted(warns - waived)}")
            self._check_files(v)
            db.execute("BEGIN IMMEDIATE")
            try:
                active, rev = db.execute("SELECT active, revision FROM pointer WHERE id = 1").fetchone()
                if rev != expected_revision:
                    raise Refused(f"revision moved: expected {expected_revision}, now {rev}")
                db.execute("UPDATE pointer SET active = ?, revision = ? WHERE id = 1", (version_id, rev + 1))
                db.execute("UPDATE version SET state = 'published' WHERE version_id = ?", (version_id,))
                if fail_at == "publish_before_commit":
                    raise RuntimeError("injected failure before commit")
                db.execute("INSERT INTO event (at, action, version_id, revision, detail) VALUES (?,?,?,?,?)",
                           (now(), "publish", version_id, rev + 1, json.dumps({"from": active})))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return self.status()

    def restore(self, version_id: str, expected_revision: int, reason: str = "restore",
                fail_at: str | None = None) -> dict:
        with self._db() as db:
            v = self._version(db, version_id)
            if v["state"] != "published":
                raise Refused(f"only a previously published version can be restored (state {v['state']})")
            self._check_files(v)
            db.execute("BEGIN IMMEDIATE")
            try:
                active, rev = db.execute("SELECT active, revision FROM pointer WHERE id = 1").fetchone()
                if rev != expected_revision:
                    raise Refused(f"revision moved: expected {expected_revision}, now {rev}")
                db.execute("UPDATE pointer SET active = ?, revision = ? WHERE id = 1", (version_id, rev + 1))
                if fail_at == "restore_before_commit":
                    raise RuntimeError("injected failure before commit")
                db.execute("INSERT INTO event (at, action, version_id, revision, detail) VALUES (?,?,?,?,?)",
                           (now(), "restore", version_id, rev + 1, json.dumps({"from": active, "reason": reason})))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return self.status()

    def previous_published(self, exclude: str) -> str | None:
        with self._db() as db:
            for (vid,) in db.execute(
                "SELECT e.version_id FROM event e JOIN version v USING (version_id)"
                " WHERE e.action IN ('publish','restore') AND v.state = 'published' AND e.version_id <> ?"
                " ORDER BY e.seq DESC", (exclude,)
            ):
                return vid
        return None

    def revoke(self, version_id: str, reason: str) -> dict:
        """Approval withdrawn: the version can no longer be active; if it is, the previous one comes back."""
        st = self.status()
        target = self.previous_published(version_id) if st["active"] == version_id else None
        if st["active"] == version_id and not target:
            raise Refused("no previous published version to fall back to")
        if target:
            self.restore(target, st["revision"], reason=f"approval revoked: {reason}")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE version SET state = 'revoked' WHERE version_id = ?", (version_id,))
            db.execute("INSERT INTO event (at, action, version_id, detail) VALUES (?,?,?,?)",
                       (now(), "revoke", version_id, reason))
            db.execute("COMMIT")
        return self.status()

    def events(self) -> list[tuple]:
        with self._db() as db:
            return db.execute("SELECT seq, action, version_id, revision FROM event ORDER BY seq").fetchall()
