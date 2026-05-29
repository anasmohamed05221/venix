async def test_initiate_success(client, test_tenant, session):
    """Valid current password stores a hashed code in DB and returns 200."""
    response = await client.post(
        "/tenants/me/initiate-change-password",
        json={"current_password": "TestPassword123!"}
    )

    assert response.status_code == 200
    assert "code" in response.json()["message"].lower()

    await session.refresh(test_tenant)
    assert test_tenant.password_change_code is not None
    assert test_tenant.password_change_code_expires_at is not None


async def test_initiate_wrong_password(client, test_tenant, session):
    """Wrong current password returns 401 and no code is stored."""
    response = await client.post(
        "/tenants/me/initiate-change-password",
        json={"current_password": "WrongPassword123!"}
    )

    assert response.status_code == 401

    await session.refresh(test_tenant)
    assert test_tenant.password_change_code is None


async def test_initiate_requires_auth(client):
    """POST /tenants/me/initiate-change-password returns 401 when the API key is invalid."""
    response = await client.post(
        "/tenants/me/initiate-change-password",
        json={"current_password": "TestPassword123!"},
        headers={"X-Tenant-API-Key": "vnx_invalid_key"}
    )

    assert response.status_code == 401
