"""Commission invoice generation — one ERPNext Sales Invoice per MIS Batch.

Pure line assembly is in build_invoice_lines() (testable standalone).
generate_invoice() wires it to Frappe DocTypes.
"""

def build_invoice_lines(mis_lines: list[dict]) -> list[dict]:
    """Convert MIS Line dicts to ERPNext Sales Invoice item rows.

    Each MIS Line becomes one item line:
      - rate  = payin_amt  (source of truth)
      - qty   = 1
      - description = LAN + customer name

    Matching status is deliberately NOT consulted here — invoicing runs
    from payin_amt irrespective of the matching waterfall.
    """
    lines = []
    for ml in mis_lines:
        lan = (ml.get("lan") or "").strip()
        name = (ml.get("customer_name") or "").strip()
        description = lan
        if name:
            description = f"{lan} — {name}" if lan else name
        lines.append({
            "item_name": lan or "Commission",
            "description": description,
            "qty": 1,
            "rate": float(ml.get("payin_amt") or 0),
            "uom": "Nos",
        })
    return lines


def _get_or_create_gst_template() -> str:
    import frappe
    name = "GST 18%"

    if not frappe.db.exists("Item Tax Template", name):
        frappe.get_doc({
            "doctype": "Item Tax Template",
            "title": name,
            "taxes": [{"tax_type": "Output Tax 18%", "tax_rate": 18}],
        }).insert(ignore_permissions=True)
    return name


def generate_invoice(mis_batch_name: str) -> str:
    import frappe
    """Create a Draft Sales Invoice for the given MIS Batch.

    Returns the new Sales Invoice name.
    Raises frappe.ValidationError if the batch already has an invoice.
    """
    batch = frappe.get_doc("MIS Batch", mis_batch_name)
    if batch.invoice:
        frappe.throw(
            f"MIS Batch {mis_batch_name} already has invoice {batch.invoice}. "
            "To regenerate, cancel and delete the existing invoice first."
        )

    entity = frappe.get_doc("Lender Entity", batch.lender_entity)
    if not entity.erp_customer:
        frappe.throw(
            f"Lender Entity '{batch.lender_entity}' has no linked ERPNext Customer. "
            "Run 'Sync as Customer' on the Lender Entity form first."
        )

    mis_lines = frappe.get_all(
        "MIS Line",
        filters={"mis_batch": mis_batch_name},
        fields=["lan", "customer_name", "disb_amt", "payin_amt", "product"],
    )

    gst_template = _get_or_create_gst_template()
    raw_lines = build_invoice_lines(mis_lines)

    items = [
        {**line, "item_tax_template": gst_template}
        for line in raw_lines
    ]

    inv = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": entity.erp_customer,
        "posting_date": frappe.utils.today(),
        "items": items,
        "custom_mis_batch": mis_batch_name,
    }).insert()

    frappe.db.set_value("MIS Batch", mis_batch_name, "invoice", inv.name)
    frappe.db.commit()
    return inv.name
