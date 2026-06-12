"""Disbursement confirmation email handler for disbursement@basichomeloan.com.

Parses semi-structured bank confirmation emails and links them to
Reported Disbursement records via norm_id() matching.
"""

import re
from basic_spine.spine.normalize import norm_id


# Common field extractors for PNB-style confirmation emails
_LAN_RE = re.compile(
    r"(?:Loan\s+Account\s+(?:No|Number|#)|LAN)[:\s]+([A-Z0-9/\-]+)",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(
    r"(?:Amount\s+Disbursed|Disbursed\s+Amount|Amount)[:\s]+(?:Rs\.?\s*)?([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"(?:Disbursement\s+Date|Date\s+of\s+Disbursement)[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    re.IGNORECASE,
)


def _extract_lan(body: str) -> str | None:
    m = _LAN_RE.search(body)
    return m.group(1).strip() if m else None


def _extract_amount(body: str) -> float | None:
    m = _AMOUNT_RE.search(body)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _extract_date(body: str) -> str | None:
    from datetime import datetime
    m = _DATE_RE.search(body)
    if not m:
        return None
    raw = m.group(1)
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw


def process_disbursement_email(communication_name: str) -> None:
    """Hook called on incoming Communication to disbursement@ account."""
    import frappe
    comm = frappe.get_doc("Communication", communication_name)
    if comm.sent_or_received != "Received":
        return

    body = comm.content or ""
    extracted_lan = _extract_lan(body)
    extracted_amount = _extract_amount(body)
    extracted_date = _extract_date(body)

    matched_name = None
    if extracted_lan:
        norm = norm_id(extracted_lan)
        matched_name = frappe.db.get_value(
            "Reported Disbursement",
            {"norm_lan": norm},
            "name",
        )

    if matched_name:
        # Check idempotency — don't double-confirm
        already_confirmed = frappe.db.get_value(
            "Reported Disbursement", matched_name, "confirmed_on"
        )
        if not already_confirmed:
            frappe.db.set_value("Reported Disbursement", matched_name, {
                "confirmed_on": frappe.utils.today(),
                "confirmation_source": "Email",
            })
            frappe.db.commit()
    else:
        frappe.get_doc({
            "doctype": "Pending Disbursement Confirmation",
            "received_on": frappe.utils.now(),
            "from_email": comm.sender,
            "subject": comm.subject,
            "raw_body": body[:2000],
            "extracted_lan": extracted_lan or "",
            "extracted_amount": extracted_amount,
            "extracted_date": extracted_date,
            "status": "Pending",
        }).insert(ignore_permissions=True)
        frappe.db.commit()
