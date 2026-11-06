"""
Statistics Package
"""

from .statistics_routes import router as statistics_router
from .statistics_service import statistics_service

__all__ = ["statistics_router", "statistics_service"]

