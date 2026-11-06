"""
Role & Permission Schemas
Models for RBAC (Role-Based Access Control) definition and assignment.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class RoleDefinition(BaseModel):
    name: str = Field(..., description="Role identifier (e.g. admin, supervisor, field_officer)")
    display_name: str
    description: str
    permissions: List[str]


class RoleAssignRequest(BaseModel):
    user_email: str
    role_name: str

