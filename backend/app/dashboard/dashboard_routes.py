"""
Dashboard & Monitoring API Routes
High-level KPIs, system health, and security alert feeds.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Query
from .dashboard_service import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=Dict[str, Any])
def get_stats():
    """
    Returns top-level KPIs:
    - total_devices: count of all registered bands
    - online_devices: count of currently communicating bands
    - offline_devices: bands currently dormant or sleeping
    - low_battery_devices: devices with battery <= 20%
    - active_alerts_count: unacknowledged security alerts
    - live_tcp_sockets: currently connected raw socket sessions
    """
    return dashboard_service.get_summary_stats()


@router.get("/overview", response_model=Dict[str, Any])
def get_dashboard_overview():
    """
    Returns complete dashboard overview:
    KPI stats, monitored devices summary, recent alerts, and map markers.
    """
    stats = dashboard_service.get_summary_stats()
    devices = dashboard_service.list_all_devices()
    alerts = dashboard_service.get_recent_alerts(limit=10)
    res = stats.copy()
    res.update({
        "stats": stats,
        "devices": devices,
        "recent_alerts": alerts,
        "alerts": alerts,
        "markers": [
            {
                "id": str(d.get("device_id")),
                "device_id": str(d.get("device_id")),
                "imei": str(d.get("device_id")),
                "name": d.get("wearer_name") or d.get("device_id"),
                "wearer_name": d.get("wearer_name") or d.get("device_id"),
                "lat": d.get("last_latitude"),
                "lng": d.get("last_longitude"),
                "latitude": d.get("last_latitude"),
                "longitude": d.get("last_longitude"),
                "battery": d.get("battery"),
                "battery_percent": d.get("battery"),
                "battery_level": d.get("battery"),
                "heading": float(d.get("heading") or d.get("bearing") or 0.0),
                "bearing": float(d.get("bearing") or d.get("heading") or 0.0),
                "course": float(d.get("course") or d.get("heading") or 0.0),
                "direction": float(d.get("direction") or d.get("heading") or 0.0),
                "direction_deg": float(d.get("direction_deg") or d.get("heading") or 0.0),
                "speed": float(d.get("speed") or d.get("speed_kmh") or 0.0),
                "speed_kmh": float(d.get("speed_kmh") or d.get("speed") or 0.0),
                "status": d.get("status", "ONLINE"),
                "online": bool(d.get("online", False)),
                "gps_valid": bool(d.get("gps_valid", False)),
                "gps_fix": bool(d.get("gps_fix", False)),
                "gps_locked": bool(d.get("gps_locked", False)),
                "gps_status": d.get("gps_status", "No Fix"),
                "last_seen": d.get("last_seen"),
                "last_valid_gps_time": d.get("last_valid_gps_time"),
            }
            for d in devices if d.get("last_latitude") is not None and d.get("last_longitude") is not None
        ]
    })
    return res


@router.get("/devices", response_model=List[Dict[str, Any]])
def get_dashboard_devices():
    """
    List all monitored custody watches with current telemetry and positions.
    """
    return dashboard_service.list_all_devices()


@router.get("/devices/{device_id}", response_model=Dict[str, Any])
def get_dashboard_device_detail(device_id: str):
    """
    Detailed status + recent coordinates for a specific watch.
    """
    return dashboard_service.get_device_detail(device_id)


@router.get("/alerts", response_model=List[Dict[str, Any]])
def get_alerts(limit: int = Query(50, ge=1, le=10000)):
    """
    Fetches real-time security alerts (SOS alarms, strap cut / band tamper, low battery warnings).
    """
    return dashboard_service.get_recent_alerts(limit=limit)
