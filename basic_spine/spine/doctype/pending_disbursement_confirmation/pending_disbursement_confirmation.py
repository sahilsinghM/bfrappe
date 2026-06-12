import frappe
from frappe.model.document import Document


class PendingDisbursementConfirmation(Document):

    @frappe.whitelist()
    def link_and_confirm(self):
        if not self.linked_disbursement:
            frappe.throw("Select a Reported Disbursement to link to.")
        frappe.db.set_value("Reported Disbursement", self.linked_disbursement, {
            "confirmed_on": frappe.utils.today(),
            "confirmation_source": "Email",
        })
        self.status = "Linked"
        self.save()
        frappe.msgprint(
            f"Linked and confirmed Reported Disbursement {self.linked_disbursement}.",
            title="Confirmed",
        )
