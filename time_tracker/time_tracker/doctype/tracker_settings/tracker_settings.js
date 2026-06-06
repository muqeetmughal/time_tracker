frappe.ui.form.on("Tracker Settings", {
	refresh(frm) {
		frm.set_query("company", () => ({ filters: { is_group: 0 } }));

		if (frm.doc.auto_create_timesheets) {
			frm.add_custom_button(__("Create Timesheets Now"), () => {
				frm.call({
					method: "create_timesheets_now",
					doc: frm.doc,
					callback(r) {
						frm.refresh();
					},
				});
			}).addClass("btn-primary");
		}
	},
});
