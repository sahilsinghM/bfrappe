import frappe
from frappe.model.document import Document


class PendingMISClassification(Document):

    @frappe.whitelist()
    def classify_and_import(self):
        if not self.assigned_profile:
            frappe.throw("Select a Lender MIS Profile before importing.")
        from basic_spine.spine.imports import import_mis
        site_path = frappe.get_site_path("public", self.attachment.lstrip("/"))
        result = import_mis(
            path=site_path,
            profile=self.assigned_profile,
            received_on=frappe.utils.today(),
        )
        self.status = "Classified"
        self.save()
        frappe.msgprint(
            f"MIS Batch {result['batch']} created — {result['imported']} rows imported.",
            title="Import complete",
        )
