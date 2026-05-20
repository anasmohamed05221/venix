from utils.hashing import verify_password, get_password_hash, hash_token
from models.users import User
from schemas.auth import CreateUserRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from utils.verification import generate_verification_code, get_code_expiry_time
from utils.email_templates import verification_email, password_reset_email
from fastapi import HTTPException
from starlette import status
from utils.logger import get_logger
from schemas.auth import VerifyEmailRequest
from datetime import datetime, timezone, timedelta
from core.config import settings
from services.token import TokenService
import secrets
from tasks.emails import send_email_task

logger = get_logger(__name__)

class AuthService:

    @staticmethod
    async def create_user(request: CreateUserRequest, db: AsyncSession):
        """
        Creates a new user and sends verification email.

        Flow:
        1. Check if email already exists
        2. Generate verification code
        3. Create user (unverified)
        4. Send verification email
        5. Return success message
        """
        existing_user = await db.scalar(select(User).where(User.email == request.email))
        if existing_user:
            logger.warning(
                "Registration attempt with existing email",
                extra={"email": request.email}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        code = generate_verification_code()
        expiry = get_code_expiry_time()

        model = User(
            email=request.email.lower().strip(),
            first_name=request.first_name,
            last_name=request.last_name,
            hashed_password=get_password_hash(request.password),
            phone_number=request.phone_number,
            is_verified=False,
            verification_code=code,
            verification_code_expires_at=expiry
        )

        db.add(model)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        subject = "Verify Your Email - E-commerce App"
        send_email_task.delay(model.email, subject, verification_email(code))

        await db.refresh(model)
        return model


    @staticmethod
    async def authenticate_user(email: str, password: str, db: AsyncSession):
        """Authenticate a user by email and password."""
        user = await db.scalar(select(User).where(User.email == email))

        if not user:
            logger.warning(
            "Login failed - user not found",
            extra={"email": email}
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate user.")

        if not user.is_active:
            logger.warning(
            "Login failed - inactive account",
            extra={"email": email}
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate user.")

        if not verify_password(password, user.hashed_password):
            logger.warning(
                "Login failed - invalid password",
                extra={"user_id": user.id, "email": email}
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate user.")

        if not user.is_verified:
            logger.warning(
                "Login attempt with unverified email",
                extra={"user_id": user.id, "email": email}
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox.")

        logger.debug(
            "User authenticated successfully",
            extra={"user_id": user.id, "email": email}
        )

        return user

    @staticmethod
    async def verify_user(body: VerifyEmailRequest, db: AsyncSession):
        """Verify a user's email with the provided verification code."""
        user = await db.scalar(select(User).where(User.email == body.email))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found")

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
            detail="Account inactive")

        if user.is_verified:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified")

        if body.code != user.verification_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code")

        if user.verification_code_expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code expired")

        user.is_verified = True
        user.verification_code = user.verification_code_expires_at = None

        db.add(user)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return user

    @staticmethod
    async def get_active_user_by_id(db: AsyncSession, user_id: int) -> User | None:
        """Fetch an active user by ID, or return None if not found or inactive."""
        model = await db.scalar(select(User).where(User.id == user_id, User.is_active == True))
        return model

    @staticmethod
    async def forgot_password(db: AsyncSession, email: str) -> None:
        """Generate a password reset token and dispatch a reset email.

        Silent no-op for unknown emails — prevents user enumeration.
        """
        model = await db.scalar(select(User).where(User.email == email))

        if not model:
            logger.info("Password reset requested for non-existent email", extra={"email": email})
            return

        reset_token = secrets.token_urlsafe(32)
        reset_token_hash = hash_token(reset_token)
        model.password_reset_token = reset_token_hash
        model.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        try:
            await db.commit()
        except Exception:
            logger.error("Forgot password commit failed", extra={"email": email}, exc_info=True)
            await db.rollback()
            raise

        reset_url = f"{settings.BASE_URL}/auth/reset-password?token={reset_token}"

        subject = "Reset Your Password"
        send_email_task.delay(model.email, subject, password_reset_email(reset_url))

        logger.info("Password reset email sent", extra={"user_id": model.id, "email": model.email})

    @staticmethod
    async def resend_verification(db: AsyncSession, email: str) -> None:
        """Generate a fresh verification code and re-dispatch the verification email.

        Silent no-op if the email is unknown or already verified — prevents user enumeration.
        Invalidates any previous code by overwriting it.
        """
        user = await db.scalar(select(User).where(User.email == email))

        if not user or user.is_verified:
            logger.info("Resend verification skipped", extra={"email": email})
            return

        user.verification_code = generate_verification_code()
        user.verification_code_expires_at = get_code_expiry_time()

        try:
            await db.commit()
        except Exception:
            logger.error("Resend verification commit failed", extra={"email": email}, exc_info=True)
            await db.rollback()
            raise

        subject = "Verify Your Email - E-commerce App"
        send_email_task.delay(user.email, subject, verification_email(user.verification_code))

        logger.info("Verification email resent", extra={"user_id": user.id, "email": user.email})

    @staticmethod
    async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
        """Apply a new password from a valid reset token and revoke all sessions.

        Raises:
            HTTPException 400: If token is invalid or expired.
        """
        model = await db.scalar(select(User).where(
            User.password_reset_token == hash_token(token),
            User.password_reset_expires_at > datetime.now(timezone.utc)
        ))

        if not model:
            logger.warning("Password reset failed - invalid or expired token")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

        model.hashed_password = get_password_hash(new_password)
        model.password_reset_token = None
        model.password_reset_expires_at = None

        try:
            await db.commit()
        except Exception:
            logger.error("Reset password commit failed", extra={"user_id": model.id}, exc_info=True)
            await db.rollback()
            raise

        await TokenService.revoke_all_user_tokens(model.id, db)

        logger.info("Password reset successfully", extra={"user_id": model.id, "email": model.email})