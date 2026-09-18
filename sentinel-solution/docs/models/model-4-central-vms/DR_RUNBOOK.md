# Model 4 Pilot DR Runbook

Status: **DESIGN TARGET** for multi-region failover. The executable pilot
procedure is SQLite backup/restore, now automated and
**AUTOMATED-TEST VERIFIED** (2026-09-18) via
`backend/scripts/backup_restore_sqlite.py` — 7 real tests in
`backend/tests/test_backup_restore.py`, using real on-disk SQLite files,
not mocks. It does not claim replication, RPO, or RTO — see "Not
implemented" below.

## Pilot backup

Automated (replaces the manual shell command below):

```bash
cd backend
python scripts/backup_restore_sqlite.py backup ./sentinel.db /path/to/backup-dir --keep 10
```

Uses SQLite's online backup API (safe against a live writer, unlike a
raw file copy), writes a SHA-256 + operator + timestamp entry to
`backup-dir/backup_manifest.jsonl` (automating the runbook's old step 4
"record operator, time and SHA-256"), and prunes backups beyond
`--keep` so it's safe to run unattended on a schedule (cron/systemd
timer/Task Scheduler — the script itself is not a scheduler).

The original manual procedure (still valid, e.g. for an ad-hoc one-off
outside the script): `sqlite3 sentinel.db ".backup
'sentinel-backup-YYYYMMDD.db'"`, then store it outside the application
tree with equivalent access controls.

## Pilot restore drill

Automated integrity check + restore-into-isolated-copy (refuses to
overwrite an existing target, and refuses to restore a backup that
fails `PRAGMA integrity_check`):

```bash
python scripts/backup_restore_sqlite.py verify /path/to/backup-dir/sentinel-<timestamp>.db
python scripts/backup_restore_sqlite.py restore /path/to/backup-dir/sentinel-<timestamp>.db ./restore-check.db
```

Then, same as before:

1. Start against `DATABASE_URL=sqlite:///./restore-check.db`.
2. Run the backend test suite and inspect `/health` plus an authenticated registry query.
3. Record success/failure and any data-loss window. Do not claim RPO/RTO until measured — the script proves the backup/restore *mechanism* works, not a measured recovery time against real production data volume.

## Not implemented

PostgreSQL replication/failover, cross-zone/cross-region object-storage
replication, Kubernetes orchestration, Kafka recovery and automated backup
scheduling remain **NOT IMPLEMENTED** for this pilot.
