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


def get_trip_vehicles(trip_id: int) -> List[Dict[str, Any]]:
    """Retrieve all vehicles configured for this trip."""
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM trip_vehicles WHERE trip_id = ? ORDER BY id ASC", (trip_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trip_vehicle(trip_id: int, vehicle_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a vehicle details configured for this trip (by ID or first vehicle)."""
    conn = get_db_connection()
    if vehicle_id:
        row = conn.execute("SELECT * FROM trip_vehicles WHERE trip_id = ? AND id = ?", (trip_id, vehicle_id)).fetchone()
    else:
        row = conn.execute("SELECT * FROM trip_vehicles WHERE trip_id = ? ORDER BY id ASC LIMIT 1", (trip_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def add_trip_vehicle(trip_id: int, vehicle_type: str, brand_model: str, fuel_type: str,
                     benchmark_mileage: float, initial_odometer: float) -> Dict[str, Any]:
    """Add a new vehicle to this trip."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO trip_vehicles (trip_id, vehicle_type, brand_model, fuel_type, benchmark_mileage, initial_odometer, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (trip_id, vehicle_type, brand_model, fuel_type, benchmark_mileage, initial_odometer, now))
    v_id = cursor.lastrowid
    conn.commit()

    row = cursor.execute("SELECT * FROM trip_vehicles WHERE id = ?", (v_id,)).fetchone()
    conn.close()
    return dict(row)


def update_trip_vehicle(trip_id: int, vehicle_id: int, vehicle_type: str, brand_model: str,
                        fuel_type: str, benchmark_mileage: float, initial_odometer: float) -> Optional[Dict[str, Any]]:
    """Update an existing vehicle's configuration."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE trip_vehicles
    SET vehicle_type = ?, brand_model = ?, fuel_type = ?, benchmark_mileage = ?, initial_odometer = ?
    WHERE id = ? AND trip_id = ?
    """, (vehicle_type, brand_model, fuel_type, benchmark_mileage, initial_odometer, vehicle_id, trip_id))
    conn.commit()
    row = cursor.execute("SELECT * FROM trip_vehicles WHERE id = ? AND trip_id = ?", (vehicle_id, trip_id)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def delete_trip_vehicle(trip_id: int, vehicle_id: int) -> bool:
    """Delete a vehicle from this trip."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trip_vehicles WHERE id = ? AND trip_id = ?", (vehicle_id, trip_id))
    conn.commit()
    conn.close()
    return True


def set_trip_vehicle(trip_id: int, vehicle_type: str, brand_model: str, fuel_type: str,
                     benchmark_mileage: float, initial_odometer: float) -> Dict[str, Any]:
    """Backward-compatible helper: Create or update first vehicle settings for a trip."""
    existing = get_trip_vehicle(trip_id)
    if existing:
        return update_trip_vehicle(trip_id, existing["id"], vehicle_type, brand_model, fuel_type, benchmark_mileage, initial_odometer)
    return add_trip_vehicle(trip_id, vehicle_type, brand_model, fuel_type, benchmark_mileage, initial_odometer)


def get_fuel_logs(trip_id: int, vehicle_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get all fuel logs for a trip with calculated segment distances and segment mileage per vehicle.
    """
    conn = get_db_connection()
    vehicles = {v["id"]: dict(v) for v in conn.execute("SELECT * FROM trip_vehicles WHERE trip_id = ?", (trip_id,)).fetchall()}

    query = """
    SELECT f.*, m.name as payer_name, m.avatar_color as payer_color,
           v.brand_model as vehicle_brand_model, v.vehicle_type as vehicle_kind, v.fuel_type as vehicle_fuel
    FROM fuel_logs f
    LEFT JOIN members m ON f.payer_id = m.id
    LEFT JOIN trip_vehicles v ON f.vehicle_id = v.id
    WHERE f.trip_id = ?
    """
    params = [trip_id]
    if vehicle_id:
        query += " AND f.vehicle_id = ?"
        params.append(vehicle_id)
    query += " ORDER BY f.odometer_reading ASC, f.date ASC, f.id ASC"

    logs = conn.execute(query, tuple(params)).fetchall()
    conn.close()

    # Track previous odometer per vehicle
    prev_odos: Dict[Optional[int], float] = {}
    for vid, v in vehicles.items():
        prev_odos[vid] = v.get("initial_odometer") or 0.0
    prev_odos[None] = 0.0

    results = []
    for log in logs:
        item = dict(log)
        vid = item.get("vehicle_id")
        v = vehicles.get(vid)

        fuel_type = (v["fuel_type"] if v else item.get("fuel_type")) or "Petrol"
        fuel_unit = "km/kg" if fuel_type == "CNG" else "km/L"

        odo = item["odometer_reading"]
        prev_odo = prev_odos.get(vid, 0.0)

        # Distance run since previous fill for this specific vehicle
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
        prev_odos[vid] = odo

    return results


def calculate_trip_mileage_summary(trip_id: int, vehicle_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Calculate comprehensive trip mileage for multi-vehicle fleets:
    - Overall fleet metrics (combined distance, total fuel cost)
    - Per-vehicle metrics array (individual mileage, benchmarks, and efficiency)
    - Backward-compatible top-level keys for UI elements
    """
    conn = get_db_connection()
    v_rows = conn.execute("SELECT * FROM trip_vehicles WHERE trip_id = ? ORDER BY id ASC", (trip_id,)).fetchall()
    logs_raw = conn.execute("""
    SELECT f.*, v.fuel_type as vehicle_fuel
    FROM fuel_logs f
    LEFT JOIN trip_vehicles v ON f.vehicle_id = v.id
    WHERE f.trip_id = ?
    ORDER BY f.odometer_reading ASC, f.date ASC, f.id ASC
    """, (trip_id,)).fetchall()
    members_count = conn.execute("SELECT COUNT(*) FROM members WHERE trip_id = ?", (trip_id,)).fetchone()[0] or 1
    conn.close()

    vehicles_list = [dict(r) for r in v_rows]
    logs = [dict(l) for l in logs_raw]

    # Map logs by vehicle
    vehicle_logs_map: Dict[Optional[int], List[Dict[str, Any]]] = {}
    for l in logs:
        vid = l.get("vehicle_id")
        vehicle_logs_map.setdefault(vid, []).append(l)

    # Calculate per-vehicle summaries
    vehicles_summaries = []
    total_fleet_distance = 0.0
    total_fleet_fuel_cost = sum(l["fuel_amount"] for l in logs)
    total_fleet_fuel_qty = sum(l["fuel_quantity"] for l in logs)

    for v in vehicles_list:
        vid = v["id"]
        v_logs = vehicle_logs_map.get(vid, [])
        initial_odo = v.get("initial_odometer") or 0.0
        benchmark = v.get("benchmark_mileage") or 20.0
        fuel_type = v.get("fuel_type") or "Petrol"
        is_cng = (fuel_type == "CNG")
        qty_unit = "kg" if is_cng else "L"
        m_unit = "km/kg" if is_cng else "km/L"

        if not v_logs:
            v_summary = {
                "vehicle": v,
                "total_distance_km": 0.0,
                "total_fuel_quantity": 0.0,
                "quantity_unit": qty_unit,
                "mileage_unit": m_unit,
                "total_fuel_cost": 0.0,
                "average_mileage": 0.0,
                "benchmark_mileage": benchmark,
                "efficiency_percentage": 0.0,
                "efficiency_label": "No fuel logs yet",
                "cost_per_km": 0.0,
                "fuel_logs_count": 0,
                "latest_odometer": initial_odo,
                "initial_odometer": initial_odo
            }
        else:
            v_fuel_qty = sum(l["fuel_quantity"] for l in v_logs)
            v_fuel_cost = sum(l["fuel_amount"] for l in v_logs)
            latest_odo = max(l["odometer_reading"] for l in v_logs)
            v_dist = max(0.0, latest_odo - initial_odo)
            if v_dist <= 0.0 and len(v_logs) > 0:
                v_dist = sum(l["distance_run"] for l in v_logs if l["distance_run"] > 0)

            total_fleet_distance += v_dist

            v_avg_mileage = round(v_dist / v_fuel_qty, 2) if v_fuel_qty > 0 and v_dist > 0 else 0.0
            v_cost_per_km = round(v_fuel_cost / v_dist, 2) if v_dist > 0 else 0.0

            if benchmark > 0 and v_avg_mileage > 0:
                eff_pct = round((v_avg_mileage / benchmark) * 100, 1)
                if eff_pct >= 95:
                    eff_lbl = "🌟 Outstanding (Near or exceeds ARAI benchmark)"
                elif eff_pct >= 85:
                    eff_lbl = "✅ High Highway Efficiency (Great performance)"
                elif eff_pct >= 70:
                    eff_lbl = "👍 Normal Real-World Driving (Mixed traffic)"
                else:
                    eff_lbl = "⚠️ Heavy Load / City Traffic / Hills"
            else:
                eff_pct = 0.0
                eff_lbl = "Log fuel & distance to see efficiency"

            v_summary = {
                "vehicle": v,
                "total_distance_km": round(v_dist, 1),
                "total_fuel_quantity": round(v_fuel_qty, 2),
                "quantity_unit": qty_unit,
                "mileage_unit": m_unit,
                "total_fuel_cost": round(v_fuel_cost, 2),
                "average_mileage": v_avg_mileage,
                "benchmark_mileage": round(benchmark, 2),
                "efficiency_percentage": eff_pct,
                "efficiency_label": eff_lbl,
                "cost_per_km": v_cost_per_km,
                "fuel_logs_count": len(v_logs),
                "latest_odometer": round(latest_odo, 1),
                "initial_odometer": round(initial_odo, 1)
            }
        vehicles_summaries.append(v_summary)

    # Primary vehicle (or selected vehicle)
    primary_summary = None
    if vehicle_id:
        for s in vehicles_summaries:
            if s["vehicle"]["id"] == vehicle_id:
                primary_summary = s
                break
    if not primary_summary and vehicles_summaries:
        primary_summary = vehicles_summaries[0]

    # Default fallback vehicle if trip has no vehicle configured yet
    if not primary_summary:
        default_v = {
            "id": None,
            "vehicle_type": "Car",
            "brand_model": "Maruti Suzuki Ertiga",
            "fuel_type": "CNG",
            "benchmark_mileage": 26.11,
            "initial_odometer": 0.0
        }
        primary_summary = {
            "vehicle": default_v,
            "total_distance_km": 0.0,
            "total_fuel_quantity": 0.0,
            "quantity_unit": "kg",
            "mileage_unit": "km/kg",
            "total_fuel_cost": 0.0,
            "average_mileage": 0.0,
            "benchmark_mileage": 26.11,
            "efficiency_percentage": 0.0,
            "efficiency_label": "No vehicle configured yet",
            "cost_per_km": 0.0,
            "fuel_logs_count": 0,
            "latest_odometer": 0.0,
            "initial_odometer": 0.0
        }

    fleet_cost_per_km = round(total_fleet_fuel_cost / total_fleet_distance, 2) if total_fleet_distance > 0 else 0.0
    cost_per_person_km = round(fleet_cost_per_km / members_count, 2) if members_count > 0 else fleet_cost_per_km

    # Combine fleet overview and top-level backward-compatible keys
    return {
        "vehicle": primary_summary["vehicle"],
        "vehicles": vehicles_summaries,
        "vehicles_count": len(vehicles_summaries),
        "total_distance_km": round(total_fleet_distance, 1),
        "total_fuel_quantity": round(total_fleet_fuel_qty, 2),
        "quantity_unit": primary_summary["quantity_unit"],
        "mileage_unit": primary_summary["mileage_unit"],
        "total_fuel_cost": round(total_fleet_fuel_cost, 2),
        "average_mileage": primary_summary["average_mileage"],
        "benchmark_mileage": primary_summary["benchmark_mileage"],
        "efficiency_percentage": primary_summary["efficiency_percentage"],
        "efficiency_label": primary_summary["efficiency_label"],
        "cost_per_km": fleet_cost_per_km if total_fleet_distance > 0 else primary_summary["cost_per_km"],
        "cost_per_person_km": cost_per_person_km,
        "fuel_logs_count": len(logs),
        "latest_odometer": primary_summary["latest_odometer"],
        "initial_odometer": primary_summary["initial_odometer"]
    }
