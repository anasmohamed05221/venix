from pydantic import BaseModel, Field, EmailStr, field_validator
from models.enums import PlanTier
from utils.validators import validate_password
from uuid import UUID
from datetime import datetime
from typing import Optional

class TenantRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=3, max_length=50, pattern=r"^[a-z0-9][a-z0-9-]{2,49}$")
    email: EmailStr
    password: str
    plan: PlanTier = PlanTier.FREE

    @field_validator('password')
    @classmethod
    def validate_password(cls, value):
        return validate_password(value)

class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: PlanTier
    is_active: bool
    created_at: datetime
    
    model_config = {
        'from_attributes': True
    }

class TenantRegisterOut(TenantOut):
    api_key: str
    message: str

class TenantRotateOut(BaseModel):
    api_key: str
    message: str

class TenantRevokeOut(BaseModel):
    message: str

class TenantProfileOut(TenantOut):
    """Response schema for GET /tenants/me and PUT /tenants/me."""
    owner_email: str
    is_verified: bool

class TenantUpdateRequest(BaseModel):
    """Request schema for PUT /tenants/me; all fields optional for partial update."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)

class TenantVerifyEmailRequest(BaseModel):
    """Request schema for POST /tenants/me/verify-email."""
    code: str = Field(pattern=r"^\d{6}$")

class TenantInitiatePasswordChangeRequest(BaseModel):
    """Request schema for POST /tenants/me/initiate-change-password."""
    current_password: str

class TenantChangePasswordRequest(BaseModel):
    """Request schema for POST /tenants/me/change-password."""
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, value):
        """Enforce password strength on the new password."""
        return validate_password(value)

class TenantDeactivateRequest(BaseModel):
    """Request schema for POST /tenants/deactivate."""
    password: str

class TenantMessageOut(BaseModel):
    """Generic message-only response for tenant management endpoints."""
    message: str