"""
Command Schemas
Models for remote watch protocol commands and dispatch tracking.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class SendCommandRequest(BaseModel):
    device_id: str = Field(..., description="Target watch IMEI")
    command_type: str = Field("CR", description="Protocol command: CR, RESET, UPLOAD, SETIP, POWEROFF, FACTORY")
    parameters: Optional[str] = Field(None, description="Optional parameters (e.g. upload interval in seconds, or IP/Port)")


class CommandAuditRecord(BaseModel):
    id: int
    device_id: str
    command_raw: str
    command_type: str
    dispatched_by: Optional[str] = None
    dispatched: bool
    timestamp: str

