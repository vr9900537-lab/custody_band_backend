"""
GPS, Telemetry & Alert Schemas
"""

from typing import Optional
from pydantic import BaseModel, Field


class GPSRecord(BaseModel):
    device_id: str
    timestamp: str
    gps_valid: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kmh: float = 0.0
    course: float = 0.0
    altitude_m: float = 0.0
    battery: int = 0
    steps: int = 0
    maps_url: Optional[str] = None
    nearby_wifi_count: Optional[int] = 0


class TelemetryRecord(BaseModel):
    device_id: str
    command: str = "UD"
    timestamp: str
    watch_date: Optional[str] = None
    watch_time_utc: Optional[str] = None
    gps_valid: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kmh: float = 0.0
    battery: int = 0
    steps: int = 0
    maps_url: Optional[str] = None
    nearby_wifi_count: int = 0


class HeartRateRecord(BaseModel):
    device_id: str
    timestamp: str
    bpm: int


class AlertRecord(BaseModel):
    alert_id: Optional[str] = None
    device_id: str
    timestamp: str
    alert_type: str = Field(..., description="SOS, STRAP_CUT, LOW_BATTERY, GEOFENCE_BREACH, TAMPER")
    message: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str = "NEW"

