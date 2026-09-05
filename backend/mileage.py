"""
Mileage and Fuel Tracking Module for Spillter
Supports Car and Bike with CNG, Petrol, and Diesel options.
Includes brand/model benchmark catalog (e.g., Maruti Suzuki Ertiga CNG),
real-world mileage calculations (km/L and km/kg), running cost per km,
and trip fuel analytics.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.database import get_db_connection

# Comprehensive vehicle benchmark catalog for Indian market
VEHICLE_CATALOG = {
    "Car": [
        {
            "brand": "Maruti Suzuki",
            "model": "Maruti Suzuki Ertiga",
            "fuels": {
                "CNG": {"benchmark": 26.11, "unit": "km/kg", "capacity": 60.0},
                "Petrol": {"benchmark": 20.51, "unit": "km/L", "capacity": 45.0},
                "Diesel": {"benchmark": 24.20, "unit": "km/L", "capacity": 45.0}
            }
        },
        {
            "brand": "Maruti Suzuki",
            "model": "Maruti Suzuki Swift",
            "fuels": {
                "Petrol": {"benchmark": 24.80, "unit": "km/L", "capacity": 37.0},
                "CNG": {"benchmark": 30.90, "unit": "km/kg", "capacity": 55.0},
                "Diesel": {"benchmark": 28.40, "unit": "km/L", "capacity": 37.0}
            }
        },
        {
            "brand": "Maruti Suzuki",
            "model": "Maruti Suzuki Brezza",
            "fuels": {
                "Petrol": {"benchmark": 19.80, "unit": "km/L", "capacity": 48.0},
                "CNG": {"benchmark": 25.51, "unit": "km/kg", "capacity": 55.0}
            }
        },
        {
            "brand": "Maruti Suzuki",
            "model": "Maruti Suzuki Baleno",
            "fuels": {
                "Petrol": {"benchmark": 22.35, "unit": "km/L", "capacity": 37.0},
                "CNG": {"benchmark": 30.61, "unit": "km/kg", "capacity": 55.0}
            }
        },
        {
            "brand": "Maruti Suzuki",
            "model": "Maruti Suzuki WagonR",
            "fuels": {
                "Petrol": {"benchmark": 24.35, "unit": "km/L", "capacity": 32.0},
                "CNG": {"benchmark": 34.05, "unit": "km/kg", "capacity": 60.0}
            }
        },
        {
            "brand": "Maruti Suzuki",
            "model": "Maruti Suzuki Dzire",
            "fuels": {
                "Petrol": {"benchmark": 24.12, "unit": "km/L", "capacity": 37.0},
                "CNG": {"benchmark": 31.12, "unit": "km/kg", "capacity": 55.0}
            }
        },
        {
            "brand": "Hyundai",
            "model": "Hyundai Creta",
            "fuels": {
                "Petrol": {"benchmark": 17.40, "unit": "km/L", "capacity": 50.0},
                "Diesel": {"benchmark": 21.80, "unit": "km/L", "capacity": 50.0}
            }
        },
        {
            "brand": "Hyundai",
            "model": "Hyundai Venue",
            "fuels": {
                "Petrol": {"benchmark": 17.50, "unit": "km/L", "capacity": 45.0},
                "Diesel": {"benchmark": 23.40, "unit": "km/L", "capacity": 45.0}
            }
        },
        {
            "brand": "Hyundai",
            "model": "Hyundai i20",
            "fuels": {
                "Petrol": {"benchmark": 20.00, "unit": "km/L", "capacity": 37.0},
                "Diesel": {"benchmark": 25.20, "unit": "km/L", "capacity": 37.0}
            }
        },
        {
            "brand": "Tata",
            "model": "Tata Nexon",
            "fuels": {
                "Petrol": {"benchmark": 17.20, "unit": "km/L", "capacity": 44.0},
                "Diesel": {"benchmark": 23.20, "unit": "km/L", "capacity": 44.0},
                "CNG": {"benchmark": 24.00, "unit": "km/kg", "capacity": 60.0}
            }
        },
        {
            "brand": "Tata",
            "model": "Tata Punch",
            "fuels": {
                "Petrol": {"benchmark": 18.80, "unit": "km/L", "capacity": 37.0},
                "CNG": {"benchmark": 26.90, "unit": "km/kg", "capacity": 60.0}
            }
        },
        {
            "brand": "Tata",
            "model": "Tata Altroz",
            "fuels": {
                "Petrol": {"benchmark": 19.30, "unit": "km/L", "capacity": 37.0},
                "Diesel": {"benchmark": 23.60, "unit": "km/L", "capacity": 37.0},
                "CNG": {"benchmark": 26.20, "unit": "km/kg", "capacity": 60.0}
            }
        },
        {
            "brand": "Mahindra",
            "model": "Mahindra Thar",
            "fuels": {
                "Petrol": {"benchmark": 15.20, "unit": "km/L", "capacity": 57.0},
                "Diesel": {"benchmark": 15.20, "unit": "km/L", "capacity": 57.0}
            }
        },
        {
            "brand": "Mahindra",
            "model": "Mahindra Scorpio-N / Classic",
            "fuels": {
                "Petrol": {"benchmark": 13.00, "unit": "km/L", "capacity": 57.0},
                "Diesel": {"benchmark": 16.20, "unit": "km/L", "capacity": 60.0}
            }
        },
        {
            "brand": "Mahindra",
            "model": "Mahindra XUV700",
            "fuels": {
                "Petrol": {"benchmark": 13.00, "unit": "km/L", "capacity": 60.0},
                "Diesel": {"benchmark": 16.50, "unit": "km/L", "capacity": 60.0}
            }
        },
        {
            "brand": "Toyota",
            "model": "Toyota Innova Crysta / Hycross",
            "fuels": {
                "Petrol": {"benchmark": 16.13, "unit": "km/L", "capacity": 52.0},
                "Diesel": {"benchmark": 15.10, "unit": "km/L", "capacity": 55.0}
            }
        },
        {
            "brand": "Toyota",
            "model": "Toyota Fortuner",
            "fuels": {
                "Petrol": {"benchmark": 10.00, "unit": "km/L", "capacity": 80.0},
                "Diesel": {"benchmark": 14.40, "unit": "km/L", "capacity": 80.0}
            }
        },
        {
            "brand": "Kia",
            "model": "Kia Seltos",
            "fuels": {
                "Petrol": {"benchmark": 17.00, "unit": "km/L", "capacity": 50.0},
                "Diesel": {"benchmark": 20.70, "unit": "km/L", "capacity": 50.0}
            }
        },
        {
            "brand": "Honda",
            "model": "Honda City",
            "fuels": {
                "Petrol": {"benchmark": 18.40, "unit": "km/L", "capacity": 40.0},
                "Diesel": {"benchmark": 24.10, "unit": "km/L", "capacity": 40.0}
            }
        },
        {
            "brand": "Custom",
            "model": "Custom Car",
            "fuels": {
                "CNG": {"benchmark": 25.0, "unit": "km/kg", "capacity": 60.0},
                "Petrol": {"benchmark": 18.0, "unit": "km/L", "capacity": 45.0},
                "Diesel": {"benchmark": 20.0, "unit": "km/L", "capacity": 45.0}
            }
        }
    ],
    "Bike": [
        {
            "brand": "Hero",
            "model": "Hero Splendor Plus",
            "fuels": {
                "Petrol": {"benchmark": 65.0, "unit": "km/L", "capacity": 9.8}
            }
        },
        {
            "brand": "Honda",
            "model": "Honda Activa 6G",
            "fuels": {
                "Petrol": {"benchmark": 50.0, "unit": "km/L", "capacity": 5.3}
            }
        },
        {
            "brand": "Bajaj",
            "model": "Bajaj Pulsar 150",
            "fuels": {
                "Petrol": {"benchmark": 47.5, "unit": "km/L", "capacity": 15.0}
            }
        },
        {
            "brand": "Royal Enfield",
            "model": "Royal Enfield Classic 350",
            "fuels": {
                "Petrol": {"benchmark": 35.0, "unit": "km/L", "capacity": 13.0}
            }
        },
        {
            "brand": "Yamaha",
            "model": "Yamaha FZ / MT-15",
            "fuels": {
                "Petrol": {"benchmark": 45.0, "unit": "km/L", "capacity": 13.0}
            }
        },
        {
            "brand": "TVS",
            "model": "TVS Jupiter",
            "fuels": {
                "Petrol": {"benchmark": 50.0, "unit": "km/L", "capacity": 6.0}
            }
        },
        {
            "brand": "TVS",
            "model": "TVS Apache RTR 160",
            "fuels": {
                "Petrol": {"benchmark": 45.0, "unit": "km/L", "capacity": 12.0}
            }
        },
        {
            "brand": "Suzuki",
            "model": "Suzuki Access 125",
            "fuels": {
                "Petrol": {"benchmark": 52.0, "unit": "km/L", "capacity": 5.0}
            }
        },
        {
            "brand": "KTM",
            "model": "KTM Duke 200/250/390",
            "fuels": {
                "Petrol": {"benchmark": 30.0, "unit": "km/L", "capacity": 13.5}
            }
        },
        {
            "brand": "Custom",
            "model": "Custom Bike",
            "fuels": {
                "Petrol": {"benchmark": 45.0, "unit": "km/L", "capacity": 10.0}
            }
        }
    ]
}


def get_vehicle_catalogs() -> Dict[str, Any]:
    """Return list of supported vehicle types, models, and fuel benchmarks."""
    return VEHICLE_CATALOG


def get_default_benchmark(vehicle_type: str, model_name: str, fuel_type: str) -> float:
    """Lookup standard benchmark mileage for a model and fuel."""
    catalog = VEHICLE_CATALOG.get(vehicle_type, VEHICLE_CATALOG["Car"])
    for item in catalog:
        if item["model"].lower() == model_name.lower():
            if fuel_type in item["fuels"]:
                return item["fuels"][fuel_type]["benchmark"]
    # Default fallbacks
    if fuel_type == "CNG":
        return 26.11 if vehicle_type == "Car" else 40.0
    elif fuel_type == "Diesel":
        return 20.0
    return 18.0 if vehicle_type == "Car" else 45.0


def get_trip_vehicle(trip_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve vehicle details configured for this trip."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM trip_vehicles WHERE trip_id = ?", (trip_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def set_trip_vehicle(trip_id: int, vehicle_type: str, brand_model: str, fuel_type: str,
                     benchmark_mileage: float, initial_odometer: float) -> Dict[str, Any]:
    """Create or update vehicle settings for a trip."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    existing = cursor.execute("SELECT id FROM trip_vehicles WHERE trip_id = ?", (trip_id,)).fetchone()
    if existing:
        cursor.execute("""
        UPDATE trip_vehicles
        SET vehicle_type = ?, brand_model = ?, fuel_type = ?, benchmark_mileage = ?, initial_odometer = ?
        WHERE trip_id = ?
        """, (vehicle_type, brand_model, fuel_type, benchmark_mileage, initial_odometer, trip_id))
        v_id = existing["id"]
    else:
        cursor.execute("""
        INSERT INTO trip_vehicles (trip_id, vehicle_type, brand_model, fuel_type, benchmark_mileage, initial_odometer, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (trip_id, vehicle_type, brand_model, fuel_type, benchmark_mileage, initial_odometer, now))
        v_id = cursor.lastrowid

    conn.commit()
    row = cursor.execute("SELECT * FROM trip_vehicles WHERE id = ?", (v_id,)).fetchone()
    conn.close()
    return dict(row)


def get_fuel_logs(trip_id: int) -> List[Dict[str, Any]]:
    """
    Get all fuel logs for a trip with calculated segment distances and segment mileage.
    """
    conn = get_db_connection()
    v_row = conn.execute("SELECT * FROM trip_vehicles WHERE trip_id = ?", (trip_id,)).fetchone()
    initial_odo = v_row["initial_odometer"] if v_row else 0.0
    fuel_unit = "km/kg" if (v_row and v_row["fuel_type"] == "CNG") else "km/L"

    logs = conn.execute("""
    SELECT f.*, m.name as payer_name, m.avatar_color as payer_color
    FROM fuel_logs f
    LEFT JOIN members m ON f.payer_id = m.id
    WHERE f.trip_id = ?
    ORDER BY f.odometer_reading ASC, f.date ASC, f.id ASC
    """, (trip_id,)).fetchall()
    conn.close()

    results = []
    prev_odo = initial_odo

    for log in logs:
        item = dict(log)
        odo = item["odometer_reading"]

        # Calculate distance run since previous fill
        dist = max(0.0, odo - prev_odo)
        item["calculated_segment_distance"] = round(dist, 1)

        # Segment mileage: distance divided by fuel quantity
        qty = item["fuel_quantity"]
        if qty > 0 and dist > 0:
            seg_mileage = round(dist / qty, 2)
            item["calculated_segment_mileage"] = seg_mileage
            item["calculated_cost_per_km"] = round(item["fuel_amount"] / dist, 2)
        else:
            item["calculated_segment_mileage"] = 0.0
            item["calculated_cost_per_km"] = 0.0

        item["mileage_unit"] = fuel_unit
        results.append(item)
        prev_odo = odo

    return results


def calculate_trip_mileage_summary(trip_id: int) -> Dict[str, Any]:
    """
    Calculate comprehensive trip mileage, total distance run, fuel consumption,
    average kmpl or km/kg, running cost per km, and comparison against benchmark.
    """
    conn = get_db_connection()
    v_row = conn.execute("SELECT * FROM trip_vehicles WHERE trip_id = ?", (trip_id,)).fetchone()
    logs = conn.execute("""
    SELECT * FROM fuel_logs
    WHERE trip_id = ?
    ORDER BY odometer_reading ASC, date ASC, id ASC
    """, (trip_id,)).fetchall()
    members_count = conn.execute("SELECT COUNT(*) FROM members WHERE trip_id = ?", (trip_id,)).fetchone()[0] or 1
    conn.close()

    vehicle = dict(v_row) if v_row else {
        "vehicle_type": "Car",
        "brand_model": "Maruti Suzuki Ertiga",
        "fuel_type": "CNG",
        "benchmark_mileage": 26.11,
        "initial_odometer": 0.0
    }

    fuel_type = vehicle["fuel_type"]
    is_cng = (fuel_type == "CNG")
    quantity_unit = "kg" if is_cng else "L"
    mileage_unit = "km/kg" if is_cng else "km/L"
    benchmark = vehicle.get("benchmark_mileage") or 20.0
    initial_odo = vehicle.get("initial_odometer") or 0.0

    if not logs:
        return {
            "vehicle": vehicle,
            "total_distance_km": 0.0,
            "total_fuel_quantity": 0.0,
            "quantity_unit": quantity_unit,
            "mileage_unit": mileage_unit,
            "total_fuel_cost": 0.0,
            "average_mileage": 0.0,
            "benchmark_mileage": benchmark,
            "efficiency_percentage": 0.0,
            "efficiency_label": "No fuel logs yet",
            "cost_per_km": 0.0,
            "cost_per_person_km": 0.0,
            "fuel_logs_count": 0,
            "latest_odometer": initial_odo,
            "initial_odometer": initial_odo
        }

    total_fuel_qty = sum(l["fuel_quantity"] for l in logs)
    total_fuel_cost = sum(l["fuel_amount"] for l in logs)
    latest_odo = max(l["odometer_reading"] for l in logs)
    total_distance = max(0.0, latest_odo - initial_odo)

    # If initial odometer was not set or matches latest, fallback to summing recorded segment distances
    if total_distance <= 0.0 and len(logs) > 0:
        total_distance = sum(l["distance_run"] for l in logs if l["distance_run"] > 0)

    # Average mileage
    avg_mileage = round(total_distance / total_fuel_qty, 2) if total_fuel_qty > 0 and total_distance > 0 else 0.0

    # Cost per km
    cost_per_km = round(total_fuel_cost / total_distance, 2) if total_distance > 0 else 0.0
    cost_per_person_km = round(cost_per_km / members_count, 2) if members_count > 0 else cost_per_km

    # Efficiency vs Benchmark
    if benchmark > 0 and avg_mileage > 0:
        efficiency_pct = round((avg_mileage / benchmark) * 100, 1)
        if efficiency_pct >= 95:
            eff_label = "🌟 Outstanding (Near or exceeds ARAI benchmark)"
        elif efficiency_pct >= 85:
            eff_label = "✅ High Highway Efficiency (Great performance)"
        elif efficiency_pct >= 70:
            eff_label = "👍 Normal Real-World Driving (Mixed traffic)"
        else:
            eff_label = "⚠️ Heavy Load / City Traffic / Hills"
    else:
        efficiency_pct = 0.0
        eff_label = "Log fuel & distance to see efficiency"

    return {
        "vehicle": vehicle,
        "total_distance_km": round(total_distance, 1),
        "total_fuel_quantity": round(total_fuel_qty, 2),
        "quantity_unit": quantity_unit,
        "mileage_unit": mileage_unit,
        "total_fuel_cost": round(total_fuel_cost, 2),
        "average_mileage": avg_mileage,
        "benchmark_mileage": round(benchmark, 2),
        "efficiency_percentage": efficiency_pct,
        "efficiency_label": eff_label,
        "cost_per_km": cost_per_km,
        "cost_per_person_km": cost_per_person_km,
        "fuel_logs_count": len(logs),
        "latest_odometer": round(latest_odo, 1),
        "initial_odometer": round(initial_odo, 1)
    }
