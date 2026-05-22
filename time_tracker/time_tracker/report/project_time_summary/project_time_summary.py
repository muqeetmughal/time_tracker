import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{
			"fieldname": "project",
			"label": _("Project"),
			"fieldtype": "Link",
			"options": "Project",
			"width": 200,
		},
		{
			"fieldname": "total_hours",
			"label": _("Total Hours"),
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"fieldname": "total_entries",
			"label": _("Total Entries"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "billable_hours",
			"label": _("Billable Hours"),
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"fieldname": "billing_amount",
			"label": _("Billing Amount"),
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"fieldname": "unique_users",
			"label": _("Unique Users"),
			"fieldtype": "Int",
			"width": 120,
		},
	]

	conditions, values = get_conditions(filters)
	data = frappe.db.sql(
		"""
		SELECT
			project,
			ROUND(SUM(hours), 2) AS total_hours,
			COUNT(name) AS total_entries,
			ROUND(SUM(CASE WHEN is_billable = 1 THEN hours ELSE 0 END), 2) AS billable_hours,
			SUM(billing_amount) AS billing_amount,
			COUNT(DISTINCT user) AS unique_users
		FROM `tabTime Tracker Entry`
		WHERE docstatus < 2
			{conditions}
		GROUP BY project
		ORDER BY total_hours DESC
		""".format(conditions=conditions),
		values=values,
		as_dict=1,
	)

	return columns, data


def get_conditions(filters):
	conditions = ""
	values = []
	if not filters:
		return conditions, values

	if filters.get("from_date"):
		conditions += " AND start_time >= %s"
		values.append(filters["from_date"])
	if filters.get("to_date"):
		conditions += " AND start_time <= %s"
		values.append(filters["to_date"])
	if filters.get("project"):
		conditions += " AND project = %s"
		values.append(filters["project"])
	if filters.get("status"):
		conditions += " AND status = %s"
		values.append(filters["status"])

	return conditions, values
