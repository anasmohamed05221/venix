import secrets
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from utils.hashing import hash_token, get_password_hash, verify_password
from utils.verification import generate_verification_code, get_code_expiry_time
from utils.email_templates import tenant_verification_email, tenant_password_change_code_email
from tasks.emails import send_email_task
from models.tenants import Tenant
from models.users import User
from models.enums import PlanTier, UserRole
from utils.logger import get_logger
from core.redis_client import redis_client
from redis.exceptions import RedisError
from services.token import TokenService

logger = get_logger(__name__)


class TenantService:
    """Handles tenant registration and lifecycle operations."""

    @staticmethod
    def _generate_api_key() -> tuple[str, str]:
        """Generate a prefixed plaintext API key and its SHA256 hash; returns (plaintext, hash)."""
        plaintext = "vnx_" + secrets.token_urlsafe(32)
        return plaintext, hash_token(plaintext)

    @staticmethod
    async def register_tenant(db: AsyncSession, name: str, slug: str, email: str, password: str, plan: PlanTier) -> tuple[Tenant, str]:
        """Create a new tenant, hash credentials, and return the tenant with its plaintext API key."""
        api_key_plaintext, api_key_hash = TenantService._generate_api_key()
        password_hash = get_password_hash(password)
        verification_code = generate_verification_code()
        verification_expiry = get_code_expiry_time()

        tenant = Tenant(
            name=name,
            owner_email=email,
            owner_password_hash=password_hash,
            slug=slug,
            plan=plan,
            api_key_hash=api_key_hash,
            is_active=True,
            verification_code=verification_code,
            verification_code_expires_at=verification_expiry,
        )

        try:
            db.add(tenant)
            await db.flush()

            user = User(
                tenant_id=tenant.id,
                email=email,
                first_name="Admin",
                last_name=name,
                hashed_password=password_hash,
                role=UserRole.ADMIN,
                is_verified=True,
            )
            db.add(user)
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
        send_email_task.delay(tenant.owner_email, "Verify Your Tenant Email - Venix", tenant_verification_email(verification_code))
        return tenant, api_key_plaintext

    @staticmethod
    async def rotate_api_key(db: AsyncSession, tenant: Tenant) -> str:
        """Rotate the tenant's API key atomically and invalidate both Redis cache entries."""
        old_hash = tenant.api_key_hash
        new_plaintext, new_hash = TenantService._generate_api_key()

        tenant_row = await db.scalar(select(Tenant).where(Tenant.id == tenant.id))
        tenant_row.api_key_hash = new_hash

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Tenant key rotation commit failed", extra={"tenant_id": str(tenant.id)}, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Tenant key rotation commit failed")

        try:
            await redis_client.redis.delete(f"tenant:apikey:{old_hash}")
        except RedisError:
            logger.warning("API key cache invalidation failed", extra={"tenant_id": str(tenant.id)})

        try:
            await redis_client.redis.delete(f"tenant:id:{tenant.id}")
        except RedisError:
            logger.warning("Tenant cache invalidation failed", extra={"tenant_id": str(tenant.id)})

        return new_plaintext

    @staticmethod
    async def revoke_api_key(db: AsyncSession, tenant: Tenant) -> None:
        """Revoke the tenant's API key and invalidate both Redis cache entries."""
        if tenant.api_key_hash is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No API key to revoke")

        old_hash = tenant.api_key_hash
        tenant_row = await db.scalar(select(Tenant).where(Tenant.id == tenant.id))
        tenant_row.api_key_hash = None

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Tenant key revocation commit failed", extra={"tenant_id": str(tenant.id)}, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Tenant key revocation commit failed")

        try:
            await redis_client.redis.delete(f"tenant:apikey:{old_hash}")
        except RedisError:
            logger.warning("API key cache invalidation failed", extra={"tenant_id": str(tenant.id)})

        try:
            await redis_client.redis.delete(f"tenant:id:{tenant.id}")
        except RedisError:
            logger.warning("Tenant cache invalidation failed", extra={"tenant_id": str(tenant.id)})

    @staticmethod
    async def update_profile(db: AsyncSession, tenant: Tenant, name: str | None) -> Tenant:
        """Update the tenant's mutable profile fields; slug is immutable and never accepted."""
        tenant_row = await db.scalar(select(Tenant).where(Tenant.id == tenant.id))

        if name is not None:
            tenant_row.name = name

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Tenant profile update commit failed", extra={"tenant_id": str(tenant.id)}, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Profile update failed")

        await db.refresh(tenant_row)

        try:
            await redis_client.redis.delete(f"tenant:id:{tenant.id}")
        except RedisError:
            logger.warning("Tenant cache invalidation failed after profile update", extra={"tenant_id": str(tenant.id)})

        return tenant_row

    @staticmethod
    async def verify_email(db: AsyncSession, tenant: Tenant, code: str) -> None:
        """Validate the verification code and mark the tenant's email as verified."""
        tenant_row = await db.scalar(select(Tenant).where(Tenant.id == tenant.id))

        if tenant_row.is_verified:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already verified")

        if code != tenant_row.verification_code:
            logger.warning("Email verification failed — invalid code", extra={"tenant_id": str(tenant.id)})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

        if tenant_row.verification_code_expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired")

        tenant_row.is_verified = True
        tenant_row.verification_code = None
        tenant_row.verification_code_expires_at = None

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Email verification commit failed", extra={"tenant_id": str(tenant.id)}, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Email verification failed")

        logger.info("Tenant email verified", extra={"tenant_id": str(tenant.id)})

        try:
            await redis_client.redis.delete(f"tenant:apikey:{tenant_row.api_key_hash}")
        except RedisError:
            logger.warning("API key cache invalidation failed after email verification", extra={"tenant_id": str(tenant.id)})

        try:
            await redis_client.redis.delete(f"tenant:id:{tenant.id}")
        except RedisError:
            logger.warning("Tenant cache invalidation failed after email verification", extra={"tenant_id": str(tenant.id)})

    @staticmethod
    async def resend_verification(db: AsyncSession, tenant: Tenant) -> None:
        """Regenerate and resend the email verification code; invalidates any previous code."""
        tenant_row = await db.scalar(select(Tenant).where(Tenant.id == tenant.id))

        if tenant_row.is_verified:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already verified")

        tenant_row.verification_code = generate_verification_code()
        tenant_row.verification_code_expires_at = get_code_expiry_time()

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Resend verification commit failed", extra={"tenant_id": str(tenant.id)}, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Resend verification failed")

        send_email_task.delay(tenant_row.owner_email, "Verify Your Tenant Email - Venix", tenant_verification_email(tenant_row.verification_code))
        logger.info("Verification email resent", extra={"tenant_id": str(tenant.id)})

    @staticmethod
    async def initiate_password_change(db: AsyncSession, tenant: Tenant, current_password: str) -> None:
        """Verify current password, store a hashed confirmation code, and dispatch it to the tenant's email."""
        tenant_row = await db.scalar(select(Tenant).where(Tenant.id == tenant.id))

        if not verify_password(current_password, tenant_row.owner_password_hash):
            logger.warning("Password change initiation rejected — incorrect current password", extra={"tenant_id": str(tenant.id)})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

        code = generate_verification_code()
        tenant_row.password_change_code = hash_token(code)
        tenant_row.password_change_code_expires_at = get_code_expiry_time(minutes=15)

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Password change initiation commit failed", extra={"tenant_id": str(tenant.id)}, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Password change initiation failed")

        send_email_task.delay(tenant_row.owner_email, "Confirm Your Password Change - Venix", tenant_password_change_code_email(code))
        logger.info("Password change initiated", extra={"tenant_id": str(tenant.id)})

    @staticmethod
    async def change_password(db: AsyncSession, tenant: Tenant, code: str, new_password: str) -> None:
        """Validate the confirmation code, apply the new password atomically to both tenant and admin user, and revoke all sessions."""
        tenant_row = await db.scalar(select(Tenant).where(Tenant.id == tenant.id))
        admin_user = await db.scalar(select(User).where(User.tenant_id == tenant.id, User.role == UserRole.ADMIN))

        if tenant_row.password_change_code is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No password change in progress")

        if tenant_row.password_change_code_expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code expired")

        if hash_token(code) != tenant_row.password_change_code:
            logger.warning("Password change rejected — invalid code", extra={"tenant_id": str(tenant.id)})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

        new_hash = get_password_hash(new_password)
        tenant_row.owner_password_hash = new_hash
        if admin_user:
            admin_user.hashed_password = new_hash

        tenant_row.password_change_code = None
        tenant_row.password_change_code_expires_at = None

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Password change commit failed", extra={"tenant_id": str(tenant.id)}, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Password change failed")

        logger.info("Tenant password changed", extra={"tenant_id": str(tenant.id)})

        if admin_user:
            await TokenService.revoke_all_user_tokens(admin_user.id, db)

        try:
            await redis_client.redis.delete(f"tenant:apikey:{tenant_row.api_key_hash}")
        except RedisError:
            logger.warning("API key cache invalidation failed after password change", extra={"tenant_id": str(tenant.id)})

        try:
            await redis_client.redis.delete(f"tenant:id:{tenant.id}")
        except RedisError:
            logger.warning("Tenant cache invalidation failed after password change", extra={"tenant_id": str(tenant.id)})

    @staticmethod
    async def deactivate(db: AsyncSession, tenant: Tenant, password: str) -> None:
        """Verify password, require email verification, set tenant inactive, and invalidate all cache entries."""
        tenant_row = await db.scalar(select(Tenant).where(Tenant.id == tenant.id))

        if not tenant_row.is_verified:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email must be verified before deactivating")

        if not verify_password(password, tenant_row.owner_password_hash):
            logger.warning("Tenant deactivation rejected — incorrect password", extra={"tenant_id": str(tenant.id)})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

        tenant_row.is_active = False

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Tenant deactivation commit failed", extra={"tenant_id": str(tenant.id)}, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Tenant deactivation failed")

        logger.info("Tenant deactivated", extra={"tenant_id": str(tenant.id)})

        try:
            await redis_client.redis.delete(f"tenant:apikey:{tenant_row.api_key_hash}")
        except RedisError:
            logger.warning("API key cache invalidation failed after deactivation", extra={"tenant_id": str(tenant.id)})

        try:
            await redis_client.redis.delete(f"tenant:id:{tenant.id}")
        except RedisError:
            logger.warning("Tenant cache invalidation failed after deactivation", extra={"tenant_id": str(tenant.id)})
