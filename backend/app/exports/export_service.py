"""
Data Export & Court Evidence Service
Generates CSV and forensic JSON evidence packages for court compliance and external archiving.
"""

import csv
import io
from typing import Dict, Any, List
from ..services.firestore_service import firestore_service
from ..services.device_service import device_service
from ..alerts.alert_service import incident_alert_service
from ..commands.command_service import command_service
from ..utils.datetime_utils import current_iso_timestamp


class ExportService:
    def export_telemetry_csv(self, device_id: str, limit: int = 500) -> str:
        points = firestore_service.get_telemetry_history(device_id, limit=limit)
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "ID", "Device_IMEI", "Timestamp", "GPS_Valid",
            "Latitude", "Longitude", "Speed_KMH", "Battery", "Steps", "Google_Maps_URL"
        ])

        for p in points:
            writer.writerow([
                p.get("id"),
                device_id,
                p.get("timestamp"),
                "YES" if p.get("gps_valid") else "NO",
                p.get("latitude"),
                p.get("longitude"),
                p.get("speed_kmh", 0.0),
                p.get("battery", 0),
                p.get("steps", 0),
                p.get("maps_url", "")
            ])
        return output.getvalue()

    def export_alerts_csv(self, limit: int = 500) -> str:
        alerts = incident_alert_service.list_alerts(limit=limit)
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Alert_ID", "Device_IMEI", "Timestamp", "Alert_Type",
            "Message", "Latitude", "Longitude", "Status", "Acknowledged_By", "Resolved_By", "Notes"
        ])

        for a in alerts:
            writer.writerow([
                a.get("id"),
                a.get("device_id"),
                a.get("timestamp"),
                a.get("alert_type"),
                a.get("message"),
                a.get("latitude"),
                a.get("longitude"),
                a.get("status"),
                a.get("acknowledged_by", ""),
                a.get("resolved_by", ""),
                a.get("notes", "")
            ])
        return output.getvalue()

    def generate_court_evidence_packet(self, device_id: str) -> Dict[str, Any]:
        """Compiles a complete court evidence audit packet."""
        dev = device_service.get_device_by_id(device_id) or {}
        telemetry = firestore_service.get_telemetry_history(device_id, limit=100)
        alerts = incident_alert_service.list_alerts(device_id=device_id, limit=50)
        commands = command_service.get_command_history(device_id=device_id, limit=50)

        return {
            "evidence_package_id": f"COURT-EVID-{device_id}-{int(current_iso_timestamp()[-5:].replace(':', ''))}",
            "generated_at": current_iso_timestamp(),
            "subject_device": {
                "device_id": device_id,
                "wearer_name": dev.get("wearer_name", "Unassigned"),
                "case_number": dev.get("case_number", "N/A"),
                "status": dev.get("status", "ACTIVE")
            },
            "total_telemetry_records": len(telemetry),
            "total_security_alerts": len(alerts),
            "total_commands_dispatched": len(commands),
            "recent_telemetry": telemetry[:20],
            "security_incidents": alerts,
            "officer_action_trail": commands
        }


export_service = ExportService()

