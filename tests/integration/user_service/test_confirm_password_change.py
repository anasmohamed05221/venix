import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from unittest.mock import patch
from services.users import UserService
from utils.hashing import verify_password


async def _setup_pending_change(session, user):
    """Helper: put user into pending password change state. Returns the RAW token."""
    import secrets as _secrets
    raw_token = _secrets.token_urlsafe(32)
    with patch("services.users.secrets.token_urlsafe", return_value=raw_token):
        with patch("tasks.emails.send_email_task.delay"):
            await UserService.request_password_change(session, user, "TestPassword123!", "NewPass123!")
    return raw_token


async def test_confirm_password_change_applies_new_password(session, verified_user):
    """Applies pending hash, clears all pending fields."""
    token = await _setup_pending_change(session, verified_user)

    await UserService.confirm_password_change(session, token)

    await session.refresh(verified_user)
    assert verify_password("NewPass123!", verified_user.hashed_password)
    assert verified_user.pending_password_hash is None
    assert verified_user.password_change_token is None
    assert verified_user.password_change_expires_at is None


async def test_confirm_password_change_invalid_token(session, verified_user):
    """Raises 400 for an unknown token."""
    with pytest.raises(HTTPException) as exc:
        await UserService.confirm_password_change(session, "invalidtoken")
    assert exc.value.status_code == 400


async def test_confirm_password_change_expired_token(session, verified_user):
    """Raises 400 when token exists but is expired."""
    raw_token = await _setup_pending_change(session, verified_user)
    verified_user.password_change_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await session.commit()

    with pytest.raises(HTTPException) as exc:
        await UserService.confirm_password_change(session, raw_token)
    assert exc.value.status_code == 400


async def test_confirm_password_change_null_pending_hash(session, verified_user):
    """Raises 400 when token is valid but pending_password_hash is None."""
    raw_token = await _setup_pending_change(session, verified_user)
    verified_user.pending_password_hash = None
    await session.commit()

    with pytest.raises(HTTPException) as exc:
        await UserService.confirm_password_change(session, raw_token)
    assert exc.value.status_code == 400
