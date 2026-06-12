import frappe
from frappe.model.document import Document


class LenderEntity(Document):

    @frappe.whitelist()
    def sync_as_customer(self):
        """Create or update an ERPNext Customer for this Lender Entity."""
        _ensure_lender_customer_group()

        if self.erp_customer and frappe.db.exists("Customer", self.erp_customer):
            cust = frappe.get_doc("Customer", self.erp_customer)
            cust.customer_name = self.entity_name
            cust.save()
        else:
            cust = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": self.entity_name,
                "customer_group": "Lender",
                "territory": "India",
                "customer_type": "Company",
            }).insert()
            frappe.db.set_value("Lender Entity", self.name, "erp_customer", cust.name)

        if self.billing_address or self.gstin:
            _upsert_address(cust.name, self.billing_address, self.gstin)

        frappe.db.commit()
        frappe.msgprint(
            f"Synced as Customer: {cust.name}",
            title="Customer synced",
        )


def _ensure_lender_customer_group():
    if not frappe.db.exists("Customer Group", "Lender"):
        frappe.get_doc({
            "doctype": "Customer Group",
            "customer_group_name": "Lender",
            "parent_customer_group": "All Customer Groups",
        }).insert(ignore_permissions=True)


def _upsert_address(customer_name: str, address_text: str, gstin: str):
    existing = frappe.db.get_value(
        "Dynamic Link",
        {"link_doctype": "Customer", "link_name": customer_name,
         "parenttype": "Address"},
        "parent",
    )
    if existing:
        addr = frappe.get_doc("Address", existing)
    else:
        addr = frappe.new_doc("Address")
        addr.address_title = customer_name
        addr.address_type = "Billing"
        addr.append("links", {"link_doctype": "Customer", "link_name": customer_name})

    if address_text:
        lines = [l.strip() for l in address_text.strip().splitlines() if l.strip()]
        addr.address_line1 = lines[0] if lines else ""
        addr.address_line2 = lines[1] if len(lines) > 1 else ""
    if gstin:
        addr.gstin = gstin

    addr.save(ignore_permissions=True)
