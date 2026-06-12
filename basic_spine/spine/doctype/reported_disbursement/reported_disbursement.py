# Copyright (c) 2026, BASIC Home Loan
# For license information, please see license.txt

import re

from frappe.model.document import Document

from basic_spine.spine.normalize import norm_id

# Console disb ids look like B00UMFG_D3: case id + tranche suffix
TRANCHE_RE = re.compile(r"^(?P<case>.+?)[_\s]D(?P<n>\d+)$", re.IGNORECASE)


class ReportedDisbursement(Document):
    def validate(self):
        self.derive_case_and_tranche()
        self.lender_app_id_norm = norm_id(self.lender_app_id_raw)
        self.lan_norm = norm_id(self.lan_raw)
        self.apply_default_collection_state()
        if not self.sla_trigger_date:
            self.sla_trigger_date = self.disb_date

    def derive_case_and_tranche(self):
        disb_id = (self.disb_id or "").strip()
        m = TRANCHE_RE.match(disb_id)
        if m:
            self.basic_case_id = m.group("case")
            self.tranche_no = int(m.group("n"))
        else:
            self.basic_case_id = disb_id
            self.tranche_no = 1

    def apply_default_collection_state(self):
        # Default Verified if the console already verified it, else Reported.
        # Only upgrade from the initial state; never touch Matched/Overdue/etc.
        if self.collection_state in (None, "", "Reported") and self.console_status == "VerifiedByBasic":
            self.collection_state = "Verified"
