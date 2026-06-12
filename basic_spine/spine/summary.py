"""End-to-end console summary — the prototype's definition-of-done numbers.

bench --site <site> execute basic_spine.spine.summary.print_summary
"""

import frappe


def print_summary():
    print("=" * 72)
    print("BASIC SPINE — END-TO-END SUMMARY")
    print("=" * 72)

    # Reported book
    total = frappe.db.count("Reported Disbursement")
    resolved = frappe.db.count("Reported Disbursement", {"lender_entity": ("is", "set")})
    unresolved_labels = [r[0] for r in frappe.db.sql(
        """select distinct lender_raw_label from `tabReported Disbursement`
           where ifnull(lender_entity,'')='' and ifnull(lender_raw_label,'')!=''""")]
    print(f"\nReported disbursements imported : {total}")
    print(f"Resolved to a lender entity     : {resolved}")
    print(f"Unresolved labels ({len(unresolved_labels)}): {unresolved_labels}")

    # MIS batches
    print("\nMIS batches:")
    for b in frappe.get_all("MIS Batch", fields=["name", "lender_entity", "mis_month",
                                                 "received_on", "line_count"]):
        print(f"  {b.name}: {b.lender_entity} {b.mis_month} received {b.received_on}, "
              f"{b.line_count} lines ingested")

    # Match quality
    print("\nMIS line match outcomes:")
    for row in frappe.db.sql(
        """select match_state, ifnull(match_confidence,'') conf, count(*) n,
                  sum(ifnull(payin_amt,0)) payin
           from `tabMIS Line` group by match_state, conf order by match_state, conf""",
        as_dict=True,
    ):
        print(f"  {row.match_state:<16} {row.conf or '-':<4} count {row.n:>4}   "
              f"payin {row.payin:>14,.0f}")

    unmatched = frappe.db.sql(
        """select count(*), sum(ifnull(payin_amt,0)) from `tabMIS Line`
           where match_state='Unmatched'""")[0]
    print(f"\nUnmatched MIS lines (leakage)   : {unmatched[0]}  "
          f"(payin at stake: {unmatched[1] or 0:,.0f})")

    rescued = frappe.db.count("MIS Line", {"norm_rescued": 1})
    print(f"\n*** NORMALIZATION-RESCUED MATCHES: {rescued} ***")
    print("    (matches that succeed on _norm but would fail on raw equality)")

    claimed = frappe.db.sql(
        """select count(*), sum(ifnull(disb_amt,0)) from `tabReported Disbursement`
           where collection_state='ClaimedPostMIS'""")[0]
    print(f"\nClaimed-post-MIS disbursements  : {claimed[0]}  (₹ {claimed[1] or 0:,.0f})")

    # Collection funnel
    print("\nCollection funnel:")
    for row in frappe.db.sql(
        """select collection_state, count(*) n, sum(ifnull(disb_amt,0)) amt
           from `tabReported Disbursement`
           group by collection_state order by n desc""", as_dict=True):
        print(f"  {row.collection_state:<16} count {row.n:>4}   ₹ {row.amt:>16,.0f}")

    # Leakage aging top 10
    print("\nLeakage aging — top 10 overdue by ₹ (payin est. = 1% of disb, placeholder):")
    for row in frappe.db.sql(
        """select name, lender_entity, overdue_days, disb_amt
           from `tabReported Disbursement` where collection_state='Overdue'
           order by disb_amt desc limit 10""", as_dict=True):
        print(f"  {row.name:<14} {row.lender_entity or '?':<28} "
              f"{row.overdue_days:>4}d  ₹ {row.disb_amt:>14,.0f}  "
              f"(payin-at-risk est. ₹ {row.disb_amt * 0.01:,.0f})")
    print("=" * 72)
