from fastapi import APIRouter, Request, status
from schemas.tenants import TenantRegisterRequest, TenantRegisterOut
from services.tenants import TenantService
from utils.deps import db_dependency
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
                api_key=api_key_plaintext
            )