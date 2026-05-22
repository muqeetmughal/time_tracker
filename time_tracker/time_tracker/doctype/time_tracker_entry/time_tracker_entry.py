# Copyright (c) 2026, Muqeet Mughal and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TimeTrackerEntry(Document):
	def validate(self):
		if self.get_doc_before_save():
			frappe.throw(_("Time Tracker Entry cannot be modified after creation"))
