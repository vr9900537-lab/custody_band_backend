"""
Journey & Route Tracking API Routes
Provides endpoints for starting, live-tracking, and ending custody band journeys,
calculating Haversine distance, and retrieving completed journey history from Firestore/SQLite.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from ..services.journey_service import journey_service
from ..config import settings

router = APIRouter(prefix="/journeys", tags=["Journeys & Travel Tracking"])


class StartJourneyRequest(BaseModel):
    device_id: str = Field(..., description="IMEI or ID of the custody band device", example="863758061830955")


class EndJourneyRequest(BaseModel):
    device_id: str = Field(..., description="IMEI or ID of the custody band device", example="863758061830955")
    journey_id: Optional[str] = Field(None, description="Optional specific journey ID to end")


@router.post("/start", response_model=Dict[str, Any])
def start_journey(request: StartJourneyRequest):
    """
    Starts a travel journey for the specified custody device.
    Captures initial valid GPS coordinates as the START marker.
    """
    dev_id = request.device_id.strip()
    if not dev_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    journey = journey_service.start_journey(dev_id)
    return {
        "success": True,
        "message": "Journey started successfully",
        "data": journey,
        "journey": journey
    }


@router.post("/end", response_model=Dict[str, Any])
def end_journey(request: EndJourneyRequest):
    """
    Ends the current travel journey for the custody device.
    Captures final valid GPS coordinates as the END marker,
    calculates total travelled distance (km) and journey duration.
    """
    dev_id = request.device_id.strip()
    if not dev_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    journey = journey_service.end_journey(dev_id, journey_id=request.journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail=f"No active journey found for device {dev_id}")

    return {
        "success": True,
        "message": "Journey ended successfully",
        "data": journey,
        "journey": journey
    }


@router.get("/active/{device_id}", response_model=Dict[str, Any])
def get_active_journey(device_id: str):
    """
    Retrieves the currently active journey for a custody device,
    including the real-time polyline route coordinates and cumulative distance.
    """
    journey = journey_service.get_active_journey(device_id)
    if not journey:
        return {
            "active": False,
            "device_id": device_id,
            "journey": None
        }

    return {
        "active": True,
        "device_id": device_id,
        "journey": journey
    }


@router.get("/device/{device_id}", response_model=List[Dict[str, Any]])
def list_device_journeys(
    device_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max journeys to retrieve")
):
    """
    Lists historical and completed journeys for a custody band.
    """
    return journey_service.get_device_journeys(device_id, limit=limit)


@router.get("/{journey_id}", response_model=Dict[str, Any])
def get_journey_by_id(journey_id: str):
    """
    Retrieves full details of a specific journey including complete polyline route coordinates.
    """
    journey = journey_service.get_journey(journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail=f"Journey {journey_id} not found")

    return journey

