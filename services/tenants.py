import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from utils.hashing import hash_token, get_password_hash
from models.tenants import Tenant
from models.enums import PlanTier
from utils.logger import get_logger

logger = get_logger(__name__)


class TenantService:
    """Handles tenant registration and lifecycle operations."""

    @staticmethod
    async def register_tenant(db: AsyncSession, name: str, slug: str, email: str, password: str, plan: PlanTier) -> tuple[Tenant, str]:
        """Create a new tenant, hash credentials, and return the tenant with its plaintext API key."""
        api_key_plaintext = "vnx_" + secrets.token_urlsafe(32)
        api_key_hash = hash_token(api_key_plaintext)

        password_hash = get_password_hash(password)

        tenant = Tenant(
            name=name,
            owner_email=email,
            owner_password_hash=password_hash,
            slug=slug,
            plan=plan,
            api_key_hash=api_key_hash,
            is_active=True,
        )

        db.add(tenant)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            logger.warning("Tenant registration conflict", extra={"slug": slug, "email": email})
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="slug already taken")
        except Exception:
            await db.rollback()
            logger.error("Tenant registration commit failed", extra={"slug": slug}, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Tenant registration commit failed")

        await db.refresh(tenant)
        return tenant, api_key_plaintext

