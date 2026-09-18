"""Automated SQLite backup/restore + integrity verification — turns
`docs/models/model-4-central-vms/DR_RUNBOOK.md`'s manual `sqlite3
.backup` shell instructions into a real, tested script.

**Status: AUTOMATED-TEST VERIFIED** (see `tests/test_backup_restore.py`)
— unlike this session's Kafka/pgvector/OIDC/Docker/K8s scaffolds, this
needs no external infrastructure: it's pure Python stdlib `sqlite3`
against the same kind of file the pilot already uses, so it was
actually run and checked, not just written.

**Still explicitly does NOT claim what the DR runbook's "Not
implemented" section says isn't implemented**: no PostgreSQL
replication, no cross-region object storage, no automated *scheduling*
(this is a script to run — via cron/Task Scheduler/systemd timer — not
a scheduler itself), and no RPO/RTO number (that requires measuring
real backup frequency and restore time against a real deployment's
actual data volume, not asserting a target).

Usage:
    python scripts/backup_restore_sqlite.py backup <db_path> <backup_dir> [--keep N]
    python scripts/backup_restore_sqlite.py verify <backup_path>
    python scripts/backup_restore_sqlite.py restore <backup_path> <restore_target_path>
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup(db_path: str, backup_dir: str, keep: int = 10) -> Path:
    """Uses SQLite's online backup API (`sqlite3.Connection.backup`) —
    safe against a live writer, unlike copying the file with `shutil`
    while WAL/journal files might be mid-write. Writes a JSON-lines
    manifest entry (operator, timestamp, sha256, source, size) per the
    DR runbook's step 4 ("record operator, time and SHA-256"), and
    prunes backups beyond `keep` (oldest first) so this can run on an
    unattended schedule without unbounded disk growth."""
    src_path = Path(db_path)
    if not src_path.exists():
        raise FileNotFoundError(f"source database not found: {src_path}")

    out_dir = Path(backup_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dest_path = out_dir / f"{src_path.stem}-{timestamp}.db"

    src_conn = sqlite3.connect(str(src_path))
    dest_conn = sqlite3.connect(str(dest_path))
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    checksum = sha256_file(dest_path)
    manifest_entry = {
        "operator": getpass.getuser(),
        "timestamp_utc": timestamp,
        "source": str(src_path),
        "backup_path": str(dest_path),
        "sha256": checksum,
        "size_bytes": dest_path.stat().st_size,
    }
    manifest_path = out_dir / "backup_manifest.jsonl"
    with open(manifest_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(manifest_entry) + "\n")

    _prune_old_backups(out_dir, src_path.stem, keep)
    return dest_path


def _prune_old_backups(out_dir: Path, stem: str, keep: int) -> None:
    backups = sorted(out_dir.glob(f"{stem}-*.db"))
    excess = len(backups) - keep
    for old in backups[:max(excess, 0)]:
        old.unlink()


def verify(backup_path: str) -> bool:
    """SQLite's own `PRAGMA integrity_check` — the DR runbook's step 3
    ("run the backend test suite and inspect /health") covers
    application-level health; this covers whether the backup FILE
    itself is structurally sound, which a restore drill needs checked
    first, before ever pointing the real app at it."""
    conn = sqlite3.connect(str(backup_path))
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()
    return result is not None and result[0] == "ok"


def restore(backup_path: str, restore_target_path: str) -> Path:
    """Copies into an explicit, separate target path — NEVER the live
    `sentinel.db` — per the DR runbook's step 1 ("restore only into an
    isolated copy; never overwrite the live pilot DB") and this repo's
    own `CLAUDE.md` §15.7/§24.3 (never destroy real accumulated
    evidence data). Refuses outright if the target already exists,
    rather than silently overwriting it."""
    target = Path(restore_target_path)
    if target.exists():
        raise FileExistsError(
            f"restore target already exists: {target} — refusing to overwrite; "
            "choose a new path (this is deliberate, see this script's docstring)"
        )
    if not verify(backup_path):
        raise RuntimeError(f"backup file failed integrity check, refusing to restore: {backup_path}")
    shutil.copy2(backup_path, target)
    return target


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_backup = sub.add_parser("backup")
    p_backup.add_argument("db_path")
    p_backup.add_argument("backup_dir")
    p_backup.add_argument("--keep", type=int, default=10)

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("backup_path")

    p_restore = sub.add_parser("restore")
    p_restore.add_argument("backup_path")
    p_restore.add_argument("restore_target_path")

    args = parser.parse_args(argv)

    if args.command == "backup":
        dest = backup(args.db_path, args.backup_dir, keep=args.keep)
        print(f"backup written: {dest}")
    elif args.command == "verify":
        ok = verify(args.backup_path)
        print("integrity check: OK" if ok else "integrity check: FAILED")
        return 0 if ok else 1
    elif args.command == "restore":
        dest = restore(args.backup_path, args.restore_target_path)
        print(f"restored to: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
