# Copyright (c) 2026, Muqeet Mughal and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TimeTrackerEntry(Document):
	def validate(self):
		self.calculate_hours()
		self.calculate_billing_amount()

	def calculate_hours(self):
		"""Derive hours from the tracked duration so dashboards/reports and the
		Timesheet rows have a value (the sync only sends duration_seconds)."""
		self.hours = (self.duration_seconds or 0) / 3600.0

	def calculate_billing_amount(self):
		"""billing_amount = hours x rate. When no rate is set on the entry, resolve
		it per-user from Tracker Settings (per-user override -> global default), so
		the dashboard and Timesheets bill each user at their own rate."""
		if not self.is_billable:
			self.billing_amount = 0
			return

		if not self.billing_rate:
			from time_tracker.time_tracker.doctype.tracker_settings.tracker_settings import get_user_rates

			billing_rate, _costing_rate = get_user_rates(self.user)
			self.billing_rate = billing_rate

		self.billing_amount = (self.hours or 0) * (self.billing_rate or 0)