# Copyright (c) 2026, BASIC Home Loan

import frappe

STATE_ORDER = ["Reported", "Verified", "AwaitingMIS", "Matched", "ClaimedPostMIS",
               "Overdue", "Disputed", "WrittenOff"]


def execute(filters=None):
    filters = filters or {}
    conditions, values = ["1=1"], {}
    if filters.get("lender_entity"):
        conditions.append("lender_entity = %(lender_entity)s")
        values["lender_entity"] = filters["lender_entity"]
    if filters.get("from_date"):
        conditions.append("disb_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conditions.append("disb_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    rows = frappe.db.sql(
        f"""select collection_state, count(*) as cases, sum(ifnull(disb_amt,0)) as disb_amt
            from `tabReported Disbursement`
            where {' and '.join(conditions)}
            group by collection_state""",
        values, as_dict=True)
    by_state = {r.collection_state: r for r in rows}
    data = [{"collection_state": s,
             "cases": by_state[s].cases,
             "disb_amt": by_state[s].disb_amt}
            for s in STATE_ORDER if s in by_state]

    columns = [
        {"fieldname": "collection_state", "label": "Collection State", "fieldtype": "Data", "width": 160},
        {"fieldname": "cases", "label": "Cases", "fieldtype": "Int", "width": 100},
        {"fieldname": "disb_amt", "label": "Disbursed Amount", "fieldtype": "Currency", "width": 180},
    ]
    return columns, data
