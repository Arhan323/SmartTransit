
const tripForm = document.getElementById("trip-form");
const busSelect = document.getElementById("trip-bus");
const routeSelect = document.getElementById("trip-route");
const tripMessage = document.getElementById("trip-message");
const tripTable = document.getElementById("trip-table-body");

let buses = [];
let routes = [];

function showTripMessage(text, isError = false) {
    tripMessage.textContent = text;
    tripMessage.classList.toggle("error", isError);
}

async function api(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Request failed");
    }

    return data;
}

async function loadOptions() {
    const data = await api("/api/dashboard");

    buses = data.buses.filter(bus => bus.status === "Active");
    routes = data.route_details;

    busSelect.replaceChildren();

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select an active bus";
    busSelect.appendChild(placeholder);

    buses.forEach(bus => {
        const option = document.createElement("option");
        option.value = bus.id;
        option.textContent = `${bus.id} — ${bus.route}`;
        busSelect.appendChild(option);
    });

    updateRouteOptions();
}

function updateRouteOptions() {
    const selectedBus = buses.find(bus => bus.id === busSelect.value);
    routeSelect.replaceChildren();

    const option = document.createElement("option");
    option.value = "";

    if (!selectedBus) {
        option.textContent = "Select a bus first";
        routeSelect.appendChild(option);
        return;
    }

    const assignedRoute = routes.find(
        route => route.id === selectedBus.route
    );

    if (!assignedRoute) {
        option.textContent = "Assigned route unavailable";
        routeSelect.appendChild(option);
        return;
    }

    option.textContent = `${assignedRoute.id} — ${assignedRoute.name}`;
    option.value = assignedRoute.id;
    routeSelect.appendChild(option);
}

busSelect.addEventListener("change", updateRouteOptions);

function addCell(row, text) {
    const cell = document.createElement("td");
    cell.textContent = text || "—";
    row.appendChild(cell);
    return cell;
}

function renderTrips(trips) {
    tripTable.replaceChildren();

    if (trips.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 7;
        cell.className = "trip-empty";
        cell.textContent = "No trips yet. Create your first trip above.";
        row.appendChild(cell);
        tripTable.appendChild(row);
        return;
    }

    trips.forEach(trip => {
        const row = document.createElement("tr");

        addCell(row, `TRIP-${String(trip.id).padStart(3, "0")}`);
        addCell(row, trip.bus_id);
        addCell(row, `${trip.route_id} — ${trip.route_name}`);
        addCell(row, trip.scheduled_arrival.replace("T", " "));
        addCell(row, trip.actual_arrival?.replace("T", " ") || "Pending");

        const statusCell = addCell(row, "");
        const badge = document.createElement("span");
        badge.className = `trip-status ${trip.status.toLowerCase()}`;
        badge.textContent = trip.status;
        statusCell.appendChild(badge);

        const actionCell = document.createElement("td");

        if (trip.status === "Ongoing") {
            const button = document.createElement("button");
            button.className = "table-action";
            button.textContent = "Complete";
            button.addEventListener("click", () => completeTrip(trip.id));
            actionCell.appendChild(button);
        } else {
            actionCell.textContent = "—";
        }

        row.appendChild(actionCell);
        tripTable.appendChild(row);
    });
}

async function loadTrips() {
    try {
        const [trips, dashboard] = await Promise.all([
            api("/api/trips"),
            api("/api/dashboard")
        ]);

        document.getElementById("trip-total").textContent = trips.length;
        document.getElementById("trip-ongoing").textContent =
            trips.filter(trip => trip.status === "Ongoing").length;
        document.getElementById("trip-completed").textContent =
            trips.filter(trip => trip.status === "Completed").length;
        document.getElementById("trip-on-time").textContent =
            `${dashboard.on_time_rate}%`;

        renderTrips(trips);
    } catch (error) {
        showTripMessage(error.message, true);
    }
}

tripForm.addEventListener("submit", async event => {
    event.preventDefault();

    try {
        await api("/api/trips", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                bus_id: busSelect.value,
                route_id: routeSelect.value,
                scheduled_arrival:
                    document.getElementById("scheduled-arrival").value
            })
        });

        tripForm.reset();
        updateRouteOptions();
        await loadTrips();
        showTripMessage("Trip created successfully.");
    } catch (error) {
        showTripMessage(error.message, true);
    }
});

async function completeTrip(tripId) {
    if (!confirm("Record the current time as this trip's arrival?")) {
        return;
    }

    try {
        await api(`/api/trips/${tripId}/complete`, {
            method: "POST"
        });

        await loadTrips();
        showTripMessage("Trip completed. Performance metrics updated.");
    } catch (error) {
        showTripMessage(error.message, true);
    }
}

document.getElementById("refresh-trips").addEventListener("click", loadTrips);

async function initializeTripsPage() {
    try {
        await loadOptions();
        await loadTrips();
    } catch (error) {
        showTripMessage(error.message, true);
    }
}

initializeTripsPage();
