
const tableBody = document.getElementById("fleet-table-body");
const searchInput = document.getElementById("bus-search");
const addForm = document.getElementById("add-bus-form");
const message = document.getElementById("fleet-message");

let fleetData = [];
let routeData = [];

function showMessage(text, isError = false) {
    message.textContent = text;
    message.classList.toggle("error", isError);
}

async function loadFleet() {
    try {
        const response = await fetch("/api/dashboard");

        if (!response.ok) {
            throw new Error("Could not load fleet data");
        }

        const data = await response.json();

        fleetData = data.buses;
        routeData = data.route_details;

        document.getElementById("fleet-total").textContent =
            fleetData.length;

        document.getElementById("fleet-active").textContent =
            fleetData.filter(bus => bus.status === "Active").length;

        document.getElementById("fleet-inactive").textContent =
            fleetData.filter(bus => bus.status === "Inactive").length;

        document.getElementById("fleet-routes").textContent =
            routeData.length;

        populateRouteOptions();
        renderFleet();

    } catch (error) {
        showMessage("Unable to load fleet data. Check the server.", true);
        console.error(error);
    }
}

function populateRouteOptions() {
    const select = document.getElementById("bus-route");
    const previousValue = select.value;

    select.replaceChildren();

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select a route";
    select.appendChild(placeholder);

    routeData.forEach(route => {
        const option = document.createElement("option");
        option.value = route.id;
        option.textContent = `${route.id} — ${route.name}`;
        select.appendChild(option);
    });

    if (routeData.some(route => route.id === previousValue)) {
        select.value = previousValue;
    }
}

function renderFleet() {
    const query = searchInput.value.trim().toLowerCase();

    const filteredBuses = fleetData.filter(bus =>
        bus.id.toLowerCase().includes(query) ||
        bus.route.toLowerCase().includes(query)
    );

    tableBody.replaceChildren();

    if (filteredBuses.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 4;
        cell.textContent = "No matching buses found.";

        row.appendChild(cell);
        tableBody.appendChild(row);
        return;
    }

    filteredBuses.forEach(bus => {
        const row = document.createElement("tr");

        const idCell = document.createElement("td");
        idCell.textContent = bus.id;
        idCell.className = "bus-id";

        const routeCell = document.createElement("td");
        const route = routeData.find(item => item.id === bus.route);
        routeCell.textContent = route
            ? `${route.id} — ${route.name}`
            : bus.route;

        const statusCell = document.createElement("td");
        const badge = document.createElement("span");
        badge.className =
            `status-badge ${bus.status.toLowerCase()}`;
        badge.textContent = bus.status;
        statusCell.appendChild(badge);

        const actionCell = document.createElement("td");
        const button = document.createElement("button");

        button.className = "table-action";
        button.textContent =
            bus.status === "Active" ? "Deactivate" : "Activate";

        button.addEventListener("click", () => toggleBus(bus.id));

        actionCell.appendChild(button);

        row.append(idCell, routeCell, statusCell, actionCell);
        tableBody.appendChild(row);
    });
}

searchInput.addEventListener("input", renderFleet);

document.getElementById("show-add-form").addEventListener("click", () => {
    addForm.hidden = !addForm.hidden;

    if (!addForm.hidden) {
        document.getElementById("bus-id").focus();
    }
});

document.getElementById("cancel-add").addEventListener("click", () => {
    addForm.reset();
    addForm.hidden = true;
    showMessage("");
});

addForm.addEventListener("submit", async event => {
    event.preventDefault();

    const busId = document.getElementById("bus-id").value.trim();
    const routeId = document.getElementById("bus-route").value;

    try {
        const response = await fetch("/api/buses", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                id: busId,
                route: routeId
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Could not add bus");
        }

        addForm.reset();
        addForm.hidden = true;

        await loadFleet();
        showMessage(`${result.bus.id} added successfully.`);

    } catch (error) {
        showMessage(error.message, true);
    }
});

async function toggleBus(busId) {
    try {
        const response = await fetch(
            `/api/buses/${encodeURIComponent(busId)}/toggle`,
            { method: "POST" }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Could not update bus");
        }

        await loadFleet();
        showMessage(
            `${result.bus.id} is now ${result.bus.status.toLowerCase()}.`
        );

    } catch (error) {
        showMessage(error.message, true);
    }
}

loadFleet();
