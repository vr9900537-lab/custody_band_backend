"""
GPS & Location Tracking API Routes
Endpoints for live map tracking, historical GPS breadcrumbs, polling, and geofence checking.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Query, Request
from pydantic import BaseModel, Field
from ..services.gps_service import gps_service
from ..services.firestore_service import firestore_service
from ..services.device_service import device_service
from ..services.alert_service import alert_service
from ..utils.datetime_utils import current_iso_timestamp
from ..receiver.tcp_server import send_command_to_device
from ..config import settings

router = APIRouter(prefix="/gps", tags=["GPS & Locations"])


@router.post("/ingest", response_model=Dict[str, Any])
@router.post("/ingest/", response_model=Dict[str, Any], include_in_schema=False)
@router.put("/ingest", response_model=Dict[str, Any], include_in_schema=False)
async def ingest_gps_telemetry(request: Request):
    """
    Ingest live GPS telemetry and location fixes from watches, mobile apps, or simulator scripts.
    Accepts single JSON object or array of objects.
    Supported fields:
      - device_id / imei / id
      - latitude / lat
      - longitude / lng / lon
      - altitude / alt
      - speed / speed_kmh
      - battery / battery_level
      - steps / step_count
      - heart_rate / bpm / pulse
      - timestamp / time
      - status / gps_valid
    """
    try:
        payload = await request.json()
    except Exception:
        try:
            form_data = await request.form()
            payload = dict(form_data) if form_data else dict(request.query_params)
        except Exception:
            payload = dict(request.query_params)

    items = payload if isinstance(payload, list) else [payload]
    results = []

    for item in items:
        if not isinstance(item, dict):
            continue

        dev_id = str(
            item.get("device_id")
            or item.get("imei")
            or item.get("id")
            or item.get("device")
            or settings.DEFAULT_WATCH_IMEI
        ).strip()

        # Extract latitude
        lat_val = item.get("latitude") if item.get("latitude") is not None else item.get("lat")
        # Extract longitude
        lon_val = (
            item.get("longitude")
            if item.get("longitude") is not None
            else (item.get("lng") if item.get("lng") is not None else item.get("lon"))
        )

        try:
            lat = float(lat_val) if lat_val is not None and str(lat_val).strip() != "" else None
        except (ValueError, TypeError):
            lat = None

        try:
            lon = float(lon_val) if lon_val is not None and str(lon_val).strip() != "" else None
        except (ValueError, TypeError):
            lon = None

        try:
            speed = float(item.get("speed_kmh") if item.get("speed_kmh") is not None else (item.get("speed") or 0.0))
        except (ValueError, TypeError):
            speed = 0.0

        # Battery parsing - NEVER default to 90 or 100
        battery_raw = item.get("battery") if item.get("battery") is not None else (item.get("battery_pct") or item.get("battery_level"))
        try:
            battery = int(float(battery_raw)) if battery_raw is not None and str(battery_raw).strip() != "" else None
        except (ValueError, TypeError):
            battery = None

        steps_raw = item.get("steps") if item.get("steps") is not None else item.get("step_count")
        try:
            steps = int(float(steps_raw)) if steps_raw is not None and str(steps_raw).strip() != "" else None
        except (ValueError, TypeError):
            steps = None

        ts = item.get("timestamp") or item.get("time") or current_iso_timestamp()

        # GPS validity: check status flag ('A' vs 'V') and coordinate bounds
        status_flag = str(item.get("status") or item.get("gps_status") or "A").strip().upper()
        is_coord_valid = (
            lat is not None and lon is not None
            and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
            and not (lat == 0.0 and lon == 0.0)
        )
        has_coords = (status_flag != "V") and bool(item.get("gps_valid", True)) and is_coord_valid
        gps_status = "GPS Locked" if has_coords else "No Fix"

        # Extract course / heading / bearing
        bearing_raw = (
            item.get("heading")
            if item.get("heading") is not None
            else (item.get("bearing") if item.get("bearing") is not None else (item.get("course") if item.get("course") is not None else item.get("direction")))
        )
        try:
            bearing = float(bearing_raw) if bearing_raw is not None else 0.0
        except (ValueError, TypeError):
            bearing = 0.0

        is_charging = bool(item.get("is_charging") or item.get("charging") or False)

        record: Dict[str, Any] = {
            "device_id": dev_id,
            "maker": item.get("maker", "MNYD"),
            "command": item.get("command", "UD"),
            "timestamp": ts,
            "gps_valid": has_coords,
            "gps_fix": has_coords,
            "gps_locked": has_coords,
            "gps_status": gps_status,
            "latitude": round(lat, 6) if has_coords else None,
            "longitude": round(lon, 6) if has_coords else None,
            "speed_kmh": speed,
            "speed": speed,
            "heading": bearing,
            "bearing": bearing,
            "course": bearing,
            "direction": bearing,
            "direction_deg": bearing,
            "is_charging": is_charging,
            "charging": is_charging,
            "charge_status": "charging" if is_charging else "discharging",
        }
        if battery is not None:
            record["battery"] = battery
            record["battery_percent"] = battery
        if steps is not None:
            record["steps"] = steps

        # Save to SQLite telemetry table and Firestore (computes dynamic bearing if None)
        gps_service.process_location_record(record)

        # Update device live location & heartbeat
        device_service.update_position(
            device_id=dev_id,
            lat=record.get("latitude"),
            lon=record.get("longitude"),
            battery=battery,
            steps=steps,
            speed=speed,
            bearing=bearing,
            is_charging=is_charging,
            gps_valid=has_coords,
            timestamp=ts
        )

        # Biometric heart rate if present
        hr_val = item.get("heart_rate") or item.get("bpm") or item.get("pulse")
        if hr_val is not None:
            try:
                bpm = int(float(hr_val))
                device_service.update_heart_rate(dev_id, bpm)
                from ..health_data.health_service import HealthService
                HealthService().record_heart_rate(dev_id, bpm)
            except Exception:
                pass

        # Check battery alert
        alert_service.check_battery_alert(dev_id, battery)

        results.append(record)

    return {
        "success": True,
        "message": f"Successfully ingested {len(results)} GPS telemetry record(s)",
        "count": len(results),
        "data": results[0] if len(results) == 1 else results,
        "records": results
    }


@router.get("/ingest", response_model=Dict[str, Any])
@router.get("/ingest/", response_model=Dict[str, Any], include_in_schema=False)
def ingest_gps_info():
    """Information and health check for the GPS ingest endpoint."""
    return {
        "status": "ready",
        "endpoint": "/api/v1/gps/ingest",
        "methods": ["POST", "PUT"],
        "description": "Post GPS telemetry records with device_id, latitude, longitude, battery, steps",
        "example": {
            "device_id": "863758061830955",
            "latitude": 17.446317,
            "longitude": 78.368395,
            "speed_kmh": 0.0,
            "battery": 94,
            "steps": 1420
        }
    }


class GeofenceCheckRequest(BaseModel):
    latitude: float = Field(..., description="Target point latitude")
    longitude: float = Field(..., description="Target point longitude")
    center_latitude: float = Field(..., description="Geofence center point latitude")
    center_longitude: float = Field(..., description="Geofence center point longitude")
    radius_meters: float = Field(..., description="Allowed zone radius in meters")


@router.get("/live", response_model=List[Dict[str, Any]])
def get_live_locations():
    """
    Get the latest GPS coordinates of all monitored custody bands.
    Includes heading/bearing angle and speed to drive directional map travel arrows.
    """
    devices = device_service.get_all_devices()
    live_points = []
    for d in devices:
        lat = d.get("last_latitude") or d.get("latitude")
        lon = d.get("last_longitude") or d.get("longitude")
        if lat is not None and lon is not None:
            dev_id = str(d.get("device_id") or d.get("imei") or "")
            name = d.get("wearer_name") or d.get("name") or "Wearer"
            bearing_val = d.get("heading") or d.get("bearing") or d.get("course") or d.get("direction") or 0.0
            speed_val = d.get("speed") or d.get("speed_kmh") or 0.0
            batt_val = d.get("battery")
            is_chg = bool(d.get("is_charging") or d.get("charging") or False)
            point = {
                "id": dev_id,
                "device_id": dev_id,
                "imei": dev_id,
                "wearer_name": name,
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "lat": lat,
                "lng": lon,
                "lon": lon,
                "bearing": bearing_val,
                "heading": bearing_val,
                "course": bearing_val,
                "direction": bearing_val,
                "angle": bearing_val,
                "rotation": bearing_val,
                "speed": speed_val,
                "speed_kmh": speed_val,
                "is_charging": is_chg,
                "charging": is_chg,
                "isCharging": is_chg,
                "charge_status": "charging" if is_chg else "discharging",
                "status": d.get("status", "ONLINE"),
                "online": bool(d.get("online", False)),
                "gps_status": d.get("gps_status", "No Fix"),
                "gps_valid": bool(d.get("gps_valid", False)),
                "gps_fix": bool(d.get("gps_fix", False)),
                "gps_locked": bool(d.get("gps_locked", False)),
                "last_seen": d.get("last_seen"),
                "last_valid_gps_time": d.get("last_valid_gps_time"),
                "maps_url": d.get("maps_url") or f"https://maps.google.com/?q={lat},{lon}"
            }
            if batt_val is not None:
                point["battery"] = batt_val
                point["battery_level"] = batt_val
                point["batteryLevel"] = batt_val
                point["battery_pct"] = batt_val
                point["battery_percentage"] = batt_val
                point["charge"] = batt_val
                point["battery_status"] = "normal" if batt_val > 20 else "low"
            live_points.append(point)
    return live_points


@router.get("/{device_id}/latest", response_model=Dict[str, Any])
def get_latest_location(device_id: str):
    """
    Get the most recent GPS location fix and telemetry for a specific band.
    """
    dev = device_service.get_device_by_id(device_id)
    if not dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )

    history = firestore_service.get_telemetry_history(device_id, limit=1)
    latest_telemetry = history[0] if history else {}
    bearing_val = dev.get("heading") or dev.get("bearing") or dev.get("course") or latest_telemetry.get("heading") or 0.0
    speed_val = latest_telemetry.get("speed_kmh") or dev.get("speed") or 0.0
    batt_val = dev.get("battery")
    is_chg = bool(dev.get("is_charging") or dev.get("charging") or False)

    res = {
        "device_id": device_id,
        "wearer_name": dev.get("wearer_name"),
        "latitude": dev.get("last_latitude"),
        "longitude": dev.get("last_longitude"),
        "lat": dev.get("last_latitude"),
        "lng": dev.get("last_longitude"),
        "lon": dev.get("last_longitude"),
        "bearing": bearing_val,
        "heading": bearing_val,
        "course": bearing_val,
        "direction": bearing_val,
        "angle": bearing_val,
        "rotation": bearing_val,
        "speed": speed_val,
        "speed_kmh": speed_val,
        "is_charging": is_chg,
        "charging": is_chg,
        "isCharging": is_chg,
        "charge_status": "charging" if is_chg else "discharging",
        "status": dev.get("status", "ONLINE"),
        "online": bool(dev.get("online", False)),
        "gps_status": dev.get("gps_status", "No Fix"),
        "gps_valid": bool(dev.get("gps_valid", False)),
        "gps_fix": bool(dev.get("gps_fix", False)),
        "gps_locked": bool(dev.get("gps_locked", False)),
        "last_seen": dev.get("last_seen"),
        "last_valid_gps_time": dev.get("last_valid_gps_time"),
        "steps": dev.get("steps"),
        "heart_rate": dev.get("heart_rate"),
        "maps_url": dev.get("maps_url")
    }
    if batt_val is not None:
        res["battery"] = batt_val
        res["battery_level"] = batt_val
        res["batteryLevel"] = batt_val
        res["battery_pct"] = batt_val
        res["battery_percentage"] = batt_val
        res["charge"] = batt_val
        res["battery_status"] = "normal" if batt_val > 20 else "low"
    return res


@router.get("/{device_id}/history", response_model=List[Dict[str, Any]])
def get_location_history(
    device_id: str,
    limit: int = Query(50, ge=1, le=500, description="Number of coordinates to return")
):
    """
    Retrieve historical GPS breadcrumbs and telemetry trail for route replay on a map.
    """
    existing = device_service.get_device_by_id(device_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )
    return firestore_service.get_telemetry_history(device_id, limit=limit)


@router.post("/{device_id}/poll", response_model=Dict[str, Any])
def poll_live_gps(device_id: str):
    """
    Transmit an immediate 'CR' command to force the watch to power on its GPS chip and return a live fix.
    """
    success = send_command_to_device(device_id, "CR")
    return {
        "device_id": device_id,
        "command": "CR",
        "polled": success,
        "message": "GPS request sent to watch" if success else "Watch is offline or in sleep mode"
    }


@router.post("/geofence/check", response_model=Dict[str, Any])
def check_geofence(geo_in: GeofenceCheckRequest):
    """
    Check whether a coordinate is within a specified geofence boundary circle.
    """
    dist = gps_service.calculate_distance_meters(
        geo_in.latitude,
        geo_in.longitude,
        geo_in.center_latitude,
        geo_in.center_longitude
    )
    inside = dist <= geo_in.radius_meters
    return {
        "is_inside": inside,
        "distance_from_center_meters": round(dist, 2),
        "allowed_radius_meters": geo_in.radius_meters,
        "status": "SAFE" if inside else "BREACHED"
    }

