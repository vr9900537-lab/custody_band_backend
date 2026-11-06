"""
Device & Custody Band Schemas
"""

from typing import Optional
from pydantic import BaseModel, Field


class DeviceBase(BaseModel):
    device_id: str = Field(..., description="Watch IMEI / Serial Number (e.g. 863758061830955)")
    maker: str = Field("MNYD", description="Manufacturer prefix")
    wearer_name: Optional[str] = Field(None, description="Assigned individual / inmate / parolee")
    case_number: Optional[str] = Field(None, description="Legal case or registry number")
    is_active: bool = True


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    wearer_name: Optional[str] = None
    case_number: Optional[str] = None
    is_active: Optional[bool] = None


class DeviceResponse(DeviceBase):
    last_seen: Optional[str] = None
    battery: Optional[int] = 0
    steps: Optional[int] = 0
    heart_rate: Optional[int] = None
    status: Optional[str] = "OFFLINE"
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    maps_url: Optional[str] = None

    class Config:
        from_attributes = True


class DeviceCommandRequest(BaseModel):
    command: str = Field("CR", description="Protocol command string (e.g. CR for live GPS, RESET for reboot)")

