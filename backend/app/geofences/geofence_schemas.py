"""
Geofence Schemas
Models for circular inclusion / exclusion security perimeters.
"""

from typing import Optional
from pydantic import BaseModel, Field


class GeofenceBase(BaseModel):
    name: str = Field(..., description="Geofence label (e.g. Home Perimeter, Workplace, Restraining Zone)")
    fence_type: str = Field("INCLUSION", description="'INCLUSION' (must remain inside) or 'EXCLUSION' (forbidden zone)")
    center_latitude: float = Field(..., description="Center latitude")
    center_longitude: float = Field(..., description="Center longitude")
    radius_meters: float = Field(500.0, ge=10.0, description="Zone radius in meters")
    assigned_device_id: Optional[str] = Field(None, description="Assigned watch IMEI")
    is_active: bool = True


class GeofenceCreate(GeofenceBase):
    pass


class GeofenceUpdate(BaseModel):
    name: Optional[str] = None
    fence_type: Optional[str] = None
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    radius_meters: Optional[float] = None
    assigned_device_id: Optional[str] = None
    is_active: Optional[bool] = None


class GeofenceResponse(GeofenceBase):
    id: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class GeofenceValidateRequest(BaseModel):
    device_id: str
    latitude: float
    longitude: float

