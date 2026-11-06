"""
User & Authentication Schemas
"""

from typing import Optional
import re
from pydantic import BaseModel, Field, field_validator


EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)+$")


class UserBase(BaseModel):
    email: str = Field(..., description="User email address")
    full_name: Optional[str] = None
    role: Optional[str] = "officer"

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean_email = v.strip().lower()
        if not EMAIL_REGEX.match(clean_email):
            raise ValueError("Invalid email format")
        return clean_email


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Password with minimum 6 characters")


class UserLogin(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: str

    @property
    def identifier(self) -> str:
        ident = self.email or self.username or ""
        return ident.strip().lower()


class UserResponse(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = "officer"
    id: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    accessToken: Optional[str] = None
    token: Optional[str] = None
    token_type: str = "bearer"
    tokenType: Optional[str] = "Bearer"
    expires_in_minutes: int = 1440
    user: Optional[dict] = None
    data: Optional[dict] = None
    success: bool = True
    message: str = "Login successful"


class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
