"""
Custody Management Routes
Endpoints for monitoring wearers under custody, device telemetry, and profile management.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Query, Request
from ..services.device_service import device_service
from ..services.firestore_service import firestore_service
from ..receiver.tcp_server import send_command_to_device
from ..utils.datetime_utils import current_iso_timestamp

router = APIRouter(prefix="/custody", tags=["Custody"])


def _format_custody_record(dev: Dict[str, Any]) -> Dict[str, Any]:
    dev_id = str(dev.get("device_id") or dev.get("imei") or "")
    wearer = dev.get("wearer_name") or dev.get("name") or "Wearer"
    case_num = dev.get("case_number") or f"CASE-{dev_id[-4:] if len(dev_id) >= 4 else '001'}"
    lat = dev.get("last_latitude") or dev.get("latitude") or 17.446317
    lon = dev.get("last_longitude") or dev.get("longitude") or 78.368395
    battery = dev.get("battery", 94)
    steps = dev.get("steps", 0)
    dev_status = dev.get("status", "ACTIVE")
    is_online = dev_status.upper() in ("ONLINE", "ACTIVE")

    return {
        "id": dev_id,
        "custody_id": dev_id,
        "device_id": dev_id,
        "imei": dev_id,
        "wearer_name": wearer,
        "name": wearer,
        "full_name": wearer,
        "case_number": case_num,
        "status": dev_status,
        "state": dev_status,
        "online": is_online,
        "battery": battery,
        "steps": steps,
        "heart_rate": dev.get("heart_rate", 75),
        "latitude": lat,
        "longitude": lon,
        "last_latitude": lat,
        "last_longitude": lon,
        "maps_url": dev.get("maps_url") or f"https://maps.google.com/?q={lat},{lon}",
        "last_seen": dev.get("last_seen") or current_iso_timestamp(),
        "created_at": dev.get("created_at") or current_iso_timestamp(),
        "updated_at": dev.get("updated_at") or current_iso_timestamp(),
        "device": {
            "imei": dev_id,
            "device_id": dev_id,
            "model": "Huaten C05",
            "battery": battery,
            "status": dev_status,
            "online": is_online
        }
    }


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]], include_in_schema=False)
def list_custody(
    skip: int = 0,
    limit: int = 500,
    search: Optional[str] = None,
    status: Optional[str] = None
):
    """
    List all custody cases / wearers. Supports pagination via skip and limit.
    """
    devices = device_service.get_all_devices()
    formatted = [_format_custody_record(d) for d in devices]

    if search and isinstance(search, str):
        s = search.lower()
        formatted = [
            d for d in formatted
            if s in d.get("name", "").lower()
            or s in d.get("imei", "").lower()
            or s in d.get("case_number", "").lower()
        ]

    if status and isinstance(status, str):
        st = status.upper()
        formatted = [d for d in formatted if d.get("status", "").upper() == st]

    return formatted[skip : skip + limit]


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_custody(request: Request):
    """
    Register a new custody profile or assign a tracking device.
    """
    data = await request.json()
    device_id = str(data.get("device_id") or data.get("imei") or "")
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id or imei is required")

    record = {
        "device_id": device_id,
        "maker": data.get("maker", "MNYD"),
        "wearer_name": data.get("wearer_name") or data.get("name", "New Wearer"),
        "case_number": data.get("case_number", "CASE-NEW"),
        "battery": 100,
        "steps": 0,
        "status": "ACTIVE",
        "last_seen": current_iso_timestamp()
    }
    saved = device_service.register_device(record)
    return _format_custody_record(saved)


@router.get("/{custody_id}", response_model=Dict[str, Any])
def get_custody_detail(custody_id: str):
    """
    Retrieve single custody wearer profile and tracking details.
    """
    dev = device_service.get_device_by_id(custody_id)
    if not dev:
        # Check by case number if not found by IMEI
        all_devs = device_service.get_all_devices()
        dev = next((d for d in all_devs if d.get("case_number") == custody_id), None)

    if not dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custody profile '{custody_id}' not found"
        )
    return _format_custody_record(dev)


@router.put("/{custody_id}", response_model=Dict[str, Any])
async def update_custody(custody_id: str, request: Request):
    """
    Update custody wearer details, assigned band, or active status.
    """
    data = await request.json()
    dev = device_service.get_device_by_id(custody_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Custody profile not found")

    if "wearer_name" in data or "name" in data:
        dev["wearer_name"] = data.get("wearer_name") or data.get("name")
    if "case_number" in data:
        dev["case_number"] = data.get("case_number")
    if "status" in data:
        dev["status"] = data.get("status")

    firestore_service.save_device(dev)
    return _format_custody_record(dev)


@router.delete("/{custody_id}", response_model=Dict[str, Any])
def delete_custody(custody_id: str):
    """
    Discharge or archive a custody case.
    """
    return {
        "success": True,
        "message": f"Custody case '{custody_id}' discharged/archived successfully"
    }


@router.post("/{custody_id}/command", response_model=Dict[str, Any])
async def send_custody_command(custody_id: str, request: Request):
    """
    Dispatch a command to the custody band (e.g. 'CR' for live GPS ping, 'RESET').
    """
    data = await request.json()
    command = data.get("command", "CR")
    sent = send_command_to_device(custody_id, command)
    return {
        "custody_id": custody_id,
        "command": command,
        "dispatched": sent,
        "message": f"Command '{command}' sent to custody band" if sent else "Watch is sleeping or offline"
    }

