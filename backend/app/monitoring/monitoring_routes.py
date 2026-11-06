"""
Monitoring API Routes
Control-room live grids, device telemetry statuses, and summary counters.
"""

from typing import List, Dict, Any
from fastapi import APIRouter
from ..monitoring.monitoring_service import monitoring_service

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("", response_model=List[Dict[str, Any]], include_in_schema=False)
@router.get("/live", response_model=List[Dict[str, Any]], include_in_schema=False)
@router.get("/live-grid", response_model=List[Dict[str, Any]])
def get_live_grid():
    """
    Returns live monitoring grid for all wearers:
    Includes coordinates, battery, steps, heart rate, and active security flags.
    """
    return monitoring_service.get_live_grid()


@router.get("/summary", response_model=Dict[str, Any])
def get_monitoring_summary():
    """
    Returns real-time summary KPIs for dispatcher screens.
    """
    return monitoring_service.get_monitoring_summary()

