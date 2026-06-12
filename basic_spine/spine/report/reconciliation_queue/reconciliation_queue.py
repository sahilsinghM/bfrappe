"""Reconciliation Queue — lists unmatched Bank Statement credit lines.

The accounts team uses this to manually match bank credits to commission invoices.
Each row has an action button (rendered by the JS companion) to open the
Reconcile Payment dialog.
"""

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}

    conditions = ["bsl.match_status = 'Unmatched'", "bsl.credit > 0"]

    if filters.get("from_date"):
        conditions.append(f"bsl.txn_date >= '{filters['from_date']}'")
    if filters.get("to_date"):
        conditions.append(f"bsl.txn_date <= '{filters['to_date']}'")
    if filters.get("min_amount"):
        conditions.append(f"bsl.credit >= {frappe.db.escape(str(filters['min_amount']))}")

    where = " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            bsl.name,
            bsl.txn_date,
            bsl.credit,
            bsl.narration,
            bsl.cheque_ref,
            bsl.match_note,
            bs.bank,
            bs.statement_date
        FROM `tabBank Statement Line` bsl
        LEFT JOIN `tabBank Statement` bs ON bs.name = bsl.bank_statement
        WHERE {where}
        ORDER BY bsl.txn_date DESC, bsl.credit DESC
        """,
        as_dict=True,
    )

    columns = [
        {"label": _("Date"), "fieldname": "txn_date", "fieldtype": "Date", "width": 100},
        {"label": _("Credit (₹)"), "fieldname": "credit", "fieldtype": "Currency", "width": 130},
        {"label": _("Narration"), "fieldname": "narration", "fieldtype": "Data", "width": 280},
        {"label": _("Cheque/Ref"), "fieldname": "cheque_ref", "fieldtype": "Data", "width": 130},
        {"label": _("Why not auto-matched"), "fieldname": "match_note",
         "fieldtype": "Small Text", "width": 220},
        {"label": _("Bank"), "fieldname": "bank", "fieldtype": "Data", "width": 100},
        {"label": _("Statement"), "fieldname": "statement_date", "fieldtype": "Date", "width": 100},
        {"label": _("Line"), "fieldname": "name", "fieldtype": "Link",
         "options": "Bank Statement Line", "width": 120},
    ]

    return columns, data


def get_filters():
    return [
        {
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
        },
        {
            "fieldname": "min_amount",
            "label": "Min Amount (₹)",
            "fieldtype": "Currency",
        },
    ]
