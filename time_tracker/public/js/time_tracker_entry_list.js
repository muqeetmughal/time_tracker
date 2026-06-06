frappe.listview_settings["Time Tracker Entry"] = {
	add_fields: ["status", "timesheet", "user", "project", "hours"],
	onload(listview) {
		listview.page.add_actions_menu_item(__("Create Timesheet"), () => {
			const all_items = listview.get_checked_items();
			const valid = all_items.filter(e => e.status !== "Timesheet Created");
			const skipped = all_items.length - valid.length;

			if (!valid.length) {
				frappe.msgprint(__("All selected entries already have a Timesheet."));
				return;
			}

			const docnames = valid.map(e => e.name);
			show_create_timesheet_dialog(docnames, valid, listview, skipped);
		});
	},
};

function show_create_timesheet_dialog(docnames, items, listview, skipped) {
	const title = skipped
		? __("Create Timesheet from {0} Entries ({1} skipped)", [docnames.length, skipped])
		: __("Create Timesheet from {0} Entries", [docnames.length]);

	const d = new frappe.ui.Dialog({
		title: title,
		fields: [
			{
				fieldname: "company",
				fieldtype: "Link",
				options: "Company",
				label: __("Company"),
				reqd: 1,
			},
			{
				fieldname: "entries_section",
				fieldtype: "Section Break",
				label: __("Selected Entries"),
			},
			{
				fieldname: "entries_html",
				fieldtype: "HTML",
			},
		],
		primary_action_label: __("Create Timesheet"),
		primary_action(values) {
			d.set_message(__("Creating Timesheet..."));
			d.get_primary_btn().prop("disabled", true);

			frappe.call({
				method: "time_tracker.time_tracker.api.create_timesheet_from_entries",
				args: {
					entries: docnames,
					company: values.company,
				},
				callback(r) {
					if (r.message) {
						frappe.msgprint({
							title: __("Timesheet Created"),
							indicator: "green",
							message: r.message,
						});
						d.hide();
						listview.refresh();
					}
				},
				error() {
					d.get_primary_btn().prop("disabled", false);
				},
			});
		},
	});

	const project_ids = [...new Set(items.filter(e => e.project).map(e => e.project))];

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Project",
			filters: { name: ["in", project_ids] },
			fields: ["name", "project_name"],
			limit_page_length: project_ids.length,
		},
		callback(r) {
			const project_map = {};
			(r.message || []).forEach(p => { project_map[p.name] = p.project_name; });

			const html = `
				<div style="max-height: 200px; overflow-y: auto;">
					<table class="table table-bordered table-hover">
						<thead>
							<tr>
								<th>${__("Entry")}</th>
								<th>${__("User")}</th>
								<th>${__("Project")}</th>
								<th>${__("Hours")}</th>
							</tr>
						</thead>
						<tbody>
							${items.map(e => `
								<tr>
									<td>${e.name}</td>
									<td>${e.user || ""}</td>
									<td>${project_map[e.project] || e.project || ""}</td>
									<td>${e.hours || 0}</td>
								</tr>
							`).join("")}
						</tbody>
					</table>
				</div>
			`;
			d.fields_dict.entries_html.$wrapper.html(html);
		},
	});

	d.show();
}