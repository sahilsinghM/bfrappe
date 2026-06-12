# Copyright (c) 2026, BASIC Home Loan
#
# Payin-at-risk is estimated at a flat 1% of disbursed amount — a clearly
# labelled placeholder until the Phase 2 rate engine exists.

import frappe

PAYIN_ESTIMATE_PCT = 0.01
BUCKETS = [(0, 15, "0-15"), (16, 30, "16-30"), (31, 60, "31-60"), (61, 10**6, "60+")]


def _bucket(days):
    for lo, hi, label in BUCKETS:
        if lo <= days <= hi:
            return label
    return "60+"


def execute(filters=None):
    filters = filters or {}
    conditions, values = ["collection_state = 'Overdue'"], {}
    if filters.get("lender_entity"):
        conditions.append("lender_entity = %(lender_entity)s")
        values["lender_entity"] = filters["lender_entity"]

    rows = frappe.db.sql(
        f"""select lender_entity, overdue_days, ifnull(disb_amt,0) as disb_amt
            from `tabReported Disbursement` where {' and '.join(conditions)}""",
        values, as_dict=True)

    agg = {}
    for r in rows:
        key = (r.lender_entity or "(unresolved)", _bucket(r.overdue_days or 0))
        slot = agg.setdefault(key, {"cases": 0, "disb_amt": 0.0})
        slot["cases"] += 1
        slot["disb_amt"] += r.disb_amt

    bucket_rank = {label: i for i, (_, _, label) in enumerate(BUCKETS)}
    data = [{
        "lender_entity": entity,
        "age_bucket": bucket,
        "cases": v["cases"],
        "disb_amt": v["disb_amt"],
        "payin_at_risk_est": v["disb_amt"] * PAYIN_ESTIMATE_PCT,
    } for (entity, bucket), v in sorted(agg.items(),
                                        key=lambda kv: (kv[0][0], bucket_rank[kv[0][1]]))]

    columns = [
        {"fieldname": "lender_entity", "label": "Lender Entity", "fieldtype": "Link",
         "options": "Lender Entity", "width": 220},
        {"fieldname": "age_bucket", "label": "Age Bucket (days)", "fieldtype": "Data", "width": 130},
        {"fieldname": "cases", "label": "Cases", "fieldtype": "Int", "width": 90},
        {"fieldname": "disb_amt", "label": "Disbursed Amount", "fieldtype": "Currency", "width": 170},
        {"fieldname": "payin_at_risk_est", "label": "Payin at Risk (est. 1% — placeholder)",
         "fieldtype": "Currency", "width": 240},
    ]
    return columns, data
