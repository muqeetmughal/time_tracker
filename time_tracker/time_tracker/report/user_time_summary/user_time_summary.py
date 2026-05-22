import frappe
from frappe import _
from frappe.utils import get_fullname


def execute(filters=None):
	columns = [
		{
			"fieldname": "user",
			"label": _("User"),
			"fieldtype": "Link",
			"options": "User",
			"width": 200,
		},
		{
			"fieldname": "full_name",
			"label": _("Full Name"),
			"fieldtype": "Data",
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
			"label": _("Entries"),
			"fieldtype": "Int",
			"width": 80,
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
			"fieldname": "projects_count",
			"label": _("Projects"),
			"fieldtype": "Int",
			"width": 80,
		},
	]

	conditions, values = get_conditions(filters)
	data = frappe.db.sql(
		"""
		SELECT
			user,
			ROUND(SUM(hours), 2) AS total_hours,
			COUNT(name) AS total_entries,
			ROUND(SUM(CASE WHEN is_billable = 1 THEN hours ELSE 0 END), 2) AS billable_hours,
			SUM(billing_amount) AS billing_amount,
			COUNT(DISTINCT project) AS projects_count
		FROM `tabTime Tracker Entry`
		WHERE docstatus < 2
			{conditions}
		GROUP BY user
		ORDER BY total_hours DESC
		""".format(conditions=conditions),
		values=values,
		as_dict=1,
	)

	for row in data:
		row["full_name"] = get_fullname(row["user"])

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
	if filters.get("user"):
		conditions += " AND user = %s"
		values.append(filters["user"])
	if filters.get("project"):
		conditions += " AND project = %s"
		values.append(filters["project"])

	return conditions, values
