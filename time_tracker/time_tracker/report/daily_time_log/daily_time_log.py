import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{
			"fieldname": "date",
			"label": _("Date"),
			"fieldtype": "Date",
			"width": 130,
		},
		{
			"fieldname": "user",
			"label": _("User"),
			"fieldtype": "Link",
			"options": "User",
			"width": 180,
		},
		{
			"fieldname": "project",
			"label": _("Project"),
			"fieldtype": "Link",
			"options": "Project",
			"width": 180,
		},
		{
			"fieldname": "task",
			"label": _("Task"),
			"fieldtype": "Link",
			"options": "Task",
			"width": 200,
		},
		{
			"fieldname": "activity_type",
			"label": _("Activity Type"),
			"fieldtype": "Link",
			"options": "Activity Type",
			"width": 130,
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "hours",
			"label": _("Hours"),
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"fieldname": "description",
			"label": _("Description"),
			"fieldtype": "Small Text",
			"width": 250,
		},
	]

	conditions, values = get_conditions(filters)
	data = frappe.db.sql(
		"""
		SELECT
			DATE(start_time) AS date,
			user,
			project,
			task,
			activity_type,
			status,
			hours,
			description
		FROM `tabTime Tracker Entry`
		WHERE docstatus < 2
			{conditions}
		ORDER BY start_time DESC
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
		conditions += " AND DATE(start_time) >= %s"
		values.append(filters["from_date"])
	if filters.get("to_date"):
		conditions += " AND DATE(start_time) <= %s"
		values.append(filters["to_date"])
	if filters.get("user"):
		conditions += " AND user = %s"
		values.append(filters["user"])
	if filters.get("project"):
		conditions += " AND project = %s"
		values.append(filters["project"])
	if filters.get("task"):
		conditions += " AND task = %s"
		values.append(filters["task"])
	if filters.get("status"):
		conditions += " AND status = %s"
		values.append(filters["status"])

	return conditions, values
