"""
Integrations API Routes
Webhook registration and external integration health checks.
"""

from typing import List, Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..integrations.integration_service import integration_service

router = APIRouter(prefix="/integrations", tags=["Integrations & Webhooks"])


class WebhookCreateRequest(BaseModel):
    name: str = Field(..., description="Webhook identifier (e.g. Police CAD Dispatch, County Jail API)")
    target_url: str = Field(..., description="HTTPS endpoint to receive alert payloads")
    events: str = Field("ALL", description="Event triggers: ALL, SOS, STRAP_CUT, GEOFENCE_BREACH")


@router.get("/status", response_model=Dict[str, Any])
def get_integrations_status():
    """Check connectivity to Firebase Cloud, Cellular Watch Receiver, and Webhook dispatchers."""
    return integration_service.get_system_integrations_status()


@router.get("/webhooks", response_model=List[Dict[str, Any]])
def list_webhooks():
    """List all configured external dispatch webhooks."""
    return integration_service.list_webhooks()


@router.post("/webhooks", response_model=Dict[str, Any])
def create_webhook(req: WebhookCreateRequest):
    """Register a new webhook URL for real-time security incident streaming."""
    return integration_service.register_webhook(req.name, req.target_url, req.events)


@router.post("/webhooks/test", response_model=Dict[str, Any])
def test_webhook():
    """Simulates a test alert payload for webhook integrations."""
    return {
        "status": "simulated",
        "sample_event": {
            "event_type": "STRAP_CUT",
            "device_id": "863758061830955",
            "severity": "CRITICAL",
            "message": "Custody band strap tamper detected"
        }
    }

