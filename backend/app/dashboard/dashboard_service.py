"""
Dashboard Service
Aggregates monitoring analytics, active custody devices, real-time map positions, and alert queues.
"""

from typing import Dict, Any, List
from ..services.device_service import device_service
from ..services.firestore_service import firestore_service
from ..services.alert_service import alert_service
from ..receiver.tcp_server import get_active_clients_count, send_command_to_device


class DashboardService:
    def get_summary_stats(self) -> Dict[str, Any]:
        """Calculates dashboard summary metrics."""
        devices = device_service.get_all_devices()
        alerts = alert_service.get_recent_alerts(limit=50)

        total_devices = len(devices)
        online_devices = sum(1 for d in devices if d.get("online") or d.get("status") == "ONLINE")
        low_battery_devices = sum(1 for d in devices if d.get("battery") is not None and d.get("battery") <= 20)
        active_alerts = len([a for a in alerts if a.get("status") == "NEW"])
        live_tcp_connections = get_active_clients_count()

        total_alerts_count = len(alerts)
        online_pct = round((online_devices / total_devices * 100)) if total_devices > 0 else 0
        offline_count = max(0, total_devices - online_devices)
        offline_pct = round((offline_count / total_devices * 100)) if total_devices > 0 else 0

        return {
            "total_devices": total_devices,
            "device_count": total_devices,
            "totalDevices": total_devices,
            "deviceCount": total_devices,
            "total_device_count": total_devices,
            "totalDeviceCount": total_devices,
            "registered_devices": total_devices,
            "registeredDevices": total_devices,
            "registered_hardware": total_devices,
            "registeredHardware": total_devices,
            "active_in_fleet": online_devices,
            "activeInFleet": online_devices,

            "online_devices": online_devices,
            "online": online_devices,
            "onlineDevices": online_devices,
            "onlineCount": online_devices,
            "currently_online": online_devices,
            "transmitting_telemetry": online_devices,
            "transmittingTelemetry": online_devices,
            "online_percent": online_pct,
            "onlinePercent": online_pct,

            "offline_devices": offline_count,
            "offline": offline_count,
            "offlineDevices": offline_count,
            "standby": offline_count,
            "sleep_mode": offline_count,
            "offline_percent": offline_pct,
            "offlinePercent": offline_pct,

            "low_battery_devices": low_battery_devices,
            "lowBatteryDevices": low_battery_devices,
            "low_battery": low_battery_devices,

            "active_alerts_count": active_alerts,
            "activeAlertsCount": active_alerts,
            "active_alerts": active_alerts,
            "activeAlerts": active_alerts,
            "active": active_alerts,
            "device_alerts": total_alerts_count,
            "deviceAlerts": total_alerts_count,
            "alerts_count": total_alerts_count,
            "alert_count": total_alerts_count,
            "alerts": total_alerts_count,
            "total_alerts": total_alerts_count,
            "totalAlerts": total_alerts_count,
            "total_records": total_alerts_count,
            "totalRecords": total_alerts_count,

            "live_tcp_sockets": live_tcp_connections
        }

    def list_all_devices(self) -> List[Dict[str, Any]]:
        return device_service.get_all_devices()

    def get_device_detail(self, device_id: str) -> Dict[str, Any]:
        dev = device_service.get_device_by_id(device_id)
        if not dev:
            return {"error": "Device not found"}
        history = firestore_service.get_telemetry_history(device_id, limit=20)
        return {
            "device": dev,
            "recent_positions": history
        }

    def get_device_history(self, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return firestore_service.get_telemetry_history(device_id, limit=limit)

    def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return alert_service.get_recent_alerts(limit=limit)

    def dispatch_command(self, device_id: str, command: str) -> Dict[str, Any]:
        success = send_command_to_device(device_id, command)
        return {
            "device_id": device_id,
            "command": command,
            "dispatched": success,
            "message": "Command transmitted to watch" if success else "Watch is offline or in low-power sleep mode"
        }


dashboard_service = DashboardService()

