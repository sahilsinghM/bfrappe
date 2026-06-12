# Copyright (c) 2026, BASIC Home Loan

import frappe


def execute(filters=None):
    filters = filters or {}
    conditions, values = ["1=1"], {}
    if filters.get("batch"):
        conditions.append("batch = %(batch)s")
        values["batch"] = filters["batch"]

    where = " and ".join(conditions)
    rows = frappe.db.sql(
        f"""select ifnull(match_method,'(none)') as match_method,
                   ifnull(match_confidence,'-') as match_confidence,
                   match_state,
                   count(*) as `lines`,
                   sum(ifnull(norm_rescued,0)) as norm_rescued,
                   sum(ifnull(payin_amt,0)) as payin_amt
            from `tabMIS Line` where {where}
            group by match_method, match_confidence, match_state
            order by match_state, match_confidence""",
        values, as_dict=True)

    total = sum(r.lines for r in rows) or 1
    auto = sum(r.lines for r in rows if r.match_state == "AutoMatched")
    for r in rows:
        r["pct_of_lines"] = round(100.0 * r.lines / total, 1)

    rows.append({
        "match_method": f"TOTAL (auto-matched {round(100.0 * auto / total, 1)}%)",
        "match_confidence": "",
        "match_state": "",
        "lines": total,
        "norm_rescued": sum(r.norm_rescued or 0 for r in rows),
        "payin_amt": sum(r.payin_amt or 0 for r in rows),
        "pct_of_lines": 100.0,
    })

    columns = [
        {"fieldname": "match_method", "label": "Match Method", "fieldtype": "Data", "width": 240},
        {"fieldname": "match_confidence", "label": "Confidence", "fieldtype": "Data", "width": 100},
        {"fieldname": "match_state", "label": "State", "fieldtype": "Data", "width": 130},
        {"fieldname": "lines", "label": "Lines", "fieldtype": "Int", "width": 80},
        {"fieldname": "pct_of_lines", "label": "% of Lines", "fieldtype": "Percent", "width": 100},
        {"fieldname": "norm_rescued", "label": "Normalization Rescued", "fieldtype": "Int", "width": 170},
        {"fieldname": "payin_amt", "label": "Payin Amount", "fieldtype": "Currency", "width": 150},
    ]
    return columns, rows
