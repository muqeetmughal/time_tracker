# Copyright (c) 2026, Muqeet Mughal and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

STALE_AFTER_SECONDS = 60
OFFLINE_AFTER_SECONDS = 300


class UserTrackerStatus(Document):
	@staticmethod
	def get_list(args):
		rows = []
		raw_map = frappe.cache().hgetall("tracker:status") or {}

		for user, raw in raw_map.items():
			data = json.loads(raw)

			last_heartbeat = data.get("last_heartbeat")
			age = None
			if last_heartbeat:
				age = (now_datetime() - get_datetime(last_heartbeat)).total_seconds()

			status = data.get("status")

			if age is not None:
				if age > OFFLINE_AFTER_SECONDS:
					status = "Offline"
				elif age > STALE_AFTER_SECONDS and status == "Running":
					status = "Stale"

			rows.append({
				"name": user,
				"user": user,
				"employee": data.get("employee"),
				"employee_name": data.get("employee_name"),
				"status": status,
				"current_task": data.get("current_task"),
				"project": data.get("project"),
				"started_at": data.get("started_at"),
				"last_heartbeat": data.get("last_heartbeat"),
				"last_seen_seconds": age,
				"machine_id": data.get("machine_id"),
				"app_version": data.get("app_version"),
				"duration": data.get("duration"),
			})

		return rows

	@staticmethod
	def get_count(args):
		raw_map = frappe.cache().hgetall("tracker:status") or {}
		return len(raw_map)

	@staticmethod
	def get_stats(args):
		return {}
