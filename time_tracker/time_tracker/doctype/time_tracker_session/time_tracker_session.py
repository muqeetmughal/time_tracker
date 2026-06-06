# Copyright (c) 2026, Muqeet Mughal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TimeTrackerSession(Document):
	@staticmethod
	def upsert(user: str, data: dict):
		existing = frappe.db.get_value(
			"Time Tracker Session",
			{"user": user, "status": ("!=", "Stopped")},
			"name",
		)

		fields = {
			"status": data.get("status", "Running"),
			"project": data.get("project"),
			"current_task": data.get("current_task"),
			"user": user,
			"employee": data.get("employee"),
			"started_at": data.get("started_at"),
			"last_heartbeat": data.get("last_heartbeat"),
			"machine_id": data.get("machine_id"),
			"app_version": data.get("app_version"),
		}

		if existing:
			doc = frappe.get_doc("Time Tracker Session", existing)
			doc.update(fields)
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": "Time Tracker Session", **fields})
			doc.insert(ignore_permissions=True)

		return doc.name
