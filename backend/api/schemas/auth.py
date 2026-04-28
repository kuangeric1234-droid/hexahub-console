from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    expires_in:   int
    user:         "UserOut"


class UserOut(BaseModel):
    id:            uuid.UUID
    email:         str
    full_name:     Optional[str]
    role:          str
    is_active:     bool
    created_at:    Optional[datetime]
    last_login_at: Optional[datetime]

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email:     str = Field(min_length=3, max_length=255)
    password:  str = Field(min_length=8)
    full_name: Optional[str] = None
    role:      str = Field(default="member", pattern="^(admin|member|viewer)$")


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role:      Optional[str] = Field(default=None, pattern="^(admin|member|viewer)$")
    is_active: Optional[bool] = None


# resolve forward ref
TokenResponse.model_rebuild()
