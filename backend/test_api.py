import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db, get_db_connection

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200

def test_list_and_dashboard_flow():
    # 1. Create a fresh trip
    trip_res = client.post("/api/trips", json={
        "name": "Integration Test Trip",
        "description": "Testing dashboard and settlement",
        "currency": "₹"
    })
    assert trip_res.status_code == 200
    trip_id = trip_res.json()["id"]

    # 2. Verify list trips contains created trip
    list_res = client.get("/api/trips")
    assert list_res.status_code == 200
    trips = list_res.json()
    assert any(t["id"] == trip_id for t in trips)

    # 3. Add members & an expense
    m1 = client.post(f"/api/trips/{trip_id}/members", json={"name": "P1"}).json()["id"]
    m2 = client.post(f"/api/trips/{trip_id}/members", json={"name": "P2"}).json()["id"]
    exp_res = client.post(f"/api/trips/{trip_id}/expenses", json={
        "title": "Welcome Lunch",
        "amount": 2000.0,
        "date": "2026-09-01",
        "category": "Food",
        "payer_id": m1,
        "split_type": "equal",
        "splits": [
            {"member_id": m1, "share_amount": 1000.0},
            {"member_id": m2, "share_amount": 1000.0}
        ]
    })
    assert exp_res.status_code == 200

    # 4. Test dashboard
    dash_res = client.get(f"/api/trips/{trip_id}/dashboard")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "kpis" in dash_data
    assert dash_data["kpis"]["total_spent"] == 2000.0
    assert "category_breakdown" in dash_data

    # 5. Test settlement & whatsapp
    settle_res = client.get(f"/api/trips/{trip_id}/settlement")
    assert settle_res.status_code == 200
    settle_data = settle_res.json()
    assert "settlements" in settle_data
    assert len(settle_data["settlements"]) == 1
    assert "whatsapp_text" in settle_data
    assert "whatsapp_url" in settle_data
    assert "api.whatsapp.com" in settle_data["whatsapp_url"]

def test_add_trip_and_custom_splits():
    # 1. Create a new test trip
    trip_res = client.post("/api/trips", json={
        "name": "Manali Trek Test",
        "description": "Himalayan trekking",
        "currency": "₹"
    })
    assert trip_res.status_code == 200
    trip_id = trip_res.json()["id"]

    # 2. Add members
    m1 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Alice", "avatar_color": "#10B981"}).json()["id"]
    m2 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Bob", "avatar_color": "#3B82F6"}).json()["id"]
    m3 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Charlie", "avatar_color": "#F59E0B"}).json()["id"]

    # 3. Add Equal Split Expense (Alice pays 3000 for Alice, Bob, Charlie)
    e1 = client.post(f"/api/trips/{trip_id}/expenses", json={
        "title": "Hotel Stay",
        "amount": 3000.0,
        "date": "2026-09-04",
        "category": "Stay",
        "payer_id": m1,
        "split_type": "equal",
        "splits": [
            {"member_id": m1, "share_amount": 1000.0, "percentage": 33.33},
            {"member_id": m2, "share_amount": 1000.0, "percentage": 33.33},
            {"member_id": m3, "share_amount": 1000.0, "percentage": 33.34},
        ],
        "notes": "Cabin in Solang Valley"
    })
    assert e1.status_code == 200

    # 4. Add Selected Members Split (Bob pays 1000 for Bob and Charlie only)
    e2 = client.post(f"/api/trips/{trip_id}/expenses", json={
        "title": "Paragliding",
        "amount": 1000.0,
        "date": "2026-09-04",
        "category": "Activities",
        "payer_id": m2,
        "split_type": "selected",
        "splits": [
            {"member_id": m2, "share_amount": 500.0, "percentage": 50.0},
            {"member_id": m3, "share_amount": 500.0, "percentage": 50.0},
        ],
        "notes": "Tandem paraglide"
    })
    assert e2.status_code == 200

    # 5. Add Custom Split (Charlie pays 2000: Alice had custom item 1000, remaining 1000 split equally between Bob and Charlie = 500 each)
    e3 = client.post(f"/api/trips/{trip_id}/expenses", json={
        "title": "Cafe Dinner",
        "amount": 2000.0,
        "date": "2026-09-04",
        "category": "Food",
        "payer_id": m3,
        "split_type": "custom",
        "splits": [
            {"member_id": m1, "share_amount": 1000.0, "percentage": None},
            {"member_id": m2, "share_amount": 500.0, "percentage": None},
            {"member_id": m3, "share_amount": 500.0, "percentage": None},
        ],
        "notes": "Old Manali Cafe"
    })
    assert e3.status_code == 200

    # 6. Check Settlement
    settle_res = client.get(f"/api/trips/{trip_id}/settlement")
    assert settle_res.status_code == 200
    settle = settle_res.json()
    assert settle["total_expenses"] == 6000.0

    # Net calculations:
    # Alice: Paid 3000, Owed (1000 + 1000) = 2000 -> Net +1000
    # Bob: Paid 1000, Owed (1000 + 500 + 500) = 2000 -> Net -1000
    # Charlie: Paid 2000, Owed (1000 + 500 + 500) = 2000 -> Net 0
    # Expected settlement: Bob pays Alice 1000! Total 1 transaction!
    assert len(settle["settlements"]) == 1
    assert settle["settlements"][0]["from_name"] == "Bob"
    assert settle["settlements"][0]["to_name"] == "Alice"
    assert settle["settlements"][0]["amount"] == 1000.0

    # 7. Record Settlement Payment (Bob pays Alice 1000)
    record_res = client.post(f"/api/trips/{trip_id}/settlements", json={
        "payer_id": m2,
        "receiver_id": m1,
        "amount": 1000.0,
        "date": "2026-09-04",
        "notes": "UPI GPay transfer"
    })
    assert record_res.status_code == 200
    settle_record_id = record_res.json()["id"]

    # 8. Check that settlement reduced all pending debts to 0
    settle_after = client.get(f"/api/trips/{trip_id}/settlement").json()
    assert len(settle_after["settlements"]) == 0
    assert len(settle_after["settlement_history"]) == 1
    assert settle_after["settlement_history"][0]["amount"] == 1000.0

    # 9. Test PDF and Excel exports with settlement history
    pdf_res = client.get(f"/api/trips/{trip_id}/export/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 1000

    excel_res = client.get(f"/api/trips/{trip_id}/export/excel")
    assert excel_res.status_code == 200
    assert len(excel_res.content) > 1000

    # 10. Test Undo settlement payment
    undo_res = client.delete(f"/api/settlements/{settle_record_id}")
    assert undo_res.status_code == 200

    # Debts should return to 1 transaction
    settle_undone = client.get(f"/api/trips/{trip_id}/settlement").json()
    assert len(settle_undone["settlements"]) == 1


def test_auth_flow():
    import time
    unique_email = f"traveler_{int(time.time())}@example.com"

    # 1. Test New User Signup
    signup_res = client.post("/api/auth/signup", json={
        "name": "Sarah Jenkins",
        "email": unique_email,
        "mobile": "+91 9988776655",
        "password": "initialpassword"
    })
    assert signup_res.status_code == 200
    signup_data = signup_res.json()
    assert "token" in signup_data
    assert signup_data["user"]["name"] == "Sarah Jenkins"
    token = signup_data["token"]

    # 2. Test /api/auth/me with Bearer token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["name"] == "Sarah Jenkins"

    # 3. Test Login with Initial Password
    login_res = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": "initialpassword"
    })
    assert login_res.status_code == 200
    assert "token" in login_res.json()

    # 4. Test Invalid Login
    bad_login = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": "wrongpassword"
    })
    assert bad_login.status_code == 401

    # 5. Test Password Reset with Unregistered Email (expect 404)
    bad_reset = client.post("/api/auth/reset-password", json={
        "email": "nonexistent_traveler@example.com",
        "new_password": "newpassword123"
    })
    assert bad_reset.status_code == 404

    # 6. Test Password Reset for Registered User
    reset_res = client.post("/api/auth/reset-password", json={
        "email": unique_email,
        "new_password": "newsecurepassword456"
    })
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert "token" in reset_data
    reset_token = reset_data["token"]

    # 7. Test Login with New Password
    new_login = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": "newsecurepassword456"
    })
    assert new_login.status_code == 200

    # Old password should no longer work
    old_login = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": "initialpassword"
    })
    assert old_login.status_code == 401

    # 8. Duplicate Email Signup check
    dup_res = client.post("/api/auth/signup", json={
        "name": "Sarah Duplicate",
        "email": unique_email,
        "password": "securepassword"
    })
    assert dup_res.status_code == 400

    # 9. Test User Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {reset_token}"})
    assert logout_res.status_code == 200

    # Token should now be invalid
    me_after_logout = client.get("/api/auth/me", headers={"Authorization": f"Bearer {reset_token}"})
    assert me_after_logout.status_code == 401

def test_demo_data_absence():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE email = 'nisarg@travel.com'")
    row = cursor.fetchone()
    cnt = row[0] if isinstance(row, (tuple, list)) else row["cnt"]
    assert cnt == 0, f"Expected 0 demo users, found {cnt}"

    cursor.execute("SELECT COUNT(*) as cnt FROM trips WHERE name LIKE '%Goa Beach & Road Trip%'")
    row = cursor.fetchone()
    trip_cnt = row[0] if isinstance(row, (tuple, list)) else row["cnt"]
    assert trip_cnt == 0, f"Expected 0 demo trips, found {trip_cnt}"
    conn.close()


def test_payment_mode_in_expenses():
    # Create trip and verify payment mode storage and report inclusion
    trip_res = client.post("/api/trips", json={
        "name": "Kerala Backwaters",
        "currency": "₹"
    })
    trip_id = trip_res.json()["id"]

    m1 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Nisarg"}).json()["id"]
    m2 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Dev"}).json()["id"]

    # Add expense with Credit Card
    exp_res = client.post(f"/api/trips/{trip_id}/expenses", json={
        "title": "Houseboat Stay",
        "amount": 15000.0,
        "date": "2026-09-04",
        "category": "Stay",
        "payer_id": m1,
        "payment_mode": "Credit Card",
        "split_type": "equal",
        "splits": [
            {"member_id": m1, "share_amount": 7500.0},
            {"member_id": m2, "share_amount": 7500.0},
        ],
        "notes": "Deluxe Alleppey houseboat"
    })
    assert exp_res.status_code == 200

    # Verify payment_mode in expenses list
    expenses = client.get(f"/api/trips/{trip_id}/expenses").json()
    assert len(expenses) == 1
    assert expenses[0]["payment_mode"] == "Credit Card"


def test_receipt_parsing():
    # 1. Test UPI GPay Text Parsing
    gpay_text = """
    Google Pay
    Paid to Fisherman's Wharf Goa
    ₹ 2,450.00
    Completed
    UPI transaction ID 424567890123
    Date: 2026-09-04
    Payment method: UPI
    """
    res1 = client.post("/api/receipts/parse-text", json={"text": gpay_text})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["amount"] == 2450.0
    assert "Fisherman" in data1["title"]
    assert data1["category"] == "Food"
    assert data1["payment_mode"] == "UPI"
    assert data1["date"] == "2026-09-04"

    # 2. Test Restaurant Bill Parsing
    bill_text = """
    THALASSA BEACH LOUNGE
    Small Vagator, Goa
    Date: 02/09/2026
    1x Greek Salad 450.00
    1x Calamari 680.00
    GRAND TOTAL: ₹ 3,608.00
    Paid by Credit Card
    """
    res2 = client.post("/api/receipts/parse-text", json={"text": bill_text})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["amount"] == 3608.0
    assert "Thalassa" in data2["title"]
    assert data2["category"] == "Food"
    assert data2["payment_mode"] == "Credit Card"
    assert data2["date"] == "2026-09-02"

    # 3. Test Sample Receipts Endpoint
    samples_res = client.get("/api/receipts/samples")
    assert samples_res.status_code == 200
    samples = samples_res.json()["samples"]
    assert len(samples) >= 3
    assert any(s["id"] == "gpay" for s in samples)

    # 4. Test Rupee Symbol OCR Misrecognition (₹ read as 2, e.g. ₹77.60 -> 277.60)
    uts_misread_text = """
    To Indian Railways UTS
    277.60
    Completed
    31 Aug 2026, 12:28pm
    State Bank of India 5343
    Payment of 277.60 completed
    Receiver's bank has confirmed deposit of money to Indian Railways UTS's bank account
    UPI transaction ID: 624329106044
    Google Pay - dp4886910-2@oksbi
    UPI
    GPay
    """
    res4 = client.post("/api/receipts/parse-text", json={"text": uts_misread_text})
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["amount"] == 77.60, f"Expected 77.60 but got {data4['amount']}"
    assert "Indian Railways" in data4["title"]
    assert data4["category"] == "Travel"
    assert data4["payment_mode"] == "UPI"
    assert data4["date"] == "2026-08-31"

def test_trip_update_and_delete():
    # Create trip
    r1 = client.post("/api/trips", json={"name": "Temp Trip", "description": "For update/delete", "currency": "₹"})
    assert r1.status_code == 200
    trip_id = r1.json()["id"]

    # Update trip
    r2 = client.put(f"/api/trips/{trip_id}", json={"name": "Renamed Trip", "description": "Updated desc", "currency": "$"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "Renamed Trip"
    assert r2.json()["currency"] == "$"

    # Delete trip
    r3 = client.delete(f"/api/trips/{trip_id}")
    assert r3.status_code == 200

    # Verify trip is deleted
    r4 = client.get(f"/api/trips/{trip_id}")
    assert r4.status_code == 404

def test_expense_update():
    trip_res = client.post("/api/trips", json={"name": "Goa Trip Update Test", "currency": "₹"})
    assert trip_res.status_code == 200
    trip_id = trip_res.json()["id"]

    m1 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Alice"}).json()["id"]
    m2 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Bob"}).json()["id"]

    create_res = client.post(f"/api/trips/{trip_id}/expenses", json={
        "title": "Dinner",
        "amount": 1000.0,
        "date": "2026-09-01",
        "category": "Food",
        "payer_id": m1,
        "split_type": "equal",
        "payment_mode": "UPI",
        "splits": [
            {"member_id": m1, "share_amount": 500.0},
            {"member_id": m2, "share_amount": 500.0}
        ],
        "notes": "Initial dinner"
    })
    assert create_res.status_code == 200
    expense_id = create_res.json()["id"]

    update_res = client.put(f"/api/expenses/{expense_id}", json={
        "title": "Seafood Banquet",
        "amount": 1500.0,
        "date": "2026-09-02",
        "category": "Food",
        "payer_id": m1,
        "split_type": "custom",
        "payment_mode": "Credit Card",
        "splits": [
            {"member_id": m1, "share_amount": 1000.0, "percentage": None},
            {"member_id": m2, "share_amount": 500.0, "percentage": None}
        ],
        "notes": "Updated with drinks and desserts"
    })
    assert update_res.status_code == 200

    expenses = client.get(f"/api/trips/{trip_id}/expenses").json()
    assert len(expenses) == 1
    exp = expenses[0]
    assert exp["title"] == "Seafood Banquet"
    assert exp["amount"] == 1500.0
    assert exp["date"] == "2026-09-02"
    assert exp["payment_mode"] == "Credit Card"
    assert exp["split_type"] == "custom"
    assert len(exp["splits"]) == 2
    alice_split = next(s for s in exp["splits"] if s["member_id"] == m1)
    assert alice_split["share_amount"] == 1000.0

def test_member_pdf_export():
    trip_res = client.post("/api/trips", json={"name": "Member PDF Test Trip", "currency": "₹"})
    assert trip_res.status_code == 200
    trip_id = trip_res.json()["id"]

    m1 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Rohan", "phone": "9876543210"}).json()["id"]
    m2 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Kavya", "phone": "9876543211"}).json()["id"]

    client.post(f"/api/trips/{trip_id}/expenses", json={
        "title": "Hotel Check-in",
        "amount": 4000.0,
        "date": "2026-09-03",
        "category": "Stay",
        "payer_id": m1,
        "split_type": "equal",
        "splits": [
            {"member_id": m1, "share_amount": 2000.0},
            {"member_id": m2, "share_amount": 2000.0}
        ]
    })

    pdf_res1 = client.get(f"/api/trips/{trip_id}/members/{m1}/export/pdf")
    assert pdf_res1.status_code == 200
    assert pdf_res1.headers["content-type"] == "application/pdf"
    assert len(pdf_res1.content) > 1000

    pdf_res2 = client.get(f"/api/trips/{trip_id}/members/{m2}/export/pdf")
    assert pdf_res2.status_code == 200
    assert pdf_res2.headers["content-type"] == "application/pdf"
    assert len(pdf_res2.content) > 1000

def test_settings_and_multi_vehicle_features():
    # 1. Signup user & get token
    email = f"settings_test_{int(datetime.now().timestamp())}@example.com"
    su_res = client.post("/api/auth/signup", json={
        "name": "Alex Mercer",
        "email": email,
        "mobile": "9988776655",
        "password": "initial_password_123"
    })
    assert su_res.status_code == 200
    token = su_res.json()["token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # 2. Update profile
    p_res = client.put("/api/auth/profile", json={"name": "Alexander Mercer", "mobile": "9988776600"}, headers=auth_header)
    assert p_res.status_code == 200
    assert p_res.json()["user"]["name"] == "Alexander Mercer"
    assert p_res.json()["user"]["mobile"] == "9988776600"

    # 3. Change password
    # 3a. Invalid current password
    bad_pw = client.post("/api/auth/change-password", json={
        "current_password": "wrong_password",
        "new_password": "new_secure_password_456"
    }, headers=auth_header)
    assert bad_pw.status_code == 400

    # 3b. Correct password change
    ok_pw = client.post("/api/auth/change-password", json={
        "current_password": "initial_password_123",
        "new_password": "new_secure_password_456"
    }, headers=auth_header)
    assert ok_pw.status_code == 200

    # 3c. Login with new password
    login_new = client.post("/api/auth/login", json={"email": email, "password": "new_secure_password_456"})
    assert login_new.status_code == 200

    # 4. Create trip for vehicle and category testing
    t_res = client.post("/api/trips", json={"name": "Multi-Vehicle Road Trip", "currency": "₹"}, headers=auth_header)
    assert t_res.status_code == 200
    trip_id = t_res.json()["id"]

    # 5. Test categories
    cats_res = client.get(f"/api/trips/{trip_id}/categories")
    assert cats_res.status_code == 200
    cats = cats_res.json()["categories"]
    assert len(cats) >= 7 # Default categories initialized

    # Add custom category
    add_cat = client.post(f"/api/trips/{trip_id}/categories", json={"name": "Nightlife & Pubs", "icon": "🍸"})
    assert add_cat.status_code == 200
    cat_id = add_cat.json()["id"]
    assert add_cat.json()["name"] == "Nightlife & Pubs"

    # Delete custom category
    del_cat = client.delete(f"/api/trips/{trip_id}/categories/{cat_id}")
    assert del_cat.status_code == 200

    # 6. Test payment modes
    modes_res = client.get(f"/api/trips/{trip_id}/payment-modes")
    assert modes_res.status_code == 200
    modes = modes_res.json()["payment_modes"]
    assert len(modes) >= 5 # Default payment modes initialized

    # Add custom payment mode
    add_mode = client.post(f"/api/trips/{trip_id}/payment-modes", json={"name": "Forex Card", "icon": "💳"})
    assert add_mode.status_code == 200
    mode_id = add_mode.json()["id"]

    # Delete payment mode
    del_mode = client.delete(f"/api/trips/{trip_id}/payment-modes/{mode_id}")
    assert del_mode.status_code == 200

    # 7. Test Multi-Vehicle Management
    # 7a. Get vehicles (initializes default Ertiga)
    v_list = client.get(f"/api/trips/{trip_id}/vehicles").json()["vehicles"]
    assert len(v_list) == 1
    v1_id = v_list[0]["id"]

    # 7b. Add second vehicle: Hyundai Creta (Petrol)
    add_v2 = client.post(f"/api/trips/{trip_id}/vehicles", json={
        "vehicle_type": "SUV",
        "brand_model": "Hyundai Creta",
        "fuel_type": "Petrol",
        "benchmark_mileage": 17.0,
        "initial_odometer": 25000.0
    })
    assert add_v2.status_code == 200
    v2_id = add_v2.json()["id"]

    # 7c. Add third vehicle: Royal Enfield Hunter 350 (Bike)
    add_v3 = client.post(f"/api/trips/{trip_id}/vehicles", json={
        "vehicle_type": "Bike",
        "brand_model": "Royal Enfield Hunter 350",
        "fuel_type": "Petrol",
        "benchmark_mileage": 36.2,
        "initial_odometer": 5000.0
    })
    assert add_v3.status_code == 200
    v3_id = add_v3.json()["id"]

    # 7d. Verify all 3 vehicles exist
    all_v = client.get(f"/api/trips/{trip_id}/vehicles").json()["vehicles"]
    assert len(all_v) == 3

    # 7e. Log fuel for vehicle 2 (Creta)
    m1 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Alex"}).json()["id"]
    f_v2 = client.post(f"/api/trips/{trip_id}/fuel-logs", json={
        "date": "2026-09-04",
        "vehicle_id": v2_id,
        "odometer_reading": 25300.0,
        "distance_run": 300.0,
        "fuel_amount": 2000.0,
        "fuel_quantity": 20.0,
        "fuel_price_per_unit": 100.0,
        "is_full_tank": True,
        "payer_id": m1
    })
    assert f_v2.status_code == 200

    # 7f. Check mileage summary contains fleet + per-vehicle data
    sum_res = client.get(f"/api/trips/{trip_id}/mileage-summary").json()
    assert sum_res["vehicles_count"] == 3
    assert len(sum_res["vehicles"]) == 3
    assert sum_res["total_fuel_cost"] == 2000.0

    # 7g. Delete third vehicle
    del_v3 = client.delete(f"/api/trips/{trip_id}/vehicles/{v3_id}")
    assert del_v3.status_code == 200
    remaining_v = client.get(f"/api/trips/{trip_id}/vehicles").json()["vehicles"]
    assert len(remaining_v) == 2

if __name__ == "__main__":
    init_db()
    test_root()
    test_list_and_dashboard_flow()
    test_add_trip_and_custom_splits()
    test_trip_update_and_delete()
    test_expense_update()
    test_member_pdf_export()
    test_auth_flow()
    test_payment_mode_in_expenses()
    test_receipt_parsing()
    test_settings_and_multi_vehicle_features()
    from backend.test_mileage import test_mileage_catalog, test_ertiga_cng_trip_mileage
    test_mileage_catalog()
    test_ertiga_cng_trip_mileage()
    print("ALL TEST CASES PASSED SUCCESSFULLY!")

