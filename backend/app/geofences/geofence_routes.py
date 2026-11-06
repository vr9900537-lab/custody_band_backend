"""
Geofence API Routes
CRUD for virtual geographic boundaries and real-time compliance validation.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from ..geofences.geofence_schemas import GeofenceCreate, GeofenceValidateRequest
from ..geofences.geofence_service import geofence_service

router = APIRouter(prefix="/geofences", tags=["Geofences"])


@router.get("", response_model=List[Dict[str, Any]])
def list_geofences():
    """List all configured inclusion and exclusion zones."""
    return geofence_service.list_geofences()


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_geofence(geo_in: GeofenceCreate):
    """Create a new geofence zone with assigned coordinates and radius."""
    return geofence_service.create_geofence(geo_in)


@router.get("/{geofence_id}", response_model=Dict[str, Any])
def get_geofence(geofence_id: int):
    """Get details for a specific geofence zone."""
    geo = geofence_service.get_geofence(geofence_id)
    if not geo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Geofence not found")
    return geo


@router.delete("/{geofence_id}", response_model=Dict[str, Any])
def delete_geofence(geofence_id: int):
    """Delete a geofence zone."""
    success = geofence_service.delete_geofence(geofence_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Geofence not found")
    return {"status": "success", "message": "Geofence removed"}


@router.post("/validate-position", response_model=Dict[str, Any])
def validate_position(req: GeofenceValidateRequest):
    """
    Check if a wearer's coordinates are compliant with all assigned geofences.
    Triggers security alerts if an inclusion zone is exited or an exclusion zone is entered.
    """
    return geofence_service.check_position_compliance(req.device_id, req.latitude, req.longitude)

