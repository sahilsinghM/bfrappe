"""Unit tests for Commission Slab Excel parser — no Frappe needed.

pytest basic_spine/tests/test_make_slabs.py
"""

from basic_spine.spine.make_slabs import parse_slab_row, resolve_lender_entity


# ── parse_slab_row ────────────────────────────────────────────────────────────

def test_numeric_rate_parsed():
    row = {"Bank name": "Chola", "Product": "HL", "Bank Code": "10012282",
           "Top-Slab": 0.8, "Condition": "", "Central/Manual": "Central"}
    result = parse_slab_row(row, sheet="HL")
    assert result["top_rate"] == 0.8
    assert result["rate_formula"] == ""
    assert result["payout_type"] == "Net"
    assert result["processing_mode"] == "Central"
    assert result["basic_dsa_code"] == "10012282"


def test_formula_rate_stored_verbatim():
    row = {"Bank name": "HDFC Sales", "Product": "HL", "Bank Code": "HC001",
           "Top-Slab": "PF=Payout", "Condition": "if LTV < 70%", "Central/Manual": "Manual"}
    result = parse_slab_row(row, sheet="HL")
    assert result["top_rate"] is None
    assert result["rate_formula"] == "PF=Payout"
    assert result["condition"] == "if LTV < 70%"
    assert result["processing_mode"] == "Manual"


def test_gross_sheet_sets_payout_type():
    row = {"Bank name": "Piramal", "Product": "LAP", "Bank Code": "PIR01",
           "Top-Slab": 1.2, "Condition": "", "Central/Manual": "Central"}
    result = parse_slab_row(row, sheet="Gross")
    assert result["payout_type"] == "Gross"


def test_lap_sheet_sets_payout_type_net():
    row = {"Bank name": "AU SFB", "Product": "LAP", "Bank Code": "AVHL00327",
           "Top-Slab": 0.9, "Condition": "", "Central/Manual": "Central"}
    result = parse_slab_row(row, sheet="LAP")
    assert result["payout_type"] == "Net"


def test_blank_bank_name_returns_none():
    row = {"Bank name": "", "Product": "HL", "Bank Code": "",
           "Top-Slab": 0.5, "Condition": "", "Central/Manual": "Central"}
    assert parse_slab_row(row, sheet="HL") is None


# ── resolve_lender_entity ─────────────────────────────────────────────────────

def test_exact_match_returns_entity():
    known = {"Chola Home Loans": "Chola Home Loans",
             "AU Small Finance Bank": "AU Small Finance Bank"}
    aliases = {"Chola": "Chola Home Loans", "AU SFB": "AU Small Finance Bank"}
    assert resolve_lender_entity("Chola Home Loans", known, aliases) == "Chola Home Loans"


def test_alias_match_returns_entity():
    known = {"Chola Home Loans": "Chola Home Loans"}
    aliases = {"Chola": "Chola Home Loans"}
    assert resolve_lender_entity("Chola", known, aliases) == "Chola Home Loans"


def test_fuzzy_match_returns_entity():
    known = {"Chola Home Loans": "Chola Home Loans",
             "AU Small Finance Bank": "AU Small Finance Bank"}
    aliases = {}
    # "Cholamandalam" is close to "Chola Home Loans" — fuzzy should find it
    result = resolve_lender_entity("Cholamandalam Home Loans", known, aliases)
    assert result == "Chola Home Loans"


def test_very_distant_name_returns_none():
    known = {"Chola Home Loans": "Chola Home Loans"}
    aliases = {}
    assert resolve_lender_entity("XYZ Random Corp", known, aliases) is None
