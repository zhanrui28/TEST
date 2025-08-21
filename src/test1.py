import mysql.connector
from mysql.connector import Error

DB_HOST = "172.23.39.165"
DB_USER = "pi_user"
DB_PASSWORD = "mypi123"
DB_NAME = "DovOps"

def get_connection():
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=False,
        )
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def add_user(rfid, username, password, phone, name, lock_password):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT COUNT(*) AS total FROM users")
            if cur.fetchone()["total"] >= 3:
                print("User limit reached. Cannot add more than 3 users.")
                return False

            cur.execute(
                "SELECT 1 FROM users WHERE RFID=%s OR Username=%s",
                (rfid, username),
            )
            if cur.fetchone():
                print("User already exists.")
                return False

            cur.execute(
                "INSERT INTO users (RFID, Username, Password, Phone, Name, LockPassword) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (rfid, username, password, phone, name, lock_password),
            )
        conn.commit()
        return True
    except Error as e:
        conn.rollback()
        print(f"Add user failed: {e}")
        return False
    finally:
        conn.close()

def find_user_by_username(username):
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM users WHERE Username=%s", (username,))
            return cur.fetchone()
    except Error as e:
        print(f"Find failed: {e}")
        return None
    finally:
        conn.close()

def update_user_field(username, field, new_value):
    allowed = {"RFID","Username","Password","Phone","Name","LockPassword"}
    if field not in allowed:
        print("Invalid field.")
        return False
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            # backtick the column name that we already validated
            cur.execute(f"UPDATE users SET `{field}`=%s WHERE Username=%s",
                        (new_value, username))
        conn.commit()
        return cur.rowcount > 0
    except Error as e:
        conn.rollback()
        print(f"Update failed: {e}")
        return False
    finally:
        conn.close()

def get_user_field(username, field):
    allowed = {"RFID","Username","Password","Phone","Name","LockPassword"}
    if field not in allowed:
        print("Invalid field.")
        return None
    user = find_user_by_username(username)
    return user.get(field) if user else None

def delete_user(username):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE Username=%s", (username,))
        conn.commit()
        if cur.rowcount > 0:
            print(f"User '{username}' has been deleted.")
            return True
        else:
            print(f"No user with username '{username}' was found.")
            return False
    except Error as e:
        conn.rollback()
        print(f"Delete failed: {e}")
        return False
    finally:
        conn.close()

print(find_user_by_username("alice"))              # None if not present
print(add_user("123456", "alice", "pw", "999", "Alice", "1234"))
print(find_user_by_username("alice"))              # now a dict
print(get_user_field("alice", "Phone"))            # "999"
print(update_user_field("alice", "Phone", "888"))
print(delete_user("alice"))
