"""
Alert Schemas
Models for incident management, emergency SOS events, and tamper notifications.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AlertAcknowledgeRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Officer acknowledgment notes")


class AlertResolveRequest(BaseModel):
    resolution_notes: str = Field(..., description="Action taken to resolve the incident")


class AlertResponse(BaseModel):
    id: int
    device_id: str
    timestamp: str
    alert_type: str
    message: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None
    notes: Optional[str] = None

