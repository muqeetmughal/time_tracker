import json

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime


TIME_TRACKER_DOCTYPE = "Time Tracker Entry"
CACHE_KEY = "tracker:status"


class TimeTrackerSyncError(frappe.ValidationError):
	pass


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _to_mysql_datetime(val: str) -> str:
	if not val:
		return frappe.utils.now()
	dt = get_datetime(val)
	return dt.strftime("%Y-%m-%d %H:%M:%S")


def _get_employee(user: str) -> str | None:
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _get_employee_name(user: str) -> str | None:
	return frappe.db.get_value("Employee", {"user_id": user}, "employee_name")


def _update_cache(user: str, data: dict):
	now = frappe.utils.now()
	data["last_heartbeat"] = data.get("last_heartbeat", now)
	if not data.get("started_at"):
		data["started_at"] = now

	frappe.cache().hset(CACHE_KEY, user, json.dumps(data, default=str))


def _create_log(user: str, event_type: str, data: dict, retries: int = 3):
	import uuid
	import time as _time

	for attempt in range(retries):
		try:
			doc = frappe.get_doc({
				"doctype": "Time Tracker Log",
				"user": user,
				"employee": _get_employee(user),
				"event_type": event_type,
				"task": data.get("current_task"),
				"project": data.get("project"),
				"timestamp": data.get("timestamp", frappe.utils.now()),
				"machine_id": data.get("machine_id"),
				"metadata": json.dumps(data, default=str),
				"name": str(uuid.uuid4()),
			})
			doc.insert(ignore_permissions=True)
			return doc
		except frappe.QueryDeadlockError:
			if attempt == retries - 1:
				raise
			_time.sleep(0.2 * (attempt + 1))


def _publish_realtime(user: str, data: dict):
	frappe.publish_realtime(
		"tracker:status_update",
		{
			"user": user,
			"status": data.get("status"),
			"current_task": data.get("current_task"),
			"project": data.get("project"),
			"last_heartbeat": data.get("last_heartbeat"),
		},
		after_commit=True,
	)


# ---------------------------------------------------------------------------
#  Public endpoints
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def sync_time_tracker_record():
	data = frappe.local.form_dict

	STATUS_MAP = {
		"idle": "Idle",
		"running": "Running",
		"paused": "Paused",
		"completed": "Completed",
	}

	payload_to_doc = {
		"external_activity_id": "activity_id",
		"project": "project_id",
		"task": "task_id",
		"activity_type": "activity_type",
		"description": "description",
		"start_time": "start_time",
		"end_time": "end_time",
		"duration_seconds": "duration_seconds",
		"status": "status",
		"screenshots_count": "screenshots_count",
		"camshots_count": "camshots_count",
		"keyboard_count": "keyboard_count",
		"mouse_click_count": "mouse_click_count",
	}

	doc_fields = {dt: data.get(payload) for dt, payload in payload_to_doc.items()}
	doc_fields["doctype"] = TIME_TRACKER_DOCTYPE
	doc_fields["source"] = "Desktop App"

	status = doc_fields.get("status")
	if status:
		doc_fields["status"] = STATUS_MAP.get(status.lower(), status)

	if not doc_fields.get("user"):
		doc_fields["user"] = frappe.session.user

	if not doc_fields.get("employee"):
		employee = _get_employee(frappe.session.user)
		if employee:
			doc_fields["employee"] = employee

	activity_id = data.get("activity_id")
	existing_name = frappe.db.get_value(
		TIME_TRACKER_DOCTYPE, {"external_activity_id": activity_id}
	) if activity_id else None

	if existing_name:
		doc = frappe.get_doc(TIME_TRACKER_DOCTYPE, existing_name)
		doc.update(doc_fields)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(doc_fields)
		doc.insert(ignore_permissions=True)

	frappe.response["message"] = "ok"


@frappe.whitelist(methods=["POST"])
def sync_media():
	activity_id = frappe.form_dict.get("activity_id")
	if not activity_id:
		frappe.throw(_("activity_id is required"))

	existing_name = frappe.db.get_value(
		TIME_TRACKER_DOCTYPE, {"external_activity_id": activity_id}
	)
	if not existing_name:
		frappe.throw(
			_("Time Tracker Entry not found for activity_id: {0}").format(activity_id)
		)

	parent = frappe.get_doc(TIME_TRACKER_DOCTYPE, existing_name)

	file_url = None
	uploaded_file = frappe.request.files.get("file")
	if uploaded_file:
		file_content = uploaded_file.read()
		filename = frappe.form_dict.get("filename") or uploaded_file.filename
		_file = frappe.get_doc({
			"doctype": "File",
			"file_name": filename,
			"content": file_content,
			"is_private": 1,
			"attached_to_doctype": TIME_TRACKER_DOCTYPE,
			"attached_to_name": parent.name,
		})
		_file.save(ignore_permissions=True)
		file_url = _file.file_url

	child = parent.append("activity_media", {
		"media_id": frappe.form_dict.get("media_id"),
		"media_type": frappe.form_dict.get("media_type"),
		"filename": frappe.form_dict.get("filename"),
		"file_size": cint(frappe.form_dict.get("file_size")),
		"status": frappe.form_dict.get("status", "pending"),
		"file": file_url,
	})
	parent.save(ignore_permissions=True)

	frappe.response["message"] = "ok"


@frappe.whitelist(methods=["POST"])
def update_tracker_status():
	user = frappe.session.user
	data = frappe.local.form_dict
	status = data.get("status", "").capitalize()

	if not status:
		frappe.throw(_("status is required"))

	# Preserve started_at from existing cache when not provided
	existing_raw = frappe.cache().hget(CACHE_KEY, user)
	existing = json.loads(existing_raw) if existing_raw else {}

	now = frappe.utils.now()
	employee = _get_employee(user)

	cache_data = {
		"status": status,
		"project": data.get("project") or existing.get("project"),
		"current_task": data.get("current_task") or existing.get("current_task"),
		"started_at": _to_mysql_datetime(data.get("started_at")) if data.get("started_at") else existing.get("started_at") or now,
		"last_heartbeat": now,
		"machine_id": data.get("machine_id") or existing.get("machine_id"),
		"app_version": data.get("app_version") or existing.get("app_version"),
		"employee": employee or existing.get("employee"),
		"employee_name": _get_employee_name(user) if employee else existing.get("employee_name"),
	}

	EVENT_MAP = {
		"Running": "Started",
		"Stopped": "Stopped",
		"Idle": "Heartbeat",
	}
	event_type = EVENT_MAP.get(status, "Heartbeat")

	_update_cache(user, cache_data)
	_create_log(user, event_type, {**cache_data, "timestamp": now})
	_publish_realtime(user, cache_data)

	if status in ("Running", "Stopped", "Idle"):
		from time_tracker.time_tracker.doctype.time_tracker_session.time_tracker_session import TimeTrackerSession
		TimeTrackerSession.upsert(user, cache_data)

	frappe.response["message"] = "ok"


@frappe.whitelist(methods=["POST"])
def sync_heartbeat():
	user = frappe.session.user
	data = frappe.local.form_dict

	status = data.get("status", "Running").capitalize()
	now = frappe.utils.now()
	employee = _get_employee(user)

	# Read existing cache state to preserve started_at across heartbeats
	existing_raw = frappe.cache().hget(CACHE_KEY, user)
	existing = json.loads(existing_raw) if existing_raw else {}

	cache_data = {
		"status": status,
		"project": data.get("project") or existing.get("project"),
		"current_task": data.get("current_task") or existing.get("current_task"),
		"started_at": existing.get("started_at") or _to_mysql_datetime(data.get("started_at")) or now,
		"last_heartbeat": now,
		"machine_id": data.get("machine_id") or existing.get("machine_id"),
		"app_version": data.get("app_version") or existing.get("app_version"),
		"employee": employee or existing.get("employee"),
		"employee_name": _get_employee_name(user) if employee else existing.get("employee_name"),
	}

	_update_cache(user, cache_data)
	_create_log(user, "Heartbeat", {**cache_data, "timestamp": now})
	_publish_realtime(user, cache_data)

	if status in ("Running", "Stopped", "Idle"):
		from time_tracker.time_tracker.doctype.time_tracker_session.time_tracker_session import TimeTrackerSession
		TimeTrackerSession.upsert(user, cache_data)

	frappe.response["message"] = "ok"


@frappe.whitelist(methods=["POST"])
def sync_heartbeat_ws():
	"""Lightweight heartbeat via WebSocket — updates cache only, no log document."""
	user = frappe.session.user
	data = frappe.local.form_dict
	status = data.get("status", "Running").capitalize()
	now = frappe.utils.now()

	existing_raw = frappe.cache().hget(CACHE_KEY, user)
	existing = json.loads(existing_raw) if existing_raw else {}

	cache_data = {
		"status": status,
		"project": data.get("project") or existing.get("project"),
		"current_task": data.get("current_task") or existing.get("current_task"),
		"started_at": existing.get("started_at") or _to_mysql_datetime(data.get("started_at")) or now,
		"last_heartbeat": now,
		"machine_id": data.get("machine_id") or existing.get("machine_id"),
		"app_version": data.get("app_version") or existing.get("app_version"),
	}

	_update_cache(user, cache_data)
	_publish_realtime(user, cache_data)

	frappe.response["message"] = "ok"


@frappe.whitelist(methods=["POST"])
def create_timesheet_from_entries():
	data = frappe.local.form_dict
	entry_names = frappe.parse_json(data.get("entries", "[]"))
	company = data.get("company")

	if not entry_names or not company:
		frappe.throw(_("Entries and Company are required"))

	settings = frappe.get_single("Tracker Settings") if frappe.db.exists("Tracker Settings", "Tracker Settings") else frappe._dict()
	default_costing_rate = settings.get("costing_rate") or 0
	default_billing_rate = settings.get("billing_rate") or 0

	entries = frappe.get_all(
		"Time Tracker Entry",
		filters={"name": ("in", entry_names), "status": ("!=", "Timesheet Created")},
		fields=["name", "user", "employee", "project", "task", "activity_type",
				"description", "start_time", "end_time", "hours", "is_billable",
				"billing_rate", "billing_amount", "timesheet"],
	)

	if not entries:
		frappe.throw(_("No valid Time Tracker Entries found"))

	already_linked = [e.name for e in entries if e.timesheet]
	if already_linked:
		frappe.throw(_("Entries already linked to a Timesheet: {0}").format(", ".join(already_linked)))

	entries_by_user = {}
	for e in entries:
		entries_by_user.setdefault(e.user, []).append(e)

	created = []
	for user, user_entries in entries_by_user.items():
		ts = frappe.get_doc({
			"doctype": "Timesheet",
			"company": company,
			"user": user,
			"employee": user_entries[0].employee,
			"naming_series": "TS-.YYYY.-",
			"time_logs": [
				{
					"activity_type": e.activity_type,
					"from_time": e.start_time,
					"to_time": e.end_time,
					"hours": e.hours,
					"description": e.description,
					"project": e.project,
					"task": e.task,
					"is_billable": e.is_billable,
					"billing_rate": e.billing_rate or default_billing_rate,
					"billing_amount": e.billing_amount,
					"costing_rate": default_costing_rate,
				}
				for e in user_entries
			],
		})
		ts.insert(ignore_permissions=True)

		for row, e in zip(ts.time_logs, user_entries):
			frappe.db.set_value("Time Tracker Entry", e.name, {
				"timesheet": ts.name,
				"timesheet_detail": row.name,
				"status": "Timesheet Created",
			})

		created.append(ts.name)

	frappe.response["message"] = _("Timesheet(s) created: {0}").format(", ".join(created))
	frappe.response["timesheets"] = created


@frappe.whitelist(methods=["GET"])
def ping():
	"""Simple endpoint to verify the time_tracker app is installed."""
	return {"app": "time_tracker", "status": "ok"}


@frappe.whitelist(methods=["GET"])
def get_tracker_status():
	"""Return live tracker status for all users (for custom views)."""
	raw_map = frappe.cache().hgetall(CACHE_KEY) or {}
	result = {}
	for user, raw in raw_map.items():
		result[user] = json.loads(raw)
	return result