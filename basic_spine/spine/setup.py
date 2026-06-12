"""Seed masters with REAL labels from BASIC's reported export.

bench --site <site> execute basic_spine.spine.setup.seed

Idempotent: re-running updates nothing that exists.
"""

import frappe

PRODUCTS = [
    ("HL", "Home Loan"),
    ("LAP", "Loan Against Property"),
    ("BT", "Balance Transfer"),
    ("TOPUP", "Top-up Loan"),
    ("AFFORDABLE", "Affordable Housing"),
    ("SENP", "Self-Employed Non-Professional"),
]

# raw_label -> (lender, entity, entity_type)
# ICICI appears as both "ICICI Bank" and "ICICI Home Finance" — two entities under
# one lender; TATA likewise. This is exactly why Lender -> Entity is two levels.
ALIASES = {
    "HDFC Sales": ("HDFC", "HDFC Sales", "Vertical"),
    "HDFC Bank": ("HDFC", "HDFC Bank", "Bank"),
    "ICICI Bank": ("ICICI", "ICICI Bank", "Bank"),
    "ICICI Home Finance": ("ICICI", "ICICI Home Finance", "HFC"),
    "ISFC (India Shelter)": ("India Shelter", "India Shelter Finance", "HFC"),
    "Bajaj Housing Finance": ("Bajaj", "Bajaj Housing Finance", "HFC"),
    "Homfinity": ("Homfinity", "Homfinity", "NBFC"),
    "Tata Capital Finance": ("TATA", "Tata Capital", "NBFC"),
    "TATA Housing": ("TATA", "Tata Housing Finance", "HFC"),
    "Aditya Birla Housing Finance": ("Aditya Birla", "Aditya Birla Housing Finance", "HFC"),
    "Canara Bank": ("Canara", "Canara Bank", "Bank"),
    "Shubham Housing Finance": ("Shubham", "Shubham Housing Finance", "HFC"),
    "SBI-MB": ("SBI", "SBI Mortgage Business", "Bank"),
    "Hinduja Housing Finance(BFPL)": ("Hinduja", "Hinduja Housing Finance", "HFC"),
    "PNB Housing Finance": ("PNB", "PNB Housing Finance", "HFC"),
    "Shriram HSG": ("Shriram", "Shriram Housing Finance", "HFC"),
    "Aadhar Housing Finance": ("Aadhar", "Aadhar Housing Finance", "HFC"),
    "Piramal": ("Piramal", "Piramal Finance", "NBFC"),
    # Pilot lenders whose MIS formats are in hand
    "Chola": ("Cholamandalam", "Chola Home Loans", "NBFC"),
    "AU SFB": ("AU", "AU Small Finance Bank", "Bank"),
}

LAN_PATTERNS = [
    ("Chola Home Loans", "LAN", r"^[A-Z]{2}\d{2}[A-Z]{3}\d{11}$",
     "e.g. HE01GUF00000160637: product HE01, branch GUF, serial"),
    ("AU Small Finance Bank", "LAN", r"^\d{16}$",
     "strip leading L; HFT- prefix on app no"),
    ("Tata Capital", "AppId", r"^TCHH[LF]\d{16,18}$",
     "embeds HHL/HHF product code"),
]

PRODUCT_MAPS = [
    ("Chola Home Loans", "HE01", "LAP"),
    ("Chola Home Loans", "HL01", "HL"),
    ("AU Small Finance Bank", "HL", "HL"),
    ("AU Small Finance Bank", "LAP", "LAP"),
]

# (profile_name, entity, cycle, start, end, delivery, grace, data_sheet, column_map)
MIS_PROFILES = [
    ("Chola Monthly", "Chola Home Loans", "Monthly-Window", 15, 15, 20, 5, "MISReportLines", [
        ("Loan Account No", "LAN", "StripZeroWidth"),
        ("Application No", "AppId", "None"),
        ("Customer Name", "CustomerName", "None"),
        ("Product", "ProductLabel", "UpperTrim"),
        ("Branch Name", "Branch", "None"),
        ("State", "State", "None"),
        ("Sanction Amount", "SanctionAmt", "None"),
        ("Disbursal Amount", "DisbAmt", "None"),
        ("Disbursal Date", "DisbDate", "None"),
        ("Payout Amount", "PayinAmt", "None"),
        ("Payout %", "SlabPct", "None"),
        ("Remarks", "Ignore", "None"),
    ]),
    ("AU Monthly", "AU Small Finance Bank", "Monthly-Window", 15, 15, 18, 5, None, [
        ("LAN", "LAN", "StripLPrefix"),
        ("APPL NO", "AppId", "None"),
        ("CUSTOMER NAME", "CustomerName", "UpperTrim"),
        ("PRODUCT", "ProductLabel", "UpperTrim"),
        ("BRANCH", "Branch", "None"),
        ("DISB AMT", "DisbAmt", "None"),
        ("DISB DATE", "DisbDate", "None"),
        ("NET PAYOUT", "PayinAmt", "None"),
    ]),
    # Cycle-only profiles (no file format yet) so aging covers the big lenders too
    ("HDFC Sales Monthly", "HDFC Sales", "Monthly-Window", 1, 1, 15, 5, None, []),
    ("ICICI Bank Monthly", "ICICI Bank", "Monthly-Window", 1, 1, 12, 5, None, []),
    ("Tata Capital Monthly", "Tata Capital", "Monthly-Window", 15, 15, 22, 5, None, []),
    ("Aditya Birla Monthly", "Aditya Birla Housing Finance", "Monthly-Window", 1, 1, 18, 5, None, []),
]

BRANCHES = [
    # (entity, branch_name, city, state, basic_dsa_code)
    ("Chola Home Loans", "Chola Central", "Chennai", "Tamil Nadu", "10012282"),
    ("AU Small Finance Bank", "AU Central", "Jaipur", "Rajasthan", "AVHL00327"),
]

MIS_PROFILE_ROUTING = [
    # (profile_name, sender_email_domain, filename_pattern)
    ("Chola Monthly", "@cholamandalam.com", r"CHOLA.*\.xlsx"),
    ("AU Monthly", "@aubank.in", r"AU.*\.xlsx"),
]

CONFIRMATION_PROFILES = [
    ("Chola Home Loans", "Disbursement", "Disbursement memo"),
    ("AU Small Finance Bank", "PDD+OTC-Clear", "PDD + OTC clearance from branch"),
]


def seed():
    created = {"Product": 0, "Lender": 0, "Lender Entity": 0, "Lender Alias": 0,
               "LAN Pattern": 0, "Lender Product Map": 0, "Lender MIS Profile": 0,
               "Lender Confirmation Profile": 0, "Lender Branch": 0}

    for code, desc in PRODUCTS:
        if not frappe.db.exists("Product", code):
            frappe.get_doc({"doctype": "Product", "product_code": code, "description": desc}).insert()
            created["Product"] += 1

    for raw_label, (lender, entity, etype) in ALIASES.items():
        if not frappe.db.exists("Lender", lender):
            frappe.get_doc({"doctype": "Lender", "lender_name": lender}).insert()
            created["Lender"] += 1
        if not frappe.db.exists("Lender Entity", entity):
            frappe.get_doc({"doctype": "Lender Entity", "entity_name": entity,
                            "lender": lender, "entity_type": etype}).insert()
            created["Lender Entity"] += 1
        if not frappe.db.exists("Lender Alias", raw_label):
            frappe.get_doc({"doctype": "Lender Alias", "raw_label": raw_label,
                            "lender_entity": entity}).insert()
            created["Lender Alias"] += 1

    for entity, kind, regex, notes in LAN_PATTERNS:
        if not frappe.db.exists("LAN Pattern", {"lender_entity": entity, "id_kind": kind}):
            frappe.get_doc({"doctype": "LAN Pattern", "lender_entity": entity,
                            "id_kind": kind, "regex": regex, "notes": notes}).insert()
            created["LAN Pattern"] += 1

    for entity, label, product in PRODUCT_MAPS:
        if not frappe.db.exists("Lender Product Map",
                                {"lender_entity": entity, "lender_product_label": label}):
            frappe.get_doc({"doctype": "Lender Product Map", "lender_entity": entity,
                            "lender_product_label": label, "basic_product": product}).insert()
            created["Lender Product Map"] += 1

    for name, entity, cycle, start, end, delivery, grace, sheet, colmap in MIS_PROFILES:
        if not frappe.db.exists("Lender MIS Profile", name):
            frappe.get_doc({
                "doctype": "Lender MIS Profile", "profile_name": name,
                "lender_entity": entity, "cycle_type": cycle,
                "window_start_day": start, "window_end_day": end,
                "expected_delivery_day": delivery, "grace_days": grace,
                "data_sheet": sheet,
                "column_map": [
                    {"source_column": src, "target_field": tgt, "transform": tr}
                    for src, tgt, tr in colmap
                ],
            }).insert()
            created["Lender MIS Profile"] += 1

    for entity, branch_name, city, state, dsa_code in BRANCHES:
        if not frappe.db.exists("Lender Branch", {"lender_entity": entity, "branch_name": branch_name}):
            frappe.get_doc({
                "doctype": "Lender Branch",
                "lender_entity": entity,
                "branch_name": branch_name,
                "city": city,
                "state": state,
                "basic_dsa_code": dsa_code,
            }).insert()
            created["Lender Branch"] += 1

    for profile_name, domain, pattern in MIS_PROFILE_ROUTING:
        if frappe.db.exists("Lender MIS Profile", profile_name):
            frappe.db.set_value("Lender MIS Profile", profile_name, {
                "sender_email_domain": domain,
                "filename_pattern": pattern,
            })

    for entity, trigger, proofs in CONFIRMATION_PROFILES:
        if not frappe.db.exists("Lender Confirmation Profile", {"lender_entity": entity}):
            frappe.get_doc({"doctype": "Lender Confirmation Profile", "lender_entity": entity,
                            "sla_trigger_event": trigger, "required_proofs": proofs}).insert()
            created["Lender Confirmation Profile"] += 1

    frappe.db.commit()
    print("[seed] created:", ", ".join(f"{k}: {v}" for k, v in created.items()))
    return created
