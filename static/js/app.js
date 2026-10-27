async function loadDashboard() {
    try {
        const response = await fetch("/api/dashboard");

        if (!response.ok) {
            throw new Error("Could not load dashboard data");
        }

        const data = await response.json();

        document.getElementById("active-buses").textContent =
            data.active_buses;

        document.getElementById("ongoing-trips").textContent =
            data.ongoing_trips;

        document.getElementById("total-routes").textContent =
            data.routes;

        document.getElementById("on-time-rate").textContent =
            data.on_time_rate + "%";

        console.log("Dashboard data loaded:", data);

    } catch (error) {
        console.error("Dashboard loading failed:", error);
    }
}

loadDashboard();
