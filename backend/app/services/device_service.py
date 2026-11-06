"""
Device Management Service
Maintains device statuses, battery life, step counts, pulse, and registration.
Strictly uses actual telemetry readings without hardcoded fallback values.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from ..utils.datetime_utils import current_iso_timestamp
from ..utils.logger import app_logger
from .firestore_service import firestore_service


class DeviceService:
    def register_device(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """Registers a custody band profile if not already present, preserving existing fields."""
        device_id = device_data["device_id"]
        existing = firestore_service.get_device(device_id)

        if existing:
            # Preserve existing device registration information and status
            merged = {**existing}
            for k, v in device_data.items():
                if v is not None and (k not in merged or merged[k] is None):
                    merged[k] = v
            firestore_service.save_device(merged)
            return firestore_service.get_device(device_id) or merged

        device_data.setdefault("status", "ACTIVE")
        device_data.setdefault("last_seen", current_iso_timestamp())

        firestore_service.save_device(device_data)
        return firestore_service.get_device(device_id) or device_data

    def update_heartbeat(
        self,
        device_id: str,
        battery: Optional[int],
        steps: Optional[int],
        is_charging: bool = False
    ):
        """Updates battery and steps from KA (Keepalive) / LK packets."""
        existing = firestore_service.get_device(device_id) or {}
        now_iso = current_iso_timestamp()

        # Preserve existing valid coordinates and GPS status
        last_lat = existing.get("last_latitude")
        last_lon = existing.get("last_longitude")
        last_gps_time = existing.get("last_valid_gps_time")
        gps_valid = bool(existing.get("gps_valid", False))

        # Check for location staleness
        gps_status = existing.get("gps_status", "No Fix")
        if gps_valid and last_gps_time:
            try:
                dt_fix = datetime.fromisoformat(last_gps_time.replace("Z", "+00:00"))
                now_dt = datetime.now(timezone.utc)
                if (now_dt - dt_fix).total_seconds() > 900:  # 15 minutes
                    gps_status = "Location Stale"
                    gps_valid = False
            except Exception:
                pass

        # Actual battery - preserve existing if current is None
        dev_battery = battery if battery is not None else existing.get("battery")
        dev_steps = steps if steps is not None else existing.get("steps")

        update_data: Dict[str, Any] = {
            "device_id": device_id,
            "last_seen": now_iso,
            "status": "ONLINE",
            "is_charging": is_charging,
            "charging": is_charging,
            "charge_status": "charging" if is_charging else "discharging",
            "gps_valid": gps_valid,
            "gps_fix": gps_valid,
            "gps_locked": gps_valid,
            "gps_status": gps_status,
        }

        if last_lat is not None and last_lon is not None:
            update_data["last_latitude"] = last_lat
            update_data["last_longitude"] = last_lon
            update_data["maps_url"] = f"https://maps.google.com/?q={last_lat:.6f},{last_lon:.6f}"
        if last_gps_time:
            update_data["last_valid_gps_time"] = last_gps_time

        if dev_battery is not None:
            update_data["battery"] = dev_battery
            update_data["battery_level"] = dev_battery
            update_data["battery_percent"] = dev_battery
            update_data["battery_status"] = "normal" if dev_battery > 20 else "low"

        if dev_steps is not None:
            update_data["steps"] = dev_steps

        firestore_service.save_device(update_data)
        batt_str = f"{dev_battery}%" if dev_battery is not None else "N/A"
        app_logger.info(f"[DEVICE STATUS] {device_id} Heartbeat: Battery={batt_str}, Steps={dev_steps}, Charging={is_charging}")

    def update_heart_rate(self, device_id: str, bpm: int):
        """Updates heart rate pulse record."""
        update_data = {
            "device_id": device_id,
            "last_seen": current_iso_timestamp(),
            "heart_rate": bpm,
            "status": "ONLINE"
        }
        firestore_service.save_device(update_data)
        app_logger.info(f"[HEALTH] {device_id} Heart Rate: {bpm} BPM")

    def update_position(
        self,
        device_id: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        battery: Optional[int] = None,
        steps: Optional[int] = None,
        speed: float = 0.0,
        bearing: float = 0.0,
        is_charging: Optional[bool] = None,
        gps_valid: bool = False,
        satellites: int = 0,
        gsm_signal: int = 0,
        timestamp: Optional[str] = None
    ):
        """
        Updates device live position and telemetry.
        CRITICAL: If gps_valid is False (status 'V'), preserves previous valid coordinates
        while updating GPS status to 'No Fix' or 'Location Stale'.
        """
        existing = firestore_service.get_device(device_id) or {}
        now_iso = timestamp or current_iso_timestamp()

        # Resolve GPS coordinates & status
        if gps_valid and lat is not None and lon is not None:
            # Valid 3D satellite fix
            last_lat = lat
            last_lon = lon
            last_gps_time = now_iso
            gps_status = "GPS Locked"
            is_fix = True
        else:
            # Invalid fix (status 'V' or no coords) - PRESERVE PREVIOUS VALID COORDINATES
            last_lat = existing.get("last_latitude")
            last_lon = existing.get("last_longitude")
            last_gps_time = existing.get("last_valid_gps_time")
            is_fix = False

            # Determine whether location is stale (> 15 minutes old) or simply No Fix
            if last_gps_time:
                try:
                    dt_fix = datetime.fromisoformat(last_gps_time.replace("Z", "+00:00"))
                    now_dt = datetime.now(timezone.utc)
                    if (now_dt - dt_fix).total_seconds() > 900:  # 15 minutes
                        gps_status = "Location Stale"
                    else:
                        gps_status = "No Fix"
                except Exception:
                    gps_status = "No Fix"
            else:
                gps_status = "No Fix"

        # Resolve battery: actual reading if given, else preserve existing; NEVER default to 90
        dev_battery = battery if battery is not None else existing.get("battery")
        dev_steps = steps if steps is not None else existing.get("steps")
        dev_chg = is_charging if is_charging is not None else bool(existing.get("is_charging") or existing.get("charging"))

        # Travel angle
        heading_val = float(bearing or 0.0)
        speed_val = float(speed or 0.0)

        update_data: Dict[str, Any] = {
            "device_id": device_id,
            "last_seen": now_iso,
            "status": "ONLINE",
            "gps_valid": is_fix,
            "gps_fix": is_fix,
            "gps_locked": is_fix,
            "gps_status": gps_status,
            "speed": speed_val,
            "speed_kmh": speed_val,
            "heading": heading_val,
            "bearing": heading_val,
            "course": heading_val,
            "direction": heading_val,
            "direction_deg": heading_val,
            "angle": heading_val,
            "rotation": heading_val,
            "satellites": satellites,
            "gsm_signal": gsm_signal,
            "is_charging": dev_chg,
            "charging": dev_chg,
            "charge_status": "charging" if dev_chg else "discharging",
        }

        # Save coordinates (new fix or preserved previous fix)
        if last_lat is not None and last_lon is not None:
            update_data["last_latitude"] = last_lat
            update_data["last_longitude"] = last_lon
            update_data["maps_url"] = f"https://maps.google.com/?q={last_lat:.6f},{last_lon:.6f}"
        if last_gps_time:
            update_data["last_valid_gps_time"] = last_gps_time

        if dev_battery is not None:
            update_data["battery"] = dev_battery
            update_data["battery_level"] = dev_battery
            update_data["battery_percent"] = dev_battery
            update_data["battery_status"] = "normal" if dev_battery > 20 else "low"

        if dev_steps is not None:
            update_data["steps"] = dev_steps

        firestore_service.save_device(update_data)

    def get_all_devices(self) -> List[Dict[str, Any]]:
        return firestore_service.get_devices()

    def get_device_by_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        return firestore_service.get_device(device_id)


device_service = DeviceService()
