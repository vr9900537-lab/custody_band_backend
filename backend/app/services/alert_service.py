"""
Alert & Anomaly Service
Handles security breaches, SOS triggers, strap removal / tamper alerts, and battery warnings.
"""

from typing import Dict, Any, Optional, List
from ..utils.datetime_utils import current_iso_timestamp
from ..utils.logger import app_logger
from .firestore_service import firestore_service


class AlertService:
    ALERT_TYPES = {
        "SOS": "Emergency SOS triggered by wearer",
        "STRAP_CUT": "Band tampering or strap removal detected!",
        "LOW_BATTERY": "Device battery critically low (< 15%)",
        "GEOFENCE_BREACH": "Wearer breached designated boundary perimeter",
        "DEVICE_OFFLINE": "Watch has not sent keepalive within threshold window"
    }

    def trigger_alert(
        self,
        device_id: str,
        alert_type: str,
        message: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Dict[str, Any]:
        """Creates and stores a security or hardware alert."""
        msg = message or self.ALERT_TYPES.get(alert_type, f"Alert event: {alert_type}")
        timestamp = current_iso_timestamp()

        alert_data = {
            "device_id": device_id,
            "timestamp": timestamp,
            "alert_type": alert_type,
            "message": msg,
            "latitude": latitude,
            "longitude": longitude,
            "status": "NEW"
        }

        firestore_service.save_alert(alert_data)
        app_logger.warning(f"[SECURITY ALERT] [{alert_type}] Device {device_id}: {msg}")
        return alert_data

    def check_battery_alert(self, device_id: str, battery: int):
        """Triggers low battery warning if under 15%."""
        if 0 < battery <= 15:
            self.trigger_alert(
                device_id=device_id,
                alert_type="LOW_BATTERY",
                message=f"Battery critically low at {battery}%. Please recharge immediately."
            )

    def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return firestore_service.get_recent_alerts(limit=limit)


alert_service = AlertService()

