"""
Role API Routes
RBAC authorization roles and permission queries.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from ..roles.role_schemas import RoleAssignRequest
from ..roles.role_service import role_service
from ..core.dependencies import get_current_user

router = APIRouter(prefix="/roles", tags=["Roles & RBAC"])


@router.get("", response_model=List[Dict[str, Any]])
def list_roles():
    """List all available system roles and their associated permissions."""
    return role_service.list_roles()


@router.get("/{role_name}", response_model=Dict[str, Any])
def get_role(role_name: str):
    """Get permission details for a specific role."""
    role = role_service.get_role(role_name)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.post("/assign", response_model=Dict[str, Any])
def assign_role(
    req: RoleAssignRequest,
    current_user: dict = Depends(get_current_user)
):
    """Assign an administrative or officer role to a user."""
    try:
        return role_service.assign_role(req.user_email, req.role_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

