from unittest.mock import patch
from utils.hashing import verify_password
from services.users import UserService


async def _setup_pending_change(session, user) -> str:
    """Put user into pending password change state and return the RAW token."""
    import secrets as _secrets
    raw_token = _secrets.token_urlsafe(32)
    with patch("services.users.secrets.token_urlsafe", return_value=raw_token):
        with patch("tasks.emails.send_email_task.delay"):
            await UserService.request_password_change(session, user, "TestPassword123!", "NewPass123!")
    return raw_token


async def test_change_password_success(client, verified_user, session):
    """Test successful password change with valid credentials."""
    # Login to get access token
    response = await client.post("/auth/token", data={
        "username": verified_user.email,
        "password": "TestPassword123!"
    })

    access_token = response.json()["access_token"]

    # Request password change
    with patch("tasks.emails.send_email_task.delay"):
        response = await client.put("/users/me/password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": "TestPassword123!",
                "new_password": "NewSecurePass456!"
            }
        )
    
    assert response.status_code == 200
    assert "confirmation email" in response.json()["message"].lower() or "check your email" in response.json()["message"].lower()
    
    # Verify pending password change is stored
    await session.refresh(verified_user)
    assert verified_user.pending_password_hash is not None
    assert verified_user.password_change_token is not None
    assert verified_user.password_change_expires_at is not None
    
    # Verify new password is stored in pending_password_hash
    assert verify_password("NewSecurePass456!", verified_user.pending_password_hash)
    
    # Verify current password is still active (not changed yet)
    assert verify_password("TestPassword123!", verified_user.hashed_password)


async def test_change_password_wrong_current_password(client, verified_user):
    """Test that password change fails with incorrect current password."""
    # Login to get access token
    response = await client.post("/auth/token", data={
        "username": verified_user.email,
        "password": "TestPassword123!"
    })
    
    access_token = response.json()["access_token"]
    
    # Try to change password with wrong current password
    response = await client.put("/users/me/password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "current_password": "WrongPassword123!",
            "new_password": "NewSecurePass456!"
        }
    )
    
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


async def test_change_password_weak_new_password(client, verified_user):
    """Test that password change fails with weak new password."""
    # Login to get access token
    response = await client.post("/auth/token", data={
        "username": verified_user.email,
        "password": "TestPassword123!"
    })
    
    access_token = response.json()["access_token"]
    
    # Try to change to weak password
    response = await client.put("/users/me/password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "current_password": "TestPassword123!",
            "new_password": "weak"  # Too short, no numbers
        }
    )
    
    # Pydantic validation error
    assert response.status_code == 422


async def test_change_password_unauthenticated(client):
    """Test that password change requires authentication."""
    # Try to change password without token
    response = await client.put("/users/me/password", json={
        "current_password": "TestPassword123!",
        "new_password": "NewSecurePass456!"
    })
    
    assert response.status_code == 401


async def test_change_password_invalid_token(client):
    """Test that password change fails with invalid token."""
    response = await client.put("/users/me/password",
        headers={"Authorization": "Bearer invalid_token"},
        json={
            "current_password": "TestPassword123!",
            "new_password": "NewSecurePass456!"
        }
    )

    assert response.status_code == 401


# --- confirm-password-change ---

async def test_confirm_password_change_success(client, verified_user, session):
    """Valid token in request body applies the pending password change."""
    token = await _setup_pending_change(session, verified_user)

    response = await client.post("/users/confirm-password-change", json={"token": token})

    assert response.status_code == 200
    assert "password updated" in response.json()["message"].lower()


async def test_confirm_password_change_invalid_token(client):
    """Unknown token returns 400."""
    response = await client.post("/users/confirm-password-change", json={"token": "invalidtoken"})

    assert response.status_code == 400


# --- deny-password-change ---

async def test_deny_password_change_success(client, verified_user, session):
    """Valid token in request body cancels the pending password change."""
    token = await _setup_pending_change(session, verified_user)

    with patch("tasks.emails.send_email_task.delay"):
        response = await client.post("/users/deny-password-change", json={"token": token})

    assert response.status_code == 200
    assert "cancelled" in response.json()["message"].lower()


async def test_deny_password_change_invalid_token(client):
    """Unknown token returns 400."""
    response = await client.post("/users/deny-password-change", json={"token": "invalidtoken"})

    assert response.status_code == 400
