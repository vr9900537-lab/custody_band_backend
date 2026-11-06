"""
Fleet Analytics & Compliance Statistics Service
Calculates battery trends, distance aggregations, alert distributions, and wearer compliance.
"""

import sqlite3
from pathlib import Path
from typing import Dict, Any, List
from ..services.device_service import device_service

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_DB = BASE_DIR / "custody_watch.db"


class StatisticsService:
    def get_fleet_statistics(self) -> Dict[str, Any]:
        devices = device_service.get_all_devices()
        total_devices = len(devices)

        # Battery Breakdown
        high_battery = sum(1 for d in devices if d.get("battery", 0) >= 75)
        medium_battery = sum(1 for d in devices if 25 <= d.get("battery", 0) < 75)
        low_battery = sum(1 for d in devices if d.get("battery", 0) < 25)

        # Alerts breakdown from DB
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        alert_rows = cur.execute("""
            SELECT alert_type, COUNT(*) as count FROM alerts GROUP BY alert_type
        """).fetchall()
        alert_distribution = {r["alert_type"]: r["count"] for r in alert_rows}

        # Telemetry metrics
        telemetry_count = cur.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
        conn.close()

        total_steps = sum(d.get("steps", 0) for d in devices)
        avg_steps = round(total_steps / total_devices) if total_devices else 0

        # Compliance score calculation
        total_alerts = sum(alert_distribution.values())
        compliance_pct = max(0.0, round(100.0 - (total_alerts * 2.5), 1))

        return {
            "total_devices_monitored": total_devices,
            "overall_compliance_percentage": compliance_pct,
            "total_telemetry_points_recorded": telemetry_count,
            "average_daily_steps": avg_steps,
            "battery_health": {
                "high_battery_75_plus": high_battery,
                "medium_battery_25_to_75": medium_battery,
                "critical_battery_under_25": low_battery
            },
            "alert_distribution": alert_distribution
        }


statistics_service = StatisticsService()

