// Copyright (c) 2026, Muqeet Mughal and contributors
// For license information, please see license.txt

frappe.realtime.on("tracker:status_update", function (data) {
	frappe.show_alert({
		message: __("{0} tracker is {1}", [data.user, data.status]),
		indicator: data.status === "Running" ? "green" : "gray",
	});

	if (cur_list && cur_list.doctype === "User Tracker Status") {
		cur_list.refresh();
	}
});
