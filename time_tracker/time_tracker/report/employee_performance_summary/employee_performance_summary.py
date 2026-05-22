import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{
			"fieldname": "employee",
			"label": _("Employee"),
			"fieldtype": "Link",
			"options": "Employee",
			"width": 150,
		},
		{
			"fieldname": "employee_name",
			"label": _("Employee Name"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "user",
			"label": _("User"),
			"fieldtype": "Link",
			"options": "User",
			"width": 180,
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
			"fieldname": "avg_daily_hours",
			"label": _("Avg Daily Hours"),
			"fieldtype": "Float",
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
			tte.employee,
			emp.employee_name,
			tte.user,
			ROUND(SUM(tte.hours), 2) AS total_hours,
			COUNT(tte.name) AS total_entries,
			ROUND(SUM(CASE WHEN tte.is_billable = 1 THEN tte.hours ELSE 0 END), 2) AS billable_hours,
			SUM(tte.billing_amount) AS billing_amount,
			COUNT(DISTINCT tte.project) AS projects_count
		FROM `tabTime Tracker Entry` tte
		LEFT JOIN `tabEmployee` emp ON emp.name = tte.employee
		WHERE tte.docstatus < 2
			AND tte.employee IS NOT NULL
			{conditions}
		GROUP BY tte.employee
		ORDER BY total_hours DESC
		""".format(conditions=conditions),
		values=values,
		as_dict=1,
	)

	for row in data:
		row["avg_daily_hours"] = compute_avg_daily(row.get("employee"), filters)

	return columns, data


def compute_avg_daily(employee, filters):
	conditions = "AND employee = %s"
	values = [employee]

	if filters:
		if filters.get("from_date"):
			conditions += " AND DATE(start_time) >= %s"
			values.append(filters["from_date"])
		if filters.get("to_date"):
			conditions += " AND DATE(start_time) <= %s"
			values.append(filters["to_date"])

	result = frappe.db.sql(
		"""
		SELECT
			ROUND(SUM(hours) / COUNT(DISTINCT DATE(start_time)), 2) AS avg_hours
		FROM `tabTime Tracker Entry`
		WHERE docstatus < 2
			AND employee IS NOT NULL
			{conditions}
		""".format(conditions=conditions),
		values=values,
		as_dict=1,
	)
	return result[0].get("avg_hours", 0) if result else 0


def get_conditions(filters):
	conditions = ""
	values = []
	if not filters:
		return conditions, values

	if filters.get("from_date"):
		conditions += " AND tte.start_time >= %s"
		values.append(filters["from_date"])
	if filters.get("to_date"):
		conditions += " AND tte.start_time <= %s"
		values.append(filters["to_date"])
	if filters.get("employee"):
		conditions += " AND tte.employee = %s"
		values.append(filters["employee"])
	if filters.get("project"):
		conditions += " AND tte.project = %s"
		values.append(filters["project"])

	return conditions, values
