// Copyright (c) 2026, Muqeet Mughal and contributors
// For license information, please see license.txt

frappe.ui.form.on("Time Tracker Entry", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.disable_form();
		}
	},
});
