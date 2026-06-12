"""Expected-in-MIS + overdue computation.

Registered as a daily scheduler job in hooks.py; also runnable on demand:

bench --site <site> execute basic_spine.spine.aging.recompute_expected
"""

from datetime import date, timedelta

import frappe
from frappe.utils import getdate

NOT_YET_MATCHED = ("Reported", "Verified", "AwaitingMIS", "Overdue")


def recompute_expected(today=None):
    today = getdate(today) if today else getdate()

    profiles = {}
    for p in frappe.get_all(
        "Lender MIS Profile",
        fields=["name", "lender_entity", "cycle_type", "window_start_day",
                "window_end_day", "expected_delivery_day", "grace_days"],
    ):
        profiles.setdefault(p.lender_entity, p)  # first profile per entity wins

    disbs = frappe.get_all(
        "Reported Disbursement",
        filters={"collection_state": ("in", NOT_YET_MATCHED)},
        fields=["name", "lender_entity", "sla_trigger_date", "disb_date", "collection_state"],
    )

    computed = overdue = no_profile = 0
    for d in disbs:
        prof = profiles.get(d.lender_entity)
        trigger = d.sla_trigger_date or d.disb_date
        if not prof or not trigger:
            no_profile += 1
            continue

        expected = _expected_delivery(prof, getdate(trigger))
        updates = {"expected_in_mis_by": expected}
        computed += 1

        if today > expected:
            updates["collection_state"] = "Overdue"
            updates["overdue_days"] = (today - expected).days
            overdue += 1
        else:
            updates["overdue_days"] = 0
            # Verified cases now have a concrete MIS expectation
            if d.collection_state == "Verified":
                updates["collection_state"] = "AwaitingMIS"
        frappe.db.set_value("Reported Disbursement", d.name, updates)

    frappe.db.commit()
    print(f"[recompute_expected] as-of {today}: examined {len(disbs)}, "
          f"expected dates set {computed}, overdue {overdue}, "
          f"skipped (no profile/trigger) {no_profile}")
    return {"examined": len(disbs), "computed": computed, "overdue": overdue}


def _expected_delivery(prof, trigger):
    """Expected MIS delivery for the cycle window containing the trigger date,
    plus grace days."""
    grace = prof.grace_days if prof.grace_days is not None else 5

    if prof.cycle_type == "Weekly":
        return trigger + timedelta(days=7 + grace)
    if prof.cycle_type == "Ten-Day":
        return trigger + timedelta(days=10 + grace)
    if prof.cycle_type != "Monthly-Window":
        # Adhoc / unspecified: flat 30-day placeholder
        return trigger + timedelta(days=30 + grace)

    # Monthly window, e.g. 15 -> 15: cases picked up from start_day of month M
    # to (end_day - 1) of month M+1, delivered on expected_delivery_day of the
    # month the window closes in.
    start_day = prof.window_start_day or 1
    delivery_day = prof.expected_delivery_day or 20
    if trigger.day >= start_day:
        close_month, close_year = _next_month(trigger.month, trigger.year)
    else:
        close_month, close_year = trigger.month, trigger.year
    return _safe_date(close_year, close_month, delivery_day) + timedelta(days=grace)


def _next_month(month, year):
    return (1, year + 1) if month == 12 else (month + 1, year)


def _safe_date(year, month, day):
    for d in range(day, 27, -1):
        try:
            return date(year, month, d)
        except ValueError:
            continue
    return date(year, month, min(day, 28))
