import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200

def test_list_trips():
    response = client.get("/api/trips")
    assert response.status_code == 200
    trips = response.json()
    assert len(trips) >= 1
    assert "name" in trips[0]

def test_get_dashboard():
    response = client.get("/api/trips/1/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "kpis" in data
    assert data["kpis"]["total_spent"] > 0
    assert "category_breakdown" in data
    assert "member_spending" in data
    assert "settlements" in data

def test_get_settlement_and_whatsapp():
    response = client.get("/api/trips/1/settlement")
    assert response.status_code == 200
    data = response.json()
    assert "settlements" in data
    assert "whatsapp_text" in data
    assert "whatsapp_url" in data
    assert "api.whatsapp.com" in data["whatsapp_url"]
    assert len(data["settlements"]) > 0

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
    # 1. Test Demo User Login
    login_res = client.post("/api/auth/login", json={
        "email": "nisarg@travel.com",
        "password": "password123"
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "token" in login_data
    assert login_data["user"]["email"] == "nisarg@travel.com"
    token = login_data["token"]

    # 2. Test /api/auth/me with Bearer token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["name"] == "Nisarg Patel"

    # 3. Test Invalid Login
    bad_login = client.post("/api/auth/login", json={
        "email": "nisarg@travel.com",
        "password": "wrongpassword"
    })
    assert bad_login.status_code == 401

    # 4. Test New User Signup
    import time
    unique_email = f"traveler_{int(time.time())}@example.com"
    signup_res = client.post("/api/auth/signup", json={
        "name": "Sarah Jenkins",
        "email": unique_email,
        "mobile": "+91 9988776655",
        "password": "securepassword"
    })
    assert signup_res.status_code == 200
    signup_data = signup_res.json()
    assert "token" in signup_data
    assert signup_data["user"]["name"] == "Sarah Jenkins"
    sarah_token = signup_data["token"]

    # 5. Duplicate Email Signup check
    dup_res = client.post("/api/auth/signup", json={
        "name": "Sarah Duplicate",
        "email": unique_email,
        "password": "securepassword"
    })
    assert dup_res.status_code == 400

    # 6. Test User Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {sarah_token}"})
    assert logout_res.status_code == 200

    # Sarah token should now be invalid
    me_after_logout = client.get("/api/auth/me", headers={"Authorization": f"Bearer {sarah_token}"})
    assert me_after_logout.status_code == 401


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

if __name__ == "__main__":
    init_db()
    test_root()
    test_list_trips()
    test_get_dashboard()
    test_get_settlement_and_whatsapp()
    test_add_trip_and_custom_splits()
    test_trip_update_and_delete()
    test_auth_flow()
    test_payment_mode_in_expenses()
    test_receipt_parsing()
    from backend.test_mileage import test_mileage_catalog, test_ertiga_cng_trip_mileage
    test_mileage_catalog()
    test_ertiga_cng_trip_mileage()
    print("ALL TEST CASES PASSED SUCCESSFULLY!")
