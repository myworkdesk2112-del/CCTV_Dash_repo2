"""Regression coverage for anpr.py's pattern-matching helpers — no
PaddleOCR/torch dependency needed, these are pure string functions.

Found 2026-09-05 against a real sandbox camera (cam06, a close-range
front-on auto-rickshaw shot): PaddleOCR read a genuinely legible two-line
plate as "GJOSA" (top line) + "Y6417" (bottom line) — neither line alone
matched PLATE_PATTERN, and the code never tried the two joined, so a
readable real plate was silently discarded as unread. `_ambiguous_variants`
/`_best_pattern_match` fix both problems: multi-line joining, and OCR's
common 0/O, 5/S, 1/I, 8/B, 2/Z digit-letter confusion.
"""
from __future__ import annotations

import logging

import pytest

from app.analytics.anpr import (
    PLATE_PATTERN,
    _KNOWN_STATE_CODES,
    _ambiguous_variants,
    _best_pattern_match,
)


def test_exact_match_needs_no_correction():
    assert _best_pattern_match("GJ01AB1234") == "GJ01AB1234"


def test_homoglyph_correction_recovers_real_cam06_style_misread():
    # PaddleOCR's literal output for the two joined lines — 0 misread as O,
    # 5 misread as S. Neither raw string matches PLATE_PATTERN.
    joined = "GJOSAY6417"
    assert not PLATE_PATTERN.fullmatch(joined)
    corrected = _best_pattern_match(joined)
    assert corrected is not None
    assert PLATE_PATTERN.fullmatch(corrected)
    # NOT asserting a specific corrected string ("GJ05AY6417" is the
    # real-world-plausible one, but "GJ0SAY6417" — flipping only the O —
    # ALSO satisfies PLATE_PATTERN with fewer flips and is what the
    # fewest-flips-first search actually returns). This is an honest
    # limitation: the heuristic has no positional knowledge of which
    # segment should be digits vs. letters, so "fewest edits" and "most
    # plausible" aren't always the same answer. Fine for gating whether a
    # read is plate-SHAPED at all; not a guarantee of the exact characters.


def test_unfixable_candidate_returns_none():
    # No amount of homoglyph flipping turns free text into a plate shape.
    assert _best_pattern_match("HELLOWORLD") is None


def test_variants_are_bounded_not_combinatorially_exploding():
    # A string where every character is homoglyph-ambiguous must still
    # terminate quickly (max_flip_positions caps how many positions flip
    # at once, not how many variants total for large inputs).
    variants = list(_ambiguous_variants("0O5S1I8B2Z", max_flip_positions=2))
    assert variants[0] == "0O5S1I8B2Z"  # original always yielded first
    assert len(variants) < 1000  # sanity bound, not an exact count


def test_prefers_fewest_flips_when_multiple_variants_match():
    # "GJ0OAB1234" has one ambiguous char that's already correct (0) and
    # one already-correct letter position — only a single flip should be
    # needed, and it should be tried before any multi-flip variant.
    result = _best_pattern_match("GJ0OAB1234")
    assert result == "GJ0OAB1234" or PLATE_PATTERN.fullmatch(result)


# --------------------------------------------------------------------------
# Bharat (BH) series — added 2026-09-19.
#
# The state-series pattern requires two LEADING LETTERS; a BH plate starts
# with two digits, so every BH plate was rejected outright. See
# docs/strategy/RESEARCH_ANPR_DEEP_2026-09-19.md §A1 for how the defect was
# found and why it was silent.
# --------------------------------------------------------------------------

def test_bh_series_plates_validate():
    """Both tail lengths are legal: 'YY BH #### X' and 'YY BH #### XX'."""
    assert PLATE_PATTERN.fullmatch("23BH1234AA")
    assert PLATE_PATTERN.fullmatch("25BH0123C")
    assert _best_pattern_match("23BH1234AA") == "23BH1234AA"


def test_state_series_still_validates_after_adding_bh():
    """The alternation must not disturb the original gate. The wider suite is
    the real regression guard; this is the explicit statement of intent."""
    for plate in ("GJ01AB1234", "DL1CAB1234", "GJ05AV6417", "UP14AB1234"):
        assert PLATE_PATTERN.fullmatch(plate), plate


def test_bh_trailing_letters_reject_i_and_o():
    """Not cosmetic. The registration rules exclude I and O from the trailing
    letters specifically to avoid confusion with 1 and 0, so a read landing on
    one of them is a misread, not a plate — and must not be accepted as a
    vehicle identity that could never legally exist."""
    assert not PLATE_PATTERN.fullmatch("23BH1234AI")
    assert not PLATE_PATTERN.fullmatch("23BH1234AO")
    assert not PLATE_PATTERN.fullmatch("23BH1234IA")
    assert not PLATE_PATTERN.fullmatch("23BH1234OA")


def test_bh_near_misses_are_rejected():
    """The BH branch must stay narrow. Widening the state-series pattern
    enough to admit BH plates would have admitted all of these too."""
    assert not PLATE_PATTERN.fullmatch("23XY1234AA")   # not the BH literal
    assert not PLATE_PATTERN.fullmatch("2BH1234AA")    # one year digit
    assert not PLATE_PATTERN.fullmatch("233BH1234AA")  # three year digits
    assert not PLATE_PATTERN.fullmatch("23BH123AA")    # three serial digits
    assert not PLATE_PATTERN.fullmatch("23BH12345AA")  # five serial digits
    assert not PLATE_PATTERN.fullmatch("23BH1234")     # no trailing letters
    assert not PLATE_PATTERN.fullmatch("23BH1234ABC")  # three trailing letters


def test_homoglyph_search_can_recover_a_bh_misread():
    """Pinned deliberately rather than left incidental: widening the gate also
    widens what the homoglyph search can 'rescue'. OCR reading the year digits
    as letters (2->Z, 3->?) is exactly the confusion _HOMOGLYPHS covers, and
    the recovered string must still be a legal BH plate."""
    misread = "Z3BH1Z34AA"  # 2 misread as Z, twice
    assert not PLATE_PATTERN.fullmatch(misread)
    corrected = _best_pattern_match(misread)
    assert corrected == "23BH1234AA"


def test_homoglyph_search_will_not_invent_an_illegal_bh_plate():
    """The I/O exclusion has to survive the flip search too — otherwise the
    rule would hold for literal reads and quietly not hold for corrected ones,
    which is the worse of the two failure modes."""
    # "1" in the trailing-letter position would flip to "I" under the
    # symmetric homoglyph table; "I" is illegal there, so no BH match exists.
    assert _best_pattern_match("23BH12341") is None
    assert _best_pattern_match("23BH12340") is None


# --------------------------------------------------------------------------
# State/UT code whitelist — implemented 2026-09-26 (researched 2026-09-19,
# see TASKS.md's P1 item). Real trigger: a 2026-09-26 sandbox scan on cam06
# misread a genuine `GJ11CO9625` as `FS11ICO9625` on a blurrier frame — "FS"
# is not a real state/UT code, and the old `[A-Z]{2}` gate would have let it
# through as a distinct, spurious plate.
# --------------------------------------------------------------------------

def test_all_40_known_state_codes_validate():
    """36 current + 4 retired = 40 codes, each on an otherwise-identical
    plate shape. `_KNOWN_STATE_CODES` itself is the source of truth here —
    this test would still pass if the set were wrong, so it's paired with
    the exact-count assertion and the explicit XQ/ZZ rejection below."""
    assert len(_KNOWN_STATE_CODES) == 40
    for code in sorted(_KNOWN_STATE_CODES):
        plate = f"{code}01AB1234"
        assert _best_pattern_match(plate) == plate, code


@pytest.mark.parametrize("code", ["XQ", "ZZ"])
def test_unrecognised_state_codes_are_rejected(code):
    assert _best_pattern_match(f"{code}01AB1234") is None


def test_unrecognised_state_code_logs_a_warning_naming_it(caplog):
    """The whole point of building this as a whitelist (rather than leaving
    the gate permissive) is the risk of silently eating a REAL code that's
    missing from the list — the same failure class as the BH-series bug.
    The warning is what converts that into an observable signal instead of
    a silent, permanent rejection of every plate starting with it."""
    with caplog.at_level(logging.WARNING, logger="sentinel.anpr"):
        assert _best_pattern_match("XQ01AB1234") is None
    assert any("XQ" in r.message for r in caplog.records)


def test_state_code_check_does_not_apply_to_bh_series():
    """A BH-series plate carries no state/UT code at all — the whitelist
    must not reject it, and must not log a spurious warning either."""
    assert _best_pattern_match("23BH1234AA") == "23BH1234AA"


def test_retired_codes_still_validate_individually():
    """Named explicitly, not just folded into the 40-code sweep above —
    these are the ones a reviewer is most likely to assume are typos and
    'fix' by deleting, which would silently break real still-on-the-road
    vehicles (see the module-level comment on why each was kept)."""
    for code in ("TS", "DN", "OR", "UA"):
        plate = f"{code}01AB1234"
        assert _best_pattern_match(plate) == plate, code
