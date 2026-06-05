module.exports = function (socket) {
	socket.on("tracker:heartbeat", async (data) => {
		try {
			await socket.frappe_request(
				"/api/method/time_tracker.time_tracker.api.sync_heartbeat_ws",
				{},
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(data),
				}
			);
		} catch (err) {
			console.error("Heartbeat handler error:", err);
		}
	});
};
