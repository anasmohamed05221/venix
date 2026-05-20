import pytest
from unittest.mock import patch
from fastapi import HTTPException
from services.users import UserService


async def test_request_password_change_wrong_password(session, verified_user):
    """Raises 401 when current password is incorrect."""
    with pytest.raises(HTTPException) as exc:
        await UserService.request_password_change(session, verified_user, "wrongpassword", "NewPass123!")
    assert exc.value.status_code == 401


async def test_request_password_change_stores_pending_data(session, verified_user):
    """Stores pending hash and token in DB on valid request."""
    with patch("tasks.emails.send_email_task.delay"):
        await UserService.request_password_change(session, verified_user, "TestPassword123!", "NewPass123!")

    await session.refresh(verified_user)
    assert verified_user.pending_password_hash is not None
    assert verified_user.password_change_token is not None
    assert verified_user.password_change_expires_at is not None
