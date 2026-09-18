"""Real, executed coverage for scripts/backup_restore_sqlite.py — the
automated implementation of docs/models/model-4-central-vms/
DR_RUNBOOK.md's previously-manual backup/restore steps. Uses real
on-disk SQLite files (via tmp_path), not mocks — the thing under test
IS file I/O + SQLite's backup API."""
from __future__ import annotations

import json
import sqlite3

import pytest

from scripts.backup_restore_sqlite import backup, restore, verify


def _make_real_db(path, rows=("alpha", "beta")) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
    conn.executemany("INSERT INTO t (val) VALUES (?)", [(r,) for r in rows])
    conn.commit()
    conn.close()


def test_backup_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup(str(tmp_path / "does_not_exist.db"), str(tmp_path / "backups"))


def test_backup_produces_a_verifiable_copy_with_identical_rows(tmp_path):
    src = tmp_path / "sentinel.db"
    _make_real_db(src)

    dest = backup(str(src), str(tmp_path / "backups"))

    assert dest.exists()
    assert verify(dest) is True

    conn = sqlite3.connect(str(dest))
    rows = conn.execute("SELECT val FROM t ORDER BY id").fetchall()
    conn.close()
    assert rows == [("alpha",), ("beta",)]


def test_backup_writes_a_manifest_entry_with_matching_sha256(tmp_path):
    src = tmp_path / "sentinel.db"
    _make_real_db(src)
    backup_dir = tmp_path / "backups"

    dest = backup(str(src), str(backup_dir))

    manifest_path = backup_dir / "backup_manifest.jsonl"
    assert manifest_path.exists()
    entry = json.loads(manifest_path.read_text().strip().splitlines()[-1])
    assert entry["backup_path"] == str(dest)
    assert "operator" in entry and entry["operator"]

    import hashlib

    actual_sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
    assert entry["sha256"] == actual_sha256


def test_backup_prunes_beyond_keep_limit(tmp_path):
    src = tmp_path / "sentinel.db"
    _make_real_db(src)
    backup_dir = tmp_path / "backups"

    import time

    paths = []
    for _ in range(4):
        paths.append(backup(str(src), str(backup_dir), keep=2))
        time.sleep(1.1)  # timestamp resolution is whole seconds

    existing = sorted(backup_dir.glob("sentinel-*.db"))
    assert len(existing) == 2
    # The two newest survive, the two oldest were pruned.
    assert [p.name for p in existing] == [paths[-2].name, paths[-1].name]


def test_verify_rejects_a_corrupted_file(tmp_path):
    corrupted = tmp_path / "corrupted.db"
    corrupted.write_bytes(b"not a real sqlite file at all")
    # A garbage file isn't even a valid SQLite database — sqlite3 raises
    # opening it, which IS the failure signal a restore drill needs.
    with pytest.raises(sqlite3.DatabaseError):
        verify(corrupted)


def test_restore_refuses_to_overwrite_an_existing_target(tmp_path):
    src = tmp_path / "sentinel.db"
    _make_real_db(src)
    dest = backup(str(src), str(tmp_path / "backups"))

    existing_target = tmp_path / "already_here.db"
    existing_target.write_text("do not touch me")

    with pytest.raises(FileExistsError):
        restore(str(dest), str(existing_target))
    assert existing_target.read_text() == "do not touch me"


def test_restore_into_a_fresh_path_produces_a_working_independent_copy(tmp_path):
    src = tmp_path / "sentinel.db"
    _make_real_db(src, rows=("gamma", "delta", "epsilon"))
    dest = backup(str(src), str(tmp_path / "backups"))

    restore_target = tmp_path / "restore-check.db"
    result = restore(str(dest), str(restore_target))

    assert result == restore_target
    conn = sqlite3.connect(str(restore_target))
    rows = conn.execute("SELECT val FROM t ORDER BY id").fetchall()
    conn.close()
    assert rows == [("gamma",), ("delta",), ("epsilon",)]

    # Mutating the restored copy must never touch the original backup —
    # confirms this is a real independent file, not a shared handle/link.
    conn = sqlite3.connect(str(restore_target))
    conn.execute("INSERT INTO t (val) VALUES ('zeta')")
    conn.commit()
    conn.close()
    original_conn = sqlite3.connect(str(dest))
    original_rows = original_conn.execute("SELECT val FROM t ORDER BY id").fetchall()
    original_conn.close()
    assert original_rows == [("gamma",), ("delta",), ("epsilon",)]
