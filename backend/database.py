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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
        trip_id INTEGER UNIQUE NOT NULL,
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

    # Migrate existing tables if missing new columns
    cursor.execute("PRAGMA table_info(expenses)")
    columns = [col[1] for col in cursor.fetchall()]
    if "payment_mode" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN payment_mode TEXT DEFAULT 'UPI'")

    cursor.execute("PRAGMA table_info(trips)")
    trip_columns = [col[1] for col in cursor.fetchall()]
    if "user_id" not in trip_columns:
        cursor.execute("ALTER TABLE trips ADD COLUMN user_id INTEGER REFERENCES users(id)")

    conn.commit()
    conn.close()

def seed_demo_user(cursor: sqlite3.Cursor) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pwd_hash = hash_password("password123")
    cursor.execute(
        "INSERT INTO users (name, email, mobile, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Nisarg Patel", "nisarg@travel.com", "+91 98765 43210", pwd_hash, now)
    )
    return cursor.lastrowid

def seed_demo_data(cursor: sqlite3.Cursor):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check demo user
    cursor.execute("SELECT id FROM users LIMIT 1")
    user_row = cursor.fetchone()
    user_id = user_row[0] if user_row else seed_demo_user(cursor)

    # 1. Create Demo Trip
    cursor.execute(
        "INSERT INTO trips (name, description, currency, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Goa Beach & Road Trip 🏖️", "Weekend road trip to North & South Goa with the gang", "₹", user_id, now)
    )
    trip_id = cursor.lastrowid

    # 2. Add Members with attractive avatar colors
    members_data = [
        ("Nisarg", "+91 98765 43210", "#4F46E5"), # Indigo
        ("Aarav", "+91 98123 45678", "#059669"),  # Emerald
        ("Rohan", "+91 99887 76655", "#D97706"),  # Amber
        ("Priya", "+91 97654 32109", "#DB2777"),  # Pink
        ("Sneha", "+91 91234 56789", "#7C3AED"),  # Purple
    ]

    member_ids = {}
    for name, phone, color in members_data:
        cursor.execute(
            "INSERT INTO members (trip_id, name, phone, avatar_color) VALUES (?, ?, ?, ?)",
            (trip_id, name, phone, color)
        )
        member_ids[name] = cursor.lastrowid

    # 3. Add Sample Expenses covering equal, selected, and custom split types + payment modes
    sample_expenses = [
        {
            "title": "Villa Booking (Candolim)",
            "amount": 25000.0,
            "date": "2026-09-01",
            "category": "Stay",
            "payment_mode": "Credit Card",
            "payer": "Nisarg",
            "split_type": "equal",
            "split_members": ["Nisarg", "Aarav", "Rohan", "Priya", "Sneha"],
            "notes": "3 nights private pool villa near beach"
        },
        {
            "title": "Self-drive SUV Rental & Fuel",
            "amount": 12000.0,
            "date": "2026-09-01",
            "category": "Travel",
            "payment_mode": "UPI",
            "payer": "Aarav",
            "split_type": "equal",
            "split_members": ["Nisarg", "Aarav", "Rohan", "Priya", "Sneha"],
            "notes": "Innova Crysta airport pickup to drop"
        },
        {
            "title": "Beach Shack Dinner & Drinks",
            "amount": 7500.0,
            "date": "2026-09-01",
            "category": "Food",
            "payment_mode": "Cash",
            "payer": "Rohan",
            "split_type": "custom",
            "splits": [
                {"member": "Rohan", "share": 2500.0}, # Rohan ordered specialty cocktails
                {"member": "Nisarg", "share": 1250.0},
                {"member": "Aarav", "share": 1250.0},
                {"member": "Priya", "share": 1250.0},
                {"member": "Sneha", "share": 1250.0},
            ],
            "notes": "Curlies Shack Anjuna Beach (Rohan fixed 2500, rest split)"
        },
        {
            "title": "Scuba Diving & Watersports",
            "amount": 9000.0,
            "date": "2026-09-02",
            "category": "Activities",
            "payment_mode": "UPI",
            "payer": "Priya",
            "split_type": "selected",
            "split_members": ["Nisarg", "Rohan", "Priya"],
            "notes": "Grande Island Scuba + Jet ski combo"
        },
        {
            "title": "Highway Tolls & Snacks",
            "amount": 1500.0,
            "date": "2026-09-02",
            "category": "Misc",
            "payment_mode": "Cash",
            "payer": "Sneha",
            "split_type": "equal",
            "split_members": ["Nisarg", "Aarav", "Rohan", "Priya", "Sneha"],
            "notes": "Fastag recharge + coconut water"
        },
        {
            "title": "Thalassa Sunset Cafe",
            "amount": 6800.0,
            "date": "2026-09-03",
            "category": "Food",
            "payment_mode": "Credit Card",
            "payer": "Nisarg",
            "split_type": "equal",
            "split_members": ["Nisarg", "Aarav", "Rohan", "Priya", "Sneha"],
            "notes": "Greek dinner with sunset view"
        },
        {
            "title": "Souvenirs & Cashew Shopping",
            "amount": 3200.0,
            "date": "2026-09-03",
            "category": "Shopping",
            "payment_mode": "UPI",
            "payer": "Sneha",
            "split_type": "selected",
            "split_members": ["Priya", "Sneha"],
            "notes": "Panjim market spiced cashews and feni chocolates"
        }
    ]

    for exp in sample_expenses:
        payer_id = member_ids[exp["payer"]]
        cursor.execute(
            """
            INSERT INTO expenses (trip_id, title, amount, date, category, payer_id, split_type, payment_mode, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (trip_id, exp["title"], exp["amount"], exp["date"], exp["category"], payer_id, exp["split_type"], exp.get("payment_mode", "UPI"), exp["notes"], now)
        )
        expense_id = cursor.lastrowid

        # Insert splits
        if exp["split_type"] in ("equal", "selected"):
            members_list = exp["split_members"]
            count = len(members_list)
            per_share = round(exp["amount"] / count, 2)
            total_allocated = 0
            for i, name in enumerate(members_list):
                mid = member_ids[name]
                if i == count - 1:
                    share = round(exp["amount"] - total_allocated, 2)
                else:
                    share = per_share
                    total_allocated += share
                cursor.execute(
                    "INSERT INTO expense_splits (expense_id, member_id, share_amount, percentage) VALUES (?, ?, ?, ?)",
                    (expense_id, mid, share, round(100.0 / count, 2))
                )
        elif exp["split_type"] == "custom":
            for s in exp["splits"]:
                mid = member_ids[s["member"]]
                cursor.execute(
                    "INSERT INTO expense_splits (expense_id, member_id, share_amount, percentage) VALUES (?, ?, ?, ?)",
                    (expense_id, mid, s["share"], round((s["share"] / exp["amount"]) * 100, 2))
                )

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with users, sessions, and payment modes.")
