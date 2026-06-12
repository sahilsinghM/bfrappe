"""Unit tests for the payment matching algorithm — no Frappe needed.

pytest basic_spine/tests/test_payment_matcher.py
"""

from basic_spine.spine.payment_matcher import find_matches, MatchResult


def _line(credit, narration="", cheque_ref="", txn_date="2026-06-18"):
    return {
        "name": f"BSL-{txn_date}-{credit}",
        "txn_date": txn_date,
        "credit": credit,
        "narration": narration,
        "cheque_ref": cheque_ref,
        "match_status": "Unmatched",
    }


def _invoice(outstanding, customer="Chola Home Loans", name="SINV-0001"):
    return {"name": name, "outstanding_amount": outstanding, "customer": customer}


# ── Confident matches ────────────────────────────────────────────────────────

def test_exact_amount_and_narration_match():
    lines = [_line(125000.0, "CHOLA HOME LOAN COMMISSION APR")]
    invoices = [_invoice(125000.0, "Chola Home Loans", "SINV-0001")]
    results = find_matches(lines, invoices)
    assert len(results) == 1
    assert results[0].match_type == "confident"
    assert results[0].invoice == "SINV-0001"


def test_amount_within_one_rupee_tolerance():
    lines = [_line(124999.50, "CHOLA HOME LOAN")]
    invoices = [_invoice(125000.0, "Chola Home Loans")]
    results = find_matches(lines, invoices)
    assert results[0].match_type == "confident"


def test_amount_outside_tolerance_no_match():
    lines = [_line(124900.0, "CHOLA HOME LOAN")]
    invoices = [_invoice(125000.0, "Chola Home Loans")]
    results = find_matches(lines, invoices)
    assert results[0].match_type == "no_match"


# ── Ambiguous matches ────────────────────────────────────────────────────────

def test_two_invoices_same_amount_is_ambiguous():
    lines = [_line(125000.0, "PAYMENT RECEIVED")]
    invoices = [
        _invoice(125000.0, "Chola Home Loans", "SINV-0001"),
        _invoice(125000.0, "AU Small Finance Bank", "SINV-0002"),
    ]
    results = find_matches(lines, invoices)
    assert results[0].match_type == "ambiguous"
    assert results[0].invoice is None


def test_ambiguous_has_note():
    lines = [_line(125000.0)]
    invoices = [
        _invoice(125000.0, name="SINV-0001"),
        _invoice(125000.0, name="SINV-0002"),
    ]
    results = find_matches(lines, invoices)
    assert results[0].match_note  # non-empty


# ── No match ─────────────────────────────────────────────────────────────────

def test_no_invoice_matches_amount():
    lines = [_line(99999.0)]
    invoices = [_invoice(125000.0)]
    results = find_matches(lines, invoices)
    assert results[0].match_type == "no_match"
    assert results[0].invoice is None


def test_empty_invoices_no_match():
    lines = [_line(125000.0)]
    results = find_matches(lines, [])
    assert results[0].match_type == "no_match"


# ── Idempotency ───────────────────────────────────────────────────────────────

def test_already_matched_line_skipped():
    lines = [
        {**_line(125000.0), "match_status": "Auto-Matched"},
    ]
    invoices = [_invoice(125000.0)]
    results = find_matches(lines, invoices)
    assert results == []


def test_zero_credit_line_skipped():
    lines = [_line(0.0, "BANK CHARGES")]
    invoices = [_invoice(0.0)]
    results = find_matches(lines, invoices)
    assert results == []
