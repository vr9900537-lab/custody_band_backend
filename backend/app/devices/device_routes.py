"""
Devices API Routes
Endpoints for managing custody bands, wearer assignments, and device commands.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Request
from ..schemas.device_schema import DeviceCreate, DeviceUpdate, DeviceCommandRequest
from ..services.device_service import device_service
from ..services.firestore_service import firestore_service
from ..receiver.tcp_server import send_command_to_device
from ..utils.datetime_utils import current_iso_timestamp
from ..config import settings

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("/ingest", response_model=Dict[str, Any])
@router.post("/ingest/", response_model=Dict[str, Any], include_in_schema=False)
@router.put("/ingest", response_model=Dict[str, Any], include_in_schema=False)
async def ingest_device(request: Request):
    """
    Ingest or synchronize device status, telemetry, wearer profile, and biometrics.
    Supports single JSON object or array of objects.
    Compatible with:
      - device_id, imei, id
      - wearer_name, name, wearer
      - case_number, case_no, case
      - battery, battery_pct, battery_level
      - steps, step_count
      - heart_rate, bpm, pulse
      - status (ONLINE / ACTIVE / OFFLINE)
      - latitude / lat, longitude / lon / lng
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

        # Build registration/update dictionary
        dev_dict = {
            "device_id": dev_id,
            "maker": item.get("maker") or item.get("model") or "Huaten C05",
            "wearer_name": item.get("wearer_name") or item.get("name") or "Custody Subject",
            "case_number": item.get("case_number") or item.get("case_no") or "CASE-2026-001",
            "status": str(item.get("status") or "ONLINE").upper()
        }

        # Battery & steps
        if "battery" in item or "battery_pct" in item or "battery_level" in item:
            try:
                b = item.get("battery") if item.get("battery") is not None else (item.get("battery_pct") or item.get("battery_level"))
                dev_dict["battery"] = int(float(b))
            except Exception:
                pass

        if "steps" in item or "step_count" in item:
            try:
                s = item.get("steps") if item.get("steps") is not None else item.get("step_count")
                dev_dict["steps"] = int(float(s))
            except Exception:
                pass

        # Coordinates
        lat_val = item.get("latitude") if item.get("latitude") is not None else item.get("lat")
        lon_val = (
            item.get("longitude")
            if item.get("longitude") is not None
            else (item.get("lng") if item.get("lng") is not None else item.get("lon"))
        )
        if lat_val is not None and lon_val is not None:
            try:
                lat = float(lat_val)
                lon = float(lon_val)
                dev_dict["last_latitude"] = lat
                dev_dict["last_longitude"] = lon
                dev_dict["maps_url"] = f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"

                # Save telemetry breadcrumb
                firestore_service.save_telemetry({
                    "device_id": dev_id,
                    "maker": dev_dict.get("maker", "MNYD"),
                    "command": "UD",
                    "timestamp": item.get("timestamp") or current_iso_timestamp(),
                    "gps_valid": True,
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "speed_kmh": float(item.get("speed") or item.get("speed_kmh") or 0.0),
                    "battery": dev_dict.get("battery", 100),
                    "steps": dev_dict.get("steps", 0),
                    "maps_url": dev_dict["maps_url"]
                })
            except Exception:
                pass

        # Pulse / Heart rate
        hr_val = item.get("heart_rate") or item.get("bpm") or item.get("pulse")
        if hr_val is not None:
            try:
                bpm = int(float(hr_val))
                dev_dict["heart_rate"] = bpm
                from ..health_data.health_service import HealthService
                HealthService().record_heart_rate(dev_id, bpm)
            except Exception:
                pass

        saved = device_service.register_device(dev_dict)
        results.append(saved)

    return {
        "success": True,
        "message": f"Successfully ingested {len(results)} device(s)",
        "count": len(results),
        "device": results[0] if len(results) == 1 else None,
        "devices": results
    }


@router.get("/ingest", response_model=Dict[str, Any])
@router.get("/ingest/", response_model=Dict[str, Any], include_in_schema=False)
def ingest_device_info():
    """Information and health check for the Device ingest endpoint."""
    return {
        "status": "ready",
        "endpoint": "/api/v1/devices/ingest",
        "methods": ["POST", "PUT"],
        "description": "Ingest device profiles and status updates",
        "example": {
            "device_id": "863758061830955",
            "wearer_name": "Demo Wearer",
            "case_number": "CASE-2026-001",
            "status": "ONLINE",
            "battery": 94,
            "steps": 1420
        }
    }


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]], include_in_schema=False)
def list_devices(
    skip: int = 0,
    limit: int = 500,
    search: Optional[str] = None,
    status: Optional[str] = None
):
    """
    List all registered custody bands.
    Supports pagination with skip and limit.
    """
    devices = device_service.get_all_devices()
    if search:
        s = search.lower()
        devices = [d for d in devices if s in str(d.get("device_id", "")).lower() or s in str(d.get("wearer_name", "")).lower()]
    if status:
        st = status.upper()
        devices = [d for d in devices if str(d.get("status", "")).upper() == st]
    return devices[skip : skip + limit]


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def register_device(device_in: DeviceCreate):
    """
    Register a new custody watch / tracking band to the system.
    """
    return device_service.register_device(device_in.model_dump())


@router.get("/{device_id}", response_model=Dict[str, Any])
def get_device(device_id: str):
    """
    Retrieve full profile and real-time status for a specific watch IMEI.
    """
    dev = device_service.get_device_by_id(device_id)
    if not dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )
    return dev


@router.put("/{device_id}", response_model=Dict[str, Any])
def update_device(device_id: str, update_in: DeviceUpdate):
    """
    Update wearer assignment, case number, or active status for a custody band.
    """
    existing = device_service.get_device_by_id(device_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )

    update_dict = {k: v for k, v in update_in.model_dump().items() if v is not None}
    update_dict["device_id"] = device_id
    firestore_service.save_device(update_dict)
    return device_service.get_device_by_id(device_id)


@router.post("/{device_id}/command", response_model=Dict[str, Any])
def send_command(device_id: str, cmd_req: DeviceCommandRequest):
    """
    Send an immediate protocol command to the connected custody watch.
    Common commands:
    - `CR`: Request immediate live GPS coordinate fix
    - `RESET`: Reboot watch firmware
    """
    success = send_command_to_device(device_id, cmd_req.command)
    return {
        "device_id": device_id,
        "command": cmd_req.command,
        "dispatched": success,
        "message": "Command transmitted to watch" if success else "Watch is offline or in low-power sleep mode"
    }

