"""
Automated unit tests for Spillter Fuel & Mileage Tracking Module:
- Car & Bike catalogs
- Maruti Suzuki Ertiga CNG trip with multiple fill-ups
- Tank-to-tank and trip average mileage calculations (km/kg and km/L)
- Running cost per km
- Comparison against manufacturer benchmark
- Automatic expense sync into group settlement
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db

client = TestClient(app)

def test_mileage_catalog():
    res = client.get("/api/mileage/catalogs")
    assert res.status_code == 200
    data = res.json()
    assert "Car" in data
    assert "Bike" in data
    cars = data["Car"]
    ertiga = next((c for c in cars if "Ertiga" in c["model"]), None)
    assert ertiga is not None
    assert "CNG" in ertiga["fuels"]
    assert ertiga["fuels"]["CNG"]["benchmark"] == 26.11
    assert ertiga["fuels"]["CNG"]["unit"] == "km/kg"

def test_ertiga_cng_trip_mileage():
    init_db()

    # 1. Create test trip
    trip_res = client.post("/api/trips", json={
        "name": "Goa Road Trip (Ertiga CNG)",
        "description": "Family trip in Ertiga CNG",
        "currency": "₹"
    })
    assert trip_res.status_code == 200
    trip_id = trip_res.json()["id"]

    # 2. Add members
    m1 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Nisarg", "avatar_color": "#4F46E5"}).json()["id"]
    m2 = client.post(f"/api/trips/{trip_id}/members", json={"name": "Dev", "avatar_color": "#10B981"}).json()["id"]

    # 3. Setup Trip Vehicle as Maruti Suzuki Ertiga (CNG)
    v_res = client.post(f"/api/trips/{trip_id}/vehicle", json={
        "vehicle_type": "Car",
        "brand_model": "Maruti Suzuki Ertiga",
        "fuel_type": "CNG",
        "benchmark_mileage": 26.11,
        "initial_odometer": 10000.0
    })
    assert v_res.status_code == 200
    vehicle = v_res.json()
    assert vehicle["brand_model"] == "Maruti Suzuki Ertiga"
    assert vehicle["fuel_type"] == "CNG"
    assert vehicle["benchmark_mileage"] == 26.11
    assert vehicle["initial_odometer"] == 10000.0

    # 4. Fill 1: at 10250 km (250 km run since start), filled 10.0 kg CNG @ ₹85/kg = ₹850
    # Auto-add to trip expenses so it splits between Nisarg and Dev
    f1 = client.post(f"/api/trips/{trip_id}/fuel-logs", json={
        "date": "2026-09-01",
        "odometer_reading": 10250.0,
        "distance_run": 250.0,
        "fuel_amount": 850.0,
        "fuel_quantity": 10.0,
        "fuel_price_per_unit": 85.0,
        "is_full_tank": True,
        "fuel_type": "CNG",
        "payer_id": m1,
        "notes": "Expressway CNG Pump",
        "add_to_expenses": True
    })
    assert f1.status_code == 200
    assert f1.json()["expense_id"] is not None

    # 5. Fill 2: at 10510 km (260 km run), filled 10.5 kg CNG @ ₹84/kg = ₹882
    f2 = client.post(f"/api/trips/{trip_id}/fuel-logs", json={
        "date": "2026-09-02",
        "odometer_reading": 10510.0,
        "distance_run": 260.0,
        "fuel_amount": 882.0,
        "fuel_quantity": 10.5,
        "fuel_price_per_unit": 84.0,
        "is_full_tank": True,
        "fuel_type": "CNG",
        "payer_id": m2,
        "notes": "Kolhapur Bypass CNG",
        "add_to_expenses": True
    })
    assert f2.status_code == 200

    # 6. Fill 3: at 10760 km (250 km run), filled 10.0 kg CNG @ ₹86/kg = ₹860
    f3 = client.post(f"/api/trips/{trip_id}/fuel-logs", json={
        "date": "2026-09-03",
        "odometer_reading": 10760.0,
        "distance_run": 250.0,
        "fuel_amount": 860.0,
        "fuel_quantity": 10.0,
        "fuel_price_per_unit": 86.0,
        "is_full_tank": True,
        "fuel_type": "CNG",
        "payer_id": m1,
        "notes": "Panaji City CNG",
        "add_to_expenses": True
    })
    assert f3.status_code == 200

    # 7. Check Fuel Logs endpoint & calculated segment metrics
    logs_res = client.get(f"/api/trips/{trip_id}/fuel-logs")
    assert logs_res.status_code == 200
    logs = logs_res.json()["logs"]
    assert len(logs) == 3
    # First segment: 10250 - 10000 = 250 km, 10 kg -> 25.0 km/kg
    assert logs[0]["calculated_segment_distance"] == 250.0
    assert logs[0]["calculated_segment_mileage"] == 25.0
    assert logs[0]["mileage_unit"] == "km/kg"

    # Second segment: 10510 - 10250 = 260 km, 10.5 kg -> 24.76 km/kg
    assert logs[1]["calculated_segment_distance"] == 260.0
    assert logs[1]["calculated_segment_mileage"] == 24.76

    # 8. Check Mileage Summary & Efficiency Analysis
    summary_res = client.get(f"/api/trips/{trip_id}/mileage-summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()

    # Total distance: 10760 - 10000 = 760.0 km
    assert summary["total_distance_km"] == 760.0
    # Total fuel: 10.0 + 10.5 + 10.0 = 30.5 kg
    assert summary["total_fuel_quantity"] == 30.5
    assert summary["quantity_unit"] == "kg"
    assert summary["mileage_unit"] == "km/kg"
    # Total cost: 850 + 882 + 860 = 2592.0
    assert summary["total_fuel_cost"] == 2592.0
    # Average Mileage: 760 / 30.5 = 24.92 km/kg
    assert summary["average_mileage"] == 24.92
    # Cost per km: 2592 / 760 = 3.41 ₹/km
    assert summary["cost_per_km"] == 3.41
    # Cost per person km (2 members): 3.41 / 2 = 1.71 ₹/person-km
    assert summary["cost_per_person_km"] == 1.71
    # Efficiency vs Benchmark: 24.92 / 26.11 * 100 = 95.4%
    assert summary["efficiency_percentage"] > 90.0

    # 9. Verify that auto-added expenses exist in trip expenses and are split
    expenses = client.get(f"/api/trips/{trip_id}/expenses").json()
    assert len(expenses) == 3
    assert all(e["category"] == "Travel" for e in expenses)

    # 10. Verify settlement debts reflect the fuel expenses
    settlement = client.get(f"/api/trips/{trip_id}/settlement").json()
    assert settlement["total_expenses"] == 2592.0
    # Nisarg paid 850 + 860 = 1710, owed 1296 -> Net +414
    # Dev paid 882, owed 1296 -> Net -414
    # Dev should owe Nisarg 414.0
    assert len(settlement["settlements"]) == 1
    assert settlement["settlements"][0]["from_name"] == "Dev"
    assert settlement["settlements"][0]["to_name"] == "Nisarg"
    assert settlement["settlements"][0]["amount"] == 414.0

if __name__ == "__main__":
    test_mileage_catalog()
    test_ertiga_cng_trip_mileage()
    print("ALL FUEL & MILEAGE TESTS PASSED SUCCESSFULLY!")
