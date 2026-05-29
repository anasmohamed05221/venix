from fastapi import APIRouter, Request, status
from schemas.tenants import (
    TenantRegisterRequest, TenantRegisterOut,
    TenantRotateOut, TenantRevokeOut,
    TenantProfileOut, TenantUpdateRequest,
    TenantVerifyEmailRequest, TenantInitiatePasswordChangeRequest,
    TenantChangePasswordRequest, TenantDeactivateRequest,
    TenantMessageOut,
)
from services.tenants import TenantService
from utils.deps import db_dependency, tenant_dependency
from middleware.rate_limiter import limiter
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/tenants",
    tags=["tenants"]
)

@router.post("/register", response_model=TenantRegisterOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register_tenant(db: db_dependency, request: Request, body: TenantRegisterRequest):
    """Register a new tenant and return a one-time plaintext API key."""
    tenant_obj, api_key_plaintext = await TenantService.register_tenant(db, body.name, body.slug,
                                                                        body.email, body.password, body.plan)
    logger.info("Tenant registered", extra={"tenant_id": str(tenant_obj.id), "slug": tenant_obj.slug})
    return TenantRegisterOut(
                id=tenant_obj.id,
                name=tenant_obj.name,
                slug=tenant_obj.slug,
                plan=tenant_obj.plan,
                is_active=tenant_obj.is_active,
                created_at=tenant_obj.created_at,
                api_key=api_key_plaintext,
                message="Tenant created successfully. Save your API key now, it will not be shown again. The owner account was automatically registered as the tenant administrator and can log in to the store using the same credentials."
            )

@router.post("/me/rotate-api-key", response_model=TenantRotateOut, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def rotate_api_key(db: db_dependency, request: Request, tenant: tenant_dependency):
    """Rotate the current tenant's API key and return the new plaintext key exactly once."""
    new_plaintext = await TenantService.rotate_api_key(db, tenant)
    logger.info("API key rotated", extra={"tenant_id": str(tenant.id)})
    return TenantRotateOut(api_key=new_plaintext, message="New API key issued. Save it now, it will not be shown again.")


@router.delete("/me/api-key", response_model=TenantRevokeOut, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def revoke_api_key(db: db_dependency, request: Request, tenant: tenant_dependency):
    """Revoke the current tenant's API key; tenant remains active and can still authenticate via JWT."""
    await TenantService.revoke_api_key(db, tenant)
    logger.info("API key revoked", extra={"tenant_id": str(tenant.id)})
    return TenantRevokeOut(message="API key revoked. Use your credentials to log in and rotate a new key.")


@router.get("/me", response_model=TenantProfileOut, status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def get_tenant_profile(request: Request, tenant: tenant_dependency):
    """Return the current tenant's profile; never exposes credentials or internal fields."""
    return tenant


@router.put("/me", response_model=TenantProfileOut, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def update_tenant_profile(db: db_dependency, request: Request, tenant: tenant_dependency, body: TenantUpdateRequest):
    """Update the current tenant's mutable profile fields."""
    updated = await TenantService.update_profile(db, tenant, body.name)
    logger.info("Tenant profile updated", extra={"tenant_id": str(tenant.id)})
    return updated


@router.post("/me/verify-email", response_model=TenantMessageOut, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def verify_tenant_email(db: db_dependency, request: Request, tenant: tenant_dependency, body: TenantVerifyEmailRequest):
    """Verify the tenant's email address using the 6-digit code sent at registration."""
    await TenantService.verify_email(db, tenant, body.code)
    return TenantMessageOut(message="Email verified successfully.")


@router.post("/me/resend-verification", response_model=TenantMessageOut, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def resend_tenant_verification(db: db_dependency, request: Request, tenant: tenant_dependency):
    """Regenerate and resend the email verification code; invalidates any previous code."""
    await TenantService.resend_verification(db, tenant)
    logger.info("Verification email resent", extra={"tenant_id": str(tenant.id)})
    return TenantMessageOut(message="Verification email sent.")


@router.post("/me/initiate-change-password", response_model=TenantMessageOut, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def initiate_tenant_password_change(db: db_dependency, request: Request, tenant: tenant_dependency, body: TenantInitiatePasswordChangeRequest):
    """Verify current password and dispatch a confirmation code to the tenant's email."""
    await TenantService.initiate_password_change(db, tenant, body.current_password)
    logger.info("Password change initiated", extra={"tenant_id": str(tenant.id)})
    return TenantMessageOut(message="A confirmation code has been sent to your email.")


@router.post("/me/change-password", response_model=TenantMessageOut, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def change_tenant_password(db: db_dependency, request: Request, tenant: tenant_dependency, body: TenantChangePasswordRequest):
    """Confirm the code and apply the new password; revokes all active sessions."""
    await TenantService.change_password(db, tenant, body.code, body.new_password)
    logger.info("Tenant password changed", extra={"tenant_id": str(tenant.id)})
    return TenantMessageOut(message="Password changed successfully. All sessions have been revoked.")


@router.post("/deactivate", response_model=TenantMessageOut, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def deactivate_tenant(db: db_dependency, request: Request, tenant: tenant_dependency, body: TenantDeactivateRequest):
    """Deactivate the tenant account after password confirmation; requires email to be verified."""
    await TenantService.deactivate(db, tenant, body.password)
    logger.info("Tenant account deactivated", extra={"tenant_id": str(tenant.id)})
    return TenantMessageOut(message="Account deactivated.")