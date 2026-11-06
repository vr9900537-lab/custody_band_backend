"""
Data Export API Routes
Endpoints for downloading CSV data trails and generating court compliance evidence packets.
"""

from typing import Dict, Any
from fastapi import APIRouter, Response, Query
from ..exports.export_service import export_service

router = APIRouter(prefix="/exports", tags=["Exports & Legal Evidence"])


@router.get("/telemetry/{device_id}/csv")
def download_telemetry_csv(
    device_id: str,
    limit: int = Query(500, ge=1, le=5000)
):
    """Download historical GPS telemetry as a CSV file."""
    csv_data = export_service.export_telemetry_csv(device_id, limit=limit)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=telemetry_{device_id}.csv"}
    )


@router.get("/alerts/csv")
def download_alerts_csv(
    limit: int = Query(500, ge=1, le=5000)
):
    """Download security incident alerts log as a CSV file."""
    csv_data = export_service.export_alerts_csv(limit=limit)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=incident_alerts.csv"}
    )


@router.get("/court-evidence/{device_id}", response_model=Dict[str, Any])
def get_court_evidence_packet(device_id: str):
    """
    Generate an unalterable forensic summary packet for judicial/parole hearings:
    Includes wearer identity, verified GPS trajectory, tampering alerts, and officer command audit logs.
    """
    return export_service.generate_court_evidence_packet(device_id)

