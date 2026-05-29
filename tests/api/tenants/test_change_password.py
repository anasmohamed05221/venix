from datetime import datetime, timedelta, timezone
from utils.hashing import verify_password, hash_token

PLAIN_CODE = "847291"


async def _set_pending_code(session, tenant, expired=False):
    """Put the tenant into a pending password change state."""
    delta = -timedelta(seconds=1) if expired else timedelta(minutes=15)
    tenant.password_change_code = hash_token(PLAIN_CODE)
    tenant.password_change_code_expires_at = datetime.now(timezone.utc) + delta
    await session.commit()


async def test_change_password_success(client, test_tenant, session):
    """Valid code and strong new password updates owner_password_hash and clears code fields."""
    await _set_pending_code(session, test_tenant)

    response = await client.post(
        "/tenants/me/change-password",
        json={"code": PLAIN_CODE, "new_password": "NewSecurePass456!"}
    )

    assert response.status_code == 200
    assert "changed" in response.json()["message"].lower()

    await session.refresh(test_tenant)
    assert verify_password("NewSecurePass456!", test_tenant.owner_password_hash)
    assert test_tenant.password_change_code is None
    assert test_tenant.password_change_code_expires_at is None


async def test_change_password_wrong_code(client, test_tenant, session):
    """Wrong code returns 400 and password is not changed."""
    await _set_pending_code(session, test_tenant)
    original_hash = test_tenant.owner_password_hash

    response = await client.post(
        "/tenants/me/change-password",
        json={"code": "000000", "new_password": "NewSecurePass456!"}
    )

    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()

    await session.refresh(test_tenant)
    assert test_tenant.owner_password_hash == original_hash


async def test_change_password_expired_code(client, test_tenant, session):
    """Expired code returns 400."""
    await _set_pending_code(session, test_tenant, expired=True)

    response = await client.post(
        "/tenants/me/change-password",
        json={"code": PLAIN_CODE, "new_password": "NewSecurePass456!"}
    )

    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


async def test_change_password_no_pending_code(client, test_tenant, session):
    """Calling change-password with no code in progress returns 400."""
    response = await client.post(
        "/tenants/me/change-password",
        json={"code": PLAIN_CODE, "new_password": "NewSecurePass456!"}
    )

    assert response.status_code == 400
    assert "no password change" in response.json()["detail"].lower()


async def test_change_password_weak_new_password(client, test_tenant, session):
    """Weak new_password fails Pydantic validation with 422."""
    await _set_pending_code(session, test_tenant)

    response = await client.post(
        "/tenants/me/change-password",
        json={"code": PLAIN_CODE, "new_password": "weak"}
    )

    assert response.status_code == 422


async def test_change_password_requires_auth(client):
    """POST /tenants/me/change-password returns 401 when the API key is invalid."""
    response = await client.post(
        "/tenants/me/change-password",
        json={"code": PLAIN_CODE, "new_password": "NewSecurePass456!"},
        headers={"X-Tenant-API-Key": "vnx_invalid_key"}
    )

    assert response.status_code == 401
