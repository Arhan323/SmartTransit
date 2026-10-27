import math
import os
import time
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from werkzeug.security import check_password_hash
from database import get_connection, initialize_database

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SMART_TRANSIT_SECRET_KEY", "dev-only-change-this-secret"
)

initialize_database()

# Stores the latest real GPS fix shared by each driver.
with get_connection() as connection:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS bus_locations (
            bus_id TEXT PRIMARY KEY,
            driver_id INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            accuracy REAL,
            heading REAL,
            speed REAL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bus_id) REFERENCES buses(id),
            FOREIGN KEY (driver_id) REFERENCES drivers(id)
        )
    """)


# ---------- Shared login and role protection ----------

def role_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Please log in"}), 401
                return redirect(url_for("login"))
            if session.get("role") not in allowed_roles:
                return jsonify({"error": "Forbidden"}), 403
            return view_function(*args, **kwargs)
        return wrapped_view
    return decorator

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_connection() as connection:
            user = connection.execute(
                """SELECT id, username, password_hash, role, driver_id
                   FROM users WHERE username = ?""",
                (username,)
            ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            if user["role"] == "driver" and user["driver_id"] is None:
                return render_template(
                    "login.html",
                    error="This driver account is not linked to a driver record yet."
                )
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["driver_id"] = user["driver_id"]

            if user["role"] == "admin":
                return redirect(url_for("home"))
            if user["role"] == "driver":
                return redirect(url_for("driver_dashboard"))
            return redirect(url_for("passenger_dashboard"))

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Pages ----------

@app.route("/")
@role_required("admin")
def home():
    return render_template("index.html")


@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    return redirect(url_for("home"))


@app.route("/fleet")
@role_required("admin")
def fleet_page():
    return render_template("fleet.html")


@app.route("/trips")
@role_required("admin")
def trips_page():
    return render_template("trips.html")


@app.route("/tracking")
def tracking_page():
    return render_template("tracking.html")


@app.route("/passenger")
@role_required("passenger")
def passenger_dashboard():
    return render_template("tracking.html")


@app.route("/driver")
@role_required("driver")
def driver_dashboard():
    driver_id = session.get("driver_id")
    with get_connection() as connection:
        driver = connection.execute(
            """SELECT d.id, d.username, d.bus_id, b.route_id, b.status
               FROM drivers d JOIN buses b ON b.id = d.bus_id
               WHERE d.id = ?""",
            (driver_id,)
        ).fetchone()

    if driver is None:
        session.clear()
        return redirect(url_for("login"))
    return render_template("driver.html", driver=driver)


# ---------- Dashboard metrics ----------

def get_on_time_rate(connection):
    completed = connection.execute(
        """SELECT scheduled_arrival, actual_arrival FROM trips
           WHERE status = 'Completed' AND actual_arrival IS NOT NULL"""
    ).fetchall()
    if not completed:
        return 0

    on_time = 0
    for trip in completed:
        scheduled = datetime.fromisoformat(trip["scheduled_arrival"])
        actual = datetime.fromisoformat(trip["actual_arrival"])
        if actual <= scheduled + timedelta(minutes=5):
            on_time += 1
    return round(on_time / len(completed) * 100)


@app.route("/api/dashboard")
@role_required("admin")
def dashboard_data():
    with get_connection() as connection:
        active_buses = connection.execute(
            "SELECT COUNT(*) FROM buses WHERE status = 'Active'"
        ).fetchone()[0]
        ongoing_trips = connection.execute(
            "SELECT COUNT(*) FROM trips WHERE status = 'Ongoing'"
        ).fetchone()[0]
        total_routes = connection.execute(
            "SELECT COUNT(*) FROM routes"
        ).fetchone()[0]
        buses = connection.execute(
            "SELECT id, route_id, status FROM buses ORDER BY id"
        ).fetchall()
        routes = connection.execute(
            "SELECT id, name FROM routes ORDER BY id"
        ).fetchall()
        on_time_rate = get_on_time_rate(connection)

    return jsonify({
        "active_buses": active_buses,
        "ongoing_trips": ongoing_trips,
        "routes": total_routes,
        "on_time_rate": on_time_rate,
        "buses": [
            {"id": b["id"], "route": b["route_id"], "status": b["status"]}
            for b in buses
        ],
        "trips": [],
        "route_details": [
            {"id": r["id"], "name": r["name"]} for r in routes
        ]
    })


# ---------- Bus management (admin only) ----------

@app.route("/api/buses", methods=["POST"])
@role_required("admin")
def add_bus():
    data = request.get_json(silent=True) or {}
    bus_id = str(data.get("id", "")).strip().upper()
    route_id = str(data.get("route", "")).strip().upper()
    if not bus_id or not route_id:
        return jsonify({"error": "Bus ID and route are required"}), 400

    try:
        with get_connection() as connection:
            route = connection.execute(
                "SELECT id FROM routes WHERE id = ?", (route_id,)
            ).fetchone()
            if route is None:
                return jsonify({"error": "Please select a valid route"}), 400
            connection.execute(
                "INSERT INTO buses (id, route_id, status) VALUES (?, ?, 'Active')",
                (bus_id, route_id)
            )
    except sqlite3.IntegrityError:
        return jsonify({"error": "Bus ID already exists"}), 409

    return jsonify({
        "bus": {"id": bus_id, "route": route_id, "status": "Active"}
    }), 201


@app.route("/api/buses/<bus_id>/toggle", methods=["POST"])
@role_required("admin")
def toggle_bus(bus_id):
    with get_connection() as connection:
        bus = connection.execute(
            "SELECT id, status FROM buses WHERE id = ?", (bus_id,)
        ).fetchone()
        if bus is None:
            return jsonify({"error": "Bus not found"}), 404

        if bus["status"] == "Active":
            ongoing = connection.execute(
                """SELECT COUNT(*) FROM trips
                   WHERE bus_id = ? AND status = 'Ongoing'""",
                (bus_id,)
            ).fetchone()[0]
            if ongoing:
                return jsonify({
                    "error": "Complete the bus's ongoing trip before deactivating it."
                }), 409

        new_status = "Inactive" if bus["status"] == "Active" else "Active"
        connection.execute(
            "UPDATE buses SET status = ? WHERE id = ?", (new_status, bus_id)
        )
    return jsonify({"bus": {"id": bus_id, "status": new_status}})


# ---------- Trips (admin only) ----------

@app.route("/api/trips", methods=["GET"])
@role_required("admin")
def list_trips():
    with get_connection() as connection:
        trips = connection.execute(
            """SELECT t.id, t.bus_id, t.route_id, t.scheduled_arrival,
                      t.actual_arrival, t.status, r.name AS route_name
               FROM trips t JOIN routes r ON r.id = t.route_id
               ORDER BY t.id DESC"""
        ).fetchall()

    return jsonify([
        {
            "id": t["id"], "bus_id": t["bus_id"], "route_id": t["route_id"],
            "route_name": t["route_name"],
            "scheduled_arrival": t["scheduled_arrival"],
            "actual_arrival": t["actual_arrival"], "status": t["status"]
        }
        for t in trips
    ])


@app.route("/api/trips", methods=["POST"])
@role_required("admin")
def create_trip():
    data = request.get_json(silent=True) or {}
    bus_id = str(data.get("bus_id", "")).strip().upper()
    route_id = str(data.get("route_id", "")).strip().upper()
    scheduled = str(data.get("scheduled_arrival", "")).strip()

    if not bus_id or not route_id or not scheduled:
        return jsonify({"error": "Bus, route and scheduled arrival are required"}), 400
    try:
        scheduled_time = datetime.fromisoformat(scheduled)
    except ValueError:
        return jsonify({"error": "Please provide a valid scheduled arrival time"}), 400

    with get_connection() as connection:
        bus = connection.execute(
            "SELECT route_id, status FROM buses WHERE id = ?", (bus_id,)
        ).fetchone()
        if bus is None:
            return jsonify({"error": "Bus not found"}), 404
        if bus["status"] != "Active":
            return jsonify({"error": "Select an active bus"}), 400
        if bus["route_id"] != route_id:
            return jsonify({
                "error": "The selected route must match the bus's assigned route."
            }), 400

        ongoing = connection.execute(
            """SELECT COUNT(*) FROM trips
               WHERE bus_id = ? AND status = 'Ongoing'""",
            (bus_id,)
        ).fetchone()[0]
        if ongoing:
            return jsonify({"error": "This bus already has an ongoing trip"}), 409

        cursor = connection.execute(
            """INSERT INTO trips (bus_id, route_id, scheduled_arrival)
               VALUES (?, ?, ?)""",
            (bus_id, route_id, scheduled_time.isoformat(timespec="minutes"))
        )
        trip_id = cursor.lastrowid
    return jsonify({"message": "Trip created", "id": trip_id}), 201


@app.route("/api/trips/<int:trip_id>/complete", methods=["POST"])
@role_required("admin")
def complete_trip(trip_id):
    actual_time = datetime.now().replace(second=0, microsecond=0)
    with get_connection() as connection:
        trip = connection.execute(
            "SELECT id, status FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        if trip is None:
            return jsonify({"error": "Trip not found"}), 404
        if trip["status"] == "Completed":
            return jsonify({"error": "This trip is already completed"}), 409

        connection.execute(
            """UPDATE trips SET status = 'Completed', actual_arrival = ?
               WHERE id = ?""",
            (actual_time.isoformat(timespec="minutes"), trip_id)
        )
        rate = get_on_time_rate(connection)
    return jsonify({"message": "Trip completed", "on_time_rate": rate})



# ---------- Real-time GPS tracking ----------

@app.route("/api/driver/location", methods=["POST"])
@role_required("driver")
def update_driver_location():
    """Receive a GPS fix from the signed-in driver's phone."""
    driver_id = session.get("driver_id")
    data = request.get_json(silent=True) or {}

    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
        accuracy = float(data.get("accuracy", 0))
        heading = data.get("heading")
        speed = data.get("speed")
        heading = float(heading) if heading is not None else None
        speed = float(speed) if speed is not None else None
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Valid latitude and longitude are required"}), 400

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return jsonify({"error": "GPS coordinates are out of range"}), 400

    with get_connection() as connection:
        driver = connection.execute(
            "SELECT id, bus_id FROM drivers WHERE id = ?",
            (driver_id,)
        ).fetchone()

        if driver is None:
            session.clear()
            return jsonify({"error": "Driver account is not linked to a driver record"}), 403

        connection.execute(
            """
            INSERT INTO bus_locations
                (bus_id, driver_id, latitude, longitude, accuracy, heading, speed, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bus_id) DO UPDATE SET
                driver_id = excluded.driver_id,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                accuracy = excluded.accuracy,
                heading = excluded.heading,
                speed = excluded.speed,
                updated_at = excluded.updated_at
            """,
            (
                driver["bus_id"], driver_id, latitude, longitude,
                accuracy, heading, speed, datetime.now().astimezone().isoformat(timespec="seconds")
            )
        )

    return jsonify({"ok": True, "bus_id": driver["bus_id"]})


@app.route("/api/driver/location", methods=["DELETE"])
@role_required("driver")
def stop_driver_location():
    """Remove the latest location when the driver stops sharing."""
    driver_id = session.get("driver_id")
    with get_connection() as connection:
        driver = connection.execute(
            "SELECT bus_id FROM drivers WHERE id = ?", (driver_id,)
        ).fetchone()
        if driver is not None:
            connection.execute(
                "DELETE FROM bus_locations WHERE bus_id = ? AND driver_id = ?",
                (driver["bus_id"], driver_id)
            )
    return jsonify({"ok": True})


@app.route("/api/tracking")
def tracking_data():
    """Return live GPS positions. No fabricated coordinates are returned."""
    now = datetime.now().astimezone()
    with get_connection() as connection:
        records = connection.execute(
            """
            SELECT b.id, b.route_id, b.status, r.name AS route_name,
                   l.latitude, l.longitude, l.accuracy, l.heading, l.speed,
                   l.updated_at
            FROM buses b
            JOIN routes r ON r.id = b.route_id
            LEFT JOIN bus_locations l ON l.bus_id = b.id
            ORDER BY b.id
            """
        ).fetchall()

    buses_on_map = []
    for bus in records:
        updated_at = bus["updated_at"]
        age_seconds = None
        if updated_at:
            try:
                fix_time = datetime.fromisoformat(updated_at)
                age_seconds = max(0, int((now - fix_time).total_seconds()))
            except (ValueError, TypeError):
                age_seconds = None

        live = (
            bus["latitude"] is not None
            and age_seconds is not None
            and age_seconds <= 30
            and bus["status"] == "Active"
        )
        buses_on_map.append({
            "id": bus["id"],
            "route": bus["route_id"],
            "route_name": bus["route_name"],
            "status": bus["status"],
            "lat": bus["latitude"] if live else None,
            "lng": bus["longitude"] if live else None,
            "accuracy": bus["accuracy"],
            "heading": bus["heading"],
            "speed_kmh": round(bus["speed"] * 3.6, 1) if live and bus["speed"] is not None else None,
            "updated_at": updated_at,
            "age_seconds": age_seconds,
            "live": live
        })

    return jsonify({
        "buses": buses_on_map,
        "updated_at": now.isoformat(timespec="seconds")
    })


if __name__ == "__main__":
    print("Starting Smart Transit...")
    app.run(host="0.0.0.0", port=5000, debug=True)
