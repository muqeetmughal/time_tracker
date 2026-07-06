# Copyright (c) 2026, Muqeet Mughal and contributors
# For license information, please see license.txt

"""Whitelisted endpoints backing the Tracker Dashboard Desk page.

Security model
--------------
The tracker doctypes grant standard read permission to ``System Manager`` only,
and all sync endpoints write with ``ignore_permissions=True``. A normal user can
therefore not read these doctypes directly. Every endpoint here resolves the
*target user* server-side via :func:`_resolve_user`:

* normal user  -> always forced to ``frappe.session.user`` (a spoofed ``user``
  argument is ignored);
* admin (the literal ``Administrator`` account) -> ``user`` argument or ``None``
  meaning "all".
"""

import json

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	get_datetime,
	get_fullname,
	getdate,
	now_datetime,
	nowdate,
)

CACHE_KEY = "tracker:status"
STALE_AFTER_SECONDS = 60
OFFLINE_AFTER_SECONDS = 300
DEFAULT_RANGE_DAYS = 7


# ---------------------------------------------------------------------------
#  Scoping helpers
# ---------------------------------------------------------------------------

def _is_admin() -> bool:
	# Only the literal Administrator account may view all users' data.
	return frappe.session.user == "Administrator"


def _resolve_user(requested_user):
	"""Return the user whose data may be returned.

	Admins may request any user, or ``None`` for the all-users aggregate.
	Everyone else is forced to themselves regardless of what they pass.
	"""
	if _is_admin():
		return requested_user or None
	return frappe.session.user


def _get_employee(user: str) -> str | None:
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _visible_users():
	"""Enabled users eligible for tracker views.

	Returns ``[{"name", "full_name"}, ...]`` of every enabled User, excluding only
	the literal ``Administrator`` and ``Guest`` accounts and disabled users (any
	``user_type`` — System or Website — is included). Used both for the admin user
	filter and the all-users live status.
	"""
	return frappe.get_all(
		"User",
		filters={
			"enabled": 1,
			"name": ("not in", ["Administrator", "Guest"]),
		},
		fields=["name", "full_name"],
		order_by="full_name asc",
	)


def _resolve_range(from_date, to_date):
	to_date = getdate(to_date) if to_date else getdate(nowdate())
	from_date = getdate(from_date) if from_date else add_days(to_date, -DEFAULT_RANGE_DAYS)
	return from_date, to_date


def _entry_conditions(user, from_date, to_date):
	"""Build a SQL WHERE fragment + values for `tabTime Tracker Entry`."""
	conditions = " AND start_time >= %(from_date)s AND start_time < %(to_date_next)s"
	values = {
		"from_date": str(from_date),
		"to_date_next": str(add_days(to_date, 1)),
	}
	if user:
		conditions += " AND `user` = %(user)s"
		values["user"] = user
	return conditions, values


# ---------------------------------------------------------------------------
#  Endpoints
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_context():
	"""Bootstrap data for the page: whether the viewer is an admin."""
	return {
		"is_admin": _is_admin(),
		"current_user": frappe.session.user,
		"default_from": str(add_days(getdate(nowdate()), -DEFAULT_RANGE_DAYS)),
		"default_to": nowdate(),
	}


@frappe.whitelist()
def get_dashboard_users():
	"""Enabled login users for the admin dropdown (no Guest/disabled). Admins only."""
	if not _is_admin():
		return []

	return [
		{"user": u.name, "full_name": u.full_name or get_fullname(u.name)}
		for u in _visible_users()
	]


@frappe.whitelist()
def get_summary(user=None, from_date=None, to_date=None):
	user = _resolve_user(user)
	from_date, to_date = _resolve_range(from_date, to_date)
	conditions, values = _entry_conditions(user, from_date, to_date)

	row = frappe.db.sql(
		"""
		SELECT
			ROUND(COALESCE(SUM(hours), 0), 2) AS total_hours,
			ROUND(COALESCE(SUM(CASE WHEN is_billable = 1 THEN hours ELSE 0 END), 0), 2) AS billable_hours,
			COALESCE(SUM(billing_amount), 0) AS billing_amount,
			COUNT(name) AS total_entries,
			COALESCE(SUM(keyboard_count), 0) AS keyboard_count,
			COALESCE(SUM(mouse_click_count), 0) AS mouse_click_count,
			COALESCE(SUM(screenshots_count), 0) AS screenshots_count,
			COALESCE(SUM(camshots_count), 0) AS camshots_count,
			COUNT(DISTINCT `user`) AS active_users
		FROM `tabTime Tracker Entry`
		WHERE docstatus < 2 {conditions}
		""".format(conditions=conditions),
		values=values,
		as_dict=True,
	)
	return row[0] if row else {}


@frappe.whitelist()
def get_trend(user=None, from_date=None, to_date=None):
	user = _resolve_user(user)
	from_date, to_date = _resolve_range(from_date, to_date)
	conditions, values = _entry_conditions(user, from_date, to_date)

	rows = frappe.db.sql(
		"""
		SELECT DATE(start_time) AS date, ROUND(COALESCE(SUM(hours), 0), 2) AS hours
		FROM `tabTime Tracker Entry`
		WHERE docstatus < 2 AND start_time IS NOT NULL {conditions}
		GROUP BY DATE(start_time)
		ORDER BY DATE(start_time)
		""".format(conditions=conditions),
		values=values,
		as_dict=True,
	)

	# Fill missing days with 0 so the chart has a continuous x-axis.
	by_date = {str(r["date"]): r["hours"] for r in rows}
	series = []
	cursor = from_date
	while cursor <= to_date:
		key = str(cursor)
		series.append({"date": key, "hours": by_date.get(key, 0)})
		cursor = add_days(cursor, 1)
	return series


@frappe.whitelist()
def get_live_status(user=None):
	"""Live tracker status, scoped to the resolved user.

	For an admin viewing everyone, every enabled login user is listed so the
	whole team is visible at a glance; users without live cache data (tracker
	never started, or app closed long enough that the entry expired) show as
	``Offline``. A normal user — or an admin filtered to one user — sees just
	that user.
	"""
	target = _resolve_user(user)

	# Decode the Redis cache into {username: data}.
	raw_map = frappe.cache().hgetall(CACHE_KEY) or {}
	cache_by_user = {}
	for user_key, raw in raw_map.items():
		uname = user_key.decode("utf-8") if isinstance(user_key, bytes) else str(user_key)
		raw_str = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
		try:
			cache_by_user[uname] = json.loads(raw_str)
		except (ValueError, TypeError):
			continue

	# Determine the set of users to report on.
	if target:
		names = {target: get_fullname(target)}
	else:
		names = {u.name: (u.full_name or get_fullname(u.name)) for u in _visible_users()}
		# Include any cached user that isn't in the visible set (e.g. a website
		# user that synced) so an active tracker is never hidden.
		for uname in cache_by_user:
			names.setdefault(uname, get_fullname(uname))

	rows = []
	for uname, full_name in names.items():
		data = cache_by_user.get(uname) or {}

		last_heartbeat = data.get("last_heartbeat")
		age = None
		if last_heartbeat:
			age = (now_datetime() - get_datetime(last_heartbeat)).total_seconds()

		status = str(data.get("status") or "")
		if not data or age is None or age > OFFLINE_AFTER_SECONDS:
			# No live data, or the last heartbeat is too old -> not active.
			status = "Offline"
		elif age > STALE_AFTER_SECONDS and status == "Running":
			status = "Stale"
		elif not status:
			status = "Offline"

		rows.append({
			"user": uname,
			"employee_name": str(data.get("employee_name") or full_name or ""),
			"status": status,
			"current_task": str(data.get("current_task") or ""),
			"project": str(data.get("project") or ""),
			"started_at": str(data.get("started_at") or ""),
			"last_heartbeat": str(last_heartbeat or ""),
			"last_seen_seconds": age,
			"machine_id": str(data.get("machine_id") or ""),
			"app_version": str(data.get("app_version") or ""),
		})

	# Active trackers first, then by name.
	rows.sort(key=lambda r: (r["status"] != "Running", r["user"]))
	return rows


@frappe.whitelist()
def get_screenshots(user=None, from_date=None, to_date=None, media_type=None, limit=60, start=0):
	user = _resolve_user(user)
	from_date, to_date = _resolve_range(from_date, to_date)

	conditions = " AND e.start_time >= %(from_date)s AND e.start_time < %(to_date_next)s"
	values = {
		"from_date": str(from_date),
		"to_date_next": str(add_days(to_date, 1)),
		"limit": int(limit),
		"start": int(start),
	}
	if user:
		conditions += " AND e.`user` = %(user)s"
		values["user"] = user
	if media_type:
		conditions += " AND m.media_type = %(media_type)s"
		values["media_type"] = media_type

	rows = frappe.db.sql(
		"""
		SELECT
			m.file AS file,
			m.media_type AS media_type,
			m.status AS status,
			m.filename AS filename,
			e.name AS entry,
			e.`user` AS user,
			e.start_time AS timestamp
		FROM `tabActivity Media` m
		INNER JOIN `tabTime Tracker Entry` e ON m.parent = e.name
		WHERE 1=1 {conditions}
		ORDER BY e.start_time DESC
		LIMIT %(limit)s OFFSET %(start)s
		""".format(conditions=conditions),
		values=values,
		as_dict=True,
	)
	for r in rows:
		r["has_file"] = bool(r.get("file"))
	return rows


@frappe.whitelist(methods=["POST"])
def create_manual_entry():
	"""Create a manual time entry from the Tracker Dashboard form."""
	data = frappe.local.form_dict
	user = frappe.session.user

	start_time = data.get("start_time")
	end_time = data.get("end_time")

	if not start_time or not end_time:
		frappe.throw(_("Start time and end time are required"))

	if not data.get("project"):
		frappe.throw(_("Project is required"))

	start_dt = get_datetime(start_time)
	end_dt = get_datetime(end_time)
	duration_seconds = (end_dt - start_dt).total_seconds()

	if duration_seconds <= 0:
		frappe.throw(_("End time must be after start time"))

	employee = _get_employee(user)

	doc = frappe.get_doc({
		"doctype": "Time Tracker Entry",
		"project": data.get("project"),
		"task": data.get("task"),
		"activity_type": data.get("activity_type"),
		"description": data.get("description"),
		"start_time": start_time,
		"end_time": end_time,
		"duration_seconds": int(duration_seconds),
		"is_billable": int(data.get("is_billable", 1)),
		"source": "Web",
		"status": "Completed",
		"user": user,
		"employee": employee,
	})
	doc.insert(ignore_permissions=True)

	return {"name": doc.name, "hours": doc.hours}


@frappe.whitelist()
def get_entries(user=None, from_date=None, to_date=None, limit=50, start=0):
	user = _resolve_user(user)
	from_date, to_date = _resolve_range(from_date, to_date)

	filters = {
		"docstatus": ("<", 2),
		"start_time": ("between", [str(from_date), str(add_days(to_date, 1))]),
	}
	if user:
		filters["user"] = user

	return frappe.get_all(
		"Time Tracker Entry",
		filters=filters,
		fields=[
			"name", "user", "employee", "project", "task", "activity_type",
			"status", "source", "start_time", "end_time", "hours",
			"duration_seconds", "keyboard_count", "mouse_click_count",
			"screenshots_count", "camshots_count", "is_billable", "billing_amount",
		],
		order_by="start_time desc",
		limit_page_length=int(limit),
		limit_start=int(start),
	)
