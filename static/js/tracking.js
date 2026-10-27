const map = L.map("map", { zoomControl: true }).setView([28.4744, 77.5040], 12);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

const markers = new Map();
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({
  "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
}[ch]));

function renderVehicles(buses) {
  const list = document.getElementById("vehicle-list");
  document.getElementById("fleet-total").textContent = buses.length;
  const liveCount = buses.filter(bus => bus.live).length;
  document.getElementById("fleet-live").textContent = liveCount;
  document.getElementById("fleet-offline").textContent = buses.length - liveCount;
  document.getElementById("vehicle-count").textContent = `${buses.length} registered vehicles`;

  list.innerHTML = buses.map(bus => `
    <div class="vehicle-row">
      <div class="bus-avatar">▰</div>
      <div class="bus-info">
        <strong>${escapeHtml(bus.id)}</strong>
        <small>${escapeHtml(bus.route)} · ${escapeHtml(bus.route_name)}</small>
        ${bus.live && bus.speed_kmh !== null ? `<small> · ${bus.speed_kmh} km/h</small>` : ""}
      </div>
      <span class="bus-state ${bus.live ? "live" : "offline"}">${bus.live ? "● LIVE" : "OFFLINE"}</span>
    </div>`).join("");

  const seen = new Set();
  for (const bus of buses) {
    if (bus.live && Number.isFinite(bus.lat) && Number.isFinite(bus.lng)) {
      seen.add(bus.id);
      const popup = `<strong>${escapeHtml(bus.id)}</strong><br>${escapeHtml(bus.route_name)}<br>GPS age: ${bus.age_seconds ?? "?"} sec`;
      if (markers.has(bus.id)) {
        markers.get(bus.id).setLatLng([bus.lat, bus.lng]).setPopupContent(popup);
      } else {
        const icon = L.divIcon({
          className: "",
          html: '<div style="width:28px;height:28px;border-radius:10px 10px 10px 2px;transform:rotate(-45deg);background:#c8ff45;border:2px solid #10130d;box-shadow:0 3px 12px #0008;display:grid;place-items:center"><span style="transform:rotate(45deg);font-size:13px;color:#111">▰</span></div>',
          iconSize: [28, 28],
          iconAnchor: [14, 24]
        });
        markers.set(bus.id, L.marker([bus.lat, bus.lng], {icon}).addTo(map).bindPopup(popup));
      }
    }
  }
  for (const [id, marker] of markers.entries()) {
    if (!seen.has(id)) {
      map.removeLayer(marker);
      markers.delete(id);
    }
  }
}

async function refreshTracking() {
  try {
    const response = await fetch("/api/tracking", {cache: "no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderVehicles(data.buses || []);
    document.getElementById("last-updated").textContent =
      `Updated ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"})}`;
    const live = (data.buses || []).filter(bus => bus.live && Number.isFinite(bus.lat) && Number.isFinite(bus.lng));
    if (live.length === 1 && !map._hasCenteredLive) {
      map.setView([live[0].lat, live[0].lng], 15);
      map._hasCenteredLive = true;
    } else if (live.length > 1 && !map._hasFitLive) {
      map.fitBounds(L.latLngBounds(live.map(bus => [bus.lat, bus.lng])).pad(0.18), {maxZoom: 15});
      map._hasFitLive = true;
    }
  } catch (error) {
    document.getElementById("last-updated").textContent = "Feed unavailable";
  }
}
refreshTracking();
setInterval(refreshTracking, 3000);
