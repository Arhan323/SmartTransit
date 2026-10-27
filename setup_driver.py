
from getpass import getpass
from werkzeug.security import generate_password_hash
from database import get_connection, initialize_database

initialize_database()

print("\n=== Smart Transit: Driver Account Setup ===")
username = input("Driver username: ").strip()
bus_id = input("Assigned bus ID (e.g. BUS-101): ").strip().upper()
password = getpass("Set driver password: ")

if not username or not bus_id or not password:
    print("All fields are required.")
    raise SystemExit(1)

try:
    with get_connection() as con:
        bus = con.execute(
            "SELECT id FROM buses WHERE id = ?", (bus_id,)
        ).fetchone()

        if not bus:
            print(f"Bus {bus_id} does not exist.")
            raise SystemExit(1)

        driver = con.execute(
            "SELECT id FROM drivers WHERE username = ?", (username,)
        ).fetchone()

        if driver:
            driver_id = driver["id"]
            con.execute(
                "UPDATE drivers SET bus_id = ? WHERE id = ?",
                (bus_id, driver_id)
            )
        else:
            cur = con.execute(
                "INSERT INTO drivers (username, password_hash, bus_id) "
                "VALUES (?, ?, ?)",
                (username, generate_password_hash(password), bus_id)
            )
            driver_id = cur.lastrowid

        existing_user = con.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()

        password_hash = generate_password_hash(password)

        if existing_user:
            con.execute(
                """UPDATE users
                   SET password_hash = ?, role = 'driver', driver_id = ?
                   WHERE id = ?""",
                (password_hash, driver_id, existing_user["id"])
            )
        else:
            con.execute(
                """INSERT INTO users
                   (username, password_hash, role, driver_id)
                   VALUES (?, ?, 'driver', ?)""",
                (username, password_hash, driver_id)
            )

    print("\nDriver account created/updated successfully!")
    print("Username:", username)
    print("Assigned bus:", bus_id)
    print("Now sign in at /login.")

except Exception as error:
    print("\nSetup failed:", error)
    print("Check the database schema and try again.")
