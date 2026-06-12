"""Payment auto-matching: reconcile Axis Bank credits against commission invoices.

Pure matching algorithm is in find_matches() — testable without Frappe.
run_auto_match() wires it to Frappe DocTypes and creates Payment Entries.
"""

from dataclasses import dataclass, field

from basic_spine.spine.normalize import norm_name


_AMOUNT_TOLERANCE = 1.0  # rupees


@dataclass
class MatchResult:
    bank_line: str
    match_type: str          # "confident" | "ambiguous" | "no_match"
    invoice: str | None = None
    match_note: str = ""


def _amounts_close(a: float, b: float) -> bool:
    return abs(a - b) <= _AMOUNT_TOLERANCE


def _narration_matches_customer(narration: str, customer: str) -> bool:
    """Loose check: normalized customer name words appear in normalized narration."""
    if not narration or not customer:
        return True  # no evidence to reject
    norm_narration = norm_name(narration)
    for word in norm_name(customer).split():
        if len(word) >= 4 and word in norm_narration:
            return True
    return False


def find_matches(
    bank_lines: list[dict],
    open_invoices: list[dict],
) -> list[MatchResult]:
    """Match unmatched credit bank lines against open invoices.

    Returns one MatchResult per processable line (already-matched and zero-credit
    lines are silently skipped — caller can check len(results) vs len(bank_lines)).
    """
    results = []

    for line in bank_lines:
        if line.get("match_status") != "Unmatched":
            continue
        credit = float(line.get("credit") or 0)
        if credit <= 0:
            continue

        amount_candidates = [
            inv for inv in open_invoices
            if _amounts_close(float(inv.get("outstanding_amount") or 0), credit)
        ]

        if not amount_candidates:
            results.append(MatchResult(
                bank_line=line["name"],
                match_type="no_match",
            ))
            continue

        if len(amount_candidates) > 1:
            names = ", ".join(inv["name"] for inv in amount_candidates)
            results.append(MatchResult(
                bank_line=line["name"],
                match_type="ambiguous",
                match_note=f"Amount ₹{credit:,.2f} matches {len(amount_candidates)} invoices: {names}",
            ))
            continue

        # Exactly one amount match — verify narration as a soft confirmation
        candidate = amount_candidates[0]
        if _narration_matches_customer(line.get("narration", ""), candidate.get("customer", "")):
            results.append(MatchResult(
                bank_line=line["name"],
                match_type="confident",
                invoice=candidate["name"],
            ))
        else:
            results.append(MatchResult(
                bank_line=line["name"],
                match_type="ambiguous",
                match_note=(
                    f"Amount matches {candidate['name']} but narration "
                    f"'{line.get('narration', '')}' doesn't mention customer "
                    f"'{candidate.get('customer', '')}'"
                ),
            ))

    return results


def _create_payment_entry(bank_line_doc, invoice_doc) -> str:
    import frappe
    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": invoice_doc.customer,
        "paid_amount": bank_line_doc.credit,
        "received_amount": bank_line_doc.credit,
        "paid_to": frappe.db.get_single_value("Company", "default_bank_account") or "",
        "reference_no": bank_line_doc.cheque_ref or bank_line_doc.name,
        "reference_date": bank_line_doc.txn_date,
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice_doc.name,
            "allocated_amount": bank_line_doc.credit,
        }],
    }).insert()
    pe.submit()
    return pe.name


def run_auto_match() -> dict:
    import frappe
    """Process all Unmatched Bank Statement Lines and match them to open invoices.

    Returns summary: {"confident": int, "ambiguous": int, "no_match": int}.
    """
    bank_lines = frappe.get_all(
        "Bank Statement Line",
        filters={"match_status": "Unmatched"},
        fields=["name", "txn_date", "credit", "narration", "cheque_ref", "match_status"],
    )
    open_invoices = frappe.get_all(
        "Sales Invoice",
        filters={"docstatus": 1, "outstanding_amount": [">", 0]},
        fields=["name", "outstanding_amount", "customer"],
    )

    results = find_matches(bank_lines, open_invoices)
    counts = {"confident": 0, "ambiguous": 0, "no_match": 0}

    for result in results:
        counts[result.match_type] += 1
        if result.match_type == "confident":
            inv_doc = frappe.get_doc("Sales Invoice", result.invoice)
            line_doc = frappe.get_doc("Bank Statement Line", result.bank_line)
            pe_name = _create_payment_entry(line_doc, inv_doc)
            frappe.db.set_value("Bank Statement Line", result.bank_line, {
                "match_status": "Auto-Matched",
                "matched_invoice": result.invoice,
                "matched_payment_entry": pe_name,
            })
        elif result.match_type == "ambiguous":
            frappe.db.set_value("Bank Statement Line", result.bank_line, {
                "match_note": result.match_note,
            })

    frappe.db.commit()
    return counts
