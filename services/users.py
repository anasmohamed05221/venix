import secrets
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.users import User
from models.enums import UserRole
from schemas.users import UpdateProfileRequest
from utils.email_templates import password_change_request_email, password_change_denied_email
from services.token import TokenService
from core.config import settings
from utils.hashing import verify_password, get_password_hash, hash_token
from tasks.emails import send_email_task

from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class UserService:

    @staticmethod
    async def request_password_change(db: AsyncSession, current_user: User, current_password: str, new_password: str) -> None:
        """Validate current password, store pending hash, and dispatch confirmation email."""
        if not verify_password(current_password, current_user.hashed_password):
            logger.warning("Password change rejected — incorrect current password", extra={"user_id": current_user.id})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Incorrect current password")

        confirmation_token = secrets.token_urlsafe(32)

        current_user.pending_password_hash = get_password_hash(new_password)
        current_user.password_change_token = hash_token(confirmation_token)
        current_user.password_change_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        try:
            await db.commit()
        except Exception:
            logger.error("Password change request commit failed", extra={"user_id": current_user.id}, exc_info=True)
            await db.rollback()
            raise

        confirm_url = f"{settings.BASE_URL}/users/confirm-password-change?token={confirmation_token}"
        deny_url = f"{settings.BASE_URL}/users/deny-password-change?token={confirmation_token}"

        subject="Confirm Password Change"
        send_email_task.delay(current_user.email, subject, password_change_request_email(confirm_url, deny_url))


    @staticmethod
    async def confirm_password_change(db: AsyncSession, token: str) -> None:
        """Apply pending password hash and revoke all sessions."""
        user = await db.scalar(select(User).where(
            User.password_change_token == hash_token(token),
            User.password_change_expires_at > datetime.now(timezone.utc)
        ))

        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid or expired token")

        if not user.pending_password_hash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid or expired token")

        user.hashed_password = user.pending_password_hash
        user.pending_password_hash = None
        user.password_change_token = None
        user.password_change_expires_at = None

        try:
            await db.commit()
        except Exception:
            logger.error("Password change confirmation commit failed", extra={"user_id": user.id}, exc_info=True)
            await db.rollback()
            raise

        await TokenService.revoke_all_user_tokens(user.id, db)


    @staticmethod
    async def deny_password_change(db: AsyncSession, token: str) -> None:
        """Cancel pending password change, revoke all sessions, and send security alert."""
        user = await db.scalar(select(User).where(
            User.password_change_token == hash_token(token)
        ))

        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid token")

        user.pending_password_hash = None
        user.password_change_token = None
        user.password_change_expires_at = None

        try:
            await db.commit()
        except Exception:
            logger.error("Password change denial commit failed", extra={"user_id": user.id}, exc_info=True)
            await db.rollback()
            raise

        await TokenService.revoke_all_user_tokens(user.id, db)

        subject="Security Alert: Password Change Denied"
        send_email_task.delay(user.email, subject, password_change_denied_email())


    @staticmethod
    async def update_profile(db: AsyncSession, user: User, data: UpdateProfileRequest) -> User:
        """Partially update user profile (name, phone number)"""
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)

        try:
            await db.commit()
        except Exception:
            logger.error("Profile update commit failed", extra={"user_id": user.id}, exc_info=True)
            await db.rollback()
            raise
        await db.refresh(user)
        return user


    @staticmethod
    async def deactivate_self(db: AsyncSession, current_user: User, password: str) -> None:
        """Verify password, deactivate account, and revoke all sessions."""
        if not verify_password(plain_password=password, hashed_password=current_user.hashed_password):
            logger.warning("Self-deactivation rejected — incorrect password", extra={"user_id": current_user.id})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Incorrect password")

        current_user.is_active = False
        try:
            await db.commit()
        except Exception:
            logger.error("Self-deactivation commit failed", extra={"user_id": current_user.id}, exc_info=True)
            await db.rollback()
            raise

        await TokenService.revoke_all_user_tokens(current_user.id, db)


    @staticmethod
    async def get_all_users(db: AsyncSession, limit: int, offset: int, role_filter: Optional[UserRole], is_active_filter: Optional[bool]) -> tuple[list[User], int]:
        """Return a paginated list of all users. Optionally filter by role and/or is_active."""
        query = select(User).order_by(User.id)
        if role_filter is not None:
            query = query.where(User.role == role_filter)
        if is_active_filter is not None:
            query = query.where(User.is_active == is_active_filter)

        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        users = (await db.scalars(query.offset(offset).limit(limit))).all()

        return users, total
    

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
        """Return a single user by ID. Raises 404 if not found."""
        user = await db.scalar(select(User).where(User.id == user_id))
        
        if user is None: 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        return user
    

    @staticmethod
    async def deactivate_user(db: AsyncSession, target_user_id: int, admin_id: int) -> User:
        """Deactivate a user account and revoke all their sessions. Admin cannot target themselves.

        Raises 400 (self-targeting), 404 (not found), 409 (already inactive).
        """
        if target_user_id == admin_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot deactivate their own account")
        
        user = await db.scalar(select(User).where(User.id == target_user_id))

        if user is None: 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already inactive")
        
        user.is_active = False

        try:
            await db.commit()
        except Exception:
            logger.error("User deactivation commit failed", extra={"target_user_id": target_user_id}, exc_info=True)
            await db.rollback()
            raise

        await TokenService.revoke_all_user_tokens(user.id, db)

        return user


    @staticmethod
    async def reactivate_user(db: AsyncSession, target_user_id: int) -> User:
        """Reactivate a previously deactivated user account. Raises 404 (not found), 409 (already active)."""
        user = await db.scalar(select(User).where(User.id == target_user_id))

        if user is None: 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        if user.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already active")
        
        user.is_active = True

        try:
            await db.commit()
        except Exception:
            logger.error("User reactivation commit failed", extra={"target_user_id": target_user_id}, exc_info=True)
            await db.rollback()
            raise

        return user

    @staticmethod
    async def update_user_role(db: AsyncSession, target_user_id: int, new_role: UserRole, admin_id: int) -> User:
        """Promote or demote a user's role. Admin cannot target themselves.

        Raises 400 (self-targeting), 404 (not found), 409 (already has role).
        """
        if target_user_id == admin_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can't change your own role")
        
        user = await db.scalar(select(User).where(User.id == target_user_id))

        if user is None: 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        if user.role == new_role:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"User already has the role: {new_role.value}")
        
        user.role = new_role

        try:
            await db.commit()
        except Exception:
            logger.error("Role update commit failed", extra={"target_user_id": target_user_id}, exc_info=True)
            await db.rollback()
            raise

        return user