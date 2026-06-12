"""File importers, runnable via bench execute:

bench --site <site> execute basic_spine.spine.imports.import_reported \
    --kwargs "{'path':'prototype_data/reported.xlsx'}"

bench --site <site> execute basic_spine.spine.imports.import_mis \
    --kwargs "{'path':'prototype_data/mis_chola.xlsx','profile':'Chola Monthly',
               'received_on':'2026-04-20','mis_month':'Apr-26'}"
"""

import frappe
import pandas as pd

from basic_spine.spine.normalize import fingerprint, norm_id, strip_invisibles

# Exact headers of the console "Case Pipeline" export (header row is the 3rd row).
REPORTED_COLUMNS = {
    "Team Name": "team",
    "Disb id": "disb_id",
    "Lender App id": "lender_app_id_raw",
    # The lender's disb/loan id column; treat as LAN candidate.
    "Lender Disb id": "lan_raw",
    "Customer Name": "customer_name",
    "pincode": "pincode",
    "District": "district",
    "Lender": "lender_raw_label",
    "application_date": "application_date",
    "Login Date": "login_date",
    "Login Amt.": "login_amt",
    "Sanc Date": "sanction_date",
    "Sanc Amt.": "sanction_amt",
    "Disb Date": "disb_date",
    "Disb. Created on": "disb_created_on",
    "Disb. Amt.": "disb_amt",
    "Disb. Status": "console_status",
    "Disb. Link": "console_link",
    "Agent": "sourcing_agent_code",
    "Agent RM": "agent_rm_code",
    "Ful. RM": "fulfilment_rm_code",
    # "Basic id" is derived from "Disb id" in validate(); ignored on purpose.
}

DATE_FIELDS = {"application_date", "login_date", "sanction_date", "disb_date", "disb_created_on"}
AMOUNT_FIELDS = {"login_amt", "sanction_amt", "disb_amt"}


# Raw id fields are stored verbatim — corruption included — so the norm fields
# can prove what normalization rescued. Everything else gets cleaned.
RAW_ID_FIELDS = {"lan_raw", "lender_app_id_raw"}


def _clean_cell(v, keep_raw=False):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v)
    if keep_raw:
        return s if strip_invisibles(s).strip() else None
    s = strip_invisibles(s).strip()
    return s or None


def _parse_date(v):
    """Export date formats vary: 01-Apr-2025, 07-Apr-25, sometimes real datetimes."""
    v = _clean_cell(v)
    if v is None:
        return None
    try:
        ts = pd.to_datetime(v, dayfirst=True)
    except (ValueError, TypeError):
        return None
    return None if pd.isna(ts) else ts.date().isoformat()


def _parse_amount(v):
    v = _clean_cell(v)
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("₹", "").strip())
    except ValueError:
        return None


def import_reported(path, header_row=2):
    """Idempotent upsert of the Case Pipeline export, keyed on disb_id."""
    df = pd.read_excel(path, header=header_row, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REPORTED_COLUMNS if c not in df.columns]
    if missing:
        frappe.throw(f"Reported export at {path} is missing expected columns: {missing}")

    inserted = updated = skipped = 0
    unresolved: dict[str, int] = {}

    for _, row in df.iterrows():
        values = {target: _clean_cell(row.get(src), keep_raw=target in RAW_ID_FIELDS)
                  for src, target in REPORTED_COLUMNS.items()}
        if not values.get("disb_id"):
            skipped += 1
            continue
        for fld in DATE_FIELDS:
            values[fld] = _parse_date(row.get(_src_for(fld)))
        for fld in AMOUNT_FIELDS:
            values[fld] = _parse_amount(row.get(_src_for(fld)))

        label = values.get("lender_raw_label")
        entity = frappe.db.get_value("Lender Alias", label, "lender_entity") if label else None
        if label and not entity:
            unresolved[label] = unresolved.get(label, 0) + 1
        values["lender_entity"] = entity

        existing = frappe.db.exists("Reported Disbursement", values["disb_id"])
        if existing:
            doc = frappe.get_doc("Reported Disbursement", existing)
            doc.update(values)
            doc.save()
            updated += 1
        else:
            doc = frappe.get_doc({"doctype": "Reported Disbursement", **values})
            doc.insert()
            inserted += 1

    frappe.db.commit()

    print(f"[import_reported] rows read: {len(df)}")
    print(f"[import_reported] inserted: {inserted}, updated: {updated}, skipped (no disb_id): {skipped}")
    print(f"[import_reported] unresolved-lender rows: {sum(unresolved.values())}")
    if unresolved:
        print("[import_reported] unresolved labels (add a Lender Alias and re-run):")
        for label, count in sorted(unresolved.items(), key=lambda kv: -kv[1]):
            print(f"  - {label!r}: {count} rows")
    return {"read": len(df), "inserted": inserted, "updated": updated, "unresolved": unresolved}


def _src_for(target):
    return next(src for src, tgt in REPORTED_COLUMNS.items() if tgt == target)


# ---------------------------------------------------------------------------
# MIS import
# ---------------------------------------------------------------------------

TARGET_TO_FIELD = {
    "LAN": "lan_raw",
    "AppId": "app_id_raw",
    "CustomerName": "customer_name",
    "Mobile": "mobile",
    "ProductLabel": "product_label",
    "Branch": "branch_label",
    "State": "state",
    "SanctionAmt": "sanction_amt",
    "DisbAmt": "disb_amt",
    "DisbDate": "disb_date",
    "PayinAmt": "payin_amt",
    "SlabPct": "slab_pct",
    "SubventionAmt": "subvention_amt",
    "CrossSellAmt": "cross_sell_amt",
    "InvoiceRef": "invoice_ref",
}
MIS_AMOUNT_TARGETS = {"SanctionAmt", "DisbAmt", "PayinAmt", "SlabPct", "SubventionAmt", "CrossSellAmt"}


def _apply_transform(value, transform):
    if value is None:
        return None
    s = str(value)
    if transform == "StripZeroWidth":
        s = strip_invisibles(s).strip()
    elif transform == "UpperTrim":
        s = strip_invisibles(s).strip().upper()
    elif transform == "StripLPrefix":
        s = strip_invisibles(s).strip()
        if s.upper().startswith("L"):
            s = s[1:]
    elif transform == "StripNonAlnum":
        s = "".join(ch for ch in strip_invisibles(s) if ch.isalnum())
    return s.strip() or None


def import_mis(path, profile, received_on, mis_month=None):
    """Ingest one lender MIS file into a new MIS Batch, dedup lines by fingerprint."""
    prof = frappe.get_doc("Lender MIS Profile", profile)
    if not prof.column_map:
        frappe.throw(f"Lender MIS Profile {profile} has no column map")

    sheet = prof.data_sheet or 0
    df = pd.read_excel(path, sheet_name=sheet, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]

    log_lines = [f"file: {path}", f"profile: {profile}", f"sheet: {sheet!r}", f"rows in file: {len(df)}"]
    missing = [m.source_column for m in prof.column_map
               if m.target_field != "Ignore" and m.source_column not in df.columns]
    if missing:
        log_lines.append(f"WARNING: mapped columns missing from file: {missing}")

    batch = frappe.get_doc({
        "doctype": "MIS Batch",
        "lender_entity": prof.lender_entity,
        "mis_month": mis_month,
        "received_on": received_on,
        "format_profile": prof.name,
    }).insert()

    strip_l = any(m.transform == "StripLPrefix" and m.target_field in ("LAN", "AppId")
                  for m in prof.column_map)

    created = duplicates = empty = 0
    for _, row in df.iterrows():
        line = {}
        for m in prof.column_map:
            if m.target_field == "Ignore" or m.source_column not in df.columns:
                continue
            raw = row.get(m.source_column)
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                continue
            value = _apply_transform(raw, m.transform or "None")
            field = TARGET_TO_FIELD[m.target_field]
            if m.target_field in MIS_AMOUNT_TARGETS:
                value = _parse_amount(value)
            elif m.target_field == "DisbDate":
                value = _parse_date(raw)
            line[field] = value

        if not any(line.values()):
            empty += 1
            continue

        line["lan_norm"] = norm_id(line.get("lan_raw"), strip_l_prefix=strip_l)
        line["app_id_norm"] = norm_id(line.get("app_id_raw"))
        fp = fingerprint(line.get("lan_raw"), line.get("app_id_raw"),
                         line.get("disb_amt"), line.get("disb_date"), line.get("customer_name"))

        # Drip-feed guard: the same month can arrive as several partial files.
        if frappe.db.exists("MIS Line", {"line_fingerprint": fp}):
            duplicates += 1
            continue

        if line.get("product_label"):
            line["mapped_product"] = frappe.db.get_value(
                "Lender Product Map",
                {"lender_entity": prof.lender_entity, "lender_product_label": line["product_label"]},
                "basic_product",
            )

        frappe.get_doc({
            "doctype": "MIS Line",
            "batch": batch.name,
            "line_fingerprint": fp,
            **line,
        }).insert()
        created += 1

    log_lines += [f"lines created: {created}", f"duplicates skipped (fingerprint): {duplicates}",
                  f"empty rows skipped: {empty}"]
    batch.line_count = created
    batch.ingest_log = "\n".join(log_lines)
    batch.save()

    _attach_source_file(batch, path)
    frappe.db.commit()

    print(f"[import_mis] batch {batch.name}: rows {len(df)}, created {created}, "
          f"duplicates skipped {duplicates}, empty {empty}")
    if missing:
        print(f"[import_mis] WARNING missing mapped columns: {missing}")
    return {"batch": batch.name, "created": created, "duplicates": duplicates}


def _attach_source_file(batch, path):
    import os

    from frappe.utils.file_manager import save_file

    try:
        with open(path, "rb") as fh:
            content = fh.read()
        file_doc = save_file(os.path.basename(path), content, "MIS Batch", batch.name, is_private=1)
        batch.db_set("source_file", file_doc.file_url)
    except Exception as e:  # attachment is best-effort; ingest already succeeded
        frappe.log_error(f"MIS source file attach failed: {e}")
