"""
Alert API Routes
Incident management, alert filtering, acknowledgment, and resolution workflows.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Query, Depends, Request
from ..alerts.alert_schemas import AlertAcknowledgeRequest, AlertResolveRequest
from ..alerts.alert_service import incident_alert_service
from ..core.dependencies import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]], include_in_schema=False)
def list_alerts(
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    device_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 500
):
    """List security alerts and tamper events with optional filtering."""
    alerts = incident_alert_service.list_alerts(
        status=status,
        alert_type=alert_type,
        device_id=device_id,
        limit=limit
    )
    return alerts[skip : skip + limit]


@router.get("/stats", response_model=Dict[str, Any])
@router.get("/summary", response_model=Dict[str, Any], include_in_schema=False)
@router.get("/count", response_model=Dict[str, Any], include_in_schema=False)
@router.get("/unread", response_model=Dict[str, Any], include_in_schema=False)
def get_alert_stats():
    """Returns aggregated alert counters."""
    alerts = incident_alert_service.list_alerts(limit=1000)
    total = len(alerts)
    new_count = sum(1 for a in alerts if a.get("status") == "NEW")
    ack_count = sum(1 for a in alerts if a.get("status") == "ACKNOWLEDGED")
    resolved_count = sum(1 for a in alerts if a.get("status") == "RESOLVED")
    return {
        "total": total,
        "count": total,
        "new": new_count,
        "unread": new_count,
        "acknowledged": ack_count,
        "resolved": resolved_count,
        "active": new_count + ack_count
    }


@router.get("/{alert_id}", response_model=Dict[str, Any])
def get_alert(alert_id: int):
    """Retrieve full incident details for an alarm."""
    alert = incident_alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.post("/acknowledge", response_model=Dict[str, Any])
@router.post("/ack", response_model=Dict[str, Any], include_in_schema=False)
async def acknowledge_alert_body(request: Request):
    """Acknowledge alert with alert ID passed in body or query."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    alert_id = body.get("id") or body.get("alert_id") or request.query_params.get("id") or request.query_params.get("alert_id")
    if not alert_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing alert id")
    notes = body.get("notes") or body.get("resolution_notes")
    res = incident_alert_service.acknowledge_alert(int(alert_id), "admin", notes)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return res


@router.post("/resolve", response_model=Dict[str, Any])
async def resolve_alert_body(request: Request):
    """Resolve alert with alert ID passed in body or query."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    alert_id = body.get("id") or body.get("alert_id") or request.query_params.get("id") or request.query_params.get("alert_id")
    if not alert_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing alert id")
    notes = body.get("resolution_notes") or body.get("notes") or "Resolved by officer"
    res = incident_alert_service.resolve_alert(int(alert_id), "admin", notes)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return res


@router.post("/{alert_id}/acknowledge", response_model=Dict[str, Any])
@router.post("/{alert_id}/ack", response_model=Dict[str, Any], include_in_schema=False)
@router.put("/{alert_id}/acknowledge", response_model=Dict[str, Any], include_in_schema=False)
@router.put("/{alert_id}/ack", response_model=Dict[str, Any], include_in_schema=False)
async def acknowledge_alert(
    alert_id: int,
    request: Request
):
    """Acknowledge an incoming security alert."""
    notes = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            notes = body.get("notes") or body.get("resolution_notes")
    except Exception:
        pass

    officer_email = "admin"
    res = incident_alert_service.acknowledge_alert(alert_id, officer_email, notes)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return res


@router.post("/{alert_id}/resolve", response_model=Dict[str, Any])
@router.put("/{alert_id}/resolve", response_model=Dict[str, Any], include_in_schema=False)
async def resolve_alert(
    alert_id: int,
    request: Request
):
    """Mark an alert incident as resolved with explanation notes."""
    notes = "Resolved by officer"
    try:
        body = await request.json()
        if isinstance(body, dict):
            notes = body.get("resolution_notes") or body.get("notes") or notes
    except Exception:
        pass

    officer_email = "admin"
    res = incident_alert_service.resolve_alert(alert_id, officer_email, notes)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return res


@router.put("/{alert_id}", response_model=Dict[str, Any])
@router.patch("/{alert_id}", response_model=Dict[str, Any], include_in_schema=False)
async def update_alert(
    alert_id: int,
    request: Request
):
    """Direct status update for an alert (ACKNOWLEDGED / RESOLVED)."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    st = body.get("status", "ACKNOWLEDGED").upper()
    notes = body.get("notes") or body.get("resolution_notes")

    if st == "RESOLVED":
        return incident_alert_service.resolve_alert(alert_id, "admin", notes or "Resolved")
    else:
        return incident_alert_service.acknowledge_alert(alert_id, "admin", notes)

