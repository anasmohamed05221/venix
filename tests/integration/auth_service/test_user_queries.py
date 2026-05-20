import pytest
from unittest.mock import patch
from sqlalchemy import select
from models.users import User
from schemas.auth import CreateUserRequest
from services.auth import AuthService


async def test_get_user_by_email(session):
    """Test retrieving a user by email."""
    user_data = CreateUserRequest(
        email="find@example.com",
        first_name="Find",
        last_name="Me",
        password="password123",
        phone_number="+201234567890"
    )
    with patch("tasks.emails.send_email_task.delay"):
        await AuthService.create_user(user_data, session)

    found_user = await session.scalar(select(User).where(User.email == "find@example.com"))

    assert found_user is not None
    assert found_user.email == "find@example.com"
    assert found_user.first_name == "Find"
    assert found_user.last_name == "Me"


async def test_deactivate_user(session):
    """Test deactivating a user account."""
    user_data = CreateUserRequest(
        email="deactivate@example.com",
        first_name="Test",
        last_name="User",
        password="password123",
        phone_number="+201111111111"
    )
    with patch("tasks.emails.send_email_task.delay"):
        created_user = await AuthService.create_user(user_data, session)

    created_user.is_active = False
    await session.commit()

    db_user = await session.scalar(select(User).where(User.id == created_user.id))
    assert db_user.is_active is False

    searched = await AuthService.get_active_user_by_id(session, db_user.id)
    assert searched is None
