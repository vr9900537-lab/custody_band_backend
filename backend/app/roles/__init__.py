"""
Roles Package
"""

from .role_routes import router as role_router
from .role_service import role_service

__all__ = ["role_router", "role_service"]

