# Copyright (c) 2026, Muqeet Mughal and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

STALE_AFTER_SECONDS = 60
OFFLINE_AFTER_SECONDS = 300

CACHE_KEY = "tracker:status"


class UserTrackerStatus(Document):
	# --- instance methods (required by virtual doctype protocol) ---

	def load_from_db(self):
		key = self.name.encode("utf-8") if isinstance(self.name, str) else self.name
		raw = frappe.cache().hget(CACHE_KEY, key)
		if not raw:
			frappe.throw(_("User not found in tracker status"), frappe.DoesNotExistError)

		raw_str = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
		data = json.loads(raw_str)
		self.update(data)

	def db_insert(self, *args, **kwargs):
		frappe.throw(_("User Tracker Status is read-only"))

	def db_update(self, *args, **kwargs):
		frappe.throw(_("User Tracker Status is read-only"))

	def delete(self, *args, **kwargs):
		frappe.throw(_("User Tracker Status is read-only"))

	# --- class/static methods (required by virtual doctype protocol) ---

	@staticmethod
	def get_list(**kwargs):
		raw_map = frappe.cache().hgetall(CACHE_KEY) or {}
		rows = []

		for user_key, raw in raw_map.items():
			user = user_key.decode("utf-8") if isinstance(user_key, bytes) else str(user_key)
			raw_str = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
			data = json.loads(raw_str)

			last_heartbeat = data.get("last_heartbeat")
			age = None
			if last_heartbeat:
				age = (now_datetime() - get_datetime(last_heartbeat)).total_seconds()

			status = str(data.get("status") or "")

			if age is not None:
				if age > OFFLINE_AFTER_SECONDS:
					status = "Offline"
				elif age > STALE_AFTER_SECONDS and status == "Running":
					status = "Stale"

			rows.append({
				"name": user,
				"user": user,
				"employee": str(data.get("employee") or ""),
				"employee_name": str(data.get("employee_name") or ""),
				"status": status,
				"current_task": str(data.get("current_task") or ""),
				"project": str(data.get("project") or ""),
				"started_at": str(data.get("started_at") or ""),
				"last_heartbeat": str(data.get("last_heartbeat") or ""),
				"last_seen_seconds": age,
				"machine_id": str(data.get("machine_id") or ""),
				"app_version": str(data.get("app_version") or ""),
				"duration": str(data.get("duration") or ""),
			})

		return rows

	@staticmethod
	def get_count(**kwargs):
		raw_map = frappe.cache().hgetall(CACHE_KEY) or {}
		return len(raw_map) if raw_map else 0

	@staticmethod
	def get_stats(**kwargs):
		return {}
