"""Email handler for bankmis@basichomeloan.com.

Pure routing logic is extracted into resolve_mis_profile() so it can be tested
without Frappe. The Frappe hook (process_incoming_email) calls it and delegates
to import_mis() on a match.
"""

import re


def resolve_mis_profile(
    from_email: str,
    filename: str,
    profiles: list[dict],
) -> str | None:
    """Return the profile_name for the first matching profile, or None.

    Matching waterfall:
      A) sender_email_domain suffix match on from_email  (most reliable)
      B) filename_pattern regex match on filename         (fallback)
    """
    from_email = (from_email or "").lower()
    filename = (filename or "")

    # Pass A — sender domain
    for p in profiles:
        domain = (p.get("sender_email_domain") or "").strip().lower()
        if domain and from_email.endswith(domain):
            return p["profile_name"]

    # Pass B — filename pattern
    for p in profiles:
        pattern = (p.get("filename_pattern") or "").strip()
        if pattern and re.search(pattern, filename, re.IGNORECASE):
            return p["profile_name"]

    return None


def _load_profiles() -> list[dict]:
    import frappe
    return frappe.get_all(
        "Lender MIS Profile",
        fields=["profile_name", "sender_email_domain", "filename_pattern"],
    )


def _already_processed(from_email: str, subject: str, attachment_filename: str) -> bool:
    import frappe
    return bool(frappe.db.exists(
        "Communication",
        {"sent_or_received": "Received", "sender": from_email,
         "subject": subject, "content": ("like", f"%{attachment_filename}%")},
    ))


def process_incoming_email(communication_name: str) -> None:  # noqa: C901
    """Called from Frappe's Communication after_insert hook.

    Loads the Communication, tries to route by profile, and either imports
    the MIS or creates a Pending MIS Classification for ops.
    """
    import frappe
    from basic_spine.spine.imports import import_mis
    comm = frappe.get_doc("Communication", communication_name)
    if comm.sent_or_received != "Received":
        return

    attachments = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Communication", "attached_to_name": communication_name},
        fields=["file_name", "file_url"],
    )
    xlsx_attachments = [
        a for a in attachments
        if (a.file_name or "").lower().endswith((".xlsx", ".xls", ".csv"))
    ]
    if not xlsx_attachments:
        return

    profiles = _load_profiles()

    for att in xlsx_attachments:
        if _already_processed(comm.sender, comm.subject, att.file_name):
            continue

        profile_name = resolve_mis_profile(comm.sender, att.file_name, profiles)

        if profile_name is None:
            frappe.get_doc({
                "doctype": "Pending MIS Classification",
                "received_on": frappe.utils.now(),
                "from_email": comm.sender,
                "subject": comm.subject,
                "attachment_filename": att.file_name,
                "attachment": att.file_url,
                "status": "Pending",
            }).insert(ignore_permissions=True)
            continue

        try:
            file_path = frappe.get_site_path("public", att.file_url.lstrip("/"))
            result = import_mis(
                path=file_path,
                profile=profile_name,
                received_on=frappe.utils.today(),
            )
            frappe.sendmail(
                recipients=[comm.sender],
                subject=f"Re: {comm.subject}",
                message=(
                    f"MIS Batch <b>{result['batch']}</b> created for {profile_name} "
                    f"— {result['imported']} rows imported."
                ),
            )
        except Exception as exc:
            frappe.log_error(title="MIS email ingest failed", message=str(exc))
            frappe.get_doc({
                "doctype": "Pending MIS Classification",
                "received_on": frappe.utils.now(),
                "from_email": comm.sender,
                "subject": comm.subject,
                "attachment_filename": att.file_name,
                "attachment": att.file_url,
                "status": "Pending",
            }).insert(ignore_permissions=True)
