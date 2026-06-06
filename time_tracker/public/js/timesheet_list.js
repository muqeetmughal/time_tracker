frappe.listview_settings["Timesheet"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Create Timesheets Now"), () => {
			frappe.call({
				method: "time_tracker.time_tracker.api.create_timesheets_from_settings",
				args: {},
				callback(r) {
					frappe.msgprint({
						title: __("Timesheets Created"),
						indicator: "green",
						message: r.message || __("No eligible entries found"),
					});
					listview.refresh();
				},
			});
		});
	},
};
