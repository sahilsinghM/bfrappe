"""Unit tests for Axis Bank CSV statement parser — no Frappe needed.

pytest basic_spine/tests/test_bank_statement_parser.py
"""

import textwrap
from basic_spine.spine.bank_statement_parser import parse_axis_csv, idempotency_key


SAMPLE_CSV = textwrap.dedent("""\
    Axis Bank Account Statement
    Account Number,1234567890
    ,,,,,
    Tran Date,CHQNO,PARTICULARS,DR,CR,BAL
    18-06-2026,NEFT123456,CHOLA HOME LOAN COMMISSION APR,,125000.00,5125000.00
    18-06-2026,,BANK CHARGES - NEFT,50.00,,5124950.00
    19-06-2026,RTGS789012,AU SFB PAYOUT MAY,,87500.50,5212450.50
    19-06-2026,,SELF TRANSFER,,0.00,5212450.50
""")


def test_parse_returns_credit_and_debit_lines():
    rows = parse_axis_csv(SAMPLE_CSV)
    assert len(rows) == 4


def test_credit_line_fields():
    rows = parse_axis_csv(SAMPLE_CSV)
    chola = rows[0]
    assert chola["txn_date"] == "2026-06-18"
    assert chola["cheque_ref"] == "NEFT123456"
    assert chola["narration"] == "CHOLA HOME LOAN COMMISSION APR"
    assert chola["credit"] == 125000.00
    assert chola["debit"] == 0.0
    assert chola["balance"] == 5125000.00


def test_debit_line_fields():
    rows = parse_axis_csv(SAMPLE_CSV)
    charge = rows[1]
    assert charge["debit"] == 50.0
    assert charge["credit"] == 0.0
    assert charge["cheque_ref"] == ""


def test_zero_cr_and_zero_dr_included():
    rows = parse_axis_csv(SAMPLE_CSV)
    # "SELF TRANSFER" line has CR=0 — still a line in statement
    self_transfer = rows[3]
    assert self_transfer["narration"] == "SELF TRANSFER"
    assert self_transfer["credit"] == 0.0


def test_header_rows_skipped():
    rows = parse_axis_csv(SAMPLE_CSV)
    # None of the metadata rows ("Axis Bank", "Account Number") should appear
    narrations = [r["narration"] for r in rows]
    assert not any("Axis Bank" in n or "Account Number" in n for n in narrations)


def test_idempotency_key_uniqueness():
    rows = parse_axis_csv(SAMPLE_CSV)
    keys = [idempotency_key(r) for r in rows]
    assert len(keys) == len(set(keys))


def test_idempotency_key_stable():
    rows = parse_axis_csv(SAMPLE_CSV)
    k1 = idempotency_key(rows[0])
    k2 = idempotency_key(rows[0])
    assert k1 == k2


def test_empty_csv_returns_empty_list():
    assert parse_axis_csv("") == []


def test_partial_csv_no_data_rows():
    header_only = "Axis Bank Account Statement\nAccount Number,1234\n,,,,,\nTran Date,CHQNO,PARTICULARS,DR,CR,BAL\n"
    assert parse_axis_csv(header_only) == []
