
import sqlite3

DATABASE_NAME = "smart_transit.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS routes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS buses (
                id TEXT PRIMARY KEY,
                route_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active'
                    CHECK (status IN ('Active', 'Inactive')),
                FOREIGN KEY (route_id) REFERENCES routes(id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                bus_id TEXT NOT NULL,
                FOREIGN KEY (bus_id) REFERENCES buses(id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK (role IN ('admin', 'driver', 'passenger')),
                driver_id INTEGER UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (driver_id) REFERENCES drivers(id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bus_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                scheduled_arrival TEXT NOT NULL,
                actual_arrival TEXT,
                status TEXT NOT NULL DEFAULT 'Ongoing'
                    CHECK (status IN ('Ongoing', 'Completed')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bus_id) REFERENCES buses(id),
                FOREIGN KEY (route_id) REFERENCES routes(id)
            )
        """)

        sample_routes = [
            ("R-01", "City Center"),
            ("R-02", "University Express"),
            ("R-03", "Airport Link"),
        ]

        connection.executemany("""
            INSERT OR IGNORE INTO routes (id, name)
            VALUES (?, ?)
        """, sample_routes)

        sample_buses = [
            ("BUS-101", "R-01", "Active"),
            ("BUS-102", "R-01", "Active"),
            ("BUS-103", "R-02", "Active"),
            ("BUS-104", "R-02", "Inactive"),
            ("BUS-105", "R-03", "Active"),
        ]

        connection.executemany("""
            INSERT OR IGNORE INTO buses (id, route_id, status)
            VALUES (?, ?, ?)
        """, sample_buses)


if __name__ == "__main__":
    initialize_database()
    print("Smart Transit database initialized successfully.")
