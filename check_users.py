from database import get_connection

with get_connection() as connection:
    users = connection.execute(
        "SELECT username, role FROM users"
    ).fetchall()

    for user in users:
        print(user["username"], "->", user["role"])