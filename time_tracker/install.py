import frappe


def after_install():
    activity_types = [
        "Discovery / Requirement Gathering",
        "Solution Design",
        "ERP Configuration",
        "Custom Development",
        "Data Migration",
        "Testing / QA",
        "UAT Support",
        "Training",
        "Support / Issue Resolution",
        "Project Coordination",
        "Documentation",
        "Internal R&D",
    ]

    existing = frappe.get_all("Activity Type", pluck="name")
    for name in existing:
        if name not in activity_types:
            doc = frappe.get_doc("Activity Type", name)
            doc.disabled = 1
            doc.save(ignore_permissions=True)

    for name in activity_types:
        if not frappe.db.exists("Activity Type", name):
            doc = frappe.new_doc("Activity Type")
            doc.activity_type = name
            doc.insert()
