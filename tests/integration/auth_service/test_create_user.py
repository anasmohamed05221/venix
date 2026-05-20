import pytest
from unittest.mock import patch
from sqlalchemy import select
from models.users import User
from schemas.auth import CreateUserRequest
from services.auth import AuthService
from fastapi import HTTPException


async def test_create_user(session):
    """Test creating a user in the database."""
    user_data = CreateUserRequest(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        password="SecurePass123!",
        phone_number="+201111111111"
    )
    with patch("tasks.emails.send_email_task.delay"):
        created_user = await AuthService.create_user(user_data, session)

    assert created_user.id is not None
    assert created_user.email == "test@example.com"
    assert created_user.first_name == "Test"
    assert created_user.is_verified is False

    db_user = await session.scalar(select(User).where(User.email == "test@example.com"))
    assert db_user is not None
    assert db_user.email == created_user.email


async def test_create_user_duplicate_email(session):
    """Test that duplicate email registration fails."""
    user_data = CreateUserRequest(
        email="duplicate@example.com",
        first_name="First",
        last_name="User",
        password="password123",
        phone_number="+201111111111"
    )
    with patch("tasks.emails.send_email_task.delay"):
        await AuthService.create_user(user_data, session)
        with pytest.raises(HTTPException) as exc_info:
            await AuthService.create_user(user_data, session)

    assert exc_info.value.status_code == 400
    assert "already registered" in exc_info.value.detail.lower()
