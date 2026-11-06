"""
Real-Time Monitoring Service
Provides streaming feeds and control-room telemetry matrices for all monitored wearers.
"""

from typing import List, Dict, Any
from ..services.device_service import device_service
from ..services.firestore_service import firestore_service
from ..services.alert_service import alert_service
from ..receiver.tcp_server import get_active_clients_count
from datetime import datetime, timezone


class MonitoringService:
    def get_live_grid(self) -> List[Dict[str, Any]]:
        """
        Returns full monitoring card data for all wearers in the jurisdiction:
        Battery, pulse, steps, last seen, GPS validity, Google Maps link, and alert flags.
        """
        devices = device_service.get_all_devices()
        alerts = alert_service.get_recent_alerts(limit=100)

        alert_device_ids = {a["device_id"] for a in alerts if a.get("status") == "NEW"}

        grid = []
        for d in devices:
            dev_id = d["device_id"]
            battery = d.get("battery", 100)
            heart_rate = d.get("heart_rate")

            # Status classification
            is_in_alert = dev_id in alert_device_ids
            status_label = "ALARM" if is_in_alert else d.get("status", "ACTIVE")

            grid.append({
                "device_id": dev_id,
                "wearer_name": d.get("wearer_name", "Unassigned"),
                "case_number": d.get("case_number", "N/A"),
                "status": status_label,
                "has_active_alarm": is_in_alert,
                "battery": battery,
                "is_low_battery": battery <= 20,
                "heart_rate": heart_rate,
                "steps": d.get("steps", 0),
                "latitude": d.get("last_latitude"),
                "longitude": d.get("last_longitude"),
                "maps_url": d.get("maps_url"),
                "last_seen": d.get("last_seen"),
            })
        return grid

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Aggregate summary for dispatch wall displays."""
        grid = self.get_live_grid()
        total = len(grid)
        online = sum(1 for g in grid if g["status"] in ("ONLINE", "ACTIVE"))
        in_alarm = sum(1 for g in grid if g["has_active_alarm"])
        low_battery = sum(1 for g in grid if g["is_low_battery"])

        return {
            "total_monitored": total,
            "online_count": online,
            "offline_count": max(0, total - online),
            "critical_alarms": in_alarm,
            "low_battery_warnings": low_battery,
            "active_sockets": get_active_clients_count()
        }


monitoring_service = MonitoringService()

