import csv
import os

CSV_FILE = "user_manage.csv"
FIELDNAMES = ["RFID", "Username", "Password", "Phone", "Name", "LockPassword"]

def init_csv():
    """Ensure the CSV has headers."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()

def load_users():
    """Load all users from the CSV file."""
    init_csv()
    with open(CSV_FILE, mode="r", newline="") as file:
        return list(csv.DictReader(file))

def save_users(users):
    """Save the entire list of users to the CSV."""
    with open(CSV_FILE, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(users)

def add_user(rfid, username, password, phone, name, lock_password):
    """Add a new user if total users <= 3 and no duplicate RFID/Username."""
    users = load_users()

    if len(users) >= 3:
        print("User limit reached. Cannot add more than 3 users.")
        return False

    for user in users:
        if user["RFID"] == rfid or user["Username"] == username:
            print("User already exists.")
            return False

    users.append({
        "RFID": rfid,
        "Username": username,
        "Password": password,
        "Phone": phone,
        "Name": name,
        "LockPassword": lock_password
    })

    save_users(users)
    return True

def find_user_by_username(username):
    """Find a user by username."""
    for user in load_users():
        if user["Username"] == username:
            return user
    return None

def update_user_field(username, field, new_value):
    """Update a specific field of a user."""
    if field not in FIELDNAMES:
        print("Invalid field.")
        return False

    users = load_users()
    updated = False

    for user in users:
        if user["Username"] == username:
            user[field] = new_value
            updated = True
            break

    if updated:
        save_users(users)
    return updated

def get_user_field(username, field):
    """Get the value of a specific field from a user."""
    if field not in FIELDNAMES:
        print("Invalid field.")
        return None

    user = find_user_by_username(username)
    if user:
        return user[field]
    return None

def delete_user(username):
    """Delete a user by username."""
    users = load_users()
    new_users = [user for user in users if user["Username"] != username]

    if len(new_users) == len(users):
        print(f"No user with username '{username}' was found.")
        return False

    save_users(new_users)
    print(f"User '{username}' has been deleted.")
    return True

