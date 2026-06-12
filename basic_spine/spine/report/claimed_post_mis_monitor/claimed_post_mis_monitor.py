# Copyright (c) 2026, BASIC Home Loan
#
# Cases the business reported only AFTER the lender's money showed up in MIS —
# a first-class leakage-behaviour metric, by team and sourcing agent.

import frappe


def execute(filters=None):
    filters = filters or {}
    conditions, values = ["collection_state = 'ClaimedPostMIS'"], {}
    if filters.get("team"):
        conditions.append("team = %(team)s")
        values["team"] = filters["team"]

    rows = frappe.db.sql(
        f"""select ifnull(team,'(none)') as team,
                   ifnull(sourcing_agent_code,'(none)') as sourcing_agent_code,
                   count(*) as cases,
                   sum(ifnull(disb_amt,0)) as disb_amt
            from `tabReported Disbursement`
            where {' and '.join(conditions)}
            group by team, sourcing_agent_code
            order by disb_amt desc""",
        values, as_dict=True)

    columns = [
        {"fieldname": "team", "label": "Team", "fieldtype": "Data", "width": 140},
        {"fieldname": "sourcing_agent_code", "label": "Sourcing Agent", "fieldtype": "Data", "width": 140},
        {"fieldname": "cases", "label": "Cases", "fieldtype": "Int", "width": 90},
        {"fieldname": "disb_amt", "label": "Disbursed Amount", "fieldtype": "Currency", "width": 180},
    ]
    return columns, rows
