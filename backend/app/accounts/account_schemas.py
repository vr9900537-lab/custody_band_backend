"""
Account Schemas
Models for officer and administrator profile management.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AccountBase(BaseModel):
    email: str = Field(..., description="User email address")
    full_name: Optional[str] = None
    role: Optional[str] = "officer"
    badge_number: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = "Custody Monitoring"


class AccountCreate(AccountBase):
    password: str = Field(..., min_length=6)


class AccountUpdate(BaseModel):
    full_name: Optional[str] = None
    badge_number: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class AccountResponse(AccountBase):
    is_active: bool = True
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

