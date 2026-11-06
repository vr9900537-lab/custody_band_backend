"""
Health Data Package
"""

from .health_routes import router as health_router
from .health_service import health_service

__all__ = ["health_router", "health_service"]

