import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{
			"fieldname": "task",
			"label": _("Task"),
			"fieldtype": "Link",
			"options": "Task",
			"width": 250,
		},
		{
			"fieldname": "task_name",
			"label": _("Task Subject"),
			"fieldtype": "Data",
			"width": 250,
		},
		{
			"fieldname": "project",
			"label": _("Project"),
			"fieldtype": "Link",
			"options": "Project",
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
			"fieldname": "unique_users",
			"label": _("Users"),
			"fieldtype": "Int",
			"width": 80,
		},
	]

	conditions, values = get_conditions(filters)
	data = frappe.db.sql(
		"""
		SELECT
			tte.task,
			ts.subject AS task_name,
			tte.project,
			ROUND(SUM(tte.hours), 2) AS total_hours,
			COUNT(tte.name) AS total_entries,
			ROUND(SUM(CASE WHEN tte.is_billable = 1 THEN tte.hours ELSE 0 END), 2) AS billable_hours,
			COUNT(DISTINCT tte.user) AS unique_users
		FROM `tabTime Tracker Entry` tte
		LEFT JOIN `tabTask` ts ON ts.name = tte.task
		WHERE tte.docstatus < 2
			AND tte.task IS NOT NULL
			{conditions}
		GROUP BY tte.task
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
		conditions += " AND tte.start_time >= %s"
		values.append(filters["from_date"])
	if filters.get("to_date"):
		conditions += " AND tte.start_time <= %s"
		values.append(filters["to_date"])
	if filters.get("project"):
		conditions += " AND tte.project = %s"
		values.append(filters["project"])
	if filters.get("task"):
		conditions += " AND tte.task = %s"
		values.append(filters["task"])
	if filters.get("user"):
		conditions += " AND tte.user = %s"
		values.append(filters["user"])

	return conditions, values
