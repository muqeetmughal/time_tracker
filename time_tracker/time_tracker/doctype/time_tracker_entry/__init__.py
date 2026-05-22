import frappe



@frappe.whitelist()
def push_time_tracker_entry(entry):
    entry = frappe._dict(frappe.parse_json(entry))
    if not entry.get("start_time"):
        entry["start_time"] = frappe.utils.now()
    if not entry.get("end_time"):
        entry["end_time"] = frappe.utils.now()

    doc = frappe.get_doc(
        {
            "doctype": "Time Tracker Entry",
            "activity_type": entry.activity_type,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "reference_doctype": entry.reference_doctype,
            "reference_name": entry.reference_name,
        }
    )
    doc.insert()
    return doc.name