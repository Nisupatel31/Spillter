import sqlite3
import os
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "splitter.db"))
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

def hash_password(password: str, salt: str = None) -> str:
    if not salt:
        salt = secrets.token_hex(8)
    hashed = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return f"{salt}${hashed}"

def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, hashed = stored_hash.split("$", 1)
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest() == hashed

class LibsqlRow(dict):
    """Row wrapper for libSQL supporting both dict keys (row['id']) and index access (row[0])."""
    def __init__(self, description, values):
        keys = [col[0] for col in description] if description else []
        super().__init__(zip(keys, values))
        self._tuple = values

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._tuple[item]
        return super().__getitem__(item)


class LibsqlCursorWrapper:
    """Cursor wrapper for libSQL ensuring transparent execution and dict-like row mapping."""
    def __init__(self, conn, cursor):
        self._conn = conn
        self._cursor = cursor

    def execute(self, *args, **kwargs):
        self._cursor.execute(*args, **kwargs)
        return self

    def executemany(self, *args, **kwargs):
        self._cursor.executemany(*args, **kwargs)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        desc = getattr(self._cursor, "description", None)
        if desc:
            return LibsqlRow(desc, row)
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        desc = getattr(self._cursor, "description", None)
        if not desc or not rows:
            return rows
        return [LibsqlRow(desc, r) for r in rows]

    @property
    def lastrowid(self):
        val = getattr(self._cursor, "lastrowid", None)
        if val is not None and val > 0:
            return val
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT last_insert_rowid()")
            res = cur.fetchone()
            if res and res[0]:
                return res[0]
        except Exception:
            pass
        return val

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class LibsqlConnectionWrapper:
    """Connection wrapper for libSQL."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return LibsqlCursorWrapper(self._conn, self._conn.cursor())

    def execute(self, *args, **kwargs):
        cur = self.cursor()
        cur.execute(*args, **kwargs)
        return cur

    def commit(self):
        if hasattr(self._conn, "commit"):
            return self._conn.commit()

    def rollback(self):
        if hasattr(self._conn, "rollback"):
            return self._conn.rollback()

    def close(self):
        if hasattr(self._conn, "close"):
            return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db_connection():
    # Cloud SQLite (Turso) connection if environment variable configured
    if TURSO_DATABASE_URL:
        try:
            import libsql_experimental as libsql
            if TURSO_AUTH_TOKEN:
                try:
                    raw_conn = libsql.connect(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
                except TypeError:
                    raw_conn = libsql.connect(f"{TURSO_DATABASE_URL}?authToken={TURSO_AUTH_TOKEN}")
            else:
                raw_conn = libsql.connect(TURSO_DATABASE_URL)
            return LibsqlConnectionWrapper(raw_conn)
        except Exception as e:
            print(f"Warning: Turso connection failed ({e}), falling back to local SQLite.")
    
    # Standard SQLite connection
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 60000")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        mobile TEXT,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        currency TEXT DEFAULT '₹',
        user_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        avatar_color TEXT,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        amount REAL NOT NULL,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        payer_id INTEGER NOT NULL,
        split_type TEXT NOT NULL,
        payment_mode TEXT DEFAULT 'UPI',
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
        FOREIGN KEY (payer_id) REFERENCES members (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expense_splits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        expense_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        share_amount REAL NOT NULL,
        percentage REAL,
        FOREIGN KEY (expense_id) REFERENCES expenses (id) ON DELETE CASCADE,
        FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settlement_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        payer_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        date TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
        FOREIGN KEY (payer_id) REFERENCES members (id) ON DELETE CASCADE,
        FOREIGN KEY (receiver_id) REFERENCES members (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trip_vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        vehicle_type TEXT NOT NULL DEFAULT 'Car',
        brand_model TEXT NOT NULL,
        fuel_type TEXT NOT NULL DEFAULT 'CNG',
        benchmark_mileage REAL DEFAULT 0.0,
        initial_odometer REAL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fuel_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        vehicle_id INTEGER,
        date TEXT NOT NULL,
        odometer_reading REAL NOT NULL,
        distance_run REAL DEFAULT 0.0,
        fuel_amount REAL NOT NULL,
        fuel_quantity REAL NOT NULL,
        fuel_price_per_unit REAL NOT NULL,
        is_full_tank INTEGER DEFAULT 1,
        fuel_type TEXT DEFAULT 'Petrol',
        payer_id INTEGER,
        expense_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
        FOREIGN KEY (vehicle_id) REFERENCES trip_vehicles (id) ON DELETE SET NULL,
        FOREIGN KEY (payer_id) REFERENCES members (id) ON DELETE SET NULL,
        FOREIGN KEY (expense_id) REFERENCES expenses (id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trip_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        icon TEXT DEFAULT '🏷️',
        created_at TEXT NOT NULL,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trip_payment_modes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        icon TEXT DEFAULT '💳',
        created_at TEXT NOT NULL,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
    )
    """)

    # Migrate existing tables if missing new columns
    cursor.execute("PRAGMA table_info(expenses)")
    columns = [col[1] for col in cursor.fetchall()]
    if "payment_mode" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN payment_mode TEXT DEFAULT 'UPI'")

    cursor.execute("PRAGMA table_info(trips)")
    trip_columns = [col[1] for col in cursor.fetchall()]
    if "user_id" not in trip_columns:
        cursor.execute("ALTER TABLE trips ADD COLUMN user_id INTEGER REFERENCES users(id)")

    # Migration for trip_vehicles unique constraint removal (support multiple vehicles per trip)
    try:
        cursor.execute("PRAGMA index_list('trip_vehicles')")
        idx_rows = cursor.fetchall()
        has_unique_trip_id = False
        for idx in idx_rows:
            is_unique = idx[2] if isinstance(idx, (tuple, list)) else idx.get("unique", 0)
            idx_name = idx[1] if isinstance(idx, (tuple, list)) else idx.get("name", "")
            if is_unique:
                cursor.execute(f"PRAGMA index_info('{idx_name}')")
                info = cursor.fetchall()
                for col in info:
                    col_name = col[2] if isinstance(col, (tuple, list)) else col.get("name", "")
                    if col_name == "trip_id":
                        has_unique_trip_id = True
                        break
        if has_unique_trip_id:
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("DROP TABLE IF EXISTS trip_vehicles_new")
            cursor.execute("CREATE TABLE trip_vehicles_new (id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id INTEGER NOT NULL, vehicle_type TEXT NOT NULL DEFAULT 'Car', brand_model TEXT NOT NULL, fuel_type TEXT NOT NULL DEFAULT 'CNG', benchmark_mileage REAL DEFAULT 0.0, initial_odometer REAL DEFAULT 0.0, created_at TEXT NOT NULL, FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE)")
            cursor.execute("INSERT INTO trip_vehicles_new SELECT * FROM trip_vehicles")
            cursor.execute("DROP TABLE trip_vehicles")
            cursor.execute("ALTER TABLE trip_vehicles_new RENAME TO trip_vehicles")
            cursor.execute("PRAGMA foreign_keys = ON")
    except Exception as e:
        cursor.execute("PRAGMA foreign_keys = ON")

    # Clean up any legacy demo data for clean and accurate user-only database
    try:
        cursor.execute("SELECT id FROM trips WHERE name LIKE '%Goa Beach & Road Trip%'")
        demo_trips = cursor.fetchall()
        for dt in demo_trips:
            dt_id = dt[0] if isinstance(dt, (tuple, list)) else dt["id"]
            cursor.execute("DELETE FROM fuel_logs WHERE trip_id = ?", (dt_id,))
            cursor.execute("DELETE FROM trip_vehicles WHERE trip_id = ?", (dt_id,))
            cursor.execute("DELETE FROM settlement_payments WHERE trip_id = ?", (dt_id,))
            cursor.execute("DELETE FROM expense_splits WHERE expense_id IN (SELECT id FROM expenses WHERE trip_id = ?)", (dt_id,))
            cursor.execute("DELETE FROM expenses WHERE trip_id = ?", (dt_id,))
            cursor.execute("DELETE FROM members WHERE trip_id = ?", (dt_id,))
            cursor.execute("DELETE FROM trips WHERE id = ?", (dt_id,))

        cursor.execute("SELECT id FROM users WHERE email = 'nisarg@travel.com'")
        demo_users = cursor.fetchall()
        for du in demo_users:
            du_id = du[0] if isinstance(du, (tuple, list)) else du["id"]
            cursor.execute("DELETE FROM sessions WHERE user_id = ?", (du_id,))
            cursor.execute("DELETE FROM trips WHERE user_id = ?", (du_id,))
            cursor.execute("DELETE FROM users WHERE id = ?", (du_id,))
    except Exception as e:
        pass

    conn.commit()
    conn.close()

DEFAULT_CATEGORIES = [
    {"name": "Food & Dining", "icon": "🍽️"},
    {"name": "Stay & Accommodation", "icon": "🏨"},
    {"name": "Travel & Transport", "icon": "🚗"},
    {"name": "Activities & Adventure", "icon": "🏄"},
    {"name": "Sightseeing & Tickets", "icon": "📸"},
    {"name": "Shopping & Souvenirs", "icon": "🛍️"},
    {"name": "Miscellaneous", "icon": "📦"}
]

DEFAULT_PAYMENT_MODES = [
    {"name": "UPI / QR", "icon": "📱"},
    {"name": "Cash", "icon": "💵"},
    {"name": "Credit Card", "icon": "💳"},
    {"name": "Debit Card", "icon": "💳"},
    {"name": "Net Banking", "icon": "🏦"}
]

def get_trip_categories(trip_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, trip_id, name, icon FROM trip_categories WHERE trip_id = ? ORDER BY id ASC", (trip_id,))
    rows = cursor.fetchall()
    if not rows:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for cat in DEFAULT_CATEGORIES:
            cursor.execute(
                "INSERT INTO trip_categories (trip_id, name, icon, created_at) VALUES (?, ?, ?, ?)",
                (trip_id, cat["name"], cat["icon"], now)
            )
        conn.commit()
        cursor.execute("SELECT id, trip_id, name, icon FROM trip_categories WHERE trip_id = ? ORDER BY id ASC", (trip_id,))
        rows = cursor.fetchall()
    categories = [dict(r) for r in rows]
    conn.close()
    return categories

def add_trip_category(trip_id: int, name: str, icon: str = "🏷️") -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO trip_categories (trip_id, name, icon, created_at) VALUES (?, ?, ?, ?)",
        (trip_id, name.strip(), icon.strip() if icon else "🏷️", now)
    )
    cat_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT id, trip_id, name, icon FROM trip_categories WHERE id = ?", (cat_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)

def delete_trip_category(trip_id: int, category_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trip_categories WHERE id = ? AND trip_id = ?", (category_id, trip_id))
    conn.commit()
    conn.close()
    return True

def get_trip_payment_modes(trip_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, trip_id, name, icon FROM trip_payment_modes WHERE trip_id = ? ORDER BY id ASC", (trip_id,))
    rows = cursor.fetchall()
    if not rows:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for mode in DEFAULT_PAYMENT_MODES:
            cursor.execute(
                "INSERT INTO trip_payment_modes (trip_id, name, icon, created_at) VALUES (?, ?, ?, ?)",
                (trip_id, mode["name"], mode["icon"], now)
            )
        conn.commit()
        cursor.execute("SELECT id, trip_id, name, icon FROM trip_payment_modes WHERE trip_id = ? ORDER BY id ASC", (trip_id,))
        rows = cursor.fetchall()
    modes = [dict(r) for r in rows]
    conn.close()
    return modes

def add_trip_payment_mode(trip_id: int, name: str, icon: str = "💳") -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO trip_payment_modes (trip_id, name, icon, created_at) VALUES (?, ?, ?, ?)",
        (trip_id, name.strip(), icon.strip() if icon else "💳", now)
    )
    mode_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT id, trip_id, name, icon FROM trip_payment_modes WHERE id = ?", (mode_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)

def delete_trip_payment_mode(trip_id: int, mode_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trip_payment_modes WHERE id = ? AND trip_id = ?", (mode_id, trip_id))
    conn.commit()
    conn.close()
    return True

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with clean user-only data schema.")
