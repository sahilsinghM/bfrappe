"""Axis Bank CSV statement parser.

Pure parsing logic is in parse_axis_csv() + idempotency_key(), both testable
without Frappe. import_statement() wires them to Frappe DocTypes.
"""

import csv
import io
import hashlib
from datetime import datetime

def _parse_amount(value: str) -> float:
    cleaned = (value or "").replace(",", "").strip()
    return float(cleaned) if cleaned else 0.0


def _parse_date(value: str) -> str:
    """Convert DD-MM-YYYY to YYYY-MM-DD (Frappe canonical)."""
    value = (value or "").strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return value


def parse_axis_csv(content: str) -> list[dict]:
    """Parse Axis Bank account statement CSV text into a list of row dicts.

    Skips metadata header rows; stops at the data header row
    (identified by 'Tran Date' in the first column).
    Returns all transaction rows regardless of CR/DR amount.
    """
    reader = csv.reader(io.StringIO(content))
    data_started = False
    rows = []

    for raw in reader:
        if not any(c.strip() for c in raw):
            continue

        # Detect the column header row
        if not data_started:
            if raw and raw[0].strip().upper() == "TRAN DATE":
                data_started = True
            continue

        if len(raw) < 6:
            continue

        txn_date_raw, cheque_ref, narration, dr_raw, cr_raw, bal_raw = (
            raw[0].strip(), raw[1].strip(), raw[2].strip(),
            raw[3].strip(), raw[4].strip(), raw[5].strip()
        )

        if not txn_date_raw:
            continue

        rows.append({
            "txn_date": _parse_date(txn_date_raw),
            "value_date": _parse_date(txn_date_raw),
            "cheque_ref": cheque_ref,
            "narration": narration,
            "debit": _parse_amount(dr_raw),
            "credit": _parse_amount(cr_raw),
            "balance": _parse_amount(bal_raw),
        })

    return rows


def idempotency_key(row: dict) -> str:
    """Stable hash for deduplication: cheque_ref + txn_date + credit."""
    raw = f"{row.get('cheque_ref', '')}|{row.get('txn_date', '')}|{row.get('credit', 0)}"
    return hashlib.sha1(raw.encode()).hexdigest()


def import_statement(path: str, source: str = "Manual Upload") -> dict:
    """Parse a CSV file and persist Bank Statement + Bank Statement Line records.

    Idempotent: skips lines whose idempotency_key already exists.
    Returns a summary dict: {"statement": name, "created": int, "skipped": int}.
    """
    import frappe
    with open(path, encoding="utf-8-sig") as fh:
        content = fh.read()

    rows = parse_axis_csv(content)
    if not rows:
        frappe.throw("No transaction rows found in the uploaded file.")

    # Infer statement date from the first data row
    stmt_date = rows[0]["txn_date"] if rows else frappe.utils.today()

    stmt = frappe.get_doc({
        "doctype": "Bank Statement",
        "statement_date": stmt_date,
        "bank": "Axis Bank",
        "line_count": len(rows),
        "source": source,
    }).insert()

    created = skipped = 0
    existing_keys = set(
        frappe.get_all("Bank Statement Line", pluck="idempotency_key")
    )

    for row in rows:
        key = idempotency_key(row)
        if key in existing_keys:
            skipped += 1
            continue
        frappe.get_doc({
            "doctype": "Bank Statement Line",
            "bank_statement": stmt.name,
            "idempotency_key": key,
            "match_status": "Unmatched",
            **row,
        }).insert()
        created += 1

    frappe.db.commit()

    from basic_spine.spine.payment_matcher import run_auto_match
    run_auto_match()

    return {"statement": stmt.name, "created": created, "skipped": skipped}
