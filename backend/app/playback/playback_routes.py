"""
Playback API Routes
Historical GPS route playback and stop-detection endpoints.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Query
from ..playback.playback_service import playback_service

router = APIRouter(prefix="/playback", tags=["Playback"])


@router.get("/{device_id}", response_model=Dict[str, Any])
def get_playback_route(
    device_id: str,
    limit: int = Query(200, ge=1, le=1000, description="Max GPS coordinates to replay"),
    start_date: Optional[str] = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date filter YYYY-MM-DD")
):
    """
    Returns historical route trail in chronological order for UI map playback,
    with calculated total distance (km) and dwell stops.
    """
    return playback_service.get_route_trail(
        device_id=device_id,
        limit=limit,
        start_date=start_date,
        end_date=end_date
    )

