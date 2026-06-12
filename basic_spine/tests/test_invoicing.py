"""Unit tests for commission invoice line assembly — no Frappe needed.

pytest basic_spine/tests/test_invoicing.py
"""

from basic_spine.spine.invoicing import build_invoice_lines


MIS_LINES = [
    {"lan": "HE01GUF00000160637", "customer_name": "Ramesh Kumar",
     "disb_amt": 2500000.0, "payin_amt": 25000.0, "product": "LAP"},
    {"lan": "HE01GUF00000160638", "customer_name": "Sunita Devi",
     "disb_amt": 1800000.0, "payin_amt": 18000.0, "product": "HL"},
    {"lan": "HE01GUF00000160639", "customer_name": "Ajay Singh",
     "disb_amt": 3000000.0, "payin_amt": 0.0, "product": "LAP"},  # zero payout
]


def test_one_line_per_mis_line():
    lines = build_invoice_lines(MIS_LINES)
    assert len(lines) == 3


def test_rate_equals_payin_amt():
    lines = build_invoice_lines(MIS_LINES)
    assert lines[0]["rate"] == 25000.0
    assert lines[1]["rate"] == 18000.0


def test_qty_is_always_one():
    lines = build_invoice_lines(MIS_LINES)
    assert all(l["qty"] == 1 for l in lines)


def test_item_description_contains_lan():
    lines = build_invoice_lines(MIS_LINES)
    assert "HE01GUF00000160637" in lines[0]["description"]


def test_zero_payin_included_not_dropped():
    lines = build_invoice_lines(MIS_LINES)
    assert lines[2]["rate"] == 0.0


def test_total_amount():
    lines = build_invoice_lines(MIS_LINES)
    assert sum(l["rate"] * l["qty"] for l in lines) == 43000.0


def test_empty_mis_lines_returns_empty():
    assert build_invoice_lines([]) == []
