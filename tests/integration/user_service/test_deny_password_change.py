import pytest
from unittest.mock import patch
from fastapi import HTTPException
from services.users import UserService


async def _setup_pending_change(session, user):
    """Helper: put user into pending password change state. Returns the RAW token."""
    import secrets as _secrets
    raw_token = _secrets.token_urlsafe(32)
    with patch("services.users.secrets.token_urlsafe", return_value=raw_token):
        with patch("tasks.emails.send_email_task.delay"):
            await UserService.request_password_change(session, user, "TestPassword123!", "NewPass123!")
    return raw_token


async def test_deny_password_change_clears_fields(session, verified_user):
    """Clears all pending password change fields and revokes tokens."""
    raw_token = await _setup_pending_change(session, verified_user)

    with patch("tasks.emails.send_email_task.delay"):
        await UserService.deny_password_change(session, raw_token)

    await session.refresh(verified_user)
    assert verified_user.pending_password_hash is None
    assert verified_user.password_change_token is None
    assert verified_user.password_change_expires_at is None


async def test_deny_password_change_invalid_token(session, verified_user):
    """Raises 400 for an unknown token."""
    with pytest.raises(HTTPException) as exc:
        await UserService.deny_password_change(session, "invalidtoken")
    assert exc.value.status_code == 400
