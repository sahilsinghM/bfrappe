"""Matching waterfall: lender MIS lines -> reported disbursements.

bench --site <site> execute basic_spine.spine.match.run_matching

Per Unmatched MIS Line, scoped to the line's lender entity (via its batch),
first hit wins:

  A   LAN exact            (lan_norm == lan_norm)
  A-  AppId exact          (app_id_norm == lender_app_id_norm, plus cross-column
                            swaps -- lenders swap LAN/AppId columns)
  B   fuzzy triangulation  (amount within 1%, disb date within +/-7 days, name
                            token-sort ratio >= 85; auto-commit + needs_review)
  C   candidate list       (name ratio >= 80, amount within 5%; top-3 stored in
                            candidate_json for the manual claim queue; no commit)
"""

import json
from datetime import timedelta

import frappe
from rapidfuzz import fuzz

from basic_spine.spine.normalize import norm_name

DISB_FIELDS = [
    "name", "lan_raw", "lan_norm", "lender_app_id_raw", "lender_app_id_norm",
    "customer_name", "disb_amt", "disb_date", "disb_created_on",
    "collection_state", "matched_mis_line",
]

MATCHABLE_STATES = ("Reported", "Verified", "AwaitingMIS", "Overdue")


def run_matching():
    lines = frappe.get_all(
        "MIS Line",
        filters={"match_state": "Unmatched"},
        fields=["name", "batch", "lan_raw", "lan_norm", "app_id_raw", "app_id_norm",
                "customer_name", "disb_amt", "disb_date", "payin_amt"],
    )
    batches = {b.name: b for b in frappe.get_all(
        "MIS Batch", fields=["name", "lender_entity", "received_on"])}

    stats = {"A": 0, "A-": 0, "B": 0, "C": 0, "unmatched": 0, "duplicate": 0,
             "claimed_post_mis": 0, "norm_rescued": 0, "unmatched_payin": 0.0}
    entity_cache = {}

    for line in lines:
        batch = batches.get(line.batch)
        entity = batch and batch.lender_entity
        if not entity:
            stats["unmatched"] += 1
            continue
        if entity not in entity_cache:
            entity_cache[entity] = _load_entity_index(entity)
        idx = entity_cache[entity]

        hit = _waterfall(line, idx)
        if hit:
            disb, method, confidence = hit
            _commit_match(line, disb, method, confidence, batch, idx, stats)
        else:
            _candidates(line, idx, stats)

    frappe.db.commit()

    matched = stats["A"] + stats["A-"] + stats["B"]
    print(f"[run_matching] lines processed: {len(lines)}")
    print(f"[run_matching] matched A: {stats['A']}  A-: {stats['A-']}  B (needs review): {stats['B']}")
    print(f"[run_matching] candidate-only (C): {stats['C']}  duplicates: {stats['duplicate']}")
    print(f"[run_matching] unmatched: {stats['unmatched']}  unmatched payin: "
          f"{stats['unmatched_payin']:,.0f}")
    print(f"[run_matching] claimed-post-MIS: {stats['claimed_post_mis']}")
    print(f"[run_matching] normalization-rescued: {stats['norm_rescued']}")
    return {**stats, "matched": matched}


def _load_entity_index(entity):
    rows = frappe.get_all("Reported Disbursement",
                          filters={"lender_entity": entity}, fields=DISB_FIELDS)
    by_lan, by_app = {}, {}
    for r in rows:
        if r.lan_norm:
            by_lan.setdefault(r.lan_norm, []).append(r)
        if r.lender_app_id_norm:
            by_app.setdefault(r.lender_app_id_norm, []).append(r)
        r._name_norm = norm_name(r.customer_name)
    return {"rows": rows, "by_lan": by_lan, "by_app": by_app}


def _pick(rows, line):
    """Among key-equal disbursements (multi-tranche cases), prefer unmatched,
    then closest amount."""
    if not rows:
        return None
    free = [r for r in rows if r.collection_state in MATCHABLE_STATES and not r.matched_mis_line]
    pool = free or rows
    amt = line.disb_amt or 0
    return min(pool, key=lambda r: abs((r.disb_amt or 0) - amt))


def _waterfall(line, idx):
    # A: LAN exact
    if line.lan_norm:
        hit = _pick(idx["by_lan"].get(line.lan_norm), line)
        if hit:
            return hit, "lan_exact", "A"
    # A-: AppId exact, plus cross-column swaps
    if line.app_id_norm:
        hit = _pick(idx["by_app"].get(line.app_id_norm), line)
        if hit:
            return hit, "appid_exact", "A-"
    if line.lan_norm:
        hit = _pick(idx["by_app"].get(line.lan_norm), line)
        if hit:
            return hit, "cross_mislan_vs_appid", "A-"
    if line.app_id_norm:
        hit = _pick(idx["by_lan"].get(line.app_id_norm), line)
        if hit:
            return hit, "cross_misapp_vs_lan", "A-"
    # B: fuzzy triangulation
    hit = _fuzzy(line, idx)
    if hit:
        return hit, "fuzzy_amt_date_name", "B"
    return None


def _fuzzy(line, idx):
    if not (line.disb_amt and line.disb_date and line.customer_name):
        return None
    name = norm_name(line.customer_name)
    best, best_ratio = None, 0
    for r in idx["rows"]:
        if not (r.disb_amt and r.disb_date) or r.matched_mis_line:
            continue
        if abs(line.disb_amt - r.disb_amt) / r.disb_amt > 0.01:
            continue
        if abs((line.disb_date - r.disb_date).days) > 7:
            continue
        ratio = fuzz.token_sort_ratio(name, r._name_norm)
        if ratio >= 85 and ratio > best_ratio:
            best, best_ratio = r, ratio
    return best


def _candidates(line, idx, stats):
    """Confidence C: store top-3 candidates for the manual claim queue."""
    if not (line.customer_name and line.disb_amt):
        stats["unmatched"] += 1
        stats["unmatched_payin"] += line.payin_amt or 0
        return
    name = norm_name(line.customer_name)
    scored = []
    for r in idx["rows"]:
        if not r.disb_amt or r.matched_mis_line:
            continue
        if abs(line.disb_amt - r.disb_amt) / r.disb_amt > 0.05:
            continue
        ratio = fuzz.token_sort_ratio(name, r._name_norm)
        if ratio >= 80:
            scored.append((ratio, r.name))
    if scored:
        top3 = [d for _, d in sorted(scored, key=lambda t: -t[0])[:3]]
        frappe.db.set_value("MIS Line", line.name, {
            "candidate_json": json.dumps(top3),
            "match_confidence": "C",
            "match_method": "candidate_name_amount",
        })
        stats["C"] += 1
    stats["unmatched"] += 1
    stats["unmatched_payin"] += line.payin_amt or 0


def _commit_match(line, disb, method, confidence, batch, idx, stats):
    # Duplicate guard: another MIS line already owns this disbursement.
    current = frappe.db.get_value("Reported Disbursement", disb.name,
                                  ["matched_mis_line", "collection_state"], as_dict=True)
    if current.matched_mis_line and current.matched_mis_line != line.name:
        frappe.db.set_value("MIS Line", line.name, {
            "match_state": "Duplicate",
            "matched_disbursement": disb.name,
            "match_method": method,
            "match_confidence": confidence,
        })
        stats["duplicate"] += 1
        print(f"[run_matching] duplicate: line {line.name} also matches {disb.name} "
              f"(already matched to {current.matched_mis_line})")
        return

    rescued = _is_norm_rescued(line, disb, method)

    # Business reported only after the money showed up in MIS — a key metric.
    claimed_post = bool(disb.disb_created_on and batch.received_on
                        and disb.disb_created_on > batch.received_on)
    new_state = "ClaimedPostMIS" if claimed_post else "Matched"

    frappe.db.set_value("MIS Line", line.name, {
        "match_state": "AutoMatched",
        "matched_disbursement": disb.name,
        "match_method": method,
        "match_confidence": confidence,
        "needs_review": 1 if confidence == "B" else 0,
        "norm_rescued": 1 if rescued else 0,
    })
    frappe.db.set_value("Reported Disbursement", disb.name, {
        "collection_state": new_state,
        "matched_mis_line": line.name,
        "match_method": method,
        "match_confidence": confidence,
        "overdue_days": 0,
    })
    disb.matched_mis_line = line.name  # keep in-memory index consistent
    disb.collection_state = new_state

    stats[confidence] += 1
    if claimed_post:
        stats["claimed_post_mis"] += 1
    if rescued:
        stats["norm_rescued"] += 1


def _is_norm_rescued(line, disb, method):
    """True when the join only works because of normalization: the raw strings
    on the two sides differ, but their normalized forms are equal."""
    pairs = {
        "lan_exact": (line.lan_raw, disb.lan_raw),
        "appid_exact": (line.app_id_raw, disb.lender_app_id_raw),
        "cross_mislan_vs_appid": (line.lan_raw, disb.lender_app_id_raw),
        "cross_misapp_vs_lan": (line.app_id_raw, disb.lan_raw),
    }
    if method not in pairs:
        return False
    a, b = pairs[method]
    if method.startswith("cross"):
        return True  # raw columns disagree by definition; only norms joined them
    return (a or "") != (b or "")
