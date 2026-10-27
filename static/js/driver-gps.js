let watchId = null;
let lastSentAt = 0;
let sending = false;

const startButton = document.getElementById("start-gps");
const stopButton = document.getElementById("stop-gps");
const gpsState = document.getElementById("gps-state");
const gpsMessage = document.getElementById("gps-message");
const statusPulse = document.getElementById("status-pulse");

function setState(active, message) {
  gpsState.textContent = active ? "GPS SHARING ACTIVE" : "GPS NOT SHARING";
  gpsMessage.textContent = message;
  statusPulse.style.background = active ? "var(--lime)" : "var(--muted)";
  startButton.disabled = active;
  stopButton.disabled = !active;
}

async function sendFix(position) {
  const c = position.coords;
  document.getElementById("latitude").textContent = c.latitude.toFixed(6);
  document.getElementById("longitude").textContent = c.longitude.toFixed(6);
  document.getElementById("accuracy").textContent = `±${Math.round(c.accuracy)} m`;
  document.getElementById("heading").textContent = c.heading == null ? "Not available" : `${Math.round(c.heading)}°`;
  document.getElementById("speed").textContent = c.speed == null ? "Not available" : `${(c.speed * 3.6).toFixed(1)} km/h`;
  document.getElementById("last-fix").textContent = new Date(position.timestamp).toLocaleTimeString();

  // Avoid spamming the server; the browser still watches GPS continuously.
  if (sending || Date.now() - lastSentAt < 2500) return;
  sending = true;
  try {
    const response = await fetch("/api/driver/location", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        latitude: c.latitude,
        longitude: c.longitude,
        accuracy: c.accuracy,
        heading: c.heading,
        speed: c.speed
      })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `Server error ${response.status}`);
    lastSentAt = Date.now();
    setState(true, "GPS fix received and sent to Smart Transit. Keep this tab open while sharing.");
  } catch (error) {
    gpsMessage.textContent = `Could not send location: ${error.message}`;
  } finally {
    sending = false;
  }
}

function gpsError(error) {
  const messages = {
    1: "Location permission was denied. Allow location access in your browser settings, then try again.",
    2: "Your device could not determine a location. Move near a window or enable device location.",
    3: "GPS timed out. Keep location services enabled and try again."
  };
  setState(false, messages[error.code] || "Unable to get GPS location.");
  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
}

startButton.addEventListener("click", () => {
  if (!("geolocation" in navigator)) {
    setState(false, "This browser does not support geolocation.");
    return;
  }
  if (!window.isSecureContext) {
    setState(false, "This page is not a secure context. Use HTTPS on your phone (localhost is also secure).");
    return;
  }
  setState(true, "Requesting location permission from your device…");
  watchId = navigator.geolocation.watchPosition(sendFix, gpsError, {
    enableHighAccuracy: true,
    maximumAge: 2000,
    timeout: 20000
  });
});

stopButton.addEventListener("click", async () => {
  if (watchId !== null) navigator.geolocation.clearWatch(watchId);
  watchId = null;
  setState(false, "GPS sharing stopped. Your latest position will be removed from the live map.");
  try {
    await fetch("/api/driver/location", {method: "DELETE"});
  } catch (_) {}
});

window.addEventListener("pagehide", () => {
  if (watchId !== null) navigator.geolocation.clearWatch(watchId);
});
