"""Pluggable ANPR (Automatic Number Plate Recognition).

Same seam pattern as detector.py: `StubPlateReader` is a no-op so the
pipeline runs without extra dependencies; `PaddleOcrPlateReader` is a real,
open-source implementation to enable once weights/deps are installed.

`read()` returns `(plate, confidence)` rather than just a plate string —
the pipeline needs the confidence to decide whether to trust a single-frame
read outright or hold it for temporal fusion (see pipeline.py), and to log
it on VehicleEvent.plate_confidence either way.
"""
from __future__ import annotations

import itertools
import logging
import re
from typing import Optional, Protocol, Tuple

import numpy as np

logger = logging.getLogger("sentinel.anpr")

# Indian vehicle registration formats. Two are legal and they are
# structurally incompatible, so the gate is an alternation of both rather
# than one loosened pattern — widening the state-series regex enough to
# also admit BH plates would admit a great deal of OCR noise with them.

# State series, e.g. "GJ01AB1234" / "DL1CAB1234".
_STATE_SERIES = r"[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{3,4}"
_STATE_SERIES_RE = re.compile(_STATE_SERIES)

# RTO state/UT code whitelist — TASKS.md's "State-code whitelist for
# _STATE_SERIES" item, researched 2026-09-19, implemented 2026-09-26 after
# a real sandbox misread (`FS11ICO9525` — "FS" is not a real code; the
# actual plate was `GJ11CO9625`, misread on a blurrier frame) made the gap
# concrete rather than theoretical.
#
# Gathered 2026-09-19 from Wikipedia's "Vehicle registration plates of
# India" — 28 states + 8 union territories, 36 current codes:
_CURRENT_STATE_CODES = frozenset({
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "GA", "GJ", "HP",
    "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ",
    "NL", "OD", "PB", "PY", "RJ", "SK", "TG", "TN", "TR", "UK", "UP", "WB",
})
# Retired codes that MUST still be accepted: a state/UT rename does not
# re-register the vehicles already on the road under the old code, so
# these keep appearing in real traffic for years after the change.
_RETIRED_STATE_CODES = frozenset({
    "TS",  # Telangana -> TG, 14 Mar 2024 (~10 years of TS-plated vehicles still on the road)
    "DN",  # Daman & Diu -> DD, 25 Jan 2020 (merged into Dadra & Nagar Haveli and Daman & Diu)
    "OR",  # Orissa -> OD (Odisha), 2011
    "UA",  # Uttaranchal -> UK (Uttarakhand), 2007
})
_KNOWN_STATE_CODES = _CURRENT_STATE_CODES | _RETIRED_STATE_CODES

# Bharat (BH) series, e.g. "23BH1234AA" / "25BH0123C". Notified by MoRTH on
# 26 Aug 2021 (registrations opened 15 Sep 2021) for vehicles that move
# between states, so these are on the road now and a Gujarat camera will
# see them.
#
# Format is YY-BH-####-XX: two year digits, the literal "BH", a four-digit
# serial, then ONE OR TWO letters. Critically it *starts with digits*,
# which is why the state-series pattern above rejects every BH plate
# outright — found 2026-09-19, see RESEARCH_ANPR_DEEP_2026-09-19.md §A1.
# The bug was silent and one-directional in a nasty way: a BH plate could
# still be added to a watchlist and searched for (both paths only call
# normalize_plate, which does no format validation), so those operations
# appeared to succeed while never being able to match anything, because no
# BH plate could ever enter the database.
#
# "I" and "O" are excluded from the trailing letters by the registration
# rules themselves, precisely to avoid confusion with the digits 1 and 0.
# Encoding that here is not cosmetic: it stops the homoglyph search below
# from "rescuing" a misread into a plate that could never legally exist.
_BH_SERIES = r"[0-9]{2}BH[0-9]{4}[A-HJ-NP-Z]{1,2}"

PLATE_PATTERN = re.compile(f"(?:{_STATE_SERIES}|{_BH_SERIES})")

# Common OCR digit/letter homoglyph confusions on small, low-contrast plate
# crops (found 2026-09-05 against a real two/three-wheeler plate at cam06:
# PaddleOCR read "GJOSA"+"Y6417" for an actual "GJ05AV6417" — 0 misread as O,
# 5 misread as S). Symmetric: doesn't assume which direction is "correct",
# just which characters get mistaken for each other either way.
_HOMOGLYPHS = {"O": "0", "0": "O", "S": "5", "5": "S", "I": "1", "1": "I",
               "B": "8", "8": "B", "Z": "2", "2": "Z"}


def _ambiguous_variants(candidate: str, max_flip_positions: int = 4):
    """Yields `candidate` itself, then variants with 1..N of its homoglyph
    -ambiguous characters flipped, cheapest (fewest flips) first. Bounded
    (max_flip_positions) so this stays a fast heuristic, not a combinatorial
    search — every variant is re-validated against the strict PLATE_PATTERN
    by the caller, so a bad flip just fails to match rather than producing
    a false plate silently; this only ever turns a REJECTED read into an
    ACCEPTED one, never the reverse."""
    yield candidate
    ambiguous_positions = [i for i, c in enumerate(candidate) if c in _HOMOGLYPHS]
    if not ambiguous_positions:
        return
    for n in range(1, min(len(ambiguous_positions), max_flip_positions) + 1):
        for combo in itertools.combinations(ambiguous_positions, n):
            chars = list(candidate)
            for i in combo:
                chars[i] = _HOMOGLYPHS[chars[i]]
            yield "".join(chars)


def _best_pattern_match(candidate: str) -> Optional[str]:
    """Strict match first; only tries homoglyph variants if the literal
    OCR output doesn't already validate. Returns the first (fewest-flips)
    variant that fullmatches, or None.

    Honest limitation (see tests/test_anpr.py): "fewest flips" is not the
    same as "most plausible plate" — this has no positional knowledge of
    which segment should be digits vs. letters, so it can return a
    technically-pattern-valid but real-world-unlikely correction (e.g.
    flipping only one of two ambiguous characters when flipping both would
    look more like a real RTO code). Good enough to gate "is this
    plate-SHAPED at all," not a guarantee of exact character accuracy —
    that's still what tracker.py's cross-frame consensus voting is for.

    State/UT code whitelist (added 2026-09-26): a state-series match
    (`_STATE_SERIES`) additionally has to carry a real RTO code — any two
    letters used to pass (`XQ01AB1234`, `ZZ01AB1234`), which is most of the
    false-positive surface at the most error-prone character positions.
    BH-series matches carry no state code and are unaffected. Deliberately
    NOT silent the way a bare whitelist would be: the same class of defect
    (an over-tight validator quietly discarding valid plates) caused the
    BH-series bug fixed 2026-09-05, and a real state/UT code missing from
    the list here would be exactly that failure again, just for a
    different population — see the module-level `_KNOWN_STATE_CODES`
    comment. So a shape-valid state-series candidate whose code isn't
    recognised is still rejected (a garbage code is still garbage), but
    the rejection logs the exact code that triggered it, once per call,
    so a real code missing from the list shows up as an observable signal
    instead of silently and permanently dropping every plate that starts
    with it."""
    unknown_state_code: Optional[str] = None
    for variant in _ambiguous_variants(candidate):
        if not PLATE_PATTERN.fullmatch(variant):
            continue
        state_match = _STATE_SERIES_RE.fullmatch(variant)
        if state_match is None:
            return variant  # BH-series — no state code to check
        code = variant[:2]
        if code in _KNOWN_STATE_CODES:
            return variant
        if unknown_state_code is None:
            unknown_state_code = code
    if unknown_state_code is not None:
        logger.warning(
            "anpr: shape-valid plate rejected — unrecognised state/UT code "
            "%r (candidate=%r). If this is a real code, add it to "
            "_KNOWN_STATE_CODES/_RETIRED_STATE_CODES in anpr.py.",
            unknown_state_code, candidate,
        )
    return None


class PlateReader(Protocol):
    def read(self, vehicle_crop: np.ndarray) -> Optional[Tuple[str, float]]: ...


class StubPlateReader:
    def read(self, vehicle_crop: np.ndarray) -> Optional[Tuple[str, float]]:
        return None


class PaddleOcrPlateReader:
    """Real implementation using PaddleOCR (open source, Apache 2.0, actively
    maintained — preferred over EasyOCR/Tesseract/OpenALPR for this project;
    see STRATEGY.md). Lazily imported.

    No open-source model reads Indian plates out of the box with high
    accuracy — this is the OCR stage of a pipeline whose Indian-plate
    specialization comes from the detector, PLATE_PATTERN validation below,
    and temporal fusion across frames (see pipeline.py), not from PaddleOCR
    itself.
    """

    def __init__(self, lang: str = "en"):
        # Windows DLL-ordering guard: torch (imported by YoloVehicleDetector
        # via ultralytics) must load before paddlepaddle in this process, or
        # torch's native DLL loading breaks — reproduced empirically (see
        # HLD.md §8). Relying on every *caller* to construct the detector
        # before the plate reader is a real footgun (a caller can easily miss
        # it — this exact bug was caught by testing against the live sandbox,
        # not by inspection). Import torch defensively here as a self-healing
        # guard, regardless of construction order upstream. Safe if torch
        # isn't installed at all (ImportError swallowed) or already imported
        # (no-op).
        try:
            import torch  # noqa: F401, PLC0415
        except ImportError:
            pass

        from paddleocr import PaddleOCR  # noqa: PLC0415

        self._reader = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    def read(self, vehicle_crop: np.ndarray) -> Optional[Tuple[str, float]]:
        results = self._reader.ocr(vehicle_crop, cls=True)
        best: Optional[Tuple[str, float]] = None
        detections = []  # (mean_y, text, conf) — collected for the multi-line join below

        for line in results or []:
            # When PaddleOCR finds no text at all in the image, it returns
            # `[None]` for that image, not `[]]` — confirmed against a real
            # blank-crop call, not assumed. Skip rather than crash.
            if not line:
                continue
            for box, (text, conf) in line:
                candidate = re.sub(r"[^A-Z0-9]", "", text.upper())
                matched = _best_pattern_match(candidate)
                if matched is not None and (best is None or conf > best[1]):
                    best = (matched, float(conf))
                mean_y = sum(pt[1] for pt in box) / len(box)
                detections.append((mean_y, candidate, float(conf)))

        if best is not None:
            return best

        # Two/three-wheeler plates are commonly TWO lines (e.g. "GJ05A" /
        # "V6417" for "GJ05AV6417") — PaddleOCR detects each line as its
        # own text region, so no single line ever fullmatches PLATE_PATTERN
        # on its own. Found 2026-09-05 against a real sandbox camera
        # (cam06): both lines read individually close-but-wrong
        # ("GJOSA"/"3Y6417"), neither matched alone, but the plate was
        # genuinely legible. Concatenating detections top-to-bottom (by
        # mean bounding-box y) and re-checking the JOINED string (with the
        # same homoglyph correction) recovers reads a single-line-only
        # check misses entirely. Skipped if there's only one detection —
        # that case is already covered by the per-line loop above.
        if len(detections) >= 2:
            detections.sort(key=lambda d: d[0])
            joined = "".join(d[1] for d in detections)
            matched = _best_pattern_match(joined)
            if matched is not None:
                # Conservative: a joined read is only as trustworthy as its
                # weakest line, not its strongest.
                joined_conf = min(d[2] for d in detections)
                return (matched, joined_conf)

        return None


def normalize_plate(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", raw.upper())
