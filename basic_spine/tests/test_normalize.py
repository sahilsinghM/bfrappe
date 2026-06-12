"""Unit tests for the normalization utility, using real formats seen in BASIC data.

Runnable standalone (no Frappe needed):  pytest basic_spine/tests/test_normalize.py
"""

from basic_spine.spine.normalize import fingerprint, norm_id, norm_name, strip_invisibles


def test_strip_invisibles():
    assert strip_invisibles("300965132​") == "300965132"
    assert strip_invisibles("a‌b‍c﻿d e") == "abcde"
    assert strip_invisibles(None) == ""


def test_norm_id_zero_width_tail():
    # Corrupt real value: trailing zero-width space
    assert norm_id("300965132​") == "300965132"


def test_norm_id_backslashes():
    # Corrupt real value: backslashes inside the id
    assert norm_id("HR\\NCH\\GURH\\A000001734") == "HRNCHGURHA000001734"


def test_norm_id_au_l_prefix():
    # AU writes the same LAN with and without a leading L
    assert norm_id("L9001061756938322", strip_l_prefix=True) == "9001061756938322"
    assert norm_id("9001061756938322", strip_l_prefix=True) == "9001061756938322"
    # Without the flag the L stays
    assert norm_id("L9001061756938322") == "L9001061756938322"


def test_norm_id_au_hft_prefix():
    # AU app number arrives as HFT-1110241 in emails
    assert norm_id("HFT-1110241") == "1110241"


def test_norm_id_separators_and_case():
    assert norm_id(" lndellap-07250307436 ") == "LNDELLAP07250307436"
    assert norm_id("TC HHL 0453 0001 0041 5440") == "TCHHL0453000100415440"


def test_norm_id_real_formats_pass_through():
    # Clean ids from each lender must come through unchanged
    for clean in [
        "77212306101",  # ICICI
        "704335805",  # HDFC Sales
        "H400HHL1553453",  # Bajaj
        "TCHHL0453000100415440",  # Tata Capital
        "TCHHF0500000100436590",  # Tata Capital
        "3000142072",  # Aditya Birla
        "10409835",  # India Shelter
        "HE01GUF00000160637",  # Chola
    ]:
        assert norm_id(clean) == clean


def test_norm_id_none_and_numeric():
    assert norm_id(None) == ""
    assert norm_id(704335805) == "704335805"


def test_norm_name():
    assert norm_name("  Ramesh  KUMAR ") == "RAMESH KUMAR"
    assert norm_name("R.K. Sharma-Verma") == "RK SHARMAVERMA"
    assert norm_name("Sunita​ Devi") == "SUNITA DEVI"
    assert norm_name(None) == ""


def test_fingerprint_stable_and_normalized():
    a = fingerprint("L9001061756938322", "HFT-1110241", 2500000, "2026-04-15", "Ramesh Kumar")
    b = fingerprint("L9001061756938322", "HFT-1110241", 2500000, "2026-04-15", "ramesh   KUMAR")
    assert a == b  # name normalization folds case/spacing
    c = fingerprint("L9001061756938322", "HFT-1110241", 2500001, "2026-04-15", "Ramesh Kumar")
    assert a != c  # amount participates


def test_fingerprint_handles_blanks():
    # Real case: one MIS line arrived with no LAN at all
    fp = fingerprint(None, "HFT-1110241", None, None, "Ramesh Kumar")
    assert isinstance(fp, str) and len(fp) == 40
