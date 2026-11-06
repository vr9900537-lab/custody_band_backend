"""
Statistics API Routes
Analytics dashboards, battery distribution, and compliance score metrics.
"""

from typing import Dict, Any
from fastapi import APIRouter
from ..statistics.statistics_service import statistics_service

router = APIRouter(prefix="/statistics", tags=["Statistics"])


@router.get("/overview", response_model=Dict[str, Any])
def get_fleet_statistics():
    """
    Returns full statistical overview:
    Compliance score, battery health distribution, total telemetry points, and incident frequencies.
    """
    return statistics_service.get_fleet_statistics()

