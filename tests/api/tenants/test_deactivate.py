async def test_deactivate_success(client, test_tenant, session):
    """Correct password on a verified tenant sets is_active=False in DB."""
    test_tenant.is_verified = True
    await session.commit()

    response = await client.post(
        "/tenants/deactivate",
        json={"password": "TestPassword123!"}
    )

    assert response.status_code == 200
    assert "deactivated" in response.json()["message"].lower()

    await session.refresh(test_tenant)
    assert test_tenant.is_active is False


async def test_deactivate_wrong_password(client, test_tenant, session):
    """Wrong password returns 401 and is_active remains unchanged."""
    test_tenant.is_verified = True
    await session.commit()

    response = await client.post(
        "/tenants/deactivate",
        json={"password": "WrongPassword123!"}
    )

    assert response.status_code == 401

    await session.refresh(test_tenant)
    assert test_tenant.is_active is True


async def test_deactivate_unverified_tenant(client, test_tenant, session):
    """Unverified tenant cannot deactivate — returns 403."""
    assert test_tenant.is_verified is False

    response = await client.post(
        "/tenants/deactivate",
        json={"password": "TestPassword123!"}
    )

    assert response.status_code == 403

    await session.refresh(test_tenant)
    assert test_tenant.is_active is True


async def test_deactivate_requires_auth(client):
    """POST /tenants/deactivate returns 401 when the API key is invalid."""
    response = await client.post(
        "/tenants/deactivate",
        json={"password": "TestPassword123!"},
        headers={"X-Tenant-API-Key": "vnx_invalid_key"}
    )

    assert response.status_code == 401
