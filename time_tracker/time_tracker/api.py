import frappe
from frappe import _
from frappe.utils import cint


TIME_TRACKER_DOCTYPE = "Time Tracker Entry"


class TimeTrackerSyncError(frappe.ValidationError):
	pass


@frappe.whitelist(methods=["POST"])
def sync_time_tracker_record():
	data = frappe.local.form_dict

	STATUS_MAP = {
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
		employee = frappe.db.get_value(
			"Employee", {"user_id": frappe.session.user}, "name"
		)
		print(f"Employee for user {frappe.session.user}: {employee}")
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
