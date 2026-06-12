"""Unit tests for MIS email routing — pure logic, no Frappe needed.

pytest basic_spine/tests/test_mis_routing.py
"""

from basic_spine.spine.mis_email_handler import resolve_mis_profile


def _profiles():
    return [
        {"profile_name": "Chola Monthly", "sender_email_domain": "@cholamandalam.com",
         "filename_pattern": r"CHOLA.*\.xlsx"},
        {"profile_name": "AU Monthly", "sender_email_domain": "@aubank.in",
         "filename_pattern": r"AU.*\.xlsx"},
        {"profile_name": "PNB HFC Monthly", "sender_email_domain": "",
         "filename_pattern": r"PNBHF.*\.(xlsx|xls)"},
    ]


def test_resolve_by_sender_domain():
    assert resolve_mis_profile("mis@cholamandalam.com", "report.xlsx", _profiles()) == "Chola Monthly"
    assert resolve_mis_profile("send@aubank.in", "data.xlsx", _profiles()) == "AU Monthly"


def test_domain_match_is_suffix_not_substring():
    # "notcholamandalam.com" should NOT match "@cholamandalam.com"
    assert resolve_mis_profile("mis@notcholamandalam.com", "report.xlsx", _profiles()) is None


def test_resolve_by_filename_when_domain_blank():
    assert resolve_mis_profile("ops@unknown.com", "PNBHF_Apr26.xlsx", _profiles()) == "PNB HFC Monthly"
    assert resolve_mis_profile("ops@unknown.com", "PNBHF_Apr26.xls", _profiles()) == "PNB HFC Monthly"


def test_domain_takes_precedence_over_filename():
    # Chola sender, but filename looks like AU — domain wins
    assert resolve_mis_profile("mis@cholamandalam.com", "AU_Apr26.xlsx", _profiles()) == "Chola Monthly"


def test_no_match_returns_none():
    assert resolve_mis_profile("ops@random.com", "mystery.xlsx", _profiles()) is None


def test_empty_profiles_returns_none():
    assert resolve_mis_profile("mis@cholamandalam.com", "report.xlsx", []) is None


def test_case_insensitive_filename_match():
    assert resolve_mis_profile("ops@unknown.com", "chola_apr26.xlsx", _profiles()) == "Chola Monthly"
