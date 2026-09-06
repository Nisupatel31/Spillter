import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import secrets
from backend.database import get_db_connection, init_db, hash_password, verify_password
from backend.settlement import calculate_trip_settlement
from backend.reports import generate_trip_pdf, generate_trip_excel, generate_member_pdf
from backend.receipt_parser import parse_receipt_text
from backend.mileage import (
    get_vehicle_catalogs,
    get_trip_vehicle,
    set_trip_vehicle,
    get_fuel_logs,
    calculate_trip_mileage_summary,
    get_default_benchmark
)
from fastapi import Header

# Initialize database
init_db()

app = FastAPI(title="Spillter - Travel Expense Tracker & Splitter", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

# ----------------- PYDANTIC SCHEMAS -----------------
class UserSignup(BaseModel):
    name: str
    email: str
    mobile: Optional[str] = ""
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class TripCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    currency: Optional[str] = "₹"
    user_id: Optional[int] = None

class TripUpdate(BaseModel):
    name: str
    description: Optional[str] = ""
    currency: Optional[str] = "₹"

class MemberCreate(BaseModel):
    name: str
    phone: Optional[str] = ""
    avatar_color: Optional[str] = "#4F46E5"

class SplitItem(BaseModel):
    member_id: int
    share_amount: float
    percentage: Optional[float] = None

class ExpenseCreate(BaseModel):
    title: str
    amount: float
    date: str
    category: str
    payer_id: int
    split_type: str # 'equal', 'selected', 'custom'
    payment_mode: Optional[str] = "UPI" # 'UPI', 'Cash', 'Credit Card', 'Debit Card', 'Net Banking'
    splits: List[SplitItem]
    notes: Optional[str] = ""

class SettlementCreate(BaseModel):
    payer_id: int
    receiver_id: int
    amount: float
    date: Optional[str] = None
    notes: Optional[str] = ""

class ReceiptParseRequest(BaseModel):
    text: str

class VehicleSetupRequest(BaseModel):
    vehicle_type: str = "Car"
    brand_model: str = "Maruti Suzuki Ertiga"
    fuel_type: str = "CNG"
    benchmark_mileage: Optional[float] = None
    initial_odometer: float = 0.0

class FuelLogCreate(BaseModel):
    date: str
    odometer_reading: float
    distance_run: Optional[float] = 0.0
    fuel_amount: float
    fuel_quantity: float
    fuel_price_per_unit: float
    is_full_tank: Optional[bool] = True
    fuel_type: Optional[str] = "Petrol"
    payer_id: Optional[int] = None
    notes: Optional[str] = ""
    add_to_expenses: Optional[bool] = False
    split_type: Optional[str] = "equal"
    splits: Optional[List[SplitItem]] = None


# ----------------- AUTHENTICATION ENDPOINTS -----------------
@app.post("/api/auth/signup")
def signup(payload: UserSignup):
    name = payload.name.strip()
    email = payload.email.strip().lower()
    mobile = payload.mobile.strip() if payload.mobile else ""

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Please provide a valid email address")
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pwd_hash = hash_password(payload.password)
    cursor.execute("""
        INSERT INTO users (name, email, mobile, password_hash, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (name, email, mobile, pwd_hash, now))
    user_id = cursor.lastrowid

    token = secrets.token_hex(24)
    cursor.execute("""
        INSERT INTO sessions (token, user_id, created_at)
        VALUES (?, ?, ?)
    """, (token, user_id, now))
    conn.commit()
    conn.close()

    return {
        "token": token,
        "user": {
            "id": user_id,
            "name": name,
            "email": email,
            "mobile": mobile
        }
    }

@app.post("/api/auth/login")
def login(payload: UserLogin):
    email = payload.email.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,))
    user_row = cursor.fetchone()

    if not user_row or not verify_password(payload.password, user_row["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = dict(user_row)
    token = secrets.token_hex(24)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO sessions (token, user_id, created_at)
        VALUES (?, ?, ?)
    """, (token, user["id"], now))
    conn.commit()
    conn.close()

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "mobile": user["mobile"] or ""
        }
    }

@app.get("/api/auth/me")
def get_current_user(authorization: Optional[str] = Header(None), x_session_token: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_session_token:
        token = x_session_token.strip()

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.mobile, u.created_at
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    user_row = cursor.fetchone()
    conn.close()

    if not user_row:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return dict(user_row)

@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None), x_session_token: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_session_token:
        token = x_session_token.strip()

    if token:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return {"message": "Logged out successfully"}


# ----------------- TRIP ENDPOINTS -----------------
@app.get("/api/trips")
def list_trips(authorization: Optional[str] = Header(None), x_session_token: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_session_token:
        token = x_session_token.strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = None
    if token:
        cursor.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
        s_row = cursor.fetchone()
        if s_row:
            user_id = s_row[0]

    if user_id:
        cursor.execute("""
            SELECT t.*, 
                   COUNT(DISTINCT m.id) as member_count,
                   COALESCE(SUM(e.amount), 0.0) as total_expenses
            FROM trips t
            LEFT JOIN members m ON t.id = m.trip_id
            LEFT JOIN expenses e ON t.id = e.trip_id
            WHERE t.user_id = ?
            GROUP BY t.id
            ORDER BY t.id DESC
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT t.*, 
                   COUNT(DISTINCT m.id) as member_count,
                   COALESCE(SUM(e.amount), 0.0) as total_expenses
            FROM trips t
            LEFT JOIN members m ON t.id = m.trip_id
            LEFT JOIN expenses e ON t.id = e.trip_id
            GROUP BY t.id
            ORDER BY t.id DESC
        """)
    trips = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return trips

@app.post("/api/trips")
def create_trip(payload: TripCreate, authorization: Optional[str] = Header(None), x_session_token: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_session_token:
        token = x_session_token.strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = payload.user_id
    if not user_id and token:
        cursor.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
        s_row = cursor.fetchone()
        if s_row:
            user_id = s_row[0]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO trips (name, description, currency, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (payload.name.strip(), payload.description.strip() if payload.description else "", payload.currency.strip(), user_id, now)
    )
    trip_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": trip_id, "name": payload.name, "currency": payload.currency}

@app.get("/api/trips/{trip_id}")
def get_trip(trip_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Trip not found")
    return dict(row)

@app.put("/api/trips/{trip_id}")
def update_trip(trip_id: int, payload: TripUpdate):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Trip name cannot be empty")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM trips WHERE id = ?", (trip_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Trip not found")

    cursor.execute(
        "UPDATE trips SET name = ?, description = ?, currency = ? WHERE id = ?",
        (name, payload.description.strip() if payload.description else "", payload.currency.strip() if payload.currency else "₹", trip_id)
    )
    conn.commit()
    cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
    updated = cursor.fetchone()
    conn.close()
    return dict(updated)

@app.delete("/api/trips/{trip_id}")
def delete_trip(trip_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM trips WHERE id = ?", (trip_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Trip not found")

    # Explicit cascading cleanup for robust cloud db compatibility
    cursor.execute("DELETE FROM fuel_logs WHERE trip_id = ?", (trip_id,))
    cursor.execute("DELETE FROM trip_vehicles WHERE trip_id = ?", (trip_id,))
    cursor.execute("DELETE FROM settlement_payments WHERE trip_id = ?", (trip_id,))
    cursor.execute("""
        DELETE FROM expense_splits 
        WHERE expense_id IN (SELECT id FROM expenses WHERE trip_id = ?)
    """, (trip_id,))
    cursor.execute("DELETE FROM expenses WHERE trip_id = ?", (trip_id,))
    cursor.execute("DELETE FROM members WHERE trip_id = ?", (trip_id,))
    cursor.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    conn.commit()
    conn.close()
    return {"message": "Trip deleted successfully"}


# ----------------- MEMBER ENDPOINTS -----------------
@app.get("/api/trips/{trip_id}/members")
def list_trip_members(trip_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM members WHERE trip_id = ? ORDER BY name ASC", (trip_id,))
    members = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return members

@app.post("/api/trips/{trip_id}/members")
def add_trip_member(trip_id: int, payload: MemberCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO members (trip_id, name, phone, avatar_color) VALUES (?, ?, ?, ?)",
        (trip_id, payload.name.strip(), payload.phone.strip() if payload.phone else "", payload.avatar_color or "#4F46E5")
    )
    member_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": member_id, "trip_id": trip_id, "name": payload.name, "phone": payload.phone, "avatar_color": payload.avatar_color}

@app.delete("/api/members/{member_id}")
def delete_member(member_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()
    return {"message": "Member removed"}


# ----------------- EXPENSE ENDPOINTS -----------------
@app.get("/api/trips/{trip_id}/expenses")
def list_trip_expenses(trip_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, m.name as payer_name, m.avatar_color as payer_color
        FROM expenses e
        JOIN members m ON e.payer_id = m.id
        WHERE e.trip_id = ?
        ORDER BY e.date DESC, e.id DESC
    """, (trip_id,))
    rows = cursor.fetchall()
    
    expenses = []
    for r in rows:
        exp = dict(r)
        cursor.execute("""
            SELECT es.*, m.name as member_name
            FROM expense_splits es
            JOIN members m ON es.member_id = m.id
            WHERE es.expense_id = ?
        """, (exp["id"],))
        exp["splits"] = [dict(s) for s in cursor.fetchall()]
        expenses.append(exp)

    conn.close()
    return expenses

@app.post("/api/trips/{trip_id}/expenses")
def create_expense(trip_id: int, payload: ExpenseCreate):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    if not payload.splits:
        raise HTTPException(status_code=400, detail="At least one split member is required")

    # Verify split amounts add up close to total amount
    total_split = sum(s.share_amount for s in payload.splits)
    if abs(total_split - payload.amount) > 0.10:
        raise HTTPException(status_code=400, detail=f"Sum of shares ({total_split:.2f}) does not match expense amount ({payload.amount:.2f})")

    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO expenses (trip_id, title, amount, date, category, payer_id, split_type, payment_mode, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (trip_id, payload.title.strip(), payload.amount, payload.date, payload.category, payload.payer_id, payload.split_type, payload.payment_mode or "UPI", payload.notes, now))
    expense_id = cursor.lastrowid

    for s in payload.splits:
        cursor.execute("""
            INSERT INTO expense_splits (expense_id, member_id, share_amount, percentage)
            VALUES (?, ?, ?, ?)
        """, (expense_id, s.member_id, s.share_amount, s.percentage))

    conn.commit()
    conn.close()
    return {"id": expense_id, "message": "Expense added successfully"}

@app.put("/api/expenses/{expense_id}")
def update_expense(expense_id: int, payload: ExpenseCreate):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    if not payload.splits:
        raise HTTPException(status_code=400, detail="At least one split member is required")

    total_split = sum(s.share_amount for s in payload.splits)
    if abs(total_split - payload.amount) > 0.10:
        raise HTTPException(status_code=400, detail=f"Sum of shares ({total_split:.2f}) does not match expense amount ({payload.amount:.2f})")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, trip_id FROM expenses WHERE id = ?", (expense_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    cursor.execute("""
        UPDATE expenses
        SET title = ?, amount = ?, date = ?, category = ?, payer_id = ?, split_type = ?, payment_mode = ?, notes = ?
        WHERE id = ?
    """, (payload.title.strip(), payload.amount, payload.date, payload.category, payload.payer_id, payload.split_type, payload.payment_mode or "UPI", payload.notes, expense_id))

    cursor.execute("DELETE FROM expense_splits WHERE expense_id = ?", (expense_id,))
    for s in payload.splits:
        cursor.execute("""
            INSERT INTO expense_splits (expense_id, member_id, share_amount, percentage)
            VALUES (?, ?, ?, ?)
        """, (expense_id, s.member_id, s.share_amount, s.percentage))

    conn.commit()
    conn.close()
    return {"id": expense_id, "message": "Expense updated successfully"}

@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expense_splits WHERE expense_id = ?", (expense_id,))
    cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return {"message": "Expense deleted"}


# ----------------- DASHBOARD & ANALYTICS -----------------
@app.get("/api/trips/{trip_id}/dashboard")
def get_trip_dashboard(trip_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Trip info
    cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
    trip = cursor.fetchone()
    if not trip:
        conn.close()
        raise HTTPException(status_code=404, detail="Trip not found")
    trip_dict = dict(trip)
    currency = trip_dict.get("currency", "₹")

    # Member count
    cursor.execute("SELECT COUNT(*) as count FROM members WHERE trip_id = ?", (trip_id,))
    member_count = cursor.fetchone()["count"]

    # Total expenses & counts
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0.0) as total_spent,
               COUNT(*) as expense_count,
               COALESCE(MAX(amount), 0.0) as max_expense
        FROM expenses
        WHERE trip_id = ?
    """, (trip_id,))
    exp_stats = cursor.fetchone()
    total_spent = float(exp_stats["total_spent"])
    expense_count = int(exp_stats["expense_count"])
    max_expense = float(exp_stats["max_expense"])
    avg_per_person = round(total_spent / member_count, 2) if member_count > 0 else 0.0

    # Category breakdown
    cursor.execute("""
        SELECT category, COALESCE(SUM(amount), 0.0) as total, COUNT(*) as count
        FROM expenses
        WHERE trip_id = ?
        GROUP BY category
        ORDER BY total DESC
    """, (trip_id,))
    category_rows = cursor.fetchall()
    category_breakdown = []
    for row in category_rows:
        tot = float(row["total"])
        pct = round((tot / total_spent) * 100.0, 1) if total_spent > 0 else 0.0
        category_breakdown.append({
            "category": row["category"],
            "total": tot,
            "count": row["count"],
            "percentage": pct
        })

    # Spending by Member (Paid vs Share)
    cursor.execute("""
        SELECT m.id, m.name, m.avatar_color,
               COALESCE(p.total_paid, 0.0) as total_paid,
               COALESCE(o.total_owed, 0.0) as total_owed
        FROM members m
        LEFT JOIN (
            SELECT payer_id, SUM(amount) as total_paid
            FROM expenses
            WHERE trip_id = ?
            GROUP BY payer_id
        ) p ON m.id = p.payer_id
        LEFT JOIN (
            SELECT es.member_id, SUM(es.share_amount) as total_owed
            FROM expense_splits es
            JOIN expenses e ON es.expense_id = e.id
            WHERE e.trip_id = ?
            GROUP BY es.member_id
        ) o ON m.id = o.member_id
        WHERE m.trip_id = ?
        ORDER BY total_paid DESC
    """, (trip_id, trip_id, trip_id))
    member_spending = []
    for r in cursor.fetchall():
        paid = float(r["total_paid"])
        owed = float(r["total_owed"])
        net = round(paid - owed, 2)
        member_spending.append({
            "id": r["id"],
            "name": r["name"],
            "avatar_color": r["avatar_color"] or "#4F46E5",
            "total_paid": paid,
            "total_owed": owed,
            "net_balance": net
        })

    # Daily spending trend
    cursor.execute("""
        SELECT date, COALESCE(SUM(amount), 0.0) as daily_total
        FROM expenses
        WHERE trip_id = ?
        GROUP BY date
        ORDER BY date ASC
    """, (trip_id,))
    daily_trend = [{"date": r["date"], "total": float(r["daily_total"])} for r in cursor.fetchall()]

    conn.close()

    # Settlement data for top debtor / top creditor highlights
    settlement_data = calculate_trip_settlement(trip_id)

    top_spender = max(member_spending, key=lambda x: x["total_paid"]) if member_spending else None

    return {
        "trip": trip_dict,
        "kpis": {
            "total_spent": total_spent,
            "currency": currency,
            "member_count": member_count,
            "expense_count": expense_count,
            "avg_per_person": avg_per_person,
            "max_expense": max_expense,
            "top_spender": top_spender["name"] if top_spender and top_spender["total_paid"] > 0 else "None",
            "pending_settlements_count": len(settlement_data["settlements"])
        },
        "category_breakdown": category_breakdown,
        "member_spending": member_spending,
        "daily_trend": daily_trend,
        "settlements": settlement_data["settlements"]
    }


# ----------------- SETTLEMENT & WHATSAPP -----------------
@app.get("/api/trips/{trip_id}/settlement")
def get_trip_settlement(trip_id: int):
    return calculate_trip_settlement(trip_id)

@app.post("/api/trips/{trip_id}/settlements")
def record_settlement_payment(trip_id: int, payload: SettlementCreate):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Settlement amount must be greater than zero")
    if payload.payer_id == payload.receiver_id:
        raise HTTPException(status_code=400, detail="Payer and receiver cannot be the same member")

    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = payload.date if payload.date else datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        INSERT INTO settlement_payments (trip_id, payer_id, receiver_id, amount, date, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (trip_id, payload.payer_id, payload.receiver_id, payload.amount, date_str, payload.notes or "", now))
    settle_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"id": settle_id, "message": "Settlement payment recorded successfully"}

@app.delete("/api/settlements/{settlement_id}")
def delete_settlement_payment(settlement_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM settlement_payments WHERE id = ?", (settlement_id,))
    conn.commit()
    conn.close()
    return {"message": "Settlement payment undone"}

@app.get("/api/trips/{trip_id}/settlements")
def list_trip_settlements(trip_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sp.*, p.name as payer_name, r.name as receiver_name
        FROM settlement_payments sp
        JOIN members p ON sp.payer_id = p.id
        JOIN members r ON sp.receiver_id = r.id
        WHERE sp.trip_id = ?
        ORDER BY sp.date DESC, sp.id DESC
    """, (trip_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ----------------- STATEMENT EXPORTS (PDF & EXCEL) -----------------
@app.get("/api/trips/{trip_id}/export/pdf")
def export_trip_pdf(trip_id: int):
    pdf_buffer = generate_trip_pdf(trip_id)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=trip_{trip_id}_statement.pdf"}
    )

@app.get("/api/trips/{trip_id}/export/excel")
def export_trip_excel(trip_id: int):
    excel_buffer = generate_trip_excel(trip_id)
    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=trip_{trip_id}_expenses.xlsx"}
    )

@app.get("/api/trips/{trip_id}/members/{member_id}/export/pdf")
def export_member_pdf(trip_id: int, member_id: int):
    pdf_buffer = generate_member_pdf(trip_id, member_id)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=trip_{trip_id}_member_{member_id}_statement.pdf"}
    )


# ----------------- RECEIPT SCANNING & PARSING -----------------
@app.post("/api/receipts/parse-text")
def parse_receipt(payload: ReceiptParseRequest):
    return parse_receipt_text(payload.text)

@app.get("/api/receipts/samples")
def get_sample_receipts():
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "samples": [
            {
                "id": "gpay",
                "name": "Google Pay UPI Receipt",
                "badge": "📱 UPI Payment",
                "raw_text": f"Google Pay\nPaid to Fisherman's Wharf Goa\n₹ 2,450.00\nCompleted\nUPI transaction ID 424567890123\nFrom: Nisarg Patel (HDFC Bank)\nTo: Fisherman's Wharf Restaurant Candolim\nGoogle transaction ID CICAgKC123456\nDate: {today}\nPayment method: UPI",
                "parsed": {
                    "title": "Fisherman's Wharf Goa",
                    "amount": 2450.0,
                    "date": today,
                    "category": "Food",
                    "payment_mode": "UPI"
                }
            },
            {
                "id": "restaurant",
                "name": "Restaurant Dinner Bill",
                "badge": "🍽️ Restaurant Bill",
                "raw_text": f"THALASSA BEACH LOUNGE\nSmall Vagator, Ozran Beach, Goa\nTax Invoice / Cash Receipt\nDate: {today} Time: 21:45\nTable: 14 Cover: 4\n--------------------------------\n1x Greek Salad        450.00\n1x Calamari Butter    680.00\n1x Seafood Platter   1250.00\n3x Craft Cocktails    900.00\n--------------------------------\nSub Total:           3280.00\nCGST 2.5%:             82.00\nSGST 2.5%:             82.00\nService Charge:       164.00\nGRAND TOTAL:        ₹ 3,608.00\nPayment Mode: Credit Card\nThank you! Visit again!",
                "parsed": {
                    "title": "Thalassa Beach Lounge",
                    "amount": 3608.0,
                    "date": today,
                    "category": "Food",
                    "payment_mode": "Credit Card"
                }
            },
            {
                "id": "fuel",
                "name": "Fuel / Transport Bill",
                "badge": "⛽ Road Trip Fuel",
                "raw_text": f"INDIAN OIL CORPORATION LTD\nCOCO Panaji Goa\nReceipt No: 98124\nDate: {today}\nFuel: Speed Petrol\nRate: 98.40 / L\nVolume: 20.32 L\nTOTAL SALE: INR 2,000.00\nCash Tendered: 2000.00\nChange: 0.00\nSAVE FUEL YAANI SAVE MONEY",
                "parsed": {
                    "title": "Indian Oil Corporation Ltd",
                    "amount": 2000.0,
                    "date": today,
                    "category": "Travel",
                    "payment_mode": "Cash"
                }
            }
        ]
    }


# ----------------- FUEL & MILEAGE TRACKING ENDPOINTS -----------------
@app.get("/api/mileage/catalogs")
def api_mileage_catalogs():
    return get_vehicle_catalogs()


@app.get("/api/trips/{trip_id}/vehicle")
def api_get_trip_vehicle(trip_id: int):
    vehicle = get_trip_vehicle(trip_id)
    if not vehicle:
        vehicle = {
            "trip_id": trip_id,
            "vehicle_type": "Car",
            "brand_model": "Maruti Suzuki Ertiga",
            "fuel_type": "CNG",
            "benchmark_mileage": 26.11,
            "initial_odometer": 0.0
        }
    return vehicle


@app.post("/api/trips/{trip_id}/vehicle")
def api_set_trip_vehicle(trip_id: int, payload: VehicleSetupRequest):
    benchmark = payload.benchmark_mileage
    if benchmark is None or benchmark <= 0:
        benchmark = get_default_benchmark(payload.vehicle_type, payload.brand_model, payload.fuel_type)
    v = set_trip_vehicle(
        trip_id=trip_id,
        vehicle_type=payload.vehicle_type,
        brand_model=payload.brand_model,
        fuel_type=payload.fuel_type,
        benchmark_mileage=benchmark,
        initial_odometer=payload.initial_odometer
    )
    return v


@app.get("/api/trips/{trip_id}/fuel-logs")
def api_get_fuel_logs(trip_id: int):
    return {"logs": get_fuel_logs(trip_id)}


@app.post("/api/trips/{trip_id}/fuel-logs")
def api_create_fuel_log(trip_id: int, payload: FuelLogCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    v_row = cursor.execute("SELECT id, fuel_type FROM trip_vehicles WHERE trip_id = ?", (trip_id,)).fetchone()
    v_id = v_row["id"] if v_row else None
    v_fuel = v_row["fuel_type"] if v_row else (payload.fuel_type or "Petrol")

    expense_id = None
    if payload.add_to_expenses and payload.payer_id:
        unit = "kg" if v_fuel == "CNG" else "L"
        exp_title = f"Fuel ({v_fuel}) - {payload.fuel_quantity} {unit}"
        cursor.execute("""
        INSERT INTO expenses (trip_id, title, amount, date, category, payer_id, split_type, payment_mode, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (trip_id, exp_title, payload.fuel_amount, payload.date, "Travel", payload.payer_id,
              payload.split_type or "equal", "UPI", payload.notes or "Auto-synced from Fuel Fill-Up", now))
        expense_id = cursor.lastrowid

        if payload.splits and len(payload.splits) > 0:
            for s in payload.splits:
                cursor.execute("""
                INSERT INTO expense_splits (expense_id, member_id, share_amount, percentage)
                VALUES (?, ?, ?, ?)
                """, (expense_id, s.member_id, s.share_amount, s.percentage))
        else:
            members = cursor.execute("SELECT id FROM members WHERE trip_id = ?", (trip_id,)).fetchall()
            if members:
                count = len(members)
                per_share = round(payload.fuel_amount / count, 2)
                allocated = 0.0
                for idx, m in enumerate(members):
                    share = per_share if idx < count - 1 else round(payload.fuel_amount - allocated, 2)
                    allocated += share
                    cursor.execute("""
                    INSERT INTO expense_splits (expense_id, member_id, share_amount, percentage)
                    VALUES (?, ?, ?, ?)
                    """, (expense_id, m["id"], share, round(100.0 / count, 2)))

    cursor.execute("""
    INSERT INTO fuel_logs (
        trip_id, vehicle_id, date, odometer_reading, distance_run, fuel_amount,
        fuel_quantity, fuel_price_per_unit, is_full_tank, fuel_type, payer_id,
        expense_id, notes, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trip_id, v_id, payload.date, payload.odometer_reading, payload.distance_run or 0.0,
        payload.fuel_amount, payload.fuel_quantity, payload.fuel_price_per_unit,
        1 if payload.is_full_tank else 0, v_fuel, payload.payer_id, expense_id,
        payload.notes or "", now
    ))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"id": log_id, "expense_id": expense_id, "message": "Fuel log recorded successfully"}


@app.put("/api/trips/{trip_id}/fuel-logs/{log_id}")
def api_update_fuel_log(trip_id: int, log_id: int, payload: FuelLogCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    log = cursor.execute("SELECT * FROM fuel_logs WHERE id = ? AND trip_id = ?", (log_id, trip_id)).fetchone()
    if not log:
        conn.close()
        raise HTTPException(status_code=404, detail="Fuel log not found")

    v_row = cursor.execute("SELECT id, fuel_type FROM trip_vehicles WHERE trip_id = ?", (trip_id,)).fetchone()
    v_fuel = v_row["fuel_type"] if v_row else (payload.fuel_type or "Petrol")

    if log["expense_id"] and payload.add_to_expenses and payload.payer_id:
        unit = "kg" if v_fuel == "CNG" else "L"
        exp_title = f"Fuel ({v_fuel}) - {payload.fuel_quantity} {unit}"
        cursor.execute("""
            UPDATE expenses
            SET title = ?, amount = ?, date = ?, payer_id = ?, split_type = ?, notes = ?
            WHERE id = ?
        """, (exp_title, payload.fuel_amount, payload.date, payload.payer_id, payload.split_type or "equal", payload.notes or "Auto-synced from Fuel Fill-Up", log["expense_id"]))

        if payload.splits and len(payload.splits) > 0:
            cursor.execute("DELETE FROM expense_splits WHERE expense_id = ?", (log["expense_id"],))
            for s in payload.splits:
                cursor.execute("""
                    INSERT INTO expense_splits (expense_id, member_id, share_amount, percentage)
                    VALUES (?, ?, ?, ?)
                """, (log["expense_id"], s.member_id, s.share_amount, s.percentage))

    cursor.execute("""
        UPDATE fuel_logs
        SET date = ?, odometer_reading = ?, distance_run = ?, fuel_amount = ?,
            fuel_quantity = ?, fuel_price_per_unit = ?, is_full_tank = ?, payer_id = ?, notes = ?
        WHERE id = ? AND trip_id = ?
    """, (
        payload.date, payload.odometer_reading, payload.distance_run or 0.0,
        payload.fuel_amount, payload.fuel_quantity, payload.fuel_price_per_unit,
        1 if payload.is_full_tank else 0, payload.payer_id, payload.notes or "",
        log_id, trip_id
    ))
    conn.commit()
    conn.close()
    return {"id": log_id, "message": "Fuel log updated successfully"}


@app.delete("/api/trips/{trip_id}/fuel-logs/{log_id}")
def api_delete_fuel_log(trip_id: int, log_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    log = cursor.execute("SELECT * FROM fuel_logs WHERE id = ? AND trip_id = ?", (log_id, trip_id)).fetchone()
    if not log:
        conn.close()
        raise HTTPException(status_code=404, detail="Fuel log not found")

    if log["expense_id"]:
        cursor.execute("DELETE FROM expenses WHERE id = ?", (log["expense_id"],))

    cursor.execute("DELETE FROM fuel_logs WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()
    return {"message": "Fuel log deleted"}


@app.get("/api/trips/{trip_id}/mileage-summary")
def api_get_mileage_summary(trip_id: int):
    return calculate_trip_mileage_summary(trip_id)


# Mount static files for frontend SPA
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return {"message": "Spillter API running. Frontend will be served from /static"}
