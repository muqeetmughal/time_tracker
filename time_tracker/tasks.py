import frappe
from frappe import _
from frappe.utils import now_datetime


def _create_timesheets(settings, update_last_run=True):
	from time_tracker.time_tracker.doctype.tracker_settings.tracker_settings import get_user_rates

	statuses = [s.strip() for s in settings.entries_status.split("\n") if s.strip()]

	entries = frappe.get_all(
		"Time Tracker Entry",
		filters={
			"status": ("in", statuses),
			"timesheet": ("is", "not set"),
		},
		fields=["name", "user", "employee", "project", "task", "activity_type",
				"description", "start_time", "end_time", "hours", "is_billable",
				"billing_rate", "billing_amount"],
	)

	if not entries:
		return []

	entries_by_user = {}
	for e in entries:
		entries_by_user.setdefault(e.user, []).append(e)

	created = []
	for user, user_entries in entries_by_user.items():
		user_billing_rate, user_costing_rate = get_user_rates(user)
		try:
			ts = frappe.get_doc({
				"doctype": "Timesheet",
				"company": settings.company,
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
						"billing_rate": e.billing_rate or user_billing_rate,
						"billing_amount": e.billing_amount,
						"costing_rate": user_costing_rate,
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
		except Exception:
			frappe.log_error(
				f"Failed to auto-create Timesheet for user {user}",
				"Auto Timesheet Creation",
			)

	if created and update_last_run:
		frappe.db.set_value("Tracker Settings", "Tracker Settings", "last_run", now_datetime())
		frappe.log_error(
			_("Auto-created Timesheets: {0}").format(", ".join(created)),
			"Auto Timesheet Creation",
		)

	return created


def auto_create_timesheets():
	settings = frappe.get_single("Tracker Settings")
	if not settings.auto_create_timesheets:
		return

	if not settings.company or not settings.entries_status:
		return

	now = now_datetime()
	last_run = settings.last_run

	if last_run:
		if settings.frequency == "Hourly" and (now - last_run).total_seconds() < 3600:
			return
		elif settings.frequency == "Daily" and (now - last_run).days < 1:
			return
		elif settings.frequency == "Weekly" and (now - last_run).days < 7:
			return
		elif settings.frequency == "Monthly" and (now - last_run).days < 30:
			return

	_create_timesheets(settings)


def unlink_timesheet_entries(doc, method):
	entries = frappe.get_all(
		"Time Tracker Entry",
		filters={"timesheet": doc.name},
		fields=["name"],
	)
	for e in entries:
		frappe.db.set_value("Time Tracker Entry", e.name, {
			"timesheet": None,
			"timesheet_detail": None,
			"status": "Completed",
		})
