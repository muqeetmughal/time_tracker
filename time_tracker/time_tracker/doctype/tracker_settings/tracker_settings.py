import frappe
from frappe import _
from frappe.model.document import Document


class TrackerSettings(Document):
	@frappe.whitelist()
	def create_timesheets_now(self):
		if not self.auto_create_timesheets:
			frappe.throw(_("Enable Auto Create Timesheets first"))

		if not self.company or not self.entries_status:
			frappe.throw(_("Company and Entry Statuses must be configured"))

		from time_tracker.tasks import _create_timesheets

		existing_statuses = [s.strip() for s in (self.entries_status or "").split("\n") if s.strip()]
		if "Completed" not in existing_statuses:
			self.entries_status = (self.entries_status or "") + "\nCompleted"

		created = _create_timesheets(self)

		if created:
			frappe.msgprint(_("Timesheets created: {0}").format(", ".join(created)))
		else:
			frappe.msgprint(_("No eligible entries found for Timesheet creation"))


def get_user_rates(user):
	settings = frappe.get_cached_doc("Tracker Settings")
	default_billing = settings.billing_rate or 0
	default_costing = settings.costing_rate or 0

	for row in settings.get("user_rates") or []:
		if row.user == user:
			return (row.billing_rate or default_billing, row.costing_rate or default_costing)

	return (default_billing, default_costing)
