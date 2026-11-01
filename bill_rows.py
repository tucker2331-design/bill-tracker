"""The Bill_Tracker sheet layout + record -> row mapping, shared by every state's writer.

Kept free of worker imports (no calendar_worker / LIS) so the Pennsylvania job writes EXACTLY the columns the site
already reads for Virginia. Moved verbatim out of bill_tracker.py (2026-11-01); test_bill_tracker_cells.py still
pins Virginia's write.
"""
import json

BILL_TRACKER_HEADER = ["Bill", "Title", "Status (LIS)", "Outcome", "Patron", "Patron ID", "Chamber",
                       "Crossed Over", "Last Committee", "Referrals", "Last Action", "Latest Vote (JSON)",
                       "Upcoming (JSON)", "History (JSON)", "Data As Of (UTC)", "Source",
                       "House Floor", "Senate Floor", "Outcome Origin", "Class", "Co-Patrons (JSON)"]


def bill_tracker_rows(records, status_label=None):
    """Header + one row per record, in BILL_TRACKER_HEADER order. Raises on a width drift (a shifted sheet).
    `status_label` renames column C for another state's sheet (PA: "Status (PA General Assembly)"); the site reads
    columns by POSITION, so only the label changes. Virginia passes nothing and keeps "Status (LIS)" byte-identical."""
    header = list(BILL_TRACKER_HEADER)
    if status_label:
        header[2] = status_label
    rows = [header] + [[
        r["bill"], r["title"], r["status_lis"], r["outcome"], r["patron"], r["patron_id"], r["chamber"],
        "yes" if r["crossed_over"] else "no", r["last_committee"], r["referral_count"], r["last_action_date"],
        json.dumps(r["latest_vote"], ensure_ascii=False), json.dumps(r["upcoming"], ensure_ascii=False),
        json.dumps(r["history"], ensure_ascii=False), r["data_as_of_utc"], r["source"],
        r["floor_house"], r["floor_senate"], r["outcome_origin"], r.get("legislation_class", ""),
        "" if r.get("copatrons") is None else json.dumps(r["copatrons"], ensure_ascii=False),
    ] for r in records]
    if any(len(row) != len(header) for row in rows):     # a row/header drift would shift every column after it
        raise RuntimeError(f"Bill_Tracker row width != header width ({len(header)}); refusing to write a "
                           f"shifted sheet")
    return rows
