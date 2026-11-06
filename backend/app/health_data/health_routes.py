"""
Health & Biometrics API Routes
Endpoints for monitoring wearer heart rate pulse and pedometer activity.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Query
from ..health_data.health_service import health_service

router = APIRouter(prefix="/health-data", tags=["Health & Biometrics"])


@router.get("/device/{device_id}/summary", response_model=Dict[str, Any])
@router.get("/{device_id}/summary", response_model=Dict[str, Any], include_in_schema=False)
@router.get("/{device_id}", response_model=Dict[str, Any], include_in_schema=False)
def get_device_health_summary(device_id: str):
    """
    Retrieve current biometric overview:
    Current pulse, average pulse, daily steps, and vital sign thresholds.
    """
    return health_service.get_health_summary(device_id)


@router.get("/device/{device_id}/heart-rate", response_model=List[Dict[str, Any]])
@router.get("/{device_id}/heart-rate", response_model=List[Dict[str, Any]], include_in_schema=False)
def get_heart_rate_history(
    device_id: str,
    limit: int = Query(50, ge=1, le=10000)
):
    """Retrieve historical pulse timeline readings."""
    return health_service.get_heart_rate_history(device_id, limit=limit)

