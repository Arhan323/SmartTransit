
import getpass

from database import get_connection
from werkzeug.security import generate_password_hash


def create_user():
    print("\n=== Smart Transit Account Setup ===")

    username = input("Choose username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    password = getpass.getpass("Choose password (minimum 8 characters): ")
    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        return

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return

    print("\nChoose role:")
    print("1. Admin")
    print("2. Driver")
    print("3. Passenger")

    roles = {"1": "admin", "2": "driver", "3": "passenger"}
    role_choice = input("Enter choice (1-3): ").strip()
    role = roles.get(role_choice)

    if role is None:
        print("Invalid role.")
        return

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing:
            print("That username already exists.")
            return

        connection.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (username, generate_password_hash(password), role)
        )

    print(f"\nAccount created successfully: {username} ({role})")


if __name__ == "__main__":
    create_user()
