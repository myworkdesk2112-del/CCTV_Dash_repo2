"""Write-time integrity and provenance for a stored evidence image.

CLAUDE.md §6 Priority B names the exact failure mode this module exists
to avoid: "Do not recompute the hash only at export and pretend that
proves write-time integrity." A hash taken at export time proves only
that a file matches itself a moment ago — it says nothing about whether
the bytes changed between capture and export. So the SHA-256 here is
computed by pipeline.py immediately after `cv2.imwrite` returns, stored
on the event row together with the timestamp it was taken at, and never
recomputed into that column afterwards.

`verify_crop` recomputes the hash of the file as it exists *now* and
compares it against the stored value. That comparison is what makes the
stored column load-bearing: a mismatch is reported as a mismatch, never
silently healed by overwriting the stored hash.

The production stamp records what actually produced the image — the
concrete detector/plate-detector/OCR class names in effect at write
time, not the configured filenames alone. That distinction matters for
evidence: a `StubPlateDetector` and a `YoloPlateDetector` produce very
different artefacts from identical config, and an evidence package that
cannot tell a reviewer which one ran is not a provenance record.

Wording is deliberately "§63-oriented" throughout, never "§63
compliant": per CLAUDE.md §17 this prepares a hash-and-provenance
package for legal review. Whether the result is admissible depends on
the operating procedure around the system and on a qualified legal
reviewer, neither of which is a property of this file.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os

from .. import config

# Bumped when the exported package's field layout changes, so a reviewer
# holding an older package can tell which schema produced it.
PACKAGE_SCHEMA_VERSION = "sentinel-evidence-package/1"

# verify_crop statuses.
VERIFIED = "VERIFIED"
HASH_MISMATCH = "HASH_MISMATCH"
FILE_MISSING = "FILE_MISSING"
NO_HASH_RECORDED = "NO_HASH_RECORDED"

_VERIFY_REASONS = {
    VERIFIED: (
        "The stored image's current SHA-256 matches the hash recorded when "
        "it was written. The bytes are unchanged since capture."
    ),
    HASH_MISMATCH: (
        "The stored image's current SHA-256 does NOT match the hash "
        "recorded at write time. The file has changed since capture — treat "
        "it as unreliable and investigate."
    ),
    FILE_MISSING: (
        "A hash was recorded at write time but the image file is no longer "
        "present on disk, so integrity cannot be confirmed."
    ),
    NO_HASH_RECORDED: (
        "This sighting predates write-time hashing, so no integrity claim "
        "can be made about its image. Absence of a hash is not evidence of "
        "tampering — it means the guarantee was never established."
    ),
}

_CHUNK_BYTES = 1024 * 1024


def sha256_file(path: str) -> str | None:
    """Hex SHA-256 of a file's bytes, or None if it can't be read.

    Chunked rather than `f.read()`: an evidence crop is small today, but
    this same helper is the obvious place a future full-frame or clip
    export would reuse, and a whole-file read would size the buffer to
    the artefact. Returns None (rather than raising) so a hashing failure
    degrades to "no integrity claim" instead of taking down the caller —
    pipeline.py must never crash the ingest loop over evidence metadata.
    """
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(_CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def production_stamp(
    detector: object | None = None,
    plate_detector: object | None = None,
    plate_reader: object | None = None,
    reid_encoder: object | None = None,
) -> str:
    """Compact, persistable record of what produced an evidence image.

    Stored as a single string column rather than a JSON blob or six
    columns: it is written once per event, is never queried on, and is
    meant to be read by a human reviewer inside an evidence package. A
    string keeps the additive migration to one column and stays readable
    if it is ever dumped straight out of the database.

    Component *class names* are recorded, not just `config` filenames,
    because the real/stub seam (CLAUDE.md §15.1) is invisible in config:
    `StubPlateDetector` and `YoloPlateDetector` can both run with the
    same `PLATE_DETECTOR_WEIGHTS` set. `build_rev` is whatever the
    deployment supplies via SENTINEL_BUILD_REV — "unknown" when nothing
    does, which is honest rather than inventing a version string the code
    cannot actually verify about itself.
    """
    parts = [
        f"schema={PACKAGE_SCHEMA_VERSION}",
        f"detector={type(detector).__name__ if detector is not None else 'unknown'}",
        f"plate_detector={type(plate_detector).__name__ if plate_detector is not None else 'unknown'}",
        f"plate_reader={type(plate_reader).__name__ if plate_reader is not None else 'unknown'}",
        f"reid={type(reid_encoder).__name__ if reid_encoder is not None else 'unknown'}",
        f"yolo_weights={config.YOLO_WEIGHTS}",
        f"plate_weights={os.path.basename(config.PLATE_DETECTOR_WEIGHTS)}",
        f"plate_min_conf={config.PLATE_MIN_CONFIDENCE}",
        f"build_rev={os.environ.get('SENTINEL_BUILD_REV', 'unknown')}",
    ]
    return ";".join(parts)


def parse_production_stamp(stamp: str | None) -> dict:
    """Split a stored stamp back into a dict for display in a package.

    Tolerant by design: a stamp written by an older or newer build may
    carry keys this version doesn't know, and a malformed segment must
    not break an evidence export. Unknown keys are preserved verbatim
    rather than dropped — a reviewer should see everything that was
    recorded, including fields this code no longer writes.
    """
    if not stamp:
        return {}
    parsed: dict = {}
    for segment in stamp.split(";"):
        if not segment:
            continue
        key, sep, value = segment.partition("=")
        if sep:
            parsed[key] = value
        else:
            parsed.setdefault("_unparsed", []).append(segment)
    return parsed


def verify_crop(crop_path: str | None, stored_sha256: str | None) -> dict:
    """Recompute and compare — the integrity check itself.

    Returns the computed hash alongside the status even on mismatch, so a
    reviewer can see both values rather than being told only that they
    differ.
    """
    if not stored_sha256:
        return {
            "status": NO_HASH_RECORDED,
            "reason": _VERIFY_REASONS[NO_HASH_RECORDED],
            "recorded_sha256": None,
            "current_sha256": None,
        }

    if not crop_path:
        return {
            "status": FILE_MISSING,
            "reason": _VERIFY_REASONS[FILE_MISSING],
            "recorded_sha256": stored_sha256,
            "current_sha256": None,
        }

    absolute = os.path.join(config.CROPS_DIR, crop_path)
    current = sha256_file(absolute)
    if current is None:
        return {
            "status": FILE_MISSING,
            "reason": _VERIFY_REASONS[FILE_MISSING],
            "recorded_sha256": stored_sha256,
            "current_sha256": None,
        }

    status = VERIFIED if current == stored_sha256 else HASH_MISMATCH
    return {
        "status": status,
        "reason": _VERIFY_REASONS[status],
        "recorded_sha256": stored_sha256,
        "current_sha256": current,
    }


def legal_review_notice() -> str:
    """The single wording of the §63 caveat, defined once.

    Kept here rather than written inline at each call site so the JSON
    package, the PDF certificate, and any future export path cannot drift
    into making different-strength legal claims about the same artefact.
    """
    return (
        "§63-ORIENTED PACKAGE — NOT A CERTIFICATE OF ADMISSIBILITY. This "
        "package is prepared to support review under Section 63 of the "
        "Bharatiya Sakshya Adhiniyam, 2023 (electronic evidence). It "
        "records the hash captured when the image was written, the "
        "software and models that produced it, the camera and department "
        "of origin, and the access/export audit trail. It does not itself "
        "certify admissibility: the Part A/Part B declarations below must "
        "be completed and signed by the authorised person, and the "
        "package reviewed by qualified legal counsel."
    )


def utc_now_iso() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"
