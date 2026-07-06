frappe.pages['tracker-dashboard'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Tracker Dashboard'),
		single_column: true,
	});
	frappe.tracker_dashboard = new TrackerDashboard(page);
};

frappe.pages['tracker-dashboard'].on_page_show = function () {
	if (frappe.tracker_dashboard) frappe.tracker_dashboard.refresh();
};

const API = 'time_tracker.time_tracker.dashboard';

const STATUS_COLORS = {
	Running: '#22c55e',
	Idle: '#f59e0b',
	Paused: '#f59e0b',
	Stale: '#eab308',
	Offline: '#94a3b8',
	Stopped: '#94a3b8',
	Error: '#ef4444',
	Completed: '#6366f1',
	Submitted: '#0ea5e9',
	Approved: '#22c55e',
	Draft: '#94a3b8',
};

const CARD_THEMES = [
	{ key: 'total_hours', label: 'Total Hours', icon: 'fa-clock-o', grad: ['#6366f1', '#8b5cf6'], fmt: (v) => format_number(v || 0, null, 2) },
	{ key: 'billable_hours', label: 'Billable Hours', icon: 'fa-hourglass-half', grad: ['#0ea5e9', '#22d3ee'], fmt: (v) => format_number(v || 0, null, 2) },
	{ key: 'billing_amount', label: 'Billing Amount', icon: 'fa-money', grad: ['#10b981', '#34d399'], fmt: (v) => format_currency(v || 0) },
	{ key: 'total_entries', label: 'Entries', icon: 'fa-list', grad: ['#f59e0b', '#fbbf24'], fmt: (v) => v || 0 },
	{ key: 'keyboard_count', label: 'Keyboard', icon: 'fa-keyboard-o', grad: ['#ec4899', '#f472b6'], fmt: (v) => format_number(v || 0) },
	{ key: 'mouse_click_count', label: 'Mouse Clicks', icon: 'fa-mouse-pointer', grad: ['#8b5cf6', '#a78bfa'], fmt: (v) => format_number(v || 0) },
	{ key: 'screenshots_count', label: 'Screenshots', icon: 'fa-camera', grad: ['#06b6d4', '#67e8f9'], fmt: (v) => format_number(v || 0) },
	{ key: 'active_users', label: 'Active Users', icon: 'fa-users', grad: ['#f43f5e', '#fb7185'], adminOnly: true, fmt: (v) => v || 0 },
];

class TrackerDashboard {
	constructor(page) {
		this.page = page;
		// Only the Administrator account gets the all-users view + user picker.
		this.is_admin = frappe.session.user === 'Administrator';
		this.selected_user = null;
		this.trend_chart = null;
		this.screenshot_start = 0;
		this.screenshot_page_size = 60;

		this.inject_styles();
		this.make_layout();
		this.make_controls();
		this.bind_realtime();
		this.refresh();
	}

	make_layout() {
		this.page.main.html(`
			<div class="tracker-dashboard">
				<div class="td-toolbar">
					<div class="td-toolbar-controls"></div>
				</div>
				<div class="td-cards" data-panel="summary">${this.skeleton_cards()}</div>
				<div class="td-grid">
					<div class="td-panel td-col-2">
						<div class="td-panel-head"><span class="td-dot td-dot-indigo"></span>${__('Hours Trend')}</div>
						<div class="td-chart" data-panel="trend"></div>
					</div>
					<div class="td-panel">
						<div class="td-panel-head"><span class="td-dot td-dot-green td-pulse"></span>${__('Live Status')}</div>
						<div class="td-live" data-panel="live"></div>
					</div>
				</div>
				<div class="td-panel">
					<div class="td-panel-head"><span class="td-dot td-dot-cyan"></span>${__('Screenshots')}</div>
					<div class="td-gallery" data-panel="gallery"></div>
					<div class="td-gallery-more"></div>
				</div>
				<div class="td-panel">
					<div class="td-panel-head"><span class="td-dot td-dot-amber"></span>${__('Time Entries')}</div>
					<div class="td-table-wrap" data-panel="entries"></div>
				</div>
			</div>
		`);

		this.$controls = this.page.main.find('.td-toolbar-controls');
		this.$summary = this.page.main.find('[data-panel="summary"]');
		this.$trend = this.page.main.find('[data-panel="trend"]');
		this.$live = this.page.main.find('[data-panel="live"]');
		this.$gallery = this.page.main.find('[data-panel="gallery"]');
		this.$gallery_more = this.page.main.find('.td-gallery-more');
		this.$entries = this.page.main.find('[data-panel="entries"]');
	}

	make_controls() {
		const today = frappe.datetime.get_today();
		const week_ago = frappe.datetime.add_days(today, -7);

		const $from = $('<div class="td-control"></div>').appendTo(this.$controls);
		this.from_ctrl = frappe.ui.form.make_control({
			df: { fieldtype: 'Date', label: __('From'), fieldname: 'from_date', change: () => this.refresh() },
			parent: $from, render_input: true,
		});
		this.from_ctrl.set_value(week_ago);

		const $to = $('<div class="td-control"></div>').appendTo(this.$controls);
		this.to_ctrl = frappe.ui.form.make_control({
			df: { fieldtype: 'Date', label: __('To'), fieldname: 'to_date', change: () => this.refresh() },
			parent: $to, render_input: true,
		});
		this.to_ctrl.set_value(today);

		if (this.is_admin) {
			const $user = $('<div class="td-control td-control-user"></div>').appendTo(this.$controls);
			this.user_ctrl = frappe.ui.form.make_control({
				df: {
					fieldtype: 'Link', label: __('User'), fieldname: 'user', options: 'User',
					placeholder: __('All users'),
					change: () => {
						this.selected_user = this.user_ctrl.get_value() || null;
						this.refresh();
					},
				},
				parent: $user, render_input: true,
			});
		}

		const $btn = $('<button class="btn btn-sm btn-primary td-manual-btn">')
			.html('<i class="fa fa-plus"></i> ' + __('Manual Entry'))
			.appendTo(this.$controls)
			.on('click', () => this.open_manual_entry_dialog());

		this.page.set_primary_action(__('Refresh'), () => this.refresh(), 'refresh');
	}

	bind_realtime() {
		frappe.realtime.on('tracker:status_update', () => {
			clearTimeout(this._live_timer);
			this._live_timer = setTimeout(() => this.load_live(), 1500);
		});
		this._poll = setInterval(() => this.load_live(), 30000);
	}

	get_filters() {
		return {
			user: this.selected_user || null,
			from_date: this.from_ctrl ? this.from_ctrl.get_value() : null,
			to_date: this.to_ctrl ? this.to_ctrl.get_value() : null,
		};
	}

	refresh() {
		this.screenshot_start = 0;
		this.load_summary();
		this.load_trend();
		this.load_live();
		this.load_screenshots(true);
		this.load_entries();
	}

	// ---------------- panels ----------------
	load_summary() {
		frappe.call({ method: `${API}.get_summary`, args: this.get_filters() }).then((r) => {
			const d = r.message || {};
			const html = CARD_THEMES.filter((c) => !c.adminOnly || (this.is_admin && !this.selected_user))
				.map((c, i) => `
					<div class="td-card" style="animation-delay:${i * 60}ms">
						<div class="td-card-icon" style="background:linear-gradient(135deg,${c.grad[0]},${c.grad[1]})">
							<i class="fa ${c.icon}"></i>
						</div>
						<div class="td-card-body">
							<div class="td-card-value">${c.fmt(d[c.key])}</div>
							<div class="td-card-label">${__(c.label)}</div>
						</div>
						<div class="td-card-bar" style="background:linear-gradient(90deg,${c.grad[0]},${c.grad[1]})"></div>
					</div>`).join('');
			this.$summary.html(html);
		});
	}

	load_trend() {
		frappe.call({ method: `${API}.get_trend`, args: this.get_filters() }).then((r) => {
			const data = r.message || [];
			const chart_data = {
				labels: data.map((d) => frappe.datetime.str_to_user(d.date).slice(0, 5)),
				datasets: [{ name: __('Hours'), values: data.map((d) => d.hours), chartType: 'bar' }],
			};
			if (this.trend_chart) {
				this.trend_chart.update(chart_data);
			} else {
				this.trend_chart = new frappe.Chart(this.$trend.get(0), {
					data: chart_data, type: 'bar', height: 240,
					colors: ['#6366f1'], barOptions: { spaceRatio: 0.4 },
					axisOptions: { xIsSeries: true }, animate: true,
				});
			}
		});
	}

	load_live() {
		frappe.call({ method: `${API}.get_live_status`, args: { user: this.selected_user || null } }).then((r) => {
			const rows = r.message || [];
			if (!rows.length) {
				this.$live.html(this.empty_state('fa-signal', __('No active trackers right now.')));
				return;
			}
			this.$live.html(rows.map((row) => {
				const color = STATUS_COLORS[row.status] || '#94a3b8';
				const seen = row.last_seen_seconds != null ? this.humanize(row.last_seen_seconds) : '—';
				const running = row.status === 'Running';
				return `
					<div class="td-live-row">
						<div class="td-live-user">
							<span class="td-status-dot ${running ? 'td-pulse' : ''}" style="background:${color}"></span>
							<div>
								<div class="td-live-name">${frappe.utils.escape_html(row.employee_name || row.user || '')}</div>
								<div class="td-live-sub">${frappe.utils.escape_html(row.project || __('No project'))}</div>
							</div>
						</div>
						<div class="td-live-meta">
							<span class="td-badge" style="color:${color};background:${color}1a">${frappe.utils.escape_html(row.status || '—')}</span>
							<span class="td-live-seen">${seen}</span>
						</div>
					</div>`;
			}).join(''));
		});
	}

	load_screenshots(reset) {
		if (reset) { this.screenshot_start = 0; }
		const token = (this._ss_token = (this._ss_token || 0) + 1);
		const args = Object.assign(this.get_filters(), { limit: this.screenshot_page_size, start: this.screenshot_start });
		frappe.call({ method: `${API}.get_screenshots`, args }).then((r) => {
			if (token !== this._ss_token) return;
			const rows = r.message || [];
			if (reset) this.$gallery.empty();
			if (!rows.length && this.screenshot_start === 0) {
				this.$gallery.html(this.empty_state('fa-camera', __('No screenshots in this range.')));
				this.$gallery_more.empty();
				return;
			}
			rows.forEach((row, i) => {
				const statusColor = STATUS_COLORS[row.status] || '#94a3b8';
				const thumb = row.has_file
					? `<img loading="lazy" src="${frappe.utils.escape_html(row.file)}" />`
					: `<div class="td-shot-placeholder"><i class="fa fa-image"></i><span>${__('No image')}</span></div>`;
				const $tile = $(`
					<div class="td-shot" style="animation-delay:${(i % 12) * 40}ms" title="${frappe.utils.escape_html(row.filename || '')}">
						${thumb}
						<div class="td-shot-meta">
							<span class="td-shot-type">${frappe.utils.escape_html(row.media_type || '')}</span>
							<span class="td-badge-sm" style="color:${statusColor};background:${statusColor}1a">${frappe.utils.escape_html(row.status || '')}</span>
						</div>
					</div>`);
				if (row.has_file) $tile.on('click', () => this.preview_image(row));
				this.$gallery.append($tile);
			});
			this.screenshot_start += rows.length;
			this.$gallery_more.empty();
			if (rows.length === this.screenshot_page_size) {
				$(`<button class="btn btn-sm td-loadmore">${__('Load more')}</button>`)
					.appendTo(this.$gallery_more).on('click', () => this.load_screenshots(false));
			}
		});
	}

	preview_image(row) {
		const d = new frappe.ui.Dialog({ title: row.filename || __('Screenshot'), size: 'large' });
		$(`<div style="text-align:center">
				<img src="${frappe.utils.escape_html(row.file)}" style="max-width:100%;border-radius:8px" />
				<div class="text-muted" style="margin-top:8px">
					${frappe.utils.escape_html(row.user || '')} · ${frappe.datetime.str_to_user(row.timestamp) || ''}
				</div>
			</div>`).appendTo(d.body);
		d.show();
	}

	load_entries() {
		frappe.call({ method: `${API}.get_entries`, args: Object.assign(this.get_filters(), { limit: 100 }) }).then((r) => {
			const rows = r.message || [];
			if (!rows.length) {
				this.$entries.html(this.empty_state('fa-list', __('No time entries in this range.')));
				return;
			}
			const showUser = this.is_admin && !this.selected_user;
			const body = rows.map((row) => {
				const color = STATUS_COLORS[row.status] || '#6366f1';
				return `
				<tr>
					<td>${frappe.datetime.str_to_user(row.start_time) || '—'}</td>
					${showUser ? `<td>${frappe.utils.escape_html(row.user || '')}</td>` : ''}
					<td>${frappe.utils.escape_html(row.project || '—')}</td>
					<td>${frappe.utils.escape_html(row.task || '—')}</td>
					<td class="text-right">${format_number(row.hours || 0, null, 2)}</td>
					<td><span class="td-badge" style="color:${color};background:${color}1a">${frappe.utils.escape_html(row.status || '—')}</span></td>
					<td class="text-right">${row.keyboard_count || 0}</td>
					<td class="text-right">${row.mouse_click_count || 0}</td>
					<td class="text-right">${row.screenshots_count || 0}</td>
				</tr>`;
			}).join('');
			this.$entries.html(`
				<table class="td-table">
					<thead><tr>
						<th>${__('Start')}</th>${showUser ? `<th>${__('User')}</th>` : ''}
						<th>${__('Project')}</th><th>${__('Task')}</th><th class="text-right">${__('Hours')}</th>
						<th>${__('Status')}</th><th class="text-right">${__('Kbd')}</th>
						<th class="text-right">${__('Mouse')}</th><th class="text-right">${__('Shots')}</th>
					</tr></thead>
					<tbody>${body}</tbody>
				</table>`);
		});
	}

	// ---------------- manual entry ----------------
	open_manual_entry_dialog() {
		const now = frappe.datetime.now_datetime();
		const dt = frappe.datetime.str_to_obj(now);
		dt.setHours(dt.getHours() - 1);
		const hour_ago = frappe.datetime.obj_to_str(dt);

		const d = new frappe.ui.Dialog({
			title: __('Manual Time Entry'),
			fields: [
				{ fieldname: 'project', label: __('Project'), fieldtype: 'Link', options: 'Project', reqd: 1 },
				{ fieldname: 'task', label: __('Task'), fieldtype: 'Link', options: 'Task' },
				{ fieldname: 'activity_type', label: __('Activity Type'), fieldtype: 'Link', options: 'Activity Type' },
				{ fieldname: 'description', label: __('Description'), fieldtype: 'Small Text' },
				{ fieldname: 'col_break', label: '', fieldtype: 'Column Break' },
				{ fieldname: 'start_time', label: __('Start Time'), fieldtype: 'Datetime', reqd: 1, default: hour_ago },
				{ fieldname: 'end_time', label: __('End Time'), fieldtype: 'Datetime', reqd: 1, default: now },
				{ fieldname: 'is_billable', label: __('Is Billable'), fieldtype: 'Check', default: 1 },
			],
			primary_action_label: __('Save'),
			primary_action: (values) => {
				d.get_primary_btn().prop('disabled', true).html(__('Saving...'));
				frappe.call({
					method: `${API}.create_manual_entry`,
					args: values,
					callback: (r) => {
						if (r.message) {
							frappe.show_alert({
								message: __('Time entry created: {0} hours', [r.message.hours]),
								indicator: 'green',
							});
							d.hide();
							this.refresh();
						}
					},
					error: () => {
						d.get_primary_btn().prop('disabled', false).html(__('Save'));
					},
				});
			},
		});

		d.get_field('task').df.get_query = () => {
			const project = d.get_value('project');
			return project ? { filters: { project } } : { filters: [['name', '=', '']] };
		};

		d.show();
	}

	// ---------------- helpers ----------------
	humanize(seconds) {
		seconds = Math.round(seconds);
		if (seconds < 60) return `${seconds}s ago`;
		if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
		if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
		return `${Math.round(seconds / 86400)}d ago`;
	}

	empty_state(icon, msg) {
		return `<div class="td-empty"><i class="fa ${icon}"></i><div>${frappe.utils.escape_html(msg)}</div></div>`;
	}

	skeleton_cards() {
		return new Array(7).fill('<div class="td-card td-skeleton"></div>').join('');
	}

	inject_styles() {
		if (document.getElementById('tracker-dashboard-styles')) return;
		const css = `
		.tracker-dashboard { display:flex; flex-direction:column; gap:16px; padding:4px 2px 24px; }
		.tracker-dashboard .td-toolbar { display:flex; justify-content:flex-end; }
		.tracker-dashboard .td-toolbar-controls { display:flex; gap:12px; flex-wrap:wrap; align-items:flex-end; }
		.tracker-dashboard .td-control { min-width:150px; }
		.tracker-dashboard .td-control .form-group { margin-bottom:0; }
		.tracker-dashboard .td-control-user { min-width:220px; }

		.tracker-dashboard .td-cards { display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(165px,1fr)); }
		.tracker-dashboard .td-card { position:relative; display:flex; align-items:center; gap:14px; padding:18px 16px;
			background:var(--card-bg,#fff); border:1px solid var(--border-color,#ebeef0); border-radius:14px;
			overflow:hidden; box-shadow:0 1px 2px rgba(0,0,0,.04); transition:transform .2s ease, box-shadow .2s ease;
			animation:td-fade-up .45s ease both; }
		.tracker-dashboard .td-card:hover { transform:translateY(-4px); box-shadow:0 12px 28px rgba(0,0,0,.12); }
		.tracker-dashboard .td-card-icon { flex:0 0 auto; width:46px; height:46px; border-radius:12px; display:flex;
			align-items:center; justify-content:center; color:#fff; font-size:18px; box-shadow:0 6px 14px rgba(0,0,0,.18); }
		.tracker-dashboard .td-card-value { font-size:1.55rem; font-weight:700; line-height:1.1; color:var(--heading-color); }
		.tracker-dashboard .td-card-label { color:var(--text-muted); font-size:.78rem; margin-top:3px; text-transform:uppercase; letter-spacing:.03em; }
		.tracker-dashboard .td-card-bar { position:absolute; left:0; bottom:0; height:4px; width:100%; opacity:.9; }
		.tracker-dashboard .td-skeleton { height:84px; background:linear-gradient(90deg,#f0f1f3 25%,#e6e8eb 37%,#f0f1f3 63%);
			background-size:400% 100%; animation:td-shimmer 1.3s infinite; border:none; }

		.tracker-dashboard .td-grid { display:grid; gap:16px; grid-template-columns:2fr 1fr; }
		@media (max-width:992px){ .tracker-dashboard .td-grid { grid-template-columns:1fr; } }
		.tracker-dashboard .td-panel { background:var(--card-bg,#fff); border:1px solid var(--border-color,#ebeef0);
			border-radius:14px; padding:18px; box-shadow:0 1px 2px rgba(0,0,0,.04); animation:td-fade-up .5s ease both; }
		.tracker-dashboard .td-panel-head { display:flex; align-items:center; gap:9px; font-weight:600; font-size:1rem;
			margin-bottom:14px; color:var(--heading-color); }
		.tracker-dashboard .td-dot { width:9px; height:9px; border-radius:50%; display:inline-block; }
		.td-dot-indigo{background:#6366f1}.td-dot-green{background:#22c55e}.td-dot-cyan{background:#06b6d4}.td-dot-amber{background:#f59e0b}

		.tracker-dashboard .td-live { display:flex; flex-direction:column; gap:8px; }
		.tracker-dashboard .td-live-row { display:flex; justify-content:space-between; align-items:center; padding:10px 12px;
			border-radius:10px; background:var(--bg-light-gray,#f8f9fa); transition:background .15s; }
		.tracker-dashboard .td-live-row:hover { background:var(--bg-gray,#f0f1f3); }
		.tracker-dashboard .td-live-user { display:flex; align-items:center; gap:11px; }
		.tracker-dashboard .td-status-dot { width:11px; height:11px; border-radius:50%; flex:0 0 auto; }
		.tracker-dashboard .td-live-name { font-weight:600; font-size:.9rem; }
		.tracker-dashboard .td-live-sub { color:var(--text-muted); font-size:.76rem; }
		.tracker-dashboard .td-live-meta { display:flex; align-items:center; gap:10px; }
		.tracker-dashboard .td-live-seen { color:var(--text-muted); font-size:.74rem; white-space:nowrap; }
		.tracker-dashboard .td-badge { padding:3px 10px; border-radius:20px; font-size:.74rem; font-weight:600; }
		.tracker-dashboard .td-badge-sm { padding:1px 7px; border-radius:20px; font-size:.66rem; font-weight:600; text-transform:capitalize; }

		.tracker-dashboard .td-gallery { display:grid; gap:12px; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); }
		.tracker-dashboard .td-shot { border:1px solid var(--border-color,#ebeef0); border-radius:12px; overflow:hidden;
			cursor:pointer; background:var(--card-bg,#fff); transition:transform .18s, box-shadow .18s; animation:td-fade-up .4s ease both; }
		.tracker-dashboard .td-shot:hover { transform:translateY(-3px) scale(1.01); box-shadow:0 10px 22px rgba(0,0,0,.14); }
		.tracker-dashboard .td-shot img { width:100%; height:115px; object-fit:cover; display:block; background:#f4f5f6; }
		.tracker-dashboard .td-shot-placeholder { height:115px; display:flex; flex-direction:column; gap:6px; align-items:center;
			justify-content:center; color:#b6bdc6; background:repeating-linear-gradient(45deg,#f6f7f9,#f6f7f9 10px,#f1f2f4 10px,#f1f2f4 20px); }
		.tracker-dashboard .td-shot-placeholder i { font-size:22px; } .tracker-dashboard .td-shot-placeholder span { font-size:.68rem; }
		.tracker-dashboard .td-shot-meta { display:flex; justify-content:space-between; align-items:center; padding:7px 9px; }
		.tracker-dashboard .td-shot-type { font-size:.72rem; color:var(--text-muted); text-transform:capitalize; }
		.tracker-dashboard .td-gallery-more { margin-top:14px; text-align:center; }
		.tracker-dashboard .td-loadmore { border:1px solid var(--border-color,#ebeef0); border-radius:8px; background:var(--card-bg,#fff); }

		.tracker-dashboard .td-table-wrap { overflow-x:auto; }
		.tracker-dashboard .td-table { width:100%; border-collapse:separate; border-spacing:0; font-size:.84rem; }
		.tracker-dashboard .td-table thead th { text-align:left; padding:10px 12px; color:var(--text-muted); font-weight:600;
			font-size:.72rem; text-transform:uppercase; letter-spacing:.03em; border-bottom:2px solid var(--border-color,#ebeef0); white-space:nowrap; }
		.tracker-dashboard .td-table tbody td { padding:11px 12px; border-bottom:1px solid var(--border-color,#f0f1f3); }
		.tracker-dashboard .td-table tbody tr { transition:background .12s; }
		.tracker-dashboard .td-table tbody tr:hover { background:var(--bg-light-gray,#f8f9fa); }
		.tracker-dashboard .text-right { text-align:right; }

		.tracker-dashboard .td-empty { padding:34px 16px; text-align:center; color:var(--text-muted); }
		.tracker-dashboard .td-empty i { font-size:30px; opacity:.45; display:block; margin-bottom:10px; }

		.td-pulse { animation:td-pulse 1.6s infinite; }
		@keyframes td-pulse { 0%{box-shadow:0 0 0 0 rgba(34,197,94,.5)} 70%{box-shadow:0 0 0 8px rgba(34,197,94,0)} 100%{box-shadow:0 0 0 0 rgba(34,197,94,0)} }
		@keyframes td-fade-up { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
		@keyframes td-shimmer { 0%{background-position:100% 0} 100%{background-position:-100% 0} }
		`;
		$(`<style id="tracker-dashboard-styles">${css}</style>`).appendTo('head');
	}
}
