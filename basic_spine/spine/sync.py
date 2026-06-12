"""Console API sync — read-only pull from dev-applicationservice.basichomeloan.com.

Pulls disbursement data every 15 minutes via the scheduler hook in hooks.py.
The API key and base URL live in Frappe System Settings (spine_api_key /
spine_api_base_url), never in code or git.

Manual backfill:
  bench --site <site> execute basic_spine.spine.sync.backfill \
    --kwargs "{'from_date':'2026-01-01','to_date':'2026-06-01'}"
"""

import requests


# ── Field mapping: DisbursementResponse → Reported Disbursement ─────────────

_FIELD_MAP = {
    "basicDisbId": "name",
    "bankAppId": "app_id",
    "disbursementAmount": "disb_amt",
    "disbursementDate": "disb_date",
    "paidOnDate": "paid_on_date",
    "invoicedOnDate": "invoiced_on_date",
    "disbursementPayoutAmount": "payout_amt",
}


def _map_record(raw: dict) -> dict:
    return {dest: raw.get(src) for src, dest in _FIELD_MAP.items() if raw.get(src) is not None}


def test_connection() -> dict:
    """Verify the API key works. Returns {"ok": True} or {"ok": False, "error": str}."""
    import frappe
    api_key = frappe.db.get_single_value("System Settings", "spine_api_key")
    base_url = frappe.db.get_single_value("System Settings", "spine_api_base_url")
    if not api_key or not base_url:
        return {"ok": False, "error": "spine_api_key or spine_api_base_url not configured"}
    try:
        resp = requests.get(
            f"{base_url}/api/v1/health",
            headers={"X-Api-Key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def pull_disbursements(since: str | None = None) -> dict:
    """Pull disbursements from the application service API.

    Returns summary: {"pulled": int, "created": int, "updated": int}.
    """
    import frappe
    api_key = frappe.db.get_single_value("System Settings", "spine_api_key")
    base_url = frappe.db.get_single_value("System Settings", "spine_api_base_url")

    if not api_key or not base_url:
        frappe.throw("spine_api_key and spine_api_base_url must be configured in System Settings.")

    log = frappe.get_doc({
        "doctype": "API Sync Log",
        "sync_started_at": frappe.utils.now(),
        "status": "Running",
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    pulled = created = updated = 0
    page = 1

    try:
        while True:
            payload = {"pageNumber": page, "pageSize": 100}
            if since:
                payload["fromDate"] = since
            resp = requests.post(
                f"{base_url}/api/v1/Disbursement/pagedDisbSummary",
                json=payload,
                headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data") or data.get("items") or []

            if not items:
                break

            for item in items:
                pulled += 1
                record = _map_record(item)
                disb_id = item.get("basicDisbId")
                if not disb_id:
                    continue
                if frappe.db.exists("Reported Disbursement", disb_id):
                    frappe.db.set_value("Reported Disbursement", disb_id, record)
                    updated += 1
                else:
                    frappe.get_doc({
                        "doctype": "Reported Disbursement",
                        "name": disb_id,
                        **record,
                    }).insert(ignore_permissions=True)
                    created += 1

            if len(items) < 100:
                break
            page += 1

        frappe.db.set_value("API Sync Log", log.name, {
            "sync_completed_at": frappe.utils.now(),
            "records_pulled": pulled,
            "records_created": created,
            "records_updated": updated,
            "status": "Success",
        })
        frappe.db.set_single_value("System Settings", "spine_last_sync_at", frappe.utils.now())

    except Exception as exc:
        frappe.db.set_value("API Sync Log", log.name, {
            "sync_completed_at": frappe.utils.now(),
            "status": "Failed",
            "error": str(exc),
        })
        frappe.log_error(title="Console API sync failed", message=str(exc))

    frappe.db.commit()
    return {"pulled": pulled, "created": created, "updated": updated}


def scheduled_pull():
    """15-minute scheduler hook. Skips silently if not configured."""
    import frappe
    api_key = frappe.db.get_single_value("System Settings", "spine_api_key")
    if not api_key:
        return
    since = frappe.db.get_single_value("System Settings", "spine_last_sync_at")
    pull_disbursements(since=since)


def backfill(from_date: str, to_date: str):
    """Backfill all disbursements in a date range. Idempotent."""
    import frappe
    frappe.msgprint(f"Backfill starting: {from_date} → {to_date}")
    result = pull_disbursements(since=from_date)
    frappe.msgprint(
        f"Backfill done — pulled: {result['pulled']}, "
        f"created: {result['created']}, updated: {result['updated']}"
    )
